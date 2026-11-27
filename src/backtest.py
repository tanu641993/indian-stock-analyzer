import argparse
import os
import sqlite3
import sys
from datetime import date

import pandas as pd
import yfinance as yf
from requests.exceptions import RequestException
from yfinance.exceptions import YFException

from scoring import ScoringEngine


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "stocks.db")
MAX_PRICE_EDGE_GAP_DAYS = 10


class BacktestEngine:
    def __init__(
        self,
        db_path=DB_PATH,
        scoring_engine=None,
        benchmark_ticker="NIFTYBEES.NS",
        benchmark_history=None,
    ):
        self.conn = sqlite3.connect(db_path)
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.benchmark_ticker = benchmark_ticker
        self.benchmark_history = benchmark_history

    def get_top_stocks(self, rebalance_year, top_n=10):
        cutoff_date = date(rebalance_year - 1, 12, 31).isoformat()
        try:
            snapshot_date = self.conn.execute(
                """
                SELECT MAX(snapshot_date)
                FROM fundamental_snapshots
                WHERE snapshot_date <= ?
                """,
                (cutoff_date,),
            ).fetchone()[0]
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise RuntimeError(
                    "No point-in-time snapshots exist yet. Run update_daily.py "
                    "to begin collecting them."
                ) from exc
            raise

        if snapshot_date is None:
            earliest_snapshot = self.conn.execute(
                "SELECT MIN(snapshot_date) FROM fundamental_snapshots"
            ).fetchone()[0]
            if earliest_snapshot is None:
                raise RuntimeError(
                    "No point-in-time snapshots exist yet. Run update_daily.py "
                    "to begin collecting them."
                )
            raise ValueError(
                f"No snapshot is available on or before {cutoff_date}; "
                f"the earliest recorded snapshot is {earliest_snapshot}."
            )

        snapshots = pd.read_sql_query(
            "SELECT * FROM fundamental_snapshots WHERE snapshot_date = ?",
            self.conn,
            params=(snapshot_date,),
        )
        rankings = self.scoring_engine.rank_fundamentals(snapshots)
        symbols = rankings["Symbol"].head(top_n).tolist()
        if not symbols:
            raise RuntimeError(
                f"The snapshot for {snapshot_date} produced no ranked stocks."
            )
        return snapshot_date, symbols

    def get_annual_stock_returns(self, symbols, holding_year):
        start_date = date(holding_year, 1, 1)
        end_date = date(holding_year + 1, 1, 1)
        placeholders = ",".join("?" for _ in symbols)
        prices = pd.read_sql_query(
            f"""
            SELECT symbol, substr(date, 1, 10) AS trade_date, close
            FROM price_history
            WHERE symbol IN ({placeholders})
              AND substr(date, 1, 10) >= ?
              AND substr(date, 1, 10) < ?
            ORDER BY symbol, trade_date
            """,
            self.conn,
            params=(*symbols, start_date.isoformat(), end_date.isoformat()),
        )
        if prices.empty:
            raise RuntimeError(
                f"No price history is available for the selected stocks in {holding_year}."
            )

        prices["trade_date"] = pd.to_datetime(prices["trade_date"], errors="coerce")
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["trade_date", "close"])

        returns = {}
        incomplete = []
        for symbol in symbols:
            stock_prices = prices.loc[prices["symbol"] == symbol]
            if len(stock_prices) < 2:
                incomplete.append(f"{symbol} (fewer than two prices)")
                continue

            first = stock_prices.iloc[0]
            last = stock_prices.iloc[-1]
            first_date = first["trade_date"].date()
            last_date = last["trade_date"].date()
            if (first_date - start_date).days > MAX_PRICE_EDGE_GAP_DAYS:
                incomplete.append(f"{symbol} (no price near start of {holding_year})")
            elif (end_date - last_date).days > MAX_PRICE_EDGE_GAP_DAYS:
                incomplete.append(f"{symbol} (no price near end of {holding_year})")
            elif first["close"] <= 0 or last["close"] <= 0:
                incomplete.append(f"{symbol} (invalid price)")
            else:
                returns[symbol] = last["close"] / first["close"] - 1

        if incomplete:
            raise RuntimeError(
                f"Incomplete price coverage for {holding_year}: "
                + ", ".join(incomplete)
                + ". No portfolio return was calculated."
            )
        return returns

    @staticmethod
    def normalize_price_series(prices):
        if isinstance(prices, pd.DataFrame):
            if "Close" not in prices:
                raise ValueError("Price history is missing a Close column.")
            closes = prices["Close"]
        else:
            closes = prices

        dates = pd.DatetimeIndex(pd.to_datetime(closes.index, errors="coerce"))
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        normalized = pd.Series(
            pd.to_numeric(closes.to_numpy(), errors="coerce"),
            index=dates,
        ).dropna()
        normalized = normalized[~normalized.index.isna()]
        return normalized[~normalized.index.duplicated(keep="last")].sort_index()

    def get_benchmark_history(self, start_year, end_year):
        if self.benchmark_history is not None:
            history = self.normalize_price_series(self.benchmark_history)
        else:
            try:
                response = yf.Ticker(self.benchmark_ticker).history(
                    start=date(start_year, 1, 1).isoformat(),
                    end=date(end_year + 1, 1, 1).isoformat(),
                    interval="1d",
                    auto_adjust=True,
                    timeout=20,
                )
            except (YFException, RequestException, TimeoutError) as exc:
                raise RuntimeError(
                    f"Could not download benchmark {self.benchmark_ticker}: {exc}"
                ) from exc
            if response.empty or "Close" not in response:
                raise RuntimeError(
                    f"No closing-price history was returned for benchmark "
                    f"{self.benchmark_ticker}."
                )
            history = self.normalize_price_series(response)

        if history.empty:
            raise RuntimeError(
                f"No closing-price history is available for benchmark "
                f"{self.benchmark_ticker}."
            )
        return history

    def get_annual_benchmark_return(self, history, holding_year):
        start_date = date(holding_year, 1, 1)
        end_date = date(holding_year + 1, 1, 1)
        period = history.loc[
            (history.index.date >= start_date)
            & (history.index.date < end_date)
        ]
        if len(period) < 2:
            raise RuntimeError(
                f"Incomplete {self.benchmark_ticker} price coverage in {holding_year}."
            )
        if (period.index[0].date() - start_date).days > MAX_PRICE_EDGE_GAP_DAYS:
            raise RuntimeError(
                f"No {self.benchmark_ticker} price near the start of {holding_year}."
            )
        if (end_date - period.index[-1].date()).days > MAX_PRICE_EDGE_GAP_DAYS:
            raise RuntimeError(
                f"No {self.benchmark_ticker} price near the end of {holding_year}."
            )
        if period.iloc[0] <= 0 or period.iloc[-1] <= 0:
            raise RuntimeError(
                f"Invalid {self.benchmark_ticker} price in {holding_year}."
            )
        return float(period.iloc[-1] / period.iloc[0] - 1)

    def run_backtest(
        self,
        start_year=2020,
        end_year=None,
        top_n=10,
        transaction_cost_bps=10,
    ):
        last_completed_year = date.today().year - 1
        if end_year is None:
            end_year = last_completed_year
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        if transaction_cost_bps < 0 or transaction_cost_bps > 1000:
            raise ValueError(
                "transaction_cost_bps must be between 0 and 1000."
            )
        if start_year > end_year:
            raise ValueError("start_year must be less than or equal to end_year.")
        if end_year > last_completed_year:
            raise ValueError(
                f"Only completed years can be tested; the latest completed year "
                f"is {last_completed_year}."
            )

        selections = []
        for holding_year in range(start_year, end_year + 1):
            snapshot_date, symbols = self.get_top_stocks(holding_year, top_n)
            selections.append((holding_year, snapshot_date, symbols))

        benchmark_history = self.get_benchmark_history(start_year, end_year)
        results = []
        previous_end_weights = {}
        transaction_cost_rate = transaction_cost_bps / 10000
        for year_index, (holding_year, snapshot_date, symbols) in enumerate(selections):
            stock_returns = self.get_annual_stock_returns(symbols, holding_year)
            gross_return = sum(stock_returns.values()) / len(stock_returns)
            target_weights = {symbol: 1 / len(symbols) for symbol in symbols}
            weight_symbols = set(previous_end_weights) | set(target_weights)
            turnover = sum(
                abs(
                    target_weights.get(symbol, 0)
                    - previous_end_weights.get(symbol, 0)
                )
                for symbol in weight_symbols
            )
            transaction_cost = transaction_cost_rate * turnover
            net_return = (1 - transaction_cost) * (1 + gross_return) - 1
            benchmark_gross_return = self.get_annual_benchmark_return(
                benchmark_history, holding_year
            )
            benchmark_transaction_cost = (
                transaction_cost_rate if year_index == 0 else 0
            )
            benchmark_return = (
                (1 - benchmark_transaction_cost) * (1 + benchmark_gross_return) - 1
            )
            excess_return = net_return - benchmark_return

            gross_growth = 1 + gross_return
            previous_end_weights = {
                symbol: target_weights[symbol]
                * (1 + stock_returns[symbol])
                / gross_growth
                for symbol in symbols
            }
            results.append(
                {
                    "year": holding_year,
                    "snapshot_date": snapshot_date,
                    "symbols": symbols,
                    "gross_return": gross_return,
                    "transaction_cost": transaction_cost,
                    "turnover": turnover,
                    "return": net_return,
                    "benchmark_gross_return": benchmark_gross_return,
                    "benchmark_transaction_cost": benchmark_transaction_cost,
                    "benchmark_return": benchmark_return,
                    "excess_return": excess_return,
                }
            )
            print(
                f"{holding_year}: net {net_return:+.2%} "
                f"(gross {gross_return:+.2%}; costs {transaction_cost:.2%}; "
                f"turnover {turnover:.2%}; {self.benchmark_ticker} net "
                f"{benchmark_return:+.2%}; excess {excess_return:+.2%}; "
                f"snapshot {snapshot_date}; {', '.join(symbols)})"
            )

        self.print_summary(results, self.benchmark_ticker, transaction_cost_bps)
        return results

    @staticmethod
    def print_summary(results, benchmark_ticker, transaction_cost_bps):
        equity = 1.0
        benchmark_equity = 1.0
        peak = equity
        benchmark_peak = benchmark_equity
        max_drawdown = 0.0
        benchmark_max_drawdown = 0.0
        for result in results:
            equity *= 1 + result["return"]
            benchmark_equity *= 1 + result["benchmark_return"]
            peak = max(peak, equity)
            benchmark_peak = max(benchmark_peak, benchmark_equity)
            max_drawdown = min(max_drawdown, equity / peak - 1)
            benchmark_max_drawdown = min(
                benchmark_max_drawdown,
                benchmark_equity / benchmark_peak - 1,
            )

        years = len(results)
        cagr = equity ** (1 / years) - 1
        benchmark_cagr = benchmark_equity ** (1 / years) - 1
        print("\nWalk-forward summary")
        print(f"Completed years: {years}")
        print(
            f"Portfolio net compounded return (after {transaction_cost_bps} bps "
            f"per traded notional): {equity - 1:+.2%}"
        )
        print(f"Portfolio net CAGR: {cagr:+.2%}")
        print(
            f"{benchmark_ticker} buy-and-hold compounded return / CAGR: "
            f"{benchmark_equity - 1:+.2%} / {benchmark_cagr:+.2%}"
        )
        print(
            f"Maximum drawdown (annual observations): portfolio {max_drawdown:.2%}; "
            f"benchmark {benchmark_max_drawdown:.2%}"
        )

    def close(self):
        self.conn.close()
        self.scoring_engine.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Backtest annual stock selections using dated fundamental snapshots."
    )
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--benchmark",
        default="NIFTYBEES.NS",
        help="Yahoo Finance benchmark ticker (default: NIFTYBEES.NS).",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=10,
        help="Estimated cost per traded notional in basis points (default: 10).",
    )
    args = parser.parse_args(argv)

    backtest = BacktestEngine(benchmark_ticker=args.benchmark)
    try:
        backtest.run_backtest(
            args.start_year,
            args.end_year,
            args.top_n,
            args.transaction_cost_bps,
        )
    except (RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"Backtest cannot run: {exc}", file=sys.stderr)
        return 1
    finally:
        backtest.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
