import requests
from datetime import datetime

# ============================================
# TELEGRAM ALERTS - FIXED VERSION
# ============================================
# CORRECT SETUP STEPS (read carefully!):
#
# STEP 1: Create bot
#   - Open Telegram app on phone
#   - Search @BotFather and tap it
#   - Send: /newbot
#   - Give name: MyTraderBot
#   - Give username: mytraderbot_xyz_bot  (MUST end in 'bot')
#   - Copy the TOKEN it gives
#   - Paste token below in TELEGRAM_TOKEN
#
# STEP 2: Get YOUR chat ID correctly
#   - Search YOUR BOT by its username in Telegram
#   - Open your bot's chat
#   - Send it ANY message like "hello"  <-- CRITICAL STEP YOU MISSED!
#   - Now run: python telegram_alerts_v2.py
#   - It will auto-find and print your Chat ID
#   - Paste that number in TELEGRAM_CHAT_ID below
#   - Run again to confirm working
#
# WHY IT FAILED:
#   "chat not found" = you never sent a message TO your bot.
#   Telegram has no idea who to deliver to until you initiate.
# ============================================

TELEGRAM_TOKEN   = "8246724147:AAEONKiASx0uiMZ4viQyzQtm3SsdIHqqFAw"
TELEGRAM_CHAT_ID = "5456096838"   # Leave empty first — auto-detected below!



def get_chat_id_automatically():
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            timeout=10
        )
        data = r.json()
        if not data.get("ok"):
            print(f"❌ Token invalid: {data.get('description')}")
            return None

        updates = data.get("result", [])
        if not updates:
            print("\n" + "="*55)
            print("⚠️  NO MESSAGES FOUND IN BOT!")
            print("="*55)
            print("→ Open Telegram on your phone")
            print("→ Search for YOUR BOT by its username")
            print("→ Open that bot chat")
            print("→ Type 'hello' and press send")
            print("→ Come back and run this file again")
            print("="*55)
            return None

        last   = updates[-1]
        chat   = last.get("message", {}).get("chat", {})
        chat_id = chat.get("id")
        name    = chat.get("first_name", "User")

        if chat_id:
            print("\n" + "="*55)
            print("✅  CHAT ID FOUND AUTOMATICALLY!")
            print("="*55)
            print(f"  👤 Name:    {name}")
            print(f"  🆔 Chat ID: {chat_id}")
            print("="*55)
            print(f'\nNow in telegram_alerts_v2.py, set:')
            print(f'  TELEGRAM_CHAT_ID = "{chat_id}"')
            print("\nThen run this file again — it will work!")
            return str(chat_id)

    except Exception as e:
        print(f"❌ Error: {e}")
    return None


def send_alert(message: str, alert_type: str = "info"):
    global TELEGRAM_CHAT_ID

    if not TELEGRAM_CHAT_ID:
        print("🔍 Chat ID not set, auto-detecting...")
        detected = get_chat_id_automatically()
        if detected:
            TELEGRAM_CHAT_ID = detected
        else:
            return False

    icons = {
        "buy":   "✅ BUY TRADE",
        "sell":  "💰 SELL TRADE",
        "loss":  "📉 STOP LOSS",
        "error": "❌ ERROR",
        "info":  "ℹ️ INFO",
        "start": "🤖 BOT STARTED",
        "daily": "📊 DAILY REPORT"
    }

    header   = icons.get(alert_type, "🔔 ALERT")
    time_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    full_msg = f"{header}\n━━━━━━━━━━━━━━━━━━━━\n{message}\n━━━━━━━━━━━━━━━━━━━━\n🕐 {time_str}"

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": full_msg},
            timeout=10
        )
        if r.status_code == 200:
            print("📱 Alert sent to Telegram!")
            return True
        else:
            err = r.json().get("description", "Unknown error")
            print(f"⚠️ Telegram error: {err}")
            return False
    except Exception as e:
        print(f"⚠️ Exception: {e}")
        return False


def alert_buy(stock, shares, price, market="US", currency="$"):
    send_alert(
        f"📈 {stock} ({market})\n"
        f"🛒 BOUGHT {shares} shares\n"
        f"💲 Price: {currency}{price:.4f}\n"
        f"💸 Total: {currency}{shares * price:.2f}",
        "buy"
    )

def alert_sell(stock, shares, price, profit, market="US", currency="$"):
    e = "🟢" if profit >= 0 else "🔴"
    send_alert(
        f"📉 {stock} ({market})\n"
        f"🏷️ SOLD {shares} shares\n"
        f"💲 Price: {currency}{price:.4f}\n"
        f"{e} P/L: {currency}{profit:.2f}",
        "sell" if profit >= 0 else "loss"
    )

def alert_daily_summary(balance, total_profit, holdings_count, daily_pnl, market="ALL"):
    e = "📈" if daily_pnl >= 0 else "📉"
    send_alert(
        f"💼 {market}\n"
        f"💰 Balance: ${balance:,.2f}\n"
        f"📦 Positions: {holdings_count}\n"
        f"{e} Today P/L: ${daily_pnl:,.2f}\n"
        f"🏦 Total P/L: ${total_profit:,.2f}",
        "daily"
    )

def alert_bot_started():
    send_alert(
        "AI Trader is LIVE! 🚀\n"
        "🇮🇳 India + 🇺🇸 US + 💱 Forex\n"
        "Watching markets 24/7\n"
        "You can sleep now 😴",
        "start"
    )


if __name__ == "__main__":
    print("🔧 TELEGRAM SETUP TESTER")
    print("="*55)

    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Paste your TOKEN first!")
        print("   Open this file → TELEGRAM_TOKEN → paste your real token")

    elif not TELEGRAM_CHAT_ID:
        print("Step 1: Detecting your Chat ID...")
        get_chat_id_automatically()

    else:
        print("Testing full system...")
        if alert_bot_started():
            print("\n✅ SUCCESS! Check your Telegram!")
        else:
            print("\n❌ Check your TOKEN is correct.")