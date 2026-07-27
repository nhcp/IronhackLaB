"""FX walk-forward sweep runner.

Replicates the FlinkTrade research/sweep.py protocol with three changes:
per-symbol round-trip costs (measured-spread table in fx_data.py) instead
of global taker/maker constants, an overnight holding charge, and
per-symbol empirical Sharpe annualization.

Engine pieces (window builder, position/return decomposition, deterministic
combo selection, metric formulas, gate evaluator) are imported from
~/FlinkTrade/research so formulas stay byte-identical to every crypto
verdict. Cost columns: 'gated' (pessimistic; selection + gate evaluation)
and 'info' (median-spread; informational only).

Flat-window policy (v2 engine amendment, 2026-07-27): if no parameter
combo reaches min_trades_is in a window's IS slice, the strategy trades
FLAT (position 0) through that window's OOS period instead of aborting.
Rationale: nothing qualified in-sample, so nothing would be deployed
out-of-sample. The window is reported as flat=True.

Pre-registration is enforced against THIS repo: the gate JSON and family
module must be committed before a run. Results append to fx_sandbox's own
KILL_LOG.md.

Usage:
    python3 fx_sweep.py <gate_name>
"""
import argparse
import importlib.util
import itertools
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

FX_DIR = Path(__file__).resolve().parent
FLINK_RESEARCH = Path.home() / "FlinkTrade" / "research"
sys.path.insert(0, str(FX_DIR))
sys.path.insert(0, str(FLINK_RESEARCH))

from harness import (  # noqa: E402
    _sharpe, _max_drawdown, _cum_return_pct, _win_rate, evaluate_gate,
)
from sweep import build_windows, _positions_raw, select_best_combo  # noqa: E402
from fx_data import COSTS, OVERNIGHT_PER_NIGHT, load_ohlcv, bars_per_year  # noqa: E402

FAMILIES_DIR = FX_DIR / "families"
GATES_DIR    = FX_DIR / "gates"
KILL_LOG     = FX_DIR / "KILL_LOG.md"


def _git(args: list) -> str:
    return subprocess.run(
        ["git"] + args, cwd=FX_DIR, capture_output=True, text=True
    ).stdout.strip()


def _check_committed(*paths) -> None:
    dirty = [str(p) for p in paths if _git(["status", "--porcelain", str(p)])]
    if dirty:
        print(
            "not committed -- pre-register before running:\n  "
            + "\n  ".join(dirty),
            file=sys.stderr,
        )
        sys.exit(1)


def _overnight_charge(sp: pd.Series) -> pd.Series:
    days = pd.Series(sp.index.normalize(), index=sp.index).diff().dt.days.fillna(0)
    return OVERNIGHT_PER_NIGHT * days * (sp.abs() > 0).astype(float)


def _sr(sp, rv, switch, rt_cost):
    return sp * rv - rt_cost * switch - _overnight_charge(sp)


def _eval_is_combo(df_is, mod, params, ann, rt_cost):
    sp, rv, switch = _positions_raw(df_is, mod, params)
    if len(rv) < 2:
        return {"sharpe": -999.0, "num_trades": 0}
    sr = _sr(sp, rv, switch, rt_cost)
    return {"sharpe": _sharpe(sr, ann), "num_trades": int(switch.sum())}


def _flat_window(oos_df):
    """Zero-position series for an OOS window where no combo qualified."""
    rv = oos_df["close"].pct_change()
    rv = rv[rv.notna()]
    sp = pd.Series(0.0, index=rv.index)
    switch = pd.Series(False, index=rv.index)
    return sp, rv, switch


def _stitch(sp_l, rv_l, sw_l, bh_l, ann, oos_months, gated_cost, info_cost):
    sp     = pd.concat(sp_l)
    rv     = pd.concat(rv_l)
    switch = pd.concat(sw_l)
    bh     = pd.concat(bh_l)

    bh_eq = (1.0 + bh).cumprod()
    bh_sh = _sharpe(bh, ann)
    bh_dd = float(_max_drawdown(bh_eq) * 100.0)
    n_trades = int(switch.sum())
    tpm = n_trades / oos_months if oos_months > 0 else 0.0

    def _m(sr: pd.Series) -> dict:
        eq    = (1.0 + sr).cumprod()
        years = len(sr) / ann
        total = float((eq.iloc[-1] - 1.0) * 100.0)
        half  = len(sr) // 2
        return {
            "total_return":         total,
            "total_return_h1":      _cum_return_pct(sr.iloc[:half]),
            "total_return_h2":      _cum_return_pct(sr.iloc[half:]),
            "cagr": (((1.0 + total / 100.0) ** (1.0 / years)) - 1.0) * 100.0
                    if years > 0 else 0.0,
            "sharpe":               _sharpe(sr, ann),
            "max_dd":               float(_max_drawdown(eq) * 100.0),
            "sharpe_minus_buyhold": _sharpe(sr, ann) - bh_sh,
            "num_trades":           n_trades,
            "win_rate":             _win_rate(sp, sr),
            "trades_per_month":     tpm,
            "_bh_sharpe":           bh_sh,
            "_bh_max_dd":           bh_dd,
        }

    return _m(_sr(sp, rv, switch, gated_cost)), _m(_sr(sp, rv, switch, info_cost))


