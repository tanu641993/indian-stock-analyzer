import pandas as pd
import sqlite3

df = pd.read_csv("data/nifty_midcap_100.csv")

conn = sqlite3.connect("database/stocks.db")

df.to_sql(
    "stocks",
    conn,
    if_exists="replace",
    index=False
)

print("Stocks Loaded")