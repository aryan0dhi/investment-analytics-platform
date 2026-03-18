"""
Optimization and walk-forward analysis utilities.

This module handles parameter grid generation, strategy evaluation,
training-set optimization, and rolling out-of-sample validation.
"""
from itertools import product

import pandas as pd

from iap_backend.analytics.metrics import (
    summarize_performance,
    calculate_trade_statistics,
)
from iap_backend.engine.backtester import Backtester
from iap_backend.strategies.moving_average_crossover import MovingAverageCrossoverStrategy
from iap_backend.strategies.momentum_strategy import MomentumStrategy
from iap_backend.strategies.mean_reversion_strategy import MeanReversionStrategy

def apply_filters(
    signals_df,
    use_vol_filter=False,
    vol_threshold=None,
):
    data = signals_df.copy()

    if use_vol_filter:
        data["Daily_Return"] = data["Close"].pct_change() 

        # Annualize rolling 20-day volatility and suppress signals in high-volatility regimes
        data["Rolling_Volatility"] = (
            data["Daily_Return"].rolling(window=20).std() * (252 ** 0.5)
        )
        data.loc[data["Rolling_Volatility"] > vol_threshold, "Signal"] = 0

    # Track entry/exit changes for downstream backtesting logic or visualization
    data["Position_Change"] = data["Signal"].diff().fillna(0)
    return data


def build_strategy(strategy_name, params):
    # Instantiate the selected strategy using the provided parameter

    if strategy_name == "Moving Average Crossover":
        return MovingAverageCrossoverStrategy(
            short_window=params["short_window"],
            long_window=params["long_window"],
        )

    if strategy_name == "Momentum":
        return MomentumStrategy(
            lookback_window=params["lookback_window"],
        )

    if strategy_name == "Mean Reversion":
        return MeanReversionStrategy(
            window=params["window"],
            threshold=params["threshold"],
        )

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def get_param_grid(strategy_name):
     #Return parameter combinations for grid-search optimization

    if strategy_name == "Moving Average Crossover":
        short_windows = [10, 20, 50]
        long_windows = [100, 150, 200]
        grid = []

        # Only keep valid crossover pairs where the short window is below the long window
        for short_w, long_w in product(short_windows, long_windows):
            if short_w < long_w:
                grid.append(
                    {
                        "short_window": short_w,
                        "long_window": long_w,
                    }
                )
        return grid

    if strategy_name == "Momentum":
        return [{"lookback_window": w} for w in [10, 20, 40, 60]]

    if strategy_name == "Mean Reversion":
        return [
            {"window": w, "threshold": t}
            for w, t in product([10, 20, 30], [0.03, 0.05, 0.08])
        ]

    raise ValueError(f"Unsupported strategy: {strategy_name}")


def run_strategy_with_params(
    strategy_name,
    params,
    df,
    initial_capital,
    position_size,
    stop_loss_pct,
    use_vol_filter,
    vol_threshold,
    commission_per_trade=0.0,
    slippage_pct=0.0,
):
    strategy = build_strategy(strategy_name, params)
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
        "params": params,
        "results_df": results_df,
        "trade_log_df": trade_log_df,
        "strategy_perf": strategy_perf,
        "benchmark_perf": benchmark_perf,
        "trade_stats": trade_stats,
        "final_value": strategy_perf["final_value"],
        "total_return": strategy_perf["total_return"],
        "sharpe_ratio": strategy_perf["sharpe_ratio"],
        "sortino_ratio": strategy_perf["sortino_ratio"],
        "max_drawdown": strategy_perf["max_drawdown"],
        "calmar_ratio": strategy_perf["calmar_ratio"],
        "volatility": strategy_perf["volatility"],
        "cagr": strategy_perf["cagr"],
    }


