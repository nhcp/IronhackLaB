# Crypto Liquidity Provision / Market-Making Pilot
## Research Thread — 2026-08-02

**Hypothesis (Bianchi, Babiak & Dickerson 2022, JBF):**
Short-term reversal / liquidity-provision returns concentrate in low-volume crypto
pairs, where compensation for adverse-selection risk is highest. The edge turns
*negative* after fees on high-volume venues (Binance) and only survives where fee
structure and low competition allow it.

---

## Task 1: Candidate Pairs & Fee Structure

### Critical Finding: Kraken "Maker Rebate" Program ≠ Rebates at Retail Volume

Kraken launched a maker fee incentive program (June 2025) covering 650+ low-liquidity
spot pairs. The fee schedule for these pairs:

| 30-Day Volume (USD) | Maker Rate | Taker Rate |
|---|---|---|
| $0+ (retail) | **+0.38%** | 0.80% |
| $2,500+ | +0.28% | 0.60% |
| $10,000+ | +0.20% | 0.38% |
| $50,000+ | +0.13% | 0.30% |
| $5M+ | 0.00% | 0.12% |
| **$10M+** | **-0.02%** | 0.10% |

**The honest verdict:** True rebates (negative maker fees) only kick in at $10M+/month
volume — far outside retail scope. At retail volume ($0 tier), maker fee is still **+0.38%**.
The pairs are "reduced fee" vs. standard pairs, but still charge makers.

**Round-trip cost at retail Kraken:** 0.38% × 2 = **0.76% per completed round-trip**
(paying maker fee on both the bid fill and the ask fill).

### MEXC as Alternative: Genuine 0% Maker Fee

MEXC spot: **0% maker, 0.05% taker** — no volume requirement.
Round-trip cost: **0.00%** (maker fees), adverse selection is the only cost.
This directly matches the paper's requirement: fee structure where edge can survive.

**Data complication:** MEXC historical trade data is less accessible for free than Kraken.
Kraken offers complete free CSV downloads of all trade history.

### Strategy: Use Kraken Data, Design for Both

Backtest will use Kraken trade history (free, complete). Results will be evaluated
under *both* fee regimes (0.38% maker for Kraken live, 0% maker for MEXC live).
The gate requires net-positive under the *higher* Kraken fee assumption. If that
passes, MEXC improves the edge further.

### Candidate Pairs (Kraken, Low-Volume, Rebate-Eligible)

Selection criteria: in Kraken's 650+ rebate program; traded actively enough to
simulate (>5 trades/day on average); not dominated by structured manipulation.

| Pair | Rationale |
|---|---|
| **MINA/USD** | ZK-chain, low Kraken volume, expected spread 0.5–2% |
| **KAVA/USD** | DeFi chain, sporadic Kraken activity, moderate spread |
| **ALGO/USD** | Algorand, established but low Kraken liquidity |
| **ICX/USD** | ICON, very low volume, potentially widest spreads |
| **FIL/USD** | Filecoin, infrastructure token, low Kraken activity |

**Caveat:** Exact pair selection requires running `data_fetch.py` to check actual
24h trade counts and observed spread proxy (price variance between consecutive
fills). The pairs above are hypotheses — kill any with <5 trades/day or spread
proxy < 0.5% (insufficient to cover Kraken fees).

---

## Task 2: Strategy Design

### Core Mechanics

```
POST bid at: mid_price - (spread/2)
POST ask at: mid_price + (spread/2)
CANCEL AND REPOST if: mid_price moves > repricing_threshold
TARGET spread: 0.8–2.0% (param to sweep; must exceed 0.76% RT fee)
POSITION LIMIT: max ±1 unit inventory (immediately flatten if hit)
```

**Mid-price estimation from trade data:**
Since we only have trade-level data (not live order book), mid-price is approximated
as exponential moving average of recent trade prices. In live operation, use
Kraken REST `Ticker` endpoint (best bid + ask available in real time).

**Fill detection in simulation:**
A "maker fill" is registered when a trade occurs at or below our posted bid
(we get bought) or at or above our posted ask (we get sold). This assumption
OVERESTIMATES our real fill rate because it ignores queue position — in reality,
other limit orders ahead of us in the queue may absorb the flow first.

**Inventory management:**
After one side fills, we hold inventory until the other side fills or we hit
the max holding period (20 minutes). If the other side doesn't fill within
20 min, close at market (taker fee penalty). This is the forced-closure scenario
that degrades real P&L vs. theoretical.

### Fill-Conditional Forward Return (The Core Diagnostic)

For every maker fill, record the price change at:
- t+1min, t+5min, t+15min, t+30min, t+60min

