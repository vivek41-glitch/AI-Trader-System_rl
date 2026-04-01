import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import time
import json
import os

# ============================================
# ALPACA US TRADER v2
# NOW WITH:
# ✅ Risk Manager connected
# ✅ Stop Loss (-5%)
# ✅ Take Profit (+8%)
# ✅ yfinance fallback when market closed
# ✅ More stocks (15 instead of 7)
# ============================================

ALPACA_API_KEY    = "YOUR_ALPACA_API_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET_KEY"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type":        "application/json"
}

# Expanded stock list (15 stocks now!)
US_STOCKS = {
    "AAPL":  "Apple",
    "TSLA":  "Tesla",
    "MSFT":  "Microsoft",
    "GOOGL": "Google",
    "AMZN":  "Amazon",
    "NVDA":  "Nvidia",
    "META":  "Meta",
    "NFLX":  "Netflix",
    "AMD":   "AMD",
    "PYPL":  "PayPal",
    "DIS":   "Disney",
    "BABA":  "Alibaba",
    "UBER":  "Uber",
    "SHOP":  "Shopify",
    "COIN":  "Coinbase",
}

from risk_manager import RiskManager
risk = RiskManager(initial_balance=100000)


def get_account():
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {
                "balance":      float(d["cash"]),
                "portfolio":    float(d["portfolio_value"]),
                "buying_power": float(d["buying_power"]),
            }
    except Exception as e:
        print(f"❌ Account error: {e}")
    return None


def get_price_data(symbol, days=150):
    """Alpaca first, yfinance fallback — always gets data."""
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 50)
        url   = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": "1Day",
            "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit":     200,
            "feed":      "iex"
        }
        r    = requests.get(url, headers=HEADERS, params=params, timeout=15)
        bars = []
        if r.status_code == 200:
            bars = r.json().get("bars", [])

        if len(bars) < 50:
            print(f"  ℹ️ Using yfinance fallback for {symbol}")
            import yfinance as yf
            df_yf = yf.download(symbol, period="200d", interval="1d",
                                auto_adjust=True, progress=False)
            if len(df_yf) < 50:
                return None
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)
            df = df_yf[["Open","High","Low","Close","Volume"]].astype(float).dropna().reset_index(drop=True)
        else:
            df = pd.DataFrame(bars)
            df = df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"})
            df = df.astype(float)

        # Add indicators
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
        df["ATR"]         = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        return df.dropna().reset_index(drop=True)

    except Exception as e:
        print(f"  ❌ Data error {symbol}: {e}")
        return None


def get_signal(df):
    """Multi-indicator signal with confidence score."""
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    # RSI
    if last["RSI"] < 30:   buy_s  += 3   # Very oversold
    elif last["RSI"] < 40: buy_s  += 1
    elif last["RSI"] > 70: sell_s += 3   # Very overbought
    elif last["RSI"] > 60: sell_s += 1

    # MACD crossover
    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_s += 3
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_s += 3

    # EMA trend
    if last["Close"] > last["EMA_20"] > last["EMA_50"]:   buy_s  += 2
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]: sell_s += 2

    # Bollinger
    if last["Close"] <= last["BB_Lower"]:   buy_s  += 2
    elif last["Close"] >= last["BB_Upper"]: sell_s += 2

    # Volume confirmation
    avg_vol = df["Volume"].iloc[-10:].mean()
    if last["Volume"] > avg_vol * 1.5:
        buy_s  += 1 if buy_s > sell_s else 0
        sell_s += 1 if sell_s > buy_s else 0

    # ATR filter
    if last["ATR"] > df["ATR"].mean() * 3:
        return "HOLD", 0   # Too volatile

    confidence = max(buy_s, sell_s) / 10.0

    if buy_s  >= 4: return "BUY",  confidence
    if sell_s >= 4: return "SELL", confidence
    return "HOLD", 0


