import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import time
import json
import os

ALPACA_API_KEY    = "PK72YCIH6UAJXUH2RLYHZHYCYA"
ALPACA_SECRET_KEY = "4mXCdKWwmCN8sHwBGnwrduyi3HW1bvE6ZBGBKhE5w9ve"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type":        "application/json"
}

# ── Trading Rules ─────────────────────────────────────────────────────────────
STOP_LOSS_PCT      = -0.05   # Sell if down 5%
TAKE_PROFIT_PCT    =  0.08   # Sell if up 8%
TRAILING_STOP_PCT  =  0.03   # Sell if drops 3% from peak
INVEST_PCT         =  0.08   # Invest 8% of buying power per stock

# ── Peak tracker (trails profit) ─────────────────────────────────────────────
PEAKS_FILE = "logs/price_peaks.json"

def load_peaks():
    if os.path.exists(PEAKS_FILE):
        with open(PEAKS_FILE) as f:
            return json.load(f)
    return {}

def save_peaks(peaks):
    os.makedirs("logs", exist_ok=True)
    with open(PEAKS_FILE, "w") as f:
        json.dump(peaks, f, indent=2)

US_STOCKS = {
    "AAPL": "Apple",    "MSFT": "Microsoft", "GOOGL": "Google",
    "AMZN": "Amazon",   "NVDA": "Nvidia",    "META":  "Meta",
    "TSLA": "Tesla",    "NFLX": "Netflix",   "AMD":   "AMD",
    "PYPL": "PayPal",   "DIS":  "Disney",    "UBER":  "Uber",
    "SHOP": "Shopify",  "COIN": "Coinbase",  "BABA":  "Alibaba",
}


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
        print(f"❌ Account: {e}")
    return None


def get_price_data(symbol, days=150):
    try:
        end   = datetime.now()
        start = end - timedelta(days=days + 50)
        url   = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": "1Day",
            "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit":     200, "feed": "iex"
        }
        r    = requests.get(url, headers=HEADERS, params=params, timeout=15)
        bars = []
        if r.status_code == 200:
            bars = r.json().get("bars", [])

        if len(bars) < 50:
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


def place_order(symbol, qty, side):
    try:
        r = requests.post(
            f"{ALPACA_BASE_URL}/v2/orders",
            headers=HEADERS,
            json={"symbol": symbol, "qty": str(qty), "side": side,
                  "type": "market", "time_in_force": "day"},
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
                } for p in r.json()
            }
    except:
        pass
    return {}


def get_signal(df):
    """Simple reliable signal."""
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    if last["RSI"] < 35:   buy_s  += 2
    elif last["RSI"] > 65: sell_s += 2

    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_s += 2
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_s += 2

    if last["Close"] > last["EMA_20"] > last["EMA_50"]:   buy_s  += 1
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]: sell_s += 1

    if last["Close"] <= last["BB_Lower"]:   buy_s  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_s += 1

    # Also try ensemble
    try:
        from ensemble_trader import get_ensemble
        ensemble = get_ensemble()
        e_signal, e_conf, _ = ensemble.vote(df)
        if e_signal == "BUY":   buy_s  += 2
        elif e_signal == "SELL": sell_s += 2
    except:
        pass

    if buy_s  >= 3: return "BUY"
    if sell_s >= 3: return "SELL"
    return "HOLD"


