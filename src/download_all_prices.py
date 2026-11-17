# download_all.py

from stock_data import StockData

sd = StockData()

sd.update_all_stocks()

sd.close()