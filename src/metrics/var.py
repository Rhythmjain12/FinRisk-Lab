"""
Value-at-Risk / Expected Shortfall (historical simulation).

Purpose:
Answers "how bad is a bad period?" from the empirical return distribution of
the portfolio at its *current* weights — no normality assumption.

- VaR(c)  : the loss exceeded in only (1 - c) of historical periods.
- CVaR(c) : the average loss in those worst (1 - c) periods (expected shortfall).

Both are returned as negative numbers (returns), per period of the input
series (daily or weekly). They are not scaled to other horizons here:
sqrt-time scaling assumes i.i.d. returns and understates fat tails.
"""

def calculate_historical_var_cvar(returns, confidence_levels):
    returns = returns.dropna()
    if len(returns) < 30:
        raise ValueError("Need at least 30 return observations for historical VaR.")
    out = {}
    for c in confidence_levels:
        var = returns.quantile(1 - c)
        out[c] = {"var": float(var), "cvar": float(returns[returns <= var].mean())}
    return out
