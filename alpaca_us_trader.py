import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import time

ALPACA_API_KEY    = "PK72YCIH6UAJXUH2RLYHZHYCYA"
ALPACA_SECRET_KEY = "4mXCdKWwmCN8sHwBGnwrduyi3HW1bvE6ZBGBKhE5w9ve"
ALPACA_BASE_URL   = "https://paper-api.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "Content-Type":        "application/json"
}

US_STOCKS = {
    "AAPL": "Apple",    "MSFT": "Microsoft", "GOOGL": "Google",
    "AMZN": "Amazon",   "NVDA": "Nvidia",    "META":  "Meta",
    "TSLA": "Tesla",    "NFLX": "Netflix",   "AMD":   "AMD",
    "PYPL": "PayPal",   "DIS":  "Disney",    "UBER":  "Uber",
    "SHOP": "Shopify",  "COIN": "Coinbase",  "BABA":  "Alibaba",
}

# Load components safely
try:
    from risk_manager import RiskManager
    risk = RiskManager(initial_balance=100000)
except:
    risk = None

try:
    from position_sizer import PositionSizer
    sizer = PositionSizer(base_pct=0.08, max_pct=0.18, min_pct=0.03)
except:
    sizer = None

try:
    from market_regime_detector import MarketRegimeDetector
    regime_detector = MarketRegimeDetector()
except:
    regime_detector = None

_ensemble = None
def get_ensemble():
    global _ensemble
    if _ensemble is None:
        try:
            from ensemble_trader import EnsembleTrader
            _ensemble = EnsembleTrader()
        except Exception as e:
            print(f"⚠️ Ensemble not loaded: {e}")
    return _ensemble


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
            print(f"  ❌ Order failed: {r.text[:80]}")
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


def get_simple_signal(df):
    """Fallback signal when ensemble not available."""
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

    if buy_s  >= 3: return "BUY",  0.6
    if sell_s >= 3: return "SELL", 0.6
    return "HOLD", 0.0


def run_us_trader():
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary, send_alert
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass
        def send_alert(*a, **k): pass

    print("\n🇺🇸 US TRADER v3")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    account = get_account()
    if not account:
        print("❌ Cannot connect to Alpaca")
        return

    print(f"💰 Balance:   ${account['balance']:,.2f}")
    print(f"📦 Portfolio: ${account['portfolio']:,.2f}")
    print(f"⚡ Buying Power: ${account['buying_power']:,.2f}")

    # Risk check
    if risk:
        risk.update_peak(account["portfolio"])
        can_trade, reason = risk.can_trade(account["portfolio"])
        if not can_trade:
            print(f"\n{reason}")
            send_alert(reason, "error")
            return

    # Market regime (informational only — does NOT block trades)
    market_regime  = "UNKNOWN"
    trade_mult     = 1.0
    if regime_detector:
        spy_df = get_price_data("SPY")
        if spy_df is not None:
            market_regime, m_conf, m_desc = regime_detector.detect(spy_df)
            emoji = regime_detector.get_emoji(market_regime)
            print(f"\n📊 Market: {emoji} {market_regime} — {m_desc}")
            # Reduce size in bear but NEVER block completely
            trade_mult = max(0.5, regime_detector.get_trade_multiplier(market_regime))

    print("=" * 60)

    ensemble  = get_ensemble()
    positions = get_positions()
    daily_pnl = 0
    invest_base = account["buying_power"] * 0.08  # 8% per trade base

    for symbol, name in US_STOCKS.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_price_data(symbol)
        if df is None:
            continue

        price = float(df["Close"].iloc[-1])

        # Stop Loss check
        if symbol in positions:
            pos = positions[symbol]
            loss_pct = pos["profit_pct"]

            if risk and risk.should_stop_loss(pos["buy_price"], price):
                print(f"  🛑 STOP LOSS! Loss: {loss_pct:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    if risk: risk.record_trade()
                    if sizer: sizer.record_trade(loss_pct / 100)
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

            # Take Profit check
            if risk and risk.should_take_profit(pos["buy_price"], price):
                print(f"  💰 TAKE PROFIT! Gain: {loss_pct:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    if risk: risk.record_trade()
                    if sizer: sizer.record_trade(loss_pct / 100)
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

        # Get signal — ensemble first, fallback to simple
        if ensemble:
            signal, conf, breakdown = ensemble.vote(df, account["balance"], symbol)
            ensemble.print_breakdown(symbol, price, breakdown)
        else:
            signal, conf = get_simple_signal(df)
            print(f"  📊 Signal: {signal} ({conf:.0%})")

        # Calculate invest amount
        invest_amt = invest_base * trade_mult
        if sizer:
            atr_pct = float(df["ATR"].iloc[-1]) / price if price > 0 else 0.02
            invest_amt, invest_pct, reason = sizer.calculate(
                balance=account["buying_power"],
                confidence=conf,
                volatility_pct=atr_pct,
                signal_strength=2
            )
            invest_amt *= trade_mult

        # Execute — NO regime blocking!
        if signal == "BUY" and symbol not in positions:
            shares = int(invest_amt // price)
            if shares > 0:
                print(f"  💰 Investing ${invest_amt:,.0f}")
                order = place_order(symbol, shares, "buy")
                if order:
                    if risk: risk.record_trade()
                    alert_buy(name, shares, price, "US")

        elif signal == "SELL" and symbol in positions:
            pos   = positions[symbol]
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                if risk: risk.record_trade()
                if sizer: sizer.record_trade(pos["profit_pct"] / 100)
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                daily_pnl += pos["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.3)

    # Summary
    account_after   = get_account()
    positions_after = get_positions()
    open_pnl        = sum(p["profit"] for p in positions_after.values())

    print("\n" + "=" * 60)
    print("📊 SESSION DONE")
    print(f"💰 Balance:      ${account_after['balance']:,.2f}")
    print(f"📈 Open P/L:     ${open_pnl:,.2f}")
    print(f"📅 Today Trades: ${daily_pnl:,.2f}")
    print(f"🌍 Market:       {market_regime}")
    print(f"📦 Positions:    {len(positions_after)}")
    print("=" * 60)

    alert_daily_summary(
        balance=account_after["balance"],
        total_profit=open_pnl,
        holdings_count=len(positions_after),
        daily_pnl=daily_pnl,
        market=f"🇺🇸 US ({market_regime})"
    )


if __name__ == "__main__":
    run_us_trader()