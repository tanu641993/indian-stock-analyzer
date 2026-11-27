# src/fundamentals_v2.py
import sqlite3
import pandas as pd
import yfinance as yf
import os
import time
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class FundamentalEngineV2:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals (
                symbol TEXT PRIMARY KEY,
                company TEXT,
                sector TEXT,
                market_cap REAL,
                roe REAL, roce REAL, debt_to_equity REAL, pe REAL, pb REAL,
                rev_cagr_3y REAL, rev_cagr_5y REAL, profit_cagr_3y REAL, profit_cagr_5y REAL, eps_cagr_3y REAL, eps_cagr_5y REAL,
                margin_expansion REAL,
                roce_increasing INTEGER, fcf_positive_5y INTEGER, cfo_to_profit REAL,
                promoter_holding REAL, promoter_pledge REAL, share_dilution REAL,
                moat_roce_10y INTEGER,
                current_ratio REAL, interest_coverage REAL, operating_margin REAL,
                is_market_leader INTEGER DEFAULT 0,
                auditor_red_flag INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                deep_updated_at TEXT
            )
        """)
        existing_columns = {
            column[1]
            for column in cursor.execute("PRAGMA table_info(fundamentals)").fetchall()
        }
        if "deep_updated_at" not in existing_columns:
            cursor.execute("ALTER TABLE fundamentals ADD COLUMN deep_updated_at TEXT")
        self.conn.commit()

    def _calc_cagr(self, start_val, end_val, years):
        if start_val is None or end_val is None or start_val <= 0 or end_val <= 0 or years <= 0:
            return None
        return (end_val / start_val) ** (1 / years) - 1

    @staticmethod
    def deep_data_refresh_due(last_updated, now=None):
        timestamp = pd.to_datetime(last_updated, utc=True, errors="coerce")
        if pd.isna(timestamp):
            return True
        now = now or pd.Timestamp.now(tz="UTC")
        return (now - timestamp).days >= 30

    def get_stock_data(self, symbol):
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info
            
            mcap = info.get("marketCap", 0) / 10000000
            de = info.get("debtToEquity")
            if de is not None and de > 5: de = de / 100
            
            fin = ticker.financials
            cf = ticker.cashflow
            bs = ticker.balance_sheet

            rev_cagr_3y, rev_cagr_5y = None, None
            profit_cagr_3y, profit_cagr_5y = None, None
            margin_expansion = None
            roce_increasing = 0
            fcf_positive_5y = 0
            cfo_to_profit = None
            moat_roce_10y = 0
            roce_list = []

            if not fin.empty and len(fin.columns) >= 3:
                try:
                    # Revenue CAGR
                    rev_curr = fin.loc["Total Revenue"].iloc[0]
                    rev_3y = fin.loc["Total Revenue"].iloc[-3] if len(fin.columns) >= 3 else None
                    rev_5y = fin.loc["Total Revenue"].iloc[-5] if len(fin.columns) >= 5 else None
                    rev_cagr_3y = self._calc_cagr(rev_3y, rev_curr, 3)
                    rev_cagr_5y = self._calc_cagr(rev_5y, rev_curr, 5)

                    # Profit CAGR
                    profit_curr = fin.loc["Net Income"].iloc[0]
                    profit_3y = fin.loc["Net Income"].iloc[-3] if len(fin.columns) >= 3 else None
                    profit_5y = fin.loc["Net Income"].iloc[-5] if len(fin.columns) >= 5 else None
                    profit_cagr_3y = self._calc_cagr(profit_3y, profit_curr, 3)
                    profit_cagr_5y = self._calc_cagr(profit_5y, profit_curr, 5)

                    # Margin Expansion
                    op_margin_curr = fin.loc["Operating Income"].iloc[0] / rev_curr if "Operating Income" in fin.index else None
                    op_margin_5y = fin.loc["Operating Income"].iloc[-5] / rev_5y if "Operating Income" in fin.index and rev_5y else None
                    if op_margin_curr and op_margin_5y:
                        margin_expansion = op_margin_curr - op_margin_5y

                    # ROCE Trend & Moat
                    for col in fin.columns:
                        ebit = fin.loc["EBIT", col] if "EBIT" in fin.index else None
                        ta = bs.loc["Total Assets", col] if not bs.empty and "Total Assets" in bs.index else None
                        cl = bs.loc["Current Liabilities", col] if not bs.empty and "Current Liabilities" in bs.index else None
                        if ebit and ta and cl and (ta - cl) > 0:
                            roce_list.append(ebit / (ta - cl))
                    
                    if len(roce_list) >= 3:
                        roce_increasing = 1 if roce_list[0] > roce_list[-1] else 0
                    
                    if len(roce_list) >= 5 and all(r > 0.20 for r in roce_list):
                        moat_roce_10y = 1

                except Exception:
                    pass

            if not cf.empty:
                try:
                    fcf_list = cf.loc["Free Cash Flow"] if "Free Cash Flow" in cf.index else []
                    if len(fcf_list) >= 3 and all(f > 0 for f in fcf_list):
                        fcf_positive_5y = 1
                        
                    cfo_curr = cf.loc["Operating Cash Flow"].iloc[0] if "Operating Cash Flow" in cf.index else None
                    net_profit = fin.loc["Net Income"].iloc[0] if not fin.empty and "Net Income" in fin.index else None
                    if cfo_curr and net_profit and net_profit > 0:
                        cfo_to_profit = cfo_curr / net_profit
                except:
                    pass

            shares = info.get("sharesOutstanding", 1)
            implied = info.get("impliedSharesOutstanding", 1)
            dilution = (implied - shares) / shares if shares > 0 else 0
            dilution = max(0, dilution)

            return {
                "symbol": symbol, "company": info.get("longName"), "sector": info.get("sector", "Unknown"),
                "deep_updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "market_cap": mcap,
                "roe": info.get("returnOnEquity"), "roce": roce_list[0] if roce_list else None,
                "debt_to_equity": de, "pe": info.get("trailingPE"), "pb": info.get("priceToBook"),
                "rev_cagr_3y": rev_cagr_3y, "rev_cagr_5y": rev_cagr_5y,
                "profit_cagr_3y": profit_cagr_3y, "profit_cagr_5y": profit_cagr_5y,
                "eps_cagr_3y": profit_cagr_3y, "eps_cagr_5y": profit_cagr_5y,
                "margin_expansion": margin_expansion,
                "roce_increasing": roce_increasing, "fcf_positive_5y": fcf_positive_5y, "cfo_to_profit": cfo_to_profit,
                "promoter_holding": info.get("heldPercentInsiders"), "promoter_pledge": 0.0, "share_dilution": dilution,
                "moat_roce_10y": moat_roce_10y,
                "current_ratio": info.get("currentRatio"), "interest_coverage": 100 if de == 0 else None, 
                "operating_margin": info.get("operatingMargins")
            }
        except Exception as e:
            print(f"Error {symbol}: {e}")
            return None

    def update_all(self):
        df = pd.read_sql("SELECT symbol FROM stocks", self.conn)
        for i, row in df.iterrows():
            sym = row['symbol']
            
            # --- INCREMENTAL CHECK ---
            existing = pd.read_sql_query(
                "SELECT deep_updated_at FROM fundamentals WHERE symbol = ?",
                self.conn,
                params=(sym,),
            )
            
            if not existing.empty:
                last_deep_update = existing.iloc[0]["deep_updated_at"]
                if not self.deep_data_refresh_due(last_deep_update):
                    print(
                        f"⏭️ {sym} deep fundamentals are still fresh. "
                        "Updating daily metrics only..."
                    )
                    try:
                        ticker = yf.Ticker(f"{sym}.NS")
                        info = ticker.info
                        mcap = info.get("marketCap", 0) / 10000000
                        pe = info.get("trailingPE")
                        
                        self.conn.execute(
                            "UPDATE fundamentals SET market_cap = ?, pe = ?, updated_at = CURRENT_TIMESTAMP WHERE symbol = ?",
                            (mcap, pe, sym)
                        )
                        self.conn.commit()
                    except Exception as e:
                        print(f"Failed to update daily metrics for {sym}: {e}")
                    continue 
                    
            print(f"📥 Fetching Full Deep Data for {sym}...")
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
    print("✅ Database fully updated with Level 1-10 metrics!")