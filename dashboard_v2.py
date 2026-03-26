import streamlit as st
import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import os

st.set_page_config(
    page_title="AI Trader System",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
<style>
.big-profit { font-size: 2.5rem; font-weight: bold; color: #00ff88; }
.big-loss { font-size: 2.5rem; font-weight: bold; color: #ff4444; }
.metric-card {
    background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
    border-radius: 15px;
    padding: 20px;
    border: 1px solid #333;
}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("# 🤖 AI Trader System — Control Center")
st.markdown(f"**Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("---")

STOCKS = {
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    'TCS_NS': 'TCS',
    'RELIANCE_NS': 'Reliance',
    'INFY_NS': 'Infosys',
    'HDFCBANK_NS': 'HDFC Bank',
    'WIPRO_NS': 'Wipro',
}

@st.cache_data
def run_backtest_all():
    model = PPO.load("models/ai_trader_best")
    results = []
    all_curves = {}

    for ticker, name in STOCKS.items():
        filepath = f'data/{ticker}_multi.csv'
        if not os.path.exists(filepath):
            continue
        df = pd.read_csv(filepath, index_col=0).dropna()
        split = int(len(df) * 0.8)
        df_test = df.iloc[split:].reset_index(drop=True)
        if len(df_test) < 50:
            continue

        env = TradingEnvironment(df_test, initial_balance=10000)
        obs, _ = env.reset()
        pvals = [10000]
        actions = []
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, done, _, info = env.step(action)
            pvals.append(info['portfolio_value'])
            actions.append(int(action))

        final = pvals[-1]
        profit = final - 10000
        ret = (profit / 10000) * 100

        results.append({
            'Stock': name,
            'Ticker': ticker,
            'Final': final,
            'Profit': profit,
            'Return': ret,
            'Buys': actions.count(1),
            'Sells': actions.count(2),
        })
        all_curves[name] = pvals

    return results, all_curves

# Load results
with st.spinner("🧠 Running AI analysis on all stocks..."):
    results, curves = run_backtest_all()

df_results = pd.DataFrame(results)

# ── TOP METRICS ──
total_profit = df_results['Profit'].sum()
avg_return = df_results['Return'].mean()
winners = len(df_results[df_results['Profit'] > 0])
best = df_results.loc[df_results['Return'].idxmax()]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 Total Profit (All Stocks)", f"${total_profit:,.2f}",
              f"+{avg_return:.1f}% avg")
with col2:
    st.metric("🏆 Winning Stocks", f"{winners}/{len(results)}",
              "out of 10")
with col3:
    st.metric("🔥 Best Stock", best['Stock'],
              f"+{best['Return']:.1f}%")
with col4:
    st.metric("📅 Test Period", "~2 Years",
              "Real historical data")

st.markdown("---")

# ── PERFORMANCE CHART ──
st.markdown("## 📈 Portfolio Growth — All Stocks")

fig = go.Figure()
colors = ['#00ff88','#ff6b35','#4ecdc4','#45b7d1','#96ceb4',
          '#ffeaa7','#dda0dd','#98d8c8','#f7dc6f','#bb8fce']

for i, (name, pvals) in enumerate(curves.items()):
    color = colors[i % len(colors)]
    final = pvals[-1]
    profit = final - 10000
    fig.add_trace(go.Scatter(
        y=pvals,
        name=f"{name} (${final:,.0f})",
        line=dict(color=color, width=2),
        hovertemplate=f"{name}<br>Value: $%{{y:,.2f}}<extra></extra>"
    ))

fig.add_hline(y=10000, line_dash="dash", line_color="white",
              opacity=0.5, annotation_text="Starting $10,000")
fig.update_layout(
    template="plotly_dark",
    height=450,
    showlegend=True,
    xaxis_title="Trading Days",
    yaxis_title="Portfolio Value ($)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02)
)
st.plotly_chart(fig, use_container_width=True)

# ── STOCK RESULTS TABLE ──
st.markdown("## 🏆 Stock by Stock Results")

col1, col2 = st.columns([2, 1])

with col1:
    # Bar chart
    fig2 = go.Figure()
    colors_bar = ['#00ff88' if r > 0 else '#ff4444'
                  for r in df_results['Return']]
    fig2.add_trace(go.Bar(
        x=df_results['Stock'],
        y=df_results['Return'],
        marker_color=colors_bar,
        text=[f"{r:.1f}%" for r in df_results['Return']],
        textposition='outside'
    ))
    fig2.add_hline(y=0, line_color="white", opacity=0.5)
    fig2.update_layout(
        template="plotly_dark",
        height=350,
        title="Return % by Stock",
        yaxis_title="Return (%)",
        showlegend=False
    )
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.markdown("### 📊 Detailed Results")
    for _, row in df_results.iterrows():
        emoji = "✅" if row['Profit'] > 0 else "❌"
        color = "green" if row['Profit'] > 0 else "red"
        st.markdown(
            f"{emoji} **{row['Stock']}** — "
            f"<span style='color:{color}'>{row['Return']:.1f}%</span> "
            f"(${row['Final']:,.0f})",
            unsafe_allow_html=True
        )

st.markdown("---")

# ── SYSTEM STATUS ──
st.markdown("## 🤖 System Status")
c1, c2, c3 = st.columns(3)
with c1:
    st.success("✅ AI Model: Loaded & Ready")
    st.info("📊 Trained on: 10 Stocks (US + India)")
with c2:
    st.success("✅ Data: 10 Years Historical")
    st.info("🧠 Algorithm: PPO (Deep RL)")
with c3:
    st.success("✅ Status: Paper Trading Mode")
    st.warning("⚠️ Real money: NOT connected (safe!)")

st.markdown("---")
st.markdown(
    "<center>🤖 AI Trader System | Built with RL + Deep Learning | "
    "Paper Trading Only 🛡️</center>",
    unsafe_allow_html=True
)

# ── LIVE PORTFOLIO ──
st.markdown("## 💼 Live Paper Portfolio")

import json
if os.path.exists('logs/paper_portfolio.json'):
    with open('logs/paper_portfolio.json') as f:
        port = json.load(f)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 Cash Balance", f"${port['balance']:,.2f}")
    with c2:
        st.metric("📈 Total Profit", f"${port['total_profit']:,.2f}")
    with c3:
        st.metric("📦 Holdings", f"{len(port['holdings'])} stocks")
    with c4:
        st.metric("📅 Last Updated", port.get('last_updated', 'Never')[:10])
    
    if port['holdings']:
        st.markdown("### Current Holdings:")
        for ticker, h in port['holdings'].items():
            st.info(f"📦 {h['name']} — {h['shares']} shares bought @ ${h['buy_price']:.2f}")
    
    if os.path.exists('logs/paper_trades.json'):
        with open('logs/paper_trades.json') as f:
            trades = json.load(f)
        if trades:
            st.markdown("### Recent Trades:")
            df_trades = pd.DataFrame(trades[-10:])
            st.dataframe(df_trades, use_container_width=True)
else:
    st.info("Run live_trader.py first to see portfolio!")

