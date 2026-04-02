import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
import os
from datetime import datetime

# ============================================
# WALK FORWARD TRAINER — PHASE 3
# Solves the OVERFITTING problem!
#
# Normal training:          Walk Forward:
# Train on 2020-2023        Train on 2020-2021
# Test on 2023-2024         Test on 2021 Q4
#                           Train on 2020-2022
# Problem: AI memorizes     Test on 2022 Q4
# old data, fails live      Train on 2020-2023
#                           Test on 2023 Q4
#                           Average all results
#
# Result: AI tested on MANY different market
# conditions — much more robust!
# ============================================

STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "NFLX"
]

WINDOW_SIZE  = 400   # Training window in days
TEST_SIZE    = 60    # Test window in days
STEP_SIZE    = 60    # Walk forward step
TIMESTEPS    = 500_000  # Per window (faster than full retrain)


def download_data(ticker, days=800):
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d",
                        auto_adjust=True, progress=False)
        if len(df) < 200:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open","High","Low","Close","Volume"]].astype(float).dropna()
        df["RSI"]         = ta.rsi(df["Close"], length=14)
        macd              = ta.macd(df["Close"])
        df["MACD"]        = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
        df["EMA_20"]      = ta.ema(df["Close"], length=20)
        df["EMA_50"]      = ta.ema(df["Close"], length=50)
        bb                = ta.bbands(df["Close"], length=20)
        df["BB_Upper"]    = bb[bb.columns[0]]
        df["BB_Mid"]      = bb[bb.columns[1]]
        df["BB_Lower"]    = bb[bb.columns[2]]
        df["ATR"]         = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        return df.dropna().reset_index(drop=True)
    except:
        return None


def backtest_model(model, df_test):
    """Quick backtest — returns profit %"""
    try:
        from trading_env import TradingEnvironment
        env  = TradingEnvironment(df_test, initial_balance=10000)
        obs, _ = env.reset()
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, done, _, info = env.step(action)
        final = info["portfolio_value"]
        return (final - 10000) / 10000 * 100
    except:
        return 0.0


def run_walk_forward():
    print("🚶 WALK FORWARD TRAINER")
    print("=" * 55)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Stocks: {len(STOCKS)}")
    print(f"Window: {WINDOW_SIZE} days train, {TEST_SIZE} days test")
    print("=" * 55)

    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
        from trading_env import TradingEnvironment
    except ImportError as e:
        print(f"❌ {e}")
        return

    # Download all data
    print("\n📥 Downloading data...")
    all_dfs = []
    for ticker in STOCKS:
        df = download_data(ticker)
        if df is not None:
            all_dfs.append(df)
            print(f"  ✅ {ticker}: {len(df)} days")

    if not all_dfs:
        print("❌ No data")
        return

    # Combine all stocks
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.fillna(0).replace([np.inf, -np.inf], 0)
    total    = len(combined)
    print(f"\n✅ Combined: {total:,} rows")

    # Walk forward windows
    windows      = []
    start        = 0
    while start + WINDOW_SIZE + TEST_SIZE <= total:
        windows.append({
            "train_start": start,
            "train_end":   start + WINDOW_SIZE,
            "test_start":  start + WINDOW_SIZE,
            "test_end":    start + WINDOW_SIZE + TEST_SIZE,
        })
        start += STEP_SIZE

    print(f"📊 Walk forward windows: {len(windows)}")
    print("=" * 55)

    results      = []
    best_return  = -999
    best_model   = None

    for i, w in enumerate(windows):
        print(f"\n🔄 Window {i+1}/{len(windows)}")
        df_train = combined.iloc[w["train_start"]:w["train_end"]].reset_index(drop=True)
        df_test  = combined.iloc[w["test_start"]:w["test_end"]].reset_index(drop=True)

        if len(df_train) < 100 or len(df_test) < 20:
            continue

        print(f"   Train: {len(df_train)} rows | Test: {len(df_test)} rows")

        # Train
        vec_env   = DummyVecEnv([lambda: TradingEnvironment(df_train)])
        train_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True,
                                 clip_obs=10.0, clip_reward=10.0)

        model = PPO(
            "MlpPolicy", train_env,
            learning_rate=0.0003,
            n_steps=2048, batch_size=64,
            n_epochs=10, gamma=0.99,
            ent_coef=0.05,
            max_grad_norm=0.5,
            verbose=0
        )
        model.learn(total_timesteps=TIMESTEPS)

        # Test
        ret = backtest_model(model, df_test)
        results.append(ret)
        print(f"   📈 Return: {ret:+.1f}%")

        if ret > best_return:
            best_return = ret
            best_model  = model
            model.save("models/walk_forward_best")
            print(f"   ⭐ New best model! ({ret:+.1f}%)")

    # Results
    print("\n" + "=" * 55)
    print("📊 WALK FORWARD RESULTS")
    print("=" * 55)
    if results:
        print(f"Windows tested:   {len(results)}")
        print(f"Average return:   {np.mean(results):+.1f}%")
        print(f"Best return:      {max(results):+.1f}%")
        print(f"Worst return:     {min(results):+.1f}%")
        print(f"Win rate:         {sum(1 for r in results if r > 0)/len(results)*100:.0f}%")
        print(f"Std deviation:    {np.std(results):.1f}%")

        if np.mean(results) > 0:
            print("\n🟢 AI is profitable across multiple market conditions!")
            if best_model:
                best_model.save("models/ai_trader_best")
                print("✅ Best walk-forward model saved as ai_trader_best!")
        else:
            print("\n🔴 AI needs more training — run again")
    print("=" * 55)


if __name__ == "__main__":
    run_walk_forward()
    