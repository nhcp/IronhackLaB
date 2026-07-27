# FX Sandbox KILL LOG — append-only. Verdicts are final.

## volatility_expansion_fx_v1 -- RUN FAILED (2026-07-27)
Engine fault, no verdict recorded: SPX500 window 1 had no combo meeting
min_trades_is=30 and the inherited crypto engine aborts on that condition.
Completed symbols before abort (gated): EURUSD -17.0% sh -0.87 tpm 3.3;
XAUUSD -32.2% sh -0.61 tpm 2.7. Engine amended with flat-window policy
(unqualified window trades flat through its OOS period); re-registered
unchanged as _fx_v2.

## volatility_expansion_fx_v2 -- KILL (2026-07-27)
commit b5068fbeea | family volatility_expansion | symbols EURUSD,XAUUSD,SPX500,GER40
- EURUSD [gated]: total -17.0%, sharpe -0.87, h1 -11.2%, h2 -6.6%, tpm 3.3, WR 38.6%, flat_windows 0
- XAUUSD [gated]: total -32.2%, sharpe -0.61, h1 -9.0%, h2 -25.5%, tpm 2.7, WR 44.7%, flat_windows 0
- SPX500 [gated]: total -23.7%, sharpe -0.47, h1 -9.9%, h2 -15.3%, tpm 3.3, WR 39.2%, flat_windows 1
- GER40 [gated]: total -24.9%, sharpe -0.67, h1 -18.0%, h2 -8.4%, tpm 1.6, WR 30.3%, flat_windows 4
