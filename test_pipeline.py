"""Offline tests for the metric fixes, the stress engine and the full pipeline.

No network: prices are synthetic and the data fetchers are stubbed.
Expected values are worked out by hand or recomputed with plain numpy, never
by calling the function under test.
Run:  cd FinRisk-Lab && venv/bin/python -m pytest -q
"""

import json

import numpy as np
import pandas as pd
import pytest

from src import main as app
from src.ingestion import holdings as holdings_module
from src.metrics.beta import calculate_beta
from src.metrics.drawdown import calculate_drawdown
from src.metrics.returns import daily_returns
from src.metrics.sharpe import calculate_sharpe
from src.metrics.var import calculate_historical_var_cvar
from src.portfolio.portfolio_engine import (
    calculate_portfolio_cagr,
    calculate_buy_and_hold_value_series,
)
from src.preprocessing.cleaner import align_prices
from src.risk_models.stress_engine import (
    calculate_concentration_stress_loss,
    calculate_correlation_breakdown_volatility,
    calculate_portfolio_loss,
    calculate_worst_historical_returns,
)


def _prices(n=600, seed=1, cols=("AAA", "BBB", "CCC"), start="2022-01-03"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    market = rng.normal(0.0004, 0.01, n)
    data = {c: 100 * np.cumprod(1 + market * (0.5 + i * 0.5) + rng.normal(0, 0.008, n))
            for i, c in enumerate(cols)}
    return pd.DataFrame(data, index=idx)


# ---------- preprocessing ----------

def test_align_prices_fills_gaps_and_drops_leading_rows():
    idx = pd.bdate_range("2024-01-01", periods=40)
    prices = pd.DataFrame({"OLD": np.arange(100.0, 140.0), "NEW": np.arange(50.0, 90.0)}, index=idx)
    prices.loc[idx[:5], "NEW"] = np.nan       # listed later
    prices.loc[idx[20], "OLD"] = np.nan       # one holiday
    aligned = align_prices(prices)
    assert aligned.index[0] == idx[5]
    assert not aligned.isna().any().any()
    assert aligned.loc[idx[20], "OLD"] == prices.loc[idx[19], "OLD"]


def test_align_prices_rejects_ticker_with_no_data():
    idx = pd.bdate_range("2024-01-01", periods=40)
    prices = pd.DataFrame({"OK": np.arange(100.0, 140.0), "DEAD": np.nan}, index=idx)
    with pytest.raises(ValueError, match="DEAD"):
        align_prices(prices)


def test_returns_do_not_invent_zero_across_a_gap():
    r = daily_returns(pd.DataFrame({"A": [100.0, 110.0, np.nan, 121.0]}))
    assert np.isnan(r["A"].iloc[2]) and np.isnan(r["A"].iloc[3])


# ---------- metrics ----------

def test_cagr_uses_calendar_time():
    # Doubling over exactly two calendar years is 41.4% a year, whatever the row count.
    idx = pd.to_datetime(["2022-01-03", "2023-01-03", "2024-01-03"])
    returns = pd.Series([0.0, 0.25, 0.60], index=idx)   # 1.25 * 1.60 = 2.0
    assert calculate_portfolio_cagr(returns) == pytest.approx(2 ** 0.5 - 1, abs=1e-3)


def test_sharpe_value_and_riskless_assets():
    r = pd.DataFrame({"RISKY": [0.02, -0.01, 0.03, 0.00], "CASH": [0.0002] * 4})
    # mean 1% x 52 = 52%; sample std 1.8257% x sqrt(52) = 13.166%
    expected = (0.01 * 52 - 0.05) / (np.std([0.02, -0.01, 0.03, 0.00], ddof=1) * np.sqrt(52))
    sharpe = calculate_sharpe(r, risk_free_rate=0.05, periods_per_year=52)
    assert sharpe["RISKY"] == pytest.approx(expected)
    assert expected == pytest.approx(3.57, abs=0.01)
    assert np.isnan(sharpe["CASH"])
    assert calculate_sharpe(r["RISKY"], 0.05, 52) == pytest.approx(expected)   # Series form


def test_historical_var_and_cvar():
    returns = pd.Series(np.arange(-50, 50) / 1000.0)   # -5.0% ... +4.9%
    out = calculate_historical_var_cvar(returns, [0.95])
    assert out[0.95]["var"] == pytest.approx(-0.04505)
    assert out[0.95]["cvar"] == pytest.approx(-0.048)   # mean of -5.0 .. -4.6%


def test_beta_is_relative_to_the_market():
    market = pd.Series([0.01, -0.02, 0.015, 0.03, -0.01], name="MKT")
    assets = pd.DataFrame({"DOUBLE": 2 * market, "INVERSE": -0.5 * market + 0.001})
    beta = calculate_beta(assets, market.to_frame())
    assert beta["DOUBLE"] == pytest.approx(2.0)
    assert beta["INVERSE"] == pytest.approx(-0.5)
    with pytest.raises(ValueError):
        calculate_beta(assets, pd.DataFrame({"MKT": [0.0] * 5}))    # flat benchmark


def test_drawdown_is_measured_from_the_running_peak():
    _, worst = calculate_drawdown(pd.Series([100.0, 120.0, 90.0, 130.0, 65.0]))
    assert worst == pytest.approx(-0.5)     # 130 -> 65, not 100 -> 65


def test_buy_and_hold_anchoring():
    idx = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"UP": [100.0, 200.0, 400.0], "FLAT": [100.0, 100.0, 100.0]}, index=idx)
    w = {"UP": 0.5, "FLAT": 0.5}
    from_start = calculate_buy_and_hold_value_series(prices, w, "start")
    assert from_start.iloc[-1] == pytest.approx(2.5)      # 0.5*4 + 0.5*1
    # Weights as of the end: UP was only 1/5 of the basket at the start.
    from_end = calculate_buy_and_hold_value_series(prices, w, "end")
    assert from_end.iloc[-1] == pytest.approx(1 / (0.5 / 4 + 0.5))


