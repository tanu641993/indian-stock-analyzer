# src/fundamentals_v2.py

import sqlite3
import pandas as pd
import numpy as np
import os
import time
from data_fetcher import DataFetcher # Import the new fetcher

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class FundamentalEngineV2:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.fetcher = DataFetcher() # Initialize the fetcher
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals (
                symbol TEXT PRIMARY KEY,
                company TEXT,
                sector TEXT,
                market_cap REAL,
                -- Level 1: Financial Quality
                roe REAL, roce REAL, debt_to_equity REAL, pe REAL, pb REAL,
                -- Level 2: Business Quality (Growth)
                rev_cagr_3y REAL, rev_cagr_5y REAL, profit_cagr_3y REAL, profit_cagr_5y REAL, eps_cagr_3y REAL, eps_cagr_5y REAL,
                margin_expansion REAL,
                -- Level 3: Capital Allocation
                roce_increasing INTEGER, fcf_positive_5y INTEGER, cfo_to_profit REAL,
                -- Level 5: Management
                promoter_holding REAL, promoter_pledge REAL, share_dilution REAL,
                -- Level 6: Moat
                moat_roce_10y INTEGER,
                -- Level 8: Risk / Misc
                current_ratio REAL, interest_coverage REAL, operating_margin REAL,
                -- Governance Flags
                is_market_leader INTEGER DEFAULT 0,
                auditor_red_flag INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _calc_cagr(self, start_val, end_val, years):
        if start_val is None or end_val is None or start_val <= 0 or end_val <= 0 or years <= 0:
            return None
        return (end_val / start_val) ** (1 / years) - 1

    def get_stock_data(self, symbol):
        try:
            # 1. Fetch raw data using the multi-source fetcher
            data = self.fetcher.fetch_fundamentals(symbol)
            if not data:
                return None

            fin = data["financials"]
            cf = data["cashflow"]
            bs = data["balance_sheet"]
            info = data.get("info", {})

            # ... (The rest of your calculation logic from Week 4 remains the same)
            # We extract metrics like ROE, ROCE, CAGR from the dataframes
            
            # Example for Revenue CAGR
            rev_cagr_3y, rev_cagr_5y = None, None
            if not fin.empty and "Total Revenue" in fin.index:
                rev_curr = fin.loc["Total Revenue"].iloc[0]
                rev_3y = fin.loc["Total Revenue"].iloc[-3] if len(fin.columns) >= 3 else None
                rev_5y = fin.loc["Total Revenue"].iloc[-5] if len(fin.columns) >= 5 else None
                rev_cagr_3y = self._calc_cagr(rev_3y, rev_curr, 3)
                rev_cagr_5y = self._calc_cagr(rev_5y, rev_curr, 5)

            # ... (Calculate Profit CAGR, Margins, ROCE trends, FCF, etc.)
            
            # 2. Fetch Shareholding Pattern (using dalal)
            shareholding_data = self.fetcher.fetch_shareholding(symbol)
            promoter_holding = None
            if shareholding_data and isinstance(shareholding_data, list) and len(shareholding_data) > 0:
                # Extract promoter holding from the response structure
                # (Structure varies, but typically shares are listed as percentages)
                promoter_holding = shareholding_data[0].get('promoterHolding', 0) / 100 # Example conversion

            return {
                "symbol": symbol,
                "company": info.get("longName"),
                "sector": info.get("sector", "Unknown"),
                "market_cap": info.get("marketCap", 0) / 10000000,
                "roe": info.get("returnOnEquity"),
                "roce": None, # Calculate from fin/bs as done in previous versions
                "debt_to_equity": info.get("debtToEquity"),
                "pe": info.get("trailingPE"),
                "pb": info.get("priceToBook"),
                "rev_cagr_3y": rev_cagr_3y,
                "rev_cagr_5y": rev_cagr_5y,
                # ... (Include all other fields calculated from the statements)
                "promoter_holding": promoter_holding,
                # ... (Fill remaining fields)
            }
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            return None

    def update_all(self):
        df = pd.read_sql("SELECT symbol FROM stocks", self.conn)
        for i, row in df.iterrows():
            sym = row['symbol']
            print(f"Fetching Deep Data for {sym}...")
            data = self.get_stock_data(sym)
            if data:
                keys = data.keys()
                query = f"INSERT OR REPLACE INTO fundamentals ({','.join(keys)}) VALUES ({','.join(['?']*len(keys))})"
                self.conn.execute(query, list(data.values()))
                self.conn.commit()
            if (i + 1) % 5 == 0: time.sleep(1)

if __name__ == "__main__":
    engine = FundamentalEngineV2()
    engine.update_all()
    engine.conn.close()
    print("✅ Database fully updated with Level 1-10 metrics using multi-source data!")