from contextlib import closing
import sqlite3

import pandas as pd


def ensure_watchlist_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            price_above REAL,
            price_below REAL,
            pe_above REAL,
            pe_below REAL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_watchlist_entries(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            ensure_watchlist_schema(conn)
        return pd.read_sql_query(
            "SELECT * FROM watchlist ORDER BY added_at, symbol",
            conn,
        )


def add_watchlist_symbol(db_path, symbol):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            ensure_watchlist_schema(conn)
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (symbol) VALUES (?)",
                (symbol,),
            )


def save_watchlist_alerts(db_path, symbol, price_above, price_below, pe_above, pe_below):
    if price_above > 0 and price_below > 0 and price_above <= price_below:
        raise ValueError("Price-above threshold must exceed price-below threshold.")
    if pe_above > 0 and pe_below > 0 and pe_above <= pe_below:
        raise ValueError("P/E-above threshold must exceed P/E-below threshold.")

    thresholds = [
        value if value > 0 else None
        for value in (price_above, price_below, pe_above, pe_below)
    ]
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                UPDATE watchlist
                SET price_above = ?, price_below = ?, pe_above = ?, pe_below = ?
                WHERE symbol = ?
                """,
                (*thresholds, symbol),
            )


def remove_watchlist_symbol(db_path, symbol):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))


def get_latest_watchlist_prices(db_path, symbols):
    if not symbols:
        return {}
    placeholders = ",".join("?" for _ in symbols)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_history_symbol_date
            ON price_history (symbol, date)
            """
        )
        prices = pd.read_sql_query(
            f"""
            SELECT symbol, date, close
            FROM (
                SELECT symbol, date, close,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol ORDER BY date DESC
                       ) AS row_number
                FROM price_history
                WHERE symbol IN ({placeholders})
            )
            WHERE row_number <= 2
            ORDER BY symbol, date DESC
            """,
            conn,
            params=tuple(symbols),
        )
    if prices.empty:
        return {}
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["close"]).groupby("symbol", sort=False).head(2)
    return {
        symbol: group.reset_index(drop=True)
        for symbol, group in prices.groupby("symbol", sort=False)
    }


def evaluate_watchlist_alerts(
    entry,
    current_price,
    pe,
    price_age_days,
    fundamentals_age_days,
    stale_after_days,
):
    triggers = []
    unevaluated = []
    configured = False

    price_is_fresh = (
        price_age_days is not None and price_age_days <= stale_after_days
    )
    fundamentals_are_fresh = (
        fundamentals_age_days is not None
        and fundamentals_age_days <= stale_after_days
    )
    for column, operator, predicate, label in (
        ("price_above", "above", lambda price, limit: price >= limit, "Price"),
        ("price_below", "below", lambda price, limit: price <= limit, "Price"),
    ):
        threshold = entry[column]
        if pd.isna(threshold) or threshold <= 0:
            continue
        configured = True
        if not price_is_fresh:
            unevaluated.append("price data stale or unavailable")
        elif pd.notna(current_price) and predicate(current_price, threshold):
            triggers.append(f"{label} {operator} {threshold:,.2f}")

    for column, operator, predicate in (
        ("pe_above", "above", lambda value, limit: value >= limit),
        ("pe_below", "below", lambda value, limit: value <= limit),
    ):
        threshold = entry[column]
        if pd.isna(threshold) or threshold <= 0:
            continue
        configured = True
        if not fundamentals_are_fresh:
            unevaluated.append("P/E data stale or unavailable")
        elif pd.isna(pe) or pe <= 0:
            unevaluated.append("P/E unavailable or non-positive")
        elif predicate(pe, threshold):
            triggers.append(f"P/E {operator} {threshold:g}")

    if triggers:
        status = "TRIGGERED: " + "; ".join(triggers)
        if unevaluated:
            status += " (also " + "; ".join(sorted(set(unevaluated))) + ")"
    elif unevaluated:
        status = "Not evaluated: " + "; ".join(sorted(set(unevaluated)))
    elif price_age_days is None or price_age_days > stale_after_days:
        status = "Price data stale or unavailable"
    elif configured:
        status = "Clear"
    else:
        status = "No thresholds set"
    return status
