# FinRisk-Lab  
**Portfolio Risk & Market Stress Intelligence Platform**
FinRisk-Lab is a modular Python-based risk analytics system designed to
quantify portfolio risk, diversification effects, and downside exposure
under both normal and stressed market conditions.

## Why FinRisk-Lab?

Most retail investors and many junior analysts focus on returns
while underestimating downside risk.

Key problems this project addresses:
- Volatility alone does not explain investor pain
- Diversification benefits disappear during market stress
- Correlations are ignored until they spike
- Many tools hide assumptions behind black boxes

FinRisk-Lab was built to answer one core question:

**“How bad can this portfolio get — and why?”**

## What This Project Is — and Is Not

This project **is**:
- A portfolio risk analytics system
- An explainable, modular risk engine
- A stress-testing and downside analysis framework

This project **is not**:
- A trading strategy
- A return prediction model
- A machine learning system
- A visualization-only dashboard

## System Architecture

Market Price Data  
→ Data Cleaning & Alignment  
→ Returns & Statistics  
→ Risk Metrics  
→ Portfolio Aggregation  
→ Stress Testing  
→ Visualization & Insights

Each layer is intentionally modular so that:
- Metrics can be reused independently
- Assumptions are explicit
- Failures occur early and loudly

## Key Risk Metrics

### Volatility
Used as a proxy for risk magnitude.
Rolling volatility is included to capture time-varying risk.

### Drawdown
Measures peak-to-trough loss.
Maximum drawdown represents the worst historical investor experience.

### Correlation Matrix
Shows how assets interact, especially during stress.
Correlation spikes explain diversification failures.

### Sharpe Ratio
Evaluates risk-adjusted return.
Explicitly guarded against zero volatility to avoid misleading results.

## Portfolio Risk & Diversification

Portfolio risk is not a weighted average of asset risk.

This project explicitly models:
- Weight constraints
- Asset risk contribution
- Diversification benefit
- Single-asset edge cases

Validation is enforced to prevent silent mispricing.

## Stress Testing & Scenario Analysis

Markets do not behave linearly under stress.

FinRisk-Lab includes:
- Market-wide crash scenarios
- Concentrated asset shocks
- Correlation breakdown scenarios

Stress inputs are constrained to realistic financial bounds.
The goal is not prediction, but understanding vulnerability.

## Defensive Design & Failure Handling

The system is designed to fail loudly rather than silently.

Examples:
- Portfolio weights are validated before aggregation
- Rolling metrics require sufficient data
- Sharpe ratios are undefined for zero volatility
- Single-asset portfolios bypass invalid diversification logic

This ensures analytical correctness under bad inputs.

## Assumptions & Limitations

- Historical prices are used as proxies for future risk
- Volatility and correlations are backward-looking
- Stress scenarios are hypothetical, not forecasts
- No transaction costs or liquidity constraints are modeled

## How to Run

1. Install dependencies  
   `pip install -r requirements.txt`

2. Configure assets and weights in `config/settings.py`

3. Run the pipeline  
   `python -m src.main`