def place_order(symbol, qty, side):
    try:
        r = requests.post(
            f"{ALPACA_BASE_URL}/v2/orders",
            headers=HEADERS,
            json={
                "symbol": symbol, "qty": str(qty),
                "side": side, "type": "market", "time_in_force": "day"
            },
            timeout=10
        )
        if r.status_code in [200, 201]:
            print(f"  ✅ {side.upper()} {qty} {symbol}")
            return r.json()
        else:
            print(f"  ❌ Order failed: {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Order error: {e}")
    return None


def get_positions():
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return {
                p["symbol"]: {
                    "shares":     float(p["qty"]),
                    "buy_price":  float(p["avg_entry_price"]),
                    "current":    float(p["current_price"]),
                    "profit":     float(p["unrealized_pl"]),
                    "profit_pct": float(p["unrealized_plpc"]) * 100
                }
                for p in r.json()
            }
    except Exception as e:
        print(f"❌ Positions error: {e}")
    return {}


def run_us_trader():
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass

    print("\n🇺🇸 US STOCK TRADER v2 (ALPACA)")
    print("=" * 55)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    account = get_account()
    if not account:
        print("❌ Cannot connect to Alpaca")
        return

    print(f"💰 Balance:      ${account['balance']:,.2f}")
    print(f"📦 Portfolio:    ${account['portfolio']:,.2f}")
    print(f"⚡ Buying Power: ${account['buying_power']:,.2f}")

    # Risk check
    risk.update_peak(account["portfolio"])
    can_trade, reason = risk.can_trade(account["portfolio"])
    if not can_trade:
        print(f"\n{reason}")
        try:
            from telegram_alerts_v2 import send_alert
            send_alert(reason, "error")
        except:
            pass
        return

    print("=" * 55)

    positions  = get_positions()
    daily_pnl  = 0
    invest_amt = account["buying_power"] * 0.08   # 8% per trade (safer)

    for symbol, name in US_STOCKS.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_price_data(symbol)
        if df is None:
            continue

        price  = float(df["Close"].iloc[-1])
        signal, confidence = get_signal(df)

        # ── Stop Loss & Take Profit Check ──────────────────
        if symbol in positions:
            pos = positions[symbol]

            # Stop Loss
            if risk.should_stop_loss(pos["buy_price"], price):
                print(f"  🛑 STOP LOSS! Loss: {pos['profit_pct']:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    risk.record_trade()
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

            # Take Profit
            if risk.should_take_profit(pos["buy_price"], price):
                print(f"  💰 TAKE PROFIT! Gain: {pos['profit_pct']:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    risk.record_trade()
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

        print(f"  💲 ${price:.2f} | Signal: {signal} | Confidence: {confidence:.0%}")

        # ── Execute Signal ──────────────────────────────────
        if signal == "BUY" and symbol not in positions:
            shares = int(invest_amt // price)
            if shares > 0:
                order = place_order(symbol, shares, "buy")
                if order:
                    risk.record_trade()
                    alert_buy(name, shares, price, "US")

        elif signal == "SELL" and symbol in positions:
            pos   = positions[symbol]
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                risk.record_trade()
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                daily_pnl += pos["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.3)

    # Summary
    account_after = get_account()
    positions_after = get_positions()
    open_pnl = sum(p["profit"] for p in positions_after.values())
    risk_stats = risk.get_stats(account_after["portfolio"])

    print("\n" + "=" * 55)
    print("📊 US SESSION DONE")
    print(f"💰 Balance:       ${account_after['balance']:,.2f}")
    print(f"📈 Open P/L:      ${open_pnl:,.2f}")
    print(f"📅 Today Trades:  ${daily_pnl:,.2f}")
    print(f"📉 Drawdown:      {risk_stats['drawdown']:.1f}%")
    print(f"🔢 Trades today:  {risk_stats['trades_today']}")
    print("=" * 55)

    alert_daily_summary(
        balance=account_after["balance"],
        total_profit=open_pnl,
        holdings_count=len(positions_after),
        daily_pnl=daily_pnl,
        market="🇺🇸 US Stocks"
    )


if __name__ == "__main__":
    run_us_trader()