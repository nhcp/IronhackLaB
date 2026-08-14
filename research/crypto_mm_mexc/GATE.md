# Crypto MM MEXC — Pre-Registered Gate
## Registered: 2026-08-14 | Status: OPEN

This gate is append-only after registration. Results are recorded below only after
the backtest has been run. The strategy does not proceed to live capital without
ALL criteria passing on BOTH candidate pairs.

---

## Research Context

Hypothesis (Bianchi, Babiak & Dickerson 2022, JBF): Short-term reversal /
liquidity-provision returns concentrate in LOW-VOLUME crypto pairs, compensating
for adverse-selection risk. The edge turns negative on high-fee venues and only
survives where maker fees are zero.

This thread tests the hypothesis on REAL MEXC data (not a Kraken proxy) for
MINA/USDT and KAVA/USDT — two low-volume pairs confirmed active on MEXC spot.

---

## Data & Methodology (Fixed Pre-Run)

- **Exchange:** MEXC spot (api.mexc.com)
- **Pairs:** MINA/USDT and KAVA/USDT
- **Data source:** MEXC public klines API — 1h OHLCV bars (max 500 bars ≈ 20 days)
- **Fee schedule:** 0% maker, 0.05% taker (no volume requirement; MEXC public documentation)
- **Spread parameter:** 1.0% total (0.5% each side from mid)
- **Spread sweep:** also run at 0.8% and 1.5% for robustness; primary evaluation at 1.0%
- **Mid-price:** previous bar's close (no lookahead)
- **Fill detection:** bar's LOW ≤ bid → bid fill at posted bid price; bar's HIGH ≥ ask → ask fill at posted ask price
- **Fill-rate haircut:** 50% (conservative; ignores queue depth — real fill rate will be lower than simulated)
- **Max inventory hold:** 3 bars (3 hours) before forced close at taker fee
- **Forward return horizons:** t+1h, t+2h, t+4h, t+8h, t+12h (bars ahead)
- **Adverse selection sign convention:** negative = price moved against our fill direction

---

## Gate Criteria (Pre-Registered)

### G1: Fill Count (Data Viability)
- **Threshold:** ≥ 5 simulated fills in the 20-day window
- **Rationale:** At 20 days of data, 5 fills = ~7.5/month annualized. Below 5 fills,
  the spread is too wide for any useful signal.
- **Measured by:** `simulator.py` output: `total_fills`

### G2: Net Return on Complete Round-Trips
- **Threshold:** Mean net P&L per complete RT > 0.10%
- **Rationale:** MEXC 0% maker means complete RTs have 0 fee cost. Must exceed
  0.10% to absorb bid-ask spread estimation error and provide real margin.
- **Measured by:** `simulator.py` output: `mean_complete_net_pct`

### G3: Fill-Rate-Adjusted Monthly Net Return
- **Threshold:** fill_adj_net_monthly_pct > 0
  - `adj_net = (complete_fills/20days × 50%) × mean_complete_net + forced_closes × mean_forced_net`
  - Normalised to per-month rate
- **Rationale:** After 50% fill-rate haircut, strategy must still show positive expected value.
- **Measured by:** `simulator.py` output: `fill_adj_net_monthly_pct`

### G4: Adverse Selection Score at t+1h
- **Threshold:** mean AS score at t+1h > -0.15 × spread_pct
  - For 1.0% spread: > -0.15%
- **Rationale:** Within 1 hour of a maker fill, price should not move systematically
  against us by more than 15% of the spread. If it does, informed flow dominates.
- **Measured by:** `analytics.py` output: `as_1h`

### G5: Adverse Selection Score at t+4h
- **Threshold:** mean AS score at t+4h > -0.30 × spread_pct
  - For 1.0% spread: > -0.30%
- **Rationale:** Persistent adverse selection at 4h horizon is the primary indicator
  of informed flow. This is the "who is on the other side?" test.
- **Measured by:** `analytics.py` output: `as_4h`

### G6: Risk-Adjusted Return
- **Threshold:** Sharpe ratio of per-RT returns ≥ 0.3
  - Threshold lower than prior gate (0.5) because 20-day sample is short.
- **Rationale:** Minimum bar for risk-adjusted viability; 0.3 is already generous for
  this sample size — a negative or near-zero Sharpe kills the strategy.
- **Measured by:** `simulator.py` output: `sharpe`

---

## Pass Rule
- All 6 criteria must pass on the SAME pair.
- Both MINA/USDT AND KAVA/USDT must pass.
- Single-pair pass = data mining concern; do not pursue.

---

## Disqualifying Conditions (Override Any Pass)
1. If AS@t+1h < -0.50 × spread_pct on ANY pair:
   → Informed flow dominant; strategy not viable on that pair. Close thread for that pair.
2. If total_fills < 3 on any pair:
   → Insufficient data; no conclusion possible. Do not count as pass or fail.
   → Extend data collection or close thread.
3. If forced-close rate > 95% (nearly every position exits without completing RT):
   → Market structure does not allow round-trips; spread too wide for this liquidity.

---

## Results — to be filled after running backtest
(This section intentionally blank until backtest complete)
