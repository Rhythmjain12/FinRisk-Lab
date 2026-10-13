"""Parity fixture: a synthetic price panel plus what the Python engine says about it.

The TypeScript engine in web/src/engine must reproduce `expected` exactly
(test/parity.test.ts). Regenerate after changing the Python methodology:

    venv/bin/python web/test/make_fixture.py
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import main as app  # noqa: E402

rng = np.random.default_rng(42)
n = 700
dates = pd.bdate_range("2022-01-05", periods=n)          # starts on a Wednesday, ends mid-week
market = rng.normal(0.0004, 0.010, n)
prices = pd.DataFrame({
    "India Equity": 100 * np.cumprod(1 + 0.9 * market + rng.normal(0, 0.006, n)),
    "US Equity": 250 * np.cumprod(1 + 0.4 * market + rng.normal(0.0003, 0.012, n)),
    "Gold": 60 * np.cumprod(1 + rng.normal(0.0003, 0.008, n)),
    "Liquid Fund": 1000 * np.cumprod(1 + rng.normal(0.00025, 0.0002, n)),
    "Fixed Deposit": 1.07 ** ((dates - dates[0]).days / 365.25),
}, index=dates)
benchmark = pd.Series(18000 * np.cumprod(1 + market), index=dates)
benchmark.iloc[:7] = np.nan                               # benchmark history starts a little later

weights = {"India Equity": 0.30, "US Equity": 0.25, "Gold": 0.10, "Liquid Fund": 0.20, "Fixed Deposit": 0.15}
groups = {
    "Asset Class": {"India Equity": "Equity", "US Equity": "Equity", "Gold": "Gold", "Liquid Fund": "Debt", "Fixed Deposit": "Cash"},
    "Region": {"India Equity": "India", "US Equity": "International", "Gold": "India", "Liquid Fund": "India", "Fixed Deposit": "India"},
}

with tempfile.TemporaryDirectory() as tmp:
    app.analyse(
        prices, weights, benchmark.dropna(), output_dir=Path(tmp), benchmark_name="^NSEI",
        risk_free_rate=0.056, sample_rule="W-FRI", weights_as_of="end",
        groups={label: pd.Series(mapping) for label, mapping in groups.items()},
    )
    expected = json.loads((Path(tmp) / "results.json").read_text())

fixture = {
    "dates": [str(d.date()) for d in dates],
    "names": list(prices.columns),
    "rows": prices.to_numpy().tolist(),
    "benchmark": [None if np.isnan(v) else v for v in benchmark],
    "weights": weights,
    "groups": groups,
    "risk_free_rate": 0.056,
    "expected": expected,
}
out = Path(__file__).parent / "fixtures" / "parity.json"
out.write_text(json.dumps(fixture))
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
