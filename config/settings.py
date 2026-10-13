# config/settings.py 

ASSETS = ["SHAKTIPUMP.NS", "WABAG.NS","NATCOPHARM.NS","DLF.NS","SUNPHARMA.NS","SUZLON.NS"] 
PORTFOLIO_WEIGHTS = {"SHAKTIPUMP.NS": 0.67, "WABAG.NS": 0.17,"SUNPHARMA.NS": 0.03,"NATCOPHARM.NS": 0.07,"DLF.NS": 0.03,"SUZLON.NS": 0.03} 

START_DATE = "2023-01-01" 
END_DATE = "2026-01-05" 
CONFIDENCE_LEVELS = [0.95, 0.99]

# Time & Market Assumptions
TRADING_DAYS_PER_YEAR = 252

# Rolling Windows
ROLLING_VOL_WINDOW = 21

# Risk-Free Rate (annual). India 91-day T-bill cut-off yield, RBI auction of
# 7 Oct 2026 = 5.57%. Update when rates move; override per run with --rf.
RISK_FREE_RATE = 0.056

# Benchmark for beta and the market-shock stress
BENCHMARK_TICKER = "^BSESN"
BENCHMARK_NAME = "SENSEX"

# Stress scenarios
MARKET_SHOCK = -0.20        # benchmark falls 20%; each asset falls beta x shock
ASSET_SHOCK = -0.40         # one holding alone falls 40%...
ASSET_SHOCK_VOL_CAP = 3     # ...but never more than 3x its own annual volatility
CORRELATION_STRESS = 0.5    # correlations move halfway toward +1

# Correlation Settings
CORRELATION_METHOD = "pearson"

# Below this annual volatility an asset is treated as riskless (cash, FD):
# its Sharpe ratio and correlations are noise, so they are not reported.
MIN_VOL_FOR_RATIOS = 0.001
