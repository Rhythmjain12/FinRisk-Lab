"""
Holdings Loader — a real, mixed portfolio in one base currency (INR)

Purpose:
Turns a hand-filled holdings CSV into the two things the risk engine needs:
an INR price history per holding, and the current weight of each holding.

Supported sources (the ``source`` column):
- yahoo : anything Yahoo Finance prices — Indian stocks/ETFs (RELIANCE.NS,
          NIFTYBEES.NS), US stocks/ETFs (AAPL, VOO). Non-INR prices are
          converted with the same-day <CUR>INR=X rate, so the INR return
          already contains the currency move. The quote currency is read
          from Yahoo; a ``currency`` you type is only cross-checked.
- mf    : Indian mutual funds by AMFI scheme code, NAV history from
          api.mfapi.in (free, no key). Use the exact plan you hold
          (Direct/Regular) and a Growth option: IDCW NAVs drop on every
          payout, which would look like a loss.
- cash  : savings / fixed deposits. Modelled as a zero-volatility asset
          growing at ``annual_yield``.

Design choices:
- Weights come from current value: ``units`` x latest INR price, or an
  explicit ``value_inr``. Exactly one of the two per row.
- Failures are loud: an unknown ticker or scheme code, a currency that does
  not match the quote, or a price series that stopped (merged fund,
  delisted stock) raises and names the holding.
"""

import io
import json
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd #type:ignore

from src.ingestion.market_data import fetch_market_data, fetch_quote_currency
from src.preprocessing.cleaner import align_prices

COLUMNS = ["name", "asset_class", "region", "source", "symbol", "currency", "units", "value_inr", "annual_yield"]
MFAPI = "https://api.mfapi.in/mf"
MIN_WEEKS = 32  # weekly statistics (VaR in particular) need 30+ complete weekly returns


def _get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "FinRisk-Lab"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search_funds(query):
    """[(scheme_code, scheme_name), ...] for a name search on mfapi.in."""
    results = _get_json(f"{MFAPI}/search?q={urllib.parse.quote(query)}")
    return [(r["schemeCode"], r["schemeName"]) for r in results]


def fetch_mf_nav(scheme_code):
    """Full NAV history for one AMFI scheme code -> (Series, scheme_name)."""
    try:
        payload = _get_json(f"{MFAPI}/{urllib.parse.quote(str(scheme_code))}")
    except urllib.error.HTTPError as error:
        raise ValueError(f"mfapi.in rejected scheme code {scheme_code!r} ({error}). "
                         "It must be the numeric AMFI code.") from error
    # An unknown code still returns HTTP 200 / "SUCCESS" with empty data.
    if not payload.get("data"):
        raise ValueError(f"mfapi.in has no NAV history for scheme code {scheme_code!r}.")
    nav = pd.Series(
        {pd.to_datetime(row["date"], format="%d-%m-%Y"): float(row["nav"]) for row in payload["data"]}
    ).sort_index()
    return nav[nav > 0], payload["meta"].get("scheme_name", "")


