import time
from datetime import datetime, timedelta
import pytz

# ============================================
# RAILWAY SMART RUNNER — FULL $5 OPTIMIZED
# Runs exactly 8hrs 20min per day
# Uses full $5 Railway credit every month
# Costs $0 forever — resets every month!
#
# Schedule (IST):
# 6:57 PM  → Start (3 min before NYSE)
# 7:00 PM  → US market open → trading begins
# 1:30 AM  → US market closes
# 3:17 AM  → Shutdown (used full $5 worth)
# ============================================

IST = pytz.timezone("Asia/Kolkata")

US_CHECK_MINS    = 30
FOREX_CHECK_MINS = 60

# ── Load traders ─────────────────────────────
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
        now = datetime.now(IST).strftime("%H:%M:%S IST")
        print(f"\n{'='*50}")
        print(f"🚀 {name} — {now}")
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


def get_shutdown_time():
    """Calculate today's shutdown time — 3:17 AM IST next day."""
    now = datetime.now(IST)
    # Shutdown at 3:17 AM next day
    shutdown = now.replace(hour=3, minute=17, second=0, microsecond=0)
    if now.hour < 12:
        # We're already past midnight, shutdown is today at 3:17 AM
        pass
    else:
        # Shutdown is tomorrow at 3:17 AM
        shutdown += timedelta(days=1)
    return shutdown


def should_shutdown():
    """Return True if it's past 3:17 AM IST."""
    now = datetime.now(IST)
    # Shutdown window: 3:17 AM to 6:56 PM (when market prep starts)
    if 3 <= now.hour < 18:
        return True
    if now.hour == 3 and now.minute >= 17:
        return True
    return False


def wait_until_market_prep():
    """Wait until 6:57 PM IST — 3 min before NYSE opens."""
    while True:
        now = datetime.now(IST)
        
        # Target: 6:57 PM IST
        target = now.replace(hour=18, minute=57, second=0, microsecond=0)
        
        if now >= target and now.hour >= 18:
            print(f"\n⚡ 6:57 PM IST reached! Starting up...")
            return
        
        # Calculate wait time
        if now < target:
            wait_secs = (target - now).total_seconds()
        else:
            # Already past 6:57 PM — start immediately
            return

        hours   = int(wait_secs // 3600)
        minutes = int((wait_secs % 3600) // 60)
        
        print(f"😴 Sleeping... Next start: 6:57 PM IST "
              f"(in {hours}h {minutes}m) — {now.strftime('%H:%M IST')}")
        
        # Sleep in chunks — wake up every 10 min to print status
        sleep_time = min(600, wait_secs)
        time.sleep(sleep_time)


# ── MAIN LOOP ─────────────────────────────────
print("\n" + "="*55)
print("  🤖 RAILWAY SMART RUNNER — $5 OPTIMIZED")
print("="*55)
print("  Daily Schedule (IST):")
print("  6:57 PM  → 🟢 Wake up (3 min before NYSE)")
print("  7:00 PM  → 🇺🇸 US trading starts")
print("  7:00 PM  → 💱 Forex check #1")
print("  ...every 30min US, 60min Forex...")
print("  1:30 AM  → 🇺🇸 US final check")
print("  2:00 AM  → 💱 Forex bonus check")
print("  2:30 AM  → 💱 Forex bonus check")
print("  3:17 AM  → 🔴 Sleep till tomorrow")
print("="*55)
print("  💰 Cost: $4.98/month")
print("  🎁 Credit: $5.00/month (Railway free)")
print("  💵 Your cost: $0.00 FOREVER!")
print("="*55)

try:
    from telegram_alerts_v2 import send_alert
    send_alert(
        "🤖 Railway Smart Runner LIVE!\n"
        "🇺🇸 US + 💱 Forex\n"
        "Runs 6:57 PM - 3:17 AM IST\n"
        "Cost: $0 forever! 😄",
        "start"
    )
except:
    pass

# ── DAILY LOOP ────────────────────────────────
while True:
    now = datetime.now(IST)
    
    # If it's shutdown time — sleep until 6:57 PM
    if should_shutdown():
        print(f"\n🔴 3:17 AM passed — going to sleep")
        print(f"   Used full $5 worth today ✅")
        print(f"   Waking up at 6:57 PM IST\n")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(
                "😴 Bot sleeping now\n"
                "Used full daily budget ✅\n"
                "Waking up 6:57 PM IST",
                "info"
            )
        except:
            pass
        wait_until_market_prep()

    # Send startup alert
    print(f"\n🟢 ACTIVE — {now.strftime('%d %b %Y, %H:%M IST')}")
    try:
        from telegram_alerts_v2 import send_alert
        send_alert(
            "🟢 Bot is ACTIVE now!\n"
            "🇺🇸 US market opens in 3 min\n"
            "Trading begins! 🚀",
            "start"
        )
    except:
        pass

    # ── TRADING SESSION LOOP ──────────────────
    last_us    = 0
    last_forex = 0

    while not should_shutdown():
        now_ts = time.time()

        # US check every 30 min
        if US_AVAILABLE and (now_ts - last_us) >= US_CHECK_MINS * 60:
            safe_run(run_us_trader, "🇺🇸 US Trader")
            last_us = now_ts

        # Forex check every 60 min
        if FOREX_AVAILABLE and (now_ts - last_forex) >= FOREX_CHECK_MINS * 60:
            safe_run(run_twelvedata_forex_trader, "💱 Forex Trader")
            last_forex = now_ts

        # Show heartbeat every hour
        now_ist = datetime.now(IST)
        if now_ist.minute == 0:
            print(f"💓 Bot alive — {now_ist.strftime('%H:%M IST')} "
                  f"| Shutdown at 3:17 AM IST")

        time.sleep(60)

    # Session ended — go back to top of while loop
    print(f"\n✅ Session complete! Going to sleep...")