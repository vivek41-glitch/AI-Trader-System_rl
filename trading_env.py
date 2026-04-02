import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces


class TradingEnvironment(gym.Env):
    def __init__(self, df, initial_balance=10000):
        super(TradingEnvironment, self).__init__()
        self.df              = df.reset_index(drop=True)
        self.initial_balance = float(initial_balance)
        self.window_size     = 20
        self.action_space    = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(20,), dtype=np.float32
        )
        self.reset()

    def reset(self, seed=None):
        self.balance      = float(self.initial_balance)
        self.shares       = 0.0
        self.current_step = self.window_size
        self.total_profit = 0.0
        self.buy_price    = 0.0
        self.hold_count   = 0
        self.trades       = []
        self.returns      = []
        self.peak_value   = float(self.initial_balance)
        return self._get_obs(), {}

    def _s(self, v, lo=-5.0, hi=5.0):
        try:
            x = float(v)
            if np.isnan(x) or np.isinf(x):
                return 0.0
            return float(np.clip(x, lo, hi))
        except:
            return 0.0

    def _get_obs(self):
        row  = self.df.iloc[self.current_step]
        prev = self.df.iloc[self.current_step - 1]
        p    = self._s(row['Close'], 0, 1e9)

        unrealized = 0.0
        if self.shares > 0 and self.buy_price > 0:
            unrealized = self._s((p - self.buy_price) / (self.buy_price + 1e-8))

        p5  = self._s(self.df['Close'].iloc[self.current_step - 5])
        p10 = self._s(self.df['Close'].iloc[self.current_step - 10])
        mom5  = self._s((p - p5)  / (p5  + 1e-8))
        mom10 = self._s((p - p10) / (p10 + 1e-8))

        rp   = self.df['Close'].iloc[self.current_step-10:self.current_step].values.astype(float)
        vol  = self._s(np.std(rp) / (np.mean(rp) + 1e-8), 0, 2)

        va   = self.df['Volume'].iloc[self.current_step-5:self.current_step].mean()
        vt   = self._s(float(row['Volume']) / (float(va) + 1e-8) / 10.0, 0, 2)

        cmax = float(self.df['Close'].max()) + 1e-8
        mmax = float(abs(self.df['MACD'].max())) + 1e-8
        smax = float(abs(self.df['MACD_Signal'].max())) + 1e-8
        ediff = self._s((float(row['EMA_20']) - float(row['EMA_50'])) / (float(row['EMA_50']) + 1e-8))

        pv    = float(np.clip(self.balance + self.shares * p, 0, 1e9))
        dd    = self._s((self.peak_value - pv) / (self.peak_value + 1e-8), -1, 0)
        pchg  = self._s((p - float(prev['Close'])) / (float(prev['Close']) + 1e-8))
        rsi3  = self.df['RSI'].iloc[max(0, self.current_step-3)]
        rsim  = self._s((float(row['RSI']) - float(rsi3)) / 100.0)

        obs = np.array([
            self._s(p / cmax, 0, 2),
            self._s(float(row['RSI']) / 100.0, 0, 1),
            self._s(float(row['MACD']) / mmax, -5, 5),
            self._s(float(row['MACD_Signal']) / smax, -5, 5),
            self._s(float(row['EMA_20']) / cmax, 0, 2),
            self._s(float(row['EMA_50']) / cmax, 0, 2),
            self._s(float(row['BB_Upper']) / cmax, 0, 2),
            self._s(float(row['BB_Lower']) / cmax, 0, 2),
            mom5, mom10, vol, vt, ediff,
            self._s(self.balance / (self.initial_balance + 1e-8), 0, 5),
            float(self.shares > 0),
            unrealized,
            self._s(self.hold_count / 100.0, 0, 1),
            dd, pchg, rsim,
        ], dtype=np.float32)

        return np.nan_to_num(obs, nan=0.0, posinf=1.0, neginf=-1.0)

    def step(self, action):
        p = float(self.df.iloc[self.current_step]['Close'])
        if p <= 0 or np.isnan(p) or np.isinf(p):
            p = 1.0

        reward = 0.0
        pv = float(np.clip(self.balance + self.shares * p, 0, 1e9))
        if pv > self.peak_value:
            self.peak_value = pv

        if action == 1:  # BUY
            if self.balance >= p and self.shares == 0:
                invest       = float(np.clip(self.balance * 0.10, 0, self.balance))
                self.shares  = float(int(invest // p))
                cost         = self.shares * p
                self.balance = float(np.clip(self.balance - cost, 0, 1e9))
                self.buy_price  = p
                self.hold_count = 0
                reward = 0.0
            else:
                reward = -0.1

        elif action == 2:  # SELL
            if self.shares > 0 and self.buy_price > 0:
                sv  = float(np.clip(self.shares * p, 0, 1e9))
                bv  = float(np.clip(self.shares * self.buy_price, 0, 1e9))
                pct = float(np.clip((sv - bv) / (bv + 1e-8), -1.0, 1.0))
                reward = float(np.clip(pct * 10, -5.0, 5.0))
                if pct > 0.05 and self.hold_count < 20:
                    reward += 0.5
                if pct < 0 and self.hold_count > 15:
                    reward -= 0.5
                self.balance      = float(np.clip(self.balance + sv, 0, 1e9))
                self.total_profit = float(np.clip(self.total_profit + sv - bv, -1e9, 1e9))
                self.shares       = 0.0
                self.buy_price    = 0.0
                self.hold_count   = 0
                self.trades.append(pct)
            else:
                reward = -0.1

        else:  # HOLD
            if self.shares > 0 and self.buy_price > 0:
                self.hold_count += 1
                u = float(np.clip((p - self.buy_price) / (self.buy_price + 1e-8), -1, 1))
                if u > 0.08:    reward =  0.2
                elif u > 0.02:  reward =  0.05
                elif u < -0.05: reward = -0.3
                else:           reward = -0.02
                if self.hold_count > 40:
                    reward -= 0.2
            else:
                reward = -0.01

        if self.peak_value > 0:
            dd = float(np.clip((self.peak_value - pv) / (self.peak_value + 1e-8), 0, 1))
            if dd > 0.10:
                reward -= float(np.clip(dd * 2, 0, 2.0))

        reward = float(np.clip(reward, -5.0, 5.0))
        if np.isnan(reward) or np.isinf(reward):
            reward = 0.0

        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        return self._get_obs(), reward, done, False, {
            'portfolio_value': pv,
            'total_profit':    self.total_profit,
            'trades':          len(self.trades)
        }


if __name__ == "__main__":
    print("Testing Trading Environment v3...")
    df = pd.read_csv('data/AAPL_indicators.csv', index_col=0)
    env = TradingEnvironment(df)
    obs, _ = env.reset()
    print(f"Shape: {obs.shape}")
    print(f"Any NaN: {np.any(np.isnan(obs))}")
    print("Done!")