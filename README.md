## Using StockIQ

Start the app from the repository folder with:

```powershell
streamlit run app.py
```

Use the sidebar pages as follows:

- **Find Stocks:** Search by company or symbol. Open “More filters and ranking
  options” only when needed. The default Master Investment Score is out of 100;
  other ranking models use different scales. Select a row's stock below the
  results to open Overview, Price chart, Peers, Financials and News.
- **Watchlist:** See recent stored price changes and configure price or P/E
  thresholds. These local thresholds are checked when the page loads.
- **Telegram score alerts:** The scheduled GitHub Actions update can notify you
  when a stock newly crosses a Master Score of 60 or a Multibagger Score of 90.
- **Market Context:** Switch between sector summaries and commodity/currency
  benchmarks. Commodity prices are global Yahoo Finance indicators, not Indian
  MCX quotes.
- **Portfolio Preview:** Identifies stock symbols in a CDSL PDF and summarizes
  their current scores. It does not parse quantities, cost basis, market value
  or profit/loss.

The app's score labels are screening heuristics, not personalized investment
advice. Check the stock's data status and company filings before relying on a
score. Headlines are displayed in India Standard Time; a headline list is not
an AI sentiment result until the local analysis is run.

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

The Find Stocks overview shows Yahoo Finance data refresh dates, missing key
fundamentals and stale-data warnings. Full financial refresh time is recorded
separately from daily valuation updates; legacy rows without a known refresh
time are intentionally shown as unknown.

The Watchlist page stores selected symbols and price/P-E thresholds in
the local, Git-ignored `database/user_state.db`, separate from market data.
Alerts are evaluated against the latest stored close and
valuation data when the page loads; stale inputs are not treated as clear
alerts. These local price/P-E thresholds are not sent automatically by GitHub
Actions. Screener, sector and watchlist tables can be downloaded as CSV.

## Telegram score alerts

To enable automated score-crossing alerts, create a Telegram bot, obtain its
bot token and your chat ID, then add them to the GitHub repository under
**Settings → Secrets and variables → Actions** as `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. Do not put either value in source code or commit them.
The daily workflow sends a message only when a stock moves from below to at or
above Master Score 60 or Multibagger Score 90. Its first run records current
scores as a baseline instead of sending a burst for stocks that already meet
the thresholds. Existing scores are also baselined if a threshold changes.
A later drop below and recross can alert again. If Telegram delivery fails,
the workflow reports a warning and leaves that crossing eligible for a retry
on the next run.

To test Telegram delivery from PowerShell without changing the database, run
this from the repository folder. Enter the replacement bot token at the
masked prompt and your chat ID at the next prompt:

```powershell
$secureToken = Read-Host "Telegram bot token" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $env:TELEGRAM_BOT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    $env:TELEGRAM_CHAT_ID = Read-Host "Telegram chat ID"
    python src\telegram_alerts.py --test-message
}
finally {
    Remove-Item Env:\TELEGRAM_BOT_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:\TELEGRAM_CHAT_ID -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    $secureToken.Dispose()
}
```

The test command sends one confirmation message and does not read or update the
market database. GitHub Actions secrets are not automatically available on
your computer, so enter the replacement token locally when prompted; do not
save it in the script or paste it into chat.

The commodity dashboard compares Yahoo Finance global futures benchmarks with
USD/INR context. These are not Indian MCX quotes, and the page explains common
Indian-sector cost exposures without presenting them as buy/sell signals.