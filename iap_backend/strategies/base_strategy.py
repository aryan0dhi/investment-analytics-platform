"""
Base strategy interface for the Investment Analytics Platform.

Defines a common structure for all trading strategies to implement
signal generation logic.
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        pass