import numpy as np #type:ignore

def daily_returns(prices_df):
    if prices_df.empty:
        raise ValueError("Price data is empty after cleaning.")

    # fill_method=None: never invent a 0% return across a gap. Gaps must be
    # handled explicitly upstream (see preprocessing.cleaner.align_prices).
    return prices_df.pct_change(fill_method=None)

def daily_log_returns(prices_df):
    return np.log(prices_df).diff()
