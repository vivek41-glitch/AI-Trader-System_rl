import yfinance as yf
import pandas as pd
import os

# Stocks we want to trade
STOCKS = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN']

# Download 10 years of data
START_DATE = '2015-01-01'
END_DATE = '2025-01-01'

print("🚀 Starting data collection...")
print("=" * 50)

for stock in STOCKS:
    print(f"📥 Downloading {stock}...")
    df = yf.download(stock, start=START_DATE, end=END_DATE)
    filepath = f'data/{stock}_10years.csv'
    df.to_csv(filepath)
    print(f"✅ {stock} saved! {len(df)} days of data")

print("=" * 50)
print("🎉 All data collected successfully!")
print("📁 Check your data/ folder")
