"""Bollinger Band mean reversion.

Enters long when close crosses below the lower band, short when close
crosses above the upper band; exits (flattens) when close reverts to the
moving-average midline. No regime filter -- deliberately kept pure to
compare against the crypto RSI-meanrev result, where an ADX filter was
implicated in masking a continuation/reversion misclassification.
"""
import numpy as np
import pandas as pd

PARAM_GRID = {
    "period":  [14, 20, 30],
    "num_std": [1.5, 2.0, 2.5],
}


def positions(df: pd.DataFrame, period=20, num_std=2.0) -> pd.Series:
    close = df["close"]
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = (sma + num_std * std).values
    lower = (sma - num_std * std).values
    sma_v = sma.values
    close_v = close.values

    n = len(df)
    states = np.zeros(n)
    cur = 0
    for i in range(n):
        if np.isnan(sma_v[i]) or np.isnan(upper[i]):
            states[i] = 0
            continue
        c = close_v[i]
        if cur == 0:
            if c < lower[i]:
                cur = 1
            elif c > upper[i]:
                cur = -1
        elif cur == 1:
            if c >= sma_v[i]:
                cur = 0
        elif cur == -1:
            if c <= sma_v[i]:
                cur = 0
        states[i] = cur

    return pd.Series(states, index=df.index)
