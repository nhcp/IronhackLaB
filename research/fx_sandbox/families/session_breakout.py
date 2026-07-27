"""Session opening-range breakout.

Computes the high/low of the first `range_hours` after a session's local
open (08:00 local time for both London and New York forex-session
convention). During the following `hold_hours`, takes the position of
whichever side breaks first (close beyond range +/- buffer); flat for the
rest of the day if no breakout occurs. Position resets to flat outside the
trading window (no overnight carry).
"""
import numpy as np
import pandas as pd

PARAM_GRID = {
    "session":     ["london", "ny"],
    "range_hours": [1, 2],
    "buffer_pct":  [0.0, 0.1],
    "hold_hours":  [4, 8],
}

_TZ = {"london": "Europe/London", "ny": "America/New_York"}
_OPEN_HOUR = 8  # local hour of session open


def positions(df: pd.DataFrame, session="london", range_hours=1,
              buffer_pct=0.05, hold_hours=6) -> pd.Series:
    tz = _TZ[session]
    local = df.index.tz_convert(tz)
    hour_frac = local.hour + local.minute / 60.0
    ldate = local.date

    work = pd.DataFrame({
        "high": df["high"].values,
        "low":  df["low"].values,
        "close": df["close"].values,
        "hour": hour_frac,
    }, index=df.index)
    work["ldate"] = ldate

    pos = pd.Series(0.0, index=df.index)

    range_end = _OPEN_HOUR + range_hours
    window_end = range_end + hold_hours

    for _, g in work.groupby("ldate", sort=False):
        rng_mask = (g["hour"] >= _OPEN_HOUR) & (g["hour"] < range_end)
        rng = g[rng_mask]
        if rng.empty:
            continue
        rng_high = rng["high"].max()
        rng_low  = rng["low"].min()
        buf = (rng_high - rng_low) * buffer_pct

        win_mask = (g["hour"] >= range_end) & (g["hour"] < window_end)
        win = g[win_mask]
        if win.empty:
            continue

        over  = (win["close"] > (rng_high + buf)).values
        under = (win["close"] < (rng_low  - buf)).values
        over_idx  = np.where(over)[0]
        under_idx = np.where(under)[0]
        first_over  = over_idx[0]  if len(over_idx)  else None
        first_under = under_idx[0] if len(under_idx) else None

        if first_over is None and first_under is None:
            continue
        if first_under is None or (first_over is not None and first_over < first_under):
            direction, start = 1.0, first_over
        else:
            direction, start = -1.0, first_under

        idx = win.index[start:]
        pos.loc[idx] = direction

    return pos
