import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
import json
import os
from datetime import datetime
import time

# ============================================
# LIVE PAPER TRADING SYSTEM
# Real market prices + Fake money = Safe test
# ============================================

STOCKS = {
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    'TCS.NS': 'TCS',
    'RELIANCE.NS': 'Reliance',
    'INFY.NS': 'Infosys',
    'HDFCBANK.NS': 'HDFC Bank',
    'WIPRO.NS': 'Wipro',
}

PORTFOLIO_FILE = 'logs/paper_portfolio.json'
TRADES_FILE = 'logs/paper_trades.json'
INITIAL_BALANCE = 10000

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
            return json.load(f)
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

        # Add indicators
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

def get_ai_decision(model, df, portfolio, ticker):
    try:
        env = TradingEnvironment(df, initial_balance=portfolio['balance'])
        obs, _ = env.reset()

        # Fast forward to last row
        for i in range(len(df) - 2):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, done, _, _ = env.step(action)
            if done:
                break

        # Get final decision
        action, _ = model.predict(obs, deterministic=True)
        actions = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        return actions[int(action)]
    except:
        return 'HOLD'

def run_paper_trading():
    print("🤖 AI LIVE PAPER TRADING SYSTEM")
    print("=" * 50)
    print(f"⏰ Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # Load model and portfolio
    model = PPO.load("models/ai_trader_best")
    portfolio = load_portfolio()
    trades = load_trades()

    print(f"💰 Current Balance: ${portfolio['balance']:,.2f}")
    print(f"📊 Holdings: {len(portfolio['holdings'])} stocks")
    print(f"📈 Total Profit: ${portfolio['total_profit']:,.2f}")
    print("=" * 50)

    daily_profit = 0
    decisions = []

    for ticker, name in STOCKS.items():
        print(f"\n📥 Fetching live data: {name}...")
        df = get_live_data(ticker)

        if df is None:
            print(f"⚠️ Skipping {name}")
            continue

        current_price = float(df['Close'].iloc[-1])
        decision = get_ai_decision(model, df, portfolio, ticker)

        safe_ticker = ticker.replace('.', '_')
        print(f"🤖 {name}: ${current_price:.2f} → Decision: {decision}")

        # Execute decision
        if decision == 'BUY' and safe_ticker not in portfolio['holdings']:
            # Buy with 10% of balance per stock (diversification!)
            invest_amount = portfolio['balance'] * 0.10
            if invest_amount >= current_price:
                shares = int(invest_amount // current_price)
                cost = shares * current_price
                portfolio['balance'] -= cost
                portfolio['holdings'][safe_ticker] = {
                    'shares': shares,
                    'buy_price': current_price,
                    'buy_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'name': name,
                    'cost': cost
                }
                trade = {
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'stock': name,
                    'action': 'BUY',
                    'shares': shares,
                    'price': current_price,
                    'cost': cost,
                    'profit': None,
                    'balance_after': portfolio['balance']
                }
                trades.append(trade)
                decisions.append(f"✅ BOUGHT {shares} {name} @ ${current_price:.2f}")
                print(f"   ✅ BOUGHT {shares} shares @ ${current_price:.2f}")

        elif decision == 'SELL' and safe_ticker in portfolio['holdings']:
            holding = portfolio['holdings'][safe_ticker]
            shares = holding['shares']
            buy_price = holding['buy_price']
            sell_value = shares * current_price
            profit = sell_value - holding['cost']
            portfolio['balance'] += sell_value
            portfolio['total_profit'] += profit
            daily_profit += profit
            del portfolio['holdings'][safe_ticker]

            trade = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stock': name,
                'action': 'SELL',
                'shares': shares,
                'price': current_price,
                'sell_value': sell_value,
                'profit': profit,
                'balance_after': portfolio['balance']
            }
            trades.append(trade)
            emoji = "💰" if profit > 0 else "📉"
            decisions.append(
                f"{emoji} SOLD {shares} {name} @ ${current_price:.2f} | "
                f"Profit: ${profit:.2f}"
            )
            print(f"   {emoji} SOLD @ ${current_price:.2f} | Profit: ${profit:.2f}")

        else:
            print(f"   ⏸️ HOLDING")

    # Update portfolio value
    total_value = portfolio['balance']
    for safe_ticker, holding in portfolio['holdings'].items():
        ticker_orig = safe_ticker.replace('_NS', '.NS')
        try:
            live = yf.download(ticker_orig, period='1d',
                             auto_adjust=True, progress=False)
            if len(live) > 0:
                if isinstance(live.columns, pd.MultiIndex):
                    live.columns = live.columns.get_level_values(0)
                price = float(live['Close'].iloc[-1])
                total_value += holding['shares'] * price
        except:
            total_value += holding['cost']

    portfolio['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Save everything
    save_portfolio(portfolio)
    save_trades(trades)

    # Summary
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
        print("\n🎯 TODAY'S TRADES:")
        for d in decisions:
            print(f"   {d}")
    else:
        print("\n⏸️ No trades today — AI is waiting for right moment")

    print("\n✅ Portfolio saved!")
    print("🚀 Run dashboard_v2.py to see visual results!")

if __name__ == "__main__":
    run_paper_trading()
