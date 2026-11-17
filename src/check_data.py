import sqlite3
import pandas as pd

conn = sqlite3.connect("database/stocks.db")

query = """
SELECT *
FROM price_history
LIMIT 10
"""

df = pd.read_sql(query, conn)

print(df)

conn.close()