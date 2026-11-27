import os
import sqlite3
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")

FUNDAMENTAL_COLUMNS = (
    "company",
    "sector",
    "market_cap",
    "roe",
    "roce",
    "debt_to_equity",
    "pe",
    "pb",
    "rev_cagr_3y",
    "rev_cagr_5y",
    "profit_cagr_3y",
    "profit_cagr_5y",
    "eps_cagr_3y",
    "eps_cagr_5y",
    "margin_expansion",
    "roce_increasing",
    "fcf_positive_5y",
    "cfo_to_profit",
    "promoter_holding",
    "promoter_pledge",
    "share_dilution",
    "moat_roce_10y",
    "current_ratio",
    "interest_coverage",
    "operating_margin",
    "is_market_leader",
    "auditor_red_flag",
)

SNAPSHOT_COLUMN_DEFINITIONS = """
    snapshot_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    company TEXT,
    sector TEXT,
    market_cap REAL,
    roe REAL,
    roce REAL,
    debt_to_equity REAL,
    pe REAL,
    pb REAL,
    rev_cagr_3y REAL,
    rev_cagr_5y REAL,
    profit_cagr_3y REAL,
    profit_cagr_5y REAL,
    eps_cagr_3y REAL,
    eps_cagr_5y REAL,
    margin_expansion REAL,
    roce_increasing INTEGER,
    fcf_positive_5y INTEGER,
    cfo_to_profit REAL,
    promoter_holding REAL,
    promoter_pledge REAL,
    share_dilution REAL,
    moat_roce_10y INTEGER,
    current_ratio REAL,
    interest_coverage REAL,
    operating_margin REAL,
    is_market_leader INTEGER,
    auditor_red_flag INTEGER,
    fundamentals_updated_at TEXT,
    deep_fundamentals_updated_at TEXT,
    PRIMARY KEY (snapshot_date, symbol)
"""


def create_snapshot_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS fundamental_snapshots (
            {SNAPSHOT_COLUMN_DEFINITIONS}
        )
        """
    )
    existing_columns = {
        column[1]
        for column in conn.execute(
            "PRAGMA table_info(fundamental_snapshots)"
        ).fetchall()
    }
    if "deep_fundamentals_updated_at" not in existing_columns:
        conn.execute(
            "ALTER TABLE fundamental_snapshots "
            "ADD COLUMN deep_fundamentals_updated_at TEXT"
        )


def capture_snapshot(conn, snapshot_date=None):
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).date().isoformat()
    datetime.strptime(snapshot_date, "%Y-%m-%d")

    create_snapshot_table(conn)
    expected_symbols = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    if expected_symbols == 0:
        raise RuntimeError("Cannot snapshot fundamentals: stocks table is empty.")

    snapshot_columns = [
        "snapshot_date",
        "symbol",
        *FUNDAMENTAL_COLUMNS,
        "fundamentals_updated_at",
        "deep_fundamentals_updated_at",
    ]
    select_columns = ", ".join(f"f.{column}" for column in FUNDAMENTAL_COLUMNS)
    fundamental_columns = {
        column[1]
        for column in conn.execute("PRAGMA table_info(fundamentals)").fetchall()
    }
    deep_updated_at = (
        "f.deep_updated_at"
        if "deep_updated_at" in fundamental_columns
        else "NULL"
    )
    insert_sql = f"""
        INSERT OR REPLACE INTO fundamental_snapshots (
            {", ".join(snapshot_columns)}
        )
        SELECT ?, s.symbol, {select_columns}, f.updated_at, {deep_updated_at}
        FROM stocks AS s
        LEFT JOIN fundamentals AS f ON f.symbol = s.symbol
    """
    conn.execute(insert_sql, (snapshot_date,))
    snapshot_symbols = conn.execute(
        "SELECT COUNT(*) FROM fundamental_snapshots WHERE snapshot_date = ?",
        (snapshot_date,),
    ).fetchone()[0]
    if snapshot_symbols != expected_symbols:
        raise RuntimeError(
            f"Snapshot contains {snapshot_symbols} symbols; "
            f"expected {expected_symbols}."
        )

    conn.commit()
    return snapshot_symbols


def main():
    snapshot_date = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        count = capture_snapshot(conn, snapshot_date)
    print(f"Captured {count} point-in-time fundamental snapshots for {snapshot_date}.")


if __name__ == "__main__":
    main()
