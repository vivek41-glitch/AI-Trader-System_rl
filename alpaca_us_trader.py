import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import json, os, time

# ============================================
# ALPACA US STOCKS TRADER (100% FREE)
# Paper trading = fake money, real prices
# ============================================
# SETUP (5 minutes, completely free):
# 1. Go to alpaca.markets
# 2. Click "Get Started Free" → sign up
# 3. Go to Dashboard → Paper Trading
# 4. Click "API Keys" → Generate Key
# 5. Copy API_KEY and SECRET_KEY below
# ============================================

ALPACA_API_KEY    = "YOUR_ALPACA_API_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET_KEY"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets"   # Paper = free fake money
# When ready for REAL money, change to: "https://api.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type": "application/json"
}

US_STOCKS = {
    "AAPL":  "Apple",
    "TSLA":  "Tesla",
    "MSFT":  "Microsoft",
    "GOOGL": "Google",
    "AMZN":  "Amazon",
    "NVDA":  "Nvidia",
    "META":  "Meta",
}

PORTFOLIO_FILE = "logs/alpaca_portfolio.json"


# ─── Account Info ────────────────────────────────────────────────────────────

def get_account():
    """Get current balance and account status."""
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "balance":    float(data["cash"]),
                "portfolio":  float(data["portfolio_value"]),
                "buying_power": float(data["buying_power"]),
                "status":     data["status"]
            }
    except Exception as e:
        print(f"❌ Account error: {e}")
    return None


# ─── Price Data ───────────────────────────────────────────────────────────────

def get_price_data(symbol, days=100):
    """Fetch historical OHLCV data from Alpaca."""
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 50)
        url   = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": "1Day",
            "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit":     200
        }
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            return None
        
        bars = r.json().get("bars", [])
        if len(bars) < 50:
            return None

        df = pd.DataFrame(bars)
        df = df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"})
        df["Close"] = df["Close"].astype(float)

        # Add technical indicators (same as your existing system)
        df["RSI"]         = ta.rsi(df["Close"], length=14)
        macd              = ta.macd(df["Close"])
        df["MACD"]        = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
        df["EMA_20"]      = ta.ema(df["Close"], length=20)
        df["EMA_50"]      = ta.ema(df["Close"], length=50)
        bb                = ta.bbands(df["Close"], length=20)
        df["BB_Upper"]    = bb[bb.columns[0]]
        df["BB_Mid"]      = bb[bb.columns[1]]
        df["BB_Lower"]    = bb[bb.columns[2]]

        return df.dropna().reset_index(drop=True)

    except Exception as e:
        print(f"❌ Price fetch error for {symbol}: {e}")
        return None


# ─── Order Execution ─────────────────────────────────────────────────────────

def place_order(symbol, qty, side):
    """Place a buy or sell order on Alpaca."""
    try:
        order = {
            "symbol":        symbol,
            "qty":           str(qty),
            "side":          side,        # "buy" or "sell"
            "type":          "market",
            "time_in_force": "day"
        }
        r = requests.post(
            f"{ALPACA_BASE_URL}/v2/orders",
            headers=HEADERS,
            json=order,
            timeout=10
        )
        if r.status_code in [200, 201]:
            data = r.json()
            print(f"  ✅ Order placed: {side.upper()} {qty} {symbol} | ID: {data['id'][:8]}...")
            return data
        else:
            print(f"  ❌ Order failed: {r.text}")
            return None
    except Exception as e:
        print(f"  ❌ Order error: {e}")
        return None


def get_positions():
    """Get all currently held positions."""
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            positions = {}
            for p in r.json():
                positions[p["symbol"]] = {
                    "shares":    float(p["qty"]),
                    "buy_price": float(p["avg_entry_price"]),
                    "current":   float(p["current_price"]),
                    "profit":    float(p["unrealized_pl"]),
                    "profit_pct": float(p["unrealized_plpc"]) * 100
                }
            return positions
    except Exception as e:
        print(f"❌ Positions error: {e}")
    return {}


# ─── AI Decision ─────────────────────────────────────────────────────────────

