import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
from datetime import datetime, timedelta
import os
import json

print("🧠 AUTO RETRAINING SYSTEM")
print("=" * 50)
print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)

STOCKS = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN',
          'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'WIPRO.NS']

def fetch_latest_data(symbol, days=365):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        if len(df) < 30:
            return None
        return df
    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return None

def add_indicators(df):
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        close = df['close'].astype(float)
        volume = df['volume'].astype(float)
        
        df['RSI'] = ta.rsi(close, length=14)
        macd = ta.macd(close)
        df['MACD'] = macd['MACD_12_26_9']
        df['EMA_20'] = ta.ema(close, length=20)
        df['EMA_50'] = ta.ema(close, length=50)
        bb = ta.bbands(close, length=20)
        bb_cols = bb.columns.tolist()
        df['BB_Upper'] = bb[bb_cols[0]]
        df['BB_Lower'] = bb[bb_cols[2]]
        df['Close'] = close
        df['Volume'] = volume
        
        cols = ['Close', 'RSI', 'MACD', 'EMA_20', 'EMA_50', 'BB_Upper', 'BB_Lower', 'Volume']
        df = df[cols]
        df.dropna(inplace=True)
        
        # Normalize to prevent overflow
        for col in df.columns:
            col_max = df[col].abs().max()
            if col_max > 0:
                df[col] = df[col] / col_max
        
        return df
    except Exception as e:
        print(f"⚠️ Indicator error: {e}")
        return None

def retrain_model():
    print("\n📥 STEP 1: Fetching latest market data...")
    all_data = []

    for symbol in STOCKS:
        print(f"  📊 Fetching {symbol}...")
        df = fetch_latest_data(symbol, days=365)
        if df is not None:
            df = add_indicators(df)
            if df is not None and len(df) > 50:
                all_data.append(df)
                print(f"  ✅ {symbol}: {len(df)} days")
            else:
                print(f"  ⚠️ {symbol}: not enough data")
        else:
            print(f"  ❌ {symbol}: failed")

    if not all_data:
        print("❌ No data! Skipping.")
        return False

    print(f"\n✅ Fetched {len(all_data)} stocks!")

    print("\n🔗 STEP 2: Combining data...")
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sample(frac=1).reset_index(drop=True)
    print(f"✅ Combined: {len(combined_df)} rows")

    print("\n🎮 STEP 3: Creating environment...")
    train_env = TradingEnvironment(combined_df, initial_balance=10000)

    print("\n🧠 STEP 4: Building fresh model with latest data...")
    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=0.0003,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=0
    )

    print("\n🚀 STEP 5: Training...")
    print("⏳ Takes 5-10 minutes...")

    model.learn(
        total_timesteps=100000,
        progress_bar=True
    )

    # Backup old model first
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    if os.path.exists("models/ai_trader_v2.zip"):
        import shutil
        shutil.copy("models/ai_trader_v2.zip", f"models/backups/ai_trader_{timestamp}.zip")
        print(f"✅ Old model backed up!")

    # Save new model
    model.save("models/ai_trader_v2")
    print("✅ New model saved!")

    # Log it
    log = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stocks_trained': len(all_data),
        'total_rows': len(combined_df),
        'status': 'success'
    }
    log_file = 'logs/retrain_history.json'
    try:
        with open(log_file, 'r') as f:
            history = json.load(f)
    except:
        history = []
    history.append(log)
    with open(log_file, 'w') as f:
        json.dump(history, f, indent=2)

    return True

def check_if_should_retrain():
    log_file = 'logs/retrain_history.json'
    try:
        with open(log_file, 'r') as f:
            history = json.load(f)
        if not history:
            return True
        last = datetime.strptime(history[-1]['date'], '%Y-%m-%d %H:%M:%S')
        days = (datetime.now() - last).days
        print(f"📅 Last retrain: {days} days ago")
        return days >= 7
    except:
        return True

print("\n🔍 Checking if retraining needed...")
if check_if_should_retrain():
    print("✅ Starting retraining...")
    os.makedirs("models/backups", exist_ok=True)
    if retrain_model():
        print("\n" + "=" * 50)
        print("🎉 RETRAINING COMPLETE!")
        print("🧠 Model updated with latest market data!")
        print("🚀 System is now smarter!")
        print("=" * 50)
else:
    print("⏳ No retraining needed yet!")
