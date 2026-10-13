"""Regression test for the weight/covariance alignment fix.

The portfolio-volatility and risk-contribution helpers feed weights into a
positional ``np.dot`` against an alphabetically-sorted covariance matrix.
If the weights (dict-insertion order) are not aligned to the frame's column
order first, each weight lands on the wrong asset and the reported volatility
is wrong. These tests pin the correct, label-aligned behaviour.

Run:  cd FinRisk-Lab && venv/bin/python -m pytest test_alignment.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.portfolio.portfolio_engine import (
    calculate_daily_portfolio_volatility,
    calculate_asset_risk_contribution,
)


def _two_asset_log_returns():
    """A high-vol asset (HI) and a low-vol asset (LO).

    Columns come out sorted -> ['HI', 'LO'] is already sorted, so to force the
    misalignment we deliberately name them so sorted order differs from the
    order we pass the weights in below.
    """
    rng = np.random.default_rng(0)
    n = 300
    # 'AAA' is the low-vol asset, 'ZZZ' is the high-vol asset.
    # Sorted column order -> ['AAA', 'ZZZ']; we pass weights ZZZ-first.
    lo = rng.normal(0.0, 0.005, n)   # AAA: low vol
    hi = rng.normal(0.0, 0.050, n)   # ZZZ: high vol (10x)
    return pd.DataFrame({"AAA": lo, "ZZZ": hi})


def test_weights_aligned_by_label_not_position():
    log_returns = _two_asset_log_returns()
    # Weights in dict order ZZZ-first (opposite of sorted column order).
    # Heavy on the HIGH-vol asset -> portfolio vol must be close to ZZZ's vol.
    weights = {"ZZZ": 0.99, "AAA": 0.01}

    vol = calculate_daily_portfolio_volatility(log_returns, weights)

    # Correct (label-aligned) answer: dominated by the high-vol asset.
    hi_std = log_returns["ZZZ"].std()
    lo_std = log_returns["AAA"].std()
    assert vol == pytest.approx(hi_std, rel=0.05)

    # The buggy positional result would apply 0.99 to the LOW-vol asset,
    # producing a vol near lo_std. Ensure we are NOT anywhere near that.
    assert abs(vol - lo_std) > 0.5 * (hi_std - lo_std)


def test_portfolio_vol_matches_manual_aligned_quadratic_form():
    log_returns = _two_asset_log_returns()
    weights = {"ZZZ": 0.7, "AAA": 0.3}

    vol = calculate_daily_portfolio_volatility(log_returns, weights)

    # Manual, explicitly label-aligned reference.
    cov = log_returns.cov()
    ws = pd.Series(weights).reindex(log_returns.columns)
    expected = np.sqrt(ws.values @ cov.values @ ws.values)
    assert vol == pytest.approx(expected, rel=1e-12)


def test_risk_contribution_is_labelled_and_dominated_by_heavy_asset():
    log_returns = _two_asset_log_returns()
    weights = {"ZZZ": 0.99, "AAA": 0.01}

    port_vol = calculate_daily_portfolio_volatility(log_returns, weights)
    rc = calculate_asset_risk_contribution(weights, log_returns, port_vol)

    # Result must be labelled by asset (not positional garbage).
    assert set(rc.index) == {"AAA", "ZZZ"}
    # Risk contributions sum to the portfolio volatility (Euler allocation).
    assert rc.sum() == pytest.approx(port_vol, rel=1e-10)
    # The heavy high-vol asset must carry essentially all the risk.
    assert rc["ZZZ"] > rc["AAA"]
