import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import time

# ============================================
# FOREX TRADER — TWELVE DATA API
# No MT5 app needed! Works on cloud 24x7!
# ============================================

TWELVE_API_KEY = "1355898cfc1a4adf8407092ca7dd4b32"

FOREX_PAIRS = {
    "EUR/USD": "Euro / US Dollar",
    "GBP/USD": "British Pound / Dollar",
    "USD/JPY": "Dollar / Japanese Yen",
    "AUD/USD": "Australian Dollar / Dollar",
    "USD/CHF": "Dollar / Swiss Franc",
    "USD/CAD": "Dollar / Canadian Dollar",
    "XAU/USD": "Gold / US Dollar",
}

# Paper portfolio file — since we have no real forex broker on cloud
# This simulates trades with fake money, tracks P/L correctly
import json, os
PORTFOLIO_FILE = "logs/forex_portfolio.json"
INITIAL_BALANCE = 10000.0


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {
        "balance":      INITIAL_BALANCE,
        "positions":    {},
        "total_profit": 0.0,
        "trades":       []
    }

def save_portfolio(p):
    os.makedirs("logs", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)


def get_forex_data(pair, outputsize=150):
    """Fetch OHLCV data from Twelve Data API."""
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol":     pair,
            "interval":   "1day",
            "outputsize": outputsize,
            "apikey":     TWELVE_API_KEY
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if data.get("status") == "error":
            print(f"  ❌ Twelve Data error: {data.get('message')}")
            return None

        values = data.get("values", [])
        if len(values) < 50:
            print(f"  ⚠️ Not enough data for {pair}")
            return None

        df = pd.DataFrame(values)
        df = df.rename(columns={
            "open":   "Open",
            "high":   "High",
            "low":    "Low",
            "close":  "Close",
            "volume": "Volume"
        })
        df = df[["Open", "High", "Low", "Close"]].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)  # oldest first

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
        print(f"  ❌ Data fetch error: {e}")
        return None


def get_signal(df):
    """Generate BUY / SELL / HOLD signal."""
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    if last["RSI"] < 35:    buy_s  += 2
    elif last["RSI"] > 65:  sell_s += 2

    if (last["MACD"] > last["MACD_Signal"] and
            second["MACD"] <= second["MACD_Signal"]):
        buy_s += 2
    elif (last["MACD"] < last["MACD_Signal"] and
            second["MACD"] >= second["MACD_Signal"]):
        sell_s += 2

    if last["Close"] > last["EMA_20"] > last["EMA_50"]:   buy_s  += 1
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]: sell_s += 1

    if last["Close"] <= last["BB_Lower"]:   buy_s  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_s += 1

    # Skip if too volatile
    if last["ATR"] > df["ATR"].mean() * 2.5:
        return "HOLD", 0

    if buy_s  >= 3: return "BUY",  buy_s
    if sell_s >= 3: return "SELL", sell_s
    return "HOLD", 0


