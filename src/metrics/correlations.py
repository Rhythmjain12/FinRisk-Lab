import pandas as pd #type:ignore
from config.settings import CORRELATION_METHOD


def calculate_correlation_matrix(returns_df):
    if returns_df.shape[1] == 1:
        raise ValueError("Correlation matrix undefined for single-asset portfolio.")

    corr_matrix = returns_df.corr(method=CORRELATION_METHOD)
    return corr_matrix