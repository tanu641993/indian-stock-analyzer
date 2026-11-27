import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import fundamentals_v2


class FundamentalFreshnessTests(unittest.TestCase):
    def test_deep_refresh_age_uses_the_deep_update_timestamp(self):
        now = pd.Timestamp("2026-11-27T00:00:00Z")
        self.assertTrue(fundamentals_v2.FundamentalEngineV2.deep_data_refresh_due(None, now))
        self.assertFalse(
            fundamentals_v2.FundamentalEngineV2.deep_data_refresh_due(
                "2026-10-29T00:00:00Z", now
            )
        )
        self.assertTrue(
            fundamentals_v2.FundamentalEngineV2.deep_data_refresh_due(
                "2026-10-28T00:00:00Z", now
            )
        )

    def test_legacy_database_records_unknown_deep_refresh_time(self):
        handle, db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE fundamentals (
                            symbol TEXT PRIMARY KEY,
                            updated_at TEXT
                        )
                        """
                    )
                    conn.execute(
                        "INSERT INTO fundamentals (symbol, updated_at) VALUES (?, ?)",
                        ("AAA", "2026-11-27 12:00:00"),
                    )

            with patch.object(fundamentals_v2, "DB_PATH", db_path):
                engine = fundamentals_v2.FundamentalEngineV2()
                columns = {
                    row[1]
                    for row in engine.conn.execute(
                        "PRAGMA table_info(fundamentals)"
                    ).fetchall()
                }
                deep_updated_at = engine.conn.execute(
                    "SELECT deep_updated_at FROM fundamentals WHERE symbol = ?",
                    ("AAA",),
                ).fetchone()[0]
                engine.conn.close()

            self.assertIn("deep_updated_at", columns)
            self.assertIsNone(deep_updated_at)
        finally:
            os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
