import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from trading_env import TradingEnvironment
import os

# ============================================
# IMPROVED TRAINER — Fix The Losers!
# Longer training + better settings
# ============================================

class ProgressCallback(BaseCallback):
    def __init__(self, check_freq=10000):
        super().__init__()
        self.check_freq = check_freq
        self.best_reward = -np.inf

    def _on_step(self):
        if self.n_calls % self.check_freq == 0:
            reward = self.locals.get('infos', [{}])[0].get('total_profit', 0)
            step = self.num_timesteps
            print(f"📊 Step {step:,} | Best so far: ${self.best_reward:,.2f}")
            if reward > self.best_reward:
                self.best_reward = reward
                self.model.save("models/ai_trader_best")
                print(f"💾 New best model saved! ${reward:,.2f}")
        return True

STOCKS = {
    # US Stocks
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    # Indian Stocks
    'TCS_NS': 'TCS',
    'RELIANCE_NS': 'Reliance',
    'INFY_NS': 'Infosys',
    'HDFCBANK_NS': 'HDFC Bank',
    'WIPRO_NS': 'Wipro',
}

print("🚀 IMPROVED TRAINING — Fixing The Losers!")
print("=" * 50)

# Load all available data
train_frames = []
test_frames = {}

for ticker, name in STOCKS.items():
    filepath = f'data/{ticker}_multi.csv'
    if not os.path.exists(filepath):
        print(f"⚠️ Skipping {name} - file not found")
        continue

    df = pd.read_csv(filepath, index_col=0).dropna()
    split = int(len(df) * 0.8)

    train_frames.append(df.iloc[:split])
    test_frames[name] = df.iloc[split:].reset_index(drop=True)
    print(f"✅ Loaded {name} — {len(df)} days")

# Combine training data
combined = pd.concat(train_frames).reset_index(drop=True).dropna()
print(f"\n✅ Total training rows: {len(combined):,}")
print("=" * 50)

# Create environment
train_env = TradingEnvironment(combined, initial_balance=10000)

# Load previous model and continue training (smarter!)
print("\n🧠 Loading previous model to continue training...")
try:
    model = PPO.load("models/ai_trader_multi_v1", env=train_env)
    print("✅ Previous model loaded! Continuing from where we left off!")
except:
    print("⚠️ Starting fresh...")
    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=0.00005,
        n_steps=2048,
        batch_size=128,
        n_epochs=20,
        gamma=0.99,
        ent_coef=0.005,
        verbose=0
    )

# Update learning rate lower for fine-tuning
model.learning_rate = 0.00005

print("\n🔥 Starting improved training...")
print("Training 3x longer than before = much smarter agent!")
print("=" * 50)

callback = ProgressCallback(check_freq=10000)

model.learn(
    total_timesteps=500000,
    callback=callback,
    progress_bar=True,
    reset_num_timesteps=False
)

# Save final model
model.save("models/ai_trader_improved_v2")
print("\n" + "=" * 50)
print("🎉 IMPROVED TRAINING COMPLETE!")
print("✅ Saved: models/ai_trader_improved_v2")
print("✅ Saved: models/ai_trader_best (best version!)")
print("=" * 50)

# Quick test on all stocks
print("\n📊 QUICK RESULTS CHECK:")
print("=" * 50)

model_best = PPO.load("models/ai_trader_best")
total_profit = 0

for name, df_test in test_frames.items():
    if len(df_test) < 50:
        continue

    env = TradingEnvironment(df_test, initial_balance=10000)
    obs, _ = env.reset()
    done = False
    while not done:
        action, _ = model_best.predict(obs, deterministic=True)
        obs, _, done, _, info = env.step(action)

    final = info['portfolio_value']
    profit = final - 10000
    ret = (profit / 10000) * 100
    total_profit += profit
    emoji = "✅" if profit > 0 else "❌"
    print(f"{emoji} {name:12} | ${final:>10,.2f} | {ret:>7.2f}%")

print("=" * 50)
print(f"💰 TOTAL PROFIT: ${total_profit:,.2f}")
print("=" * 50)
