import requests
from datetime import datetime

# ============================================
# TELEGRAM ALERT SYSTEM
# Get notified on phone for every trade!
# ============================================
# SETUP STEPS (one time only, 5 minutes):
# 1. Open Telegram app on your phone
# 2. Search "@BotFather" → click it
# 3. Type /newbot → follow steps → copy the TOKEN it gives
# 4. Search "@userinfobot" → it will tell you your CHAT_ID
# 5. Paste both below and you're done!
# ============================================

TELEGRAM_TOKEN = "8246724147:AAEONKiASx0uiMZ4viQyzQtm3SsdIHqqFAw"   # From @BotFather
TELEGRAM_CHAT_ID = "5456096838"   # From @userinfobot

def send_alert(message: str, alert_type: str = "info"):
    """Send a message to your Telegram phone."""
    
    # Add emoji based on type
    icons = {
        "buy":     "✅ BUY TRADE",
        "sell":    "💰 SELL TRADE", 
        "loss":    "📉 STOP LOSS",
        "profit":  "🎉 PROFIT",
        "error":   "❌ ERROR",
        "info":    "ℹ️ INFO",
        "start":   "🤖 BOT STARTED",
        "daily":   "📊 DAILY SUMMARY"
    }

    header = icons.get(alert_type, "🔔 ALERT")
    time_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    full_message = f"""
{header}
━━━━━━━━━━━━━━━━━━━━
{message}
━━━━━━━━━━━━━━━━━━━━
🕐 {time_str}
    """.strip()

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": full_message,
            "parse_mode": "HTML"
        }, timeout=10)
        
        if response.status_code == 200:
            print(f"📱 Telegram sent: {alert_type}")
            return True
        else:
            print(f"⚠️ Telegram failed: {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")
        return False


def alert_buy(stock, shares, price, market="US", currency="$"):
    send_alert(
        f"📈 Stock: {stock} ({market})\n"
        f"🛒 Action: BOUGHT {shares} shares\n"
        f"💲 Price: {currency}{price:.2f}\n"
        f"💸 Total Cost: {currency}{shares * price:.2f}",
        alert_type="buy"
    )

def alert_sell(stock, shares, price, profit, market="US", currency="$"):
    emoji = "🟢" if profit >= 0 else "🔴"
    send_alert(
        f"📉 Stock: {stock} ({market})\n"
        f"🏷️ Action: SOLD {shares} shares\n"
        f"💲 Price: {currency}{price:.2f}\n"
        f"{emoji} Profit/Loss: {currency}{profit:.2f}",
        alert_type="sell" if profit >= 0 else "loss"
    )

def alert_daily_summary(balance, total_profit, holdings_count, daily_pnl, market="ALL"):
    emoji = "📈" if daily_pnl >= 0 else "📉"
    send_alert(
        f"💼 Market: {market}\n"
        f"💰 Balance: ${balance:,.2f}\n"
        f"📦 Holdings: {holdings_count} positions\n"
        f"{emoji} Today's P/L: ${daily_pnl:,.2f}\n"
        f"🏦 Total Profit: ${total_profit:,.2f}",
        alert_type="daily"
    )

def alert_bot_started():
    send_alert(
        "AI Trading Bot is now LIVE!\n"
        "🇮🇳 India + 🇺🇸 US + 💱 Forex\n"
        "Watching markets 24/7...\n"
        "You can sleep now 😴",
        alert_type="start"
    )

# Test function — run this file directly to check if Telegram works
if __name__ == "__main__":
    print("Testing Telegram connection...")
    result = alert_bot_started()
    if result:
        print("✅ SUCCESS! Check your Telegram!")
    else:
        print("❌ FAILED. Check your TOKEN and CHAT_ID above.")