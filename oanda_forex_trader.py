import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
import time

# ============================================
# OANDA FOREX TRADER (100% FREE DEMO)
# Trades currency pairs: EUR/USD, GBP/USD etc
# Forex = 24 hours, 5 days/week. No sleep!
# ============================================
# SETUP (5 minutes, completely free):
# 1. Go to oanda.com
# 2. Click "Try a Free Demo" → sign up
# 3. Go to Manage Funds → API Access
# 4. Generate Practice API Token
# 5. Paste TOKEN and ACCOUNT_ID below
# ============================================

OANDA_TOKEN      = "dbacef5f-2f06-4bfd-a11e-9f12d3d8a188"
OANDA_ACCOUNT_ID = "YOUR_OANDA_ACCOUNT_ID"
OANDA_BASE_URL   = "https://api-fxpractice.oanda.com"   # Practice = free
# Real trading URL: "https://api-fxtrade.oanda.com"

HEADERS = {
    "Authorization": f"Bearer {OANDA_TOKEN}",
    "Content-Type":  "application/json"
}

# ── Forex Pairs to Trade ──────────────────────────────────────────────────────
FOREX_PAIRS = {
    "EUR_USD": "Euro / US Dollar",
    "GBP_USD": "British Pound / US Dollar",
    "USD_JPY": "US Dollar / Japanese Yen",
    "AUD_USD": "Australian Dollar / US Dollar",
    "USD_INR": "US Dollar / Indian Rupee",   # Indian pair!
}

UNITS_PER_TRADE = 1000   # Start small — 1000 units per trade


# ─── Account Info ────────────────────────────────────────────────────────────

def get_account():
    """Get Forex account balance."""
    try:
        r = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/summary",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            acc = r.json()["account"]
            return {
                "balance":    float(acc["balance"]),
                "nav":        float(acc["NAV"]),
                "open_trades": int(acc["openTradeCount"]),
                "currency":   acc["currency"]
            }
    except Exception as e:
        print(f"❌ Account error: {e}")
    return None


# ─── Price Data ───────────────────────────────────────────────────────────────

def get_candles(pair, count=150, granularity="D"):
    """
    Fetch OHLCV candles for a forex pair.
    granularity: M1=1min, H1=1hr, D=daily
    """
    try:
        r = requests.get(
            f"{OANDA_BASE_URL}/v3/instruments/{pair}/candles",
            headers=HEADERS,
            params={"count": count, "granularity": granularity, "price": "M"},
            timeout=15
        )
        if r.status_code != 200:
            return None

        candles = r.json()["candles"]
        rows = []
        for c in candles:
            if c["complete"]:
                rows.append({
                    "Open":   float(c["mid"]["o"]),
                    "High":   float(c["mid"]["h"]),
                    "Low":    float(c["mid"]["l"]),
                    "Close":  float(c["mid"]["c"]),
                    "Volume": int(c["volume"])
                })

        if len(rows) < 50:
            return None

        df = pd.DataFrame(rows)

        # Add indicators (same as your existing system)
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

        # ATR — measures volatility, important for Forex
        df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        return df.dropna().reset_index(drop=True)

    except Exception as e:
        print(f"❌ Candle error for {pair}: {e}")
        return None


# ─── AI Signal (same logic as US trader, works for Forex too) ────────────────

def get_forex_signal(df):
    """Generate BUY/SELL/HOLD signal for a forex pair."""
    last   = df.iloc[-1]
    second = df.iloc[-2]

    buy_signals  = 0
    sell_signals = 0

    if last["RSI"] < 35:   buy_signals  += 2
    elif last["RSI"] > 65: sell_signals += 2

    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_signals += 2
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_signals += 2

    if last["Close"] > last["EMA_20"] > last["EMA_50"]:
        buy_signals += 1
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]:
        sell_signals += 1

    if last["Close"] <= last["BB_Lower"]:   buy_signals  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_signals += 1

    # ATR filter — don't trade in extremely volatile conditions
    avg_atr = df["ATR"].mean()
    if last["ATR"] > avg_atr * 2.5:
        return "HOLD", 0   # Too volatile, skip

    if buy_signals >= 3:   return "BUY",  buy_signals
    if sell_signals >= 3:  return "SELL", sell_signals
    return "HOLD", 0


# ─── Get Open Trades ─────────────────────────────────────────────────────────

