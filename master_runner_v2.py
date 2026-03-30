import schedule
import time
import subprocess
from datetime import datetime

# ============================================
# MASTER AUTO RUNNER — UPDATED v2
# Controls ALL THREE markets:
# 🇮🇳 India  → your existing live_trader.py
# 🇺🇸 US     → Alpaca (alpaca_us_trader.py)
# 💱 Forex   → MT5    (mt5_forex_trader.py)
#
# HOW TO RUN:
#   python master_runner_v2.py
# ============================================

INDIA_AVAILABLE = False
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("live_trader", "live_trader.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run_india_trader = mod.run_paper_trading
    INDIA_AVAILABLE  = True
    print("✅ India trader loaded")
except Exception as e:
    print(f"⚠️ India trader not loaded: {e}")

US_AVAILABLE = False
try:
    from alpaca_us_trader import run_us_trader
    US_AVAILABLE = True
    print("✅ US trader (Alpaca) loaded")
except Exception as e:
    print(f"⚠️ US trader not loaded: {e}")

FOREX_AVAILABLE = False
try:
    from mt5_forex_trader import run_mt5_forex_trader
    FOREX_AVAILABLE = True
    print("✅ Forex (MT5) trader loaded")
except Exception as e:
    print(f"⚠️ Forex (MT5) not loaded: {e}")


def safe_run(fn, name):
    try:
        print(f"\n{'='*55}")
        print(f"🚀 STARTING: {name}")
        print(f"{'='*55}")
        fn()
        print(f"✅ DONE: {name}")
    except Exception as e:
        print(f"❌ ERROR in {name}: {e}")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(f"❌ {name} crashed!\nError: {str(e)[:200]}", "error")
        except:
            pass


def run_india():
    if INDIA_AVAILABLE:
        safe_run(run_india_trader, "🇮🇳 India Trader")

def run_us():
    if US_AVAILABLE:
        safe_run(run_us_trader, "🇺🇸 US Trader (Alpaca)")

def run_forex():
    if FOREX_AVAILABLE:
        safe_run(run_mt5_forex_trader, "💱 Forex (MT5)")

def run_all():
    print(f"\n{'#'*55}")
    print(f"🌍 ALL MARKETS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*55}")
    run_india()
    run_us()
    run_forex()
    print(f"\n✅ ALL DONE. Next run on schedule. Sleeping 😴\n")


print("\n" + "="*55)
print("   🤖 MASTER AUTO RUNNER v2 — MT5 EDITION")
print("="*55)
print("📅 SCHEDULE (IST):")
print("  09:00 → India open  🇮🇳")
print("  13:00 → Forex check 💱")
print("  15:30 → India close 🇮🇳")
print("  17:00 → Forex check 💱")
print("  19:30 → US open     🇺🇸")
print("  21:00 → Forex check 💱")
print("  01:00 → Forex check 💱")
print("  02:00 → US close    🇺🇸")
print("  05:00 → Forex check 💱")
print("  Sunday 00:00 → AI auto-retrains 🧠")
print("="*55)

schedule.every().day.at("09:00").do(run_india)
schedule.every().day.at("15:30").do(run_india)
schedule.every().day.at("19:30").do(run_us)
schedule.every().day.at("02:00").do(run_us)
schedule.every().day.at("05:00").do(run_forex)
schedule.every().day.at("09:00").do(run_forex)
schedule.every().day.at("13:00").do(run_forex)
schedule.every().day.at("17:00").do(run_forex)
schedule.every().day.at("21:00").do(run_forex)
schedule.every().day.at("01:00").do(run_forex)
schedule.every().sunday.at("00:00").do(
    lambda: subprocess.run(["python", "auto_retrain.py"])
)

print("\n⚡ Running all markets once on startup to test connections...\n")
run_all()

print("🔄 Scheduler ACTIVE. Telegram alerts ON.")
print("💤 Keep terminal open or deploy to Railway for 24/7.")
print("Press Ctrl+C to stop.\n")

while True:
    schedule.run_pending()
    time.sleep(30)