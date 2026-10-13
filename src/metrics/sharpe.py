import numpy as np #type:ignore
from config.settings import TRADING_DAYS_PER_YEAR, RISK_FREE_RATE, MIN_VOL_FOR_RATIOS

def calculate_sharpe(returns, risk_free_rate=RISK_FREE_RATE, periods_per_year=TRADING_DAYS_PER_YEAR):
    """
    Annualised Sharpe ratio per asset (DataFrame) or for one series (Series).

    Notes:
    - Numerator and denominator both come from ``returns`` (simple returns),
      so the ratio uses a single, consistent return type.
    - ``risk_free_rate`` is annual.
    - Sharpe is undefined for a (near-)zero-volatility series (cash, fixed
      deposit): those come back as NaN rather than a misleading huge number.
    """
    annual_return = returns.mean() * periods_per_year
    annual_vol = returns.std() * np.sqrt(periods_per_year)
    if np.ndim(annual_vol) == 0:
        return (annual_return - risk_free_rate) / annual_vol if annual_vol >= MIN_VOL_FOR_RATIOS else float("nan")
    return (annual_return - risk_free_rate) / annual_vol.where(annual_vol >= MIN_VOL_FOR_RATIOS)
