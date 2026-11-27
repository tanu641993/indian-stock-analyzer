# src/stock_data.py

import sqlite3
import pandas as pd
import yfinance as yf

DB_PATH = "database/stocks.db"


class StockData:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)

    def get_stock_list(self):
        """
        Read stocks from stocks table
        """

        query = """
        SELECT symbol
        FROM stocks
        """

        df = pd.read_sql(query, self.conn)

        return df["symbol"].tolist()

    def download_history(self,
                         symbol,
                         period="10y"):
        """
        Download stock history from Yahoo Finance
        """

        try:

            ticker = yf.Ticker(f"{symbol}.NS")

            df = ticker.history(
                period=period,
                auto_adjust=True
            )

            if df.empty:

                print(f"No data found: {symbol}")
                return None

            df.reset_index(inplace=True)

            df["symbol"] = symbol

            return df

        except Exception as e:

            print(f"Error downloading {symbol}: {e}")
            return None

    def save_history(self,
                     df):
        """
        Save stock history into SQLite
        """

        if df is None:
            return

        columns = [
            "symbol",
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        temp = df[columns].copy()

        temp.columns = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        temp.to_sql(
            "price_history",
            self.conn,
            if_exists="append",
            index=False
        )

    def clear_existing_history(self,
                               symbol):
        """
        Prevent duplicate records
        """

        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM price_history
            WHERE symbol = ?
            """,
            (symbol,)
        )

        self.conn.commit()

    def update_stock(self,
                     symbol):
        """
        Full update for a single stock
        """

        print(f"Downloading {symbol}")

        df = self.download_history(symbol)

        if df is None:
            return

        self.clear_existing_history(symbol)

        self.save_history(df)

        print(f"Saved {symbol}")

    def update_all_stocks(self):
        """
        Download all stocks
        """

        stocks = self.get_stock_list()

        for symbol in stocks:

            try:

                self.update_stock(symbol)

            except Exception as e:

                print(symbol, e)

    def get_price_history(
            self,
            symbol):

        query = """
        SELECT *
        FROM price_history
        WHERE symbol = ?
        ORDER BY date
        """

        return pd.read_sql(
            query,
            self.conn,
            params=(symbol,)
        )

    def close(self):
        self.conn.close()