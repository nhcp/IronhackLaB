"""
Market-maker simulator from trade-level data.

Assumptions (documented, conservative where overestimating):
- We post at mid ± (spread/2) where mid = EMA of recent trade prices
- Fill when a trade crosses our limit (OVERESTIMATES fill rate — ignores queue)
- Round-trip completes when both sides fill, or forced close after max_hold_min
- Forced close = taker fee (inventory risk penalty)
- Fill rate haircut applied post-simulation per GATE.md (60%)

Output: per-pair summary + fills CSV for analytics.py
"""

import argparse
import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Fee constants
MAKER_FEE_KRAKEN = 0.0038   # 0.38% retail tier
TAKER_FEE_KRAKEN = 0.0080   # 0.80% retail tier
MAKER_FEE_MEXC = 0.0000     # 0% maker
TAKER_FEE_MEXC = 0.0005     # 0.05% taker

FILL_RATE_HAIRCUT = 0.60    # paper: retail fill rate 54-65%, use 60%


@dataclass
class Config:
    spread_pct: float = 0.012       # 1.2% total spread posted (0.6% each side)
    ema_alpha: float = 0.15         # EMA weight for mid-price update
    max_hold_min: float = 20.0      # minutes before forced inventory close
    maker_fee: float = MAKER_FEE_KRAKEN
    taker_fee: float = TAKER_FEE_KRAKEN
    notional_per_fill: float = 50.0  # $50 per fill (capital cap)


@dataclass
class Fill:
    ts: float
    side: str           # "bid_fill" or "ask_fill"
    fill_price: float
    mid_at_fill: float
    future_prices: dict = field(default_factory=dict)  # {minutes: price}


def load_trades(pair: str) -> list[dict]:
    path = DATA_DIR / f"{pair}_trades.csv"
    if not path.exists():
        raise FileNotFoundError(f"No data for {pair} — run data_fetch.py first")
    with open(path) as f:
        return list(csv.DictReader(f))


