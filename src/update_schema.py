# src/update_schema.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Add is_market_leader
try:
    cursor.execute("ALTER TABLE fundamentals ADD COLUMN is_market_leader INTEGER DEFAULT 0")
    print("✅ Added is_market_leader")
except sqlite3.OperationalError:
    print("ℹ️ is_market_leader already exists")

# 2. Add auditor_red_flag
try:
    cursor.execute("ALTER TABLE fundamentals ADD COLUMN auditor_red_flag INTEGER DEFAULT 0")
    print("✅ Added auditor_red_flag")
except sqlite3.OperationalError:
    print("ℹ️ auditor_red_flag already exists")

conn.commit()
conn.close()
print("🎉 Database schema update complete!")