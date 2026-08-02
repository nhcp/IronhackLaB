# Crypto MM Pilot — Pre-Registered Gate
## Registered: 2026-08-02 | Status: OPEN

This gate is append-only after registration. Results will be recorded below.
Strategy does not proceed to live capital without ALL criteria passing on ≥ 2 pairs.

---

## Gate Criteria (Pre-Registered)

### G1: Trade Frequency (Data Viability)
- **Threshold:** ≥ 10 simulated fills/month (not trades — fills where our limit is crossed)
- **Rationale:** Below 10 fills/month, sample size is too small to distinguish signal from noise
- **Measured by:** `simulator.py` output: `fills_per_month`

### G2: Gross Spread Coverage of Fees
- **Threshold:** Mean gross spread captured per round-trip > 0.76% (Kraken maker × 2)
- **Rationale:** A strategy that can't cover its own fees before any adverse selection is dead
- **Measured by:** `simulator.py` output: `mean_rt_spread_pct`
- **Note:** Under MEXC (0% maker), this threshold drops to >0% + adverse selection cost

### G3: Fill-Rate-Adjusted Net Return
- **Threshold:** Expected net P&L > 0 when gross P&L discounted by 60% fill rate
  - `adjusted_net = (gross_spread_per_rt - round_trip_fee) × 0.60 × fills_per_month`
- **Rationale:** Paper shows retail limit order fill rates of 54–65%; 60% is the midpoint
- **Measured by:** `simulator.py` output: `fill_rate_adj_net_monthly`

### G4: Adverse Selection Score — Short Term (t+5min)
- **Threshold:** AS-score at t+5min > -0.15 × mean_spread
  - AS-score = mean signed fill-conditional forward return at t+5min
  - Sign convention: negative = price moved against the fill direction
- **Rationale:** If 15% or more of the spread is eroded by adverse selection within 5 minutes,
  inventory risk is too high for a retail market maker
- **Measured by:** `analytics.py` output: `as_score_5m`

### G5: Adverse Selection Score — Medium Term (t+30min)
- **Threshold:** AS-score at t+30min > -0.30 × mean_spread
- **Rationale:** If adverse selection is persistent through 30 minutes, we're consistently
  trading against informed flow. This is the "who is on the other side?" test.
- **Measured by:** `analytics.py` output: `as_score_30m`

### G6: Risk-Adjusted Return
- **Threshold:** Monthly Sharpe ratio ≥ 0.5 (using fill-rate-adjusted net returns)
- **Rationale:** Minimum bar for strategy to justify live capital allocation
- **Measured by:** `analytics.py` output: `monthly_sharpe`

---

## Pass Rule
- All 6 criteria must pass on the SAME pair
- This must hold on ≥ 2 of the 5 candidate pairs
- Single-pair pass = data mining concern, do not pursue

---

## Disqualifying Conditions (Override Any Pass)
- If any pair shows fill-conditional forward return worse than -0.50 × spread at t+30min:
  → Informed flow is present; strategy is not viable on that pair regardless of other metrics
- If best-bid/best-ask proxy spread during simulation is consistently < 0.30%:
  → Not a low-volume pair in practice; the paper's edge regime does not apply

---

## Results — Simulation Date 2026-08-03

**Data:** Kraken trade-level CSVs, last 30 days. Fee scenario A = Kraken retail (0.38%
maker / 0.80% taker). Fee scenario B = MEXC (0.00% maker / 0.05% taker). Spread: 1.5%.

### Gate Results by Pair (MEXC fee regime, the viable scenario)

| Pair | G1 Fills/mo | G2 Gross>0.76% | G3 Adj Net>0 | G4 AS@5m | G5 AS@30m | G6 Sharpe≥0.5 | PASS? |
|---|---|---|---|---|---|---|---|
| MINA/USD | 69 ✓ | 1.5% ✓ | +6.16%/mo ✓ | -0.111% PASS ✓ | -0.191% PASS ✓ | 1.13 ✓ | **6/6** |
| KAVA/USD | 49 ✓ | 1.5% ✓ | +4.60%/mo ✓ | +0.048% PASS ✓ | +0.186% PASS ✓ | 1.49 ✓ | **6/6** |
| ALGO/USD | 2 ✗ | n/a ✗ | — | -0.180% PASS | +0.123% PASS | NaN ✗ | **FAIL** (too liquid) |
| ICX/USD | 68 ✓ | 1.5% ✓ | -16.49%/mo ✗ | -0.202% PASS | -0.276% PASS | -1.87 ✗ | **FAIL** (real AS) |
| FIL/USD | 29 ✓ | n/a* ✗ | +3.23%/mo ✓ | +0.111% PASS | +0.153% PASS | 1.13 ✓ | **FAIL** (no complete RTs) |

*FIL: zero complete round trips in 30 days — 100% forced closes, spread capture not occurring.

### Under Kraken Retail Fees (0.38% maker): ALL PAIRS FAIL

Forced close cost at Kraken = 0.38% + 0.80% = 1.18% per one-sided exit. Since 77-91%
of positions forced-close, mean net P&L = -0.90% to -1.34% per event.
No pair achieves positive adj_net_monthly under Kraken retail fee structure.

### Key Structural Finding

The forced-close P&L under MEXC fees reveals the mechanism:
- MINA forced close net: -0.02% → price barely moves during 20-min hold
- KAVA forced close net: +0.003% → essentially flat
- ICX forced close net: -0.31% → REAL adverse selection during hold period

For MINA and KAVA, losses on Kraken are **entirely fee-driven**, not adverse-selection-driven.
The edge exists in the economics; the blocking variable is exchange choice.

---

**Pairs passing all gates:** MINA/USD and KAVA/USD (2 of 5) — **under MEXC fee regime**
**Pairs passing under Kraken retail fees:** 0 of 5

**Verdict:** CONDITIONAL PROCEED — requires MEXC venue validation (see RESEARCH.md § Next Steps)

---

## Remaining Gaps Before Live Capital

1. Confirm MINA and KAVA are listed on MEXC spot with adequate order book
2. Pull MEXC trade data (separate API) or paper trade 30 days to validate fill dynamics
3. Address queue-position uncertainty: simulation overestimates fill rates (no order book depth)
4. Note: 1-month simulation window is short; repeat over longer history when data available
