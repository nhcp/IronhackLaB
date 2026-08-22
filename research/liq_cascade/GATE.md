# Liquidation Cascade Mean Reversion — Pre-Registered Gate
## Registered: 2026-08-22 | Status: COLLECTING — Fix-10 override granted 2026-08-22; backtest gate on 2026-11-20

This document is append-only after registration. No results section exists yet.
Fix-10 override granted 2026-08-22 (rules-based strategy, not ML-dependent — see
RESEARCH.md Fix-10 Override Log for full rationale). Prospective data collection
running from 2026-08-22. Backtest not permitted before 2026-11-20 and event count
thresholds — see RESEARCH.md Re-Check Gate section.

---

## Research Context

**Hypothesis:** Large forced liquidation events on Binance USDT-M perpetual futures
create temporary, non-informational price overshoots. Price reverts once the mechanical
selling (or buying) pressure from the exchange's risk engine exhausts. The mechanism is
structural: it requires leverage, margin engines, and liquidation clustering — not a generic
mean-reversion pattern expressible with price indicators alone.

**Symbol scope:** BTC/USDT and ETH/USDT perpetuals (Binance USDS-M Futures).
Both must pass for the strategy to proceed. Single-symbol pass = not pursued.

**Mechanism:** Exchange risk engine closes leveraged positions at market when margin
falls below maintenance threshold. Forced market orders in concentrated clusters
overshoot fundamental value because they are non-price-sensitive (the engine
executes regardless of the resulting price).

**Mechanism is distinct from KILLed leveraged-token rebalancing mechanism:**
Leveraged tokens: daily NAV rebalancing by the issuer (predictable timing, known size formula).
Liquidation cascades: random timing (triggered by price), unknown size until observed,
caused by individual trader margin breaches rather than issuer portfolio management.

---

## Data & Methodology (Fixed Pre-Run)

- **Venue:** Binance USDS-M Futures (perps)
- **Symbols:** BTCUSDT, ETHUSDT
- **Data source:** [TBD — user must decide: Tardis.dev / CoinGlass / prospective WebSocket]
  - Tardis.dev: `forceOrder` channel, available from 2019-09-08
  - CoinGlass API: hourly aggregate, available from ~2019, $29/month
  - Prospective: WebSocket listener from approval date onward
- **Event definition:** sum of `forceOrder` qty (in USD notional) on one side
  within a rolling 5-minute window ≥ 95th percentile of all 5-min windows in sample.
  (Threshold is computed from the first half of the sample — IS period — and applied
  fixed to the OOS period.)
- **Entry:** LONG if event is long liquidation (engine sold = price fell);
  SHORT if event is short liquidation (engine bought = price rose).
  Entry at the close of the 5-min bar containing the cascade trigger.
- **Exit — profit target:** Price moves ≥ 50% of the initial cascade bar's range
  in the reversion direction. Exit at that price (limit order assumed; taker fee applied
  because cascade environment has wide spreads — conservative).
- **Exit — time limit:** 30 minutes from entry. Exit at market (taker fee).
- **Costs:** 0.10% round-trip (0.05% × 2, both legs taker). Applied to all fills.
- **Evaluation window:** Full available sample, split 50/50 IS/OOS by calendar.
  If Tardis history from 2019: IS = 2019-09-08 to ~2022-12-31, OOS = 2023-01-01 onward.
  If CoinGlass/prospective: define IS/OOS at time of data decision.
- **Primary parameters:** 95th pct threshold, immediate entry, 50% profit target, 30min limit.
  These are LOCKED. No post-hoc adjustment permitted.

---

## Gate Criteria (Pre-Registered)

### G1: Event Count (Data Viability)
- **Threshold:** ≥ 30 qualifying cascade events per year in the sample
- **Rationale:** Fewer than 30 events/year → insufficient statistical power and the
  strategy is not meaningfully different from "hold cash."
- **Evaluated on:** OOS period, annualized

### G2: Mean Net Return Per Event
- **Threshold:** Mean net return > 0.10% per trade (after 0.10% RT fee)
- **Rationale:** Must clear fees with margin. Below 0.10% net, the edge is too thin
  to survive any real-world degradation (slippage, queue position, connection latency
  during cascade conditions — which are the worst possible execution environment).
- **Evaluated on:** OOS event population

### G3: Win Rate
- **Threshold:** Win rate ≥ 55% (price reaches 50% reversion before time limit)
- **Rationale:** A mean-reversion mechanism should succeed more than half the time.
  Below 55%, the positive expectation (if any) is entirely driven by outlier events,
  making the result fragile.
- **Evaluated on:** OOS event population

### G4: Risk-Adjusted Return (Sharpe)
- **Threshold:** Sharpe ≥ 0.5 (per-event returns, annualized)
- **Rationale:** Minimum viability bar for an event-driven strategy with realistic
  execution costs. Below 0.5, the strategy has insufficient signal-to-noise to
  distinguish from luck in a multi-year sample.
- **Evaluated on:** OOS per-event return series

### G5: Temporal Stability (H1/H2 Split)
- **Threshold:** OOS H2 Sharpe ≥ 0.6 × OOS H1 Sharpe
- **Rationale:** If the mechanism is structural (not regime-specific), performance should
  not collapse in the second half of the OOS window. A 40% tolerance allows for
  normal variation; collapse beyond that flags a decaying or vanishing edge.
- **Evaluated on:** First and second halves of OOS period

