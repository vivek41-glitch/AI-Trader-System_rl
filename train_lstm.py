import pandas as pd
import numpy as np
from sb3_contrib import RecurrentPPO
from trading_env import TradingEnvironment
from stable_baselines3.common.callbacks import BaseCallback
import os

# ============================================
# LSTM TRAINING — Agent Gets Memory!
# Remembers last 30 days of patterns
# ============================================

class BestModelCallback(BaseCallback):
    def __init__(self, check_freq=10000):
        super().__init__()
        self.check_freq = check_freq
        self.best_reward = -np.inf

    def _on_step(self):
        if self.n_calls % self.check_freq == 0:
            print(f"📊 Step {self.num_timesteps:,}")
            mean_reward = np.mean([ep['r'] for ep in self.model.ep_info_buffer]) if self.model.ep_info_buffer else 0
            if mean_reward > self.best_reward:
                self.best_reward = mean_reward
                self.model.save("models/ai_trader_lstm_best")
                print(f"💾 Best LSTM model saved! Reward: {mean_reward:.2f}")
        return True

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

print("🧠 LSTM TRAINING — Agent Gets Memory!")
print("=" * 50)

# Load all data
train_frames = []
test_frames = {}

for ticker, name in STOCKS.items():
    # Try multi file first, then indicators file
    for suffix in ['_multi.csv', '_indicators.csv']:
        filepath = f'data/{ticker}{suffix}'
        if os.path.exists(filepath):
            df = pd.read_csv(filepath, index_col=0).dropna()
            if len(df) > 100:
                split = int(len(df) * 0.8)
                train_frames.append(df.iloc[:split])
                test_frames[name] = df.iloc[split:].reset_index(drop=True)
                print(f"✅ Loaded {name} — {len(df)} days")
                break

if not train_frames:
    print("❌ No data found! Run data_collector.py first!")
    exit()

# Combine
combined = pd.concat(train_frames).reset_index(drop=True).dropna()
print(f"\n✅ Total training rows: {len(combined):,}")
print("=" * 50)

# Create environment
train_env = TradingEnvironment(combined, initial_balance=10000)

# Build LSTM agent
print("\n🧠 Building LSTM Agent (has memory!)...")
model = RecurrentPPO(
    "MlpLstmPolicy",
    train_env,
    learning_rate=0.0001,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    ent_coef=0.01,
    verbose=1,
    tensorboard_log="./logs/"
)

print("=" * 50)
print("🚀 Training LSTM Agent!")
print("⏳ Takes 20-25 minutes...")
print("This agent REMEMBERS patterns over time!")
print("=" * 50)

callback = BestModelCallback(check_freq=10000)

model.learn(
    total_timesteps=300000,
    callback=callback,
    progress_bar=True
)

model.save("models/ai_trader_lstm_v1")
print("\n" + "=" * 50)
print("🎉 LSTM TRAINING COMPLETE!")
print("✅ Saved: models/ai_trader_lstm_v1")
print("✅ Saved: models/ai_trader_lstm_best")
print("=" * 50)

# Quick test
print("\n📊 TESTING LSTM AGENT:")
print("=" * 50)

try:
    from sb3_contrib import RecurrentPPO
    lstm_model = RecurrentPPO.load("models/ai_trader_lstm_best")
    total_profit = 0

    for name, df_test in test_frames.items():
        if len(df_test) < 50:
            continue

        env = TradingEnvironment(df_test, initial_balance=10000)
        obs, _ = env.reset()
        done = False
        lstm_states = None
        episode_start = True

        while not done:
            action, lstm_states = lstm_model.predict(
                obs,
                state=lstm_states,
                episode_start=episode_start,
                deterministic=True
            )
            obs, _, done, _, info = env.step(action)
            episode_start = False

        final = info['portfolio_value']
        profit = final - 10000
        ret = (profit / 10000) * 100
        total_profit += profit
        emoji = "✅" if profit > 0 else "❌"
        print(f"{emoji} {name:12} | ${final:>10,.2f} | {ret:>7.2f}%")

    print("=" * 50)
    print(f"💰 TOTAL PROFIT: ${total_profit:,.2f}")
    print("=" * 50)
except Exception as e:
    print(f"⚠️ Test error: {e}")
    print("Model saved successfully — test manually later!")
