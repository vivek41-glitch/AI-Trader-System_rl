import time
import subprocess
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

INDIA_CHECK_MINS = 30
US_CHECK_MINS    = 30
FOREX_CHECK_MINS = 60

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
    print(f"⚠️ India: {e}")

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


last_india   = 0
last_us      = 0
last_forex   = 0
last_retrain = 0
RETRAIN_INTERVAL = 7 * 24 * 60 * 60

print("\n" + "="*55)
print("  🤖 RAILWAY RUNNER — ALL 3 MARKETS 24x7")
print("="*55)
print(f"  India:  every {INDIA_CHECK_MINS} min")
print(f"  US:     every {US_CHECK_MINS} min")
print(f"  Forex:  every {FOREX_CHECK_MINS} min (Twelve Data)")
print(f"  Retrain: every Sunday")
print("="*55)
print("📱 Telegram alerts for every trade")
print("😴 YOU SLEEP — BOT WORKS!\n")

try:
    from telegram_alerts_v2 import send_alert
    send_alert(
        "🚀 Railway Server STARTED!\n"
        "India + US + Forex running 24x7\n"
        "Laptop can be OFF now 😴",
        "start"
    )
except:
    pass

print("⚡ Running all markets on startup...\n")
if INDIA_AVAILABLE:  safe_run(run_india_trader,            "India Trader")
if US_AVAILABLE:     safe_run(run_us_trader,               "US Trader")
if FOREX_AVAILABLE:  safe_run(run_twelvedata_forex_trader, "Forex Trader")
last_india = last_us = last_forex = time.time()

print("\n✅ ALL STARTED. Running forever...\n")

while True:
    now = time.time()

    if INDIA_AVAILABLE and (now - last_india) >= INDIA_CHECK_MINS * 60:
        safe_run(run_india_trader, "India Trader")
        last_india = now

    if US_AVAILABLE and (now - last_us) >= US_CHECK_MINS * 60:
        safe_run(run_us_trader, "US Trader")
        last_us = now

    if FOREX_AVAILABLE and (now - last_forex) >= FOREX_CHECK_MINS * 60:
        safe_run(run_twelvedata_forex_trader, "Forex Trader")
        last_forex = now

    now_ist = datetime.now(IST)
    if now_ist.weekday() == 6 and (now - last_retrain) >= RETRAIN_INTERVAL:
        print("\n🧠 Weekly retrain...")
        try:
            subprocess.run(["python", "auto_retrain.py"])
            last_retrain = now
        except Exception as e:
            print(f"❌ Retrain failed: {e}")

    time.sleep(60)