def optimize_on_train(
    strategy_name,
    train_df,
    initial_capital,
    position_size,
    stop_loss_pct,
    use_vol_filter,
    vol_threshold,
    commission_per_trade=0.0,
    slippage_pct=0.0,
    objective="Sharpe Ratio",
):
    # Evaluate a parameter grid on training data and return the best-performing configuration
    objective_map = {
        "Sharpe Ratio": "Sharpe Ratio",
        "Return (%)": "Return (%)",
        "Sortino Ratio": "Sortino Ratio",
        "Calmar Ratio": "Calmar Ratio",
    }

    if objective not in objective_map:
        raise ValueError("Unsupported optimization objective.")

    param_grid = get_param_grid(strategy_name)
    all_results = []

    for params in param_grid:
        result = run_strategy_with_params(
            strategy_name=strategy_name,
            params=params,
            df=train_df,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss_pct=stop_loss_pct,
            use_vol_filter=use_vol_filter,
            vol_threshold=vol_threshold,
            commission_per_trade=commission_per_trade,
            slippage_pct=slippage_pct,
        )
        all_results.append(result)

    summary_rows = []
    for result in all_results:
        row = {
            "Params": str(result["params"]),
            "Final Value": result["final_value"],
            "Return (%)": result["total_return"],
            "Sharpe Ratio": result["sharpe_ratio"],
            "Sortino Ratio": result["sortino_ratio"],
            "Calmar Ratio": result["calmar_ratio"],
            "Volatility (%)": result["volatility"],
            "Max Drawdown (%)": result["max_drawdown"],
            "Trades": result["trade_stats"]["num_trades"],
            "Win Rate (%)": result["trade_stats"]["win_rate"],
        }

        if strategy_name == "Moving Average Crossover":
            row["Short Window"] = result["params"]["short_window"]
            row["Long Window"] = result["params"]["long_window"]
        elif strategy_name == "Momentum":
            row["Lookback Window"] = result["params"]["lookback_window"]
        elif strategy_name == "Mean Reversion":
            row["Window"] = result["params"]["window"]
            row["Threshold"] = result["params"]["threshold"]

        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    best_idx = summary_df[objective_map[objective]].idxmax()
    best_result = all_results[best_idx]

    return best_result, summary_df


def run_walk_forward_analysis(
    strategy_name,
    df,
    initial_capital,
    position_size,
    stop_loss_pct,
    use_vol_filter,
    vol_threshold,
    commission_per_trade=0.0,
    slippage_pct=0.0,
    objective="Sharpe Ratio",
    train_window_size=504,
    test_window_size=126,
):
    data = df.copy().sort_values("Date").reset_index(drop=True)

    if train_window_size <= 0 or test_window_size <= 0:
        raise ValueError("Train and test window sizes must be positive.")

    window_rows = []
    walk_forward_results = []
    start_idx = 0
    window_number = 1

    while start_idx + train_window_size + test_window_size <= len(data):
        train_df = data.iloc[start_idx : start_idx + train_window_size].copy()
        test_df = data.iloc[
            start_idx + train_window_size : start_idx + train_window_size + test_window_size
        ].copy()

        best_train_result, _ = optimize_on_train(
            strategy_name=strategy_name,
            train_df=train_df,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss_pct=stop_loss_pct,
            use_vol_filter=use_vol_filter,
            vol_threshold=vol_threshold,
            commission_per_trade=commission_per_trade,
            slippage_pct=slippage_pct,
            objective=objective,
        )

        test_result = run_strategy_with_params(
            strategy_name=strategy_name,
            params=best_train_result["params"],
            df=test_df,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss_pct=stop_loss_pct,
            use_vol_filter=use_vol_filter,
            vol_threshold=vol_threshold,
            commission_per_trade=commission_per_trade,
            slippage_pct=slippage_pct,
        )

        walk_forward_results.append(test_result)

        row = {
            "Window": window_number,
            "Train Start": pd.to_datetime(train_df["Date"].iloc[0]).date(),
            "Train End": pd.to_datetime(train_df["Date"].iloc[-1]).date(),
            "Test Start": pd.to_datetime(test_df["Date"].iloc[0]).date(),
            "Test End": pd.to_datetime(test_df["Date"].iloc[-1]).date(),
            "Best Params": str(best_train_result["params"]),
            "Test Return (%)": test_result["strategy_perf"]["total_return"],
            "Buy & Hold Return (%)": test_result["benchmark_perf"]["total_return"],
            "Test Sharpe Ratio": test_result["strategy_perf"]["sharpe_ratio"],
            "Test Sortino Ratio": test_result["strategy_perf"]["sortino_ratio"],
            "Test Max Drawdown (%)": test_result["strategy_perf"]["max_drawdown"],
            "Trades": test_result["trade_stats"]["num_trades"],
            "Win Rate (%)": test_result["trade_stats"]["win_rate"],
        }
        window_rows.append(row)

        start_idx += test_window_size
        window_number += 1

    summary_df = pd.DataFrame(window_rows)

    return summary_df, walk_forward_results