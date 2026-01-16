import json
from pathlib import Path
from config import settings
from src.ingestion.market_data import fetch_market_data
from src.preprocessing.cleaner import clean_prices
from src.metrics.returns import daily_returns, daily_log_returns
from src.metrics.volatility import (
    calculate_daily_volatility,
    calculate_annual_volatility,
    calculate_rolling_volatility,
    calculate_rolling_annual_volatility
)
from src.metrics.drawdown import calculate_drawdown
from src.metrics.correlations import calculate_correlation_matrix
from src.metrics.beta import calculate_beta
from src.metrics.sharpe import calculate_sharpe
from src.portfolio.portfolio_engine import (
    calculate_portfolio_returns,
    calculate_portfolio_annual_return,
    calculate_portfolio_value_series,
    calculate_daily_portfolio_volatility,
    calculate_annual_portfolio_volatility,
    calculate_diversification_benefit,
    calculate_asset_risk_contribution
)
from src.risk_models.stress_engine import (
    calculate_stressed_assets_returns,
    calculate_portfolio_loss,
    calculate_concentration_stress_loss,
    calculate_correlation_breakdown_volatility,
    calculate_annual_correlation_breakdown_volatility
)
from src.visualization.visuals import (
    plot_normalized_prices,
    plot_drawdowns_comparison,
    plot_correlation_heatmap,
    plot_risk_contribution,
    plot_stress_test,
    plot_asset_risk_return,
    plot_max_drawdown_comparison,
    plot_diversification_benefit
)

