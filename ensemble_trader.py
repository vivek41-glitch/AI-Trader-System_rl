import numpy as np
import pandas as pd
import pandas_ta as ta

# ============================================
# ENSEMBLE TRADER v2 — RAILWAY COMPATIBLE
# Works WITHOUT stable_baselines3!
# Uses 3 models:
# Model 1: Rule-based Expert (no ML needed)
# Model 2: Momentum Model (no ML needed)
# Model 3: PPO (only if available locally)
# ============================================

class RuleBasedExpert:
    def predict(self, df):
        if len(df) < 50:
            return "HOLD", 0.0
        last   = df.iloc[-1]
        second = df.iloc[-2]
        buy_s  = 0.0
        sell_s = 0.0

        if last['RSI'] < 30:   buy_s  += 0.3
        elif last['RSI'] < 40: buy_s  += 0.1
        if last['RSI'] > 70:   sell_s += 0.3
        elif last['RSI'] > 60: sell_s += 0.1

        if last['MACD'] > last['MACD_Signal'] and second['MACD'] <= second['MACD_Signal']:
            buy_s += 0.25
        elif last['MACD'] < last['MACD_Signal'] and second['MACD'] >= second['MACD_Signal']:
            sell_s += 0.25

        if last['Close'] > last['EMA_20'] > last['EMA_50']:   buy_s  += 0.2
        elif last['Close'] < last['EMA_20'] < last['EMA_50']: sell_s += 0.2

        bb_range = last['BB_Upper'] - last['BB_Lower']
        if bb_range > 0:
            bb_pos = (last['Close'] - last['BB_Lower']) / bb_range
            if bb_pos < 0.1:   buy_s  += 0.15
            elif bb_pos > 0.9: sell_s += 0.15

        price_3ago = df.iloc[-4]['Close'] if len(df) > 4 else last['Close']
        momentum   = (last['Close'] - price_3ago) / (price_3ago + 1e-8)
        if momentum > 0.03:    buy_s  += 0.1
        elif momentum < -0.03: sell_s += 0.1

        avg_vol = df['Volume'].iloc[-10:].mean()
        if last['Volume'] > avg_vol * 1.5:
            if buy_s > sell_s:  buy_s  += 0.1
            else:               sell_s += 0.1

        if 'ATR' in df.columns:
            avg_atr = df['ATR'].mean()
            if avg_atr > 0 and last.get('ATR', 0) > avg_atr * 3:
                return "HOLD", 0.0

        if buy_s >= 0.5 and buy_s > sell_s:
            return "BUY",  round(buy_s, 2)
        elif sell_s >= 0.5 and sell_s > buy_s:
            return "SELL", round(sell_s, 2)
        return "HOLD", 0.0


class MomentumModel:
    def predict(self, df, lookback=14):
        if len(df) < lookback + 5:
            return "HOLD", 0.0

        closes   = df['Close'].values[-lookback:]
        returns  = np.diff(closes) / (closes[:-1] + 1e-8)
        pos_days = np.sum(returns > 0)
        neg_days = np.sum(returns < 0)
        avg_ret  = np.mean(returns)
        vol      = np.std(returns)
        win_rate = pos_days / (pos_days + neg_days + 1e-8)
        sharpe   = avg_ret / (vol + 1e-8)
        recent   = np.mean(returns[-5:])
        older    = np.mean(returns[-14:-5])
        accel    = recent - older
        ema_s    = float(df['EMA_20'].iloc[-1])
        ema_l    = float(df['EMA_50'].iloc[-1])
        trend    = (ema_s - ema_l) / (ema_l + 1e-8)

        buy_s = sell_s = 0.0
        if sharpe > 0.5:    buy_s  += 0.3
        elif sharpe < -0.5: sell_s += 0.3
        if win_rate > 0.6:  buy_s  += 0.2
        elif win_rate < 0.4: sell_s += 0.2
        if accel > 0.005:   buy_s  += 0.2
        elif accel < -0.005: sell_s += 0.2
        if trend > 0.02:    buy_s  += 0.2
        elif trend < -0.02:  sell_s += 0.2
        if avg_ret > 0:     buy_s  += 0.1
        else:               sell_s += 0.1

        if buy_s >= 0.5 and buy_s > sell_s:
            return "BUY",  round(buy_s, 2)
        elif sell_s >= 0.5 and sell_s > buy_s:
            return "SELL", round(sell_s, 2)
        return "HOLD", 0.0


