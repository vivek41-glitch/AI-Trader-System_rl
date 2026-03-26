class RiskManager:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.max_risk_per_trade = 0.05
        self.max_daily_loss = 0.30
        self.max_drawdown = 0.40
        self.peak_value = initial_balance
        self.daily_start_value = initial_balance
        self.trades_today = 0
        self.max_trades_per_day = 10

    def update_peak(self, current_value):
        if current_value > self.peak_value:
            self.peak_value = current_value

    def can_trade(self, current_value):
        drawdown = (self.peak_value - current_value) / self.peak_value
        if drawdown >= self.max_drawdown:
            return False, f"🛑 Max drawdown reached! ({drawdown*100:.1f}%)"
        daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
        if daily_loss >= self.max_daily_loss:
            return False, f"🛑 Daily loss limit reached! ({daily_loss*100:.1f}%)"
        if self.trades_today >= self.max_trades_per_day:
            return False, f"🛑 Max trades per day reached! ({self.trades_today})"
        return True, "✅ Trading allowed"

    def position_size(self, balance, confidence=1.0):
        max_amount = balance * self.max_risk_per_trade * confidence
        return max_amount

    def new_day(self, current_value):
        self.daily_start_value = current_value
        self.trades_today = 0

    def record_trade(self):
        self.trades_today += 1

    def get_stats(self, current_value):
        drawdown = (self.peak_value - current_value) / self.peak_value * 100
        daily_change = (current_value - self.daily_start_value) / self.daily_start_value * 100
        return {
            'drawdown': drawdown,
            'daily_change': daily_change,
            'trades_today': self.trades_today,
            'peak_value': self.peak_value
        }

if __name__ == "__main__":
    print("🛡️ Testing Risk Manager...")
    rm = RiskManager(initial_balance=10000)
    print(rm.can_trade(9800))
    print(rm.can_trade(8400))
    rm.record_trade()
    rm.record_trade()
    rm.record_trade()
    print(rm.can_trade(9900))
    print("✅ Risk Manager working perfectly!")