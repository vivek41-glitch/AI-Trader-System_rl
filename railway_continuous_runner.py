import time
import subprocess
from datetime import datetime
import pytz

# ============================================
# RAILWAY SMART RUNNER v3 — PHASE 2 UPDATED
# Now trades ALL markets:
# 🇺🇸 US Stocks (15 stocks)
# 💱 Forex (8 pairs)
# 🪙 Crypto (10 coins — 24/7!)
# 🥇 Commodities (Gold, Silver, Oil etc)
# 📰 News briefing before US market opens
#
# Schedule (IST):
# 6:30 PM → 📰 News briefing sent to Telegram
# 6:57 PM → 🟢 Server wakes up
# 7:00 PM → All markets start trading
# 3:17 AM → 😴 Server sleeps
# Cost: ~$4.98/month (Railway free = $5)
# ============================================

IST = pytz.timezone("Asia/Kolkata")

US_CHECK_MINS          = 30
FOREX_CHECK_MINS       = 60
CRYPTO_CHECK_MINS      = 45   # Crypto more active — check more often
COMMODITIES_CHECK_MINS = 90   # Slower moving

# ── Load all traders ──────────────────────────
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
    print("✅ Forex trader loaded")
except Exception as e:
    print(f"⚠️ Forex: {e}")

CRYPTO_AVAILABLE = False
try:
    from crypto_commodities_trader import run_crypto_trader
    CRYPTO_AVAILABLE = True
    print("✅ Crypto trader loaded")
except Exception as e:
    print(f"⚠️ Crypto: {e}")

COMMODITIES_AVAILABLE = False
try:
    from crypto_commodities_trader import run_commodities_trader
    COMMODITIES_AVAILABLE = True
    print("✅ Commodities trader loaded")
except Exception as e:
    print(f"⚠️ Commodities: {e}")

NEWS_AVAILABLE = False
try:
    from news_sentiment import morning_market_briefing
    NEWS_AVAILABLE = True
    print("✅ News sentiment loaded")
except Exception as e:
    print(f"⚠️ News: {e}")


def safe_run(fn, name):
    try:
        print(f"\n{'='*55}")
        print(f"🚀 {name} — {datetime.now(IST).strftime('%H:%M:%S IST')}")
        print(f"{'='*55}")
        fn()
        print(f"✅ DONE: {name}")
    except Exception as e:
        print(f"❌ {name} crashed: {e}")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(f"❌ {name} crashed!\n{str(e)[:150]}", "error")
        except:
            pass


def should_shutdown():
    now = datetime.now(IST)
    if 3 <= now.hour < 18:
        return True
    if now.hour == 3 and now.minute >= 17:
        return True
    return False


def wait_until_market_prep():
    while True:
        now = datetime.now(IST)
        if now.hour == 18 and now.minute >= 57:
            return
        if now.hour >= 19:
            return
        now_ts  = time.time()
        target  = now.replace(hour=18, minute=57, second=0)
        if now < target:
            wait  = (target - now).total_seconds()
            hrs   = int(wait // 3600)
            mins  = int((wait % 3600) // 60)
            print(f"😴 Sleeping... Waking at 6:57 PM IST (in {hrs}h {mins}m)")
            time.sleep(min(600, wait))
        else:
            return


# ── STARTUP ───────────────────────────────────
print("\n" + "="*55)
print("  🤖 RAILWAY RUNNER v3 — ALL MARKETS")
print("="*55)
print("  Schedule (IST):")
print("  6:30 PM → 📰 News briefing")
print("  6:57 PM → 🟢 Wake up")
print("  7:00 PM → 🇺🇸 US + 💱 Forex + 🪙 Crypto + 🥇 Gold")
print("  Every 30min → US check")
print("  Every 45min → Crypto check")
print("  Every 60min → Forex check")
print("  Every 90min → Commodities check")
print("  3:17 AM → 😴 Sleep")
print("="*55)
print("  💰 Cost: $4.98/month (Railway free $5)")
print("="*55)

try:
    from telegram_alerts_v2 import send_alert
    send_alert(
        "🚀 Railway v3 LIVE!\n"
        "🇺🇸 US + 💱 Forex + 🪙 10 Crypto\n"
        "🥇 Gold + Silver + Oil\n"
        "📰 News sentiment active\n"
        "Cost: $0 forever! 😄",
        "start"
    )
except:
    pass

# ── MAIN LOOP ─────────────────────────────────
last_us          = 0
last_forex       = 0
last_crypto      = 0
last_commodities = 0
last_news        = 0
last_retrain     = 0
news_briefing_done = False

# Run everything once on startup
print("\n⚡ Running all markets on startup...\n")
if US_AVAILABLE:          safe_run(run_us_trader,            "US Trader")
if FOREX_AVAILABLE:       safe_run(run_twelvedata_forex_trader, "Forex Trader")
if CRYPTO_AVAILABLE:      safe_run(run_crypto_trader,        "Crypto Trader")
if COMMODITIES_AVAILABLE: safe_run(run_commodities_trader,   "Commodities Trader")

last_us = last_forex = last_crypto = last_commodities = time.time()
print("\n✅ All markets started! Running forever...\n")

while True:
    now     = time.time()
    now_ist = datetime.now(IST)

    # News briefing at 6:30 PM
    if now_ist.hour == 18 and now_ist.minute >= 30 and not news_briefing_done:
        if NEWS_AVAILABLE:
            safe_run(morning_market_briefing, "📰 News Briefing")
        news_briefing_done = True
    if now_ist.hour == 19:
        news_briefing_done = False   # Reset for tomorrow

    # Shutdown check
    if should_shutdown():
        print(f"\n🔴 3:17 AM — going to sleep")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert("😴 Bot sleeping\nUsed full daily budget ✅\nWaking 6:57 PM IST", "info")
        except:
            pass
        wait_until_market_prep()
        # Reset timers after waking up
        last_us = last_forex = last_crypto = last_commodities = 0

    # US check every 30 min
    if US_AVAILABLE and (now - last_us) >= US_CHECK_MINS * 60:
        safe_run(run_us_trader, "US Trader")
        last_us = now

    # Forex check every 60 min
    if FOREX_AVAILABLE and (now - last_forex) >= FOREX_CHECK_MINS * 60:
        safe_run(run_twelvedata_forex_trader, "Forex Trader")
        last_forex = now

    # Crypto every 45 min
    if CRYPTO_AVAILABLE and (now - last_crypto) >= CRYPTO_CHECK_MINS * 60:
        safe_run(run_crypto_trader, "Crypto Trader")
        last_crypto = now

    # Commodities every 90 min
    if COMMODITIES_AVAILABLE and (now - last_commodities) >= COMMODITIES_CHECK_MINS * 60:
        safe_run(run_commodities_trader, "Commodities Trader")
        last_commodities = now

    # Weekly retrain reminder
    if now_ist.weekday() == 6 and now_ist.hour == 10 and (now - last_retrain) > 3600:
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(
                "🧠 Weekly Reminder!\n"
                "Run on your laptop:\n"
                "python train_all_stocks.py\n"
                "Train AI on 50 stocks!", "info"
            )
        except:
            pass
        last_retrain = now

    time.sleep(60)