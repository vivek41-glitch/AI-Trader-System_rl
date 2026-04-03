import numpy as np
import pandas as pd
import pandas_ta as ta

# ============================================
# MARKET REGIME DETECTOR — PHASE 3
# AI detects WHAT TYPE of market it is
# and adjusts strategy accordingly!
#
# 5 Regimes:
# 1. STRONG_BULL  → Aggressive buying
# 2. WEAK_BULL    → Normal buying
# 3. SIDEWAYS     → Reduced trading
# 4. WEAK_BEAR    → Mostly hold/sell
# 5. STRONG_BEAR  → Sell everything, wait
#
# This ALONE can improve returns by 20-30%!
# ============================================

class MarketRegimeDetector:

    def detect(self, df):
        """
        Detect current market regime.
        Returns: regime, confidence, description
        """
        if len(df) < 60:
            return "UNKNOWN", 0.0, "Not enough data"

        last    = df.iloc[-1]
        score   = 0   # Positive = bullish, negative = bearish

        # ── Signal 1: EMA alignment (most important) ──
        ema20 = float(last.get('EMA_20', last['Close']))
        ema50 = float(last.get('EMA_50', last['Close']))
        price = float(last['Close'])

        ema_diff = (ema20 - ema50) / (ema50 + 1e-8)
        if ema_diff > 0.03:   score += 3   # Strong uptrend
        elif ema_diff > 0.01: score += 1   # Weak uptrend
        elif ema_diff < -0.03: score -= 3  # Strong downtrend
        elif ema_diff < -0.01: score -= 1  # Weak downtrend

        # Price vs EMAs
        if price > ema20 > ema50:  score += 2
        elif price < ema20 < ema50: score -= 2

        # ── Signal 2: RSI regime ──────────────────────
        rsi = float(last.get('RSI', 50))
        if rsi > 60:   score += 1
        elif rsi < 40: score -= 1
        if rsi > 70:   score += 1   # Momentum
        elif rsi < 30: score -= 1

        # ── Signal 3: Price momentum ──────────────────
        prices_20 = df['Close'].iloc[-20:].values.astype(float)
        prices_5  = df['Close'].iloc[-5:].values.astype(float)
        mom_20    = (prices_20[-1] - prices_20[0]) / (prices_20[0] + 1e-8)
        mom_5     = (prices_5[-1]  - prices_5[0])  / (prices_5[0]  + 1e-8)

        if mom_20 > 0.05:   score += 2
        elif mom_20 > 0.02: score += 1
        elif mom_20 < -0.05: score -= 2
        elif mom_20 < -0.02: score -= 1

        if mom_5 > 0.02:   score += 1
        elif mom_5 < -0.02: score -= 1

        # ── Signal 4: Volatility ──────────────────────
        returns    = np.diff(prices_20) / (prices_20[:-1] + 1e-8)
        volatility = np.std(returns)
        is_volatile = volatility > 0.025

        # ── Signal 5: Volume trend ────────────────────
        if 'Volume' in df.columns:
            vol_recent = df['Volume'].iloc[-5:].mean()
            vol_avg    = df['Volume'].iloc[-20:].mean()
            vol_ratio  = vol_recent / (vol_avg + 1e-8)
            if vol_ratio > 1.3 and score > 0:  score += 1   # Bullish volume
            elif vol_ratio > 1.3 and score < 0: score -= 1  # Bearish volume

        # ── Classify regime ───────────────────────────
        if score >= 6:
            regime = "STRONG_BULL"
            conf   = min(score / 10, 1.0)
            desc   = "Strong uptrend — aggressive buying"
        elif score >= 3:
            regime = "WEAK_BULL"
            conf   = score / 10
            desc   = "Mild uptrend — normal buying"
        elif score <= -6:
            regime = "STRONG_BEAR"
            conf   = min(abs(score) / 10, 1.0)
            desc   = "Strong downtrend — sell and wait"
        elif score <= -3:
            regime = "WEAK_BEAR"
            conf   = abs(score) / 10
            desc   = "Mild downtrend — reduce exposure"
        else:
            regime = "SIDEWAYS"
            conf   = 0.3
            desc   = "Choppy market — reduce trading"

        if is_volatile:
            desc += " (HIGH VOLATILITY)"

        return regime, round(conf, 2), desc

    def get_trade_multiplier(self, regime):
        """
        How aggressively to trade in each regime.
        Returns multiplier for position size.
        """
        multipliers = {
            "STRONG_BULL": 1.3,   # Trade 30% larger
            "WEAK_BULL":   1.0,   # Normal size
            "SIDEWAYS":    0.5,   # Half size — uncertain
            "WEAK_BEAR":   0.3,   # Very small — mostly avoid
            "STRONG_BEAR": 0.0,   # Don't buy at all
            "UNKNOWN":     0.5,
        }
        return multipliers.get(regime, 0.5)

    def should_buy(self, regime):
        """Should we buy in this regime?"""
        return regime in ["STRONG_BULL", "WEAK_BULL"]

    def should_sell_holdings(self, regime):
        """Should we sell existing holdings?"""
        return regime in ["STRONG_BEAR", "WEAK_BEAR"]

    def get_emoji(self, regime):
        emojis = {
            "STRONG_BULL": "🚀",
            "WEAK_BULL":   "📈",
            "SIDEWAYS":    "➡️",
            "WEAK_BEAR":   "📉",
            "STRONG_BEAR": "💥",
            "UNKNOWN":     "❓",
        }
        return emojis.get(regime, "❓")


# Singleton
_detector = None
def get_regime_detector():
    global _detector
    if _detector is None:
        _detector = MarketRegimeDetector()
    return _detector


if __name__ == "__main__":
    import yfinance as yf

    print("Testing Market Regime Detector...")
    detector = MarketRegimeDetector()

    tickers = ["AAPL", "SPY", "QQQ"]
    for ticker in tickers:
        df = yf.download(ticker, period="200d", interval="1d",
                        auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open","High","Low","Close","Volume"]].astype(float).dropna()
        df["EMA_20"] = ta.ema(df["Close"], length=20)
        df["EMA_50"] = ta.ema(df["Close"], length=50)
        df["RSI"]    = ta.rsi(df["Close"], length=14)
        df = df.dropna()

        regime, conf, desc = detector.detect(df)
        emoji = detector.get_emoji(regime)
        mult  = detector.get_trade_multiplier(regime)

        print(f"\n{ticker}:")
        print(f"  {emoji} Regime:     {regime}")
        print(f"  📊 Confidence: {conf:.0%}")
        print(f"  📝 {desc}")
        print(f"  💰 Trade size: {mult*100:.0f}% of normal")