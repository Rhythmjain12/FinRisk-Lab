import yfinance as yf #type:ignore

def fetch_market_data(ticker,start_date,end_date):
    # auto_adjust explicit: the library default changed between versions.
    # Adjusted closes fold dividends/splits/bonuses into the price series.
    data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No market data returned for {ticker} ({start_date} to {end_date}).")
    return data


# Some exchanges quote in a minor unit (London in pence): currency -> (major currency, scale).
MINOR_UNITS = {"GBp": ("GBP", 0.01), "GBX": ("GBP", 0.01), "ZAc": ("ZAR", 0.01), "ILA": ("ILS", 0.01)}

def fetch_quote_currency(ticker):
    """(currency, scale) Yahoo quotes this ticker in; price x scale is in that currency."""
    currency = yf.Ticker(ticker).fast_info["currency"]
    if not currency:
        raise ValueError(f"Yahoo Finance does not report a currency for {ticker!r}.")
    return MINOR_UNITS.get(currency, (currency.upper(), 1.0))
