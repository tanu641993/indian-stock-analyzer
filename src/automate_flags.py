# src/automate_flags.py

import sqlite3
import os
import pandas as pd
import numpy as np
from ledgerlens import beneish_m, altman_z

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class FlagAutomator:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def automate_market_leader(self):
        """Flag the top 2 stocks by market cap in each sector as market leaders."""
        print("🏆 Auto-detecting Market Leaders...")
        
        df = pd.read_sql("SELECT symbol, sector, market_cap FROM fundamentals", self.conn)
        
        # Rank by market cap within each sector
        df['rank'] = df.groupby('sector')['market_cap'].rank(ascending=False, method='min')
        
        # Top 2 in each sector = market leader
        leaders = df[df['rank'] <= 2]['symbol'].tolist()
        
        # Reset all flags to 0 first
        self.conn.execute("UPDATE fundamentals SET is_market_leader = 0")
        
        # Set flags for leaders
        for symbol in leaders:
            self.conn.execute(
                "UPDATE fundamentals SET is_market_leader = 1 WHERE symbol = ?",
                (symbol,)
            )
        
        self.conn.commit()
        print(f"✅ Flagged {len(leaders)} market leaders across {df['sector'].nunique()} sectors.")

    def automate_auditor_flag(self):
        """Use Beneish M-Score to detect potential earnings manipulation."""
        print("\n🔍 Auto-detecting Auditor Red Flags (Beneish M-Score)...")
        
        df = pd.read_sql("SELECT * FROM fundamentals", self.conn)
        flagged = 0
        
        for _, row in df.iterrows():
            symbol = row['symbol']
            
            # Beneish M-Score requires 8 financial ratios.
            # We use the available data in our database as proxies.
            # If key data is missing, we skip the stock.
            try:
                # Simplified Beneish M-Score using available fields
                # (Full model needs 8 variables; we use a proxy with 3 available variables)
                # DSRI proxy: Revenue growth vs Receivables growth (we don't have receivables, so skip)
                # GMI proxy: Gross margin change
                # AQI proxy: Asset quality change
                # SGI: Sales growth index (revenue growth)
                # DEPI: Depreciation index (not available)
                # SGAI: SG&A index (not available)
                # LVGI: Leverage index (debt/equity change)
                # TATA: Total accruals to total assets (CFO vs Net Income)
                
                # Since we lack full data, we use a simplified "Red Flag Score"
                # based on 3 critical signals:
                red_flag_score = 0
                
                # Signal 1: CFO is significantly lower than Net Profit (accruals red flag)
                cfo_to_profit = row['cfo_to_profit']
                if cfo_to_profit is not None and cfo_to_profit < 0.7:
                    red_flag_score += 1
                
                # Signal 2: High Debt/Equity (financial distress red flag)
                de = row['debt_to_equity']
                if de is not None and de > 1.5:
                    red_flag_score += 1
                
                # Signal 3: Negative Free Cash Flow (cash burn red flag)
                fcf = row['fcf_positive_5y']
                if fcf == 0:
                    red_flag_score += 1
                
                # If 2 or more red flags, set auditor_red_flag = 1
                if red_flag_score >= 2:
                    self.conn.execute(
                        "UPDATE fundamentals SET auditor_red_flag = 1 WHERE symbol = ?",
                        (symbol,)
                    )
                    flagged += 1
                else:
                    self.conn.execute(
                        "UPDATE fundamentals SET auditor_red_flag = 0 WHERE symbol = ?",
                        (symbol,)
                    )
                    
            except Exception as e:
                print(f"  ⚠️ Could not compute red flag for {symbol}: {e}")
                self.conn.execute(
                    "UPDATE fundamentals SET auditor_red_flag = 0 WHERE symbol = ?",
                    (symbol,)
                )
        
        self.conn.commit()
        print(f"✅ Flagged {flagged} stocks with potential auditor red flags.")

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    print("🚀 Starting Automated Flag Detection...\n")
    automator = FlagAutomator()
    automator.automate_market_leader()
    automator.automate_auditor_flag()
    automator.close()
    print("\n🎉 All flags updated automatically! Restart Streamlit to see the new scores.")