def load_holdings(path):
    # Only whole lines starting with '#' are comments (a '#' inside a fund name is data).
    with open(path, encoding="utf-8-sig") as f:
        text = "".join(line for line in f if not line.lstrip().startswith("#"))
    holdings = pd.read_csv(io.StringIO(text), dtype=str, skipinitialspace=True, index_col=False)
    holdings.columns = holdings.columns.str.strip().str.lower()
    missing = [c for c in ["name", "source"] if c not in holdings.columns]
    if missing:
        raise ValueError(f"Holdings file is missing column(s): {missing}. Expected: {COLUMNS}")
    holdings = holdings.reindex(columns=COLUMNS).astype(object)
    holdings = holdings.apply(lambda col: col.map(lambda v: v.strip() if isinstance(v, str) else v))
    holdings = holdings.replace("", pd.NA).dropna(how="all")
    if holdings.empty:
        raise ValueError("Holdings file has no rows.")

    # (.map, not .str: a column that is entirely blank is not a string column)
    holdings["source"] = holdings["source"].map(lambda v: v.lower() if isinstance(v, str) else v)
    holdings["currency"] = holdings["currency"].map(lambda v: v.upper() if isinstance(v, str) else v).astype(object)
    yahoo_rows = holdings["source"] == "yahoo"
    holdings.loc[yahoo_rows, "symbol"] = holdings.loc[yahoo_rows, "symbol"].map(
        lambda v: v.upper() if isinstance(v, str) else v
    )
    # Funds and cash are INR by definition; a Yahoo row's currency is detected later.
    holdings.loc[~yahoo_rows, "currency"] = holdings.loc[~yahoo_rows, "currency"].fillna("INR")
    for col in ["asset_class", "region"]:
        holdings[col] = holdings[col].fillna("Unclassified")
    for col in ["units", "value_inr", "annual_yield"]:
        try:
            holdings[col] = holdings[col].map(
                lambda v: float(v.replace(",", "")) if isinstance(v, str) else float("nan")
            )
        except ValueError as error:
            raise ValueError(f"Holdings column '{col}' must contain numbers only ({error}).") from error

    def fail(row, message):
        raise ValueError(f"Holdings row '{row['name']}': {message}")

    if holdings["name"].isna().any() or holdings["name"].duplicated().any():
        raise ValueError("Every holding needs a unique 'name'.")
    if holdings["name"].map(str.lower).eq("portfolio").any():
        raise ValueError("'Portfolio' is reserved for the total; rename that holding.")
    for _, row in holdings.iterrows():
        if row["source"] not in ("yahoo", "mf", "cash"):
            fail(row, f"source must be yahoo, mf or cash (got {row['source']!r}).")
        if row["source"] == "cash":
            if pd.isna(row["value_inr"]) or pd.notna(row["units"]):
                fail(row, "cash needs value_inr (and no units).")
            if row["currency"] != "INR":
                fail(row, "cash must be entered in INR (convert the balance yourself).")
        else:
            if pd.isna(row["symbol"]):
                fail(row, "symbol is required (Yahoo ticker or AMFI scheme code).")
            if pd.isna(row["units"]) == pd.isna(row["value_inr"]):
                fail(row, "give exactly one of units or value_inr.")
        if row["source"] == "mf" and row["currency"] != "INR":
            fail(row, "mutual fund NAVs are in INR; currency must be INR.")
        amount = row["value_inr"] if pd.notna(row["value_inr"]) else row["units"]
        if amount <= 0:
            fail(row, "units / value_inr must be positive.")
        if pd.notna(row["annual_yield"]) and not (0 <= row["annual_yield"] < 0.5):
            fail(row, "annual_yield is a fraction: enter 0.07 for 7%.")
    holdings["annual_yield"] = holdings["annual_yield"].fillna(0.0)
    return holdings.reset_index(drop=True)