# ---------- stress engine ----------

def test_correlation_stress_never_lowers_risk_and_hits_weighted_average_at_one():
    corr = pd.DataFrame([[1.0, -0.6], [-0.6, 1.0]], index=["A", "B"], columns=["A", "B"])
    vols = pd.Series({"B": 0.02, "A": 0.02})            # deliberately out of order
    w = {"A": 0.5, "B": 0.5}
    base = calculate_correlation_breakdown_volatility(corr, vols, w, stress=0.0)
    half = calculate_correlation_breakdown_volatility(corr, vols, w, stress=0.5)
    full = calculate_correlation_breakdown_volatility(corr, vols, w, stress=1.0)
    assert base == pytest.approx(0.02 * np.sqrt(0.2))   # sqrt(2 * 0.25 * (1 - 0.6)) * 2%
    assert base < half < full
    assert full == pytest.approx(0.02)                  # perfectly correlated -> weighted-average vol


def test_correlation_stress_aligns_vols_by_label():
    corr = pd.DataFrame(np.eye(2), index=["A", "B"], columns=["A", "B"])
    w = {"A": 0.9, "B": 0.1}
    ordered = calculate_correlation_breakdown_volatility(corr, pd.Series({"A": 0.05, "B": 0.01}), w, 0.0)
    shuffled = calculate_correlation_breakdown_volatility(corr, pd.Series({"B": 0.01, "A": 0.05}), w, 0.0)
    assert ordered == pytest.approx(shuffled)
    assert ordered == pytest.approx(np.sqrt((0.9 * 0.05) ** 2 + (0.1 * 0.01) ** 2))


def test_stress_functions_validate_weights():
    with pytest.raises(ValueError):
        calculate_portfolio_loss({"A": 0.5, "B": 0.5}, pd.Series({"A": -0.2}))   # beta missing for B
    with pytest.raises(ValueError):
        calculate_concentration_stress_loss({"A": 1.0, "B": 1.0}, -0.4)          # weights sum to 2


def test_concentration_stress_accepts_per_asset_shocks():
    loss = calculate_concentration_stress_loss({"EQ": 0.6, "FD": 0.4}, pd.Series({"EQ": -0.4, "FD": 0.0}))
    assert loss == pytest.approx({"EQ": -0.24, "FD": 0.0})
    assert calculate_concentration_stress_loss({"EQ": 0.6, "FD": 0.4}, -0.5) == pytest.approx({"EQ": -0.3, "FD": -0.2})


def test_worst_historical_returns():
    r = pd.Series([0.01, -0.10, -0.10, 0.02, 0.03])
    out = calculate_worst_historical_returns(r, {"one": 1, "two": 2, "too_long": 99})
    assert out["one"] == pytest.approx(-0.10)
    assert out["two"] == pytest.approx(0.9 * 0.9 - 1)
    assert "too_long" not in out