def run_simulation(pair: str, cfg: Config) -> dict:
    trades = load_trades(pair)
    if len(trades) < 50:
        return {"pair": pair, "error": "insufficient trades (<50)"}

    prices = [float(t["price"]) for t in trades]
    timestamps = [float(t["timestamp"]) for t in trades]
    sides = [t["side"] for t in trades]

    # EMA mid-price seed
    mid = prices[0]

    pending_bid: dict | None = None   # {price, ts, mid_at_fill}
    pending_ask: dict | None = None

    fills: list[Fill] = []
    round_trips: list[dict] = []

    for i, (ts, px, side) in enumerate(zip(timestamps, prices, sides)):
        mid = cfg.ema_alpha * px + (1 - cfg.ema_alpha) * mid

        bid_limit = mid * (1 - cfg.spread_pct / 2)
        ask_limit = mid * (1 + cfg.spread_pct / 2)

        # Check forced close (max hold exceeded)
        for pending, close_side in [(pending_bid, "ask"), (pending_ask, "bid")]:
            if pending is None:
                continue
            age_min = (ts - pending["ts"]) / 60
            if age_min >= cfg.max_hold_min:
                # Force close at current price using taker order
                close_px = px
                if pending is pending_bid:
                    # We're long (bid filled), need to sell at market (taker)
                    gross = (close_px - pending["fill_price"]) / pending["fill_price"]
                    net = gross - cfg.maker_fee - cfg.taker_fee  # maker on entry, taker on exit
                else:
                    # We're short (ask filled), need to buy at market (taker)
                    gross = (pending["fill_price"] - close_px) / pending["fill_price"]
                    net = gross - cfg.maker_fee - cfg.taker_fee
                round_trips.append({
                    "ts": pending["ts"],
                    "type": "forced_close",
                    "gross_pct": gross,
                    "net_pct": net,
                    "hold_min": age_min,
                })
                if pending is pending_bid:
                    pending_bid = None
                else:
                    pending_ask = None

        # Check bid fill: a "sell" trade at or below our bid means someone sold to us
        if pending_bid is None and side == "s" and px <= bid_limit:
            pending_bid = {"price": bid_limit, "fill_price": px, "ts": ts, "mid": mid}
            fill = Fill(ts=ts, side="bid_fill", fill_price=px, mid_at_fill=mid)
            fills.append(fill)

        # Check ask fill: a "buy" trade at or above our ask means someone bought from us
        if pending_ask is None and side == "b" and px >= ask_limit:
            pending_ask = {"price": ask_limit, "fill_price": px, "ts": ts, "mid": mid}
            fill = Fill(ts=ts, side="ask_fill", fill_price=px, mid_at_fill=mid)
            fills.append(fill)

        # Check round-trip completion
        if pending_bid is not None and pending_ask is not None:
            # Both sides filled — collect spread
            gross = cfg.spread_pct  # full spread captured
            net = gross - 2 * cfg.maker_fee
            hold_min = (ts - min(pending_bid["ts"], pending_ask["ts"])) / 60
            round_trips.append({
                "ts": min(pending_bid["ts"], pending_ask["ts"]),
                "type": "complete",
                "gross_pct": gross,
                "net_pct": net,
                "hold_min": hold_min,
            })
            pending_bid = None
            pending_ask = None

    # Record future prices for fills (for analytics.py)
    horizons_min = [1, 5, 15, 30, 60]
    for fill in fills:
        for h in horizons_min:
            target_ts = fill.ts + h * 60
            # Find nearest trade at or after target_ts
            for j in range(len(timestamps)):
                if timestamps[j] >= target_ts:
                    fill.future_prices[h] = prices[j]
                    break

    # Summary statistics
    complete_rts = [r for r in round_trips if r["type"] == "complete"]
    forced_rts = [r for r in round_trips if r["type"] == "forced_close"]

    if not round_trips:
        return {"pair": pair, "error": "no round-trips generated"}

    span_days = (timestamps[-1] - timestamps[0]) / 86400
    fills_per_month = len(fills) / max(span_days, 1) * 30
    complete_per_month = len(complete_rts) / max(span_days, 1) * 30
    forced_per_month = len(forced_rts) / max(span_days, 1) * 30

    gross_spreads = [r["gross_pct"] * 100 for r in complete_rts]
    complete_net = [r["net_pct"] * 100 for r in complete_rts]
    forced_net = [r["net_pct"] * 100 for r in forced_rts]
    all_net = complete_net + forced_net

    mean_gross = sum(gross_spreads) / len(gross_spreads) if gross_spreads else 0
    mean_complete_net = sum(complete_net) / len(complete_net) if complete_net else 0
    mean_forced_net = sum(forced_net) / len(forced_net) if forced_net else 0
    mean_all_net = sum(all_net) / len(all_net) if all_net else 0

    # Fill-rate-adjusted monthly net: weight complete and forced by actual P&L,
    # then apply 60% haircut. Forced closes are real losses — include them.
    adj_complete_monthly = complete_per_month * FILL_RATE_HAIRCUT * mean_complete_net
    # Forced closes are exits NOT conditional on fill rate (already happened); treat as 1×
    adj_forced_monthly = forced_per_month * mean_forced_net
    adj_net_monthly_pct = adj_complete_monthly + adj_forced_monthly

    # Sharpe from ALL round trips (complete + forced), using percentage P&L per event
    if len(all_net) > 2:
        mean_r = mean_all_net
        var_r = sum((r - mean_r) ** 2 for r in all_net) / (len(all_net) - 1)
        std_r = math.sqrt(var_r) if var_r > 0.0001 else float("nan")
        rts_per_month = len(all_net) / max(span_days, 1) * 30
        sharpe = (mean_r / std_r * math.sqrt(rts_per_month)) if not math.isnan(std_r) else float("nan")
    else:
        sharpe = float("nan")

    result = {
        "pair": pair,
        "span_days": round(span_days, 1),
        "total_fills": len(fills),
        "fills_per_month": round(fills_per_month, 1),
        "adj_fills_per_month_60pct": round(fills_per_month * FILL_RATE_HAIRCUT, 1),
        "complete_rts": len(complete_rts),
        "forced_rts": len(forced_rts),
        "complete_per_month": round(complete_per_month, 1),
        "forced_per_month": round(forced_per_month, 1),
        "mean_gross_spread_pct": round(mean_gross, 4),
        "mean_complete_net_pct": round(mean_complete_net, 4),
        "mean_forced_net_pct": round(mean_forced_net, 4),
        "mean_all_net_pct": round(mean_all_net, 4),
        "adj_net_monthly_pct": round(adj_net_monthly_pct, 4),
        "monthly_sharpe_raw": round(sharpe, 3) if not math.isnan(sharpe) else float("nan"),
        "fee_regime": "kraken_retail" if cfg.maker_fee == MAKER_FEE_KRAKEN else "mexc",
        "spread_param_pct": cfg.spread_pct * 100,
        "fills": fills,  # raw fills for analytics.py
    }
    return result


def check_gate(result: dict, pair_spread_pct: float) -> dict:
    """Evaluate GATE.md criteria. Returns {criterion: pass/fail, overall: bool}."""
    gate = {}
    s = pair_spread_pct / 100

    gate["G1_fills_per_month"] = result.get("fills_per_month", 0) >= 10
    gate["G2_gross_spread_covers_fees"] = result.get("mean_gross_spread_pct", 0) > 0.76
    gate["G3_fill_adj_net_positive"] = result.get("adj_net_monthly_pct", 0) > 0
    # G4 and G5 are filled in by analytics.py
    gate["G4_as_5m"] = None   # pending analytics
    gate["G5_as_30m"] = None  # pending analytics
    sharpe = result.get("monthly_sharpe_raw", float("nan"))
    gate["G6_sharpe"] = (not math.isnan(sharpe)) and sharpe >= 0.5

    decided = [v for v in gate.values() if v is not None]
    gate["overall"] = all(decided) and len(decided) >= 4  # partial while AS pending
    return gate


