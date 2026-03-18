"""
Mean reversion trading strategy.

Generates buy signals when price falls below its rolling average
by a specified threshold.
"""

import pandas as pd
from iap_backend.strategies.base_strategy import BaseStrategy

class MeanReversionStrategy(BaseStrategy):
    def __init__(self, window=20, threshold=0.05):
        self.window = window
        self.threshold = threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        data["Rolling_Mean"] = data["Close"].rolling(window=self.window).mean()
        data["Deviation"] = (data["Close"] - data["Rolling_Mean"]) / data["Rolling_Mean"]

        # 1 = invested, 0 = in cash
        data["Signal"] = 0
        data.loc[data["Deviation"] < -self.threshold, "Signal"] = 1

        data["Position_Change"] = data["Signal"].diff().fillna(0)

        return data