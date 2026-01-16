"""
Volatility Metrics Module

Purpose:
This module computes daily, annualized, and rolling volatility measures
for financial return series.

Why volatility matters:
Volatility is the primary proxy for risk in financial markets.
It captures the magnitude of return fluctuations, not direction,
and is a core input into portfolio risk, Sharpe ratios, and stress testing.

Design choices:
- Log returns are used to ensure time-additivity.
- Annualization assumes a configurable number of trading days.
- Rolling volatility is included to capture time-varying risk.
"""

from pathlib import Path
import pandas as pd #type:ignore
import numpy as np #type:ignore
from config.settings import TRADING_DAYS_PER_YEAR
from config.settings import ROLLING_VOL_WINDOW

def calculate_daily_volatility(log_returns_df):
    if len(log_returns_df) < ROLLING_VOL_WINDOW:
        raise ValueError(
            f"Not enough data for rolling volatility. "
            f"Need at least {ROLLING_VOL_WINDOW} rows."
        )

    daily_std = log_returns_df.std()
    return  daily_std

def calculate_annual_volatility(daily_vol):
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    return annual_vol

def calculate_rolling_volatility(log_returns_df):
    rolling_std=log_returns_df.rolling(ROLLING_VOL_WINDOW).std()
    return rolling_std

def calculate_rolling_annual_volatility(rolling_std):
    rolling_annual_vol = rolling_std * np.sqrt(TRADING_DAYS_PER_YEAR)
    return rolling_annual_vol