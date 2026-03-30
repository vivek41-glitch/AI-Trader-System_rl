import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
import time
import json
import os

# ============================================
# MT5 FOREX TRADER — Replaces OANDA
# MetaTrader 5 — Free, No email verify nonsense
# Works on Windows laptop directly!
# ============================================
# SETUP (10 minutes, completely free):
#
# STEP 1: Install MT5 platform
#   → Go to: https://www.metatrader5.com/en/download
#   → Download and install MT5 for Windows
#
# STEP 2: Open a FREE Demo Account inside MT5
#   → Open MT5 app
#   → Click: File → Open Account
#   → Select any broker (recommend: "MetaQuotes-Demo")
#   → Choose "Open a demo account with a broker"
#   → Fill name, email → click Next
#   → You get $10,000 fake money instantly! No email verify!
#   → Save your Login number and Password shown
#
# STEP 3: Install Python library
#   → Open terminal/cmd: pip install MetaTrader5
#
# STEP 4: Paste your Login + Password below
# ============================================

MT5_LOGIN    = 105182881 # Your MT5 demo login number (e.g. 12345678)
MT5_PASSWORD = "-iVtHuD0"          # Your MT5 demo password
MT5_SERVER   = "MetaQuotes-Demo"   # Broker server name (shown during signup)

# Forex pairs to trade
FOREX_PAIRS = {
    "EURUSD": "Euro / US Dollar",
    "GBPUSD": "British Pound / Dollar",
    "USDJPY": "Dollar / Japanese Yen",
    "AUDUSD": "Australian Dollar / Dollar",
    "USDCHF": "Dollar / Swiss Franc",
    "USDCAD": "Dollar / Canadian Dollar",
    "XAUUSD": "Gold / US Dollar",      # Gold! Very popular
}

LOT_SIZE = 0.01   # Minimum lot — safest for demo trading
PORTFOLIO_FILE = "logs/mt5_portfolio.json"


def connect_mt5():
    """Connect to MetaTrader 5."""
    try:
        import MetaTrader5 as mt5

        if not mt5.initialize():
            print("❌ MT5 not installed or not running!")
            print("   → Make sure MT5 app is OPEN on your computer")
            print("   → Download: https://www.metatrader5.com/en/download")
            return None

        # Login to demo account
        if MT5_LOGIN == 0:
            print("⚠️ MT5_LOGIN not set — using currently logged in account")
            account = mt5.account_info()
            if account:
                print(f"✅ Connected: Account #{account.login}, Balance: ${account.balance:,.2f}")
                return mt5
        else:
            authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            if not authorized:
                print(f"❌ Login failed: {mt5.last_error()}")
                print("   Check your Login number, Password, and Server name")
                return None
            account = mt5.account_info()
            print(f"✅ Connected: Account #{account.login}")
            print(f"   Balance:  ${account.balance:,.2f}")
            print(f"   Equity:   ${account.equity:,.2f}")
            print(f"   Server:   {account.server}")

        return mt5

    except ImportError:
        print("❌ MetaTrader5 library not installed!")
        print("   Run this in terminal: pip install MetaTrader5")
        print("   Note: Only works on Windows!")
        return None
    except Exception as e:
        print(f"❌ MT5 connection error: {e}")
        return None


def get_forex_data(mt5, symbol, bars=150):
    """Fetch historical price data from MT5."""
    try:
        import MetaTrader5 as mt5_lib

        # Get daily candles
        rates = mt5_lib.copy_rates_from_pos(symbol, mt5_lib.TIMEFRAME_D1, 0, bars)
        if rates is None or len(rates) < 50:
            print(f"  ⚠️ No data for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df["time"]  = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={
            "open": "Open", "high": "High",
            "low": "Low",   "close": "Close",
            "tick_volume": "Volume"
        })
        df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)

        # Add indicators — same as your existing system
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
        print(f"  ❌ Data error for {symbol}: {e}")
        return None


