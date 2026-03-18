"""
Momentum trading strategy.

Generates buy signals when recent returns are positive.
"""

import pandas as pd
from iap_backend.strategies.base_strategy import BaseStrategy

class MomentumStrategy(BaseStrategy):
    def __init__(self, lookback_window=20):
        self.lookback_window = lookback_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        data["Momentum"] = data["Close"].pct_change(self.lookback_window)

        data["Signal"] = 0
        data.loc[data["Momentum"] > 0, "Signal"] = 1

        data["Position_Change"] = data["Signal"].diff().fillna(0)

        return data