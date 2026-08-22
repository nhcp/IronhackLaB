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

## session_breakout_fx_v1 -- KILL (2026-07-27)
commit 594365f614 | family session_breakout | symbols EURUSD,XAUUSD,SPX500,GER40
- EURUSD [gated]: total -73.3%, sharpe -3.38, h1 -48.8%, h2 -47.9%, tpm 37.3, WR 41.4%, flat_windows 0
- XAUUSD [gated]: total -96.6%, sharpe -3.94, h1 -79.4%, h2 -83.4%, tpm 39.3, WR 39.8%, flat_windows 0
- SPX500 [gated]: total -91.7%, sharpe -2.06, h1 -74.1%, h2 -68.0%, tpm 42.1, WR 46.2%, flat_windows 0
- GER40 [gated]: total -98.4%, sharpe -4.25, h1 -90.3%, h2 -83.9%, tpm 38.4, WR 39.3%, flat_windows 0

## time_of_day_fx_v1 -- KILL (2026-07-27)
commit 594365f614 | family time_of_day | symbols EURUSD,XAUUSD,SPX500,GER40
- EURUSD [gated]: total -38.6%, sharpe -3.97, h1 -16.7%, h2 -26.2%, tpm 13.3, WR 35.3%, flat_windows 0
- XAUUSD [gated]: total -83.2%, sharpe -4.69, h1 -65.9%, h2 -50.8%, tpm 19.2, WR 30.9%, flat_windows 0
- SPX500 [gated]: total -80.3%, sharpe -2.29, h1 -75.9%, h2 -18.2%, tpm 22.1, WR 37.6%, flat_windows 0
- GER40 [gated]: total -91.3%, sharpe -4.65, h1 -76.5%, h2 -62.7%, tpm 19.6, WR 30.4%, flat_windows 0

## bollinger_meanrev_fx_v1 -- KILL (2026-07-27)
commit 594365f614 | family bollinger_meanrev | symbols EURUSD,XAUUSD,SPX500,GER40
- EURUSD [gated]: total -56.0%, sharpe -1.85, h1 -29.3%, h2 -37.8%, tpm 21.9, WR 57.2%, flat_windows 0
- XAUUSD [gated]: total -89.9%, sharpe -2.21, h1 -67.9%, h2 -68.5%, tpm 17.9, WR 56.2%, flat_windows 0
- SPX500 [gated]: total -56.0%, sharpe -0.69, h1 -18.7%, h2 -45.9%, tpm 18.0, WR 60.4%, flat_windows 0
- GER40 [gated]: total -87.8%, sharpe -1.84, h1 -69.2%, h2 -60.3%, tpm 17.7, WR 59.6%, flat_windows 0

## rsi_meanrev_fx_v1 -- KILL (2026-07-27)
commit 594365f614 | family rsi_meanrev | symbols EURUSD,XAUUSD,SPX500,GER40
- EURUSD [gated]: total -11.6%, sharpe -0.46, h1 -2.5%, h2 -9.4%, tpm 4.3, WR 64.1%, flat_windows 0
- XAUUSD [gated]: total -39.0%, sharpe -0.70, h1 -37.3%, h2 -2.8%, tpm 3.4, WR 54.1%, flat_windows 0
- SPX500 [gated]: total -18.2%, sharpe -0.29, h1 -10.3%, h2 -8.8%, tpm 3.5, WR 54.5%, flat_windows 0
- GER40 [gated]: total -25.8%, sharpe -0.45, h1 -18.7%, h2 -8.7%, tpm 2.9, WR 57.9%, flat_windows 0
