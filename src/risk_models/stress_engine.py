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
- Stress scenarios are parameterized, not hard-coded.
- Shocks are constrained to realistic financial bounds.
- Correlation breakdown is modeled explicitly.
"""

import pandas as pd #type:ignore
import numpy as np #type:ignore

def calculate_stressed_assets_returns(betas,shock_amt):
    if not (-1.0 <= shock_amt <= 0):
        raise ValueError("Shock must be between -100% and 0%.")

    asset_stress_return = betas * shock_amt
    return asset_stress_return

def calculate_portfolio_loss(weights,asset_stress_returns):
    shocked_portfolio_ret= (pd.Series(weights)*asset_stress_returns).sum()
    return shocked_portfolio_ret

def calculate_concentration_stress_loss(weights,stress_amt):
    if not (-1.0 <= stress_amt <= 0):
        raise ValueError("Shock must be between -100% and 0%.")
                         
    portfolio_loss={}
    portfolio_weights=pd.Series(weights)
    for asset in portfolio_weights.index:
        zero_ret_series=pd.Series(0.0, index=portfolio_weights.index)#creating an all zero series for returns
        zero_ret_series.loc[asset] = stress_amt #changing retunr of 1 asset at atime to -40%
        portfolio_loss[asset]=(portfolio_weights*zero_ret_series).sum() #calucltion pf loss
    return portfolio_loss

def calculate_correlation_breakdown_volatility(corr_matrix,asset_vols,weights):
    stressed_corr_matrix=(corr_matrix*1.5).clip(-1, 1)
    D = np.diag(asset_vols)
    stressed_cov_matrix = D @ stressed_corr_matrix.values @ D
    weights_matrix=pd.Series(weights)
    daily_breakdown_portfolio_vol= np.sqrt(np.dot(weights_matrix.T,np.dot(stressed_cov_matrix,weights_matrix)))
    return daily_breakdown_portfolio_vol

def calculate_annual_correlation_breakdown_volatility(daily_breakdown_portfolio_vol):
    return (daily_breakdown_portfolio_vol* np.sqrt(252))