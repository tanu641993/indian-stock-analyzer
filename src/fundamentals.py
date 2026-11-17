# src/fundamentals.py

import sqlite3
import pandas as pd
import yfinance as yf
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class FundamentalEngine:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        # ADDED: roa, gnpa, nnpa, casa, nim, car (Banking), rd_expense (Pharma)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals (
                symbol TEXT PRIMARY KEY,
                company TEXT,
                sector TEXT,
                roe REAL,
                roce REAL,
                roa REAL,
                operating_margin REAL,
                debt_to_equity REAL,
                current_ratio REAL,
                interest_coverage REAL,
                pe REAL,
                pb REAL,
                peg REAL,
                ev_ebitda REAL,
                eps_growth REAL,
                revenue_growth REAL,
                profit_growth REAL,
                free_cash_flow REAL,
                promoter_holding REAL,
                promoter_pledge REAL,
                share_dilution REAL,
                -- Sector Specific (Banks)
                gnpa REAL, nnpa REAL, casa REAL, nim REAL, car REAL,
                -- Sector Specific (Pharma)
                rd_expense REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def get_stock_fundamentals(self, symbol):
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info
            
            debt_to_equity = info.get("debtToEquity")
            if debt_to_equity is not None and debt_to_equity > 5:
                debt_to_equity = debt_to_equity / 100

            promoter_holding = info.get("heldPercentInsiders") 
            shares_out = info.get("sharesOutstanding")
            implied_shares = info.get("impliedSharesOutstanding")
            dilution = 0.0
            if shares_out and implied_shares and shares_out > 0:
                dilution = max(0.0, (implied_shares - shares_out) / shares_out)

            return {
                "symbol": symbol,
                "company": info.get("longName") or info.get("shortName"),
                "sector": info.get("sector", "Unknown"),
                "roe": info.get("returnOnEquity"),
                "roce": self._calculate_roce(ticker),
                "roa": info.get("returnOnAssets"),
                "operating_margin": info.get("operatingMargins"),
                "debt_to_equity": debt_to_equity,
                "current_ratio": info.get("currentRatio"),
                "interest_coverage": self._calculate_interest_coverage(ticker),
                "pe": info.get("trailingPE"),
                "pb": info.get("priceToBook"),
                "peg": info.get("pegRatio"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "eps_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_growth": info.get("earningsGrowth"),
                "free_cash_flow": info.get("freeCashflow"),
                "promoter_holding": promoter_holding,
                "promoter_pledge": 0.0, # Placeholder
                "share_dilution": dilution,
                # Placeholders for banking/pharma (To be scraped later)
                "gnpa": None, "nnpa": None, "casa": None, "nim": None, "car": None,
                "rd_expense": None
            }
        except Exception as e:
            print(f"Failed {symbol}: {e}")
            return None

    def _calculate_roce(self, ticker):
        try:
            fin, bs = ticker.financials, ticker.balance_sheet
            if fin.empty or bs.empty: return None
            ebit = fin.loc["EBIT"].iloc[0] if "EBIT" in fin.index else None
            ta = bs.loc["Total Assets"].iloc[0] if "Total Assets" in bs.index else None
            cl = bs.loc["Current Liabilities"].iloc[0] if "Current Liabilities" in bs.index else None
            return round(ebit / (ta - cl), 4) if ebit and ta and cl and (ta - cl) > 0 else None
        except: return None

    def _calculate_interest_coverage(self, ticker):
        try:
            fin = ticker.financials
            if fin.empty: return None
            ebit = fin.loc["EBIT"].iloc[0] if "EBIT" in fin.index else None
            interest = fin.loc["Interest Expense"].iloc[0] if "Interest Expense" in fin.index else None
            if interest is None or interest == 0: return 100.0
            if ebit is None: return None
            return round(abs(ebit) / abs(interest), 2)
        except: return None

    def save_fundamentals(self, data):
        if data is None: return False
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO fundamentals
            (symbol, company, sector, roe, roce, roa, operating_margin, debt_to_equity, 
             current_ratio, interest_coverage, pe, pb, peg, ev_ebitda, eps_growth, revenue_growth, profit_growth, free_cash_flow, 
             promoter_holding, promoter_pledge, share_dilution, gnpa, nnpa, casa, nim, car, rd_expense)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["symbol"], data["company"], data["sector"], data["roe"], data["roce"], data["roa"], data["operating_margin"], data["debt_to_equity"],
            data["current_ratio"], data["interest_coverage"], data["pe"], data["pb"], data["peg"], data["ev_ebitda"],
            data["eps_growth"], data["revenue_growth"], data["profit_growth"], data["free_cash_flow"],
            data["promoter_holding"], data["promoter_pledge"], data["share_dilution"],
            data["gnpa"], data["nnpa"], data["casa"], data["nim"], data["car"], data["rd_expense"]
        ))
        self.conn.commit()
        return True

    def update_all_fundamentals(self):
        df = pd.read_sql("SELECT symbol FROM stocks", self.conn)
        for i, row in df.iterrows():
            sym = row['symbol']
            print(f"Processing {sym}...")
            if self.save_fundamentals(self.get_stock_fundamentals(sym)):
                print(f"  ✅ Saved {sym}")
            if (i + 1) % 10 == 0: time.sleep(1)

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    print("Dropping old table to apply new schema...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS fundamentals")
    conn.commit()
    conn.close()

    engine = FundamentalEngine()
    engine.update_all_fundamentals()
    engine.close()