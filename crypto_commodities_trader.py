import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
import json, os, time

# ============================================
# CRYPTO + COMMODITIES TRADER v1
# Trades via Twelve Data (FREE)
# ============================================
# CRYPTO (10 coins):
#   BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, MATIC, DOT
# COMMODITIES (6):
#   Gold, Silver, Oil, Natural Gas, Platinum, Copper
# ============================================

TWELVE_DATA_KEY = "1355898cfc1a4adf8407092ca7dd4b32"
BASE_URL        = "https://api.twelvedata.com"

# ── Crypto pairs ─────────────────────────────
CRYPTO = {
    "BTC/USD":   "Bitcoin",
    "ETH/USD":   "Ethereum",
    "BNB/USD":   "Binance Coin",
    "SOL/USD":   "Solana",
    "XRP/USD":   "Ripple",
    "ADA/USD":   "Cardano",
    "DOGE/USD":  "Dogecoin",
    "AVAX/USD":  "Avalanche",
    "MATIC/USD": "Polygon",
    "DOT/USD":   "Polkadot",
}

# ── Commodities ───────────────────────────────
COMMODITIES = {
    "XAU/USD":  "Gold",
    "XAG/USD":  "Silver",
    "BRENT":    "Brent Crude Oil",
    "WTI":      "WTI Crude Oil",
    "XPT/USD":  "Platinum",
    "COPPER":   "Copper",
}

PORTFOLIO_FILE  = "logs/crypto_commodities_portfolio.json"
INITIAL_BALANCE = 10000.0

from risk_manager import RiskManager
risk_crypto = RiskManager(initial_balance=INITIAL_BALANCE)
risk_crypto.stop_loss_pct    = 0.07   # Crypto more volatile — 7% stop
risk_crypto.take_profit_pct  = 0.12   # 12% take profit for crypto
risk_crypto.max_risk_per_trade = 0.08  # 8% per trade


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {
        "balance":      INITIAL_BALANCE,
        "holdings":     {},
        "total_profit": 0,
        "trades":       []
    }

def save_portfolio(p):
    os.makedirs("logs", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)


def get_data(symbol, outputsize=150):
    """Fetch OHLCV from Twelve Data."""
    try:
        r = requests.get(
            f"{BASE_URL}/time_series",
            params={
                "symbol":     symbol,
                "interval":   "1day",
                "outputsize": outputsize,
                "apikey":     TWELVE_DATA_KEY
            },
            timeout=15
        )
        data = r.json()
        if data.get("status") == "error":
            print(f"  ⚠️ {data.get('message', 'API error')}")
            return None

        values = data.get("values", [])
        if len(values) < 50:
            return None

        df = pd.DataFrame(values).rename(columns={
            "open": "Open", "high": "High",
            "low":  "Low",  "close": "Close",
            "volume": "Volume"
        })
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna().reset_index(drop=True)

        # Indicators
        df["RSI"]         = ta.rsi(df["Close"], length=14)
        macd              = ta.macd(df["Close"])
        df["MACD"]        = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
        df["EMA_20"]      = ta.ema(df["Close"], length=20)
        df["EMA_50"]      = ta.ema(df["Close"], length=50)
        df["EMA_200"]     = ta.ema(df["Close"], length=min(200, len(df)-1))
        bb                = ta.bbands(df["Close"], length=20)
        df["BB_Upper"]    = bb[bb.columns[0]]
        df["BB_Mid"]      = bb[bb.columns[1]]
        df["BB_Lower"]    = bb[bb.columns[2]]
        df["ATR"]         = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        # Stochastic (extra for crypto)
        stoch             = ta.stoch(df["High"], df["Low"], df["Close"])
        df["STOCH_K"]     = stoch["STOCHk_14_3_3"]
        df["STOCH_D"]     = stoch["STOCHd_14_3_3"]

        return df.dropna().reset_index(drop=True)

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def detect_regime(df):
    last    = df.iloc[-1]
    ema_diff = abs(last["EMA_20"] - last["EMA_50"]) / last["EMA_50"]
    if ema_diff > 0.01:          # Crypto needs wider threshold
        return "UPTREND" if last["EMA_20"] > last["EMA_50"] else "DOWNTREND"
    return "SIDEWAYS"


def get_signal(df, is_crypto=False):
    """Enhanced signal with stochastic for crypto."""
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    regime = detect_regime(df)
    if regime == "SIDEWAYS" and not is_crypto:
        return "HOLD", 0, regime

    # RSI
    threshold_low  = 35 if is_crypto else 30
    threshold_high = 65 if is_crypto else 70
    if last["RSI"] < threshold_low:   buy_s  += 2
    elif last["RSI"] > threshold_high: sell_s += 2

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

    # Stochastic (crypto extra signal)
    if is_crypto:
        if last["STOCH_K"] < 20 and last["STOCH_K"] > last["STOCH_D"]:
            buy_s += 2
        elif last["STOCH_K"] > 80 and last["STOCH_K"] < last["STOCH_D"]:
            sell_s += 2

    # EMA 200 trend filter
    if "EMA_200" in df.columns:
        if last["Close"] > last["EMA_200"]:
            buy_s  += 1
        else:
            sell_s += 1

    # ATR volatility filter
    if last["ATR"] > df["ATR"].mean() * 3.5:
        return "HOLD", 0, regime

    min_signals = 5 if is_crypto else 4
    if buy_s  >= min_signals: return "BUY",  buy_s/10,  regime
    if sell_s >= min_signals: return "SELL", sell_s/10, regime
    return "HOLD", 0, regime


