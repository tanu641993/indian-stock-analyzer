# src/automate_flags.py

import sqlite3
import os
import pandas as pd
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class FlagAutomator:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._ensure_columns_exist()

    def _ensure_columns_exist(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(fundamentals)")
        existing_cols = [col[1] for col in cursor.fetchall()]
        
        if "is_market_leader" not in existing_cols:
            cursor.execute("ALTER TABLE fundamentals ADD COLUMN is_market_leader INTEGER DEFAULT 0")
            print("🔧 Added missing column: is_market_leader")
        
        if "auditor_red_flag" not in existing_cols:
            cursor.execute("ALTER TABLE fundamentals ADD COLUMN auditor_red_flag INTEGER DEFAULT 0")
            print("🔧 Added missing column: auditor_red_flag")
        
        self.conn.commit()

    def automate_market_leader(self):
        print("🏆 Auto-detecting Market Leaders...")
        df = pd.read_sql("SELECT symbol, sector, market_cap FROM fundamentals", self.conn)
        
        df['rank'] = df.groupby('sector')['market_cap'].rank(ascending=False, method='min')
        leaders = df[df['rank'] <= 2]['symbol'].tolist()
        
        self.conn.execute("UPDATE fundamentals SET is_market_leader = 0")
        for symbol in leaders:
            self.conn.execute("UPDATE fundamentals SET is_market_leader = 1 WHERE symbol = ?", (symbol,))
        
        self.conn.commit()
        print(f"✅ Flagged {len(leaders)} market leaders across {df['sector'].nunique()} sectors.")

    def automate_auditor_flag(self):
        print("\n🔍 Auto-detecting Auditor Red Flags...")
        df = pd.read_sql("SELECT * FROM fundamentals", self.conn)
        flagged = 0
        
        for _, row in df.iterrows():
            symbol = row['symbol']
            try:
                red_flag_score = 0
                
                cfo_to_profit = row['cfo_to_profit']
                if cfo_to_profit is not None and cfo_to_profit < 0.7:
                    red_flag_score += 1
                
                de = row['debt_to_equity']
                if de is not None and de > 1.5:
                    red_flag_score += 1
                
                fcf = row['fcf_positive_5y']
                if fcf == 0:
                    red_flag_score += 1
                
                if red_flag_score >= 2:
                    self.conn.execute("UPDATE fundamentals SET auditor_red_flag = 1 WHERE symbol = ?", (symbol,))
                    flagged += 1
                else:
                    self.conn.execute("UPDATE fundamentals SET auditor_red_flag = 0 WHERE symbol = ?", (symbol,))
                    
            except Exception as e:
                print(f"  ⚠️ Could not compute red flag for {symbol}: {e}")
                self.conn.execute("UPDATE fundamentals SET auditor_red_flag = 0 WHERE symbol = ?", (symbol,))
        
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
    print("\n🎉 All flags updated automatically!")