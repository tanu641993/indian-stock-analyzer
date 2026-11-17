# src/test_financial_statements.py

import yfinance as yf
import pandas as pd

symbol = "COFORGE.NS"

print("=" * 80)
print(f"TESTING: {symbol}")
print("=" * 80)

ticker = yf.Ticker(symbol)

# ------------------------------------------------------------------
# FINANCIALS
# ------------------------------------------------------------------

print("\n\nFINANCIALS")
print("-" * 80)

try:
    financials = ticker.financials

    if financials.empty:
        print("No financial data found")
    else:
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)

        print(financials)

        print("\nAvailable Financial Rows:")
        for row in financials.index:
            print(row)

except Exception as e:
    print("Financials Error:", e)

# ------------------------------------------------------------------
# BALANCE SHEET
# ------------------------------------------------------------------

print("\n\nBALANCE SHEET")
print("-" * 80)

try:
    balance_sheet = ticker.balance_sheet

    if balance_sheet.empty:
        print("No balance sheet data found")
    else:
        print(balance_sheet)

        print("\nAvailable Balance Sheet Rows:")
        for row in balance_sheet.index:
            print(row)

except Exception as e:
    print("Balance Sheet Error:", e)

# ------------------------------------------------------------------
# CASH FLOW
# ------------------------------------------------------------------

print("\n\nCASH FLOW")
print("-" * 80)

try:
    cashflow = ticker.cashflow

    if cashflow.empty:
        print("No cash flow data found")
    else:
        print(cashflow)

        print("\nAvailable Cash Flow Rows:")
        for row in cashflow.index:
            print(row)

except Exception as e:
    print("Cash Flow Error:", e)

# ------------------------------------------------------------------
# INFO
# ------------------------------------------------------------------

print("\n\nBASIC INFO")
print("-" * 80)

try:
    info = ticker.info

    keys_to_check = [
        "longName",
        "sector",
        "industry",
        "marketCap",
        "trailingPE",
        "priceToBook",
        "returnOnEquity",
        "returnOnAssets",
        "revenueGrowth",
        "earningsGrowth",
        "operatingMargins",
        "freeCashflow",
        "debtToEquity",
        "currentRatio",
        "heldPercentInsiders"
    ]

    for key in keys_to_check:
        print(f"{key}: {info.get(key)}")

except Exception as e:
    print("Info Error:", e)

print("\n\nTEST COMPLETE")