# ---------- end to end: settings-style portfolio (daily returns) ----------

def test_analyse_matches_independent_numpy(tmp_path):
    prices = _prices()
    benchmark = _prices(cols=("MKT",), seed=7)["MKT"]
    weights = {"CCC": 0.5, "AAA": 0.3, "BBB": 0.2}       # not in column order on purpose
    results, figures = app.analyse(
        prices, weights, benchmark, output_dir=tmp_path, benchmark_name="MKT", risk_free_rate=0.05,
    )
    pm, am, st = results["portfolio_metrics"], results["asset_metrics"], results["stress_test_results"]
    assert len(figures) == 8

    w = np.array([weights[c] for c in prices.columns])
    R = prices.pct_change().dropna().to_numpy()
    m = benchmark.pct_change().dropna().to_numpy()
    port = R @ w
    vol = port.std(ddof=1) * np.sqrt(252)
    asset_vol = R.std(axis=0, ddof=1) * np.sqrt(252)
    beta = np.array([np.cov(R[:, i], m)[0, 1] / m.var(ddof=1) for i in range(3)])

    assert pm["annual_volatility"] == pytest.approx(vol)
    assert pm["sharpe_ratio"] == pytest.approx((port.mean() * 252 - 0.05) / vol)
    assert [am["beta"][c] for c in prices.columns] == pytest.approx(list(beta))
    assert pm["beta"] == pytest.approx(float(w @ beta))
    assert st["market_shock_loss"] == pytest.approx(-0.20 * float(w @ beta))
    assert pm["diversification_benefit"] == pytest.approx(float(w @ asset_vol) - vol)
    assert pm["diversification_benefit"] > 0
    cov = np.cov(R, rowvar=False)
    rc = w * (cov @ w) / (w @ cov @ w) * 100
    assert [am["risk_contribution_pct"][c] for c in prices.columns] == pytest.approx(list(rc))
    value = np.concatenate([[1.0], np.cumprod(1 + port)])
    assert pm["max_drawdown"] == pytest.approx((value / np.maximum.accumulate(value) - 1).min())
    assert pm["value_at_risk_1_day"]["95pct"]["var"] == pytest.approx(np.quantile(port, 0.05))
    tail = port[port <= np.quantile(port, 0.05)]
    assert pm["value_at_risk_1_day"]["95pct"]["cvar"] == pytest.approx(tail.mean())
    assert json.loads((tmp_path / "results.json").read_text())["run"]["return_frequency"] == "daily"


# ---------- end to end: holdings mode (mixed assets, INR, weekly returns) ----------

HEADER = "name,asset_class,region,source,symbol,currency,units,value_inr,annual_yield\n"


@pytest.fixture
def market(monkeypatch, tmp_path):
    """A stubbed market ending yesterday: an Indian stock, a US stock on a
    different holiday calendar, USDINR, a mutual fund with weekend NAVs, Nifty."""
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=900)
    base = _prices(n=900, cols=("INFY.NS", "AAPL", "^NSEI", "HSBA.L"), seed=5)
    base.index = idx
    series = {c: base[c] for c in base}
    series["AAPL"] = series["AAPL"].drop(idx[[100, 101, 400]])          # US holidays
    series["INFY.NS"] = series["INFY.NS"].drop(idx[[200, 555]])         # Indian holidays
    series["USDINR=X"] = pd.Series(np.linspace(80, 90, 900), index=idx)
    series["GBPINR=X"] = pd.Series(100.0, index=idx)
    rng = np.random.default_rng(11)
    nav_idx = pd.date_range(idx[0], idx[-1], freq="D")                   # liquid-fund style: every day
    nav = pd.Series(1000 * np.cumprod(1 + rng.normal(0.0002, 0.0004, len(nav_idx))), index=nav_idx)
    currencies = {"INFY.NS": ("INR", 1.0), "AAPL": ("USD", 1.0), "^NSEI": ("INR", 1.0), "HSBA.L": ("GBP", 0.01)}

    def fake_fetch(ticker, start, end):
        wanted = ticker if isinstance(ticker, list) else [ticker]
        panel = pd.DataFrame({t: series[t] for t in wanted if t in series}).reindex(columns=wanted)
        return pd.concat({"Close": panel[(panel.index >= start) & (panel.index < end)]}, axis=1)

    for module in (holdings_module, app):
        monkeypatch.setattr(module, "fetch_market_data", fake_fetch)
        monkeypatch.setattr(module, "fetch_quote_currency", lambda t: currencies[t])
    monkeypatch.setattr(holdings_module, "fetch_mf_nav", lambda code: (nav, "Test Fund"))
    monkeypatch.setattr(app, "ROOT", tmp_path)

    def write(rows, header=HEADER):
        path = tmp_path / "mine.csv"
        path.write_text(header + rows)
        return path
    return write, series, nav


