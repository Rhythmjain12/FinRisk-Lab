def clean_prices(df):
    df_close =df.loc[:,("Close",slice(None))]
    df_close.columns=df_close.columns.droplevel(0)
    return align_prices(df_close)


def align_prices(prices):
    """Put every asset on one common calendar, loudly.

    - A column with no data at all (bad / delisted ticker) raises.
    - Gaps (an exchange holiday on one calendar but not another, a mutual-fund
      NAV not published that day) are forward-filled: the last known price is
      the best estimate of the value on that date.
    - Leading rows before the youngest asset's first price are dropped, so the
      whole window is one in which every asset actually existed.
    """
    empty = prices.columns[prices.isna().all()].tolist()
    if empty:
        raise ValueError(f"No price data returned for: {empty}")
    aligned = prices.sort_index().ffill().dropna(how="any")
    if len(aligned) < 30:
        raise ValueError(f"Only {len(aligned)} common price rows after alignment; need at least 30.")
    return aligned
