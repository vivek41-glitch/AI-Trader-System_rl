import json
import os
import yfinance as yf
from datetime import datetime

PORTFOLIO_FILE = 'logs/paper_portfolio.json'
PERFORMANCE_FILE = 'logs/performance_history.json'

STOCK_SYMBOLS = {
    'Apple': 'AAPL',
    'Tesla': 'TSLA',
    'Microsoft': 'MSFT',
    'Google': 'GOOGL',
    'Amazon': 'AMZN',
    'Nvidia': 'NVDA',
    'Meta': 'META',
    'Netflix': 'NFLX',
    'Reliance': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'Infosys': 'INFY.NS',
    'HDFC Bank': 'HDFCBANK.NS',
    'Wipro': 'WIPRO.NS'
}

def get_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if len(hist) > 0:
            return float(hist['Close'].iloc[-1])
    except:
        pass
    return None

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def load_trades():
    try:
        with open('logs/paper_trades.json', 'r') as f:
            return json.load(f)
    except:
        return []

def load_performance():
    try:
        with open(PERFORMANCE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def print_report():
    print("\n" + "=" * 55)
    print("📊 AI TRADER — LIVE PERFORMANCE REPORT")
    print("=" * 55)

    portfolio = load_portfolio()
    if not portfolio:
        print("⚠️ No portfolio data found!")
        return

    trades = load_trades()
    sell_trades = [t for t in trades if t['action'] == 'SELL']
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    profitable_sells = [t for t in sell_trades if t.get('profit') and t['profit'] > 0]
    win_rate = (len(profitable_sells) / len(sell_trades) * 100) if sell_trades else 0
    realized_profit = sum(t['profit'] for t in sell_trades if t.get('profit'))

    print("📡 Fetching live prices...")

    holdings_value = 0
    holdings_detail = []
    total_unrealized = 0

    for ticker, holding in portfolio['holdings'].items():
        name = holding.get('name', ticker)
        shares = holding['shares']
        buy_price = holding['buy_price']

        # Get symbol
        symbol = STOCK_SYMBOLS.get(name, ticker)
        current_price = get_current_price(symbol)

        if current_price:
            value = shares * current_price
            unrealized = (current_price - buy_price) * shares
            holdings_value += value
            total_unrealized += unrealized
            holdings_detail.append({
                'stock': name,
                'shares': shares,
                'buy_price': round(buy_price, 2),
                'current_price': round(current_price, 2),
                'value': round(value, 2),
                'unrealized_profit': round(unrealized, 2)
            })
        else:
            # Use cost if price fetch fails
            holdings_value += holding['cost']

    cash = portfolio['balance']
    total_portfolio = cash + holdings_value
    total_return = ((total_portfolio - 10000) / 10000) * 100

    print(f"📅 Date:                {datetime.now().strftime('%Y-%m-%d')}")
    print(f"💰 Cash Balance:        ${cash:,.2f}")
    print(f"📦 Holdings Value:      ${holdings_value:,.2f}")
    print(f"🏦 Total Portfolio:     ${total_portfolio:,.2f}")
    print(f"📈 Total Return:        {total_return:+.2f}%")
    print(f"✅ Realized Profit:     ${realized_profit:,.2f}")
    print(f"⏳ Unrealized P/L:      ${total_unrealized:+,.2f}")
    print(f"🎯 Win Rate:            {win_rate:.1f}%")
    print(f"🛒 Buy Trades:          {len(buy_trades)}")
    print(f"💸 Sell Trades:         {len(sell_trades)}")

    print("\n📦 CURRENT HOLDINGS:")
    print("-" * 55)
    for h in holdings_detail:
        arrow = "📈" if h['unrealized_profit'] >= 0 else "📉"
        print(f"{arrow} {h['stock']}: {h['shares']} shares | "
              f"Buy: ${h['buy_price']} | Now: ${h['current_price']} | "
              f"P/L: ${h['unrealized_profit']:+.2f}")

    # Save snapshot
    performance = load_performance()
    today = datetime.now().strftime('%Y-%m-%d')
    performance = [p for p in performance if p['date'] != today]
    performance.append({
        'date': today,
        'cash': round(cash, 2),
        'holdings_value': round(holdings_value, 2),
        'total_portfolio': round(total_portfolio, 2),
        'total_return': round(total_return, 2),
        'realized_profit': round(realized_profit, 2),
        'unrealized_profit': round(total_unrealized, 2),
        'win_rate': round(win_rate, 2),
        'total_trades': len(trades)
    })
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(performance, f, indent=2)

    print("\n🎯 READINESS CHECK:")
    print("-" * 40)
    days = len(performance)
    print(f"Days tracked: {days}/30")
    if days < 30:
        print(f"⏳ Need {30 - days} more days of paper trading")
    elif win_rate >= 55 and total_return > 5:
        print("✅ READY FOR REAL MONEY!")
    else:
        print("⚠️ Keep paper trading — need more data")
    print("=" * 55)

if __name__ == "__main__":
    print_report()
