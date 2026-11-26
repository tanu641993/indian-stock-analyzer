# src/data_fetcher.py

import pandas as pd
import numpy as np
import yfinance as yf # Kept for fallback
import bfinance as bf
import dalal
import finstack as fs
import os
import time

class DataFetcher:
    def __init__(self):
        pass

    def fetch_historical_prices(self, symbol, period="5y"):
        """Fetches historical OHLCV data."""
        # 1. Try bfinance (yfinance drop-in)
        try:
            ticker = bf.Ticker(f"{symbol}.NS")
            hist = ticker.history(period=period)
            if not hist.empty: return hist
        except Exception:
            pass

        # 2. Try dalal
        try:
            # dalal needs start/end dates, we approximate
            from datetime import datetime, timedelta
            end = datetime.now()
            start = end - timedelta(days=5*365)
            data = dalal.history(symbol, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
            if data:
                df = pd.DataFrame(data)
                df['Date'] = pd.to_datetime(df['date'])
                df = df.set_index('Date')
                df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
                return df
        except Exception:
            pass

        # 3. Try finstack
        try:
            df = fs.fetch("india_daily_prices", symbol, start="5y", adjust=True)
            if not df.empty:
                # Standardize column names
                df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.set_index('Date')
                return df
        except Exception:
            pass

        # 4. Final fallback to yfinance
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            return ticker.history(period=period)
        except Exception:
            return pd.DataFrame()

    def fetch_fundamentals(self, symbol):
        """Fetches deep financial statements."""
        try:
            # We use bfinance for the primary fetch because it offers 10+ years of data
            # which is critical for your 5-year CAGR calculations.
            ticker = bf.Ticker(f"{symbol}.NS")
            
            financials = ticker.financials
            balance_sheet = ticker.balance_sheet
            cashflow = ticker.cashflow
            
            if financials.empty or balance_sheet.empty:
                raise ValueError("bfinance returned empty data")

            return {
                "financials": financials,
                "balance_sheet": balance_sheet,
                "cashflow": cashflow,
                "info": ticker.info
            }
        except Exception as e:
            print(f"bfinance failed for {symbol}, falling back to dalal/finstack...")
            # Fallback to finstack for financial statements
            try:
                fin_data = fs.fetch("india_company_financials", symbol, statement="annual")
                return {
                    "financials": fin_data,
                    "balance_sheet": None, # finstack might not have all in one call
                    "cashflow": None,
                    "info": {}
                }
            except Exception:
                return None

    def fetch_shareholding(self, symbol):
        """Fetches promoter and institutional holding data."""
        # dalal is excellent for this
        try:
            sh = dalal.shareholding(symbol)
            return sh
        except Exception:
            # Try bfinance
            try:
                ticker = bf.Ticker(f"{symbol}.NS")
                return ticker.shareholding
            except Exception:
                return None