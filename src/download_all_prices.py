# src/download_all_prices.py

import sqlite3
import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class StockData:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)

    def update_all_stocks(self):
        # Get list of stocks
        df = pd.read_sql("SELECT symbol FROM stocks", self.conn)
        symbols = df["symbol"].tolist()

        for symbol in symbols:
            try:
                # 1. Find the last date we have data for this stock
                query = "SELECT MAX(date) as last_date FROM price_history WHERE symbol = ?"
                result = pd.read_sql(query, self.conn, params=(symbol,))
                last_date_str = result.iloc[0]['last_date']

                ticker = yf.Ticker(f"{symbol}.NS")

                if last_date_str:
                    # We have data. Only download from the day after the last date.
                    last_date = datetime.strptime(str(last_date_str)[:10], "%Y-%m-%d")
                    start_date = last_date + timedelta(days=1)
                    
                    # If the last date is today or yesterday, we are up to date
                    if start_date.date() >= datetime.today().date():
                        print(f"⏭️ {symbol} is already up to date.")
                        continue
                    
                    print(f"📥 Fetching new data for {symbol} from {start_date.date()}...")
                    df_new = ticker.history(start=start_date.strftime("%Y-%m-%d"), auto_adjust=True)
                else:
                    # No data exists, download 5 years
                    print(f"📥 Fetching 5Y history for {symbol}...")
                    df_new = ticker.history(period="5y", auto_adjust=True)

                if df_new.empty:
                    print(f"⚠️ No new data for {symbol}")
                    continue

                # 2. Format and save
                df_new.reset_index(inplace=True)
                df_new["symbol"] = symbol
                
                # Standardize column names
                df_new.rename(columns={
                    "Date": "date", "Open": "open", "High": "high", 
                    "Low": "low", "Close": "close", "Volume": "volume"
                }, inplace=True)
                
                # Format date to string to match SQLite
                df_new['date'] = df_new['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Append only the new rows
                df_new[["symbol", "date", "open", "high", "low", "close", "volume"]].to_sql(
                    "price_history", self.conn, if_exists="append", index=False
                )
                print(f"✅ Saved {len(df_new)} new rows for {symbol}")
                
            except Exception as e:
                print(f"❌ Error updating {symbol}: {e}")

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    sd = StockData()
    sd.update_all_stocks()
    sd.close()