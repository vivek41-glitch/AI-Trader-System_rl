import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from trading_env import TradingEnvironment
import yfinance as yf
import os

# ============================================
# MULTI-STOCK TRAINER (US + Indian Stocks)
# ALL FREE via yfinance!
# ============================================

STOCKS = {
    # US Stocks
    'AAPL': 'Apple',
    'TSLA': 'Tesla', 
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    # Indian Stocks (yfinance uses .NS for NSE)
    'TCS.NS': 'TCS',
    'RELIANCE.NS': 'Reliance',
    'INFY.NS': 'Infosys',
    'HDFCBANK.NS': 'HDFC Bank',
    'WIPRO.NS': 'Wipro',
}

START_DATE = '2015-01-01'
END_DATE = '2025-01-01'

import pandas_ta as ta

def download_and_process(ticker, name):
    print(f"📥 Downloading {name} ({ticker})...")
    try:
        df = yf.download(ticker, start=START_DATE, end=END_DATE, auto_adjust=True)
        if len(df) < 100:
            print(f"⚠️ Not enough data for {name}, skipping...")
            return None

        # Flatten columns if needed
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.columns = [c.strip() for c in df.columns]
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df = df.astype(float)
        df.dropna(inplace=True)

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

        df.dropna(inplace=True)
        safe_name = ticker.replace('.', '_')
        df.to_csv(f'data/{safe_name}_multi.csv')
        print(f"✅ {name} ready! {len(df)} days of data")
        return df
    except Exception as e:
        print(f"❌ Failed {name}: {e}")
        return None

# Download all stocks
print("🚀 Downloading ALL stocks (US + Indian)...")
print("=" * 50)
all_data = {}
for ticker, name in STOCKS.items():
    df = download_and_process(ticker, name)
    if df is not None:
        all_data[ticker] = df

print(f"\n✅ Successfully loaded {len(all_data)} stocks!")
print("=" * 50)

# Combine all training data
print("\n🧠 Combining all stock data for training...")
train_frames = []
for ticker, df in all_data.items():
    split = int(len(df) * 0.8)
    train_frames.append(df.iloc[:split])

combined_train = pd.concat(train_frames).reset_index(drop=True)
combined_train = combined_train.dropna()
print(f"✅ Combined training data: {len(combined_train)} rows!")

# Create environment
print("\n🎮 Creating multi-stock environment...")
train_env = TradingEnvironment(combined_train, initial_balance=10000)

# Build stronger agent
print("🤖 Building Stronger AI Agent...")
model = PPO(
    "MlpPolicy",
    train_env,
    learning_rate=0.0001,
    n_steps=2048,
    batch_size=128,
    n_epochs=15,
    gamma=0.99,
    ent_coef=0.01,
    verbose=1,
    tensorboard_log="./logs/"
)

print("=" * 50)
print("🚀 Training on ALL stocks combined!")
print("⏳ This takes 15-20 minutes...")
print("Watch ep_rew_mean go UP! 📈")
print("=" * 50)

model.learn(total_timesteps=200000, progress_bar=True)

# Save
model.save("models/ai_trader_multi_v1")
print("\n" + "=" * 50)
print("🎉 MULTI-STOCK TRAINING COMPLETE!")
print("✅ Model saved: models/ai_trader_multi_v1")
print("🚀 This agent has seen US + Indian markets!")
print("=" * 50)
