# src/create_financial_history_table.py

import sqlite3

conn = sqlite3.connect("database/stocks.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS financial_history(

    symbol TEXT,

    year INTEGER,

    revenue REAL,

    net_income REAL,

    operating_income REAL,

    eps REAL,

    free_cash_flow REAL,

    PRIMARY KEY(symbol, year)

)
""")

conn.commit()
conn.close()
