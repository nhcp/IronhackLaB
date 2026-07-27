"""Hour-of-day seasonality.

For each UTC hour bucket, tracks a trailing rolling average of that hour's
historical returns (lookback_days most recent occurrences of the same
hour, shifted by one to avoid using the current bar's own return). Goes
long when the historical average return for this hour exceeds
entry_thresh, short when below -entry_thresh, else flat.
"""
import pandas as pd

PARAM_GRID = {
    "lookback_days": [30, 60, 90],
    "entry_thresh":  [0.0003, 0.0005, 0.001],
}


def positions(df: pd.DataFrame, lookback_days=60, entry_thresh=0.0005) -> pd.Series:
    ret = df["close"].pct_change()
    hour = df.index.hour

    work = pd.DataFrame({"ret": ret, "hour": hour}, index=df.index)

    def _roll(g: pd.DataFrame) -> pd.Series:
        return g["ret"].rolling(lookback_days, min_periods=10).mean().shift(1)

    hourly_avg = work.groupby("hour", group_keys=False).apply(_roll)
    hourly_avg = hourly_avg.reindex(df.index)

    pos = pd.Series(0.0, index=df.index)
    pos[hourly_avg > entry_thresh] = 1.0
    pos[hourly_avg < -entry_thresh] = -1.0
    return pos
