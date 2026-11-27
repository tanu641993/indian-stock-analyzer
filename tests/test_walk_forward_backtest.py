import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backtest import BacktestEngine
from scoring import ScoringEngine
from snapshot_fundamentals import (
    FUNDAMENTAL_COLUMNS,
    capture_snapshot,
)


class WalkForwardBacktestTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            "CREATE TABLE stocks (symbol TEXT PRIMARY KEY, company TEXT)"
        )
        fundamental_definitions = []
        for column in FUNDAMENTAL_COLUMNS:
            column_type = "TEXT" if column in ("company", "sector") else "REAL"
            fundamental_definitions.append(f"{column} {column_type}")
        self.conn.execute(
            "CREATE TABLE fundamentals ("
            "symbol TEXT PRIMARY KEY, "
            + ", ".join(fundamental_definitions)
            + ", updated_at TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE price_history "
            "(symbol TEXT, date TEXT, close REAL)"
        )
        self.conn.commit()
        self.scoring_engine = ScoringEngine()
        self.backtest = BacktestEngine(self.db_path, self.scoring_engine)

    def tearDown(self):
        self.backtest.close()
        self.conn.close()
        os.remove(self.db_path)

    def save_fundamental(self, symbol, strong):
        values = {
            "company": symbol,
            "sector": "Industrials",
            "market_cap": 1000,
            "roe": 0.3 if strong else 0.05,
            "roce": 0.3 if strong else 0.05,
            "debt_to_equity": 0.1 if strong else 3.0,
            "pe": 12 if strong else 100,
            "pb": 1 if strong else 8,
            "rev_cagr_3y": 0.3 if strong else 0.01,
            "rev_cagr_5y": 0.2 if strong else 0.01,
            "profit_cagr_3y": 0.3 if strong else 0.01,
            "profit_cagr_5y": 0.2 if strong else 0.01,
            "eps_cagr_3y": 0.3 if strong else 0.01,
            "eps_cagr_5y": 0.2 if strong else 0.01,
            "margin_expansion": 0.04 if strong else 0,
            "roce_increasing": int(strong),
            "fcf_positive_5y": int(strong),
            "cfo_to_profit": 1.2 if strong else 0.2,
            "promoter_holding": 0.6 if strong else 0.2,
            "promoter_pledge": 0.01 if strong else 0.2,
            "share_dilution": 0,
            "moat_roce_10y": int(strong),
            "current_ratio": 2 if strong else 0.5,
            "interest_coverage": 8 if strong else 1,
            "operating_margin": 0.2 if strong else 0.05,
            "is_market_leader": int(strong),
            "auditor_red_flag": int(not strong),
            "updated_at": "2025-01-01",
        }
        columns = ["symbol", *FUNDAMENTAL_COLUMNS, "updated_at"]
        self.conn.execute(
            f"INSERT OR REPLACE INTO fundamentals ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})",
            [symbol, *(values[column] for column in FUNDAMENTAL_COLUMNS), values["updated_at"]],
        )

    def test_picks_use_only_snapshot_available_before_rebalance(self):
        self.conn.executemany(
            "INSERT INTO stocks (symbol, company) VALUES (?, ?)",
            [("AAA", "AAA"), ("BBB", "BBB")],
        )
        self.save_fundamental("AAA", strong=True)
        self.save_fundamental("BBB", strong=False)
        capture_snapshot(self.conn, "2019-12-31")

        self.save_fundamental("AAA", strong=False)
        self.save_fundamental("BBB", strong=True)
        capture_snapshot(self.conn, "2020-12-31")

        snapshot_date, symbols = self.backtest.get_top_stocks(2020, top_n=1)
        self.assertEqual(snapshot_date, "2019-12-31")
        self.assertEqual(symbols, ["AAA"])

        snapshot_date, symbols = self.backtest.get_top_stocks(2021, top_n=1)
        self.assertEqual(snapshot_date, "2020-12-31")
        self.assertEqual(symbols, ["BBB"])

    def test_annual_returns_are_equal_weighted_from_adjusted_close_data(self):
        self.conn.executemany(
            "INSERT INTO price_history (symbol, date, close) VALUES (?, ?, ?)",
            [
                ("AAA", "2024-01-02", 100),
                ("AAA", "2024-12-31", 120),
                ("BBB", "2024-01-02", 50),
                ("BBB", "2024-12-31", 45),
            ],
        )
        self.conn.commit()

        stock_returns = self.backtest.get_annual_stock_returns(
            ["AAA", "BBB"], 2024
        )
        portfolio_return = sum(stock_returns.values()) / len(stock_returns)
        self.assertAlmostEqual(portfolio_return, 0.05)

    def test_missing_price_coverage_fails_instead_of_skipping_a_pick(self):
        self.conn.executemany(
            "INSERT INTO price_history (symbol, date, close) VALUES (?, ?, ?)",
            [("AAA", "2024-01-02", 100), ("AAA", "2024-12-31", 120)],
        )
        self.conn.commit()

        with self.assertRaisesRegex(RuntimeError, "BBB"):
            self.backtest.get_annual_stock_returns(["AAA", "BBB"], 2024)

    def test_backtest_reports_benchmark_and_turnover_costs(self):
        self.conn.executemany(
            "INSERT INTO stocks (symbol, company) VALUES (?, ?)",
            [("AAA", "AAA"), ("BBB", "BBB")],
        )
        self.save_fundamental("AAA", strong=True)
        self.save_fundamental("BBB", strong=False)
        capture_snapshot(self.conn, "2019-12-31")
        self.save_fundamental("AAA", strong=False)
        self.save_fundamental("BBB", strong=True)
        capture_snapshot(self.conn, "2020-12-31")

        self.conn.executemany(
            "INSERT INTO price_history (symbol, date, close) VALUES (?, ?, ?)",
            [
                ("AAA", "2020-01-02", 100),
                ("AAA", "2020-12-31", 120),
                ("BBB", "2021-01-04", 50),
                ("BBB", "2021-12-31", 60),
            ],
        )
        self.conn.commit()
        self.backtest.benchmark_history = pd.Series(
            [100, 105, 105, 110],
            index=pd.to_datetime(
                ["2020-01-02", "2020-12-31", "2021-01-04", "2021-12-31"]
            ),
        )

        with redirect_stdout(StringIO()):
            results = self.backtest.run_backtest(
                start_year=2020,
                end_year=2021,
                top_n=1,
                transaction_cost_bps=10,
            )

        self.assertAlmostEqual(results[0]["gross_return"], 0.2)
        self.assertAlmostEqual(results[0]["turnover"], 1.0)
        self.assertAlmostEqual(results[0]["return"], 0.1988)
        self.assertAlmostEqual(results[0]["benchmark_gross_return"], 0.05)
        self.assertAlmostEqual(results[0]["benchmark_transaction_cost"], 0.001)
        self.assertAlmostEqual(results[0]["benchmark_return"], 0.04895)
        self.assertAlmostEqual(results[1]["turnover"], 2.0)
        self.assertAlmostEqual(results[1]["return"], 0.1976)
        self.assertAlmostEqual(
            results[1]["excess_return"],
            results[1]["return"] - results[1]["benchmark_return"],
        )


if __name__ == "__main__":
    unittest.main()
