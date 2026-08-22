# Liquidation Cascade Mean Reversion — Research Thread
## Pre-registered: 2026-08-22 | Status: ACTIVE — Fix-10 override granted 2026-08-22

---

## Mechanism Definition

**Hypothesis:** Large forced liquidations of leveraged positions on perpetual futures markets
create temporary, non-informational price overshoots. The flow is mechanical (margin engine
closes at market regardless of price), not informed (the forced counterparty has no view on
fair value). Price reverts once the liquidation pressure exhausts.

### Mechanism Chain

```
Price moves to threshold
  → Liquidation engine breaches maintenance margin on a cluster of positions
  → Engine sends market orders (sells for long liquidations, buys for short liquidations)
  → Concentrated market-order flow amplifies the initial move
  → Overshoot beyond fundamental value
  → Buying (or selling) interest absorbs exhausted flow
  → Price reverts toward pre-cascade level
```

**Why it is non-informational:** The forced seller/buyer did not choose this price. The
liquidation engine has no view on fair value — it closes positions to protect the exchange's
insurance fund. This is distinct from a large holder deliberately selling at these prices
(which would be informational).

**What defines "large":** A cluster of liquidations large enough to move spot price
meaningfully. Threshold definition is part of the pre-registered gate (see GATE.md).
Candidates: $5M+ BTC-equivalent liquidated in a 5-minute window, or the 95th percentile
of 5-minute liquidation volumes over the sample period.

---

## Distinction from Killed Mechanism: Leveraged Token Rebalancing

| Dimension | Leveraged Token Rebalancing (KILLED) | Liquidation Cascade (THIS) |
|---|---|---|
| Who triggers flow | Token issuer (Binance, FTX etc.) | Exchange risk/margin engine |
| Trigger condition | Daily NAV drift → rebalance to restore 3× lever | Individual trader's margin < maintenance margin |
| Timing | Predictable: daily close, known formula | Random: whenever price hits a position's liq price |
| Direction | Predictable: same as daily return | Depends on whether longs or shorts are underwater |
| Size | Moderate, proportional to AUM drift | Highly variable: small trickle to cascade |
| Information content | Zero (issuer acts mechanically at scheduled time) | Zero (engine acts mechanically to cover exposure) |
| Observable data | Token nav/AUM changes (published) | forceOrder feed (exchange API, see below) |

---

## Data Source Assessment

**Required:** Time-stamped individual liquidation events with size, side (long/short),
and symbol. Aggregated hourly volumes can proxy for a weaker test; event-level data is
preferred to define cascade threshold precisely.

### Source 1: Binance REST API — `/fapi/v1/allForceOrders`

- **Content:** Individual forceOrder records (symbol, side, qty, price, time)
- **Lookback via REST:** ~7 days maximum. NOT paginated for historical queries beyond
  the most recent 1000 records. **VERDICT: Insufficient for backtesting. Real-time only.**
- **Source:** Binance developer forum confirms this limitation.

### Source 2: Binance Public Data Portal — data.binance.vision

- **Content:** klines, aggTrades, trades, bookTicker — for spot and futures
- **forceOrder data:** NOT included in the public download portal.
  **VERDICT: Confirmed unavailable.** (dev.binance.vision community thread confirms.)
- **Source:** https://dev.binance.vision/t/trying-to-understand-binance-historical-liquidation-snapshots/22392

### Source 3: Tardis.dev — Paid Historical Tick Data

- **Content:** Full tick-level `forceOrder` channel replayed from the original Binance
  WebSocket stream.
- **Binance USDS-M Futures (BTCUSDT, ETHUSDT etc.):** Available from approximately
  **2019-09-08** (≈ 7 years of history as of 2026).
