import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np #type:ignore
import pandas as pd #type:ignore

from config import settings
from src.ingestion.market_data import fetch_market_data, fetch_quote_currency
from src.ingestion.holdings import load_holdings, build_inr_prices, search_funds
from src.preprocessing.cleaner import clean_prices
from src.metrics.returns import daily_returns
from src.metrics.volatility import (
    calculate_daily_volatility,
    calculate_annual_volatility
)
from src.metrics.drawdown import calculate_drawdown
from src.metrics.correlations import calculate_correlation_matrix
from src.metrics.beta import calculate_beta
from src.metrics.sharpe import calculate_sharpe
from src.metrics.var import calculate_historical_var_cvar
from src.portfolio.portfolio_engine import (
    calculate_portfolio_returns,
    calculate_portfolio_cumulative_return,
    calculate_portfolio_cagr,
    calculate_portfolio_value_series,
    calculate_buy_and_hold_value_series,
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
    calculate_annual_correlation_breakdown_volatility,
    calculate_worst_historical_returns
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

ROOT = Path(__file__).resolve().parents[1]


def analyse(prices, weights, benchmark_prices, *, output_dir, benchmark_name,
            risk_free_rate, sample_rule=None, weights_as_of="start", groups=None):
    """Run every metric, stress test and chart for one portfolio.

    prices           : daily prices, one column per asset, one currency, no gaps
    weights          : dict asset -> weight (sums to 1)
    benchmark_prices : daily benchmark prices (same currency)
    sample_rule      : None -> risk statistics from daily returns (252/yr).
                       "W-FRI" -> from weekly returns (52/yr). Use weekly when
                       assets trade on different calendars or time zones: a
                       US close and an Indian close on the same date are ~10
                       hours apart, which biases daily correlations toward 0
                       and overstates diversification.
    weights_as_of    : "start" or "end" -- see calculate_buy_and_hold_value_series
    groups           : optional {label: Series(asset -> group)} for roll-ups
    Returns (results dict, list of plotly figures).
    """
    if sample_rule:
        periods = 52
        sampled_prices = _complete_periods(prices, sample_rule)
        sampled_benchmark = _complete_periods(benchmark_prices, sample_rule)
        rows_per_year = 261   # the holdings calendar has every weekday
    else:
        periods = rows_per_year = settings.TRADING_DAYS_PER_YEAR
        sampled_prices, sampled_benchmark = prices, benchmark_prices
    period_name = "week" if sample_rule else "day"

    # --- Asset metrics (all risk statistics use simple returns at the sampled frequency) ---
    returns = daily_returns(sampled_prices).iloc[1:]
    period_volatility = calculate_daily_volatility(returns)
    annual_volatility = calculate_annual_volatility(period_volatility, periods)
    riskless = annual_volatility < settings.MIN_VOL_FOR_RATIOS  # cash, fixed deposits

    asset_drawdowns, asset_max_drawdown = calculate_drawdown(prices)

    correlation_matrix = calculate_correlation_matrix(returns)
    # A (near-)constant series has no meaningful correlation; show 0, not float noise.
    correlation_matrix.loc[riskless, :] = 0.0
    correlation_matrix.loc[:, riskless] = 0.0
    np.fill_diagonal(correlation_matrix.values, 1.0)

    benchmark_returns = daily_returns(sampled_benchmark.to_frame(benchmark_name)).iloc[1:]
    beta = calculate_beta(returns, benchmark_returns)

    annual_sharpe = calculate_sharpe(returns, risk_free_rate, periods)

    # --- Portfolio ---
    # Constant-weight series: today's weights applied to every historical day.
    # This is the standard basis for "how risky is the portfolio I hold now".
    # (The first row has no return and sums to 0, so the series spans the full window.)
    portfolio_daily_returns = calculate_portfolio_returns(daily_returns(prices), weights)
    portfolio_cumulative_return = calculate_portfolio_cumulative_return(portfolio_daily_returns)
    portfolio_cagr = calculate_portfolio_cagr(portfolio_daily_returns)
    portfolio_daily_value = calculate_portfolio_value_series(portfolio_daily_returns)
    portfolio_drawdown, portfolio_max_drawdown = calculate_drawdown(portfolio_daily_value)

    # Buy-and-hold series: no rebalancing, weights drift with prices.
    buy_hold_value = calculate_buy_and_hold_value_series(prices, weights, weights_as_of)
    _, buy_hold_max_drawdown = calculate_drawdown(buy_hold_value)

    portfolio_returns = calculate_portfolio_returns(returns, weights)
    portfolio_period_volatility = calculate_daily_portfolio_volatility(returns, weights)
    portfolio_annual_volatility = calculate_annual_portfolio_volatility(portfolio_period_volatility, periods)
    portfolio_sharpe = calculate_sharpe(portfolio_returns, risk_free_rate, periods)
    portfolio_beta = float((pd.Series(weights) * beta).sum())

    diversification_benefit = calculate_diversification_benefit(
        annual_volatility, weights, portfolio_annual_volatility
    )
    asset_risk_contribution = calculate_asset_risk_contribution(
        weights, returns, portfolio_period_volatility
    )
    risk_contribution_pct = asset_risk_contribution / asset_risk_contribution.sum() * 100

    var_cvar = calculate_historical_var_cvar(portfolio_returns, settings.CONFIDENCE_LEVELS)

    # --- Stress tests ---
    stressed_assets_returns = calculate_stressed_assets_returns(beta, settings.MARKET_SHOCK)
    stressed_portfolio_loss = calculate_portfolio_loss(weights, stressed_assets_returns)

    # A flat -40% is an equity-sized shock. Cap it at a 3-sigma annual move for
    # each asset so a liquid fund or fixed deposit is not "crashed" by 40%.
    asset_shocks = (-settings.ASSET_SHOCK_VOL_CAP * annual_volatility).clip(lower=settings.ASSET_SHOCK)
    concentration_stress_loss = calculate_concentration_stress_loss(weights, asset_shocks)
    worst_asset = min(concentration_stress_loss, key=concentration_stress_loss.get)

    correlation_stress_volatility = calculate_annual_correlation_breakdown_volatility(
        calculate_correlation_breakdown_volatility(correlation_matrix, period_volatility, weights),
        periods,
    )

    worst_historical = calculate_worst_historical_returns(
        portfolio_daily_returns,
        {"worst_week": 5, "worst_month": round(rows_per_year / 12), "worst_year": rows_per_year}
    )

    # --- Results (written before any chart is drawn, so a chart failure cannot lose the numbers) ---
    results = {
        "run": {
            "window_start": str(prices.index[0].date()),
            "window_end": str(prices.index[-1].date()),
            "return_frequency": "weekly" if sample_rule else "daily",
            "periods_per_year": periods,
            "risk_free_rate": risk_free_rate,
            "benchmark": benchmark_name,
            "observations": int(len(returns)),
        },
        "portfolio_metrics": {
            "cumulative_return": float(portfolio_cumulative_return),
            "cagr": float(portfolio_cagr),
            "annual_volatility": float(portfolio_annual_volatility),
            "sharpe_ratio": float(portfolio_sharpe),
            "beta": portfolio_beta,
            "max_drawdown": float(portfolio_max_drawdown),
            "max_drawdown_buy_and_hold": float(buy_hold_max_drawdown),
            "diversification_benefit": float(diversification_benefit),
            f"value_at_risk_1_{period_name}": {
                f"{int(c * 100)}pct": v for c, v in var_cvar.items()
            },
        },
        "stress_test_results": {
            "market_shock": settings.MARKET_SHOCK,
            "market_shock_loss": float(stressed_portfolio_loss),
            "single_asset_shock": asset_shocks.to_dict(),
            "single_asset_shock_per_asset": {k: float(v) for k, v in concentration_stress_loss.items()},
            "worst_single_asset_shock_loss": float(concentration_stress_loss[worst_asset]),
            "worst_single_asset": worst_asset,
            "correlation_stress": settings.CORRELATION_STRESS,
            "correlation_stress_volatility": float(correlation_stress_volatility),
            "historical": worst_historical,
        },
        "asset_metrics": {
            "weight": {k: float(v) for k, v in weights.items()},
            "annual_volatility": annual_volatility.to_dict(),
            "sharpe_ratio": annual_sharpe.to_dict(),
            "beta": beta.to_dict(),
            "max_drawdown": asset_max_drawdown.to_dict(),
            "risk_contribution_pct": risk_contribution_pct.to_dict(),
        },
    }

    weight_series = pd.Series(weights)
    grouped = {}
    for label, mapping in (groups or {}).items():
        grouped[label] = pd.DataFrame({
            "weight_pct": weight_series.groupby(mapping).sum() * 100,
            "risk_contribution_pct": risk_contribution_pct.groupby(mapping).sum(),
        })
        results.setdefault("exposure", {})[label] = grouped[label].to_dict(orient="index")

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "results.json", "w") as f:
        # NaN (e.g. Sharpe of cash) is not valid JSON; write null instead.
        json.dump(_nan_to_none(results), f, indent=4)

    # --- Charts ---
    # Per-asset panels stop being readable past ~12 rows: show the largest holdings.
    top = weight_series.sort_values(ascending=False).index[:12]
    scenario_losses = {
        f"{benchmark_name} {settings.MARKET_SHOCK:.0%} (beta-scaled)": float(stressed_portfolio_loss),
        f"{worst_asset} alone {asset_shocks[worst_asset]:.0%}": float(concentration_stress_loss[worst_asset]),
        f"1-{period_name} VaR 99%": var_cvar[0.99]["var"] if 0.99 in var_cvar else min(v["var"] for v in var_cvar.values()),
    }
    if "worst_month" in worst_historical:
        scenario_losses["Worst historical month"] = worst_historical["worst_month"]
    if "worst_year" in worst_historical:
        scenario_losses["Worst historical 12 months"] = worst_historical["worst_year"]

    figures = [
        plot_normalized_prices(prices[top], benchmark_prices.to_frame(benchmark_name), benchmark_name),
        plot_drawdowns_comparison(asset_drawdowns[top], portfolio_drawdown),
        plot_correlation_heatmap(correlation_matrix),
        plot_risk_contribution(weights, asset_risk_contribution),
        plot_stress_test(scenario_losses, float(portfolio_max_drawdown)),
        plot_asset_risk_return(annual_volatility, annual_sharpe, beta),
        plot_max_drawdown_comparison(asset_max_drawdown, portfolio_max_drawdown),
        plot_diversification_benefit(annual_volatility, weights, portfolio_annual_volatility),
    ]
    for label, table in grouped.items():
        figures.append(plot_risk_contribution(
            (table["weight_pct"] / 100).to_dict(), table["risk_contribution_pct"], label
        ))
    return results, figures


