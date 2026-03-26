import pandas as pd
import pandas_ta as ta
import os

STOCKS = ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'AMZN']

print("🧠 Adding technical indicators...")
print("=" * 50)

for stock in STOCKS:
    print(f"📊 Processing {stock}...")
    
    # Load data
    df = pd.read_csv(f'data/{stock}_10years.csv', header=[0,1], index_col=0)
    df.columns = ['Close', 'High', 'Low', 'Open', 'Volume']
    df.index = pd.to_datetime(df.index)
    df = df.astype(float)
    
    # Add indicators
    df['RSI'] = ta.rsi(df['Close'], length=14)
    macd = ta.macd(df['Close'])
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_Signal'] = macd['MACDs_12_26_9']
    df['EMA_20'] = ta.ema(df['Close'], length=20)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    
    # Fix Bollinger Bands - detect column names automatically
    bb = ta.bbands(df['Close'], length=20)
    bb_cols = bb.columns.tolist()
    df['BB_Upper'] = bb[bb_cols[0]]
    df['BB_Mid'] = bb[bb_cols[1]]
    df['BB_Lower'] = bb[bb_cols[2]]
    
    # Remove empty rows
    df.dropna(inplace=True)
    
    # Save
    df.to_csv(f'data/{stock}_indicators.csv')
    print(f"✅ {stock} done! {len(df)} rows with indicators")

print("=" * 50)
print("🎉 All indicators added successfully!")
