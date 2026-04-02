import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
import time

# ============================================
# ALPACA US TRADER v3 — PHASE 3 FULL UPGRADE
# Now uses:
# ✅ Ensemble (3 models vote)
# ✅ Position Sizer (smart sizing)
# ✅ Market Regime Detection
# ✅ Risk Manager
# ✅ 15 stocks
# ✅ Stop Loss + Take Profit
# ============================================

ALPACA_API_KEY    = "YOUR_ALPACA_API_KEY"
ALPACA_SECRET_KEY = "YOUR_ALPACA_SECRET_KEY"
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

# Load Phase 3 components
from risk_manager        import RiskManager
from position_sizer      import PositionSizer
from market_regime_detector import MarketRegimeDetector

risk    = RiskManager(initial_balance=100000)
sizer   = PositionSizer(base_pct=0.08, max_pct=0.18, min_pct=0.03)
regime_detector = MarketRegimeDetector()

# Load ensemble (lazy — loads on first use)
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


def run_us_trader():
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary, send_alert
    except:
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass
        def send_alert(*a, **k): pass

    print("\n🇺🇸 US TRADER v3 — ENSEMBLE + REGIME + SMART SIZING")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    account = get_account()
    if not account:
        print("❌ Cannot connect to Alpaca")
        return

    print(f"💰 Balance:   ${account['balance']:,.2f}")
    print(f"📦 Portfolio: ${account['portfolio']:,.2f}")

    # Risk check
    risk.update_peak(account["portfolio"])
    can_trade, reason = risk.can_trade(account["portfolio"])
    if not can_trade:
        print(f"\n{reason}")
        send_alert(reason, "error")
        return

    # Get overall market regime from SPY
    print("\n📊 Detecting market regime...")
    spy_df = get_price_data("SPY")
    market_regime = "SIDEWAYS"
    if spy_df is not None:
        market_regime, m_conf, m_desc = regime_detector.detect(spy_df)
        emoji = regime_detector.get_emoji(market_regime)
        print(f"  {emoji} Market: {market_regime} ({m_conf:.0%}) — {m_desc}")

        if market_regime == "STRONG_BEAR":
            msg = f"🛑 STRONG BEAR market detected!\nReducing all positions."
            print(f"\n{msg}")
            send_alert(msg, "error")

    trade_mult = regime_detector.get_trade_multiplier(market_regime)
    print(f"  💰 Trade size multiplier: {trade_mult:.1f}x")
    print("=" * 60)

    ensemble  = get_ensemble()
    positions = get_positions()
    daily_pnl = 0

    for symbol, name in US_STOCKS.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_price_data(symbol)
        if df is None:
            continue

        price = float(df["Close"].iloc[-1])

        # Detect individual stock regime
        stock_regime, s_conf, s_desc = regime_detector.detect(df)
        s_emoji = regime_detector.get_emoji(stock_regime)

        # Stop Loss & Take Profit
        if symbol in positions:
            pos = positions[symbol]
            if risk.should_stop_loss(pos["buy_price"], price):
                print(f"  🛑 STOP LOSS! Loss: {pos['profit_pct']:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    risk.record_trade()
                    sizer.record_trade(pos["profit_pct"] / 100)
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

            if risk.should_take_profit(pos["buy_price"], price):
                print(f"  💰 TAKE PROFIT! Gain: {pos['profit_pct']:.1f}%")
                order = place_order(symbol, int(pos["shares"]), "sell")
                if order:
                    risk.record_trade()
                    sizer.record_trade(pos["profit_pct"] / 100)
                    alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                    daily_pnl += pos["profit"]
                continue

            # Bear regime → sell holdings
            if regime_detector.should_sell_holdings(market_regime) and not regime_detector.should_buy(stock_regime):
                print(f"  📉 Selling due to bear regime")
                order = place_order(symbol, int(positions[symbol]["shares"]), "sell")
                if order:
                    risk.record_trade()
                    alert_sell(name, int(positions[symbol]["shares"]), price,
                               positions[symbol]["profit"], "US")
                    daily_pnl += positions[symbol]["profit"]
                continue

        # Get ensemble vote
        if ensemble:
            signal, conf, breakdown = ensemble.vote(df, account["balance"], symbol)
            ensemble.print_breakdown(symbol, price, breakdown)
            signal_strength = breakdown["buy_votes"] if signal == "BUY" else breakdown["sell_votes"]
        else:
            # Fallback signal
            last = df.iloc[-1]
            if last["RSI"] < 35 and last["MACD"] > last["MACD_Signal"]:
                signal, conf, signal_strength = "BUY", 0.6, 2
            elif last["RSI"] > 65 and last["MACD"] < last["MACD_Signal"]:
                signal, conf, signal_strength = "SELL", 0.6, 2
            else:
                signal, conf, signal_strength = "HOLD", 0.0, 0

        print(f"  {s_emoji} Stock regime: {stock_regime} | Signal: {signal} ({conf:.0%})")

        # Skip buying in bad regimes
        if signal == "BUY" and not regime_detector.should_buy(stock_regime):
            print(f"  ⏭️ Skipping BUY — bad regime ({stock_regime})")
            continue

        # Calculate position size
        atr_pct = float(df["ATR"].iloc[-1]) / price if price > 0 else 0.02
        invest_amt, invest_pct, size_reason = sizer.calculate(
            balance=account["buying_power"],
            confidence=conf,
            volatility_pct=atr_pct,
            signal_strength=signal_strength
        )
        # Apply regime multiplier
        invest_amt *= trade_mult

        if signal == "BUY" and symbol not in positions:
            shares = int(invest_amt // price)
            if shares > 0:
                print(f"  💰 Size: ${invest_amt:,.0f} ({invest_pct}%) — {size_reason}")
                order = place_order(symbol, shares, "buy")
                if order:
                    risk.record_trade()
                    alert_buy(name, shares, price, "US")

        elif signal == "SELL" and symbol in positions:
            pos   = positions[symbol]
            order = place_order(symbol, int(pos["shares"]), "sell")
            if order:
                risk.record_trade()
                sizer.record_trade(pos["profit_pct"] / 100)
                alert_sell(name, int(pos["shares"]), price, pos["profit"], "US")
                daily_pnl += pos["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.3)

    # Summary
    account_after   = get_account()
    positions_after = get_positions()
    open_pnl        = sum(p["profit"] for p in positions_after.values())
    risk_stats      = risk.get_stats(account_after["portfolio"])
    sizer_stats     = sizer.get_stats()

    print("\n" + "=" * 60)
    print("📊 SESSION DONE")
    print(f"💰 Balance:       ${account_after['balance']:,.2f}")
    print(f"📈 Open P/L:      ${open_pnl:,.2f}")
    print(f"📅 Today Trades:  ${daily_pnl:,.2f}")
    print(f"🌍 Market regime: {regime_detector.get_emoji(market_regime)} {market_regime}")
    print(f"📉 Drawdown:      {risk_stats['drawdown']:.1f}%")
    if sizer_stats:
        print(f"🎯 Win rate:      {sizer_stats.get('win_rate', 0):.1f}%")
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