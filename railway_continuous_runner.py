import time
from datetime import datetime
import pytz

# ============================================
# RAILWAY RUNNER — US + FOREX ONLY
# No heavy ML libraries needed!
# India trader runs on your laptop separately
# ============================================

IST = pytz.timezone("Asia/Kolkata")

US_CHECK_MINS    = 30
FOREX_CHECK_MINS = 60

US_AVAILABLE = False
try:
    from alpaca_us_trader import run_us_trader
    US_AVAILABLE = True
    print("✅ US trader loaded")
except Exception as e:
    print(f"⚠️ US: {e}")

FOREX_AVAILABLE = False
try:
    from twelvedata_forex_trader import run_twelvedata_forex_trader
    FOREX_AVAILABLE = True
    print("✅ Forex (Twelve Data) loaded")
except Exception as e:
    print(f"⚠️ Forex: {e}")


def safe_run(fn, name):
    try:
        print(f"\n{'='*50}")
        print(f"🚀 {name} — {datetime.now(IST).strftime('%H:%M:%S IST')}")
        print(f"{'='*50}")
        fn()
        print(f"✅ DONE: {name}")
    except Exception as e:
        print(f"❌ {name} crashed: {e}")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(f"❌ {name} crashed!\n{str(e)[:150]}", "error")
        except:
            pass


last_us    = 0
last_forex = 0

print("\n" + "="*55)
print("  🤖 RAILWAY — US + FOREX 24x7")
print("="*55)
print(f"  🇺🇸 US:    every {US_CHECK_MINS} min (Alpaca)")
print(f"  💱 Forex:  every {FOREX_CHECK_MINS} min (Twelve Data)")
print(f"  🇮🇳 India: run on your laptop separately")
print("="*55)
print("😴 YOU SLEEP — BOT WORKS!\n")

try:
    from telegram_alerts_v2 import send_alert
    send_alert(
        "🚀 Railway Server LIVE!\n"
        "🇺🇸 US + 💱 Forex running 24x7\n"
        "Laptop can be OFF now 😴",
        "start"
    )
except:
    pass

# Run once on startup
print("⚡ Running on startup...\n")
if US_AVAILABLE:    safe_run(run_us_trader,                "US Trader")
if FOREX_AVAILABLE: safe_run(run_twelvedata_forex_trader,  "Forex Trader")
last_us = last_forex = time.time()

print("\n✅ Running forever...\n")

while True:
    now = time.time()

    if US_AVAILABLE and (now - last_us) >= US_CHECK_MINS * 60:
        safe_run(run_us_trader, "US Trader")
        last_us = now

    if FOREX_AVAILABLE and (now - last_forex) >= FOREX_CHECK_MINS * 60:
        safe_run(run_twelvedata_forex_trader, "Forex Trader")
        last_forex = now

    time.sleep(60)