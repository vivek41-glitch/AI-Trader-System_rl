import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from trading_env import TradingEnvironment
import matplotlib.pyplot as plt
import os

print("📊 MULTI-STOCK BACKTEST")
print("=" * 50)

STOCKS = {
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'AMZN': 'Amazon',
    'TCS_NS': 'TCS',
    'RELIANCE_NS': 'Reliance',
    'INFY_NS': 'Infosys',
    'HDFCBANK_NS': 'HDFC Bank',
    'WIPRO_NS': 'Wipro',
}

model = PPO.load("models/ai_trader_multi_v1")

results = []

for ticker, name in STOCKS.items():
    filepath = f'data/{ticker}_multi.csv'
    if not os.path.exists(filepath):
        print(f"⚠️ Skipping {name} - data not found")
        continue

    df = pd.read_csv(filepath, index_col=0)
    df = df.dropna()

    split = int(len(df) * 0.8)
    df_test = df.iloc[split:].reset_index(drop=True)

    if len(df_test) < 50:
        continue

    env = TradingEnvironment(df_test, initial_balance=10000)
    obs, _ = env.reset()
    portfolio_values = [10000]
    actions = []
    done = False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, _, info = env.step(action)
        portfolio_values.append(info['portfolio_value'])
        actions.append(int(action))

    final = portfolio_values[-1]
    profit = final - 10000
    ret = (profit / 10000) * 100
    buys = actions.count(1)
    sells = actions.count(2)

    results.append({
        'Stock': name,
        'Final Value': final,
        'Profit': profit,
        'Return %': ret,
        'Buys': buys,
        'Sells': sells
    })

    emoji = "✅" if profit > 0 else "❌"
    print(f"{emoji} {name:12} | Final: ${final:>10,.2f} | Return: {ret:>7.2f}% | B:{buys} S:{sells}")

print("=" * 50)

# Summary
profits = [r['Profit'] for r in results]
returns = [r['Return %'] for r in results]
winners = [r for r in results if r['Profit'] > 0]

print(f"\n🏆 OVERALL RESULTS:")
print(f"✅ Winning Stocks : {len(winners)}/{len(results)}")
print(f"💰 Total Profit   : ${sum(profits):,.2f}")
print(f"📈 Avg Return     : {np.mean(returns):.2f}%")
print(f"🏆 Best Stock     : {max(results, key=lambda x: x['Return %'])['Stock']} ({max(returns):.2f}%)")
print(f"📉 Worst Stock    : {min(results, key=lambda x: x['Return %'])['Stock']} ({min(returns):.2f}%)")

# Chart
fig, axes = plt.subplots(2, 5, figsize=(20, 8))
axes = axes.flatten()

for i, (ticker, name) in enumerate(STOCKS.items()):
    filepath = f'data/{ticker}_multi.csv'
    if not os.path.exists(filepath) or i >= len(axes):
        continue

    df = pd.read_csv(filepath, index_col=0).dropna()
    split = int(len(df) * 0.8)
    df_test = df.iloc[split:].reset_index(drop=True)

    if len(df_test) < 50:
        continue

    env = TradingEnvironment(df_test, initial_balance=10000)
    obs, _ = env.reset()
    pvals = [10000]
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, _, done, _, info = env.step(action)
        pvals.append(info['portfolio_value'])

    color = 'green' if pvals[-1] > 10000 else 'red'
    axes[i].plot(pvals, color=color, linewidth=2)
    axes[i].axhline(y=10000, color='gray', linestyle='--', alpha=0.5)
    axes[i].set_title(f'{name}\n${pvals[-1]:,.0f}', fontsize=10)
    axes[i].set_xlabel('Days')
    axes[i].set_ylabel('Value ($)')
    axes[i].grid(True, alpha=0.3)

plt.suptitle('AI Trader — All Stocks Performance', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('backtest/multi_stock_performance.png', dpi=150)
plt.show()
print("\n✅ Chart saved to backtest/multi_stock_performance.png")