def run_us_trader():
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary, send_alert
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass
        def send_alert(*a, **k): pass

    print("\n🇺🇸 US TRADER — AUTO PROFIT PROTECTION")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛑 Stop Loss:     {STOP_LOSS_PCT*100:.0f}%")
    print(f"💰 Take Profit:   {TAKE_PROFIT_PCT*100:.0f}%")
    print(f"📉 Trailing Stop: {TRAILING_STOP_PCT*100:.0f}% from peak")

    account = get_account()
    if not account:
        print("❌ Cannot connect to Alpaca")
        return

    print(f"\n💰 Balance:      ${account['balance']:,.2f}")
    print(f"📦 Portfolio:    ${account['portfolio']:,.2f}")
    print(f"⚡ Buying Power: ${account['buying_power']:,.2f}")
    print("=" * 60)

    positions = get_positions()
    peaks     = load_peaks()
    daily_pnl = 0

    # ── Check existing positions ───────────────────────────────────────────────
    for symbol, pos in positions.items():
        price     = pos["current"]
        buy_price = pos["buy_price"]
        profit_pct = pos["profit_pct"] / 100
        name      = US_STOCKS.get(symbol, symbol)

        print(f"\n📊 {name} ({symbol})")
        print(f"   Buy: ${buy_price:.2f} | Now: ${price:.2f} | P/L: {profit_pct*100:.1f}%")

        # Update peak price for trailing stop
        if symbol not in peaks or price > peaks[symbol]:
            peaks[symbol] = price
            save_peaks(peaks)

        peak_price   = peaks.get(symbol, buy_price)
        drop_from_peak = (price - peak_price) / peak_price

        # ── TRAILING STOP — most important! ──
        if drop_from_peak <= -TRAILING_STOP_PCT and profit_pct > 0:
            print(f"   📉 TRAILING STOP! Dropped {drop_from_peak*100:.1f}% from peak ${peak_price:.2f}")
            print(f"   🔒 Locking in profit: ${pos['profit']:.2f}")
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                daily_pnl += pos["profit"]
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                if symbol in peaks:
                    del peaks[symbol]
                    save_peaks(peaks)
            continue

        # ── STOP LOSS ──
        if profit_pct <= STOP_LOSS_PCT:
            print(f"   🛑 STOP LOSS triggered! Loss: {profit_pct*100:.1f}%")
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                daily_pnl += pos["profit"]
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                if symbol in peaks:
                    del peaks[symbol]
                    save_peaks(peaks)
            continue

        # ── TAKE PROFIT ──
        if profit_pct >= TAKE_PROFIT_PCT:
            print(f"   💰 TAKE PROFIT! Gain: {profit_pct*100:.1f}%")
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                daily_pnl += pos["profit"]
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                if symbol in peaks:
                    del peaks[symbol]
                    save_peaks(peaks)
            continue

        print(f"   ⏸️ Holding | Peak: ${peak_price:.2f} | Drop from peak: {drop_from_peak*100:.1f}%")

    # ── Buy new positions ──────────────────────────────────────────────────────
    positions_after = get_positions()
    account_fresh   = get_account()

    if account_fresh and account_fresh["buying_power"] > 1000:
        for symbol, name in US_STOCKS.items():
            if symbol in positions_after:
                continue  # Already holding

            df = get_price_data(symbol)
            if df is None:
                continue

            signal = get_signal(df)
            price  = float(df["Close"].iloc[-1])

            print(f"\n📥 {name} ({symbol}) — Signal: {signal}")

            if signal == "BUY":
                invest = account_fresh["buying_power"] * INVEST_PCT
                shares = int(invest // price)
                if shares > 0:
                    print(f"   💰 Buying {shares} shares @ ${price:.2f}")
                    order = place_order(symbol, shares, "buy")
                    if order:
                        peaks[symbol] = price  # Start tracking peak
                        save_peaks(peaks)
                        alert_buy(name, shares, price, "US")

            time.sleep(0.3)

    # ── Final summary ──────────────────────────────────────────────────────────
    account_final   = get_account()
    positions_final = get_positions()
    open_pnl        = sum(p["profit"] for p in positions_final.values())

    print("\n" + "=" * 60)
    print("📊 SESSION COMPLETE")
    print(f"💰 Balance:      ${account_final['balance']:,.2f}")
    print(f"📦 Positions:    {len(positions_final)}")
    print(f"📈 Unrealized:   ${open_pnl:,.2f}")
    print(f"📅 Sold Today:   ${daily_pnl:,.2f}")
    print("=" * 60)

    alert_daily_summary(
        balance=account_final["balance"],
        total_profit=open_pnl + daily_pnl,
        holdings_count=len(positions_final),
        daily_pnl=daily_pnl,
        market="🇺🇸 US Stocks"
    )


if __name__ == "__main__":
    run_us_trader()