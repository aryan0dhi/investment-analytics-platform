"""
Core analysis service for the Investment Analytics Platform.

Handles data loading, strategy execution, optimization, and walk-forward
evaluation. The main layer between API inputs and the backtesting/analytics engine.
"""

import math
from typing import Any

import pandas as pd

from iap_backend.analytics.metrics import (
    summarize_performance,
    calculate_trade_statistics,
)
from iap_backend.analytics.optimizer import (
    optimize_on_train,
    run_strategy_with_params,
    run_walk_forward_analysis,
)
from iap_backend.data.market_data import fetch_market_data
from iap_backend.engine.backtester import Backtester
from iap_backend.strategies.mean_reversion_strategy import MeanReversionStrategy
from iap_backend.strategies.momentum_strategy import MomentumStrategy
from iap_backend.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from functools import lru_cache

@lru_cache(maxsize=32)
def load_asset_data_cached(ticker, start_date, end_date):
    return load_asset_data(ticker, start_date, end_date)

def _clean_value(value: Any):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, (pd.Series, pd.Index)):
        return [_clean_value(v) for v in value.tolist()]

    if isinstance(value, list):
        return [_clean_value(v) for v in value]

    if isinstance(value, tuple):
        return tuple(_clean_value(v) for v in value)

    if isinstance(value, dict):
        return {k: _clean_value(v) for k, v in value.items()}

    if pd.isna(value):
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    return value


def df_to_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []

    safe_df = df.copy()

    for col in safe_df.columns:
        if pd.api.types.is_datetime64_any_dtype(safe_df[col]):
            safe_df[col] = safe_df[col].astype(str)

    records = safe_df.to_dict(orient="records")
    return [_clean_value(record) for record in records]


def apply_filters(
    signals_df: pd.DataFrame,
    use_vol_filter: bool = False,
    vol_threshold: float | None = None,
) -> pd.DataFrame:
    data = signals_df.copy()

    if use_vol_filter:
        data["Daily_Return"] = data["Close"].pct_change()
        data["Rolling_Volatility"] = (
            data["Daily_Return"].rolling(window=20).std() * (252 ** 0.5)
        )
        data.loc[data["Rolling_Volatility"] > vol_threshold, "Signal"] = 0

    data["Position_Change"] = data["Signal"].diff().fillna(0)
    return data


def build_strategy_from_inputs(inputs: dict):
    strategy_name = inputs["strategy_name"]

    if strategy_name == "Moving Average Crossover":
        fast_ma = inputs.get("fast_ma")
        slow_ma = inputs.get("slow_ma")

        if fast_ma is None or slow_ma is None:
            raise ValueError("Fast MA and Slow MA are required.")

        if fast_ma >= slow_ma:
            raise ValueError("Fast MA must be smaller than Slow MA.")

        return MovingAverageCrossoverStrategy(
            short_window=fast_ma,
            long_window=slow_ma,
        )

    if strategy_name == "Momentum":
        lookback_window = inputs.get("lookback_window")
        if lookback_window is None:
            raise ValueError("Momentum lookback window is required.")

        return MomentumStrategy(lookback_window=lookback_window)

    if strategy_name == "Mean Reversion":
        mean_reversion_window = inputs.get("mean_reversion_window")
        threshold_percent = inputs.get("threshold_percent")

        if mean_reversion_window is None or threshold_percent is None:
            raise ValueError("Mean reversion window and threshold are required.")

        return MeanReversionStrategy(
            window=mean_reversion_window,
            threshold=threshold_percent / 100.0,
        )

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def run_strategy(
    strategy,
    df: pd.DataFrame,
    initial_capital: float,
    position_size: float,
    stop_loss_pct: float,
    use_vol_filter: bool,
    vol_threshold: float | None,
    commission_per_trade: float = 0.0,
    slippage_pct: float = 0.0,
) -> dict:
    signals_df = strategy.generate_signals(df)

    filtered_df = apply_filters(
        signals_df,
        use_vol_filter=use_vol_filter,
        vol_threshold=vol_threshold,
    )

    backtester = Backtester(
        initial_capital=initial_capital,
        position_size=position_size,
        stop_loss_pct=stop_loss_pct,
        commission_per_trade=commission_per_trade,
        slippage_pct=slippage_pct,
    )

    results_df = backtester.run(filtered_df)
    trade_log_df = pd.DataFrame(backtester.trade_log)

    strategy_perf = summarize_performance(results_df["Portfolio_Value"])
    benchmark_perf = summarize_performance(results_df["Buy_Hold_Value"])
    trade_stats = calculate_trade_statistics(trade_log_df)

    return {
        "results_df": results_df,
        "trade_log_df": trade_log_df,
        "strategy_perf": _clean_value(strategy_perf),
        "benchmark_perf": _clean_value(benchmark_perf),
        "trade_stats": _clean_value(trade_stats),
        "final_value": _clean_value(strategy_perf["final_value"]),
        "total_return": _clean_value(strategy_perf["total_return"]),
        "sharpe_ratio": _clean_value(strategy_perf["sharpe_ratio"]),
        "sortino_ratio": _clean_value(strategy_perf["sortino_ratio"]),
        "max_drawdown": _clean_value(strategy_perf["max_drawdown"]),
        "calmar_ratio": _clean_value(strategy_perf["calmar_ratio"]),
        "volatility": _clean_value(strategy_perf["volatility"]),
        "cagr": _clean_value(strategy_perf["cagr"]),
    }


