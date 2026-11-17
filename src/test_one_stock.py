# test_one_stock.py

from stock_data import StockData

sd = StockData()

sd.update_stock("COFORGE")

history = sd.get_price_history("COFORGE")

print(history.tail())

sd.close()