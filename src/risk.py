# src/risk.py

import sqlite3
import pandas as pd
import yfinance as yf
import numpy as np
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class RiskEngine:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.market_returns = None # Cache for Nifty 50 returns

    def _get_market_returns(self):
        """Fetch 1 year of Nifty 50 daily returns for Beta calculation"""
        if self.market_returns is not None:
            return self.market_returns

        try:
            # Download 1 year of Nifty 50 data
            nifty = yf.download("^NSEI", period="1y", progress=False, auto_adjust=True, multi_level_index=False)
            if nifty.empty:
                return None
                
            nifty.index = pd.to_datetime(nifty.index).tz_localize(None)
            self.market_returns = nifty['Close'].pct_change().dropna()
            return self.market_returns
        except Exception as e:
            print(f"Failed to fetch Nifty 50 data: {e}")
            return None

    def calculate_risk_metrics(self, symbol):
        """Calculate Volatility, Beta, and Max Drawdown for a stock"""
        
        # 1. Fetch stock data (last 1 year = approx 252 trading days)
        query = "SELECT date, close FROM price_history WHERE symbol = ? ORDER BY date DESC LIMIT 252"
        df = pd.read_sql(query, self.conn, params=(symbol,))
        
        if df.empty or len(df) < 50:
            return None # Not enough data
        
        # Sort ascending
        df = df.sort_values("date")
        df.index = pd.to_datetime(df['date']).dt.tz_localize(None)
        
        prices = df['close']
        returns = prices.pct_change().dropna()

        # 2. Calculate Volatility (Annualized)
        # Standard deviation of daily returns * sqrt(252)
        volatility = returns.std() * np.sqrt(252)

        # 3. Calculate Max Drawdown
        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max
        max_drawdown = drawdown.min() # This will be a negative number (e.g., -0.25)

        # 4. Calculate Beta
        market_returns = self._get_market_returns()
        beta = 1.0 # Default to market beta if we can't calculate
        if market_returns is not None:
            # Align dates between stock and market
            combined = pd.concat([returns, market_returns], axis=1, join='inner')
            combined.columns = ['stock', 'market']
            
            if len(combined) > 20:
                covariance = combined['stock'].cov(combined['market'])
                variance = combined['market'].var()
                if variance > 0:
                    beta = covariance / variance

        return {
            "volatility": round(volatility, 4),
            "max_drawdown": round(max_drawdown, 4),
            "beta": round(beta, 2)
        }

    def calculate_penalty(self, symbol):
        """Calculate a risk penalty (0 to 10 points) based on risk metrics"""
        metrics = self.calculate_risk_metrics(symbol)
        
        if metrics is None:
            # Penalize slightly if data is missing (can't verify risk)
            return 2.0, {"Error": "Insufficient data"}

        vol = metrics['volatility']
        mdd = metrics['max_drawdown']
        beta = metrics['beta']
        
        penalty = 0
        breakdown = {}

        # 1. Volatility Penalty (Max 3 pts)
        # > 40% annualized vol is high for Indian midcaps
        if vol > 0.45: penalty += 3; breakdown["High_Vol"] = -3
        elif vol > 0.35: penalty += 2; breakdown["High_Vol"] = -2
        elif vol > 0.25: penalty += 1; breakdown["High_Vol"] = -1

        # 2. Max Drawdown Penalty (Max 4 pts)
        # If the stock dropped > 30% from its peak in the last year
        if mdd < -0.40: penalty += 4; breakdown["Deep_Drawdown"] = -4
        elif mdd < -0.30: penalty += 3; breakdown["Deep_Drawdown"] = -3
        elif mdd < -0.20: penalty += 1; breakdown["Deep_Drawdown"] = -1

        # 3. Beta Penalty (Max 3 pts)
        # High beta means it amplifies market crashes
        if beta > 1.6: penalty += 3; breakdown["High_Beta"] = -3
        elif beta > 1.3: penalty += 2; breakdown["High_Beta"] = -2
        elif beta > 1.1: penalty += 1; breakdown["High_Beta"] = -1

        return penalty, breakdown

    def close(self):
        self.conn.close()