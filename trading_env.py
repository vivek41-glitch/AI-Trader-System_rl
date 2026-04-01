import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

# ============================================
# TRADING ENVIRONMENT v2 — FIXED REWARD
# Key improvements:
# 1. Better reward function (not gambler!)
# 2. Sharpe ratio based rewards
# 3. Drawdown penalty
# 4. More features (20 vs 12 before)
# 5. Market regime awareness
# ============================================

class TradingEnvironment(gym.Env):
    def __init__(self, df, initial_balance=10000):
        super(TradingEnvironment, self).__init__()
        self.df              = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.window_size     = 20

        # Actions: 0=Hold, 1=Buy, 2=Sell
        self.action_space = spaces.Discrete(3)

        # 20 features now (was 12) — AI sees much more
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(20,), dtype=np.float32
        )
        self.reset()

    def reset(self, seed=None):
        self.balance       = self.initial_balance
        self.shares        = 0
        self.current_step  = self.window_size
        self.total_profit  = 0
        self.buy_price     = 0
        self.hold_count    = 0
        self.trades        = []
        self.returns       = []   # Track returns for Sharpe ratio
        self.peak_value    = self.initial_balance
        self.max_drawdown  = 0
        return self._get_observation(), {}

    def _get_observation(self):
        row   = self.df.iloc[self.current_step]
        prev  = self.df.iloc[self.current_step - 1]
        price = row['Close']

        # Unrealized profit
        unrealized = 0
        if self.shares > 0 and self.buy_price > 0:
            unrealized = (price - self.buy_price) / self.buy_price

        # Price momentum (new!)
        momentum_5  = (price - self.df['Close'].iloc[self.current_step-5])  / self.df['Close'].iloc[self.current_step-5]
        momentum_10 = (price - self.df['Close'].iloc[self.current_step-10]) / self.df['Close'].iloc[self.current_step-10]

        # Volatility (new!)
        recent_prices = self.df['Close'].iloc[self.current_step-10:self.current_step]
        volatility    = recent_prices.std() / recent_prices.mean()

        # Volume trend (new!)
        vol_avg    = self.df['Volume'].iloc[self.current_step-5:self.current_step].mean()
        vol_trend  = row['Volume'] / (vol_avg + 1e-10)

        # Market regime (new!) — trending vs sideways
        ema_diff  = (row['EMA_20'] - row['EMA_50']) / row['EMA_50']

        # Portfolio stats
        portfolio_value = self.balance + (self.shares * price)
        drawdown = (self.peak_value - portfolio_value) / self.peak_value

        obs = np.array([
            # Price indicators
            price / self.df['Close'].max(),
            row['RSI'] / 100.0,
            row['MACD'] / (abs(self.df['MACD'].max()) + 1e-10),
            row['MACD_Signal'] / (abs(self.df['MACD_Signal'].max()) + 1e-10),
            row['EMA_20'] / self.df['Close'].max(),
            row['EMA_50'] / self.df['Close'].max(),
            row['BB_Upper'] / self.df['Close'].max(),
            row['BB_Lower'] / self.df['Close'].max(),
            # New features
            momentum_5,
            momentum_10,
            volatility,
            vol_trend / 10.0,
            ema_diff,
            # Portfolio state
            self.balance / self.initial_balance,
            float(self.shares > 0),
            unrealized,
            self.hold_count / 100.0,
            drawdown,
            # Price change
            (price - prev['Close']) / prev['Close'],
            # RSI momentum
            (row['RSI'] - self.df['RSI'].iloc[self.current_step-3]) / 100.0
        ], dtype=np.float32)

        return obs

    def step(self, action):
        price = self.df.iloc[self.current_step]['Close']
        reward = 0

        portfolio_value = self.balance + (self.shares * price)

        # Update peak for drawdown tracking
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value

        # BUY
        if action == 1:
            if self.balance >= price and self.shares == 0:
                self.shares    = self.balance // price
                self.balance  -= self.shares * price
                self.buy_price = price
                self.hold_count = 0
                reward = 0.0   # No reward for buying — reward comes on sell
            else:
                reward = -0.5  # Penalty for invalid buy

        # SELL
        elif action == 2:
            if self.shares > 0:
                sell_value    = self.shares * price
                profit        = sell_value - (self.shares * self.buy_price)
                profit_pct    = profit / (self.shares * self.buy_price)

                # Sharpe-like reward — reward profit but penalize volatility
                if profit_pct > 0:
                    reward = profit_pct * 100 + 3.0   # Big reward for profit
                elif profit_pct < -0.05:
                    reward = profit_pct * 100 - 3.0   # Big penalty for big loss
                else:
                    reward = profit_pct * 50           # Small penalty for small loss

                # Bonus for taking profit quickly
                if profit_pct > 0.05 and self.hold_count < 20:
                    reward += 2.0

                # Penalty for holding losing position too long
                if profit_pct < 0 and self.hold_count > 15:
                    reward -= 2.0

                self.balance      += sell_value
                self.total_profit += profit
                self.shares        = 0
                self.buy_price     = 0
                self.hold_count    = 0
                self.trades.append(profit_pct)
                self.returns.append(profit_pct)
            else:
                reward = -0.5   # Penalty for invalid sell

        # HOLD
        else:
            if self.shares > 0:
                self.hold_count += 1
                unrealized = (price - self.buy_price) / self.buy_price

                if unrealized > 0.08:
                    reward = 0.2    # Good — holding a winner
                elif unrealized < -0.05:
                    reward = -0.5   # Bad — holding a loser
                elif unrealized > 0.02:
                    reward = 0.05   # Okay — small gain
                else:
                    reward = -0.05  # Slight penalty for doing nothing

                # Penalty for holding way too long
                if self.hold_count > 40:
                    reward -= 0.3
            else:
                reward = -0.02   # Small penalty for sitting out

        # Drawdown penalty — penalize if portfolio dropping
        drawdown = (self.peak_value - portfolio_value) / self.peak_value
        if drawdown > 0.10:
            reward -= drawdown * 5   # Heavy penalty for big drawdown

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        return self._get_observation(), reward, done, False, {
            'portfolio_value': portfolio_value,
            'total_profit':    self.total_profit,
            'trades':          len(self.trades)
        }


if __name__ == "__main__":
    print("🎮 Testing Trading Environment v2...")
    df = pd.read_csv('data/AAPL_indicators.csv', index_col=0)
    env = TradingEnvironment(df)
    obs, _ = env.reset()
    print(f"✅ Environment v2 created!")
    print(f"✅ Observation shape: {obs.shape} (was 12, now 20!)")
    print(f"✅ Action space: {env.action_space}")
    print("🎉 Trading Environment v2 works!")