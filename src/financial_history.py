# src/financial_history.py

import yfinance as yf

ticker = yf.Ticker("COFORGE.NS")

print(ticker.financials)