def get_ai_signal(df):
    """
    Simple but effective signal logic using your indicators.
    Later: replace this with your PPO model.
    """
    last   = df.iloc[-1]
    second = df.iloc[-2]

    buy_signals  = 0
    sell_signals = 0

    # RSI signal
    if last["RSI"] < 35:   buy_signals  += 2   # Oversold = BUY
    elif last["RSI"] > 65: sell_signals += 2   # Overbought = SELL

    # MACD crossover
    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_signals += 2
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_signals += 2

    # Price vs EMA trend
    if last["Close"] > last["EMA_20"] > last["EMA_50"]:
        buy_signals += 1
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]:
        sell_signals += 1

    # Bollinger Band bounce
    if last["Close"] <= last["BB_Lower"]:  buy_signals  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_signals += 1

    if buy_signals >= 3:   return "BUY",  buy_signals
    if sell_signals >= 3:  return "SELL", sell_signals
    return "HOLD", 0


# ─── Stop Loss Check ─────────────────────────────────────────────────────────

def should_stop_loss(position, stop_pct=-0.05):
    """Force sell if loss exceeds stop_pct (default -5%)."""
    return position["profit_pct"] / 100 <= stop_pct


# ─── Main Trading Loop ───────────────────────────────────────────────────────

def run_us_trader(model=None):
    """Main function — run this every day."""
    from telegram_alerts import alert_buy, alert_sell, alert_daily_summary

    print("\n🇺🇸 US STOCK TRADER (ALPACA PAPER)")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get account
    account = get_account()
    if not account:
        print("❌ Cannot connect to Alpaca. Check your API keys.")
        return

    print(f"💰 Balance:       ${account['balance']:,.2f}")
    print(f"📦 Portfolio:     ${account['portfolio']:,.2f}")
    print(f"⚡ Buying Power:  ${account['buying_power']:,.2f}")
    print("=" * 50)

    positions   = get_positions()
    daily_pnl   = 0
    invest_each = account["buying_power"] * 0.10   # 10% per stock max

    for symbol, name in US_STOCKS.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_price_data(symbol)
        if df is None:
            print(f"  ⚠️ No data for {symbol}")
            continue

        current_price = float(df["Close"].iloc[-1])
        signal, strength = get_ai_signal(df)

        # ── Stop Loss Check ──
        if symbol in positions:
            pos = positions[symbol]
            if should_stop_loss(pos):
                print(f"  🛑 STOP LOSS triggered! Loss: {pos['profit_pct']:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    alert_sell(name, int(pos["shares"]), current_price,
                                pos["profit"], market="US")
                    daily_pnl += pos["profit"]
                continue

        print(f"  💲 Price: ${current_price:.2f} | Signal: {signal} (strength: {strength})")

        # ── Execute Signal ──
        if signal == "BUY" and symbol not in positions:
            shares = int(invest_each // current_price)
            if shares > 0:
                order = place_order(symbol, shares, "buy")
                if order:
                    alert_buy(name, shares, current_price, market="US")

        elif signal == "SELL" and symbol in positions:
            pos    = positions[symbol]
            shares = int(pos["shares"])
            order  = place_order(symbol, shares, "sell")
            if order:
                alert_sell(name, shares, current_price, pos["profit"], market="US")
                daily_pnl += pos["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.5)   # Be polite to the API

    # ── Daily Summary ──
    positions_after = get_positions()
    account_after   = get_account()
    total_profit    = sum(p["profit"] for p in positions_after.values())

    print("\n" + "=" * 50)
    print("📊 SESSION DONE")
    print(f"💰 Balance: ${account_after['balance']:,.2f}")
    print(f"📈 Open P/L: ${total_profit:,.2f}")
    print(f"📅 Today's Trades P/L: ${daily_pnl:,.2f}")
    print("=" * 50)

    alert_daily_summary(
        balance=account_after["balance"],
        total_profit=total_profit,
        holdings_count=len(positions_after),
        daily_pnl=daily_pnl,
        market="🇺🇸 US Stocks"
    )


if __name__ == "__main__":
    run_us_trader()