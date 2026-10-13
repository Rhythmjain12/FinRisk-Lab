"""
Stress Testing Engine

Purpose:
This module simulates adverse market scenarios to assess
portfolio vulnerability under extreme but plausible conditions.

Why stress testing matters:
Risk is not linear.
Portfolios that appear safe under normal conditions
can behave very differently during market stress.

Design choices:
- Stress scenarios are parameterized (see config/settings.py), not hard-coded.
- Shocks are constrained to realistic financial bounds.
- Correlation breakdown is modeled explicitly.
"""

import pandas as pd #type:ignore
import numpy as np #type:ignore
from config.settings import TRADING_DAYS_PER_YEAR, CORRELATION_STRESS
from src.portfolio.portfolio_engine import validate_weights

def calculate_stressed_assets_returns(betas,shock_amt):
    if not (-1.0 <= shock_amt <= 0):
        raise ValueError("Shock must be between -100% and 0%.")

    asset_stress_return = betas * shock_amt
    return asset_stress_return

def calculate_portfolio_loss(weights,asset_stress_returns):
    validate_weights(weights, asset_stress_returns.index.tolist())
    shocked_portfolio_ret= (pd.Series(weights)*asset_stress_returns).sum()
    return shocked_portfolio_ret

def calculate_concentration_stress_loss(weights,stress_amt):
    """Portfolio loss when one asset alone is shocked and the rest are flat.

    stress_amt : one shock for every asset (e.g. -0.40), or a Series/dict of
                 per-asset shocks.
    """
    validate_weights(weights, list(weights))
    portfolio_weights=pd.Series(weights)
    shocks=pd.Series(stress_amt, index=portfolio_weights.index, dtype=float)
    if shocks.isna().any() or not shocks.between(-1.0, 0).all():
        raise ValueError("Every shock must be between -100% and 0%.")
    # With every other return at zero, the portfolio loss is just weight x shock.
    return (portfolio_weights*shocks).to_dict()

def calculate_correlation_breakdown_volatility(corr_matrix,asset_vols,weights,stress=CORRELATION_STRESS):
    """Portfolio vol when every pairwise correlation moves ``stress`` of the
    way toward +1:  rho' = rho + stress * (1 - rho).

    stress=0 is the base case, stress=1 is "everything moves together" (the
    portfolio vol becomes the weighted-average asset vol). Unlike scaling
    rho by a constant, this always *raises* correlation (a negative rho is
    pulled up, not pushed further negative) and the result stays a valid
    (positive semi-definite) correlation matrix.
    """
    if not (0 <= stress <= 1):
        raise ValueError("Correlation stress must be between 0 and 1.")
    validate_weights(weights, corr_matrix.columns.tolist())
    stressed_corr_matrix=corr_matrix + stress*(1 - corr_matrix)
    # Align vols and weights to the matrix's column order: np.diag / np.dot are positional.
    D = np.diag(pd.Series(asset_vols).reindex(corr_matrix.columns))
    stressed_cov_matrix = D @ stressed_corr_matrix.values @ D
    weights_matrix=pd.Series(weights).reindex(corr_matrix.columns)
    breakdown_variance=np.dot(weights_matrix.T,np.dot(stressed_cov_matrix,weights_matrix))
    return np.sqrt(breakdown_variance)

def calculate_annual_correlation_breakdown_volatility(daily_breakdown_portfolio_vol, periods_per_year=TRADING_DAYS_PER_YEAR):
    return (daily_breakdown_portfolio_vol* np.sqrt(periods_per_year))

def calculate_worst_historical_returns(portfolio_returns, windows):
    """Worst compounded return the portfolio actually had over each rolling
    window. ``windows`` maps a label to a number of periods, e.g.
    {"worst_week": 5, "worst_month": 21} for daily data."""
    growth = np.log1p(portfolio_returns.dropna())
    out = {}
    for label, n in windows.items():
        if len(growth) >= n:
            out[label] = float(np.expm1(growth.rolling(n).sum().min()))
    return out
