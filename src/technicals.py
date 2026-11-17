# src/technicals.py

import sqlite3
import pandas as pd
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class TechnicalEngine:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)

    def calculate_rsi(self, series, period=14):
        """Calculate Relative Strength Index (RSI)"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def get_technical_analysis(self, symbol):
        """Calculate all technical indicators for a specific stock"""
        
        # 1. Fetch data from SQLite
        query = "SELECT date, close, volume FROM price_history WHERE symbol = ? ORDER BY date ASC"
        df = pd.read_sql(query, self.conn, params=(symbol,))
        
        if df.empty or len(df) < 200:
            return {"error": f"Not enough data for {symbol}"}

        # 2. Calculate Moving Averages
        df['dma50'] = df['close'].rolling(window=50).mean()
        df['dma200'] = df['close'].rolling(window=200).mean()
        
        # 3. Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'], period=14)
        
        # 4. Calculate 52-Week High / Low (approx 252 trading days)
        # We use the last 252 rows to get the rolling 52-week metrics
        last_252_days = df.tail(252)
        high_52w = last_252_days['close'].max()
        low_52w = last_252_days['close'].min()
        
        # 5. Calculate Returns (approx 126 days = 6M, 252 days = 12M)
        current_price = df['close'].iloc[-1]
        
        # 6 month return
        price_6m_ago = df['close'].iloc[-126] if len(df) >= 126 else df['close'].iloc[0]
        return_6m = ((current_price / price_6m_ago) - 1) * 100
        
        # 12 month return
        price_12m_ago = df['close'].iloc[-252] if len(df) >= 252 else df['close'].iloc[0]
        return_12m = ((current_price / price_12m_ago) - 1) * 100

        # 6. Volume
        current_volume = int(df['volume'].iloc[-1])
        avg_volume_20d = int(df['volume'].tail(20).mean())

        # 7. Compile Results
        result = {
            "stock": symbol,
            "current_price": round(current_price, 2),
            "rsi": round(df['rsi'].iloc[-1], 2) if not pd.isna(df['rsi'].iloc[-1]) else None,
            "dma50": round(df['dma50'].iloc[-1], 2) if not pd.isna(df['dma50'].iloc[-1]) else None,
            "dma200": round(df['dma200'].iloc[-1], 2) if not pd.isna(df['dma200'].iloc[-1]) else None,
            "52w_high": round(high_52w, 2),
            "52w_low": round(low_52w, 2),
            "return_6m_pct": round(return_6m, 2),
            "return_12m_pct": round(return_12m, 2),
            "volume": current_volume,
            "avg_volume_20d": avg_volume_20d
        }
        
        return result

    def close(self):
        self.conn.close()

# --- Test Block ---
if __name__ == "__main__":
    engine = TechnicalEngine()
    
    # Test with a stock you know is in your database
    test_symbol = "POLYCAB"
    print(f"Calculating Technicals for {test_symbol}...\n")
    
    result = engine.get_technical_analysis(test_symbol)
    
    # Print as formatted JSON
    print(json.dumps(result, indent=4))
    
    engine.close()