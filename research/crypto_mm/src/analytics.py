"""
Adverse selection analytics — the primary diagnostic per GATE.md G4 and G5.

Reads fills CSVs produced by simulator.py and computes:
- Fill-conditional forward returns at t+1,5,15,30,60min
- Adverse selection score (signed: negative = price moved against fill direction)
- Distribution of AS scores (not just mean — fat tails matter)

Usage:
    python src/analytics.py
    python src/analytics.py --pair MINAUSD

Interpretation key:
    AS_score < 0          → some adverse selection present (expected; zero would be impossible)
    AS_score < -0.15×spread → FAIL G4 (5min) or G5 (30min) gate
    AS_score < -0.50×spread → Informed flow dominant — close thread for this pair
"""

import argparse
import csv
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PAIRS = ["MINAUSD", "KAVAUSD", "ALGOUSD", "ICXUSD", "FILUSD"]


def load_fills(pair: str) -> list[dict]:
    path = DATA_DIR / f"{pair}_fills.csv"
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def signed_forward_return(fill: dict, horizon_min: int) -> float | None:
    """
    Returns the signed forward return from the perspective of adverse selection.

    For an ASK fill (we SOLD at fill_price):
        Adverse = price rises after we sold → return is NEGATIVE for us
        signed_fwd = -(px_after - fill_price) / fill_price

    For a BID fill (we BOUGHT at fill_price):
        Adverse = price falls after we bought → return is NEGATIVE for us
        signed_fwd = (px_after - fill_price) / fill_price

    So negative AS score always means "price moved against our position."
    """
    key = f"px_{horizon_min}m"
    if not fill.get(key):
        return None
    px_after = float(fill[key])
    fill_price = float(fill["fill_price"])
    if fill_price == 0:
        return None

    raw_return = (px_after - fill_price) / fill_price

    if fill["side"] == "ask_fill":
        return -raw_return   # we sold; rising price hurts us
    else:
        return raw_return    # we bought; falling price hurts us


def compute_as_stats(signed_returns: list[float]) -> dict:
    if not signed_returns:
        return {"n": 0, "mean": None, "median": None, "pct25": None, "pct75": None}
    n = len(signed_returns)
    sorted_r = sorted(signed_returns)
    mean = sum(signed_returns) / n
    median = sorted_r[n // 2]
    p25 = sorted_r[int(n * 0.25)]
    p75 = sorted_r[int(n * 0.75)]
    return {"n": n, "mean": round(mean * 100, 5), "median": round(median * 100, 5),
            "pct25": round(p25 * 100, 5), "pct75": round(p75 * 100, 5)}


def evaluate_gate(as_mean_pct: float | None, spread_pct: float,
                  horizon: int) -> str:
    if as_mean_pct is None:
        return "PENDING (no data)"
    threshold_4 = -0.15 * spread_pct  # G4: 5min
    threshold_5 = -0.30 * spread_pct  # G5: 30min
    hard_fail = -0.50 * spread_pct    # override fail

    threshold = threshold_4 if horizon == 5 else threshold_5
    if as_mean_pct < hard_fail:
        return f"FAIL (hard — informed flow dominant: {as_mean_pct:.4f}% < {hard_fail:.4f}%)"
    if as_mean_pct < threshold:
        return f"FAIL ({as_mean_pct:.4f}% < {threshold:.4f}%)"
    return f"PASS ({as_mean_pct:.4f}% > {threshold:.4f}%)"


def analyze_pair(pair: str, spread_pct: float) -> dict:
    fills = load_fills(pair)
    if not fills:
        print(f"[{pair}] No fills file found — run simulator.py first")
        return {}

    horizons = [1, 5, 15, 30, 60]
    as_by_horizon: dict[int, list[float]] = {h: [] for h in horizons}

    for fill in fills:
        for h in horizons:
            r = signed_forward_return(fill, h)
            if r is not None:
                as_by_horizon[h].append(r)

    print(f"\n{'=' * 60}")
    print(f" Adverse Selection Analysis: {pair}")
    print(f" Spread param: {spread_pct:.2f}%  |  Fills analyzed: {len(fills)}")
    print(f"{'=' * 60}")
    print(f"  {'Horizon':<10} {'N':>5} {'Mean%':>10} {'Median%':>10} "
          f"{'p25%':>10} {'p75%':>10}  Gate")
    print(f"  {'-'*80}")

    results = {}
    for h in horizons:
        stats = compute_as_stats(as_by_horizon[h])
        gate_label = ""
        if h in (5, 30):
            gate_label = evaluate_gate(stats.get("mean"), spread_pct, h)
        print(f"  t+{h}min     {stats['n']:>5}  {str(stats.get('mean','—')):>10}  "
              f"{str(stats.get('median','—')):>10}  {str(stats.get('pct25','—')):>10}  "
              f"{str(stats.get('pct75','—')):>10}  {gate_label}")
        results[h] = stats

    # Bid fills vs ask fills separately (diagnose asymmetric adverse selection)
    bid_fills = [f for f in fills if f["side"] == "bid_fill"]
    ask_fills = [f for f in fills if f["side"] == "ask_fill"]
    print(f"\n  Fill breakdown: {len(bid_fills)} bid fills, {len(ask_fills)} ask fills")

    if bid_fills and ask_fills:
        bid_5m = [signed_forward_return(f, 5) for f in bid_fills
                  if signed_forward_return(f, 5) is not None]
        ask_5m = [signed_forward_return(f, 5) for f in ask_fills
                  if signed_forward_return(f, 5) is not None]
        if bid_5m:
            print(f"  Bid-fill AS (t+5m): mean = {sum(bid_5m)/len(bid_5m)*100:.4f}%")
        if ask_5m:
            print(f"  Ask-fill AS (t+5m): mean = {sum(ask_5m)/len(ask_5m)*100:.4f}%")

    return {
        "pair": pair,
        "as_5m": results.get(5, {}).get("mean"),
        "as_30m": results.get(30, {}).get("mean"),
        "G4_pass": "PASS" in evaluate_gate(results.get(5, {}).get("mean"), spread_pct, 5),
        "G5_pass": "PASS" in evaluate_gate(results.get(30, {}).get("mean"), spread_pct, 30),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", help="Single pair to analyze")
    parser.add_argument("--spread", type=float, default=1.2,
                        help="Spread %% used in simulation (for gate thresholds)")
    args = parser.parse_args()

    pairs = [args.pair] if args.pair else PAIRS
    all_results = []

    for pair in pairs:
        r = analyze_pair(pair, args.spread)
        if r:
            all_results.append(r)

    print("\n\nAdverse Selection Gate Summary:")
    print(f"  {'Pair':<12} {'AS@5m%':>10} {'G4':>6} {'AS@30m%':>10} {'G5':>6}")
    print(f"  {'-' * 48}")
    full_pass = []
    for r in all_results:
        g4 = "PASS" if r.get("G4_pass") else "FAIL"
        g5 = "PASS" if r.get("G5_pass") else "FAIL"
        print(f"  {r['pair']:<12} {str(r.get('as_5m','—')):>10} {g4:>6} "
              f"{str(r.get('as_30m','—')):>10} {g5:>6}")
        if r.get("G4_pass") and r.get("G5_pass"):
            full_pass.append(r["pair"])

    print(f"\n  Pairs passing G4+G5: {full_pass if full_pass else 'none'}")
    print(f"\nUpdate GATE.md with these results and cross-reference simulator.py G1-G3/G6.")
    print("Final gate: ALL 6 criteria must pass on ≥ 2 pairs.")


if __name__ == "__main__":
    main()
