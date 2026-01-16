import yfinance as yf #type:ignore

def fetch_market_data(ticker,start_date,end_date):
    data = yf.download(ticker, start=start_date, end=end_date)
    return data
