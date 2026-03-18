"""
Market data loader for the Investment Analytics Platform.

Fetches historical price data from Yahoo Finance and returns
a cleaned, standardized DataFrame for downstream analysis.
"""

import yfinance as yf
import pandas as pd


def fetch_market_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end)

    if df.empty:
        raise ValueError(f"No data found for ticker {ticker}")

    # Flatten columns in case yfinance returns a MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    # Keep only the columns we need
    needed_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[needed_cols].copy()

    # Force numeric types
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().reset_index(drop=True)

    return df