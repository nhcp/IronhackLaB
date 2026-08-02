"""
Fetch historical trade data for candidate pairs from Kraken public API.
Produces per-pair CSV: timestamp, price, volume, side (b=buy/s=sell).

Usage:
    python src/data_fetch.py                      # all 5 candidate pairs
    python src/data_fetch.py --pair MINAUSD       # single pair
    python src/data_fetch.py --days 180           # last N days only

Output: data/<PAIR>_trades.csv
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAIRS = ["MINAUSD", "KAVAUSD", "ALGOUSD", "ICXUSD", "FILUSD"]

BASE_URL = "https://api.kraken.com/0/public/Trades"
DATA_DIR = Path(__file__).parent.parent / "data"
RATE_LIMIT_SLEEP = 1.2  # seconds between API calls (Kraken: ~1 req/s public)


def fetch_trades_since(pair: str, since_ns: int) -> tuple[list[dict], int]:
    """Return (trades, last_timestamp_ns). Trades are raw Kraken tuples."""
    url = f"{BASE_URL}?pair={pair}&since={since_ns}&count=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "crypto-mm-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  HTTP error fetching {pair}: {e}", file=sys.stderr)
        return [], since_ns

    if data.get("error"):
        print(f"  Kraken API error for {pair}: {data['error']}", file=sys.stderr)
        return [], since_ns

    result = data.get("result", {})
    # Kraken returns trades under the pair key (possibly reformatted)
    pair_key = next((k for k in result if k != "last"), None)
    if not pair_key:
        return [], since_ns

    raw_trades = result[pair_key]
    last_ns = int(result.get("last", since_ns))

    trades = []
    for t in raw_trades:
        # Kraken trade tuple: [price, volume, time, buy/sell, market/limit, misc, trade_id]
        trades.append({
            "timestamp": float(t[2]),
            "price": float(t[0]),
            "volume": float(t[1]),
            "side": t[3],  # "b" or "s"
        })
    return trades, last_ns


def fetch_pair(pair: str, since_days: int | None, out_path: Path) -> int:
    if since_days is not None:
        now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
        since_ns = now_ns - int(since_days * 86400 * 1e9)
    else:
        since_ns = 0  # full history

    existing: list[dict] = []
    if out_path.exists():
        with open(out_path) as f:
            reader = csv.DictReader(f)
            existing = list(reader)
        if existing:
            # Resume from last timestamp
            last_ts = float(existing[-1]["timestamp"])
            since_ns = int(last_ts * 1e9) + 1
            print(f"  Resuming {pair} from {datetime.fromtimestamp(last_ts, timezone.utc)}")

    all_new: list[dict] = []
    call_count = 0
    prev_since = -1

    while True:
        if since_ns == prev_since:
            # Kraken returned same `last` twice — we're at the end
            break
        prev_since = since_ns

        trades, new_since = fetch_trades_since(pair, since_ns)
        if not trades:
            break

        all_new.extend(trades)
        since_ns = new_since
        call_count += 1

        if call_count % 10 == 0:
            last_dt = datetime.fromtimestamp(trades[-1]["timestamp"], timezone.utc)
            print(f"  {pair}: {len(all_new):,} trades fetched, up to {last_dt}")

        if len(trades) < 1000:
            # Fewer than 1000 returned means we've hit the current end
            break

        time.sleep(RATE_LIMIT_SLEEP)

    all_trades = existing + all_new
    if not all_trades:
        print(f"  {pair}: no trades found")
        return 0

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "price", "volume", "side"])
        writer.writeheader()
        writer.writerows(all_trades)

    print(f"  {pair}: {len(all_trades):,} total trades → {out_path.name}")
    return len(all_trades)


def quick_stats(pair: str, out_path: Path) -> None:
    """Print basic diagnostic stats after fetching."""
    if not out_path.exists():
        return
    with open(out_path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return

    prices = [float(r["price"]) for r in rows]
    ts = [float(r["timestamp"]) for r in rows]
    span_days = (ts[-1] - ts[0]) / 86400
    trades_per_day = len(rows) / max(span_days, 1)

    # Proxy for spread: mean absolute pct change between consecutive trades
    pct_changes = [abs(prices[i] / prices[i - 1] - 1) * 100 for i in range(1, len(prices))]
    median_jump = sorted(pct_changes)[len(pct_changes) // 2] if pct_changes else 0

    print(f"\n  [{pair}] stats:")
    print(f"    Trades total:    {len(rows):,}")
    print(f"    Date range:      {datetime.fromtimestamp(ts[0], timezone.utc).date()} "
          f"→ {datetime.fromtimestamp(ts[-1], timezone.utc).date()}")
    print(f"    Trades/day:      {trades_per_day:.1f}")
    print(f"    Price range:     ${min(prices):.4f} – ${max(prices):.4f}")
    print(f"    Median |jump|:   {median_jump:.4f}%  (spread proxy)")
    if trades_per_day < 5:
        print(f"    WARNING: <5 trades/day — pair is too thin for simulation")
    if median_jump < 0.30:
        print(f"    WARNING: spread proxy <0.30% — fee coverage unlikely on Kraken")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", help="Single Kraken pair to fetch (e.g. MINAUSD)")
    parser.add_argument("--days", type=int, help="Fetch only last N days of history")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pairs = [args.pair] if args.pair else PAIRS

    for pair in pairs:
        out_path = DATA_DIR / f"{pair}_trades.csv"
        print(f"\nFetching {pair}...")
        count = fetch_pair(pair, args.days, out_path)
        if count > 0:
            quick_stats(pair, out_path)

    print("\nDone. Run src/simulator.py next.")


if __name__ == "__main__":
    main()
