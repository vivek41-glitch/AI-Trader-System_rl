import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from sb3_contrib import RecurrentPPO
from trading_env import TradingEnvironment
import json
import os
from datetime import datetime

# ============================================
# LIVE PAPER TRADING SYSTEM V3 — LSTM!
# Agent now has MEMORY of past 30 days!
# ============================================

STOCKS = {
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    'NVDA': 'Nvidia',
    'META': 'Meta',
    'NFLX': 'Netflix',
}

PORTFOLIO_FILE = 'logs/paper_portfolio.json'
TRADES_FILE = 'logs/paper_trades.json'
INITIAL_BALANCE = 10000
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 8.0

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {
        'balance': INITIAL_BALANCE,
        'holdings': {},
        'total_profit': 0,
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'last_updated': None
    }

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2)

def load_trades():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    return []

def save_trades(trades):
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def get_live_data(ticker, days=100):
    try:
        df = yf.download(ticker, period=f'{days}d',
                        interval='1d', auto_adjust=True, progress=False)
        if len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.strip() for c in df.columns]
        df = df[['Open','High','Low','Close','Volume']].copy()
        df = df.astype(float).dropna()
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        df['EMA_20'] = ta.ema(df['Close'], length=20)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        bb = ta.bbands(df['Close'], length=20)
        bb_cols = bb.columns.tolist()
        df['BB_Upper'] = bb[bb_cols[0]]
        df['BB_Mid'] = bb[bb_cols[1]]
        df['BB_Lower'] = bb[bb_cols[2]]
        return df.dropna()
    except Exception as e:
        print(f"❌ Error fetching {ticker}: {e}")
        return None

def get_ai_decision(model, df, portfolio):
    try:
        env = TradingEnvironment(df, initial_balance=portfolio['balance'])
        obs, _ = env.reset()
        lstm_states = None
        episode_start = True
        for i in range(len(df) - 2):
            action, lstm_states = model.predict(
                obs,
                state=lstm_states,
                episode_start=episode_start,
                deterministic=True
            )
            obs, _, done, _, _ = env.step(action)
            episode_start = False
            if done:
                break
        action, _ = model.predict(
            obs,
            state=lstm_states,
            episode_start=False,
            deterministic=True
        )
        return {0: 'HOLD', 1: 'BUY', 2: 'SELL'}[int(action)]
    except:
        return 'HOLD'

def execute_sell(portfolio, trades, ticker, name, current_price, reason="AI"):
    holding = portfolio['holdings'][ticker]
    shares = holding['shares']
    sell_value = shares * current_price
    profit = sell_value - holding['cost']
    portfolio['balance'] += sell_value
    portfolio['total_profit'] += profit
    del portfolio['holdings'][ticker]
    trade = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stock': name,
        'action': 'SELL',
        'reason': reason,
        'shares': shares,
        'price': current_price,
        'sell_value': sell_value,
        'profit': profit,
        'balance_after': portfolio['balance']
    }
    trades.append(trade)
    emoji = "💰" if profit > 0 else "📉"
    print(f"   {emoji} [{reason}] SOLD {shares} shares @ ${current_price:.2f} | Profit: ${profit:.2f}")
    return profit