def print_summary(result: dict, gate: dict) -> None:
    p = result["pair"]
    if "error" in result:
        print(f"\n[{p}] ERROR: {result['error']}")
        return

    print(f"\n{'=' * 55}")
    print(f" {p}  |  {result['span_days']} days  |  spread param {result['spread_param_pct']:.1f}%")
    print(f"{'=' * 55}")
    print(f"  Fills total:          {result['total_fills']:,}")
    print(f"  Fills/month (raw):    {result['fills_per_month']:.1f}")
    print(f"  Fills/month (60%):    {result['adj_fills_per_month_60pct']:.1f}")
    print(f"  Complete RTs/month:   {result['complete_per_month']:.1f}  (both sides fill)")
    print(f"  Forced closes/month:  {result['forced_per_month']:.1f}  (WARNING: one-sided, close at market)")
    print(f"  Mean gross spread:    {result['mean_gross_spread_pct']:.4f}%  (complete RTs only)")
    print(f"  Mean net (complete):  {result['mean_complete_net_pct']:.4f}%")
    print(f"  Mean net (forced):    {result['mean_forced_net_pct']:.4f}%  ← actual forced-close P&L")
    print(f"  Mean net (all):       {result['mean_all_net_pct']:.4f}%")
    print(f"  Adj net monthly:      {result['adj_net_monthly_pct']:.4f}%  (60% fill-rate haircut on complete)")
    sharpe_str = f"{result['monthly_sharpe_raw']:.3f}" if not math.isnan(result['monthly_sharpe_raw']) else "NaN (insufficient variance)"
    print(f"  Monthly Sharpe:       {sharpe_str}")
    print(f"  Fee regime:           {result['fee_regime']}")
    print(f"\n  Gate results:")
    for k, v in gate.items():
        if k == "overall":
            continue
        status = "PASS" if v is True else ("FAIL" if v is False else "PENDING")
        print(f"    {k}: {status}")
    print(f"  Overall gate: {'PASS (partial)' if gate['overall'] else 'FAIL / PENDING'}")


def save_fills_for_analytics(pair: str, fills: list[Fill]) -> None:
    out = DATA_DIR / f"{pair}_fills.csv"
    with open(out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "side", "fill_price", "mid_at_fill",
                         "px_1m", "px_5m", "px_15m", "px_30m", "px_60m"])
        for fill in fills:
            writer.writerow([
                fill.ts,
                fill.side,
                fill.fill_price,
                fill.mid_at_fill,
                fill.future_prices.get(1, ""),
                fill.future_prices.get(5, ""),
                fill.future_prices.get(15, ""),
                fill.future_prices.get(30, ""),
                fill.future_prices.get(60, ""),
            ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", help="Single pair to simulate")
    parser.add_argument("--spread", type=float, default=1.2,
                        help="Total spread %% to post (default 1.2)")
    parser.add_argument("--venue", choices=["kraken", "mexc"], default="kraken")
    args = parser.parse_args()

    pairs_to_run = ["MINAUSD", "KAVAUSD", "ALGOUSD", "ICXUSD", "FILUSD"]
    if args.pair:
        pairs_to_run = [args.pair]

    maker = MAKER_FEE_KRAKEN if args.venue == "kraken" else MAKER_FEE_MEXC
    taker = TAKER_FEE_KRAKEN if args.venue == "kraken" else TAKER_FEE_MEXC

    cfg = Config(spread_pct=args.spread / 100, maker_fee=maker, taker_fee=taker)

    all_gates = {}
    for pair in pairs_to_run:
        try:
            result = run_simulation(pair, cfg)
        except FileNotFoundError as e:
            print(f"\n[{pair}] {e}")
            continue

        gate = check_gate(result, args.spread)
        print_summary(result, gate)
        all_gates[pair] = gate

        if "fills" in result and result["fills"]:
            save_fills_for_analytics(pair, result["fills"])
            print(f"  Fills saved → data/{pair}_fills.csv (run analytics.py next)")

    print(f"\n\nGate summary ({args.venue}, spread={args.spread}%):")
    passing = [p for p, g in all_gates.items() if g.get("overall")]
    print(f"  Pairs with partial gate pass: {passing if passing else 'none'}")
    print(f"  Minimum required (G4/G5 pending analytics): 2 pairs")
    print("\nRun: python src/analytics.py  — to compute AS scores and finalize G4/G5")


if __name__ == "__main__":
    main()