def get_signal(df):
    """Generate BUY / SELL / HOLD signal."""
    last   = df.iloc[-1]
    second = df.iloc[-2]
    buy_s  = 0
    sell_s = 0

    # RSI
    if last["RSI"] < 35:   buy_s  += 2
    elif last["RSI"] > 65: sell_s += 2

    # MACD crossover
    if last["MACD"] > last["MACD_Signal"] and second["MACD"] <= second["MACD_Signal"]:
        buy_s += 2
    elif last["MACD"] < last["MACD_Signal"] and second["MACD"] >= second["MACD_Signal"]:
        sell_s += 2

    # EMA trend
    if last["Close"] > last["EMA_20"] > last["EMA_50"]:   buy_s  += 1
    elif last["Close"] < last["EMA_20"] < last["EMA_50"]: sell_s += 1

    # Bollinger Band
    if last["Close"] <= last["BB_Lower"]:   buy_s  += 1
    elif last["Close"] >= last["BB_Upper"]: sell_s += 1

    # Skip if too volatile
    if last["ATR"] > df["ATR"].mean() * 2.5:
        return "HOLD", 0

    if buy_s  >= 3: return "BUY",  buy_s
    if sell_s >= 3: return "SELL", sell_s
    return "HOLD", 0


def get_open_positions(mt5):
    """Get all open MT5 positions."""
    try:
        import MetaTrader5 as mt5_lib
        positions = mt5_lib.positions_get()
        if positions is None:
            return {}
        result = {}
        for p in positions:
            result[p.symbol] = {
                "ticket":     p.ticket,
                "type":       p.type,      # 0=BUY, 1=SELL
                "volume":     p.volume,
                "open_price": p.price_open,
                "current":    p.price_current,
                "profit":     p.profit,
                "sl":         p.sl,
            }
        return result
    except:
        return {}


def place_order(mt5, symbol, action, lot=LOT_SIZE):
    """Place a BUY or SELL order on MT5."""
    try:
        import MetaTrader5 as mt5_lib

        symbol_info = mt5_lib.symbol_info(symbol)
        if symbol_info is None:
            print(f"  ❌ Symbol {symbol} not found in MT5")
            return None

        if not symbol_info.visible:
            mt5_lib.symbol_select(symbol, True)

        tick = mt5_lib.symbol_info_tick(symbol)
        if tick is None:
            return None

        if action == "BUY":
            order_type = mt5_lib.ORDER_TYPE_BUY
            price      = tick.ask
        else:
            order_type = mt5_lib.ORDER_TYPE_SELL
            price      = tick.bid

        # Calculate stop loss (50 pips away)
        point = symbol_info.point
        digits = symbol_info.digits
        sl_distance = 50 * point * (10 if digits == 5 or digits == 3 else 1)
        sl = (price - sl_distance) if action == "BUY" else (price + sl_distance)

        request = {
            "action":      mt5_lib.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      lot,
            "type":        order_type,
            "price":       price,
            "sl":          round(sl, digits),
            "deviation":   20,
            "magic":       20240101,
            "comment":     "AI_Trader",
            "type_time":   mt5_lib.ORDER_TIME_GTC,
            "type_filling": mt5_lib.ORDER_FILLING_IOC,
        }

        result = mt5_lib.order_send(request)
        if result.retcode == mt5_lib.TRADE_RETCODE_DONE:
            print(f"  ✅ {action} {lot} lot {symbol} @ {price:.5f}")
            return result
        else:
            print(f"  ❌ Order failed: {result.comment} (code: {result.retcode})")
            return None

    except Exception as e:
        print(f"  ❌ Order error: {e}")
        return None