def build_inr_prices(holdings, start_date, end_date):
    """Returns (prices, values).

    prices : DataFrame of daily INR prices, one column per holding name, on
             one calendar (every weekday, gaps forward-filled).
    values : Series of each holding's current INR value.
    Also fills in ``holdings["currency"]`` for Yahoo rows from the quote currency.
    """
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    funds = holdings[holdings["source"] == "mf"]

    # Trust Yahoo, not the file, for the quote currency: a wrong or missing
    # currency would mis-value the holding by the exchange rate (or by 100x
    # for London's pence quotes) without any error.
    scale = {}
    for i, row in holdings[holdings["source"] == "yahoo"].iterrows():
        currency, scale[row["symbol"]] = fetch_quote_currency(row["symbol"])
        if pd.notna(row["currency"]) and row["currency"] != currency:
            raise ValueError(f"Holdings row '{row['name']}': {row['symbol']} is quoted in {currency}, "
                             f"not {row['currency']}. Fix or blank the currency column.")
        holdings.loc[i, "currency"] = currency
    yahoo = holdings[holdings["source"] == "yahoo"]

    raw = {}  # symbol -> local-currency price series

    fx_tickers = [f"{cur}INR=X" for cur in yahoo["currency"].unique() if cur != "INR"]
    tickers = sorted(set(yahoo["symbol"]) | set(fx_tickers))
    if tickers:
        closes = fetch_market_data(tickers, start_date, end_date)["Close"]
        for ticker in tickers:
            if ticker not in closes or closes[ticker].isna().all():
                raise ValueError(f"Yahoo Finance returned no prices for {ticker!r}. Check the symbol.")
            raw[ticker] = closes[ticker] * scale.get(ticker, 1.0)

    # ponytail: one HTTP call per fund, no disk cache. Add a cache if the
    # fund list gets long or mfapi.in starts rate-limiting.
    for code in funds["symbol"].unique():
        raw[code], scheme_name = fetch_mf_nav(code)
        print(f"  mf {code}: {scheme_name}")

    if not raw:
        raise ValueError("Holdings contain only cash; there is no market risk to analyse.")

    def holding_names(symbol):
        return holdings.loc[holdings["symbol"] == symbol, "name"].tolist() or [symbol]

    panel = pd.DataFrame(raw).sort_index()
    panel = panel[(panel.index >= start) & (panel.index < end)]
    if panel.empty:
        raise ValueError(f"No prices between {start.date()} and {end.date()}.")

    # A series that stopped well before the others is a merged fund or a
    # delisted stock. Forward-filling it to today would value it at a stale
    # price and understate its risk, so refuse.
    last_dates = panel.apply(lambda col: col.last_valid_index())
    stale = last_dates[last_dates < panel.index[-1] - pd.Timedelta(days=10)]
    if len(stale):
        details = ", ".join(f"{holding_names(s)[0]} (last price {d.date()})" for s, d in stale.items())
        raise ValueError(f"Price history has stopped for: {details}. "
                         "The fund may have merged or the stock delisted; use the current symbol.")

    # One calendar: every weekday. Liquid funds publish NAVs on weekends
    # (dropped); exchange holidays differ by country (forward-filled). A fixed
    # 5-day week keeps weekly samples exactly 7 days apart.
    first_dates = panel.apply(lambda col: col.first_valid_index())
    panel = panel.reindex(pd.bdate_range(panel.index[0], panel.index[-1])).ffill()

    prices = pd.DataFrame(index=panel.index)
    for _, row in holdings.iterrows():
        if row["source"] == "cash":
            days = (panel.index - panel.index[0]).days
            prices[row["name"]] = (1 + row["annual_yield"]) ** (days / 365.25)
        elif row["currency"] != "INR":
            prices[row["name"]] = panel[row["symbol"]] * panel[f"{row['currency']}INR=X"]
        else:
            prices[row["name"]] = panel[row["symbol"]]
    prices = align_prices(prices)

    # Say which holding shortened the window: a recently launched fund
    # silently cutting 5 years down to 8 months would mislead.
    limiting = holding_names(first_dates.idxmax())[0]
    if prices.index[0] > panel.index[0] + pd.Timedelta(days=7):
        print(f"  NOTE: history starts {prices.index[0].date()} (limited by {limiting}), "
              f"not {panel.index[0].date()}.")
    weeks = (prices.index[-1] - prices.index[0]).days // 7
    if weeks < MIN_WEEKS:
        raise ValueError(f"Only {weeks} weeks of common history (from {prices.index[0].date()}, limited by "
                         f"{limiting}); need at least {MIN_WEEKS}. Use a longer --years, or leave out "
                         "holdings that are too new to measure.")

    last = prices.iloc[-1]
    values = pd.Series(
        {row["name"]: row["value_inr"] if pd.notna(row["value_inr"]) else row["units"] * last[row["name"]]
         for _, row in holdings.iterrows()}
    )
    return prices, values
