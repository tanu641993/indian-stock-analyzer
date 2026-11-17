import sqlite3

conn = sqlite3.connect("database/stocks.db")

cursor = conn.cursor()

cursor.execute(
    "PRAGMA table_info(price_history)"
)

for row in cursor.fetchall():
    print(row)

conn.close()