def load_asset_data(ticker: str, start_date: str, end_date: str) -> dict:
    if not ticker:
        raise ValueError("Ticker is required.")

    if start_date >= end_date:
        raise ValueError("Start date must be earlier than end date.")

    df = fetch_market_data(ticker, start_date, end_date)

    return {
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "rows": len(df),
        "price_data": df_to_records(df),
    }


def run_single_strategy_analysis(inputs: dict) -> dict:
    if not inputs.get("ticker"):
        raise ValueError("Ticker is required.")

    if inputs["start_date"] >= inputs["end_date"]:
        raise ValueError("Start date must be earlier than end date.")

    df = fetch_market_data(
        inputs["ticker"],
        inputs["start_date"],
        inputs["end_date"],
    )

    if df.empty:
        raise ValueError("No data returned for the selected ticker and date range.")

    strategy = build_strategy_from_inputs(inputs)

    strategy_results = run_strategy(
        strategy=strategy,
        df=df,
        initial_capital=inputs["initial_capital"],
        position_size=inputs["position_size_pct"] / 100.0,
        stop_loss_pct=inputs["stop_loss_pct"] / 100.0,
        use_vol_filter=inputs["use_vol_filter"],
        vol_threshold=inputs["vol_threshold"],
        commission_per_trade=inputs["commission_per_trade"],
        slippage_pct=inputs["slippage_pct"],
    )

    results_df = strategy_results["results_df"]
    trade_log_df = strategy_results["trade_log_df"]

    if "Actual_Position_Change" in results_df.columns:
        buy_signals = results_df[results_df["Actual_Position_Change"] == 1]
        sell_signals = results_df[results_df["Actual_Position_Change"] == -1]
    else:
        buy_signals = results_df[results_df["Position_Change"] == 1]
        sell_signals = results_df[results_df["Position_Change"] == -1]

    return {
        "mode": "single_strategy",
        "asset": inputs["ticker"],
        "strategy_name": inputs["strategy_name"],
        "results_df": df_to_records(results_df),
        "trade_log_df": df_to_records(trade_log_df),
        "buy_signals": df_to_records(buy_signals),
        "sell_signals": df_to_records(sell_signals),
        "strategy_perf": strategy_results["strategy_perf"],
        "benchmark_perf": strategy_results["benchmark_perf"],
        "trade_stats": strategy_results["trade_stats"],
        "meta": {
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "stop_loss_pct": inputs["stop_loss_pct"],
            "rolling_sharpe_window": inputs.get("rolling_sharpe_window"),
            "rolling_return_window": inputs.get("rolling_return_window"),
        },
    }


