# src/test_download.py

import yfinance as yf

ticker = yf.Ticker("COFORGE.NS")

df = ticker.history(period="10y")

print(df.head())
print(df.tail())