def main():
    # --- Configuration ---
    tickers = settings.ASSETS
    portfolio_weights = settings.PORTFOLIO_WEIGHTS
    start_date = settings.START_DATE
    end_date = settings.END_DATE

    # Ensure output directory exists
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    print("--- [FinRisk-Lab] Starting Analysis ---")

    # --- Phase 1: Ingestion ---
    print("Fetching market data...")
    data = fetch_market_data(
        ticker=tickers,
        start_date=start_date,
        end_date=end_date
    )
    
    # Save Raw Data
    raw_data_file = Path("data/raw/prices.csv")
    raw_data_file.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(raw_data_file)
    
    print("Cleaning data...")
    cleaned_data = clean_prices(data)
    
    # Save Cleaned Data
    clean_data_file = Path("data/processed/cleaned_prices.csv")
    clean_data_file.parent.mkdir(parents=True, exist_ok=True)
    cleaned_data.to_csv(clean_data_file)
    
    # --- Phase 2: Metrics ---
    print("Calculating risk metrics...")
    
    # Returns
    normal_returns = daily_returns(cleaned_data)
    log_returns = daily_log_returns(cleaned_data)
    
    # Volatility
    daily_volatility = calculate_daily_volatility(log_returns)
    annual_volatility = calculate_annual_volatility(daily_volatility)
    
    rolling_volatility = calculate_rolling_volatility(log_returns)
    rolling_annual_volatility = calculate_rolling_annual_volatility(rolling_volatility)
    
    # Drawdown
    asset_drawdowns, asset_max_drawdown = calculate_drawdown(cleaned_data)
    
    # Correlation
    correlation_matrix = calculate_correlation_matrix(normal_returns)
    
    # Benchmark (SENSEX) & Beta
    print("Fetching benchmark data...")
    benchmark_ticker = "^BSESN"
    benchmark_data = fetch_market_data(
        ticker=benchmark_ticker,
        start_date=start_date,
        end_date=end_date
    )
    benchmark_clean = clean_prices(benchmark_data)
    benchmark_returns = daily_returns(benchmark_clean)
    
    beta = calculate_beta(normal_returns, benchmark_returns)
    
    # Sharpe Ratio
    annual_sharpe = calculate_sharpe(normal_returns, annual_volatility)
    
    # --- Phase 3: Portfolio Engine ---
    print("Calculating portfolio analytics...")
    
    portfolio_daily_returns = calculate_portfolio_returns(normal_returns, portfolio_weights)
    portfolio_annual_return = calculate_portfolio_annual_return(portfolio_daily_returns)
    
    portfolio_daily_volatility = calculate_daily_portfolio_volatility(log_returns, portfolio_weights)
    portfolio_annual_volatility = calculate_annual_portfolio_volatility(portfolio_daily_volatility)
    
    diversification_benefit = calculate_diversification_benefit(
        annual_volatility, portfolio_weights, portfolio_annual_volatility
    )
    
    asset_risk_contribution = calculate_asset_risk_contribution(
        portfolio_weights, log_returns, portfolio_daily_volatility
    )
    
    # Portfolio Value and Drawdown
    portfolio_daily_value = calculate_portfolio_value_series(portfolio_daily_returns)
    portfolio_drawdown, portfolio_max_drawdown = calculate_drawdown(portfolio_daily_value)
    
    # --- Phase 4: Stress Testing ---
    print("Running stress tests...")
    
    # Full Market Shock (-20%)
    market_shock = -0.20
    stressed_assets_returns = calculate_stressed_assets_returns(beta, market_shock)
    stressed_portfolio_loss = calculate_portfolio_loss(portfolio_weights, stressed_assets_returns)
    
    # Concentrated Asset Shock (-40%)
    asset_shock = -0.40
    concentration_stress_loss = calculate_concentration_stress_loss(portfolio_weights, asset_shock)
    
    # Correlation Breakdown (Diversification Failure)
    portfolio_vol_diversification_failure = calculate_correlation_breakdown_volatility(
        correlation_matrix, daily_volatility, portfolio_weights
    )
    annual_portfolio_vol_diversification_failure = calculate_annual_correlation_breakdown_volatility(
        portfolio_vol_diversification_failure
    )
    
    # --- Phase 5: Visualization ---
    print("Generating visualizations...")
    
    plot_normalized_prices(cleaned_data, benchmark_clean)
    plot_drawdowns_comparison(
        asset_drawdowns, asset_max_drawdown, portfolio_drawdown, portfolio_max_drawdown
    )
    plot_correlation_heatmap(correlation_matrix)
    plot_risk_contribution(portfolio_weights, asset_risk_contribution)
    
    # Aggregate concentrated stress for plot
    concentration_portfolio_loss_agg = float(sum(concentration_stress_loss.values()))
    
    plot_stress_test(
        stresses_portfolio_returns=float(stressed_portfolio_loss),
        concentrated_portfolio_loss=concentration_portfolio_loss_agg,
        annual_portfolio_vol_diversification_failure=float(annual_portfolio_vol_diversification_failure),
        portfolio_max_drawdown=float(portfolio_max_drawdown)
    )
    
    plot_asset_risk_return(annual_volatility, annual_sharpe, beta)
    
    plot_max_drawdown_comparison(
        asset_max_drawdown=asset_max_drawdown,
        portfolio_max_drawdown=portfolio_max_drawdown
    )
    
    plot_diversification_benefit(
        annual_volatility, portfolio_weights, portfolio_annual_volatility
    )
    
    # --- Output Results ---
    results = {
        "portfolio_metrics": {
            "annual_return": float(portfolio_annual_return),
            "annual_volatility": float(portfolio_annual_volatility),
            "max_drawdown": float(portfolio_max_drawdown),
            "diversification_benefit": float(diversification_benefit)
        },
        "stress_test_results": {
            "market_shock_20pct_loss": float(stressed_portfolio_loss),
            "diversification_failure_volatility": float(annual_portfolio_vol_diversification_failure)
        },
        "asset_metrics": {
            "annual_volatility": annual_volatility.to_dict(),
            "sharpe_ratio": annual_sharpe.to_dict(),
            "beta": beta.to_dict(),
            "max_drawdown": asset_max_drawdown.to_dict()
        }
    }
    
    results_file = output_dir / "results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"Analysis Complete. Results saved to {results_file}")

if __name__ == "__main__":
    main()
