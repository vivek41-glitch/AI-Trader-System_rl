import schedule
import time
import subprocess
from datetime import datetime

# ============================================
# MASTER AUTO RUNNER
# Controls ALL THREE markets automatically:
# 🇮🇳 India  →  NSE (your existing live_trader.py)
# 🇺🇸 US     →  Alpaca (alpaca_us_trader.py)
# 💱 Forex   →  OANDA  (oanda_forex_trader.py)
# ============================================
# HOW TO RUN:
#   python master_runner.py
# Then leave it running. That's it. Done.
# ============================================

from alpaca_us_trader  import run_us_trader
from oanda_forex_trader import run_forex_trader

# Try to import your existing India trader
try:
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("live_trader", "live_trader.py")
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    run_india_trader = live.run_paper_trading
    INDIA_AVAILABLE = True
except Exception as e:
    print(f"⚠️ India trader not loaded: {e}")
    INDIA_AVAILABLE = False


def safe_run(fn, name):
    """Run a trader function safely — if it crashes, log and continue."""
    try:
        print(f"\n{'='*55}")
        print(f"🚀 STARTING: {name}")
        print(f"{'='*55}")
        fn()
        print(f"✅ DONE: {name}")
    except Exception as e:
        print(f"❌ ERROR in {name}: {e}")
        try:
            from telegram_alerts import send_alert
            send_alert(f"❌ {name} crashed!\nError: {str(e)[:200]}", alert_type="error")
        except:
            pass


def run_india():
    if INDIA_AVAILABLE:
        safe_run(run_india_trader, "🇮🇳 India Trader")
    else:
        print("⚠️ India trader not available")

def run_us():
    safe_run(run_us_trader, "🇺🇸 US Trader (Alpaca)")

def run_forex():
    safe_run(run_forex_trader, "💱 Forex Trader (OANDA)")

def run_all():
    """Run all three markets back to back."""
    print(f"\n{'#'*55}")
    print(f"🌍 ALL MARKETS SESSION — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'#'*55}")
    run_india()
    run_us()
    run_forex()
    print(f"\n✅ ALL DONE. Next run scheduled. Sleeping... 😴")


# ─── Schedule ────────────────────────────────────────────────────────────────
# Times are in your LOCAL time (IST)

print("🤖 MASTER AUTO RUNNER STARTED!")
print("=" * 55)
print("📅 SCHEDULE:")
print("  09:00 IST → India market open   🇮🇳")
print("  15:30 IST → India market close  🇮🇳")
print("  19:30 IST → US market open      🇺🇸 (9:30 AM EST)")
print("  02:00 IST → US market close     🇺🇸 (4:00 PM EST)")
print("  Forex runs every 4 hours        💱 (24/7)")
print("=" * 55)

# India: runs at open and close
schedule.every().day.at("09:00").do(run_india)
schedule.every().day.at("15:30").do(run_india)

# US: runs when NYSE opens and closes
schedule.every().day.at("19:30").do(run_us)
schedule.every().day.at("02:00").do(run_us)

# Forex: every 4 hours (Forex never sleeps)
schedule.every(4).hours.do(run_forex)

# Run everything once immediately on startup
print("\n⚡ Running all markets once right now on startup...")
run_all()

print("\n🔄 Scheduler is active. Bot will run automatically.")
print("📱 You'll get Telegram alerts for every trade.")
print("💤 You can close this terminal? NO — keep it running.")
print("🚀 Want 24/7? Deploy to Railway.app (free) — see README.")
print("\nPress Ctrl+C to stop.\n")

# Keep running forever
while True:
    schedule.run_pending()
    time.sleep(30)