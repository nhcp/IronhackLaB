"""FX sandbox data layer.

Loads the pinned wave-1 Dukascopy parquets, enforcing:
  1. SHA256 pin check against data/SHA256SUMS -- a hash mismatch aborts,
     so no verdict can ever run on silently changed data.
  2. Weekend/closed-hours flat-bar filter -- Dukascopy emits flat bars
     (zero range, zero volume) while an instrument is closed; these must
     not reach indicator code.

Also provides per-symbol empirical annualization (bars per year measured
from the filtered data itself) replacing the 24/7 ANNUALIZE constants
used on the crypto side.
"""
import hashlib
from pathlib import Path

import pandas as pd

FX_DIR   = Path(__file__).resolve().parent
DATA_DIR = FX_DIR / "data"
SUMS     = DATA_DIR / "SHA256SUMS"

SYMBOLS = ["EURUSD", "XAUUSD", "SPX500", "GER40"]

# Round-trip costs, fraction of price. Derived from measured spreads
# (2026-07-27 download): gated = 2 x p95 one-way spread (+ 0.007%
# commission RT on commission-account instruments EURUSD/XAUUSD);
# informational = 2 x median one-way spread (+ same commission).
# OVERNIGHT: charged per calendar night a position is held, both columns.
COSTS = {
    #             gated      informational
    "EURUSD": {"gated": 0.000305, "info": 0.000125},
    "XAUUSD": {"gated": 0.000789, "info": 0.000455},
    "SPX500": {"gated": 0.000541, "info": 0.000300},
    "GER40":  {"gated": 0.001041, "info": 0.000310},
}
OVERNIGHT_PER_NIGHT = 0.0001   # 0.01% per night held


def _pinned_hash(path: Path) -> str:
    for line in SUMS.read_text().splitlines():
        digest, _, name = line.partition("  ")
        if Path(name.strip()).name == path.name:
            return digest.strip()
    raise RuntimeError(f"{path.name} not found in {SUMS}")


def _verify_pin(path: Path) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = _pinned_hash(path)
    if actual != expected:
        raise RuntimeError(
            f"PIN VIOLATION: {path.name} sha256 {actual[:12]}... != pinned "
            f"{expected[:12]}... -- data changed since registration, refusing to run"
        )


def load_ohlcv(symbol: str) -> pd.DataFrame:
    """Return filtered OHLCV indexed by UTC datetime for one symbol.

    Columns: open, high, low, close, volume (volume 0.0 if absent upstream).
    Flat closed-market bars are removed. ask_close is dropped here; use
    load_raw() if spread data is needed.
    """
    df = load_raw(symbol)
    flat = (df["high"] == df["low"]) & (df["open"] == df["close"])
    if "volume" in df.columns:
        flat &= df["volume"].fillna(0) == 0
    else:
        df["volume"] = 0.0
    df = df[~flat]
    out = df[["open", "high", "low", "close", "volume"]].copy()
    return out


def load_raw(symbol: str) -> pd.DataFrame:
    """Pinned parquet -> DataFrame indexed by UTC datetime, unfiltered."""
    path = DATA_DIR / f"{symbol}_1h.parquet"
    _verify_pin(path)
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df


def bars_per_year(df: pd.DataFrame) -> float:
    """Empirical annualization factor from the filtered data itself."""
    years = (df.index[-1] - df.index[0]).days / 365.25
    return len(df) / years