def close_position(mt5, symbol, position):
    """Close an open MT5 position."""
    try:
        import MetaTrader5 as mt5_lib

        tick = mt5_lib.symbol_info_tick(symbol)
        if tick is None:
            return None

        # Close opposite to open direction
        if position["type"] == 0:   # Was BUY → close with SELL
            order_type = mt5_lib.ORDER_TYPE_SELL
            price      = tick.bid
        else:                        # Was SELL → close with BUY
            order_type = mt5_lib.ORDER_TYPE_BUY
            price      = tick.ask

        request = {
            "action":   mt5_lib.TRADE_ACTION_DEAL,
            "symbol":   symbol,
            "volume":   position["volume"],
            "type":     order_type,
            "position": position["ticket"],
            "price":    price,
            "deviation": 20,
            "magic":    20240101,
            "comment":  "AI_Trader_Close",
            "type_time": mt5_lib.ORDER_TIME_GTC,
            "type_filling": mt5_lib.ORDER_FILLING_IOC,
        }

        result = mt5_lib.order_send(request)
        if result.retcode == mt5_lib.TRADE_RETCODE_DONE:
            print(f"  ✅ Closed {symbol} position | Profit: ${position['profit']:.2f}")
            return result
        else:
            print(f"  ❌ Close failed: {result.comment}")
            return None

    except Exception as e:
        print(f"  ❌ Close error: {e}")
        return None


def run_mt5_forex_trader():
    """Main function — runs all forex pairs."""
    try:
        from telegram_alerts_v2 import alert_buy, alert_sell, alert_daily_summary
    except:
        # Fallback if telegram not set up yet
        def alert_buy(*a, **k): pass
        def alert_sell(*a, **k): pass
        def alert_daily_summary(*a, **k): pass

    print("\n💱 MT5 FOREX TRADER")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    mt5 = connect_mt5()
    if mt5 is None:
        print("❌ Cannot start — MT5 connection failed")
        return

    open_positions = get_open_positions(mt5)
    daily_pnl      = 0
    total_profit   = sum(p["profit"] for p in open_positions.values())

    print(f"📦 Open positions: {len(open_positions)}")
    print(f"📈 Floating P/L:   ${total_profit:.2f}")
    print("=" * 50)

    for symbol, name in FOREX_PAIRS.items():
        print(f"\n📥 {name} ({symbol})...")

        df = get_forex_data(mt5, symbol)
        if df is None:
            continue

        current_price = float(df["Close"].iloc[-1])
        signal, strength = get_signal(df)

        # Stop loss check — close if losing more than 3%
        if symbol in open_positions:
            pos = open_positions[symbol]
            loss_pct = pos["profit"] / (pos["open_price"] * pos["volume"] * 100)
            if loss_pct <= -0.03:
                print(f"  🛑 STOP LOSS: {symbol} loss={loss_pct:.1%}")
                result = close_position(mt5, symbol, pos)
                if result:
                    alert_sell(name, pos["volume"], current_price,
                               pos["profit"], market="FOREX", currency="$")
                    daily_pnl += pos["profit"]
                continue

        print(f"  💲 Price: {current_price:.5f} | Signal: {signal} (strength {strength})")

        if signal == "BUY" and symbol not in open_positions:
            result = place_order(mt5, symbol, "BUY")
            if result:
                alert_buy(name, LOT_SIZE, current_price, market="FOREX", currency="$")

        elif signal == "SELL" and symbol in open_positions:
            pos    = open_positions[symbol]
            result = close_position(mt5, symbol, pos)
            if result:
                alert_sell(name, pos["volume"], current_price,
                           pos["profit"], market="FOREX", currency="$")
                daily_pnl += pos["profit"]

        else:
            print(f"  ⏸️ HOLDING")

        time.sleep(0.3)

    # Final summary
    import MetaTrader5 as mt5_lib
    account = mt5_lib.account_info()
    open_after = get_open_positions(mt5)
    total_after = sum(p["profit"] for p in open_after.values())

    print("\n" + "=" * 50)
    print("📊 MT5 FOREX SESSION DONE")
    print(f"💰 Balance:    ${account.balance:,.2f}")
    print(f"📈 Equity:     ${account.equity:,.2f}")
    print(f"📦 Positions:  {len(open_after)}")
    print(f"💹 Float P/L:  ${total_after:.2f}")
    print("=" * 50)

    alert_daily_summary(
        balance=account.balance,
        total_profit=total_after,
        holdings_count=len(open_after),
        daily_pnl=daily_pnl,
        market="💱 Forex (MT5)"
    )

    mt5_lib.shutdown()


if __name__ == "__main__":
    run_mt5_forex_trader()