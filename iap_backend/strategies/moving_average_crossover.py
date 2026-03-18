"""
Moving average crossover strategy.

Generates buy signals when the short-term average is above the long-term average.
"""

import pandas as pd
from iap_backend.strategies.base_strategy import BaseStrategy


class MovingAverageCrossoverStrategy(BaseStrategy):
    def __init__(self, short_window=50, long_window=200):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        data["SMA_short"] = data["Close"].rolling(window=self.short_window).mean()
        data["SMA_long"] = data["Close"].rolling(window=self.long_window).mean()

        # 1 = invested, 0 = out of market
        data["Signal"] = 0
        data.loc[data["SMA_short"] > data["SMA_long"], "Signal"] = 1

        data["Position_Change"] = data["Signal"].diff().fillna(0)

        return data