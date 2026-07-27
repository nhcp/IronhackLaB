"""One-shot validation of the wave-1 data layer. Read-only."""
import pandas as pd
from fx_data import SYMBOLS, load_raw, load_ohlcv, bars_per_year

for sym in SYMBOLS:
    raw = load_raw(sym)
    df  = load_ohlcv(sym)
    gaps = df.index.to_series().diff().dropna()
    big  = gaps[gaps > pd.Timedelta(hours=6)]
    print(f"{sym}: raw={len(raw):,}  filtered={len(df):,}  "
          f"removed={len(raw)-len(df):,} flat bars")
    print(f"        bars/year={bars_per_year(df):,.0f}  "
          f"span={df.index[0].date()} -> {df.index[-1].date()}")
    print(f"        gaps>6h: {len(big)} "
          f"(largest: {gaps.max()})")
    wk = df[df.index.dayofweek >= 5]
    print(f"        weekend bars remaining after filter: {len(wk)}\n")
print("PIN CHECK: all four hashes verified (load_raw would have aborted otherwise)")
