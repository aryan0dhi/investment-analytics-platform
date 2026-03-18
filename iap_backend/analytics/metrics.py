"""
metrics.py

Utility functions for calculating portfolio performance metrics and trade statistics.
"""

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252     # Standard approximation for US trading days in a year


def _to_series(values: pd.Series) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.dropna().astype(float)
    return pd.Series(values).dropna().astype(float)


def _daily_returns(portfolio_values: pd.Series) -> pd.Series:
    values = _to_series(portfolio_values)
    return values.pct_change().dropna()


def calculate_total_return(initial_capital: float, final_value: float) -> float:
    if initial_capital == 0:
        return 0.0
    return ((final_value - initial_capital) / initial_capital) * 100


def calculate_annualized_volatility(portfolio_values: pd.Series) -> float:
    daily_returns = _daily_returns(portfolio_values)
    if daily_returns.empty:
        return 0.0
    return daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100


def calculate_sharpe_ratio(
    portfolio_values: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    daily_returns = _daily_returns(portfolio_values)
    if daily_returns.empty:
        return 0.0

    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1 # Convert annual risk-free rate to an equivalent daily rate
    excess_returns = daily_returns - daily_rf

    if excess_returns.std() == 0:
        return 0.0

    return (excess_returns.mean() / excess_returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)


def calculate_sortino_ratio(
    portfolio_values: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    daily_returns = _daily_returns(portfolio_values)
    if daily_returns.empty:
        return 0.0

    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_returns = daily_returns - daily_rf
    downside_returns = excess_returns[excess_returns < 0]

    if downside_returns.empty or downside_returns.std() == 0:
        return 0.0

    return (excess_returns.mean() / downside_returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)


def calculate_max_drawdown(portfolio_values: pd.Series) -> float:
    values = _to_series(portfolio_values)
    if values.empty:
        return 0.0

    running_max = values.cummax()
    drawdown = (values - running_max) / running_max
    return drawdown.min() * 100


def calculate_cagr(portfolio_values: pd.Series) -> float:
    values = _to_series(portfolio_values)
    if len(values) < 2 or values.iloc[0] <= 0:
        return 0.0

    num_years = len(values) / TRADING_DAYS_PER_YEAR # Assumes portfolio_values are sampled at daily trading frequency
    if num_years <= 0:
        return 0.0

    return ((values.iloc[-1] / values.iloc[0]) ** (1 / num_years) - 1) * 100


def calculate_calmar_ratio(portfolio_values: pd.Series) -> float:
    cagr = calculate_cagr(portfolio_values)
    max_drawdown = abs(calculate_max_drawdown(portfolio_values))

    if max_drawdown == 0:
        return 0.0

    return cagr / max_drawdown


def summarize_performance(portfolio_values: pd.Series) -> dict:
    values = _to_series(portfolio_values)
    if values.empty:
        return {
            "final_value": 0.0,
            "total_return": 0.0,
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "calmar_ratio": 0.0,
        }

    initial_value = float(values.iloc[0])
    final_value = float(values.iloc[-1])

    return {
        "final_value": final_value,
        "total_return": calculate_total_return(initial_value, final_value),
        "cagr": calculate_cagr(values),
        "volatility": calculate_annualized_volatility(values),
        "sharpe_ratio": calculate_sharpe_ratio(values),
        "sortino_ratio": calculate_sortino_ratio(values),
        "max_drawdown": calculate_max_drawdown(values),
        "calmar_ratio": calculate_calmar_ratio(values),
    }


def calculate_trade_statistics(trade_log_df: pd.DataFrame) -> dict:
    if trade_log_df is None or trade_log_df.empty:
        return {
            "num_trades": 0,
            "win_rate": 0.0,
            "avg_trade_return": 0.0,
            "avg_gain": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "avg_holding_days": 0.0,
            "total_net_pnl": 0.0,
        }

    closed_trades = trade_log_df.copy()

    wins = closed_trades[closed_trades["Net PnL"] > 0]
    losses = closed_trades[closed_trades["Net PnL"] < 0]

    gross_profit = wins["Net PnL"].sum() if not wins.empty else 0.0
    gross_loss = abs(losses["Net PnL"].sum()) if not losses.empty else 0.0

    if gross_loss == 0:
        # No losing trades: define profit factor as infinity if there was profit,
        # otherwise keep it at 0 when there were no gains either.
        profit_factor = 0.0 if gross_profit == 0 else float("inf")
    else:
        profit_factor = gross_profit / gross_loss

    return {
        "num_trades": int(len(closed_trades)),
        "win_rate": (len(wins) / len(closed_trades)) * 100 if len(closed_trades) > 0 else 0.0,
        "avg_trade_return": closed_trades["Return (%)"].mean(),
        "avg_gain": wins["Return (%)"].mean() if not wins.empty else 0.0,
        "avg_loss": losses["Return (%)"].mean() if not losses.empty else 0.0,
        "profit_factor": profit_factor,
        "avg_holding_days": closed_trades["Holding Days"].mean(),
        "total_net_pnl": closed_trades["Net PnL"].sum(),
    }