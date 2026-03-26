import json
import os
import yfinance as yf
from datetime import datetime

PORTFOLIO_FILE = 'logs/paper_trades.json'
PERFORMANCE_FILE = 'logs/performance_history.json'

STOCK_SYMBOLS = {
    'Apple': 'AAPL',
    'Tesla': 'TSLA',
    'Microsoft': 'MSFT',
    'Google': 'GOOGL',
    'Amazon': 'AMZN',
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

def load_trades():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def load_performance():
    try:
        with open(PERFORMANCE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def calculate_portfolio():
    trades = load_trades()
    if not trades:
        return None

    # Calculate holdings
    holdings = {}
    buy_prices = {}
    cash = 10000

    for trade in trades:
        stock = trade['stock']
        if trade['action'] == 'BUY':
            holdings[stock] = holdings.get(stock, 0) + trade['shares']
            buy_prices[stock] = trade['price']
            cash -= trade['cost']
        elif trade['action'] == 'SELL':
            holdings[stock] = holdings.get(stock, 0) - trade['shares']
            cash += trade.get('revenue', 0)

    # Get current prices and calculate portfolio value
    print("📡 Fetching live prices...")
    holdings_value = 0
    holdings_detail = []
    total_profit_unrealized = 0

    for stock, shares in holdings.items():
        if shares > 0:
            symbol = STOCK_SYMBOLS.get(stock)
            if symbol:
                current_price = get_current_price(symbol)
                if current_price:
                    value = shares * current_price
                    buy_price = buy_prices.get(stock, current_price)
                    unrealized_profit = (current_price - buy_price) * shares
                    holdings_value += value
                    total_profit_unrealized += unrealized_profit
                    holdings_detail.append({
                        'stock': stock,
                        'shares': shares,
                        'buy_price': round(buy_price, 2),
                        'current_price': round(current_price, 2),
                        'value': round(value, 2),
                        'unrealized_profit': round(unrealized_profit, 2)
                    })

    total_portfolio = cash + holdings_value
    total_return = ((total_portfolio - 10000) / 10000) * 100

    sell_trades = [t for t in trades if t['action'] == 'SELL']
    profitable_sells = [t for t in sell_trades if t.get('profit') and t['profit'] > 0]
    win_rate = (len(profitable_sells) / len(sell_trades) * 100) if sell_trades else 0
    realized_profit = sum(t['profit'] for t in sell_trades if t.get('profit'))

    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'cash': round(cash, 2),
        'holdings_value': round(holdings_value, 2),
        'total_portfolio': round(total_portfolio, 2),
        'total_return': round(total_return, 2),
        'realized_profit': round(realized_profit, 2),
        'unrealized_profit': round(total_profit_unrealized, 2),
        'total_trades': len(trades),
        'sell_trades': len(sell_trades),
        'win_rate': round(win_rate, 2),
        'holdings': holdings_detail
    }

def print_report():
    print("\n" + "=" * 55)
    print("📊 AI TRADER — LIVE PERFORMANCE REPORT")
    print("=" * 55)

    data = calculate_portfolio()
    if not data:
        print("⚠️ No data found!")
        return

    print(f"📅 Date:                {data['date']}")
    print(f"💰 Cash Balance:        ${data['cash']:,.2f}")
    print(f"📦 Holdings Value:      ${data['holdings_value']:,.2f}")
    print(f"🏦 Total Portfolio:     ${data['total_portfolio']:,.2f}")
    print(f"📈 Total Return:        {data['total_return']:+.2f}%")
    print(f"✅ Realized Profit:     ${data['realized_profit']:,.2f}")
    print(f"⏳ Unrealized Profit:   ${data['unrealized_profit']:,.2f}")
    print(f"🎯 Win Rate:            {data['win_rate']:.1f}%")
    print(f"🛒 Total Trades:        {data['total_trades']}")

    print("\n📦 CURRENT HOLDINGS:")
    print("-" * 55)
    for h in data['holdings']:
        arrow = "📈" if h['unrealized_profit'] >= 0 else "📉"
        print(f"{arrow} {h['stock']}: {h['shares']} shares | Buy: ${h['buy_price']} | Now: ${h['current_price']} | P/L: ${h['unrealized_profit']:+.2f}")

    # Save snapshot
    performance = load_performance()
    today = datetime.now().strftime('%Y-%m-%d')
    performance = [p for p in performance if p['date'] != today]
    performance.append(data)
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(performance, f, indent=2)

    print("\n🎯 READINESS CHECK:")
    print("-" * 40)
    days = len(performance)
    print(f"Days tracked: {days}/30")
    if days < 30:
        print(f"⏳ Need {30 - days} more days of paper trading")
    elif data['win_rate'] >= 55 and data['total_return'] > 5:
        print("✅ READY FOR REAL MONEY!")
    else:
        print("⚠️ Keep paper trading — need more data")
    print("=" * 55)

if __name__ == "__main__":
    print_report()