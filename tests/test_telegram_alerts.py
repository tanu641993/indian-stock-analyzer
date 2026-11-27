import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from telegram_alerts import (
    deliver_alerts,
    mark_alert_delivered,
    prepare_score_alerts,
    send_test_message,
)


class TelegramAlertsTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

    def tearDown(self):
        os.remove(self.db_path)

    @staticmethod
    def scores(master, multibagger):
        return pd.DataFrame(
            [
                {
                    "Symbol": "AAA",
                    "Company": "Acme Ltd",
                    "Master_Score": master,
                    "Multibagger_Score": multibagger,
                }
            ]
        )

    def test_initial_run_baselines_existing_qualifiers_without_alerting(self):
        alerts = prepare_score_alerts(self.db_path, self.scores(85, 95))
        self.assertEqual(alerts, [])

    def test_alerts_only_on_crossing_and_can_alert_again_after_falling_below(self):
        prepare_score_alerts(self.db_path, self.scores(55, 80))

        crossed = prepare_score_alerts(self.db_path, self.scores(60, 91))
        self.assertEqual(len(crossed), 1)
        self.assertEqual(
            {item["alert_type"] for item in crossed[0]["crossings"]},
            {"master_score", "multibagger_score"},
        )
        mark_alert_delivered(
            self.db_path,
            "AAA",
            crossed[0]["crossings"],
        )
        self.assertEqual(
            prepare_score_alerts(self.db_path, self.scores(61, 92)),
            [],
        )

        prepare_score_alerts(self.db_path, self.scores(59, 89))
        recrossed = prepare_score_alerts(self.db_path, self.scores(60, 90))
        self.assertEqual(len(recrossed), 1)
        self.assertEqual(len(recrossed[0]["crossings"]), 2)

    def test_failed_delivery_remains_eligible_for_retry(self):
        prepare_score_alerts(self.db_path, self.scores(59, 89))
        first_attempt = prepare_score_alerts(self.db_path, self.scores(60, 90))
        retry = prepare_score_alerts(self.db_path, self.scores(61, 91))
        self.assertEqual(
            [item["alert_type"] for item in retry[0]["crossings"]],
            [item["alert_type"] for item in first_attempt[0]["crossings"]],
        )

    def test_below_threshold_update_resets_crossing_state(self):
        prepare_score_alerts(self.db_path, self.scores(59, 89))
        crossed = prepare_score_alerts(self.db_path, self.scores(60, 90))
        mark_alert_delivered(
            self.db_path,
            "AAA",
            crossed[0]["crossings"],
        )
        prepare_score_alerts(self.db_path, self.scores(59, 89))

        with closing(sqlite3.connect(self.db_path)) as conn:
            state = conn.execute(
                "SELECT is_above FROM telegram_score_alert_state "
                "WHERE symbol = 'AAA' ORDER BY alert_type"
            ).fetchall()
        self.assertEqual(state, [(0,), (0,)])

    def test_delivery_marks_the_crossing_only_after_telegram_accepts_it(self):
        prepare_score_alerts(self.db_path, self.scores(59, 89))
        alert = prepare_score_alerts(self.db_path, self.scores(60, 90))[0]
        sent_messages = []

        class FakeBot:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def send_message(self, **kwargs):
                sent_messages.append(kwargs)

        with patch("telegram.Bot", return_value=FakeBot()):
            asyncio.run(deliver_alerts("token", "chat", self.db_path, [alert]))

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0]["chat_id"], "chat")
        self.assertIn("Acme Ltd (AAA)", sent_messages[0]["text"])
        with closing(sqlite3.connect(self.db_path)) as conn:
            state = conn.execute(
                "SELECT is_above FROM telegram_score_alert_state "
                "WHERE symbol = 'AAA' ORDER BY alert_type"
            ).fetchall()
        self.assertEqual(state, [(1,), (1,)])

    def test_failed_telegram_send_does_not_mark_the_crossing_delivered(self):
        prepare_score_alerts(self.db_path, self.scores(59, 89))
        alert = prepare_score_alerts(self.db_path, self.scores(60, 90))[0]

        class FailingBot:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def send_message(self, **kwargs):
                raise RuntimeError("Telegram unavailable")

        with patch("telegram.Bot", return_value=FailingBot()):
            with self.assertRaisesRegex(RuntimeError, "Telegram unavailable"):
                asyncio.run(deliver_alerts("token", "chat", self.db_path, [alert]))

        with closing(sqlite3.connect(self.db_path)) as conn:
            state = conn.execute(
                "SELECT is_above FROM telegram_score_alert_state "
                "WHERE symbol = 'AAA' ORDER BY alert_type"
            ).fetchall()
        self.assertEqual(state, [(0,), (0,)])

    def test_existing_scores_are_baselined_after_threshold_change(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE telegram_score_alert_state (
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    is_above INTEGER NOT NULL,
                    score REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, alert_type)
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO telegram_score_alert_state
                    (symbol, alert_type, is_above, score)
                VALUES ('AAA', ?, 0, ?)
                """,
                [("master_score", 64), ("multibagger_score", 80)],
            )

        alerts = prepare_score_alerts(self.db_path, self.scores(64, 80))
        self.assertEqual(alerts, [])

    def test_test_message_sends_without_touching_alert_state(self):
        sent_messages = []

        class FakeBot:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def send_message(self, **kwargs):
                sent_messages.append(kwargs)

        with patch("telegram.Bot", return_value=FakeBot()):
            asyncio.run(send_test_message("token", "chat"))

        self.assertEqual(sent_messages[0]["chat_id"], "chat")
        self.assertIn("connection successful", sent_messages[0]["text"])
        self.assertEqual(os.path.getsize(self.db_path), 0)


if __name__ == "__main__":
    unittest.main()
