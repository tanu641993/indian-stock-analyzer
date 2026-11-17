import sqlite3
import pandas as pd

conn = sqlite3.connect("database/stocks.db")

df = pd.read_sql(
    "SELECT * FROM stocks",
    conn
)

print(df.head())