import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
import os
from datetime import datetime

# ============================================
# TRAIN AI ON ALL BEST US STOCKS
# 50 top US stocks — proper diversification
# Run this on your LAPTOP (not Railway)
# Takes 2-3 hours but makes AI much smarter
# ============================================
# HOW TO RUN:
#   python train_all_stocks.py
# ============================================

# 50 Best US Stocks across all sectors
ALL_STOCKS = {
    # Tech Giants
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "AMZN": "Amazon",
    "NVDA": "Nvidia",
    "META": "Meta",
    "TSLA": "Tesla",
    "AMD":  "AMD",
    "INTC": "Intel",
    "CRM":  "Salesforce",
    # Finance
    "JPM":  "JP Morgan",
    "BAC":  "Bank of America",
    "GS":   "Goldman Sachs",
    "V":    "Visa",
    "MA":   "Mastercard",
    "PYPL": "PayPal",
    "COIN": "Coinbase",
    # Healthcare
    "JNJ":  "Johnson & Johnson",
    "PFE":  "Pfizer",
    "MRNA": "Moderna",
    "ABBV": "AbbVie",
    "UNH":  "United Health",
    # Consumer
    "NFLX": "Netflix",
    "DIS":  "Disney",
    "SBUX": "Starbucks",
    "MCD":  "McDonald's",
    "NKE":  "Nike",
    "AMGN": "Amgen",
    # Energy
    "XOM":  "ExxonMobil",
    "CVX":  "Chevron",
    # ETFs (market overview)
    "SPY":  "S&P 500 ETF",
    "QQQ":  "Nasdaq ETF",
    "IWM":  "Russell 2000",
    # Growth
    "SHOP": "Shopify",
    "UBER": "Uber",
    "SNAP": "Snapchat",
    "ROKU": "Roku",
    "SPOT": "Spotify",
    "HOOD": "Robinhood",
    "RBLX": "Roblox",
    # Semiconductors
    "QCOM": "Qualcomm",
    "AVGO": "Broadcom",
    "MU":   "Micron",
    "LRCX": "Lam Research",
    # Cloud
    "SNOW": "Snowflake",
    "DDOG": "Datadog",
    "NET":  "Cloudflare",
    "ZS":   "Zscaler",
    # Others
    "BABA": "Alibaba",
    "TSM":  "TSMC",
}


def download_and_prepare(ticker, name):
    """Download 3 years of data and add indicators."""
    try:
        print(f"  📥 {name} ({ticker})...", end=" ")

        df = yf.download(
            ticker, period="3y", interval="1d",
            auto_adjust=True, progress=False
        )

        if len(df) < 100:
            print("❌ Not enough data")
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Open","High","Low","Close","Volume"]].astype(float).dropna()

        # Full indicator suite
        df["RSI"]         = ta.rsi(df["Close"], length=14)
        macd              = ta.macd(df["Close"])
        df["MACD"]        = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
        df["EMA_20"]      = ta.ema(df["Close"], length=20)
        df["EMA_50"]      = ta.ema(df["Close"], length=50)
        df["EMA_200"]     = ta.ema(df["Close"], length=200)
        bb                = ta.bbands(df["Close"], length=20)
        df["BB_Upper"]    = bb[bb.columns[0]]
        df["BB_Mid"]      = bb[bb.columns[1]]
        df["BB_Lower"]    = bb[bb.columns[2]]
        df["ATR"]         = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        df["Volume_MA"]   = df["Volume"].rolling(20).mean()

        df = df.dropna().reset_index(drop=True)
        print(f"✅ {len(df)} days")
        return df

    except Exception as e:
        print(f"❌ {e}")
        return None


