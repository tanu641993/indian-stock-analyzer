import sqlite3

conn = sqlite3.connect("database/stocks.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks(
    symbol TEXT PRIMARY KEY,
    company_name TEXT
)
""")

conn.commit()
conn.close()

print("Database Created")