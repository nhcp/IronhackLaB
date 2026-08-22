# liq_cascade / data

Prospective collection from Binance USDS-M Futures `!forceOrder@arr` WebSocket stream.
Collection started: 2026-08-22.

## Files

| File | Contents |
|---|---|
| `events_BTCUSDT.csv` | One row per forceOrder event for BTCUSDT |
| `events_ETHUSDT.csv` | One row per forceOrder event for ETHUSDT |
| `collector.log` | Collector startup, reconnect, and heartbeat events |

## Column definitions

| Column | Type | Notes |
|---|---|---|
| `event_time_ms` | int | Binance-timestamped event receipt (ms since epoch) |
| `trade_time_ms` | int | Binance-reported trade execution time (ms since epoch) |
| `symbol` | str | BTCUSDT or ETHUSDT |
| `side` | str | SELL = long-side liquidation (forced sell); BUY = short-side (forced buy) |
| `order_price` | float | Limit price the liquidation engine posted |
| `avg_fill_price` | float | Actual average fill price (ap field); use this for notional |
| `orig_qty` | float | Original order quantity in base asset |
| `fill_qty` | float | Quantity actually filled (z or l field) |
| `notional_usd` | float | fill_qty × avg_fill_price |
| `status` | str | FILLED or PARTIALLY_FILLED |
| `collected_at_utc` | str | ISO 8601 UTC timestamp when row was written locally |

## Stream behaviour note

Binance pushes **only the largest single liquidation order within each 1000ms window**
per symbol. A multi-position cascade within one second appears as a single high-notional
event. This is the correct unit for identifying cascade events — the gate threshold
(95th percentile of 5-min aggregated notional) is defined over 5-minute bins of the
raw event data.

## Re-check gate

Backtest can run when:
- Date >= 2026-11-20 (90 days from collection start), AND
- BTCUSDT has >= 30 qualifying cascade events at the preliminary $10M/5min threshold, AND
- ETHUSDT has >= 20 qualifying cascade events at the same threshold.

The 95th-percentile threshold used in the actual backtest is computed from the first
60 days of the sample and applied fixed to days 61-90 as the OOS window.

## What NOT to do with this data

- Do not run a backtest until the re-check date thresholds are met.
- Do not use this data to inform any live or paper trade position.
- Do not retrain any ML model with this data (Fix-10 suspension in effect for ML).