def train_on_all_stocks():
    print("🧠 TRAINING AI ON ALL 50 US STOCKS")
    print("=" * 55)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Stocks: {len(ALL_STOCKS)}")
    print("=" * 55)

    try:
        from stable_baselines3 import PPO
        from trading_env import TradingEnvironment
        import gymnasium as gym
    except ImportError as e:
        print(f"❌ Missing library: {e}")
        print("Run: pip install stable-baselines3 gymnasium")
        return

    # Step 1: Download all data
    print("\n📥 STEP 1: Downloading data for all 50 stocks...")
    all_dfs = []
    failed  = []

    for ticker, name in ALL_STOCKS.items():
        df = download_and_prepare(ticker, name)
        if df is not None:
            all_dfs.append(df)
        else:
            failed.append(ticker)
        import time; time.sleep(0.3)   # Be nice to yfinance

    print(f"\n✅ Got data for {len(all_dfs)}/{len(ALL_STOCKS)} stocks")
    if failed:
        print(f"⚠️ Failed: {', '.join(failed)}")

    if len(all_dfs) < 10:
        print("❌ Not enough data downloaded")
        return

    # Step 2: Combine all into one big training dataset
    print("\n🔗 STEP 2: Combining all data...")
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sample(frac=1).reset_index(drop=True)   # Shuffle!
    print(f"✅ Combined dataset: {len(combined):,} rows")

    # Step 3: Train/test split
    split = int(len(combined) * 0.8)
    df_train = combined.iloc[:split].reset_index(drop=True)
    df_test  = combined.iloc[split:].reset_index(drop=True)
    print(f"✅ Train: {len(df_train):,} | Test: {len(df_test):,}")

    # Step 4: Create environment and train
    print("\n🚀 STEP 3: Training AI... (this takes 1-2 hours)")
    print("Watch ep_rew_mean go UP over time!")
    print("=" * 55)

    os.makedirs("models", exist_ok=True)

    # Wrap environment with normalization — THIS fixes the NaN problem!
    # VecNormalize keeps observations and rewards in a safe range
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.env_checker import check_env

    print("🔍 Checking environment...")
    base_env  = TradingEnvironment(df_train, initial_balance=10000)
    vec_env   = DummyVecEnv([lambda: TradingEnvironment(df_train, initial_balance=10000)])
    train_env = VecNormalize(
        vec_env,
        norm_obs=True,       # Normalize observations to mean=0, std=1
        norm_reward=True,    # Normalize rewards — THIS stops the 3e+05 values!
        clip_obs=10.0,       # Clip observations to [-10, 10]
        clip_reward=10.0,    # Clip rewards to [-10, 10]
    )

    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=0.0003,     # Slightly higher — stable now with normalization
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.05,
        clip_range=0.2,
        max_grad_norm=0.5,        # Gradient clipping — prevents NaN in weights!
        verbose=1,
        tensorboard_log="./logs/"
    )

    model.learn(

        total_timesteps=3_000_000,
        progress_bar=True
    )

    # Save VecNormalize stats too — needed for live trading
    train_env.save("models/vec_normalize.pkl")

    # Save model
    model.save("models/ai_trader_v3_all_stocks")
    print("\n" + "=" * 55)
    print("🎉 TRAINING COMPLETE!")
    print("✅ Model saved: models/ai_trader_v3_all_stocks")
    print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 5: Quick backtest
    print("\n📊 STEP 4: Quick backtest on test data...")
    test_env = TradingEnvironment(df_test, initial_balance=10000)
    obs, _   = test_env.reset()
    done     = False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, _, info = test_env.step(action)

    final_value = info["portfolio_value"]
    profit_pct  = (final_value - 10000) / 10000 * 100

    print(f"✅ Test result: ${final_value:,.2f} ({profit_pct:+.1f}%)")
    print("=" * 55)

    if profit_pct > 0:
        print("🟢 AI is profitable on unseen data! Good sign!")
        model.save("models/ai_trader_best")
        print("✅ Also saved as ai_trader_best (used by live_trader.py)")
    else:
        print("🔴 AI lost on test data — needs more training")
        print("   Try running again with more timesteps")


if __name__ == "__main__":
    train_on_all_stocks()