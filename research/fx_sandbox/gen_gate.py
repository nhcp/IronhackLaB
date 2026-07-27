"""Generate the wave-1 template gate JSON for one FX family.

Reads PARAM_GRID from families/<name>.py and writes gates/<name>_fx_v1.json.
Review the JSON, then commit it -- fx_sweep.py refuses to run uncommitted
gates. Template conditions: h1>0, h2>0, gated sharpe >= 0.5, trades/month
within the 30-500 band. pass_mode any_symbol: a family advances per
passing instrument.
"""
import importlib.util
import json
import sys
from pathlib import Path

FX_DIR = Path(__file__).resolve().parent


def main():
    fam = sys.argv[1]
    fam_path = FX_DIR / "families" / f"{fam}.py"
    spec = importlib.util.spec_from_file_location(fam, fam_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    gate = {
        "name": f"{fam}_fx_v1",
        "family": fam,
        "symbols": ["EURUSD", "XAUUSD", "SPX500", "GER40"],
        "timeframe": "1h",
        "is_months": 18,
        "oos_months": 6,
        "step_months": 6,
        "min_trades_is": 30,
        "pass_mode": "any_symbol",
        "param_grid": mod.PARAM_GRID,
        "conditions": [
            {"metric": "total_return_h1",  "operator": ">",  "threshold": 0},
            {"metric": "total_return_h2",  "operator": ">",  "threshold": 0},
            {"metric": "sharpe",           "operator": ">=", "threshold": 0.5},
            {"metric": "trades_per_month", "operator": ">=", "threshold": 30},
            {"metric": "trades_per_month", "operator": "<=", "threshold": 500},
        ],
        "cost_model": "fx_data.COSTS gated column + 0.01%/night held; "
                      "data pins in data/SHA256SUMS",
    }
    out = FX_DIR / "gates" / f"{fam}_fx_v1.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(gate, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
