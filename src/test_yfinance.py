import yfinance as yf

stock = yf.Ticker("COFORGE.NS")

hist = stock.history(period="1y")

print(hist.tail())