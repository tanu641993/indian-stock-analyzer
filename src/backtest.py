# src/backtest.py

import sqlite3
import pandas as pd
import yfinance as yf
import os
import numpy as np
from scoring import ScoringEngine

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class BacktestEngine:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.scoring_engine = ScoringEngine()

    def get_top_stocks(self, top_n=10):
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            rankings = self.scoring_engine.rank_all_stocks()
        
        return [r['symbol'] for r in rankings[:top_n]]

    def get_portfolio_prices(self, symbols, start_date="2020-01-01"):
        placeholders = ",".join(["?"] * len(symbols))
        query = f"""
            SELECT date, symbol, close 
            FROM price_history 
            WHERE symbol IN ({placeholders}) 
            AND date >= ?
        """
        params = symbols + [start_date]
        
        df = pd.read_sql(query, self.conn, params=params)
        if df.empty: return pd.DataFrame()
        
        df_pivot = df.pivot(index="date", columns="symbol", values="close")
        
        # FIX 1: Strip timezone to match benchmark data
        df_pivot.index = pd.to_datetime(df_pivot.index)
        if df_pivot.index.tz is not None:
            df_pivot.index = df_pivot.index.tz_localize(None)
            
        df_pivot = df_pivot.sort_index().ffill().dropna()
        return df_pivot

    def get_benchmark_data(self, start_date="2020-01-01"):
        print("Downloading Benchmark Data (Nifty 50 & Midcap 100)...")
        # FIX 2: Use ETF proxies as fallbacks if indices fail
        tickers = {
            "Nifty_50": "^NSEI", 
            "Midcap_100": "^NSMIDCP"
        }
        fallback_tickers = {
            "Nifty_50": "NIFTYBEES.NS",  # Nippon India ETF Nifty 50
            "Midcap_100": "MID150BEES.NS" # Nippon India ETF Nifty Midcap 150
        }
        
        benchmarks = {}
        for name, ticker in tickers.items():
            try:
                # FIX 3: multi_level_index=False fixes the MultiIndex column issues
                df = yf.download(ticker, start=start_date, progress=False, auto_adjust=True, multi_level_index=False)
                
                if df.empty:
                    print(f"  ⚠️ {ticker} failed. Trying fallback {fallback_tickers[name]}...")
                    df = yf.download(fallback_tickers[name], start=start_date, progress=False, auto_adjust=True, multi_level_index=False)
                
                if not df.empty:
                    close_prices = df['Close']
                    close_prices.index = pd.to_datetime(close_prices.index).tz_localize(None)
                    benchmarks[name] = close_prices
            except Exception as e:
                print(f"  ❌ Failed to download {name}: {e}")
                
        return pd.DataFrame(benchmarks)

    def calculate_metrics(self, series):
        if series.empty or len(series) < 2:
            return 0.0, 0.0, 0.0
            
        days = (series.index[-1] - series.index[0]).days
        years = days / 365.25
        if years == 0: years = 1 
            
        start_price = series.iloc[0]
        end_price = series.iloc[-1]
        
        total_return = (end_price - start_price) / start_price
        cagr = (end_price / start_price) ** (1 / years) - 1
        
        rolling_max = series.cummax()
        drawdown = (series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        return total_return, cagr, max_drawdown

    def run_backtest(self, top_n=10):
        print(f"🚀 Running 5-Year Backtest for Top {top_n} Stocks...\n")
        
        top_symbols = self.get_top_stocks(top_n)
        print(f"Selected Portfolio: {', '.join(top_symbols)}\n")
        
        print("Fetching historical prices for portfolio...")
        portfolio_prices = self.get_portfolio_prices(top_symbols)
        benchmark_prices = self.get_benchmark_data()
        
        if portfolio_prices.empty:
            print("❌ Error: No price data found for the selected stocks in SQLite.")
            return
            
        if benchmark_prices.empty:
            print("❌ Error: Could not download benchmark data.")
            return

        # Align dates
        combined_dates = portfolio_prices.index.intersection(benchmark_prices.index)
        if len(combined_dates) == 0:
            print("❌ Error: No overlapping dates found between portfolio and benchmarks.")
            return
            
        portfolio_prices = portfolio_prices.loc[combined_dates]
        benchmark_prices = benchmark_prices.loc[combined_dates]
        
        # Calculate Portfolio Performance
        daily_returns = portfolio_prices.pct_change().dropna()
        portfolio_daily_return = daily_returns.mean(axis=1)
        portfolio_equity = (1 + portfolio_daily_return).cumprod() * 100
        
        port_tr, port_cagr, port_mdd = self.calculate_metrics(portfolio_equity)
        
        print("\n" + "="*60)
        print("📊 BACKTEST RESULTS (Equal-Weighted Portfolio)")
        print("="*60)
        print(f"{'Metric':<20} | {'Portfolio':<12} | {'Nifty 50':<12} | {'Midcap 100'}")
        print("-" * 62)
        
        print(f"{'Total Return':<20} | {port_tr*100:>10.2f}% | ", end="")
        b_metrics = {}
        for b_name in benchmark_prices.columns:
            b_tr, b_cagr, b_mdd = self.calculate_metrics(benchmark_prices[b_name])
            b_metrics[b_name] = (b_tr, b_cagr, b_mdd)
            print(f"{b_tr*100:>10.2f}% | ", end="")
        print()
        
        print(f"{'CAGR':<20} | {port_cagr*100:>10.2f}% | ", end="")
        for b_name in benchmark_prices.columns:
            print(f"{b_metrics[b_name][1]*100:>10.2f}% | ", end="")
        print()
        
        print(f"{'Max Drawdown':<20} | {port_mdd*100:>10.2f}% | ", end="")
        for b_name in benchmark_prices.columns:
            print(f"{b_metrics[b_name][2]*100:>10.2f}% | ", end="")
        print()
        print("-" * 62)
        
        stock_returns = (portfolio_prices.iloc[-1] - portfolio_prices.iloc[0]) / portfolio_prices.iloc[0]
        winners = (stock_returns > 0).sum()
        win_rate = winners / len(top_symbols) * 100
        
        print(f"\n🎯 Win Rate: {win_rate:.1f}% ({winners}/{top_n} stocks had positive returns)")
        
        print("\n📈 Individual Stock Returns:")
        for sym, ret in stock_returns.sort_values(ascending=False).items():
            print(f"  {sym:<12} : {ret*100:>7.2f}%")
            
        print("\n" + "="*60)

    def close(self):
        self.conn.close()
        self.scoring_engine.close()

if __name__ == "__main__":
    backtester = BacktestEngine()
    backtester.run_backtest(top_n=10)
    backtester.close()