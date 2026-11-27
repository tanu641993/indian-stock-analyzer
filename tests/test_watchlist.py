import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from watchlist import (
    add_watchlist_symbol,
    evaluate_watchlist_alerts,
    get_latest_watchlist_prices,
    get_watchlist_entries,
    save_watchlist_alerts,
)


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        handle, self.state_db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute(
                    "CREATE TABLE price_history "
                    "(symbol TEXT, date TEXT, close REAL)"
                )
                conn.executemany(
                    "INSERT INTO price_history (symbol, date, close) "
                    "VALUES (?, ?, ?)",
                    [
                        ("AAA", "2026-11-25", 100),
                        ("AAA", "2026-11-26", 110),
                        ("AAA", "2026-11-27", 125),
                    ],
                )

    def tearDown(self):
        os.remove(self.db_path)
        os.remove(self.state_db_path)

    def test_watchlist_persists_thresholds_and_only_reads_two_latest_prices(self):
        self.assertTrue(get_watchlist_entries(self.state_db_path).empty)
        add_watchlist_symbol(self.state_db_path, "AAA")
        add_watchlist_symbol(self.state_db_path, "AAA")
        save_watchlist_alerts(self.state_db_path, "AAA", 120, 80, 20, 5)

        entries = get_watchlist_entries(self.state_db_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries.loc[0, "price_above"], 120)
        prices = get_latest_watchlist_prices(self.db_path, ["AAA"])
        self.assertEqual(prices["AAA"]["close"].tolist(), [125, 110])
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'watchlist'"
                ).fetchone()
            )

    def test_alerts_are_checked_and_stale_inputs_are_not_reported_clear(self):
        entry = {
            "price_above": 120,
            "price_below": 80,
            "pe_above": 20,
            "pe_below": 5,
        }
        fresh_status = evaluate_watchlist_alerts(
            entry, 125, 25, 1, 1, stale_after_days=7
        )
        self.assertIn("TRIGGERED", fresh_status)
        self.assertIn("Price above", fresh_status)
        self.assertIn("P/E above", fresh_status)

        stale_status = evaluate_watchlist_alerts(
            entry, 125, 25, 10, 10, stale_after_days=7
        )
        self.assertTrue(stale_status.startswith("Not evaluated:"))
        self.assertIn("stale", stale_status)

    def test_zero_disables_thresholds(self):
        add_watchlist_symbol(self.state_db_path, "AAA")
        save_watchlist_alerts(self.state_db_path, "AAA", 0, 0, 0, 0)
        entry = get_watchlist_entries(self.state_db_path).iloc[0]
        status = evaluate_watchlist_alerts(entry, 100, 10, 1, 1, 7)
        self.assertEqual(status, "No thresholds set")

    def test_overlapping_thresholds_are_rejected(self):
        add_watchlist_symbol(self.state_db_path, "AAA")
        with self.assertRaisesRegex(ValueError, "must exceed"):
            save_watchlist_alerts(self.state_db_path, "AAA", 80, 100, 20, 25)


if __name__ == "__main__":
    unittest.main()
