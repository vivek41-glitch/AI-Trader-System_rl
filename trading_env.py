import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

class TradingEnvironment(gym.Env):
    def __init__(self, df, initial_balance=10000):
        super(TradingEnvironment, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.window_size = 20
        
        # Actions: 0=Hold, 1=Buy, 2=Sell
        self.action_space = spaces.Discrete(3)
        
        # State: 12 features (added more!)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(12,), dtype=np.float32
        )
        self.reset()

    def reset(self, seed=None):
        self.balance = self.initial_balance
        self.shares = 0
        self.current_step = self.window_size
        self.total_profit = 0
        self.buy_price = 0
        self.trades = []
        self.hold_count = 0
        return self._get_observation(), {}

    def _get_observation(self):
        row = self.df.iloc[self.current_step]
        current_price = row['Close']
        
        # Unrealized profit if holding
        unrealized = 0
        if self.shares > 0 and self.buy_price > 0:
            unrealized = (current_price - self.buy_price) / self.buy_price

        obs = np.array([
            current_price / self.df['Close'].max(),
            row['RSI'] / 100.0,
            row['MACD'] / (abs(self.df['MACD'].max()) + 1e-10),
            row['EMA_20'] / self.df['Close'].max(),
            row['EMA_50'] / self.df['Close'].max(),
            row['BB_Upper'] / self.df['Close'].max(),
            row['BB_Lower'] / self.df['Close'].max(),
            row['Volume'] / (self.df['Volume'].max() + 1e-10),
            self.balance / self.initial_balance,
            float(self.shares > 0),
            unrealized,
            self.hold_count / 100.0
        ], dtype=np.float32)
        return obs

    def step(self, action):
        current_price = self.df.iloc[self.current_step]['Close']
        reward = 0

        # BUY
        if action == 1:
            if self.balance >= current_price and self.shares == 0:
                self.shares = self.balance // current_price
                self.balance -= self.shares * current_price
                self.buy_price = current_price
                self.hold_count = 0
                reward = 0
            else:
                reward = -0.1  # Penalty for invalid buy

        # SELL
        elif action == 2:
            if self.shares > 0:
                sell_value = self.shares * current_price
                profit = sell_value - (self.shares * self.buy_price)
                reward = (profit / self.initial_balance) * 100

                # Bonus for good profit
                if profit > 0:
                    reward += 2.0
                else:
                    reward -= 1.0

                self.balance += sell_value
                self.total_profit += profit
                self.shares = 0
                self.buy_price = 0
                self.hold_count = 0
                self.trades.append(profit)
            else:
                reward = -0.1  # Penalty for invalid sell

        # HOLD
        else:
            if self.shares > 0:
                self.hold_count += 1
                unrealized = (current_price - self.buy_price) / self.buy_price
                # Small reward for holding winners
                if unrealized > 0.02:
                    reward = 0.1
                # Penalty for holding too long
                if self.hold_count > 30:
                    reward = -0.2
            else:
                reward = -0.01  # Small penalty for not being in market

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        portfolio_value = self.balance + (self.shares * current_price)

        return self._get_observation(), reward, done, False, {
            'portfolio_value': portfolio_value,
            'total_profit': self.total_profit
        }

# Test
if __name__ == "__main__":
    print("🎮 Testing Improved Trading Environment...")
    df = pd.read_csv('data/AAPL_indicators.csv', index_col=0)
    env = TradingEnvironment(df)
    obs, _ = env.reset()
    print(f"✅ Environment created!")
    print(f"✅ Observation shape: {obs.shape}")
    print(f"✅ Action space: {env.action_space}")
    print(f"✅ Initial balance: ${env.balance:,.2f}")
    print("🎉 Improved Environment works perfectly!")
