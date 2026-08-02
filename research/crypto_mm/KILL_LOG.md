# Crypto MM Pilot — Outcome Log
## append-only after each verdict

---

## ALGO/USD — KILLED (2026-08-03)
pair too liquid for 1.5% spread MM; natural spread far below fee coverage threshold
- 30-day Kraken: 1998 trades/day, only 2 fills at 1.5% spread → G1 FAIL
- Spread proxy 0.012% confirms market is tighter than retail MM can compete with
- Eliminated: not a low-volume pair in practice despite rebate list eligibility

## ICX/USD — KILLED (2026-08-03)
real adverse selection present — survives neither Kraken nor MEXC fee structure
- 30-day: 68 fills, 91% forced closes, mean forced net -0.31% under MEXC (fee-neutral)
- Price persistently moves against fills: AS@60m = -0.38%
- Unlike MINA/KAVA, ICX losses are structural (informed flow), not a fee artifact

## FIL/USD — KILLED (2026-08-03)
zero complete round trips in 30 days — spread capture cannot occur
- 29 fills, 0 complete RTs; market structure does not close the other side within 20 min
- Tick clustering at identical prices (median jump 0.00%) suggests bot-dominated flow
- No path forward without structural change to holding time or spread

## MINA/USD — CONDITIONAL PROCEED (2026-08-03)
- 30-day on Kraken data: 69 fills, 8 complete RTs, adj net +6.16%/mo under MEXC fees
- All 6 gate criteria pass; AS-scores manageable (-0.11% at t+5m, -0.19% at t+30m)
- Forced close net under MEXC = -0.02% (losses are fee-driven; near-zero on zero-fee venue)
- BLOCKER: MEXC pair confirmation + 30-day paper trade required before any capital
- Sharpe 1.13 (adequate but slim; live conditions will differ from Kraken simulation)

## KAVA/USD — CONDITIONAL PROCEED (2026-08-03)
- 30-day on Kraken data: 49 fills, 5 complete RTs, adj net +4.60%/mo under MEXC fees
- All 6 gate criteria pass; AS-scores positive (+0.048% at t+5m, +0.186% at t+30m)
- Forced close net under MEXC = +0.003% (price reverts to entry; forced close nearly free)
- BLOCKER: same as MINA — MEXC venue confirmation + paper trade before capital
- Sharpe 1.49 — strongest candidate; best AS profile of all 5 pairs
