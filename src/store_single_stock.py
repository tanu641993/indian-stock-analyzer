# src/store_single_stock.py

import sqlite3
import pandas as pd
import yfinance as yf

# Stock symbol
symbol = "COFORGE.NS"

# Download 10 years of data
df = yf.download(
    symbol,
    period="10y",
    auto_adjust=True,
    progress=False
)

# Check if data exists
if df.empty:
    print("No data downloaded")
    exit()

# Fix MultiIndex columns (newer yfinance versions)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Move Date from index to column
df.reset_index(inplace=True)

# Rename columns
df.rename(columns={
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume"
}, inplace=True)

# Add symbol column
df["symbol"] = symbol

# Keep only needed columns
df = df[
    [
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]
]

# Debug output
print("\nColumns:")
print(df.columns)

print("\nFirst 5 rows:")
print(df.head())

# Save to SQLite
conn = sqlite3.connect("database/stocks.db")

df.to_sql(
    "price_history",
    conn,
    if_exists="append",
    index=False
)

conn.close()

print(f"\nSaved {len(df)} rows successfully!")