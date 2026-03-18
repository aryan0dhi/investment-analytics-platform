"""
Request schemas for the Investment Analytics Platform API.

Defines the structure and validation of inputs sent from the frontend,
including strategy selection, parameters, and analysis configuration.
"""

from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel


StrategyName = Literal[
    "Moving Average Crossover",
    "Momentum",
    "Mean Reversion",
    "Compare All Strategies",
]


class AnalysisRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    strategy_name: StrategyName

    initial_capital: float = 10000
    position_size_pct: float = 100
    stop_loss_pct: float = 8
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.0

    use_vol_filter: bool = False
    vol_threshold: Optional[float] = None

    fast_ma: Optional[int] = None
    slow_ma: Optional[int] = None
    lookback_window: Optional[int] = None
    mean_reversion_window: Optional[int] = None
    threshold_percent: Optional[float] = None

    use_optimization: bool = False
    optimization_objective: Optional[str] = None
    train_ratio: Optional[float] = None

    use_walk_forward: bool = False
    walk_forward_train_ratio: Optional[float] = None
    walk_forward_test_ratio: Optional[float] = None

    rolling_sharpe_window: int = 63
    rolling_return_window: int = 63