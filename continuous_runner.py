import time
import subprocess
from datetime import datetime
import pytz

# ============================================
# CONTINUOUS MASTER RUNNER
# Checks markets every few minutes
# Trades whenever AI sees a good signal
# No fixed schedule — always watching!
# ============================================
# HOW TO RUN:
#   python continuous_runner.py
#
# For 24x7 without laptop:
#   → Option A: Leave laptop ON, change power settings to never sleep
#   → Option B: Get Windows VPS (~Rs 300/month) and run there
# ============================================

IST = pytz.timezone("Asia/Kolkata")

# How often to check each market (in minutes)
INDIA_CHECK_MINS  = 30    # Check India every 30 min during market hours
US_CHECK_MINS     = 30    # Check US every 30 min during market hours
FOREX_CHECK_MINS  = 60    # Check Forex every 60 min (24/5)

# Load all traders
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
    print(f"⚠️ India trader: {e}")

US_AVAILABLE = False
try:
    from alpaca_us_trader import run_us_trader
    US_AVAILABLE = True
    print("✅ US trader loaded")
except Exception as e:
    print(f"⚠️ US trader: {e}")

FOREX_AVAILABLE = False
try:
    from mt5_forex_trader import run_mt5_forex_trader
    FOREX_AVAILABLE = True
    print("✅ Forex (MT5) loaded")
except Exception as e:
    print(f"⚠️ Forex trader: {e}")


def is_india_market_open():
    """NSE is open Mon-Fri 9:15 AM to 3:30 PM IST."""
    now = datetime.now(IST)
    if now.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0)
    market_close = now.replace(hour=15, minute=30, second=0)
    return market_open <= now <= market_close


def is_us_market_open():
    """NYSE is open Mon-Fri 9:30 AM to 4:00 PM EST = 7:00 PM to 1:30 AM IST."""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    # In IST: NYSE opens 7:00 PM, closes 1:30 AM next day
    hour = now.hour
    return (hour >= 19) or (hour < 2) or (hour == 1 and now.minute <= 30)


def is_forex_market_open():
    """Forex is open Mon-Fri 24 hours. Closed Saturday and Sunday."""
    now = datetime.now(IST)
    # Forex closes Friday 11:30 PM IST, opens Sunday 11:30 PM IST (approx)
    if now.weekday() == 5:   # Saturday — fully closed
        return False
    if now.weekday() == 6 and now.hour < 22:   # Sunday before 10 PM IST
        return False
    return True


def safe_run(fn, name):
    try:
        print(f"\n{'='*50}")
        print(f"🚀 {name} — {datetime.now(IST).strftime('%H:%M:%S IST')}")
        print(f"{'='*50}")
        fn()
    except Exception as e:
        print(f"❌ {name} crashed: {e}")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(f"❌ {name} crashed!\n{str(e)[:150]}", "error")
        except:
            pass


# Track last run times
last_india_run = 0
last_us_run    = 0
last_forex_run = 0
last_retrain   = 0

RETRAIN_INTERVAL = 7 * 24 * 60 * 60   # 1 week in seconds

print("\n" + "="*55)
print("  🤖 CONTINUOUS AUTO RUNNER — ALWAYS WATCHING")
print("="*55)
print(f"  India checks:  every {INDIA_CHECK_MINS} min (market hours only)")
print(f"  US checks:     every {US_CHECK_MINS} min (market hours only)")
print(f"  Forex checks:  every {FOREX_CHECK_MINS} min (24/5)")
print(f"  AI retrains:   every Sunday automatically")
print("="*55)
print("\n📱 Telegram alert sent for every trade")
print("💤 To run 24x7: keep laptop ON + change power settings")
print("   OR get a Windows VPS (~Rs 300/month)")
print("\nPress Ctrl+C to stop.\n")

# Send startup alert
try:
    from telegram_alerts_v2 import send_alert
    send_alert(
        "🔄 Continuous Runner STARTED!\n"
        f"India: every {INDIA_CHECK_MINS}min\n"
        f"US: every {US_CHECK_MINS}min\n"
        f"Forex: every {FOREX_CHECK_MINS}min\n"
        "Always watching markets 👀",
        "start"
    )
except:
    pass

# ── MAIN LOOP — runs forever ──────────────────────────────────────────────────
while True:
    now_ts = time.time()
    now_ist = datetime.now(IST)

    # ── INDIA ────────────────────────────────────────────────────────────────
    if INDIA_AVAILABLE:
        india_open = is_india_market_open()
        india_due  = (now_ts - last_india_run) >= (INDIA_CHECK_MINS * 60)

        if india_due:
            status = "OPEN" if india_open else "CLOSED — using previous data"
            print(f"\n🇮🇳 India market {status}")
            safe_run(run_india_trader, "🇮🇳 India Trader")
            last_india_run = now_ts

    # ── US STOCKS ────────────────────────────────────────────────────────────
    if US_AVAILABLE:
        us_open = is_us_market_open()
        us_due  = (now_ts - last_us_run) >= (US_CHECK_MINS * 60)

        if us_due:
            status = "OPEN" if us_open else "CLOSED — using previous 150 days data"
            print(f"\n🇺🇸 US market {status}")
            safe_run(run_us_trader, "🇺🇸 US Trader (Alpaca)")
            last_us_run = now_ts

    # ── FOREX ────────────────────────────────────────────────────────────────
    if FOREX_AVAILABLE:
        forex_open = is_forex_market_open()
        forex_due  = (now_ts - last_forex_run) >= (FOREX_CHECK_MINS * 60)

        if forex_open and forex_due:
            safe_run(run_mt5_forex_trader, "💱 Forex (MT5)")
            last_forex_run = now_ts
        elif not forex_open:
            h = now_ist.hour
            m = now_ist.minute
            if m == 0:
                print(f"💱 Forex closed (weekend) — {now_ist.strftime('%H:%M IST')} — waiting...")

    # ── AUTO RETRAIN (weekly) ─────────────────────────────────────────────────
    if (now_ts - last_retrain) >= RETRAIN_INTERVAL:
        if now_ist.weekday() == 6:   # Sunday
            print("\n🧠 Weekly auto-retrain starting...")
            try:
                subprocess.run(["python", "auto_retrain.py"])
                last_retrain = now_ts
                print("✅ Retrain done!")
            except Exception as e:
                print(f"❌ Retrain failed: {e}")

    # Sleep 60 seconds between checks
    time.sleep(60)