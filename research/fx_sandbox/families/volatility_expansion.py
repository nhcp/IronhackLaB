"""
Volatility Expansion -- 1H.

Signal: ATR expands above its rolling average by a multiplier threshold.
  When ATR(atr_period) > expansion_mult × ATR_avg(avg_period), a
  volatility expansion is underway.  Direction: enter long if the close is
  above the avg_period rolling mean (momentum side), short if below.

Rationale: volatility expansions often accompany breakout moves.  Entering
in the direction of the current trend when vol spikes aims to capture the
initial move.  Exit is via SL/TP before the expansion exhausts.

Structural distinction from killed experiments:
  No killed experiment uses ATR expansion as a signal.  trend_200sma_v1
  (killed) is a slow trend-follower; this reacts to intraday volatility regime
  changes.  rsi_meanrev_1h_v1/v2/v3 (killed) mean-revert against momentum;
  this enters WITH momentum when volatility expands.

Fixed time exit: 48 bars (2 days).

Known deviations: close-bar exits, direction determined at bar close.
"""

import pandas as pd

PARAM_GRID = {
    "atr_period":     [14, 21],                 # ATR calculation period
    "expansion_mult": [1.5, 2.0, 2.5, 3.0],    # ATR must exceed avg × this
    "avg_period":     [20, 40],                 # period for rolling ATR average
    "sl_mult":        [1.5, 2.5],               # × ATR(atr_period)
    "tp_mult":        [2.0, 3.0, 4.0, 5.0],    # × ATR(atr_period)
}
# Grid size: 2 × 4 × 2 × 2 × 4 = 128 combos.
# Fixed time exit: _TIME_EXIT = 48 bars.

_TIME_EXIT = 48


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]),
         (df["high"] - prev).abs(),
         (df["low"]  - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def positions(df: pd.DataFrame, **params) -> pd.Series:
    atr_period     = int(params["atr_period"])
    expansion_mult = float(params["expansion_mult"])
    avg_period     = int(params["avg_period"])
    sl_mult        = float(params["sl_mult"])
    tp_mult        = float(params["tp_mult"])

    atr_series     = _atr(df, atr_period)
    atr_avg        = atr_series.rolling(avg_period).mean()
    price_avg      = df["close"].rolling(avg_period).mean()

    atr_vals    = atr_series.values
    atr_avg_v   = atr_avg.values
    price_avg_v = price_avg.values
    closes      = df["close"].values
    n           = len(df)
    pos         = [0] * n

    side = 0
    sl = tp = entry_bar = None

    for i in range(n):
        c = closes[i]

        if side != 0:
            if (i - entry_bar) >= _TIME_EXIT:
                side = 0; sl = tp = entry_bar = None
            elif (side == 1 and (c <= sl or c >= tp)) or \
                 (side == -1 and (c >= sl or c <= tp)):
                side = 0; sl = tp = entry_bar = None
            else:
                pos[i] = side
                continue

        atrv  = float(atr_vals[i])
        avgv  = float(atr_avg_v[i])
        pavgv = float(price_avg_v[i])

        if pd.isna(atrv) or pd.isna(avgv) or pd.isna(pavgv) or avgv <= 0.0 or atrv <= 0.0:
            continue

        if atrv < expansion_mult * avgv:
            continue  # volatility not yet expanding

        raw = 1 if c > pavgv else -1

        side = raw
        entry_bar = i
        sl = c - side * sl_mult * atrv
        tp = c + side * tp_mult * atrv
        pos[i] = side

    return pd.Series(pos, index=df.index, dtype=int)