class PPOModel:
    """PPO model — only loads if stable_baselines3 available."""
    def __init__(self, model_path="models/ai_trader_best"):
        self.model  = None
        self.loaded = False
        self.path   = model_path
        self._load()

    def _load(self):
        try:
            from stable_baselines3 import PPO
            from trading_env import TradingEnvironment
            self.model = PPO.load(self.path)
            self.TradingEnvironment = TradingEnvironment
            self.loaded = True
            print(f"✅ PPO model loaded")
        except Exception as e:
            # On Railway — stable_baselines3 not installed, that's OK!
            # Expert + Momentum still vote (2 models instead of 3)
            print(f"ℹ️ PPO not available (Railway mode): {e}")

    def predict(self, df, balance=10000):
        if not self.loaded:
            return "HOLD", 0.0
        try:
            env    = self.TradingEnvironment(df, initial_balance=balance)
            obs, _ = env.reset()
            for _ in range(len(df) - 2):
                action, _ = self.model.predict(obs, deterministic=True)
                obs, _, done, _, _ = env.step(action)
                if done:
                    break
            action, _ = self.model.predict(obs, deterministic=True)
            actions   = {0: "HOLD", 1: "BUY", 2: "SELL"}
            signal    = actions[int(action)]
            return signal, 0.7 if signal != "HOLD" else 0.0
        except:
            return "HOLD", 0.0


class EnsembleTrader:
    """
    3-model ensemble. Works on Railway even without stable_baselines3!
    On Railway: Expert + Momentum vote (need 2/2)
    On laptop:  Expert + Momentum + PPO vote (need 2/3)
    """
    def __init__(self):
        print("🤖 Loading Ensemble...")
        self.expert   = RuleBasedExpert()
        self.momentum = MomentumModel()
        self.ppo      = PPOModel()
        mode = "Full (3 models)" if self.ppo.loaded else "Railway (2 models)"
        print(f"✅ Ensemble ready! Mode: {mode}")

    def vote(self, df, balance=10000, symbol=""):
        exp_signal, exp_conf = self.expert.predict(df)
        mom_signal, mom_conf = self.momentum.predict(df)
        ppo_signal, ppo_conf = self.ppo.predict(df, balance)

        votes = {
            "Expert":   (exp_signal, exp_conf),
            "Momentum": (mom_signal, mom_conf),
        }

        # Only count PPO if loaded
        if self.ppo.loaded:
            votes["PPO"] = (ppo_signal, ppo_conf)

        total_models = len(votes)
        needed       = 2   # Always need at least 2 to agree

        buy_votes  = sum(1 for s, c in votes.values() if s == "BUY")
        sell_votes = sum(1 for s, c in votes.values() if s == "SELL")

        buy_conf  = np.mean([c for s, c in votes.values() if s == "BUY"]  or [0])
        sell_conf = np.mean([c for s, c in votes.values() if s == "SELL"] or [0])

        if buy_votes >= needed:
            final, conf = "BUY",  buy_conf
        elif sell_votes >= needed:
            final, conf = "SELL", sell_conf
        else:
            final, conf = "HOLD", 0.0

        breakdown = {
            "Expert":    exp_signal,
            "Momentum":  mom_signal,
            "PPO":       ppo_signal if self.ppo.loaded else "N/A",
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
            "final":     final,
            "confidence": round(conf, 2)
        }
        return final, conf, breakdown

    def print_breakdown(self, symbol, price, breakdown):
        b = breakdown
        ppo_str = f"PPO: {b['PPO']:4s} | " if b['PPO'] != "N/A" else ""
        print(f"  🗳️  Expert: {b['Expert']:4s} | Momentum: {b['Momentum']:4s} | "
              f"{ppo_str}→ {b['final']} ({b['buy_votes']} buy votes)")


_ensemble = None
def get_ensemble():
    global _ensemble
    if _ensemble is None:
        _ensemble = EnsembleTrader()
    return _ensemble


if __name__ == "__main__":
    print("Testing Ensemble Trader...")
    import yfinance as yf
    df = yf.download("AAPL", period="200d", interval="1d",
                     auto_adjust=True, progress=False)
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
    df = df.dropna().reset_index(drop=True)

    ensemble = EnsembleTrader()
    signal, conf, breakdown = ensemble.vote(df)
    print(f"\nAAPL Result:")
    print(f"  Expert:   {breakdown['Expert']}")
    print(f"  Momentum: {breakdown['Momentum']}")
    print(f"  PPO:      {breakdown['PPO']}")
    print(f"  FINAL:    {signal} ({conf:.0%})")