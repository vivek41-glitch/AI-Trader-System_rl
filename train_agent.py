import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
import os

print("🧠 Retraining AI Trader with Improved Environment...")
print("=" * 50)

# Load data
df = pd.read_csv('data/AAPL_indicators.csv', index_col=0)

# 80% train, 20% test
split = int(len(df) * 0.8)
df_train = df.iloc[:split].reset_index(drop=True)
df_test = df.iloc[split:].reset_index(drop=True)

print(f"✅ Training data: {len(df_train)} days")
print(f"✅ Testing data:  {len(df_test)} days")

# Create environment
train_env = TradingEnvironment(df_train, initial_balance=10000)

# Build improved PPO agent
model = PPO(
    "MlpPolicy",
    train_env,
    learning_rate=0.0003,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    ent_coef=0.01,
    verbose=1,
    tensorboard_log="./logs/"
)

print("=" * 50)
print("🚀 Training started! Watch ep_rew_mean go UP!")
print("⏳ Takes about 10-15 minutes...")
print("=" * 50)

model.learn(
    total_timesteps=200000,
    progress_bar=True
)

model.save("models/ai_trader_v2")
print("=" * 50)
print("🎉 Training Complete!")
print("✅ Model saved as ai_trader_v2")
print("🚀 Ready for backtesting!")