def get_open_trades():
    """Get all currently open forex trades."""
    try:
        r = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/openTrades",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            trades = {}
            for t in r.json()["trades"]:
                inst = t["instrument"]
                trades[inst] = {
                    "id":         t["id"],
                    "units":      float(t["currentUnits"]),
                    "open_price": float(t["price"]),
                    "profit":     float(t["unrealizedPL"])
                }
            return trades
    except Exception as e:
        print(f"❌ Trades fetch error: {e}")
    return {}


# ─── Place Order ─────────────────────────────────────────────────────────────

def place_forex_order(pair, units):
    """
    Place a Forex order.
    Positive units = BUY, Negative units = SELL
    """
    try:
        order = {
            "order": {
                "type":        "MARKET",
                "instrument":  pair,
                "units":       str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT"
            }
        }
        r = requests.post(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/orders",
            headers=HEADERS,
            json=order,
            timeout=10
        )
        if r.status_code in [200, 201]:
            print(f"  ✅ Forex order placed: {'BUY' if units > 0 else 'SELL'} {abs(units)} {pair}")
            return r.json()
        else:
            print(f"  ❌ Order failed: {r.text}")
            return None
    except Exception as e:
        print(f"  ❌ Order error: {e}")
        return None


def close_trade(trade_id, pair):
    """Close an open forex trade."""
    try:
        r = requests.put(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/trades/{trade_id}/close",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            print(f"  ✅ Trade {trade_id} closed for {pair}")
            return r.json()
    except Exception as e:
        print(f"  ❌ Close trade error: {e}")
    return None


# ─── Main Forex Trading Loop ─────────────────────────────────────────────────

def run_forex_trader():
    """Main function — run this every few hours."""
    from telegram_alerts import alert_buy, alert_sell, alert_daily_summary

    print("\n💱 FOREX TRADER (OANDA PRACTICE)")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    account = get_account()
    if not account:
        print("❌ Cannot connect to OANDA. Check your token.")
        return

    print(f"💰 Balance:     {account['currency']} {account['balance']:,.2f}")
    print(f"📦 Open Trades: {account['open_trades']}")
    print("=" * 50)

    open_trades = get_open_trades()
    daily_pnl   = 0

    for pair, name in FOREX_PAIRS.items():
        print(f"\n📥 {name} ({pair})...")

        df = get_candles(pair)
        if df is None:
            print(f"  ⚠️ No data for {pair}")
            continue

        current_price = float(df["Close"].iloc[-1])
        signal, strength = get_forex_signal(df)

        # ── Stop Loss: close if down 3% ──
        if pair in open_trades:
            trade = open_trades[pair]
            loss_pct = trade["profit"] / (abs(trade["units"]) * trade["open_price"])
            if loss_pct <= -0.03:
                print(f"  🛑 STOP LOSS: closing {pair}")
                result = close_trade(trade["id"], pair)
                if result:
                    alert_sell(name, abs(int(trade["units"])), current_price,
                                trade["profit"], market="FOREX", currency="")
                    daily_pnl += trade["profit"]
                continue

        print(f"  💲 Price: {current_price:.5f} | Signal: {signal} (strength: {strength})")

        if signal == "BUY" and pair not in open_trades:
            order = place_forex_order(pair, UNITS_PER_TRADE)
            if order:
                alert_buy(name, UNITS_PER_TRADE, current_price, market="FOREX", currency="")

        elif signal == "SELL" and pair in open_trades:
            trade  = open_trades[pair]
            result = close_trade(trade["id"], pair)
            if result:
                alert_sell(name, abs(int(trade["units"])), current_price,
                            trade["profit"], market="FOREX", currency="")
                daily_pnl += trade["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.5)

    # Summary
    open_trades_after = get_open_trades()
    total_forex_pnl   = sum(t["profit"] for t in open_trades_after.values())
    account_after     = get_account()

    print("\n" + "=" * 50)
    print("📊 FOREX SESSION DONE")
    print(f"💰 Balance: {account_after['balance']:,.2f}")
    print(f"📈 Open P/L: {total_forex_pnl:,.2f}")
    print("=" * 50)

    alert_daily_summary(
        balance=account_after["balance"],
        total_profit=total_forex_pnl,
        holdings_count=len(open_trades_after),
        daily_pnl=daily_pnl,
        market="💱 Forex"
    )


if __name__ == "__main__":
    run_forex_trader()