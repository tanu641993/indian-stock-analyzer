import argparse
import asyncio
import os
import sqlite3
from contextlib import closing

from scoring import ScoringEngine


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")
ALERT_RULES = (
    ("Master_Score", "master_score", 80, "Master Score"),
    ("Multibagger_Score", "multibagger_score", 90, "Multibagger Score"),
)


def prepare_score_alerts(db_path, ranked_scores):
    alerts_by_symbol = {}
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_score_alert_state (
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    is_above INTEGER NOT NULL,
                    score REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, alert_type)
                )
                """
            )
            for row in ranked_scores.itertuples(index=False):
                symbol = str(row.Symbol)
                company = str(getattr(row, "Company", symbol))
                for score_column, alert_type, threshold, label in ALERT_RULES:
                    score = float(getattr(row, score_column))
                    is_above = score >= threshold
                    previous = conn.execute(
                        """
                        SELECT is_above
                        FROM telegram_score_alert_state
                        WHERE symbol = ? AND alert_type = ?
                        """,
                        (symbol, alert_type),
                    ).fetchone()

                    if previous is None:
                        conn.execute(
                            """
                            INSERT INTO telegram_score_alert_state
                                (symbol, alert_type, is_above, score)
                            VALUES (?, ?, ?, ?)
                            """,
                            (symbol, alert_type, int(is_above), score),
                        )
                    elif is_above and not previous[0]:
                        alert = alerts_by_symbol.setdefault(
                            symbol,
                            {"symbol": symbol, "company": company, "crossings": []},
                        )
                        alert["crossings"].append(
                            {
                                "alert_type": alert_type,
                                "label": label,
                                "score": score,
                                "threshold": threshold,
                            }
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE telegram_score_alert_state
                            SET is_above = ?, score = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE symbol = ? AND alert_type = ?
                            """,
                            (int(is_above), score, symbol, alert_type),
                        )
    return list(alerts_by_symbol.values())


def mark_alert_delivered(db_path, symbol, alert_types):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executemany(
                """
                UPDATE telegram_score_alert_state
                SET is_above = 1, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ? AND alert_type = ?
                """,
                [(symbol, alert_type) for alert_type in alert_types],
            )


def format_alert(alert):
    lines = [
        "StockIQ score alert",
        f"{alert['company']} ({alert['symbol']})",
    ]
    for crossing in alert["crossings"]:
        lines.append(
            f"{crossing['label']}: {crossing['score']:.1f} "
            f"(crossed {crossing['threshold']})"
        )
    return "\n".join(lines)


async def deliver_alerts(token, chat_id, db_path, alerts):
    from telegram import Bot

    async with Bot(token=token) as bot:
        for alert in alerts:
            await bot.send_message(
                chat_id=chat_id,
                text=format_alert(alert),
            )
            mark_alert_delivered(
                db_path,
                alert["symbol"],
                [crossing["alert_type"] for crossing in alert["crossings"]],
            )


async def send_test_message(token, chat_id):
    from telegram import Bot

    async with Bot(token=token) as bot:
        await bot.send_message(
            chat_id=chat_id,
            text="StockIQ Telegram test: connection successful.",
        )


def main():
    parser = argparse.ArgumentParser(description="Send Telegram stock score alerts.")
    parser.add_argument("--db", default=DB_PATH, help="Path to the stocks SQLite database")
    parser.add_argument(
        "--test-message",
        action="store_true",
        help="Send a test message without reading or changing the database",
    )
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token and not chat_id:
        if args.test_message:
            raise RuntimeError(
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before sending a test."
            )
        print(
            "Telegram alerts skipped: set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in the GitHub Actions secrets."
        )
        return
    if not token or not chat_id:
        raise RuntimeError(
            "Both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be configured."
        )

    if args.test_message:
        asyncio.run(send_test_message(token, chat_id))
        print("Test Telegram message sent.")
        return

    engine = ScoringEngine(args.db)
    try:
        scores = engine.rank_all()
        companies = engine.conn.execute(
            "SELECT symbol, company FROM fundamentals"
        ).fetchall()
        company_by_symbol = {row["symbol"]: row["company"] for row in companies}
    finally:
        engine.close()

    scores["Company"] = scores["Symbol"].map(company_by_symbol).fillna(scores["Symbol"])
    alerts = prepare_score_alerts(args.db, scores)
    if not alerts:
        print("No new Master Score or Multibagger Score threshold crossings.")
        return

    asyncio.run(deliver_alerts(token, chat_id, args.db, alerts))
    print(f"Sent {len(alerts)} Telegram score alert(s).")


if __name__ == "__main__":
    main()
