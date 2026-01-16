import pandas as pd  #type:ignore

def calculate_beta(stock_returns, market_returns):
    aligned = pd.concat(
        [stock_returns, market_returns],
        axis=1,
        join="inner"
    ).dropna()

    assets = aligned.iloc[:, :-1]
    market = aligned.iloc[:, -1]

    betas = {}

    for col in assets.columns:
        betas[col] = assets[col].cov(market) / market.var()

    return pd.Series(betas)