- **Bybit Derivatives:** Available from **2020-11-03** (Bybit's `liquidation` channel).
- **Format:** Per-message CSV or real-time replay via API.
- **Cost:** Paid subscription. Individual dataset access (pay-per-download) also available.
  No free tier for historical data; free tier is real-time streaming only.
- **VERDICT: Best available source for rigorous backtest. Cost is the constraint.**
- **Source:** https://docs.tardis.dev/historical-data-details/binance-futures

### Source 4: CoinGlass API — Aggregated Liquidation History

- **Content:** Hourly/daily long and short liquidation volumes per exchange and per symbol.
  Aggregated — NOT individual events.
- **History:** ~2019+ (multi-year)
- **Cost:** No free tier. Hobbyist plan $29/month.
- **Signal limitation:** Hourly buckets lose the within-hour cascade event structure.
  A 5-minute cascade that drove $50M in liquidations appears as one hourly observation
  alongside other quieter periods. Threshold events cannot be precisely identified without
  the sub-hourly event stream.
- **Usable for:** Approximate test using hourly-aggregated signal (e.g., "any hour with
  liquidations > Nth percentile"). Weaker than event-level but possible.
- **VERDICT: Acceptable weak proxy if Tardis is not approved. Not ideal.**
- **Source:** https://docs.coinglass.com/reference/liquidation-history

### Source 5: Prospective WebSocket Collection

- **Method:** Run a Binance USDS-M forceOrder WebSocket listener, store to CSV, backtest
  after 90+ days.
- **Cost:** Zero
- **Limitation:** No historical training data. First backtest possible only after ~90 days
  of collection. Cannot test 2018 bear, 2020 COVID crash, 2022 LUNA/3AC cascades.
- **VERDICT: Viable only if cost is the binding constraint. Results will be limited by
  short sample and absence of stress-period data.**

### Data Source Summary

| Source | History | Granularity | Cost | Verdict |
|---|---|---|---|---|
| Binance REST `/allForceOrders` | ~7 days | Individual event | Free | Insufficient |
| data.binance.vision | N/A | Not available | Free | Unavailable |
| Tardis.dev | 2019-09-08 → | Individual event (tick) | Paid | **Best** |
| CoinGlass API | ~2019 → | Hourly aggregate | $29/month | Acceptable proxy |
| Prospective WebSocket | 0 now, grows | Individual event | Free | Viable but slow |

**Data decision required before any code is written.** See bottom of this document.

---

## Candidate Symbols

BTC/USDT perp and ETH/USDT perp on Binance (or Bybit). Rationale:
- Largest open interest → largest individual liquidation events
- Most liquid underlying → reversion signal less contaminated by spread
- Highest frequency of large cascade events (multiple per month during volatile regimes)
- Both venues have multi-year forceOrder feed history on Tardis

Secondary candidates (lower priority): SOL/USDT, BNB/USDT.
Multi-symbol pass rule: Strategy must work on BOTH BTC and ETH to proceed. Single-pair
pass = data mining.

---

## Strategy Design (Pre-Registered)

### Entry Signal

```
LONG entry (fade long liquidation cascade):
  When: sum(forceOrder.qty, side=SELL, last 5 minutes) ≥ threshold_long
  → price has fallen due to forced long closures
  → enter LONG at close of the 5-min bar containing the trigger
  → exit: either (a) price recovers X% above cascade low, or (b) time limit T

SHORT entry (fade short liquidation cascade):
  When: sum(forceOrder.qty, side=BUY, last 5 minutes) ≥ threshold_short
  → price has risen due to forced short closures
  → enter SHORT at close of the 5-min bar containing the trigger
  → exit: either (a) price drops X% below cascade high, or (b) time limit T
```

### Parameters (to sweep during pre-registered backtest)

| Parameter | Candidate Range | Primary |
|---|---|---|
| Event threshold | 90th / 95th / 99th percentile of 5-min liq vol | 95th pct |
| Entry timing | Immediate (bar close) / +1 bar / +2 bars | Immediate |
| Profit target | 30% / 50% / 70% of initial cascade move | 50% |
| Time limit | 15min / 30min / 60min | 30min |

Primary parameters are locked before the data is loaded. Sweeps are for robustness
reporting only — primary result is evaluated at primary parameter set.

### Costs

Binance USDT-M perp fees (market order): 0.05% taker per side = 0.10% round-trip.
Every simulated entry and exit uses the taker fee (cascade trades are urgent; we take
liquidity on both legs). No maker fee credit is assumed.

---

## Pre-Registered Gate

**See GATE.md for the formal gate document.**

Summary of required criteria:
- G1: Event count ≥ 30 qualifying cascade events per year (viability floor)
- G2: Mean net return per event > 0.10% (clears 0.10% RT fee with margin)
- G3: Win rate (price reverts before time limit) ≥ 55%
- G4: Sharpe (per-event returns) ≥ 0.5
- G5: H1/H2 Sharpe split — H2 Sharpe ≥ 0.6 × H1 Sharpe (no second-half collapse)
- G6: NC battery all FAIL (see GATE.md)

Pass rule: G1–G5 must pass on BOTH BTC and ETH. NC battery must all FAIL.

---

## Negative Control Battery (Pre-Registered)

All five controls must show significantly lower performance than the primary strategy.
If any control matches or exceeds the primary, the primary result is classified as
data-mining or a generic signal unrelated to the liquidation mechanism.

| Control | Description | Expected outcome |
|---|---|---|
| NC-1 (Random time entry) | Enter at same times-of-day as observed cascade events, but on days with NO qualifying liquidation event | Negative or flat expected return — liquidation events are the signal, not time-of-day |
| NC-2 (Shuffled timestamps) | Same strategy applied but liquidation event timestamps randomly permuted within calendar month | Performance collapse — signal timing is structural, not spurious correlation |
| NC-3 (Trend-following version) | Enter in the SAME direction as the cascade (sell after long liquidations, buy after short) | Should underperform — if trend-following wins, it is directional momentum, not cascade reversion |
| NC-4 (Spot-only pair without perps) | Apply the same price-pattern filter on a coin with no liquid perp market and therefore no liquidation mechanism | Flat or negative — the effect should require the leverage mechanism to exist |
| NC-5 (Sized by small events only) | Same strategy triggered only on below-threshold liquidation events (< 10th percentile) | Flat or negative — the cascade size must matter for the mechanism to hold |

---

## Fix-10 Suspension Status and Override Log

### Suspension (still active for ML families)

Source: `FlinkTrade/docs/roadmap.md` line 698 (dated 2026-07-27):
> "Research program suspended. No new strategy families will be tested until the ML label
> pipeline and locked holdout partition are rebuilt. Fix 10 retraining (P2a) is next —
> 30 days of clean data under the June 14 fixes have been collected and the 25/25/50
> label distribution is ready, pending explicit approval per CLAUDE.md Fix 10 gate."

Source: `FlinkTrade/CLAUDE.md`, Fix 10 section:
> "DO NOT RETRAIN UNTIL APPROVED"

No approval has been logged anywhere in the research record as of 2026-08-22.
The suspension remains active for ML-label-dependent families.

### One-off override granted: 2026-08-22

**Date:** 2026-08-22  
**Granted by:** User (explicit instruction, this session)  
**Scope:** This gate only — liq_cascade prospective data collection and eventual
backtest. Not a general resumption of the suspended research program.

**Auditable exception rationale:**  
Fix-10 is specifically about the ML label pipeline (BUY/SELL/HOLD distribution,
retrain.py, S7/S9 model quality). It blocks new strategy families that depend on
the same ML training infrastructure.

The liquidation cascade strategy is **mechanically rules-based**:
- Signal: aggregated notional from Binance `forceOrder` WebSocket events
- Entry/exit: threshold-crossing and time-limit rules, no model inference
- No call to retrain.py, ml_model.pkl, or any FlinkTrade ML component
- Does not share feature pipeline or label logic with any FlinkTrade strategy

The suspension's stated objective (prevent new families from compounding the ML
pipeline's known label-distribution flaw) is not implicated. The override is a
one-off exception on that basis — analogous to prior overrides for leveraged-token
rebalancing and non-naive VRP, which were also rules-based mechanisms exempt from
the ML-specific ban.

**What this override authorises:**
- Prospective data collection from Binance forceOrder stream (no paid data)
- Pre-registration of gate and NC battery (already complete — see GATE.md)
- Backtest execution after re-check date (2026-11-20) or event count threshold

**What this override does NOT authorise:**
- Live or paper trading
- Capital allocation of any kind
- Lifting the Fix-10 suspension for any other family
- Running retrain.py or modifying FlinkTrade ML infrastructure

---

## Data Decision Checkpoint

Before any code is written, the user must decide:

**Option A:** Tardis.dev paid access
- Pros: Full event-level history from 2019, covers multiple market regimes (COVID, LUNA,
  FTX, 2024 ETF run, 2025/2026 corrections). Most rigorous.
- Cons: Cost (subscription or per-download pricing; check current rates).

**Option B:** CoinGlass $29/month
- Pros: Affordable, multi-year history, immediate access.
- Cons: Hourly aggregates only. Cascade threshold must be defined as "hour with top-N%
  aggregate liquidation volume" rather than a true event. Weaker test of the mechanism.

**Option C:** Prospective WebSocket collection
- Pros: Free, event-level granularity.
- Cons: 90-day lead time before first backtest. No stress-period history.

**Decision (2026-08-22):** Option C — Prospective WebSocket collection.
Tardis.dev and CoinGlass are explicitly out of scope.

---

## Collection Status

**Started:** 2026-08-22  
**Script:** `src/collect_liquidations.py`  
**Data:** `data/events_BTCUSDT.csv`, `data/events_ETHUSDT.csv`  
**Stream:** `wss://fstream.binance.com/ws/!forceOrder@arr` (Binance USDS-M Futures)  
**Process:** Background via `nohup`; `@reboot` cron entry for persistence.

Binance pushes the largest single liquidation order per 1000ms per symbol.
A large cascade within one second appears as one high-notional event row.

---

## Re-Check Gate (Backtest Unlock Criteria)

The backtest may NOT be run before ALL of the following are true:

| Criterion | Threshold | Rationale |
|---|---|---|
| Date | >= 2026-11-20 | 90 calendar days from collection start |
| BTCUSDT events | >= 30 rows where notional_usd >= $10M in any 5-min bin | Preliminary power floor — ensures the 95th-pct threshold will yield enough signal events |
| ETHUSDT events | >= 20 rows where notional_usd >= $5M in any 5-min bin | Same for ETH (smaller market, lower threshold) |

**IS/OOS split:** First 60 days = IS (compute 95th-percentile threshold). Last 30 days = OOS
(apply fixed threshold, evaluate gate). The OOS window is only 30 days — this is a
preliminary screen; a pass here is a green light for continued collection, not for capital.

**Check date reminder:** Add a calendar reminder for 2026-11-20. Run
`python3 src/check_collection.py` (to be written at re-check time) to count events
against the thresholds before deciding whether to run the backtest.

---

## Next Steps After Re-Check Date

1. `src/aggregate.py` — bin raw events into 5-min notional volumes, compute IS threshold
2. `src/simulator.py` — entry/exit logic against minute-bar OHLCV (pulled from Binance klines at backtest time)
3. `src/analytics.py` — gate G1–G6 + NC battery
4. Run BTC gate first; only run ETH gate after BTC verdict is locked
5. Record results in GATE.md
