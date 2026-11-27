# src/download_all_prices.py

import sqlite3
import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")
HISTORY_YEARS = 10


def history_start_date(today=None):
    today = today or datetime.today().date()
    try:
        return today.replace(year=today.year - HISTORY_YEARS)
    except ValueError:
        return today.replace(year=today.year - HISTORY_YEARS, day=28)

class StockData:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)

    def update_all_stocks(self):
        # Get list of stocks
        df = pd.read_sql("SELECT symbol FROM stocks", self.conn)
        symbols = df["symbol"].tolist()
        target_start = history_start_date()

        for symbol in symbols:
            try:
                query = """
                    SELECT MIN(date) AS first_date, MAX(date) AS last_date
                    FROM price_history
                    WHERE symbol = ?
                """
                result = pd.read_sql(query, self.conn, params=(symbol,)).iloc[0]
                first_date_str = result["first_date"]
                last_date_str = result["last_date"]

                ticker = yf.Ticker(f"{symbol}.NS")
                history_frames = []

                if first_date_str:
                    first_date = datetime.strptime(
                        str(first_date_str)[:10], "%Y-%m-%d"
                    ).date()
                    if first_date > target_start:
                        print(
                            f"📥 Backfilling {symbol} from {target_start} "
                            f"to {first_date}..."
                        )
                        df_older = ticker.history(
                            start=target_start.strftime("%Y-%m-%d"),
                            end=first_date.strftime("%Y-%m-%d"),
                            auto_adjust=True,
                        )
                        if not df_older.empty:
                            history_frames.append(df_older)

                    last_date = datetime.strptime(str(last_date_str)[:10], "%Y-%m-%d")
                    start_date = (last_date + timedelta(days=1)).date()
                    if start_date < datetime.today().date():
                        print(f"📥 Fetching new data for {symbol} from {start_date}...")
                        df_new = ticker.history(
                            start=start_date.strftime("%Y-%m-%d"),
                            auto_adjust=True,
                        )
                        if not df_new.empty:
                            history_frames.append(df_new)
                else:
                    print(f"📥 Fetching {HISTORY_YEARS}Y history for {symbol}...")
                    df_new = ticker.history(
                        start=target_start.strftime("%Y-%m-%d"),
                        auto_adjust=True,
                    )
                    if not df_new.empty:
                        history_frames.append(df_new)

                if not history_frames:
                    print(f"⚠️ No new data for {symbol}")
                    continue

                df_new = pd.concat(history_frames)
                df_new = df_new[~df_new.index.duplicated(keep="last")]

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