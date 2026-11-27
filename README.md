## Walk-forward backtest

The daily updater now stores a dated copy of each stock's fundamentals after
the data and risk flags are refreshed:

```powershell
python src\update_daily.py
```

Run the annual equal-weight backtest with:

```powershell
python src\backtest.py --start-year 2020 --top-n 10 `
  --benchmark NIFTYBEES.NS --transaction-cost-bps 10
```

For each holding year, the script ranks stocks using the latest fundamental
snapshot on or before December 31 of the previous year. It then calculates
each selected stock's return from the first to last available adjusted close
in the holding year. Incomplete price coverage is reported as an error rather
than silently dropping that holding.

The default benchmark is the NIFTYBEES ETF, using adjusted closing prices. The
portfolio applies the configured cost (10 basis points by default) to initial
buys and annual rebalance turnover; the buy-and-hold benchmark is charged for
its initial purchase only. Brokerage, taxes, slippage and final liquidation are
not modeled, so treat costs as an estimate rather than a broker-specific result.

The existing database has no historical fundamental snapshots, so it cannot
produce a valid 2020 walk-forward result. Daily collection starts when the
updater first runs with this change; it does not reconstruct older fundamentals.
As a result, historical results are only possible for years with a saved
pre-rebalance snapshot. The database also has no historical stock-universe
membership, so snapshots reflect the universe present in `stocks` on each
capture date.

## Data quality, watchlist and exports

The Stock Detail page shows Yahoo Finance data refresh dates, missing key
fundamentals and stale-data warnings. Full financial refresh time is recorded
separately from daily valuation updates; legacy rows without a known refresh
time are intentionally shown as unknown.

The Watchlist & Alerts page stores selected symbols and price/P-E thresholds in
the local, Git-ignored `database/user_state.db`, separate from market data.
Alerts are evaluated against the latest stored close and
valuation data when the page loads; stale inputs are not treated as clear
alerts, and no email or push notifications are sent. Screener, sector and
watchlist tables can be downloaded as CSV.

The commodity dashboard compares Yahoo Finance global futures benchmarks with
USD/INR context. These are not Indian MCX quotes, and the page explains common
Indian-sector cost exposures without presenting them as buy/sell signals.