def sweep_symbol(df, mod, gate, symbol):
    is_m    = gate.get("is_months", 18)
    oos_m   = gate.get("oos_months", 6)
    step_m  = gate.get("step_months", 6)
    min_tr  = gate.get("min_trades_is", 30)
    grid    = gate["param_grid"]
    ann     = int(round(bars_per_year(df)))
    gated_c = COSTS[symbol]["gated"]
    info_c  = COSTS[symbol]["info"]

    names  = sorted(grid)
    combos = [dict(zip(names, c))
              for c in itertools.product(*[grid[k] for k in names])]

    windows = build_windows(df, is_m, oos_m, step_m)
    if not windows:
        raise ValueError(f"{symbol}: no complete walk-forward windows fit")

    reports = []
    n_flat = 0
    sp_l, rv_l, sw_l, bh_l = [], [], [], []
    for w in windows:
        cm = [(p, _eval_is_combo(w["is_df"], mod, p, ann, gated_c))
              for p in combos]
        best_p, best_is = select_best_combo(cm, min_tr)

        if best_p is None:
            sp, rv, switch = _flat_window(w["oos_df"])
            n_flat += 1
            flat = True
        else:
            sp, rv, switch = _positions_raw(w["oos_df"], mod, best_p)
            flat = False

        sp_l.append(sp); rv_l.append(rv)
        sw_l.append(switch); bh_l.append(rv.copy())
        srw = _sr(sp, rv, switch, gated_c)
        reports.append({
            "window_num":       w["window_num"],
            "oos_period":       (str(w["oos_start"].date()),
                                 str(w["oos_end"].date())),
            "flat":             flat,
            "selected_params":  best_p,
            "is_sharpe":        best_is["sharpe"] if best_is else 0.0,
            "oos_sharpe_gated": _sharpe(srw, ann),
            "oos_return_gated": float(((1.0 + srw).prod() - 1.0) * 100.0),
            "oos_trades":       int(switch.sum()),
        })

    oos_total = len(windows) * oos_m
    g_m, i_m = _stitch(sp_l, rv_l, sw_l, bh_l, ann, oos_total, gated_c, info_c)
    return {"windows": reports, "gated": g_m, "info": i_m,
            "ann": ann, "n_combos": len(combos), "n_flat": n_flat}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gate_name")
    args = ap.parse_args()

    gate_path = GATES_DIR / f"{args.gate_name}.json"
    if not gate_path.exists():
        print(f"gate not found: {gate_path}", file=sys.stderr)
        sys.exit(1)
    gate = json.loads(gate_path.read_text())
    fam_path = FAMILIES_DIR / f"{gate['family']}.py"
    _check_committed(gate_path, fam_path)

    spec = importlib.util.spec_from_file_location(gate["family"], fam_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    results, metrics_by_symbol = {}, {}
    for sym in gate["symbols"]:
        df = load_ohlcv(sym)
        res = sweep_symbol(df, mod, gate, sym)
        results[sym] = res
        metrics_by_symbol[sym] = res["gated"]
        print(f"\n=== {sym}  (ann={res['ann']}, "
              f"combos/window={res['n_combos']}, "
              f"flat_windows={res['n_flat']}) ===")
        for w in res["windows"]:
            if w["flat"]:
                print(f"  W{w['window_num']}: OOS {w['oos_period'][0]} -> "
                      f"{w['oos_period'][1]}  FLAT (no combo met min_trades_is)")
                continue
            print(f"  W{w['window_num']}: OOS {w['oos_period'][0]} -> "
                  f"{w['oos_period'][1]}  params={w['selected_params']}  "
                  f"IS_sh={w['is_sharpe']:+.2f}  "
                  f"OOS_sh={w['oos_sharpe_gated']:+.2f}  "
                  f"OOS_ret={w['oos_return_gated']:+.1f}%  "
                  f"trades={w['oos_trades']}")
        for tag in ("gated", "info"):
            m = res[tag]
            print(f"  [{tag:5}] total={m['total_return']:+.1f}%  "
                  f"h1={m['total_return_h1']:+.1f}%  "
                  f"h2={m['total_return_h2']:+.1f}%  "
                  f"sharpe={m['sharpe']:+.2f}  dd={m['max_dd']:.1f}%  "
                  f"WR={m['win_rate']*100:.1f}%  "
                  f"tpm={m['trades_per_month']:.1f}")

    cond_results, verdict = evaluate_gate(metrics_by_symbol, gate)
    print(f"\nVERDICT: {verdict}")
    for sym, res in cond_results.items():
        for cond, passed, actual in res:
            shown = f"{actual:+.3f}" if actual is not None else "n/a"
            print(f"  {sym}  {cond['metric']} {cond['operator']} "
                  f"{cond['threshold']}: {shown}  "
                  f"{'PASS' if passed else 'FAIL'}")

    commit = _git(["rev-parse", "HEAD"])
    with open(KILL_LOG, "a") as fh:
        fh.write(f"\n## {args.gate_name} -- {verdict} ({date.today()})\n")
        fh.write(f"commit {commit[:10]} | family {gate['family']} | "
                 f"symbols {','.join(gate['symbols'])}\n")
        for sym in gate["symbols"]:
            m = results[sym]["gated"]
            fh.write(f"- {sym} [gated]: total {m['total_return']:+.1f}%, "
                     f"sharpe {m['sharpe']:+.2f}, "
                     f"h1 {m['total_return_h1']:+.1f}%, "
                     f"h2 {m['total_return_h2']:+.1f}%, "
                     f"tpm {m['trades_per_month']:.1f}, "
                     f"WR {m['win_rate']*100:.1f}%, "
                     f"flat_windows {results[sym]['n_flat']}\n")
    print(f"\nappended to {KILL_LOG}")


if __name__ == "__main__":
    main()
