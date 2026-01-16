import pandas as pd #type:ignore
import numpy as np #type:ignore
from config.settings import TRADING_DAYS_PER_YEAR

def calculate_sharpe(daily_returns,annual_vol):
    """
    Computes the annualized Sharpe ratio for each asset.

    Parameters:
    - daily_returns : pd.DataFrame
        Daily simple returns for each asset.
    - annual_vol : pd.Series
        Annualized volatility per asset.

    Returns:
    - pd.Series
        Sharpe ratio per asset.

    Notes:
    - Sharpe ratio is undefined for zero volatility.
    - Risk-free rate is configurable.
    """

    # Fail loudly here to avoid producing misleading Sharpe ratios
    if (annual_vol <= 0).any(): 
        raise ValueError("Sharpe ratio undefined when volatility is zero or negative.")

    annual_sharpe=(daily_returns.mean()*TRADING_DAYS_PER_YEAR)/annual_vol
    return annual_sharpe