def run_compare_all_analysis(inputs: dict) -> dict:
    if not inputs.get("ticker"):
        raise ValueError("Ticker is required.")

    if inputs["start_date"] >= inputs["end_date"]:
        raise ValueError("Start date must be earlier than end date.")

    df = fetch_market_data(
        inputs["ticker"],
        inputs["start_date"],
        inputs["end_date"],
    )

    if df.empty:
        raise ValueError("No data returned for the selected ticker and date range.")

    ma_strategy = MovingAverageCrossoverStrategy(50, 200)
    momentum_strategy = MomentumStrategy(20)
    mean_reversion_strategy = MeanReversionStrategy(window=20, threshold=0.05)

    ma_results = run_strategy(
        ma_strategy,
        df,
        inputs["initial_capital"],
        inputs["position_size_pct"] / 100.0,
        inputs["stop_loss_pct"] / 100.0,
        inputs["use_vol_filter"],
        inputs["vol_threshold"],
        inputs["commission_per_trade"],
        inputs["slippage_pct"],
    )

    momentum_results = run_strategy(
        momentum_strategy,
        df,
        inputs["initial_capital"],
        inputs["position_size_pct"] / 100.0,
        inputs["stop_loss_pct"] / 100.0,
        inputs["use_vol_filter"],
        inputs["vol_threshold"],
        inputs["commission_per_trade"],
        inputs["slippage_pct"],
    )

    mean_reversion_results = run_strategy(
        mean_reversion_strategy,
        df,
        inputs["initial_capital"],
        inputs["position_size_pct"] / 100.0,
        inputs["stop_loss_pct"] / 100.0,
        inputs["use_vol_filter"],
        inputs["vol_threshold"],
        inputs["commission_per_trade"],
        inputs["slippage_pct"],
    )

    benchmark_perf = ma_results["benchmark_perf"]

    comparison_df = pd.DataFrame(
        {
            "Strategy": [
                "Moving Average Crossover",
                "Momentum",
                "Mean Reversion",
                "Buy and Hold",
            ],
            "Final Value": [
                ma_results["strategy_perf"]["final_value"],
                momentum_results["strategy_perf"]["final_value"],
                mean_reversion_results["strategy_perf"]["final_value"],
                benchmark_perf["final_value"],
            ],
            "Return (%)": [
                ma_results["strategy_perf"]["total_return"],
                momentum_results["strategy_perf"]["total_return"],
                mean_reversion_results["strategy_perf"]["total_return"],
                benchmark_perf["total_return"],
            ],
            "Sharpe Ratio": [
                ma_results["strategy_perf"]["sharpe_ratio"],
                momentum_results["strategy_perf"]["sharpe_ratio"],
                mean_reversion_results["strategy_perf"]["sharpe_ratio"],
                benchmark_perf["sharpe_ratio"],
            ],
            "Sortino Ratio": [
                ma_results["strategy_perf"]["sortino_ratio"],
                momentum_results["strategy_perf"]["sortino_ratio"],
                mean_reversion_results["strategy_perf"]["sortino_ratio"],
                benchmark_perf["sortino_ratio"],
            ],
            "Max Drawdown (%)": [
                ma_results["strategy_perf"]["max_drawdown"],
                momentum_results["strategy_perf"]["max_drawdown"],
                mean_reversion_results["strategy_perf"]["max_drawdown"],
                benchmark_perf["max_drawdown"],
            ],
            "Volatility (%)": [
                ma_results["strategy_perf"]["volatility"],
                momentum_results["strategy_perf"]["volatility"],
                mean_reversion_results["strategy_perf"]["volatility"],
                benchmark_perf["volatility"],
            ],
        }
    ).sort_values(by="Return (%)", ascending=False).reset_index(drop=True)

    chart_df = pd.DataFrame(
        {
            "Date": ma_results["results_df"]["Date"],
            "Moving Average Crossover": ma_results["results_df"]["Portfolio_Value"],
            "Momentum": momentum_results["results_df"]["Portfolio_Value"],
            "Mean Reversion": mean_reversion_results["results_df"]["Portfolio_Value"],
            "Buy and Hold": ma_results["results_df"]["Buy_Hold_Value"],
        }
    )

    return {
        "mode": "compare_all",
        "asset": inputs["ticker"],
        "comparison_table": df_to_records(comparison_df),
        "chart_df": df_to_records(chart_df),
        "meta": {
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "baseline_settings": {
                "Moving Average Crossover": {"fast_ma": 50, "slow_ma": 200},
                "Momentum": {"lookback_window": 20},
                "Mean Reversion": {"window": 20, "threshold_percent": 5},
            },
            "shared_backtest_settings": {
                "initial_capital": inputs["initial_capital"],
                "stop_loss_pct": inputs["stop_loss_pct"],
                "use_vol_filter": inputs["use_vol_filter"],
                "vol_threshold": inputs["vol_threshold"],
                "commission_per_trade": inputs["commission_per_trade"],
                "slippage_pct": inputs["slippage_pct"],
            },
        },
    }