def run_twelvedata_forex_trader():
    """Main forex trading function using Twelve Data."""
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass

    print("\n💱 FOREX TRADER — TWELVE DATA")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    portfolio  = load_portfolio()
    daily_pnl  = 0.0
    invest_pct = 0.10   # 10% of balance per trade

    print(f"💰 Balance:   ${portfolio['balance']:,.2f}")
    print(f"📦 Positions: {len(portfolio['positions'])}")
    print(f"📈 Total P/L: ${portfolio['total_profit']:,.2f}")
    print("=" * 50)

    for pair, name in FOREX_PAIRS.items():
        print(f"\n📥 {name} ({pair})...")

        df = get_forex_data(pair)
        if df is None:
            time.sleep(1)   # respect rate limit
            continue

        current_price = float(df["Close"].iloc[-1])
        signal, strength = get_signal(df)

        safe_pair = pair.replace("/", "_")

        # ── Stop loss: close if down 5% ──────────────────────────────────────
        if safe_pair in portfolio["positions"]:
            pos      = portfolio["positions"][safe_pair]
            buy_price = pos["buy_price"]
            loss_pct  = (current_price - buy_price) / buy_price

            if loss_pct <= -0.05:
                # Close position
                units   = pos["units"]
                profit  = (current_price - buy_price) * units
                portfolio["balance"]      += pos["cost"] + profit
                portfolio["total_profit"] += profit
                daily_pnl += profit
                del portfolio["positions"][safe_pair]

                portfolio["trades"].append({
                    "time":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "pair":   pair,
                    "action": "STOP LOSS",
                    "price":  current_price,
                    "profit": profit
                })
                print(f"  🛑 STOP LOSS! Closed @ {current_price:.5f} | Loss: ${profit:.2f}")
                alert_sell(name, units, current_price, profit, market="FOREX", currency="$")
                save_portfolio(portfolio)
                time.sleep(1)
                continue

        print(f"  💲 Price: {current_price:.5f} | Signal: {signal} (strength {strength})")

        # ── BUY ───────────────────────────────────────────────────────────────
        if signal == "BUY" and safe_pair not in portfolio["positions"]:
            invest  = portfolio["balance"] * invest_pct
            units   = invest / current_price
            cost    = units * current_price

            if portfolio["balance"] >= cost:
                portfolio["balance"] -= cost
                portfolio["positions"][safe_pair] = {
                    "pair":      pair,
                    "units":     units,
                    "buy_price": current_price,
                    "cost":      cost,
                    "time":      datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                portfolio["trades"].append({
                    "time":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "pair":   pair,
                    "action": "BUY",
                    "price":  current_price,
                    "units":  units,
                    "cost":   cost
                })
                print(f"  ✅ BOUGHT {units:.4f} units @ {current_price:.5f} | Cost: ${cost:.2f}")
                alert_buy(name, round(units, 4), current_price, market="FOREX", currency="$")
                save_portfolio(portfolio)

        # ── SELL ──────────────────────────────────────────────────────────────
        elif signal == "SELL" and safe_pair in portfolio["positions"]:
            pos       = portfolio["positions"][safe_pair]
            units     = pos["units"]
            buy_price = pos["buy_price"]
            profit    = (current_price - buy_price) * units

            portfolio["balance"]      += pos["cost"] + profit
            portfolio["total_profit"] += profit
            daily_pnl += profit
            del portfolio["positions"][safe_pair]

            portfolio["trades"].append({
                "time":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                "pair":   pair,
                "action": "SELL",
                "price":  current_price,
                "profit": profit
            })
            emoji = "💰" if profit >= 0 else "📉"
            print(f"  {emoji} SOLD @ {current_price:.5f} | Profit: ${profit:.2f}")
            alert_sell(name, round(units, 4), current_price, profit, market="FOREX", currency="$")
            save_portfolio(portfolio)

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(1)   # Twelve Data rate limit — 8 calls/min on free plan

    # ── Summary ───────────────────────────────────────────────────────────────
    total_value = portfolio["balance"]
    for safe_pair, pos in portfolio["positions"].items():
        # Approximate current value
        total_value += pos["cost"]

    print("\n" + "=" * 50)
    print("📊 FOREX SESSION DONE")
    print(f"💰 Balance:    ${portfolio['balance']:,.2f}")
    print(f"📦 Positions:  {len(portfolio['positions'])}")
    print(f"📅 Today P/L:  ${daily_pnl:,.2f}")
    print(f"🏦 Total P/L:  ${portfolio['total_profit']:,.2f}")
    print("=" * 50)

    alert_daily_summary(
        balance=portfolio["balance"],
        total_profit=portfolio["total_profit"],
        holdings_count=len(portfolio["positions"]),
        daily_pnl=daily_pnl,
        market="💱 Forex (Twelve Data)"
    )


if __name__ == "__main__":
    run_twelvedata_forex_trader()