def run_trader_for_assets(assets, label, is_crypto=False):
    """Generic runner for crypto or commodities."""
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass

    portfolio = load_portfolio()
    daily_pnl = 0

    risk_crypto.update_peak(portfolio["balance"])
    can, reason = risk_crypto.can_trade(portfolio["balance"])
    if not can:
        print(f"\n{reason}")
        return

    print(f"\n💰 Balance: ${portfolio['balance']:,.2f} | Holdings: {len(portfolio['holdings'])}")
    print("=" * 55)

    for symbol, name in assets.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_data(symbol)
        if df is None:
            time.sleep(2)
            continue

        price     = float(df["Close"].iloc[-1])
        signal, confidence, regime = get_signal(df, is_crypto=is_crypto)
        safe_sym  = symbol.replace("/", "_")

        # Stop Loss & Take Profit
        if safe_sym in portfolio["holdings"]:
            h = portfolio["holdings"][safe_sym]
            if risk_crypto.should_stop_loss(h["buy_price"], price):
                profit = (price - h["buy_price"]) * h["units"]
                portfolio["balance"]      += h["cost"] + profit
                portfolio["total_profit"] += profit
                daily_pnl                 += profit
                del portfolio["holdings"][safe_sym]
                save_portfolio(portfolio)
                print(f"  🛑 STOP LOSS! ${profit:.2f}")
                alert_sell(name, h["units"], price, profit, label, "$")
                time.sleep(1)
                continue

            if risk_crypto.should_take_profit(h["buy_price"], price):
                profit = (price - h["buy_price"]) * h["units"]
                portfolio["balance"]      += h["cost"] + profit
                portfolio["total_profit"] += profit
                daily_pnl                 += profit
                del portfolio["holdings"][safe_sym]
                save_portfolio(portfolio)
                print(f"  💰 TAKE PROFIT! ${profit:.2f}")
                alert_sell(name, h["units"], price, profit, label, "$")
                time.sleep(1)
                continue

        print(f"  💲 ${price:,.4f} | {signal} ({confidence:.0%}) | {regime}")

        invest = portfolio["balance"] * risk_crypto.max_risk_per_trade
        units  = round(invest / price, 6)
        cost   = units * price

        if signal == "BUY" and safe_sym not in portfolio["holdings"]:
            if portfolio["balance"] >= cost:
                portfolio["balance"] -= cost
                portfolio["holdings"][safe_sym] = {
                    "symbol": symbol, "name": name, "units": units,
                    "buy_price": price, "cost": cost,
                    "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                portfolio["trades"].append({
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "symbol": symbol, "action": "BUY",
                    "price": price, "units": units
                })
                save_portfolio(portfolio)
                risk_crypto.record_trade()
                print(f"  ✅ BOUGHT {units:.6f} units @ ${price:,.4f}")
                alert_buy(name, units, price, label, "$")

        elif signal == "SELL" and safe_sym in portfolio["holdings"]:
            h      = portfolio["holdings"][safe_sym]
            profit = (price - h["buy_price"]) * h["units"]
            portfolio["balance"]      += h["cost"] + profit
            portfolio["total_profit"] += profit
            daily_pnl                 += profit
            del portfolio["holdings"][safe_sym]
            save_portfolio(portfolio)
            risk_crypto.record_trade()
            e = "💰" if profit >= 0 else "📉"
            print(f"  {e} SOLD | Profit: ${profit:.2f}")
            alert_sell(name, h["units"], price, profit, label, "$")

        else:
            print("  ⏸️ HOLDING")

        time.sleep(1.5)  # Twelve Data rate limit

    return daily_pnl


def run_crypto_trader():
    """Trade all 10 crypto coins."""
    print("\n🪙 CRYPTO TRADER")
    print("=" * 55)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Trading: {', '.join(CRYPTO.values())}")

    pnl = run_trader_for_assets(CRYPTO, "🪙 CRYPTO", is_crypto=True)

    portfolio = load_portfolio()
    print(f"\n✅ Crypto session done | Total P/L: ${portfolio['total_profit']:.2f}")

    try:
        from telegram_alerts_v2 import alert_daily_summary
        alert_daily_summary(
            balance=portfolio["balance"],
            total_profit=portfolio["total_profit"],
            holdings_count=len(portfolio["holdings"]),
            daily_pnl=pnl or 0,
            market="🪙 Crypto (10 coins)"
        )
    except:
        pass


def run_commodities_trader():
    """Trade Gold, Silver, Oil etc."""
    print("\n🥇 COMMODITIES TRADER")
    print("=" * 55)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Trading: {', '.join(COMMODITIES.values())}")

    pnl = run_trader_for_assets(COMMODITIES, "🥇 COMMODITIES", is_crypto=False)

    portfolio = load_portfolio()
    print(f"\n✅ Commodities session done | Total P/L: ${portfolio['total_profit']:.2f}")

    try:
        from telegram_alerts_v2 import alert_daily_summary
        alert_daily_summary(
            balance=portfolio["balance"],
            total_profit=portfolio["total_profit"],
            holdings_count=len(portfolio["holdings"]),
            daily_pnl=pnl or 0,
            market="🥇 Commodities (Gold/Silver/Oil)"
        )
    except:
        pass


if __name__ == "__main__":
    print("Testing Crypto + Commodities Trader...")
    run_crypto_trader()
    run_commodities_trader()