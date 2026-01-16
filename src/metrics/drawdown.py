"""
Drawdown Analysis Module

Purpose:
This module computes drawdowns and maximum drawdowns for assets
and portfolios.

Why drawdowns matter:
Volatility measures dispersion, but drawdown measures pain.
Maximum drawdown answers the question:
'What is the worst loss an investor would have experienced?'

Design choice:
- Drawdowns are computed relative to running peak values.
- This aligns with how investors psychologically experience losses.
"""

import pandas as pd #type:ignore

def calculate_drawdown(cleaned_prices):
    running_max=cleaned_prices.cummax()
    drawdown=(cleaned_prices-running_max)/running_max
    max_drawdown=drawdown.min()
    return drawdown,max_drawdown
