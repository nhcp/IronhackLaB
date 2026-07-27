"""Download 1H bid+ask history from Dukascopy for the FX/gold/indices sandbox.

Writes one parquet per instrument to research/fx_sandbox/data/ with columns:
timestamp (UTC), open, high, low, close, volume (all bid side),
ask_close (for spread measurement).
Prints median and 95th-percentile spread per instrument at the end.
"""
import datetime as dt
import os
import sys

import pandas as pd
import dukascopy_python as dk

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")

INSTRUMENTS = {
    "EURUSD": "EUR/USD",
    "XAUUSD": "XAU/USD",
    "SPX500": "E_SandP-500",
    "GER40":  "E_DAAX",
}

START = dt.datetime(2016, 1, 1)
END = dt.datetime(2026, 7, 26)


def fetch_side(code: str, side: str) -> pd.DataFrame:
    print(f"  fetching {code} {side} ...", flush=True)
    df = dk.fetch(
        instrument=code,
        interval=dk.INTERVAL_HOUR_1,
        offer_side=side,
        start=START,
        end=END,
    )
    if df is None or len(df) == 0:
        raise RuntimeError(f"empty result for {code} {side}")
    df = df.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    tcol = df.columns[0]
    df = df.rename(columns={tcol: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    spread_report = []
    for name, code in INSTRUMENTS.items():
        out_path = os.path.join(OUT_DIR, f"{name}_1h.parquet")
        if os.path.exists(out_path):
            print(f"{name}: already downloaded, skipping")
            df = pd.read_parquet(out_path)
        else:
            print(f"{name} ({code}):")
            bid = fetch_side(code, dk.OFFER_SIDE_BID)
            ask = fetch_side(code, dk.OFFER_SIDE_ASK)
            ask_close = ask[["timestamp", "close"]].rename(
                columns={"close": "ask_close"}
            )
            df = bid.merge(ask_close, on="timestamp", how="inner")
            keep = ["timestamp", "open", "high", "low", "close", "ask_close"]
            if "volume" in df.columns:
                keep.append("volume")
            df = df[keep].sort_values("timestamp").reset_index(drop=True)
            df = df[df["close"] > 0]
            df.to_parquet(out_path, index=False)
            print(f"  saved {len(df):,} rows -> {out_path}")

        spread_pct = (df["ask_close"] - df["close"]) / df["close"] * 100
        spread_pct = spread_pct[spread_pct >= 0]
        spread_report.append(
            (name, len(df), df["timestamp"].min(), df["timestamp"].max(),
             spread_pct.median(), spread_pct.quantile(0.95))
        )

    print("\n=== spread report (one-way, % of price) ===")
    for name, n, t0, t1, med, p95 in spread_report:
        print(f"{name:8s} rows={n:7,d}  {t0.date()} -> {t1.date()}  "
              f"median={med:.5f}%  p95={p95:.5f}%")


if __name__ == "__main__":
    sys.exit(main())
