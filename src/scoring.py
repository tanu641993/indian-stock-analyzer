# src/scoring.py
import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

class ScoringEngine:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def _safe(self, val, default=0):
        return default if val is None or pd.isna(val) else val

    # 1. BUSINESS QUALITY (Max 25)
    def score_business_quality(self, row):
        score = 0
        # ROCE > 20% (10 pts)
        if self._safe(row["roce"]) > 0.20: score += 10
        elif self._safe(row["roce"]) > 0.15: score += 6
        
        # Operating Margin > 15% (5 pts)
        if self._safe(row["operating_margin"]) > 0.15: score += 5
        elif self._safe(row["operating_margin"]) > 0.10: score += 3
        
        # Margin Stability/Expansion (10 pts)
        if self._safe(row["margin_expansion"]) > 0.02: score += 10
        elif self._safe(row["margin_expansion"]) > 0: score += 5
        
        return score

    # 2. GROWTH (Max 20)
    def score_growth(self, row):
        score = 0
        # 3Y Rev CAGR > 20% (5 pts)
        if self._safe(row["rev_cagr_3y"]) > 0.20: score += 5
        elif self._safe(row["rev_cagr_3y"]) > 0.15: score += 3

        # 5Y Rev CAGR > 15% (5 pts)
        if self._safe(row["rev_cagr_5y"]) > 0.15: score += 5

        # 3Y Profit CAGR > 20% (5 pts)
        if self._safe(row["profit_cagr_3y"]) > 0.20: score += 5
        elif self._safe(row["profit_cagr_3y"]) > 0.15: score += 3

        # Acceleration: 3Y CAGR > 5Y CAGR (5 pts)
        if self._safe(row["rev_cagr_3y"]) > self._safe(row["rev_cagr_5y"]) and self._safe(row["rev_cagr_3y"]) > 0:
            score += 5
        
        return score

    # 3. FINANCIAL STRENGTH (Max 15)
    def score_financial_strength(self, row):
        score = 0
        de = self._safe(row["debt_to_equity"], 2)
        if de < 0.3: score += 7
        elif de < 0.5: score += 5
        elif de < 1.0: score += 2

        if self._safe(row["interest_coverage"]) > 5.0: score += 4
        elif self._safe(row["interest_coverage"]) > 3.0: score += 2

        if self._safe(row["current_ratio"]) > 1.5: score += 4
        elif self._safe(row["current_ratio"]) > 1.0: score += 2
        
        return score

    # 4. VALUATION (Max 10) - Sector Relative
    def score_valuation(self, row, sector_pe_median):
        score = 0
        pe = self._safe(row["pe"], 999)
        pb = self._safe(row["pb"], 999)
        
        # PE vs Sector
        if pe < (sector_pe_median * 0.8): score += 5
        elif pe < sector_pe_median: score += 3
        elif pe < (sector_pe_median * 1.5): score += 1
            
        # PB
        if pb < 2: score += 5
        elif pb < 4: score += 3
        elif pb < 6: score += 1
        
        return score

    # 5. CAPITAL ALLOCATION (Max 10)
    def score_capital_allocation(self, row):
        score = 0
        if self._safe(row["fcf_positive_5y"]) == 1: score += 5
        if self._safe(row["cfo_to_profit"]) > 0.9: score += 5
        return score

    # 6. GOVERNANCE (Max 10)
    def score_governance(self, row):
        score = 0
        if self._safe(row["promoter_holding"]) > 0.50: score += 4
        elif self._safe(row["promoter_holding"]) > 0.30: score += 2

        if self._safe(row["promoter_pledge"]) < 0.05: score += 3
        elif self._safe(row["promoter_pledge"]) < 0.10: score += 1

        # NEW: Auditor Red Flag
        if self._safe(row["auditor_red_flag"]) == 0: score += 3
        
        return score

    # 7. MOAT (Max 5)
    def score_moat(self, row):
        score = 0
        if self._safe(row["moat_roce_10y"]) == 1: score += 3
        # NEW: Manual Market Leadership
        if self._safe(row["is_market_leader"]) == 1: score += 2
        return score

    # 8. RISK PENALTY (Max 5 deduction)
    def score_risk(self, row):
        score = 5 # Start with full points
        de = self._safe(row["debt_to_equity"], 0)
        if de > 1.0: score -= 2
        if self._safe(row["share_dilution"]) > 0.05: score -= 2
        if self._safe(row["promoter_pledge"]) > 0.10: score -= 1
        return max(0, score)

    # ==========================================
    # MASTER INVESTMENT QUALITY SCORE (Out of 100)
    # ==========================================
    def calculate_master_score(self, row, sector_pe_median):
        bq = self.score_business_quality(row)
        gr = self.score_growth(row)
        fs = self.score_financial_strength(row)
        va = self.score_valuation(row, sector_pe_median)
        ca = self.score_capital_allocation(row)
        gov = self.score_governance(row)
        moat = self.score_moat(row)
        risk = self.score_risk(row)

        total = bq + gr + fs + va + ca + gov + moat + risk
        return round(total, 1)

    # Keep these for the dashboard tabs
    def score_compounder(self, row):
        # Simplified Compounder (Quality + Capital Allocation + Moat)
        return self.score_business_quality(row) + self.score_capital_allocation(row) + self.score_moat(row)
        
    def score_multibagger(self, row):
        # Strict Screener
        if self._safe(row["market_cap"]) > 20000: return 0
        if self._safe(row["roce"]) < 0.20: return 0
        if self._safe(row["debt_to_equity"]) > 0.5: return 0
        if self._safe(row["rev_cagr_3y"]) < 0.20: return 0
        if self._safe(row["profit_cagr_3y"]) < 0.20: return 0
        if self._safe(row["promoter_holding"]) < 0.50: return 0
        return 80 + (self.score_growth(row) / 2) # Scale up to 100

    def rank_all(self):
        df = pd.read_sql("SELECT * FROM fundamentals", self.conn)
        return self.rank_fundamentals(df)

    def rank_fundamentals(self, df):
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "Symbol",
                    "Sector",
                    "Master_Score",
                    "Compounder_Score",
                    "Growth_Score",
                    "Value_Score",
                    "Multibagger_Score",
                ]
            )

        # Calculate Sector Median PE
        sector_pe = df.groupby("sector")["pe"].median().to_dict()
        
        results = []
        for _, row in df.iterrows():
            sector = row["sector"] if row["sector"] in sector_pe else "Unknown"
            median_pe = sector_pe.get(sector, 25)
            
            results.append({
                "Symbol": row["symbol"],
                "Sector": sector,
                "Master_Score": self.calculate_master_score(row, median_pe),
                "Compounder_Score": self.score_compounder(row), # Out of 40 (scaled to 100 later if needed)
                "Growth_Score": self.score_growth(row),         # Out of 20 (scaled to 100 later if needed)
                "Value_Score": self.score_valuation(row, median_pe), # Out of 10
                "Multibagger_Score": self.score_multibagger(row)
            })
            
        final_df = pd.DataFrame(results)
        final_df = final_df.loc[:, ~final_df.columns.duplicated()]
        return final_df.sort_values(
            ["Master_Score", "Symbol"], ascending=[False, True]
        ).reset_index(drop=True)

    def close(self):
        self.conn.close()