def run_optimization_service(inputs: dict) -> dict:
    if not inputs.get("ticker"):
        raise ValueError("Ticker is required.")

    if inputs["start_date"] >= inputs["end_date"]:
        raise ValueError("Start date must be earlier than end date.")

    df = fetch_market_data(
        inputs["ticker"],
        inputs["start_date"],
        inputs["end_date"],
    )

    if df.empty:
        raise ValueError("No data returned for the selected ticker and date range.")

    split_idx = int(len(df) * inputs["train_ratio"])
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    if len(train_df) < 50 or len(test_df) < 20:
        raise ValueError("Not enough data for train/test split. Choose a wider date range.")

    best_train_result, optimization_table = optimize_on_train(
        strategy_name=inputs["strategy_name"],
        train_df=train_df,
        initial_capital=inputs["initial_capital"],
        position_size=inputs["position_size_pct"] / 100.0,
        stop_loss_pct=inputs["stop_loss_pct"] / 100.0,
        use_vol_filter=inputs["use_vol_filter"],
        vol_threshold=inputs["vol_threshold"],
        commission_per_trade=inputs["commission_per_trade"],
        slippage_pct=inputs["slippage_pct"],
        objective=inputs["optimization_objective"],
    )

    best_params = best_train_result["params"]

    test_result = run_strategy_with_params(
        strategy_name=inputs["strategy_name"],
        params=best_params,
        df=test_df,
        initial_capital=inputs["initial_capital"],
        position_size=inputs["position_size_pct"] / 100.0,
        stop_loss_pct=inputs["stop_loss_pct"] / 100.0,
        use_vol_filter=inputs["use_vol_filter"],
        vol_threshold=inputs["vol_threshold"],
        commission_per_trade=inputs["commission_per_trade"],
        slippage_pct=inputs["slippage_pct"],
    )

    summary_df = pd.DataFrame(
        {
            "Period": ["Train", "Test"],
            "Strategy Final Value": [
                best_train_result["strategy_perf"]["final_value"],
                test_result["strategy_perf"]["final_value"],
            ],
            "Strategy Return (%)": [
                best_train_result["strategy_perf"]["total_return"],
                test_result["strategy_perf"]["total_return"],
            ],
            "Buy & Hold Return (%)": [
                best_train_result["benchmark_perf"]["total_return"],
                test_result["benchmark_perf"]["total_return"],
            ],
            "Sharpe Ratio": [
                best_train_result["strategy_perf"]["sharpe_ratio"],
                test_result["strategy_perf"]["sharpe_ratio"],
            ],
            "Sortino Ratio": [
                best_train_result["strategy_perf"]["sortino_ratio"],
                test_result["strategy_perf"]["sortino_ratio"],
            ],
            "Max Drawdown (%)": [
                best_train_result["strategy_perf"]["max_drawdown"],
                test_result["strategy_perf"]["max_drawdown"],
            ],
        }
    )

    return {
        "mode": "optimization",
        "asset": inputs["ticker"],
        "strategy_name": inputs["strategy_name"],
        "best_params": _clean_value(best_params),
        "summary_df": df_to_records(summary_df),
        "optimization_table": df_to_records(optimization_table),
        "best_train_result": {
            "results_df": df_to_records(best_train_result["results_df"]),
            "trade_log_df": df_to_records(best_train_result["trade_log_df"]),
            "strategy_perf": _clean_value(best_train_result["strategy_perf"]),
            "benchmark_perf": _clean_value(best_train_result["benchmark_perf"]),
            "trade_stats": _clean_value(best_train_result["trade_stats"]),
        },
        "test_result": {
            "results_df": df_to_records(test_result["results_df"]),
            "trade_log_df": df_to_records(test_result["trade_log_df"]),
            "strategy_perf": _clean_value(test_result["strategy_perf"]),
            "benchmark_perf": _clean_value(test_result["benchmark_perf"]),
            "trade_stats": _clean_value(test_result["trade_stats"]),
        },
        "meta": {
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "optimization_objective": inputs["optimization_objective"],
            "train_ratio": inputs["train_ratio"],
            "rolling_sharpe_window": inputs.get("rolling_sharpe_window"),
            "rolling_return_window": inputs.get("rolling_return_window"),
        },
    }


