# src/create_price_table.py

import sqlite3

conn = sqlite3.connect("database/stocks.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS price_history (

    symbol TEXT,

    date TEXT,

    open REAL,

    high REAL,

    low REAL,

    close REAL,

    volume INTEGER
)
""")

conn.commit()

conn.close()

print("price_history table created")