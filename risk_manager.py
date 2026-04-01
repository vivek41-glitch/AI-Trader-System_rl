# ============================================
# RISK MANAGER v2 — NOW ACTUALLY CONNECTED!
# Used by ALL 3 traders automatically
# ============================================

class RiskManager:
    def __init__(self, initial_balance=10000):
        self.initial_balance  = initial_balance
        self.peak_value       = initial_balance
        self.daily_start      = initial_balance
        self.trades_today     = 0

        # Risk limits
        self.max_risk_per_trade  = 0.10   # Max 10% per trade
        self.stop_loss_pct       = 0.05   # Stop loss at -5%
        self.take_profit_pct     = 0.08   # Take profit at +8%
        self.max_daily_loss      = 0.15   # Stop all trading if down 15% today
        self.max_drawdown        = 0.25   # Stop all trading if down 25% from peak
        self.max_trades_per_day  = 15     # Max 15 trades per day

    def update_peak(self, value):
        if value > self.peak_value:
            self.peak_value = value

    def new_day(self, value):
        self.daily_start  = value
        self.trades_today = 0
        print("🔄 Risk Manager: New day reset")

    def can_trade(self, current_value):
        """Check if trading is allowed right now."""
        # Check max drawdown
        drawdown = (self.peak_value - current_value) / self.peak_value
        if drawdown >= self.max_drawdown:
            return False, f"🛑 DRAWDOWN LIMIT! Down {drawdown*100:.1f}% from peak. Trading paused."

        # Check daily loss
        daily_loss = (self.daily_start - current_value) / self.daily_start
        if daily_loss >= self.max_daily_loss:
            return False, f"🛑 DAILY LOSS LIMIT! Down {daily_loss*100:.1f}% today. Trading paused."

        # Check trade count
        if self.trades_today >= self.max_trades_per_day:
            return False, f"🛑 MAX TRADES REACHED! {self.trades_today} trades today."

        return True, "✅ Trading allowed"

    def should_stop_loss(self, buy_price, current_price):
        """Return True if position should be stopped out."""
        loss_pct = (current_price - buy_price) / buy_price
        return loss_pct <= -self.stop_loss_pct

    def should_take_profit(self, buy_price, current_price):
        """Return True if position should take profit."""
        gain_pct = (current_price - buy_price) / buy_price
        return gain_pct >= self.take_profit_pct

    def position_size(self, balance, confidence=1.0):
        """How much to invest per trade."""
        return balance * self.max_risk_per_trade * confidence

    def record_trade(self):
        self.trades_today += 1

    def get_stats(self, current_value):
        drawdown    = (self.peak_value - current_value) / self.peak_value * 100
        daily_change = (current_value - self.daily_start) / self.daily_start * 100
        return {
            "drawdown":     round(drawdown, 2),
            "daily_change": round(daily_change, 2),
            "trades_today": self.trades_today,
            "peak_value":   self.peak_value
        }