def run_paper_trading():
    print("🤖 AI LIVE PAPER TRADING SYSTEM V3 — LSTM")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🧠 Agent: LSTM (has memory!)")
    print(f"🛡️ Stop Loss: {STOP_LOSS_PCT}% | Take Profit: +{TAKE_PROFIT_PCT}%")
    print("=" * 50)

    model = RecurrentPPO.load("models/ai_trader_lstm_best")
    portfolio = load_portfolio()
    trades = load_trades()

    print(f"💰 Balance: ${portfolio['balance']:,.2f}")
    print(f"📦 Holdings: {len(portfolio['holdings'])} stocks")
    print(f"📈 Total Profit: ${portfolio['total_profit']:,.2f}")
    print("=" * 50)

    daily_profit = 0
    decisions = []

    for ticker, name in STOCKS.items():
        print(f"\n📥 {name}...")
        df = get_live_data(ticker)
        if df is None:
            print(f"   ⚠️ Skipping")
            continue

        current_price = float(df['Close'].iloc[-1])

        # ── STOP LOSS & TAKE PROFIT ──
        if ticker in portfolio['holdings']:
            holding = portfolio['holdings'][ticker]
            buy_price = holding['buy_price']
            change_pct = (current_price - buy_price) / buy_price * 100

            if change_pct <= STOP_LOSS_PCT:
                print(f"   🛑 STOP LOSS triggered! {change_pct:.1f}%")
                profit = execute_sell(portfolio, trades, ticker, name, current_price, "STOP_LOSS")
                daily_profit += profit
                decisions.append(f"🛑 STOP LOSS {name} | {change_pct:.1f}% | ${profit:.2f}")
                continue

            if change_pct >= TAKE_PROFIT_PCT:
                print(f"   🎯 TAKE PROFIT triggered! +{change_pct:.1f}%")
                profit = execute_sell(portfolio, trades, ticker, name, current_price, "TAKE_PROFIT")
                daily_profit += profit
                decisions.append(f"🎯 TAKE PROFIT {name} | +{change_pct:.1f}% | ${profit:.2f}")
                continue

        # ── LSTM AI DECISION ──
        decision = get_ai_decision(model, df, portfolio)
        print(f"   🧠 ${current_price:.2f} → {decision}", end="")

        if decision == 'BUY' and ticker not in portfolio['holdings']:
            invest_amount = portfolio['balance'] * 0.10
            if invest_amount >= current_price:
                shares = int(invest_amount // current_price)
                cost = shares * current_price
                portfolio['balance'] -= cost
                portfolio['holdings'][ticker] = {
                    'shares': shares,
                    'buy_price': current_price,
                    'buy_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'name': name,
                    'cost': cost
                }
                trades.append({
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'stock': name,
                    'action': 'BUY',
                    'reason': 'LSTM_AI',
                    'shares': shares,
                    'price': current_price,
                    'cost': cost,
                    'profit': None,
                    'balance_after': portfolio['balance']
                })
                decisions.append(f"✅ BUY {shares} {name} @ ${current_price:.2f}")
                print(f" → ✅ BOUGHT {shares} shares @ ${current_price:.2f}")
            else:
                print(f" → ⚠️ Not enough balance")

        elif decision == 'SELL' and ticker in portfolio['holdings']:
            profit = execute_sell(portfolio, trades, ticker, name, current_price, "LSTM_AI")
            daily_profit += profit
            decisions.append(f"{'💰' if profit>0 else '📉'} SELL {name} | ${profit:.2f}")

        else:
            if ticker in portfolio['holdings']:
                holding = portfolio['holdings'][ticker]
                change = (current_price - holding['buy_price']) / holding['buy_price'] * 100
                print(f" → ⏸️ HOLD ({change:+.1f}%)")
            else:
                print(f" → ⏸️ HOLD")

    # ── PORTFOLIO VALUE ──
    total_value = portfolio['balance']
    for t, h in portfolio['holdings'].items():
        try:
            live = yf.download(t, period='1d', auto_adjust=True, progress=False)
            if len(live) > 0:
                if isinstance(live.columns, pd.MultiIndex):
                    live.columns = live.columns.get_level_values(0)
                total_value += h['shares'] * float(live['Close'].iloc[-1])
        except:
            total_value += h['cost']

    portfolio['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_portfolio(portfolio)
    save_trades(trades)

    print("\n" + "=" * 50)
    print("📊 SESSION SUMMARY")
    print("=" * 50)
    print(f"💰 Cash Balance:    ${portfolio['balance']:,.2f}")
    print(f"📦 Portfolio Value: ${total_value:,.2f}")
    print(f"📈 Total Profit:    ${portfolio['total_profit']:,.2f}")
    print(f"📅 Today's P/L:     ${daily_profit:,.2f}")
    print(f"🕐 Holdings:        {len(portfolio['holdings'])} stocks")
    print("=" * 50)

    if decisions:
        print("\n🎯 TODAY'S ACTIONS:")
        for d in decisions:
            print(f"   {d}")
    else:
        print("\n⏸️ LSTM AI waiting for right moment...")

    print("\n✅ Done! Run performance_tracker.py to see full report!")

if __name__ == "__main__":
    run_paper_trading()