def _complete_periods(prices, rule):
    """Last price of each period, without the unfinished current period
    (a 2-day stub would otherwise be counted as a full weekly return)."""
    sampled = prices.resample(rule).last().dropna()
    return sampled.iloc[:-1] if sampled.index[-1] > prices.index[-1] else sampled


def _nan_to_none(obj):
    if isinstance(obj, dict):
        return {str(k): _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def run_settings_portfolio(risk_free_rate):
    """The model portfolio in config/settings.py (single market, daily returns)."""
    print("Fetching market data...")
    data = fetch_market_data(settings.ASSETS, settings.START_DATE, settings.END_DATE)

    raw_data_file = ROOT / "data/raw/prices.csv"
    raw_data_file.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(raw_data_file)

    print("Cleaning data...")
    cleaned_data = clean_prices(data)

    clean_data_file = ROOT / "data/processed/cleaned_prices.csv"
    clean_data_file.parent.mkdir(parents=True, exist_ok=True)
    cleaned_data.to_csv(clean_data_file)

    print("Fetching benchmark data...")
    benchmark = clean_prices(
        fetch_market_data(settings.BENCHMARK_TICKER, settings.START_DATE, settings.END_DATE)
    ).iloc[:, 0]

    print("Calculating risk metrics and stress tests...")
    output_dir = ROOT / "outputs"
    _, figures = analyse(
        cleaned_data, settings.PORTFOLIO_WEIGHTS, benchmark,
        output_dir=output_dir, benchmark_name=settings.BENCHMARK_NAME,
        risk_free_rate=risk_free_rate, weights_as_of="start",
    )
    print("Generating visualizations...")
    for fig in figures:
        fig.show()
    return output_dir


def run_holdings_portfolio(path, years, risk_free_rate, benchmark_ticker):
    """A real mixed portfolio from a holdings CSV, analysed in INR on weekly returns."""
    holdings = load_holdings(path)
    if years <= 0:
        raise ValueError("--years must be positive.")
    end = date.today()  # exclusive: today's partial bar is not used
    start = pd.Timestamp(end) - pd.Timedelta(days=round(years * 365.25))
    start_date, end_date = str(start.date()), str(end)

    print(f"Fetching prices for {len(holdings)} holdings...")
    prices, values = build_inr_prices(holdings, start_date, end_date)
    weights = (values / values.sum()).to_dict()

    print("Fetching benchmark data...")
    benchmark = fetch_inr_benchmark(benchmark_ticker, start_date, end_date, prices.index)

    print("Calculating risk metrics and stress tests...")
    output_dir = ROOT / "outputs" / Path(path).stem
    by_name = holdings.set_index("name")
    results, figures = analyse(
        prices, weights, benchmark,
        output_dir=output_dir, benchmark_name=benchmark_ticker,
        risk_free_rate=risk_free_rate, sample_rule="W-FRI", weights_as_of="end",
        groups={"Asset Class": by_name["asset_class"], "Region": by_name["region"],
                "Currency": by_name["currency"]},
    )

    prices.to_csv(output_dir / "prices_inr.csv")
    results["run"]["total_value_inr"] = float(values.sum())
    results["asset_metrics"]["value_inr"] = values.to_dict()
    with open(output_dir / "results.json", "w") as f:
        json.dump(_nan_to_none(results), f, indent=4)

    write_html_report(results, figures, output_dir / "report.html")
    print_summary(results)
    print(f"Report: {output_dir / 'report.html'}")
    return output_dir


def fetch_inr_benchmark(ticker, start_date, end_date, calendar):
    """Benchmark prices in INR on the portfolio's calendar. A foreign index
    (e.g. ^GSPC) is converted, so beta compares INR returns with INR returns."""
    currency, scale = fetch_quote_currency(ticker)
    benchmark = fetch_market_data(ticker, start_date, end_date)["Close"].iloc[:, 0] * scale
    benchmark = benchmark.reindex(calendar.union(benchmark.index)).ffill().reindex(calendar)
    if currency != "INR":
        fx = fetch_market_data(f"{currency}INR=X", start_date, end_date)["Close"].iloc[:, 0]
        benchmark = benchmark * fx.reindex(calendar.union(fx.index)).ffill().reindex(calendar)
    return benchmark.dropna()


def print_summary(results):
    run, pm, st = results["run"], results["portfolio_metrics"], results["stress_test_results"]
    var_key = next(k for k in pm if k.startswith("value_at_risk"))
    print(f"\n  Window            {run['window_start']} to {run['window_end']} ({run['return_frequency']} returns)")
    if "total_value_inr" in run:
        print(f"  Total value       INR {run['total_value_inr']:,.0f}")
    print(f"  CAGR              {pm['cagr']:.1%}   (today's weights, backcast)")
    print(f"  Annual volatility {pm['annual_volatility']:.1%}")
    print(f"  Sharpe ratio      {pm['sharpe_ratio']:.2f}   (rf {run['risk_free_rate']:.1%})")
    print(f"  Beta vs {run['benchmark']:<10}{pm['beta']:.2f}")
    print(f"  Max drawdown      {pm['max_drawdown']:.1%}   (buy-and-hold {pm['max_drawdown_buy_and_hold']:.1%})")
    for level, v in pm[var_key].items():
        print(f"  {var_key.replace('value_at_risk_', 'VaR ').replace('_', '-')} {level:<6}{v['var']:.1%}   (CVaR {v['cvar']:.1%})")
    print(f"  {run['benchmark']} {st['market_shock']:.0%} shock  {st['market_shock_loss']:.1%}   (beta-scaled)")
    print(f"  Worst single-holding shock  {st['worst_single_asset_shock_loss']:.1%}   ({st['worst_single_asset']})")
    for label, table in results.get("exposure", {}).items():
        print(f"\n  By {label}:" + "".join(
            f"\n    {name:<22} weight {row['weight_pct']:5.1f}%   risk {row['risk_contribution_pct']:5.1f}%"
            for name, row in table.items()))
    print()


def write_html_report(results, figures, path):
    """One self-contained page: headline numbers, per-holding table, every chart."""
    run, pm, am = results["run"], results["portfolio_metrics"], results["asset_metrics"]
    var_key = next(k for k in pm if k.startswith("value_at_risk"))
    pct = lambda v: "n/a" if v is None or v != v else f"{v:.1%}"
    num = lambda v: "n/a" if v is None or v != v else f"{v:.2f}"
    headline = [
        ("Total value (INR)", f"{run.get('total_value_inr', 0):,.0f}"),
        ("CAGR (today's weights, backcast)", pct(pm["cagr"])),
        ("Annual volatility", pct(pm["annual_volatility"])),
        (f"Sharpe ratio (rf {run['risk_free_rate']:.1%})", num(pm["sharpe_ratio"])),
        (f"Beta vs {run['benchmark']}", num(pm["beta"])),
        ("Max drawdown (constant weights)", pct(pm["max_drawdown"])),
        ("Max drawdown (buy-and-hold)", pct(pm["max_drawdown_buy_and_hold"])),
    ] + [(f"{var_key.replace('value_at_risk_', 'VaR ').replace('_', '-')} {lvl} / CVaR",
          f"{pct(v['var'])} / {pct(v['cvar'])}") for lvl, v in pm[var_key].items()]

    holdings = pd.DataFrame({
        "Weight": pd.Series(am["weight"]).map(pct),
        "Risk share": pd.Series(am["risk_contribution_pct"]).map(lambda v: f"{v:.1f}%"),
        "Annual vol": pd.Series(am["annual_volatility"]).map(pct),
        "Sharpe": pd.Series(am["sharpe_ratio"]).map(num),
        "Beta": pd.Series(am["beta"]).map(num),
        "Max drawdown": pd.Series(am["max_drawdown"]).map(pct),
    }).loc[pd.Series(am["weight"]).sort_values(ascending=False).index]

    parts = [
        "<!doctype html><html><head><meta charset='utf-8'><title>FinRisk-Lab report</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:32px;color:#0f172a}"
        "table{border-collapse:collapse;margin:12px 0 28px}td,th{padding:6px 14px;border-bottom:1px solid #e2e8f0;text-align:right}"
        "td:first-child,th:first-child{text-align:left}p.note{color:#475569;max-width:900px}</style></head><body>",
        "<h1>Portfolio risk report</h1>",
        f"<p class='note'>Window {run['window_start']} to {run['window_end']}, {run['observations']} "
        f"{run['return_frequency']} returns, all values in INR. Every figure applies <b>today's holdings</b> "
        "to past prices: it describes the risk of the portfolio you hold now, not your actual past returns "
        "(which depend on when you bought).</p>",
        "<table>" + "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k, v in headline) + "</table>",
        "<h2>Holdings</h2>", holdings.to_html(border=0, escape=True),
    ]
    for i, fig in enumerate(figures):
        parts.append(fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False))
    parts.append("</body></html>")
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="FinRisk-Lab: portfolio risk and stress testing.")
    parser.add_argument("--holdings", help="CSV of your holdings (see holdings.example.csv). "
                                           "Omit to run the model portfolio in config/settings.py.")
    parser.add_argument("--years", type=float, default=5, help="history window for --holdings (default 5)")
    parser.add_argument("--rf", type=float, default=settings.RISK_FREE_RATE, help="annual risk-free rate, e.g. 0.056")
    parser.add_argument("--benchmark", default="^NSEI", help="Yahoo ticker for beta with --holdings (default ^NSEI)")
    parser.add_argument("--find-fund", metavar="NAME", help="look up AMFI scheme codes by fund name and exit")
    args = parser.parse_args(argv)

    if args.find_fund:
        for code, name in search_funds(args.find_fund):
            print(f"{code}\t{name}")
        return

    print("--- [FinRisk-Lab] Starting Analysis ---")
    if args.holdings:
        output_dir = run_holdings_portfolio(args.holdings, args.years, args.rf, args.benchmark)
    else:
        output_dir = run_settings_portfolio(args.rf)
    print(f"Analysis Complete. Results saved to {output_dir / 'results.json'}")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:   # bad input: say what to fix, without a traceback
        raise SystemExit(f"\nError: {error}")
