from pathlib import Path
import pandas as pd #type:ignore
import numpy as np #type:ignore

def daily_returns(prices_df):
    if prices_df.empty:
        raise ValueError("Price data is empty after cleaning.")

    return prices_df.pct_change()

def daily_log_returns(prices_df):
    return np.log(prices_df).diff()
