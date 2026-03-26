import yfinance as yf
import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
from risk_manager import RiskManager
import time
from datetime import datetime
import json
import os

print("🤖 AI Paper Trader Starting...")
print("=" * 50)

STOCKS = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN']
INITIAL_BALANCE = 10000
TRADE_LOG_FILE = 'logs/paper_trades.json'

model = PPO.load("models/ai_trader_v2")
rm = RiskManager(initial_balance=INITIAL_BALANCE)

portfolio = {
    'balance': INITIAL_BALANCE,
    'shares': {},
    'buy_prices': {},
    'total_profit': 0,
    'trades': []
}

def get_live_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="60d", interval="1d")
        return hist
    except:
        return None

def prepare_observation(hist_df, symbol):
    import pandas_ta as ta
    df = hist_df.copy()
    df.columns = [c.lower() for c in df.columns]
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['ema_20'] = ta.ema(df['close'], length=20)
    df['ema_50'] = ta.ema(df['close'], length=50)
    bb = ta.bbands(df['close'], length=20)
    bb_cols = bb.columns.tolist()
    df['bb_upper'] = bb[bb_cols[0]]
    df['bb_lower'] = bb[bb_cols[2]]
    df.dropna(inplace=True)
    if len(df) < 2:
        return None
    row = df.iloc[-1]
    current_price = row['close']
    unrealized = 0
    if portfolio['shares'].get(symbol, 0) > 0:
        buy_price = portfolio['buy_prices'].get(symbol, current_price)
        unrealized = (current_price - buy_price) / buy_price
    obs = np.array([
        current_price / df['close'].max(),
        row['rsi'] / 100.0,
        row['macd'] / (abs(df['macd'].max()) + 1e-10),
        row['ema_20'] / df['close'].max(),
        row['ema_50'] / df['close'].max(),
        row['bb_upper'] / df['close'].max(),
        row['bb_lower'] / df['close'].max(),
        row['volume'] / (df['volume'].max() + 1e-10),
        portfolio['balance'] / INITIAL_BALANCE,
        float(portfolio['shares'].get(symbol, 0) > 0),
        unrealized,
        0.0
    ], dtype=np.float32)
    return obs, current_price

def save_trades():
    with open(TRADE_LOG_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2, default=str)

def run_trading_cycle():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🕐 Trading Cycle: {now}")
    print("-" * 40)
    portfolio_value = portfolio['balance']
    for symbol in STOCKS:
        shares_held = portfolio['shares'].get(symbol, 0)
        hist = get_live_data(symbol)
        if hist is None or len(hist) < 50:
            print(f"⚠️ Not enough data for {symbol}")
            continue
        result = prepare_observation(hist, symbol)
        if result is None:
            continue
        obs, current_price = result
        portfolio_value += shares_held * current_price
    rm.update_peak(portfolio_value)
    for symbol in STOCKS:
        hist = get_live_data(symbol)
        if hist is None or len(hist) < 50:
            continue
        result = prepare_observation(hist, symbol)
        if result is None:
            continue
        obs, current_price = result
        can_trade, reason = rm.can_trade(portfolio_value)
        if not can_trade:
            print(f"🛑 {symbol}: {reason}")
            continue
        action, _ = model.predict(obs, deterministic=True)
        action = int(action)
        if action == 1 and portfolio['balance'] >= current_price:
            shares_to_buy = int(portfolio['balance'] * 0.1 // current_price)
            if shares_to_buy > 0:
                cost = shares_to_buy * current_price
                portfolio['balance'] -= cost
                portfolio['shares'][symbol] = portfolio['shares'].get(symbol, 0) + shares_to_buy
                portfolio['buy_prices'][symbol] = current_price
                rm.record_trade()
                trade = {
                    'time': now, 'symbol': symbol, 'action': 'BUY',
                    'shares': shares_to_buy, 'price': current_price,
                    'cost': cost
                }
                portfolio['trades'].append(trade)
                print(f"🟢 BUY {symbol}: {shares_to_buy} shares @ ${current_price:.2f}")
        elif action == 2 and portfolio['shares'].get(symbol, 0) > 0:
            shares_to_sell = portfolio['shares'][symbol]
            revenue = shares_to_sell * current_price
            buy_price = portfolio['buy_prices'].get(symbol, current_price)
            profit = revenue - (shares_to_sell * buy_price)
            portfolio['balance'] += revenue
            portfolio['total_profit'] += profit
            portfolio['shares'][symbol] = 0
            rm.record_trade()
            trade = {
                'time': now, 'symbol': symbol, 'action': 'SELL',
                'shares': shares_to_sell, 'price': current_price,
                'profit': profit
            }
            portfolio['trades'].append(trade)
            print(f"🔴 SELL {symbol}: {shares_to_sell} shares @ ${current_price:.2f} | Profit: ${profit:.2f}")
        else:
            print(f"⏸️ HOLD {symbol} @ ${current_price:.2f}")
    print(f"\n💰 Balance: ${portfolio['balance']:,.2f}")
    print(f"📈 Total Profit: ${portfolio['total_profit']:,.2f}")
    print(f"🏦 Portfolio Value: ${portfolio_value:,.2f}")
    save_trades()

print("✅ Paper Trader Ready!")
print(f"💰 Starting Balance: ${INITIAL_BALANCE:,.2f}")
print("🔄 Running every 60 seconds...")
print("Press Ctrl+C to stop\n")

while True:
    try:
        run_trading_cycle()
        print("\n⏳ Waiting 60 seconds for next cycle...")
        time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 Paper Trader stopped!")
        print(f"Final Balance: ${portfolio['balance']:,.2f}")
        print(f"Total Profit: ${portfolio['total_profit']:,.2f}")
        break
    except Exception as e:
        print(f"⚠️ Error: {e}")
        time.sleep(30)
