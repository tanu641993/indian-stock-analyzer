import dalal
import pandas as pd

# Get a live quote for RELIANCE on NSE
nse_quote = dalal.quote("RELIANCE")
print("NSE Quote:", nse_quote)

# Get a quote for a BSE scrip (using its numeric code)
bse_quote = dalal.quote("500325", exchange="BSE")
print("BSE Quote:", bse_quote)

# Get historical data for RELIANCE
hist_data = dalal.history("RELIANCE", "2024-01-01", "2024-12-31")
df = pd.DataFrame(hist_data)
print(df.head())

# Get fundamentals (BSE) - This is where it shines
fundamentals = dalal.fundamentals("500325")
print("Fundamentals:", fundamentals)

# Get shareholding pattern (NSE) - Crucial for your Governance Score!
shareholding = dalal.shareholding("RELIANCE")
print("Shareholding:", shareholding)