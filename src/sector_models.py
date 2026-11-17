# src/sector_models.py

class SectorScoring:
    """
    Applies specific scoring models based on the industry.
    Total Quality + Financial Score = 40 Points.
    """

    @staticmethod
    def normal_company(row):
        """Standard Manufacturing/Consumer/Industrial Companies (Max 40 pts)"""
        score = 0
        breakdown = {}

        # 1. ROCE (10 pts)
        roce = row["roce"]
        if roce is not None:
            if roce > 0.20: score += 10; breakdown["ROCE"] = 10
            elif roce > 0.15: score += 7; breakdown["ROCE"] = 7
            elif roce > 0.10: score += 4; breakdown["ROCE"] = 4
            else: breakdown["ROCE"] = 0

        # 2. ROE (10 pts)
        roe = row["roe"]
        if roe is not None:
            if roe > 0.18: score += 10; breakdown["ROE"] = 10
            elif roe > 0.12: score += 7; breakdown["ROE"] = 7
            else: breakdown["ROE"] = 0

        # 3. Debt/Equity (10 pts)
        de = row["debt_to_equity"]
        if de is not None:
            if de < 0.5: score += 10; breakdown["Debt_Eq"] = 10
            elif de < 1.0: score += 6; breakdown["Debt_Eq"] = 6
            else: breakdown["Debt_Eq"] = 0

        # 4. FCF (10 pts)
        fcf = row["free_cash_flow"]
        if fcf is not None and fcf > 0: score += 10; breakdown["FCF"] = 10
        else: breakdown["FCF"] = 0

        return score, breakdown

    @staticmethod
    def bank(row):
        """Banking & Financial Services (Max 40 pts)"""
        score = 0
        breakdown = {}

        # 1. ROA (10 pts) - Critical for Banks
        roa = row["roa"]
        if roa is not None:
            if roa > 0.015: score += 10; breakdown["ROA"] = 10 # >1.5% is excellent
            elif roa > 0.010: score += 6; breakdown["ROA"] = 6
            else: breakdown["ROA"] = 0

        # 2. ROE (10 pts)
        roe = row["roe"]
        if roe is not None:
            if roe > 0.15: score += 10; breakdown["ROE"] = 10
            elif roe > 0.11: score += 6; breakdown["ROE"] = 6
            else: breakdown["ROE"] = 0

        # 3. GNPA & NNPA (10 pts) - Placeholder (Requires manual/scraped data)
        # For now, if not available, we assume average quality (5 pts)
        gnpa = row["gnpa"]
        if gnpa is not None:
            if gnpa < 0.02: score += 10; breakdown["GNPA"] = 10
            elif gnpa < 0.05: score += 5; breakdown["GNPA"] = 5
            else: breakdown["GNPA"] = 0
        else:
            score += 5; breakdown["GNPA_Default"] = 5 

        # 4. NIM & CASA (10 pts) - Placeholder
        nim = row["nim"]
        if nim is not None:
            if nim > 0.035: score += 10; breakdown["NIM"] = 10
            elif nim > 0.025: score += 5; breakdown["NIM"] = 5
            else: breakdown["NIM"] = 0
        else:
            score += 5; breakdown["NIM_Default"] = 5

        return score, breakdown

    @staticmethod
    def it_company(row):
        """Information Technology / Software (Max 40 pts)"""
        score = 0
        breakdown = {}

        # 1. Revenue Growth (15 pts) - IT companies need to grow
        rev = row["revenue_growth"]
        if rev is not None:
            if rev > 0.15: score += 15; breakdown["Rev_Growth"] = 15
            elif rev > 0.10: score += 10; breakdown["Rev_Growth"] = 10
            elif rev > 0.05: score += 5; breakdown["Rev_Growth"] = 5
            else: breakdown["Rev_Growth"] = 0

        # 2. Operating Margin (15 pts) - High margins are key
        op = row["operating_margin"]
        if op is not None:
            if op > 0.25: score += 15; breakdown["Op_Margin"] = 15
            elif op > 0.18: score += 10; breakdown["Op_Margin"] = 10
            else: breakdown["Op_Margin"] = 0

        # 3. Free Cash Flow (10 pts) - IT must generate cash
        fcf = row["free_cash_flow"]
        if fcf is not None and fcf > 0: score += 10; breakdown["FCF"] = 10
        else: breakdown["FCF"] = 0

        return score, breakdown

    @staticmethod
    def pharma(row):
        """Pharmaceuticals / Healthcare (Max 40 pts)"""
        score = 0
        breakdown = {}

        # 1. Revenue Growth (15 pts)
        rev = row["revenue_growth"]
        if rev is not None:
            if rev > 0.15: score += 15; breakdown["Rev_Growth"] = 15
            elif rev > 0.10: score += 10; breakdown["Rev_Growth"] = 10
            else: breakdown["Rev_Growth"] = 0

        # 2. Operating Margin (15 pts)
        op = row["operating_margin"]
        if op is not None:
            if op > 0.20: score += 15; breakdown["Op_Margin"] = 15
            elif op > 0.15: score += 10; breakdown["Op_Margin"] = 10
            else: breakdown["Op_Margin"] = 0

        # 3. R&D / FCF (10 pts) 
        # (yfinance doesn't have R&D, so we use FCF as a proxy for funding R&D)
        fcf = row["free_cash_flow"]
        if fcf is not None and fcf > 0: score += 10; breakdown["FCF"] = 10
        else: breakdown["FCF"] = 0

        return score, breakdown

    @classmethod
    def calculate(cls, row):
        """Routes the stock to the correct model based on yfinance sector"""
        sector = row["sector"]
        
        if sector is None:
            sector = "Unknown"

        # Map yfinance sectors to our models
        if "Financial" in sector or "Bank" in sector:
            return cls.bank(row), "Bank"
        elif "Technology" in sector:
            return cls.it_company(row), "IT"
        elif "Healthcare" in sector or "Pharma" in sector:
            return cls.pharma(row), "Pharma"
        else:
            return cls.normal_company(row), "Normal"