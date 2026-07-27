"""RSI mean reversion (FX retest of the crypto S6 lineage).

Long when RSI drops below oversold, short when RSI rises above
overbought; exits (flattens) when RSI reverts through the 50 midline.
No trend/ADX filter -- FX ranges structurally differently from crypto,
so this is a from-scratch look, not a port.
"""
import numpy as np
import pandas as pd

PARAM_GRID = {
    "period":     [7, 14, 21],
    "oversold":   [20, 25, 30],
    "overbought": [70, 75, 80],
}


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def positions(df: pd.DataFrame, period=14, oversold=30, overbought=70) -> pd.Series:
    r = _rsi(df["close"], period).values
    n = len(df)
    states = np.zeros(n)
    cur = 0
    for i in range(n):
        v = r[i]
        if np.isnan(v):
            states[i] = 0
            continue
        if cur == 0:
            if v < oversold:
                cur = 1
            elif v > overbought:
                cur = -1
        elif cur == 1:
            if v >= 50:
                cur = 0
        elif cur == -1:
            if v <= 50:
                cur = 0
        states[i] = cur
    return pd.Series(states, index=df.index)