MIXED = (
    "# a comment line\n"
    "Infosys,Equity,India,yahoo,infy.ns,INR,10,,\n"
    "Apple #1,Equity,International,yahoo,AAPL,,2,,\n"
    "Liquid Fund,Debt,India,mf,123456,INR,40,,\n"
    "FD,Cash,India,cash,,INR,,\"40,000\",0.07\n"
)


def test_holdings_mode_matches_independent_numpy(market):
    write, series, nav = market
    path = write(MIXED.replace("\n", ",\n"))        # a trailing comma on every data row must not shift columns
    app.main(["--holdings", str(path), "--years", "2.5"])      # fractional years
    out = path.parent / "outputs" / "mine"
    results = json.loads((out / "results.json").read_text())
    prices = pd.read_csv(out / "prices_inr.csv", index_col=0, parse_dates=True)
    am, pm, st = results["asset_metrics"], results["portfolio_metrics"], results["stress_test_results"]
    names = list(prices.columns)

    # calendar: every weekday, no gaps, ends before today, about 2.5 years long
    assert not prices.isna().any().any()
    assert prices.index.dayofweek.max() == 4
    assert prices.index[-1] < pd.Timestamp.today().normalize()
    assert 2.4 < (prices.index[-1] - prices.index[0]).days / 365.25 <= 2.5

    # INR conversion at the same-day rate; a US holiday carries the last USD price at that day's FX
    last = prices.index[-1]
    assert prices.loc[last, "Apple #1"] == pytest.approx(series["AAPL"][last] * 90)
    assert results["exposure"]["Currency"]["USD"]["weight_pct"] == pytest.approx(am["weight"]["Apple #1"] * 100)

    # weights = units x INR price (or the typed value) / total
    value = {"Infosys": 10 * series["INFY.NS"][last], "Apple #1": 2 * series["AAPL"][last] * 90,
             "Liquid Fund": 40 * nav[last], "FD": 40000.0}
    total = sum(value.values())
    assert results["run"]["total_value_inr"] == pytest.approx(total)
    assert am["weight"] == pytest.approx({k: v / total for k, v in value.items()})
    w = np.array([value[n] / total for n in names])

    # weekly statistics from complete Friday-to-Friday weeks, annualised with 52
    fridays = prices[prices.index.dayofweek == 4]
    R = fridays.pct_change().dropna().to_numpy()
    assert results["run"]["observations"] == len(R)
    port = R @ w
    vol = port.std(ddof=1) * np.sqrt(52)
    assert pm["annual_volatility"] == pytest.approx(vol)
    assert pm["sharpe_ratio"] == pytest.approx((port.mean() * 52 - 0.056) / vol)
    nifty = series["^NSEI"].reindex(prices.index).ffill()
    m = nifty[nifty.index.dayofweek == 4].pct_change().dropna().to_numpy()
    beta = np.array([np.cov(R[:, i], m)[0, 1] / m.var(ddof=1) for i in range(len(names))])
    assert [am["beta"][n] for n in names] == pytest.approx(list(beta), abs=1e-9)
    assert pm["beta"] == pytest.approx(float(w @ beta))

    # cash: no risk, no Sharpe, no shock; a low-vol fund is shocked by 3x its vol, a stock by -40%
    assert am["annual_volatility"]["FD"] == pytest.approx(0, abs=1e-9)
    assert am["sharpe_ratio"]["FD"] is None
    assert am["risk_contribution_pct"]["FD"] == pytest.approx(0, abs=1e-6)
    asset_vol = R.std(axis=0, ddof=1) * np.sqrt(52)
    shocks = st["single_asset_shock"]
    assert shocks["FD"] == pytest.approx(0, abs=1e-9)
    assert shocks["Liquid Fund"] == pytest.approx(-3 * asset_vol[names.index("Liquid Fund")])
    assert -0.05 < shocks["Liquid Fund"] < 0
    assert shocks["Infosys"] == -0.40

    # a riskless holding must not poison the correlation stress (its correlations are undefined)
    assert vol < st["correlation_stress_volatility"] < float(w @ asset_vol)

    # roll-ups add up
    region = results["exposure"]["Region"]
    rc = am["risk_contribution_pct"]
    assert region["India"]["risk_contribution_pct"] == pytest.approx(rc["Infosys"] + rc["Liquid Fund"] + rc["FD"])
    assert region["India"]["weight_pct"] + region["International"]["weight_pct"] == pytest.approx(100)

    # buy-and-hold: today's units held fixed through history
    held = (prices.to_numpy() / prices.iloc[-1].to_numpy()) @ w
    assert pm["max_drawdown_buy_and_hold"] == pytest.approx((held / np.maximum.accumulate(held) - 1).min())
    assert (out / "report.html").stat().st_size > 10_000


