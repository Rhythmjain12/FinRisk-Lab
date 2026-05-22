
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


def calculate_portfolio_cagr(portfolio_daily_ret, trading_days_per_year=252):
    """Annualised compound growth rate derived from cumulative return."""
    cumulative = (1 + portfolio_daily_ret).prod()
    n_years = len(portfolio_daily_ret) / trading_days_per_year
    if n_years <= 0:
        return 0.0
    return cumulative ** (1 / n_years) - 1

def calculate_daily_portfolio_volatility(log_returns,weights):
    validate_weights(weights, log_returns.columns.tolist())
    cov_matrix=log_returns.cov()
    weights_matrix=pd.Series(weights)
    portfolio_vol= np.sqrt(np.dot(weights_matrix.T,np.dot(cov_matrix,weights_matrix)))
    return portfolio_vol

def calculate_annual_portfolio_volatility(portfolio_vol):
    annual_portfolio_vol= portfolio_vol* np.sqrt(252)
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
    MRC=np.dot(cov_matrix,pd.Series(weights))/portfolio_vol
    risk_contri=pd.Series(weights)*MRC
    return risk_contri

def calculate_portfolio_value_series(portfolio_daily_ret):
    initial_value=1
    portfolio_daily_value=(initial_value + portfolio_daily_ret).cumprod()
    return portfolio_daily_value
