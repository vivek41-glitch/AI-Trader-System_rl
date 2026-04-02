import numpy as np

# ============================================
# POSITION SIZER — PHASE 3
# AI decides HOW MUCH to invest per trade
# Based on confidence + volatility + portfolio
#
# Before: Always invest 10% per trade
# After:  High confidence = 15%, low = 5%
#         High volatility = smaller position
#         On winning streak = slightly bigger
#         On losing streak = much smaller
# ============================================

class PositionSizer:
    def __init__(self, base_pct=0.10, max_pct=0.20, min_pct=0.03):
        self.base_pct    = base_pct   # Default 10%
        self.max_pct     = max_pct    # Never more than 20%
        self.min_pct     = min_pct    # Never less than 3%
        self.win_streak  = 0
        self.lose_streak = 0
        self.recent_pnl  = []

    def calculate(self, balance, confidence, volatility_pct,
                  signal_strength=1.0, recent_profit=None):
        """
        Calculate optimal position size.

        Args:
            balance:         Current portfolio balance
            confidence:      Model confidence 0.0-1.0
            volatility_pct:  ATR as % of price (0.01 = 1%)
            signal_strength: How many models agreed (1-3)
            recent_profit:   Last trade profit % (None if first)

        Returns:
            invest_amount:   Dollar amount to invest
            position_pct:    % of portfolio used
            reason:          Why this size was chosen
        """
        pct = self.base_pct

        # ── Confidence adjustment ─────────────────────
        # Higher confidence = bigger position
        if confidence >= 0.8:
            pct += 0.05    # +5% for very high confidence
        elif confidence >= 0.6:
            pct += 0.02    # +2% for good confidence
        elif confidence < 0.4:
            pct -= 0.03    # -3% for low confidence

        # ── Ensemble agreement bonus ───────────────────
        # More models agreeing = bigger position
        if signal_strength >= 3:
            pct += 0.04    # All 3 models agree!
        elif signal_strength == 2:
            pct += 0.01    # 2 models agree

        # ── Volatility adjustment ──────────────────────
        # Higher volatility = smaller position (more risk)
        if volatility_pct > 0.03:    # Very volatile
            pct -= 0.05
        elif volatility_pct > 0.02:  # Moderately volatile
            pct -= 0.02
        elif volatility_pct < 0.01:  # Low volatility
            pct += 0.01

        # ── Streak adjustment ──────────────────────────
        if self.win_streak >= 3:
            pct += 0.02    # Small increase on winning streak
        elif self.lose_streak >= 2:
            pct -= 0.04    # Reduce on losing streak
        elif self.lose_streak >= 4:
            pct -= 0.07    # Significantly reduce after bad run

        # ── Kelly Criterion simplified ─────────────────
        # If we have recent trade history
        if len(self.recent_pnl) >= 5:
            wins      = [p for p in self.recent_pnl if p > 0]
            losses    = [p for p in self.recent_pnl if p <= 0]
            win_rate  = len(wins) / len(self.recent_pnl)
            avg_win   = np.mean(wins)   if wins   else 0
            avg_loss  = abs(np.mean(losses)) if losses else 1

            # Kelly fraction
            if avg_loss > 0:
                kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss + 1e-8)
                kelly = np.clip(kelly * 0.25, 0, 0.15)  # Use 25% of Kelly
                pct   = (pct + kelly) / 2  # Blend with current size

        # ── Hard limits ────────────────────────────────
        pct = float(np.clip(pct, self.min_pct, self.max_pct))

        invest = balance * pct

        # Reason string
        reasons = []
        if confidence >= 0.8:   reasons.append("high confidence")
        if signal_strength >= 3: reasons.append("all models agree")
        if volatility_pct > 0.03: reasons.append("reduced for volatility")
        if self.lose_streak >= 2: reasons.append("reduced after losses")
        if self.win_streak >= 3:  reasons.append("boosted on win streak")
        reason = ", ".join(reasons) if reasons else "standard sizing"

        return round(invest, 2), round(pct * 100, 1), reason

    def record_trade(self, profit_pct):
        """Record trade outcome to improve future sizing."""
        self.recent_pnl.append(profit_pct)
        if len(self.recent_pnl) > 20:
            self.recent_pnl.pop(0)

        if profit_pct > 0:
            self.win_streak  += 1
            self.lose_streak  = 0
        else:
            self.lose_streak += 1
            self.win_streak   = 0

    def get_stats(self):
        if not self.recent_pnl:
            return {}
        wins = [p for p in self.recent_pnl if p > 0]
        return {
            "win_rate":    round(len(wins) / len(self.recent_pnl) * 100, 1),
            "win_streak":  self.win_streak,
            "lose_streak": self.lose_streak,
            "avg_return":  round(np.mean(self.recent_pnl) * 100, 2),
            "total_trades": len(self.recent_pnl)
        }


if __name__ == "__main__":
    print("Testing Position Sizer...")
    ps = PositionSizer()

    balance     = 100000
    test_cases  = [
        (0.8, 0.01, 3, "High confidence, low vol, all agree"),
        (0.5, 0.02, 2, "Medium confidence, medium vol"),
        (0.3, 0.04, 1, "Low confidence, high vol, only 1 model"),
        (0.9, 0.005, 3, "Very high confidence, very low vol"),
    ]

    print(f"\n{'Case':<45} {'Amount':>10} {'Pct':>6} {'Reason'}")
    print("-" * 80)
    for conf, vol, strength, desc in test_cases:
        amt, pct, reason = ps.calculate(balance, conf, vol, strength)
        print(f"{desc:<45} ${amt:>9,.0f} {pct:>5.1f}% {reason}")

    # Simulate losing streak
    print("\nSimulating 3 consecutive losses...")
    for _ in range(3):
        ps.record_trade(-0.05)
    amt, pct, reason = ps.calculate(balance, 0.7, 0.015, 2)
    print(f"After 3 losses: ${amt:,.0f} ({pct}%) — {reason}")

    print("\n✅ Position Sizer working!")