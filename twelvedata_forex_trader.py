import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
import json, os, time

# ============================================
# TWELVE DATA FOREX TRADER v2
# NOW WITH:
# ✅ Risk Manager connected
# ✅ Stop Loss (-3%)
# ✅ Take Profit (+5%)
# ✅ Market regime detection
# ✅ More pairs
# ============================================

TWELVE_DATA_KEY = "1355898cfc1a4adf8407092ca7dd4b32"
BASE_URL        = "https://api.twelvedata.com"

FOREX_PAIRS = {
    "EUR/USD": "Euro / Dollar",
    "GBP/USD": "British Pound / Dollar",
    "USD/JPY": "Dollar / Yen",
    "AUD/USD": "Australian Dollar",
    "USD/CHF": "Dollar / Swiss Franc",
    "USD/CAD": "Dollar / Canadian",
    "XAU/USD": "Gold",
    "EUR/GBP": "Euro / British Pound",
}

PORTFOLIO_FILE  = "logs/forex_portfolio.json"
INITIAL_BALANCE = 10000.0

from risk_manager import RiskManager
risk = RiskManager(initial_balance=INITIAL_BALANCE)
risk.stop_loss_pct    = 0.03   # Tighter for forex
risk.take_profit_pct  = 0.05   # Faster profit taking


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"balance": INITIAL_BALANCE, "holdings": {}, "total_profit": 0, "trades": []}

def save_portfolio(p):
    os.makedirs("logs", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)


def get_forex_data(pair, outputsize=150):
    try:
        r = requests.get(
            f"{BASE_URL}/time_series",
            params={"symbol": pair, "interval": "1day",
                    "outputsize": outputsize, "apikey": TWELVE_DATA_KEY},
            timeout=15
        )
        data = r.json()
        if data.get("status") == "error":
            return None

        values = data.get("values", [])
        if len(values) < 50:
            return None

        df = pd.DataFrame(values).rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume"
        })
        for col in ["Open","High","Low","Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().reset_index(drop=True)

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
        print(f"  ❌ Data error: {e}")
        return None


def detect_regime(df):
    """Detect if market is trending or sideways."""
    last = df.iloc[-1]
    ema_diff = abs(last["EMA_20"] - last["EMA_50"]) / last["EMA_50"]

    if ema_diff > 0.005:
        if last["EMA_20"] > last["EMA_50"]:
            return "UPTREND"
        else:
            return "DOWNTREND"
    else:
        return "SIDEWAYS"


def get_signal(df):
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    # Regime check — skip sideways market
    regime = detect_regime(df)
    if regime == "SIDEWAYS":
        return "HOLD", 0, regime

    if last["RSI"] < 35:   buy_s  += 2
    elif last["RSI"] > 65: sell_s += 2

    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_s += 3
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_s += 3

    if last["Close"] > last["EMA_20"] > last["EMA_50"]:   buy_s  += 2
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]: sell_s += 2

    if last["Close"] <= last["BB_Lower"]:   buy_s  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_s += 1

    # ATR filter
    if last["ATR"] > df["ATR"].mean() * 2.5:
        return "HOLD", 0, regime

    if buy_s  >= 4: return "BUY",  buy_s/8, regime
    if sell_s >= 4: return "SELL", sell_s/8, regime
    return "HOLD", 0, regime


def run_twelvedata_forex_trader():
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass

    print("\n💱 TWELVE DATA FOREX TRADER v2")
    print("=" * 55)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    portfolio = load_portfolio()
    daily_pnl = 0

    # Risk check
    risk.update_peak(portfolio["balance"])
    can_trade, reason = risk.can_trade(portfolio["balance"])
    if not can_trade:
        print(f"\n{reason}")
        return

    print(f"💰 Balance:   ${portfolio['balance']:,.2f}")
    print(f"📦 Holdings:  {len(portfolio['holdings'])}")
    print("=" * 55)

    for pair, name in FOREX_PAIRS.items():
        print(f"\n📥 {name} ({pair})...")

        df = get_forex_data(pair)
        if df is None:
            time.sleep(1)
            continue

        price = float(df["Close"].iloc[-1])
        signal, confidence, regime = get_signal(df)
        safe_pair = pair.replace("/", "_")

        print(f"  📊 Regime: {regime}")

        # Stop Loss & Take Profit
        if safe_pair in portfolio["holdings"]:
            h = portfolio["holdings"][safe_pair]

            if risk.should_stop_loss(h["buy_price"], price):
                profit = (price - h["buy_price"]) * h["units"]
                portfolio["balance"]      += h["cost"] + profit
                portfolio["total_profit"] += profit
                daily_pnl                 += profit
                del portfolio["holdings"][safe_pair]
                save_portfolio(portfolio)
                print(f"  🛑 STOP LOSS! Loss: ${profit:.2f}")
                alert_sell(name, h["units"], price, profit, "FOREX", "$")
                time.sleep(1)
                continue

            if risk.should_take_profit(h["buy_price"], price):
                profit = (price - h["buy_price"]) * h["units"]
                portfolio["balance"]      += h["cost"] + profit
                portfolio["total_profit"] += profit
                daily_pnl                 += profit
                del portfolio["holdings"][safe_pair]
                save_portfolio(portfolio)
                print(f"  💰 TAKE PROFIT! Gain: ${profit:.2f}")
                alert_sell(name, h["units"], price, profit, "FOREX", "$")
                time.sleep(1)
                continue

        print(f"  💲 {price:.5f} | {signal} | Confidence: {confidence:.0%}")

        if signal == "BUY" and safe_pair not in portfolio["holdings"]:
            invest = portfolio["balance"] * 0.10
            units  = round(invest / price, 4)
            cost   = units * price
            if portfolio["balance"] >= cost:
                portfolio["balance"] -= cost
                portfolio["holdings"][safe_pair] = {
                    "pair": pair, "name": name, "units": units,
                    "buy_price": price, "cost": cost,
                    "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                portfolio["trades"].append({
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "pair": pair, "action": "BUY", "price": price
                })
                save_portfolio(portfolio)
                risk.record_trade()
                print(f"  ✅ BOUGHT {units:.4f} units @ {price:.5f}")
                alert_buy(name, units, price, "FOREX", "$")

        elif signal == "SELL" and safe_pair in portfolio["holdings"]:
            h      = portfolio["holdings"][safe_pair]
            profit = (price - h["buy_price"]) * h["units"]
            portfolio["balance"]      += h["cost"] + profit
            portfolio["total_profit"] += profit
            daily_pnl                 += profit
            del portfolio["holdings"][safe_pair]
            save_portfolio(portfolio)
            risk.record_trade()
            print(f"  {'💰' if profit >= 0 else '📉'} SOLD | Profit: ${profit:.2f}")
            alert_sell(name, h["units"], price, profit, "FOREX", "$")

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(1)

    risk_stats = risk.get_stats(portfolio["balance"])
    print("\n" + "=" * 55)
    print("📊 FOREX SESSION DONE")
    print(f"💰 Balance:      ${portfolio['balance']:,.2f}")
    print(f"📈 Total Profit: ${portfolio['total_profit']:,.2f}")
    print(f"📉 Drawdown:     {risk_stats['drawdown']:.1f}%")
    print("=" * 55)

    alert_daily_summary(
        balance=portfolio["balance"],
        total_profit=portfolio["total_profit"],
        holdings_count=len(portfolio["holdings"]),
        daily_pnl=daily_pnl,
        market="💱 Forex (Twelve Data)"
    )


if __name__ == "__main__":
    run_twelvedata_forex_trader()