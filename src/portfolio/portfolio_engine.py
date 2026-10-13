
"""
Portfolio Aggregation Engine

Purpose:
This module aggregates asset-level returns and risk metrics
into portfolio-level quantities using user-defined weights.

Why this exists:
Portfolio risk is not a simple average of asset risks.
Correlations, weights, and diversification effects matter.
This module explicitly models those interactions.

Design principles:
- Portfolio constraints are validated explicitly.
- Asset-level and portfolio-level logic are kept separate.
"""

import pandas as pd #type:ignore
import numpy as np #type:ignore
from config.settings import TRADING_DAYS_PER_YEAR

def validate_weights(weights: dict, assets: list):
    if set(weights.keys()) != set(assets):
        raise ValueError("Portfolio weights must match asset universe exactly.")

    total_weight = sum(weights.values())
    if abs(total_weight - 1) > 1e-6:
        raise ValueError(f"Portfolio weights must sum to 1. Current sum = {total_weight:.4f}")

    if any(w < 0 for w in weights.values()):
        raise ValueError("Portfolio weights cannot be negative.")


def calculate_portfolio_returns(asset_returns,weights):
    validate_weights(weights, asset_returns.columns.tolist())
    portfolio_daily_ret=(asset_returns*weights).sum(axis=1)
    return portfolio_daily_ret

def calculate_portfolio_cumulative_return(portfolio_daily_ret):
    """Total return over the full window: (1+r1)(1+r2)...(1+rn) - 1."""
    return (1 + portfolio_daily_ret).prod() - 1


def calculate_portfolio_cagr(portfolio_daily_ret):
    """Annualised compound growth rate over the calendar span of the series.

    Uses elapsed calendar time (not row_count / 252): exchanges do not all
    trade 252 days a year, and weekly data has 52 rows a year.
    """
    cumulative = (1 + portfolio_daily_ret).prod()
    idx = portfolio_daily_ret.index
    n_years = (idx[-1] - idx[0]).days / 365.25
    if n_years <= 0:
        return 0.0
    return cumulative ** (1 / n_years) - 1

def calculate_daily_portfolio_volatility(log_returns,weights):
    validate_weights(weights, log_returns.columns.tolist())
    cov_matrix=log_returns.cov()
    # Align weights to the frame's column order; np.dot is positional and would
    # otherwise apply each weight to the wrong asset (dict order != sorted columns).
    weights_matrix=pd.Series(weights).reindex(log_returns.columns)
    portfolio_vol= np.sqrt(np.dot(weights_matrix.T,np.dot(cov_matrix,weights_matrix)))
    return portfolio_vol

def calculate_annual_portfolio_volatility(portfolio_vol, periods_per_year=TRADING_DAYS_PER_YEAR):
    annual_portfolio_vol= portfolio_vol* np.sqrt(periods_per_year)
    return annual_portfolio_vol

def calculate_diversification_benefit(asset_vols,weights, portfolio_vol):
    validate_weights(weights, asset_vols.index.tolist())
    if len(weights) == 1:
        return 0.0
    naive_vol=(asset_vols*pd.Series(weights)).sum()
    divers_benefit=naive_vol-portfolio_vol
    return divers_benefit

def calculate_asset_risk_contribution(weights,log_returns,portfolio_vol):
    validate_weights(weights,log_returns.columns.tolist())
    cov_matrix=log_returns.cov()
    # Align weights to the frame's column order before the positional np.dot.
    weights_aligned=pd.Series(weights).reindex(log_returns.columns)
    MRC=pd.Series(np.dot(cov_matrix,weights_aligned)/portfolio_vol, index=cov_matrix.columns)
    risk_contri=weights_aligned*MRC
    return risk_contri

def calculate_portfolio_value_series(portfolio_daily_ret):
    initial_value=1
    portfolio_daily_value=(initial_value + portfolio_daily_ret).cumprod()
    return portfolio_daily_value

def calculate_buy_and_hold_value_series(prices, weights, weights_as_of="start"):
    """Value of a basket that is bought once and never rebalanced.

    weights_as_of="start": weights describe the basket on the first day
                           (a model portfolio you set up and left alone).
    weights_as_of="end"  : weights describe the basket today (a holdings
                           statement); units are held fixed backwards in time.
    Winners drift to larger weights, so this can differ a lot from the
    constant-weight (daily-rebalanced) series for a concentrated portfolio.
    """
    validate_weights(weights, prices.columns.tolist())
    anchor = prices.iloc[0] if weights_as_of == "start" else prices.iloc[-1]
    value = (prices / anchor * pd.Series(weights)).sum(axis=1)
    return value / value.iloc[0]