**Interpretation:**
- After an ASK fill (we sold): if price RISES afterward → adverse selection hit us
  (we sold to someone who knew price was going up)
- After a BID fill (we bought): if price FALLS afterward → adverse selection hit us

**Adverse selection score (AS-score):**
```
AS_score = mean(signed_forward_return) across all fills
           where sign = -1 if ask fill, +1 if bid fill
```
If AS_score < -0.2 × spread: adverse selection is eating more than 20% of the
gross spread — fail the diagnostic even if gross P&L looks positive.

---

## Task 3: Data Access Assessment

### What We Have (Free)

**Kraken trade-level CSVs:**
- Format: `timestamp, price, volume, buy_sell`
- Coverage: from market inception to Q3 2024 (quarterly updates)
- Access: downloadable bulk ZIP from Kraken support page
- Also: REST API `GET /0/public/Trades?pair=X&since=Y` — paginated, free, up to present

**This is sufficient to compute:**
- Fill-conditional forward returns (primary diagnostic)
- Gross spread captured (using trade-crossing detection)
- Adverse selection score
- Trade frequency per pair (winnow candidate list)
- Approximate round-trip P&L under fee assumptions

### What We Are Missing

**Order book snapshots:**
- We cannot know queue position → cannot estimate real fill rates precisely
- We cannot know the actual bid-ask spread at any moment (only infer from trades)
- Cost to fix: Crypto Lake (~$20–$50/month for historical L2 data)

**Consequence of missing order book data:**
Our simulation produces an *upper-bound* P&L (100% fill rate assumption). We must
apply the paper's 54–65% fill rate discount manually. If the strategy is marginal
at 100% fills, it's dead. If it's robustly profitable at 100% fills, surviving a
60% haircut is the gate.

**DATA ACCESS VERDICT:** Sufficient to run a *conservative screening test* using
trade-level data. NOT sufficient to produce a precise execution-quality estimate.
If the strategy passes the trade-level screen, the next stage would require order
book data (paid source) before any live capital allocation.

---

## Task 4: Pre-Registered Gate

**See GATE.md for the formal gate document. Summary:**

| Criterion | Threshold | Disqualifies if |
|---|---|---|
| Min trade frequency | ≥ 10 fills/month (simulated) | Fewer than 10 fills → not tradeable |
| Gross spread captured | > 0.76% per RT (Kraken) | Dead on fees alone |
| Fill-rate-adjusted net return | > 0 at 60% fill rate | Fails fill-rate haircut |
| AS-score at t+5min | > -0.15 × spread | Adverse selection dominant |
| AS-score at t+30min | > -0.30 × spread | Adverse selection persistent |
| Sharpe (monthly simulated) | ≥ 0.5 | Insufficient risk-adjusted return |

**Minimum bar:** ALL six criteria must pass on ≥ 2 of the 5 candidate pairs.
A strategy that looks good on 1 pair only is not pursued — that's data mining.

---

## Task 5: Capital Cap

**Pilot size:** $500 maximum deployed capital.
**Per-pair maximum:** $200.
**Max inventory per fill:** $50 notional per side.

At $50 notional per fill and 0.38% maker fee = $0.19 per fill. A 1% spread
capture = $0.50 gross per round-trip, net $0.12 after both maker fees.
This is small enough that losses are bounded and signals are observable.

No expansion until 90 live-trade days with net-positive after fees.

---

## Task 6: Honest Status

**Can proceed to simulation:** Yes, with trade-level data.

**Known limitations to disclose before any capital:**
1. Fill rate is overestimated (queue position unknown) — must apply 60% haircut
2. Spread estimation from trades is a proxy, not the true order book spread
3. Kraken retail maker fee (0.38%) significantly narrows the edge — MEXC is preferred
   venue for live operation but requires separate data validation
4. Low-volume pairs on Kraken carry operational risk: thin order books amplify
   slippage during the inventory close leg (taker fill when position times out)
5. The research paper's finding (edge concentrates in low-volume pairs) may already
   be partially arbitraged away since 2022 — we are testing whether it still holds,
   not assuming it does

**"Can't test, not pursuing" trigger:**
If running `data_fetch.py` shows that the candidate pairs have fewer than 5 trades/day
on average (too thin even for simulation), or the spread proxy is below 0.5%, this
thread is closed without further investment.

---

## Next Steps

1. Run `src/data_fetch.py` → pull trade history for all 5 candidate pairs
2. Run `src/simulator.py` → produce P&L and AS-score table
3. Compare results against GATE.md criteria
4. If ≥ 2 pairs pass: move to order book data sourcing (Crypto Lake trial) before live
5. If 0–1 pairs pass: close thread, log outcome in KILL_LOG.md