### G6: Negative Control Battery (All Must Fail)
- **Threshold:** All 5 negative controls (NC-1 through NC-5) must show Sharpe < 0.2
  or Win Rate < 50% on the same OOS period.
- **Rationale:** If the controls match the strategy, the identified edge is not specific
  to the liquidation mechanism — it is generic mean-reversion or time-of-day bias.
- **Controls:** Defined in RESEARCH.md §Negative Control Battery and reproduced below.

---

## Negative Control Battery (Pre-Registered)

Each control is run on the SAME symbols and SAME OOS period as the primary strategy.
Results are recorded alongside primary results. Controls that beat the primary raise
a red flag requiring investigation before any override of negative finding.

### NC-1: Random Time Entry (No Liquidation Event)
- **Method:** Identify the exact times of observed cascade events. For each event, find
  a matched day with no qualifying liquidation event at the same time-of-day ±15 min.
  Execute the same entry/exit logic at that matched time.
- **What it tests:** Whether time-of-day (not the liquidation event) drives the return.
- **Expected result:** Sharpe < 0.2, Win Rate < 52%

### NC-2: Shuffled Liquidation Timestamps
- **Method:** Keep all event sizes fixed. Randomly permute event timestamps within
  the same calendar month (so monthly seasonality is preserved). Apply the same
  entry/exit logic at the shuffled timestamps.
- **What it tests:** Whether the return depends on when the liquidation happens (not
  just that there was a liquidation). If permuting times destroys the edge, the
  signal is structurally timing-dependent.
- **Expected result:** Sharpe ≈ 0 or negative after shuffling

### NC-3: Trend-Following Version (Same Direction as Cascade)
- **Method:** Enter in the SAME direction as the cascade flow, not against it.
  After a long liquidation event (price fell), enter SHORT. After a short liquidation
  event (price rose), enter LONG.
- **What it tests:** Whether a trend-following interpretation of the same events is
  better or worse. If NC-3 outperforms the primary, the edge is momentum, not
  mean-reversion.
- **Expected result:** Sharpe significantly below primary; likely negative (because
  entry is at maximum overshoot)

### NC-4: Spot-Only Pair (No Leveraged Mechanism)
- **Method:** Apply the same price-pattern trigger (the cascade bar pattern: rapid
  directional move of similar magnitude to observed cascade events) on a crypto asset
  that does NOT have a meaningful liquid perpetual market and therefore no significant
  liquidation cascade mechanism. Candidate: a small-cap coin traded spot-only.
- **What it tests:** Whether the price pattern alone (sharp move then reversal) drives
  the signal without requiring the leverage/liquidation mechanism.
- **Expected result:** No meaningful edge. If NC-4 shows similar Sharpe to primary,
  the liquidation mechanism is not required — we are just backtesting a generic
  sharp-reversal pattern.

### NC-5: Below-Threshold Events Only
- **Method:** Same strategy applied only when the 5-min liquidation volume is BELOW
  the 10th percentile (tiny, non-cascade events).
- **What it tests:** Whether event size matters. If small events produce the same
  edge, the cascade threshold is irrelevant — any liquidation event triggers the pattern.
- **Expected result:** No edge. Confirms that the threshold (defining "cascade") is
  mechanistically necessary.

---

## Pass Rule

- **Primary must pass:** G1, G2, G3, G4, AND G5 on BOTH BTCUSDT and ETHUSDT.
- **NC battery must fail:** NC-1 through NC-5 each show Sharpe < 0.2.
- **Single-symbol pass:** Not pursued. Flagged as data mining.
- **NC battery partial pass:** Any NC-control with Sharpe > 0.3 requires explicit
  investigation before a "proceed" verdict is issued.

---

## Disqualifying Conditions (Override Any Pass)

1. If execution during a real cascade event is infeasible (latency, API limits, or
   spread widens to > 0.50% during the cascade): strategy is operationally unviable.
   Must be assessed before paper trade.
2. If the qualifying event frequency drops below 15 events/year in the most recent
   12 months of OOS data: edge may have been arbitraged away by other traders.
   Do not proceed regardless of historical backtest results.
3. If NC-3 (trend-following version) outperforms the primary strategy: mechanism
   diagnosis is incorrect. Kill this thread; the signal (if real) is momentum, not
   mean-reversion around cascades.

---

## Results — [NOT YET RUN]

Fix-10 suspension active as of 2026-08-22. No backtest has been executed.
Results to be recorded here after explicit user override and execution.

| Criterion | Threshold | BTCUSDT | ETHUSDT | Verdict |
|---|---|---|---|---|
| G1: Event count/yr | ≥ 30 | — | — | PENDING |
| G2: Mean net return | > 0.10% | — | — | PENDING |
| G3: Win rate | ≥ 55% | — | — | PENDING |
| G4: Sharpe | ≥ 0.5 | — | — | PENDING |
| G5: H1/H2 split | H2 ≥ 0.6×H1 | — | — | PENDING |
| G6: NC battery | All Sharpe < 0.2 | — | — | PENDING |
| **OVERALL** | All 6 pass, both syms | — | — | **PENDING** |

### NC Battery Results — [NOT YET RUN]

| Control | Sharpe | Win Rate | Verdict |
|---|---|---|---|
| NC-1: Random time | — | — | PENDING |
| NC-2: Shuffled timestamps | — | — | PENDING |
| NC-3: Trend-following | — | — | PENDING |
| NC-4: Spot-only proxy | — | — | PENDING |
| NC-5: Below-threshold events | — | — | PENDING |