def test_pence_quoted_stock_is_scaled_and_currency_is_detected(market):
    write, series, _ = market
    held = holdings_module.load_holdings(write(
        "HSBC,Equity,International,yahoo,HSBA.L,,100,,\nInfosys,Equity,India,yahoo,INFY.NS,,10,,\n"))
    prices, values = holdings_module.build_inr_prices(held, "2000-01-01", "2100-01-01")
    assert values["HSBC"] == pytest.approx(100 * series["HSBA.L"].iloc[-1] * 0.01 * 100)   # pence -> GBP -> INR
    assert held.set_index("name")["currency"].to_dict() == {"HSBC": "GBP", "Infosys": "INR"}


def test_wrong_currency_is_rejected(market):
    write, _, _ = market
    held = holdings_module.load_holdings(write("Apple,Equity,International,yahoo,AAPL,INR,2,,\n"))
    with pytest.raises(ValueError, match="quoted in USD"):
        holdings_module.build_inr_prices(held, "2000-01-01", "2100-01-01")


def test_stopped_price_history_is_rejected(market):
    write, series, _ = market
    series["AAPL"] = series["AAPL"].iloc[:-60]             # delisted three months ago
    held = holdings_module.load_holdings(write(MIXED))
    with pytest.raises(ValueError, match="stopped.*Apple #1"):
        holdings_module.build_inr_prices(held, "2000-01-01", "2100-01-01")


def test_too_little_history_names_the_limiting_holding(market):
    write, series, _ = market
    series["AAPL"] = series["AAPL"].iloc[-100:]            # listed five months ago
    with pytest.raises(ValueError, match="weeks of common history.*Apple #1"):
        app.main(["--holdings", str(write(MIXED))])


def test_optional_columns_may_be_absent(market):
    write, _, _ = market
    held = holdings_module.load_holdings(write("Infosys,yahoo,INFY.NS,10\nApple,yahoo,AAPL,2\n",
                                               header="name,source,symbol,units\n"))
    assert held["asset_class"].tolist() == ["Unclassified"] * 2
    prices, values = holdings_module.build_inr_prices(held, "2000-01-01", "2100-01-01")
    assert list(prices.columns) == ["Infosys", "Apple"]


@pytest.mark.parametrize("row, message", [
    ("X,Equity,India,yahoo,INFY.NS,INR,10,5000,", "exactly one"),
    ("X,Equity,India,yahoo,,INR,10,,", "symbol"),
    ("X,Equity,India,broker,INFY.NS,INR,10,,", "source"),
    ("X,Cash,India,cash,,INR,5,,0.07", "cash"),
    ("X,Equity,India,yahoo,INFY.NS,INR,-3,,", "positive"),
    ("X,Cash,India,cash,,INR,,1000,7", "0.07 for 7%"),
    ("X,Equity,India,yahoo,INFY.NS,INR,ten,,", "numbers only"),
    ("Portfolio,Equity,India,yahoo,INFY.NS,INR,10,,", "reserved"),
    ("X,Equity,India,yahoo,INFY.NS,INR,10,,\nX,Equity,India,yahoo,AAPL,USD,1,,", "unique"),
])
def test_holdings_file_validation(tmp_path, row, message):
    csv = tmp_path / "bad.csv"
    csv.write_text(HEADER + row + "\n")
    with pytest.raises(ValueError, match=message):
        holdings_module.load_holdings(csv)