def run_walk_forward_service(inputs: dict) -> dict:
    if not inputs.get("ticker"):
        raise ValueError("Ticker is required.")

    if inputs["start_date"] >= inputs["end_date"]:
        raise ValueError("Start date must be earlier than end date.")

    df = fetch_market_data(
        inputs["ticker"],
        inputs["start_date"],
        inputs["end_date"],
    )

    if df.empty:
        raise ValueError("No data returned for the selected ticker and date range.")

    train_window_size = max(
        126,
        int(len(df) * inputs["walk_forward_train_ratio"]),
    )
    test_window_size = max(
        42,
        int(len(df) * inputs["walk_forward_test_ratio"]),
    )

    summary_df, wf_results = run_walk_forward_analysis(
        strategy_name=inputs["strategy_name"],
        df=df,
        initial_capital=inputs["initial_capital"],
        position_size=inputs["position_size_pct"] / 100.0,
        stop_loss_pct=inputs["stop_loss_pct"] / 100.0,
        use_vol_filter=inputs["use_vol_filter"],
        vol_threshold=inputs["vol_threshold"],
        commission_per_trade=inputs["commission_per_trade"],
        slippage_pct=inputs["slippage_pct"],
        objective=inputs["optimization_objective"],
        train_window_size=train_window_size,
        test_window_size=test_window_size,
    )

    if summary_df.empty:
        return {
            "mode": "walk_forward",
            "asset": inputs["ticker"],
            "strategy_name": inputs["strategy_name"],
            "summary_df": [],
            "wf_results": [],
            "meta": {
                "train_window_size": train_window_size,
                "test_window_size": test_window_size,
                "optimization_objective": inputs["optimization_objective"],
                "rolling_sharpe_window": inputs.get("rolling_sharpe_window"),
                "rolling_return_window": inputs.get("rolling_return_window"),
            },
        }

    avg_strategy_return = summary_df["Test Return (%)"].mean()
    avg_benchmark_return = summary_df["Buy & Hold Return (%)"].mean()
    avg_sharpe = summary_df["Test Sharpe Ratio"].mean()
    avg_sortino = summary_df["Test Sortino Ratio"].mean()
    avg_mdd = summary_df["Test Max Drawdown (%)"].mean()
    positive_windows = (summary_df["Test Return (%)"] > 0).mean() * 100

    walk_forward_summary = {
        "windows": int(len(summary_df)),
        "avg_test_return": _clean_value(avg_strategy_return),
        "avg_buy_hold_return": _clean_value(avg_benchmark_return),
        "avg_test_sharpe": _clean_value(avg_sharpe),
        "avg_test_sortino": _clean_value(avg_sortino),
        "avg_test_max_drawdown": _clean_value(avg_mdd),
        "positive_windows_pct": _clean_value(positive_windows),
        "avg_outperformance": _clean_value(avg_strategy_return - avg_benchmark_return),
    }

    serialized_wf_results = []
    for result in wf_results:
        serialized_wf_results.append(
            {
                "results_df": df_to_records(result["results_df"]),
                "trade_log_df": df_to_records(result["trade_log_df"]),
                "strategy_perf": _clean_value(result["strategy_perf"]),
                "benchmark_perf": _clean_value(result["benchmark_perf"]),
                "trade_stats": _clean_value(result["trade_stats"]),
                "params": _clean_value(result["params"]),
            }
        )

    return {
        "mode": "walk_forward",
        "asset": inputs["ticker"],
        "strategy_name": inputs["strategy_name"],
        "summary_df": df_to_records(summary_df),
        "walk_forward_summary": walk_forward_summary,
        "wf_results": serialized_wf_results,
        "meta": {
            "start_date": inputs["start_date"],
            "end_date": inputs["end_date"],
            "optimization_objective": inputs["optimization_objective"],
            "train_window_size": train_window_size,
            "test_window_size": test_window_size,
            "rolling_sharpe_window": inputs.get("rolling_sharpe_window"),
            "rolling_return_window": inputs.get("rolling_return_window"),
        },
    }


def run_analysis(inputs: dict) -> dict:
    strategy_name = inputs.get("strategy_name")

    if strategy_name == "Compare All Strategies":
        return run_compare_all_analysis(inputs)

    if inputs.get("use_optimization") and inputs.get("use_walk_forward"):
        return run_walk_forward_service(inputs)

    if inputs.get("use_optimization"):
        return run_optimization_service(inputs)

    return run_single_strategy_analysis(inputs)