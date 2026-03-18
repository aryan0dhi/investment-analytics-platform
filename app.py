"""
Streamlit frontend for the Investment Analytics Platform.

Handles:
- user input (ticker, strategy, parameters)
- API communication with FastAPI backend
- rendering charts, metrics, and trade analysis
"""

import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Investment Analytics Platform", layout="wide")

st.markdown(
    """
    <style>
    .main-title {
        text-align: center;
        font-size: 2.9rem;
        font-weight: 700;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
        color: white;
    }

    .section-title {
        font-size: 2.0rem;
        font-weight: 700;
        margin-top: 1.2rem;
        margin-bottom: 1rem;
        color: white;
    }

    .metric-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 16px 18px;
        background: rgba(255,255,255,0.02);
        min-height: 118px;
        margin-bottom: 12px;
    }

    .metric-card.good {
        border: 1px solid rgba(34,197,94,0.28);
        background: rgba(34,197,94,0.06);
        box-shadow: 0 0 0 1px rgba(34,197,94,0.03) inset;
    }

    .metric-card.bad {
        border: 1px solid rgba(239,68,68,0.28);
        background: rgba(239,68,68,0.06);
        box-shadow: 0 0 0 1px rgba(239,68,68,0.03) inset;
    }

    .metric-card.neutral {
        border: 1px solid rgba(148,163,184,0.18);
        background: rgba(148,163,184,0.04);
    }

    .metric-label {
        font-size: 0.92rem;
        color: rgba(255,255,255,0.72);
        margin-bottom: 12px;
        line-height: 1.25;
    }

    .metric-value {
        font-size: 2.15rem;
        font-weight: 700;
        line-height: 1.1;
        color: white;
    }

    div[data-testid="stButton"] > button {
        white-space: nowrap !important;
    }

    .top-nav-btn button {
        white-space: nowrap !important;
        width: 130px !important;
        font-size: 0.95rem !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        background: rgba(255,255,255,0.03) !important;
    }

    .top-nav-btn button:hover {
        border: 1px solid rgba(59,130,246,0.6) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "has_run" not in st.session_state:
    st.session_state.has_run = False

if "submitted_inputs" not in st.session_state:
    st.session_state.submitted_inputs = None

if "asset_loaded" not in st.session_state:
    st.session_state.asset_loaded = False

if "asset_inputs" not in st.session_state:
    st.session_state.asset_inputs = None

if "asset_df" not in st.session_state:
    st.session_state.asset_df = None

if "show_help_page" not in st.session_state:
    st.session_state.show_help_page = False


def render_section_title(title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def render_metric_card(label: str, value: str, tone: str = "neutral"):
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_strategy_description(strategy_name):
    descriptions = {
        "Moving Average Crossover": (
            "Buys when the short term trend moves above the long term trend. "
            "This strategy works best in sustained trending markets."
        ),
        "Momentum": (
            "Buys when recent returns are positive. "
            "This strategy works best when strong assets continue trending higher."
        ),
        "Mean Reversion": (
            "Buys when price falls below its recent average by a set threshold. "
            "This strategy works best in choppy or sideways markets."
        ),
        "Compare All Strategies": (
            "Runs all available strategies on the same asset and compares them side by side "
            "against a buy and hold benchmark."
        ),
    }
    return descriptions.get(strategy_name, "")


def format_value(value, pct=False, currency=False):
    if value is None:
        return "N/A"

    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return "N/A"

    if currency:
        return f"${value:,.2f}"

    if pct:
        return f"{value:.2f}%"

    return f"{value:.2f}"


# Convert API response records into a clean DataFrame
def records_to_df(records):
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


# Ensure trade log date columns are proper datetime objects
def normalize_trade_log_df(trade_log_df: pd.DataFrame) -> pd.DataFrame:
    if trade_log_df.empty:
        return trade_log_df

    for col in ["Entry Date", "Exit Date"]:
        if col in trade_log_df.columns:
            trade_log_df[col] = pd.to_datetime(trade_log_df[col])

    return trade_log_df


# Wrapper for GET requests to backend API
def api_get(path: str, params: dict):
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=120)
    if response.status_code != 200:
        try:
            detail = response.json().get("detail", "Request failed.")
        except Exception:
            detail = response.text
        raise ValueError(detail)
    return response.json()


# Wrapper for POST requests to backend API
def api_post(path: str, payload: dict):
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=300)
    if response.status_code != 200:
        try:
            detail = response.json().get("detail", "Request failed.")
        except Exception:
            detail = response.text
        raise ValueError(detail)
    return response.json()


def render_performance_cards(title, strategy_perf, benchmark_perf):
    render_section_title(title)

    outperformance = strategy_perf["total_return"] - benchmark_perf["total_return"]

    row1 = st.columns(4)
    with row1[0]:
        render_metric_card(
            "Strategy Final Value",
            format_value(strategy_perf["final_value"], currency=True),
            "good" if strategy_perf["final_value"] >= benchmark_perf["final_value"] else "bad",
        )
    with row1[1]:
        render_metric_card(
            "Buy & Hold Final Value",
            format_value(benchmark_perf["final_value"], currency=True),
            "neutral",
        )
    with row1[2]:
        render_metric_card(
            "Strategy Return",
            format_value(strategy_perf["total_return"], pct=True),
            "good" if strategy_perf["total_return"] >= 0 else "bad",
        )
    with row1[3]:
        render_metric_card(
            "Outperformance",
            format_value(outperformance, pct=True),
            "good" if outperformance >= 0 else "bad",
        )

    row2 = st.columns(4)
    with row2[0]:
        render_metric_card(
            "Sharpe Ratio",
            format_value(strategy_perf["sharpe_ratio"]),
            "good" if strategy_perf["sharpe_ratio"] >= 0 else "bad",
        )
    with row2[1]:
        render_metric_card(
            "Sortino Ratio",
            format_value(strategy_perf["sortino_ratio"]),
            "good" if strategy_perf["sortino_ratio"] >= 0 else "bad",
        )
    with row2[2]:
        render_metric_card(
            "Volatility",
            format_value(strategy_perf["volatility"], pct=True),
            "neutral",
        )
    with row2[3]:
        render_metric_card(
            "CAGR",
            format_value(strategy_perf["cagr"], pct=True),
            "good" if strategy_perf["cagr"] >= 0 else "bad",
        )

    row3 = st.columns(4)
    with row3[0]:
        render_metric_card(
            "Max Drawdown",
            format_value(strategy_perf["max_drawdown"], pct=True),
            "good" if strategy_perf["max_drawdown"] >= -15 else "bad",
        )
    with row3[1]:
        render_metric_card(
            "Calmar Ratio",
            format_value(strategy_perf["calmar_ratio"]),
            "good" if strategy_perf["calmar_ratio"] >= 0 else "bad",
        )
    with row3[2]:
        render_metric_card(
            "Buy & Hold Sharpe",
            format_value(benchmark_perf["sharpe_ratio"]),
            "neutral",
        )
    with row3[3]:
        render_metric_card(
            "Buy & Hold Max Drawdown",
            format_value(benchmark_perf["max_drawdown"], pct=True),
            "neutral",
        )

    comparison_df = pd.DataFrame(
        {
            "Metric": [
                "Final Value",
                "Total Return (%)",
                "CAGR (%)",
                "Volatility (%)",
                "Sharpe Ratio",
                "Sortino Ratio",
                "Max Drawdown (%)",
                "Calmar Ratio",
            ],
            "Strategy": [
                strategy_perf["final_value"],
                strategy_perf["total_return"],
                strategy_perf["cagr"],
                strategy_perf["volatility"],
                strategy_perf["sharpe_ratio"],
                strategy_perf["sortino_ratio"],
                strategy_perf["max_drawdown"],
                strategy_perf["calmar_ratio"],
            ],
            "Buy & Hold": [
                benchmark_perf["final_value"],
                benchmark_perf["total_return"],
                benchmark_perf["cagr"],
                benchmark_perf["volatility"],
                benchmark_perf["sharpe_ratio"],
                benchmark_perf["sortino_ratio"],
                benchmark_perf["max_drawdown"],
                benchmark_perf["calmar_ratio"],
            ],
        }
    )

    st.dataframe(
        comparison_df.style.format(
            {
                "Strategy": "{:.2f}",
                "Buy & Hold": "{:.2f}",
            }
        ),
        use_container_width=True,
    )


def render_trade_stats(trade_stats, title="Trade Statistics"):
    render_section_title(title)

    profit_factor = trade_stats.get("profit_factor")
    avg_gain = trade_stats.get("avg_gain")
    avg_loss = trade_stats.get("avg_loss")
    total_net_pnl = trade_stats.get("total_net_pnl")
    win_rate = trade_stats.get("win_rate")
    avg_trade_return = trade_stats.get("avg_trade_return")

    row1 = st.columns(4)
    with row1[0]:
        render_metric_card(
            "Number of Trades",
            f"{trade_stats['num_trades']}",
            "neutral",
        )
    with row1[1]:
        render_metric_card(
            "Win Rate",
            format_value(win_rate, pct=True),
            "good" if win_rate is not None and win_rate >= 50 else "bad",
        )
    with row1[2]:
        render_metric_card(
            "Average Trade Return",
            format_value(avg_trade_return, pct=True),
            "good" if avg_trade_return is not None and avg_trade_return >= 0 else "bad",
        )
    with row1[3]:
        render_metric_card(
            "Profit Factor",
            format_value(profit_factor),
            "good" if profit_factor is not None and profit_factor >= 1 else "neutral",
        )

    row2 = st.columns(4)
    with row2[0]:
        render_metric_card(
            "Average Gain",
            format_value(avg_gain, pct=True),
            "good" if avg_gain is not None and avg_gain >= 0 else "neutral",
        )
    with row2[1]:
        render_metric_card(
            "Average Loss",
            format_value(avg_loss, pct=True),
            "bad" if avg_loss is not None and avg_loss < 0 else "neutral",
        )
    with row2[2]:
        render_metric_card(
            "Average Holding Days",
            format_value(trade_stats["avg_holding_days"]),
            "neutral",
        )
    with row2[3]:
        render_metric_card(
            "Total Net PnL",
            format_value(total_net_pnl, currency=True),
            "good" if total_net_pnl is not None and total_net_pnl >= 0 else "bad",
        )


def render_trade_log(trade_log_df):
    st.subheader("Trade Log")
    if trade_log_df.empty:
        st.info("No closed trades were generated for this run.")
        return

    display_df = trade_log_df.copy()
    st.dataframe(
        display_df.style.format(
            {
                "Entry Signal Price": "{:.2f}",
                "Entry Execution Price": "{:.2f}",
                "Exit Signal Price": "{:.2f}",
                "Exit Execution Price": "{:.2f}",
                "Shares": "{:.4f}",
                "Entry Cost": "${:,.2f}",
                "Exit Proceeds": "${:,.2f}",
                "Net PnL": "${:,.2f}",
                "Return (%)": "{:.2f}",
                "Holding Days": "{:.0f}",
            }
        ),
        use_container_width=True,
    )


def render_parameter_heatmap(summary_df, strategy_name, metric_column):
    st.subheader("Parameter Heatmap")

    if strategy_name == "Moving Average Crossover":
        pivot_df = summary_df.pivot(
            index="Short Window",
            columns="Long Window",
            values=metric_column,
        )
        x_title = "Long Window"
        y_title = "Short Window"

    elif strategy_name == "Mean Reversion":
        pivot_df = summary_df.pivot(
            index="Window",
            columns="Threshold",
            values=metric_column,
        )
        x_title = "Threshold"
        y_title = "Window"

    else:
        st.info("Heatmap is shown for two parameter strategies.")
        return

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_df.values,
            x=[str(x) for x in pivot_df.columns],
            y=[str(y) for y in pivot_df.index],
            text=[
                ["N/A" if pd.isna(v) else f"{v:.2f}" for v in row]
                for row in pivot_df.values
            ],
            texttemplate="%{text}",
            hovertemplate=(
                f"{y_title}: %{{y}}<br>{x_title}: %{{x}}"
                f"<br>{metric_column}: %{{z:.2f}}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)


# Compute drawdown (%) from portfolio value series
def calculate_drawdown_series(portfolio_values: pd.Series) -> pd.Series:
    running_max = portfolio_values.cummax()
    drawdown = (portfolio_values / running_max) - 1.0
    return drawdown * 100


# Compute rolling Sharpe ratio over a moving window
def calculate_rolling_sharpe_series(
    portfolio_values: pd.Series,
    window: int = 63,
) -> pd.Series:
    daily_returns = portfolio_values.pct_change()
    rolling_mean = daily_returns.rolling(window=window).mean()
    rolling_std = daily_returns.rolling(window=window).std()
    rolling_sharpe = (rolling_mean / rolling_std) * (252 ** 0.5)
    return rolling_sharpe

# Compute rolling returns (%)
def calculate_rolling_return_series(
    portfolio_values: pd.Series,
    window: int = 63,
) -> pd.Series:
    return portfolio_values.pct_change(periods=window) * 100


def render_underwater_chart(results_df: pd.DataFrame, title: str):
    strategy_drawdown = calculate_drawdown_series(results_df["Portfolio_Value"])
    benchmark_drawdown = calculate_drawdown_series(results_df["Buy_Hold_Value"])

    st.subheader(title)
    st.caption(
        "A filled version of drawdown that highlights both the depth of losses and how long the portfolio stays below its prior high."
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=strategy_drawdown,
            mode="lines",
            name="Strategy Underwater",
            fill="tozeroy",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=benchmark_drawdown,
            mode="lines",
            name="Buy and Hold Underwater",
            fill="tozeroy",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_drawdown_chart(results_df: pd.DataFrame, title: str):
    strategy_drawdown = calculate_drawdown_series(results_df["Portfolio_Value"])
    benchmark_drawdown = calculate_drawdown_series(results_df["Buy_Hold_Value"])

    st.subheader(title)
    st.caption(
        "Shows how far the portfolio is below its previous peak over time. More negative values mean deeper losses."
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=strategy_drawdown,
            mode="lines",
            name="Strategy Drawdown",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=benchmark_drawdown,
            mode="lines",
            name="Buy and Hold Drawdown",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_rolling_sharpe_chart(
    results_df: pd.DataFrame,
    title: str,
    window: int = 63,
):
    strategy_rolling_sharpe = calculate_rolling_sharpe_series(
        results_df["Portfolio_Value"],
        window=window,
    )
    benchmark_rolling_sharpe = calculate_rolling_sharpe_series(
        results_df["Buy_Hold_Value"],
        window=window,
    )

    st.subheader(title)
    st.caption(
        f"Shows risk adjusted performance over a moving {window}-day window. Higher values are better, while negative values indicate weak recent risk adjusted returns."
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=strategy_rolling_sharpe,
            mode="lines",
            name=f"Strategy Rolling Sharpe ({window}D)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=benchmark_rolling_sharpe,
            mode="lines",
            name=f"Buy and Hold Rolling Sharpe ({window}D)",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Rolling Sharpe Ratio",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_rolling_return_chart(
    results_df: pd.DataFrame,
    title: str,
    window: int = 63,
):
    strategy_rolling_return = calculate_rolling_return_series(
        results_df["Portfolio_Value"],
        window=window,
    )
    benchmark_rolling_return = calculate_rolling_return_series(
        results_df["Buy_Hold_Value"],
        window=window,
    )

    st.subheader(title)
    st.caption(
        f"Shows the percent return over the most recent {window}-day window at each point in time. This helps reveal whether recent performance is improving or weakening."
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=strategy_rolling_return,
            mode="lines",
            name=f"Strategy Rolling Return ({window}D)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=results_df["Date"],
            y=benchmark_rolling_return,
            mode="lines",
            name=f"Buy and Hold Rolling Return ({window}D)",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Rolling Return (%)",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def show_landing_page():
    st.markdown("## Getting Started")

    st.markdown(
        """
        This platform lets you test trading strategies, compare them against buy and hold, and analyze performance using professional metrics.

        Follow these steps to get started:
        """
    )

    st.markdown(
        """
        **1. Search a ticker**  
        Enter any supported Yahoo Finance ticker at the top of the screen and click **Load Asset** to view its price history.

        **2. Choose a strategy**  
        Use the sidebar to select a trading strategy and adjust its parameters.

        **3. Run analysis**  
        Click **Run Analysis** to generate performance metrics, trade statistics, and charts.

        **4. Explore results**  
        Review:
        - Price chart with strategy signals  
        - Performance metrics (Sharpe, CAGR, drawdown, etc.)  
        - Trade statistics and trade log  
        - Risk and return visualizations  

        **5. Optimization & validation**  
        Enable optimization to:
        - tune parameters on training data  
        - test performance on unseen data  
        - run walk-forward validation  
        """
    )

    st.markdown("---")

    st.markdown("## What this platform does")

    st.markdown(
        """
        - load and analyze historical price data for any supported ticker  
        - test multiple trading strategies on a selected asset  
        - compare strategy performance against buy and hold  
        - evaluate advanced metrics like Sharpe, Sortino, CAGR, volatility, and drawdown  
        - inspect detailed trade logs and trade-level statistics  
        - optimize parameters using training and out-of-sample testing  
        - run walk-forward validation for more realistic evaluation  
        - visualize drawdowns, underwater periods, rolling Sharpe, and rolling returns  
        """
    )

    st.markdown("---")

    st.markdown("## Help")

    st.markdown(
        """
        Click the **Help** button in the top right corner to view detailed explanations of:

        - all strategy settings and parameters  
        - how each strategy works  
        - how metrics like Sharpe ratio, CAGR, and drawdown are calculated  
        - how optimization and validation are performed  
        """
    )


def render_raw_price_chart(df: pd.DataFrame, ticker: str):
    st.subheader(f"{ticker} Price History")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["Close"],
            mode="lines",
            name="Price",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def show_help_page():
    st.header("Help and Strategy Guide")

    st.markdown("## How to use this dashboard")
    st.write(
        """
1. Search for a ticker at the top of the screen and load the asset.
2. Review the price chart.
3. Use the sidebar to choose a strategy and adjust settings.
4. Click Run Analysis to generate signals, metrics, charts, and trade logs.
5. Use optimization and walk forward tools for deeper validation.
"""
    )

    st.markdown("## Search and asset loading")
    st.write(
        """
**Search Ticker**  
Enter a Yahoo Finance ticker such as MSFT, AAPL, SPY, NVDA, BTC-USD, or GLD.

**Start Date / End Date**  
Defines the historical period used to load market data.

**Load Asset**  
Fetches the selected asset and displays its raw price history before any strategy is applied.
"""
    )

    st.markdown("## Strategies")
    st.write(
        """
**Moving Average Crossover**  
Buys when the short moving average crosses above the long moving average. Best suited for trending markets.

**Momentum**  
Buys when recent price performance is strong over a chosen lookback period. Works best when trends persist.

**Mean Reversion**  
Buys when price falls far enough below its recent average. Works best in range bound or choppy markets.

**Compare All Strategies**  
Runs all available strategies on the same asset and compares them against buy and hold.
"""
    )

    st.markdown("## Strategy settings")
    st.write(
        """
**Fast MA / Slow MA**  
Used in Moving Average Crossover. The fast MA reacts quickly to price moves. The slow MA tracks the broader trend.

**Momentum Lookback Window**  
Used in Momentum. Controls how many past days are used to measure recent strength.

**Mean Reversion Window**  
Used in Mean Reversion. Controls the rolling average period.

**Buy Threshold (%)**  
Used in Mean Reversion. Triggers entry when price is sufficiently below the rolling mean.

**Initial Capital**  
Starting portfolio value for the backtest.

**Stop Loss (%)**  
Exits a trade if price falls this far below entry.

**Use Volatility Filter**  
Blocks trades when recent volatility is above the allowed threshold.

**Max Annualized Volatility**  
Threshold used by the volatility filter.
"""
    )

    st.markdown("## Risk visualization")
    st.write(
        """
**Rolling Sharpe Window**  
Lookback window for the rolling Sharpe chart.

**Rolling Return Window**  
Lookback window for the rolling return chart.

These controls are hidden in a collapsed sidebar section to keep the main interface cleaner.
"""
    )

    st.markdown("## Optimization and validation")
    st.write(
        """
**Use Parameter Optimization + Out of Sample Test**  
Finds the best strategy settings on a training period and then tests them on unseen data.

**Optimize For**  
Metric used to rank parameter combinations:
- Sharpe Ratio
- Return (%)
- Sortino Ratio
- Calmar Ratio

**Training Period Ratio**  
Controls how much of the dataset is used for training versus testing.

**Use Walk Forward Testing**  
Runs repeated rolling train/test evaluations to reduce overfitting risk.

**Walk Forward Train Window Ratio**  
Relative size of each rolling training segment.

**Walk Forward Test Window Ratio**  
Relative size of each rolling test segment.
"""
    )

    st.markdown("## Performance metrics")
    st.write(
        """
**Final Value**  
Ending portfolio value.

**Total Return (%)**  
Percent gain or loss over the full backtest.

**CAGR (%)**  
Annualized growth rate over the period.

**Volatility (%)**  
Annualized standard deviation of returns.

**Sharpe Ratio**  
Risk adjusted return using total volatility.

**Sortino Ratio**  
Risk adjusted return using downside volatility only.

**Max Drawdown (%)**  
Largest peak to trough loss.

**Calmar Ratio**  
CAGR divided by max drawdown.

**Win Rate (%)**  
Percent of closed trades that were profitable.

**Profit Factor**  
Gross profits divided by gross losses.
"""
    )


st.markdown(
    '<div class="main-title">Investment Analytics Platform</div>',
    unsafe_allow_html=True,
)

nav_outer_left, nav_outer_right = st.columns([9, 3])

with nav_outer_right:
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        st.markdown('<div class="top-nav-btn">', unsafe_allow_html=True)
        if st.button("Dashboard"):
            st.session_state.show_help_page = False
        st.markdown("</div>", unsafe_allow_html=True)

    with btn_col2:
        st.markdown('<div class="top-nav-btn">', unsafe_allow_html=True)
        if st.button("Help"):
            st.session_state.show_help_page = True
        st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.show_help_page:
    show_help_page()
    st.stop()

top_col1, top_col2, top_col3, top_col4 = st.columns([3, 2, 2, 1])

with top_col1:
    search_ticker = st.text_input(
        "Search Ticker",
        value=(
            st.session_state.asset_inputs["ticker"]
            if st.session_state.asset_loaded
            else "MSFT"
        ),
        placeholder="AAPL, NVDA, SPY, BTC-USD, GLD...",
    ).strip().upper()

with top_col2:
    search_start = st.date_input(
        "Start Date",
        value=(
            st.session_state.asset_inputs["start_date"]
            if st.session_state.asset_loaded
            else date(2020, 1, 1)
        ),
        key="top_start",
    )

with top_col3:
    search_end = st.date_input(
        "End Date",
        value=(
            st.session_state.asset_inputs["end_date"]
            if st.session_state.asset_loaded
            else date(2025, 1, 1)
        ),
        key="top_end",
    )

with top_col4:
    st.write("")
    st.write("")
    load_asset = st.button("Load Asset", use_container_width=True)

if load_asset:
    if not search_ticker:
        st.error("Please enter a ticker.")
        st.stop()

    if search_start >= search_end:
        st.error("Start date must be earlier than end date.")
        st.stop()

    with st.spinner("Loading asset data..."):
        payload = api_get(
            "/asset",
            {
                "ticker": search_ticker,
                "start_date": str(search_start),
                "end_date": str(search_end),
            },
        )

    df = records_to_df(payload["price_data"])

    if df.empty:
        st.error("No data returned for this ticker.")
        st.stop()

    st.session_state.asset_loaded = True
    st.session_state.asset_inputs = {
        "ticker": search_ticker,
        "start_date": search_start,
        "end_date": search_end,
    }
    st.session_state.asset_df = df
    st.session_state.has_run = False
    st.session_state.submitted_inputs = None

st.sidebar.header("Strategy Settings")

if st.session_state.asset_loaded:
    ticker = st.session_state.asset_inputs["ticker"]
    start_date = st.session_state.asset_inputs["start_date"]
    end_date = st.session_state.asset_inputs["end_date"]
else:
    ticker = None
    start_date = None
    end_date = None

if not st.session_state.asset_loaded:
    st.sidebar.info("Load an asset from the top search bar to begin.")

strategy_name = st.sidebar.selectbox(
    "Strategy",
    [
        "Moving Average Crossover",
        "Momentum",
        "Mean Reversion",
        "Compare All Strategies",
    ],
    disabled=not st.session_state.asset_loaded,
)

fast_ma = None
slow_ma = None
lookback_window = None
mean_reversion_window = None
threshold_percent = None

if strategy_name == "Moving Average Crossover":
    fast_ma = st.sidebar.number_input(
        "Fast MA",
        min_value=5,
        max_value=200,
        value=50,
        disabled=not st.session_state.asset_loaded,
    )
    slow_ma = st.sidebar.number_input(
        "Slow MA",
        min_value=20,
        max_value=400,
        value=200,
        disabled=not st.session_state.asset_loaded,
    )

elif strategy_name == "Momentum":
    lookback_window = st.sidebar.number_input(
        "Momentum Lookback Window",
        min_value=5,
        max_value=252,
        value=20,
        disabled=not st.session_state.asset_loaded,
    )

elif strategy_name == "Mean Reversion":
    mean_reversion_window = st.sidebar.number_input(
        "Mean Reversion Window",
        min_value=5,
        max_value=252,
        value=20,
        disabled=not st.session_state.asset_loaded,
    )
    threshold_percent = st.sidebar.number_input(
        "Buy Threshold (%)",
        min_value=1.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
        disabled=not st.session_state.asset_loaded,
    )

initial_capital = st.sidebar.number_input(
    "Initial Capital",
    min_value=1000,
    value=10000,
    step=1000,
    disabled=not st.session_state.asset_loaded,
)

stop_loss_pct = st.sidebar.slider(
    "Stop Loss (%)",
    min_value=1,
    max_value=20,
    value=8,
    step=1,
    disabled=not st.session_state.asset_loaded,
)

position_size_pct = 100
commission_per_trade = 0.0
slippage_pct_input = 0.0

use_vol_filter = st.sidebar.checkbox(
    "Use Volatility Filter",
    value=False,
    disabled=not st.session_state.asset_loaded,
)

vol_threshold = None
if use_vol_filter:
    vol_threshold = st.sidebar.slider(
        "Max Annualized Volatility",
        min_value=0.10,
        max_value=1.00,
        value=0.30,
        step=0.05,
        disabled=not st.session_state.asset_loaded,
    )

st.sidebar.markdown("---")

with st.sidebar.expander("Risk Visualization", expanded=False):
    rolling_sharpe_window = st.selectbox(
        "Rolling Sharpe Window",
        [21, 63, 126, 252],
        index=1,
        disabled=not st.session_state.asset_loaded,
    )

    rolling_return_window = st.selectbox(
        "Rolling Return Window",
        [21, 63, 126, 252],
        index=1,
        disabled=not st.session_state.asset_loaded,
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Optimization and Validation")

use_optimization = st.sidebar.checkbox(
    "Use Parameter Optimization + Out of Sample Test",
    value=False,
    disabled=(
        not st.session_state.asset_loaded or strategy_name == "Compare All Strategies"
    ),
)

optimization_objective = None
train_ratio = None
use_walk_forward = False
walk_forward_train_ratio = None
walk_forward_test_ratio = None

if use_optimization and strategy_name != "Compare All Strategies":
    optimization_objective = st.sidebar.selectbox(
        "Optimize For",
        ["Sharpe Ratio", "Return (%)", "Sortino Ratio", "Calmar Ratio"],
        disabled=not st.session_state.asset_loaded,
    )

    train_ratio = st.sidebar.slider(
        "Training Period Ratio",
        min_value=0.50,
        max_value=0.90,
        value=0.70,
        step=0.05,
        disabled=not st.session_state.asset_loaded,
    )

    use_walk_forward = st.sidebar.checkbox(
        "Use Walk Forward Testing",
        value=False,
        disabled=not st.session_state.asset_loaded,
    )

    if use_walk_forward:
        walk_forward_train_ratio = st.sidebar.slider(
            "Walk Forward Train Window Ratio",
            min_value=0.30,
            max_value=0.70,
            value=0.50,
            step=0.05,
            disabled=not st.session_state.asset_loaded,
        )
        walk_forward_test_ratio = st.sidebar.slider(
            "Walk Forward Test Window Ratio",
            min_value=0.10,
            max_value=0.30,
            value=0.15,
            step=0.05,
            disabled=not st.session_state.asset_loaded,
        )

run_button = st.sidebar.button(
    "Run Analysis",
    disabled=not st.session_state.asset_loaded,
    use_container_width=True,
)

# Collect user inputs and trigger backend analysis
if run_button:
    if not st.session_state.asset_loaded:
        st.error("Please load an asset first.")
        st.stop()

    st.session_state.has_run = True
    st.session_state.submitted_inputs = {
        "ticker": ticker,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "strategy_name": strategy_name,
        "initial_capital": float(initial_capital),
        "position_size_pct": float(position_size_pct),
        "stop_loss_pct": float(stop_loss_pct),
        "commission_per_trade": float(commission_per_trade),
        "slippage_pct": float(slippage_pct_input) / 100.0,
        "rolling_sharpe_window": int(rolling_sharpe_window),
        "rolling_return_window": int(rolling_return_window),
        "use_vol_filter": bool(use_vol_filter),
        "vol_threshold": None if vol_threshold is None else float(vol_threshold),
        "fast_ma": None if fast_ma is None else int(fast_ma),
        "slow_ma": None if slow_ma is None else int(slow_ma),
        "lookback_window": None if lookback_window is None else int(lookback_window),
        "mean_reversion_window": None if mean_reversion_window is None else int(mean_reversion_window),
        "threshold_percent": None if threshold_percent is None else float(threshold_percent),
        "use_optimization": bool(use_optimization),
        "optimization_objective": optimization_objective,
        "train_ratio": None if train_ratio is None else float(train_ratio),
        "use_walk_forward": bool(use_walk_forward),
        "walk_forward_train_ratio": None if walk_forward_train_ratio is None else float(walk_forward_train_ratio),
        "walk_forward_test_ratio": None if walk_forward_test_ratio is None else float(walk_forward_test_ratio),
    }

if not st.session_state.asset_loaded:
    show_landing_page()
    st.stop()

asset_inputs = st.session_state.asset_inputs
df = st.session_state.asset_df

if not st.session_state.has_run:
    render_raw_price_chart(df, asset_inputs["ticker"])
    st.caption("Use the sidebar to apply a trading strategy and run analysis.")
    st.stop()

inputs = st.session_state.submitted_inputs

try:
    if not inputs["ticker"]:
        st.error("Please enter a ticker.")
        st.stop()

    if inputs["start_date"] >= inputs["end_date"]:
        st.error("Start date must be earlier than end date.")
        st.stop()

    if df.empty:
        st.error("No data returned for the selected ticker and date range.")
        st.stop()

    with st.spinner("Running analysis..."):
        analysis_data = api_post("/analyze", inputs)

    mode = analysis_data.get("mode")

    # Handle different backend response modes
    # compare_all | walk_forward | optimization | single_strategy
    if mode == "compare_all":
        st.caption(
            "Compare all strategies side by side with transaction cost aware backtests."
        )

        shared = analysis_data["meta"]["shared_backtest_settings"]

        st.info(
            f"""
            **Comparison Baseline Settings**

            - **Moving Average Crossover:** Fast MA = 50, Slow MA = 200  
            - **Momentum:** Lookback Window = 20  
            - **Mean Reversion:** Window = 20, Threshold = 5%  

            **Shared backtest settings:** Initial Capital = ${shared["initial_capital"]:,.0f}, Stop Loss = {shared["stop_loss_pct"]}%
        """
        )

        comparison_df = pd.DataFrame(analysis_data["comparison_table"])
        chart_df = records_to_df(analysis_data["chart_df"])

        st.dataframe(
            comparison_df.style.format(
                {
                    "Final Value": "${:,.2f}",
                    "Return (%)": "{:.2f}",
                    "Sharpe Ratio": "{:.2f}",
                    "Sortino Ratio": "{:.2f}",
                    "Max Drawdown (%)": "{:.2f}",
                    "Volatility (%)": "{:.2f}",
                }
            ),
            use_container_width=True,
        )

        fig_compare = go.Figure()
        fig_compare.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Moving Average Crossover"],
                mode="lines",
                name="Moving Average Crossover",
            )
        )
        fig_compare.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Momentum"],
                mode="lines",
                name="Momentum",
            )
        )
        fig_compare.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Mean Reversion"],
                mode="lines",
                name="Mean Reversion",
            )
        )
        fig_compare.add_trace(
            go.Scatter(
                x=chart_df["Date"],
                y=chart_df["Buy and Hold"],
                mode="lines",
                name="Buy and Hold",
            )
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    elif mode == "walk_forward":
        st.caption(
            "Single strategy analysis with advanced metrics, trade logs, optimization, heatmaps, and walk forward validation."
        )

        meta = analysis_data["meta"]
        summary_df = pd.DataFrame(analysis_data["summary_df"])
        wf_results = analysis_data["wf_results"]

        st.info(
            f"""
**Asset:** {analysis_data["asset"]}  
**Strategy:** {analysis_data["strategy_name"]}  
**Mode:** Walk Forward Testing  
**Optimization Objective:** {meta["optimization_objective"]}  
**Train Window Size:** {meta["train_window_size"]} rows  
**Test Window Size:** {meta["test_window_size"]} rows  
"""
        )

        if summary_df.empty:
            st.warning("Not enough data for walk forward testing with the chosen settings.")
            st.stop()

        walk_forward_summary = analysis_data["walk_forward_summary"]

        render_section_title("Walk Forward Summary")

        row1 = st.columns(4)
        with row1[0]:
            render_metric_card("Windows", f"{walk_forward_summary['windows']}", "neutral")
        with row1[1]:
            render_metric_card(
                "Avg Test Return",
                format_value(walk_forward_summary["avg_test_return"], pct=True),
                "good" if walk_forward_summary["avg_test_return"] >= 0 else "bad",
            )
        with row1[2]:
            render_metric_card(
                "Avg Buy & Hold Return",
                format_value(walk_forward_summary["avg_buy_hold_return"], pct=True),
                "neutral",
            )
        with row1[3]:
            render_metric_card(
                "Positive Windows",
                format_value(walk_forward_summary["positive_windows_pct"], pct=True),
                "good" if walk_forward_summary["positive_windows_pct"] >= 50 else "bad",
            )

        row2 = st.columns(4)
        with row2[0]:
            render_metric_card(
                "Avg Test Sharpe",
                format_value(walk_forward_summary["avg_test_sharpe"]),
                "good" if walk_forward_summary["avg_test_sharpe"] >= 0 else "bad",
            )
        with row2[1]:
            render_metric_card(
                "Avg Test Sortino",
                format_value(walk_forward_summary["avg_test_sortino"]),
                "good" if walk_forward_summary["avg_test_sortino"] >= 0 else "bad",
            )
        with row2[2]:
            render_metric_card(
                "Avg Test Max Drawdown",
                format_value(walk_forward_summary["avg_test_max_drawdown"], pct=True),
                "good" if walk_forward_summary["avg_test_max_drawdown"] >= -15 else "bad",
            )
        with row2[3]:
            render_metric_card(
                "Avg Outperformance",
                format_value(walk_forward_summary["avg_outperformance"], pct=True),
                "good" if walk_forward_summary["avg_outperformance"] >= 0 else "bad",
            )

        st.subheader("Walk Forward Window Summary")
        st.dataframe(
            summary_df.style.format(
                {
                    "Test Return (%)": "{:.2f}",
                    "Buy & Hold Return (%)": "{:.2f}",
                    "Test Sharpe Ratio": "{:.2f}",
                    "Test Sortino Ratio": "{:.2f}",
                    "Test Max Drawdown (%)": "{:.2f}",
                    "Win Rate (%)": "{:.2f}",
                }
            ),
            use_container_width=True,
        )

        fig_wf = go.Figure()
        fig_wf.add_trace(
            go.Bar(
                x=summary_df["Window"],
                y=summary_df["Test Return (%)"],
                name="Strategy Test Return (%)",
            )
        )
        fig_wf.add_trace(
            go.Bar(
                x=summary_df["Window"],
                y=summary_df["Buy & Hold Return (%)"],
                name="Buy & Hold Return (%)",
            )
        )
        fig_wf.update_layout(
            barmode="group",
            xaxis_title="Walk Forward Window",
            yaxis_title="Return (%)",
        )
        st.plotly_chart(fig_wf, use_container_width=True)

        if wf_results:
            with st.expander("View Walk Forward Test Window Details"):
                window_names = [f"Window {i}" for i in range(1, len(wf_results) + 1)]
                window_tabs = st.tabs(window_names)

                for i, (window_tab, result) in enumerate(zip(window_tabs, wf_results), start=1):
                    with window_tab:
                        result_df = records_to_df(result["results_df"])
                        trade_log_df = normalize_trade_log_df(records_to_df(result["trade_log_df"]))

                        chart_tab1, chart_tab2, chart_tab3, chart_tab4, chart_tab5 = st.tabs(
                            [
                                "Drawdown",
                                "Underwater",
                                "Rolling Sharpe",
                                "Rolling Return",
                                "Trade Log",
                            ]
                        )

                        with chart_tab1:
                            render_drawdown_chart(result_df, f"Window {i} Drawdown Chart")

                        with chart_tab2:
                            render_underwater_chart(result_df, f"Window {i} Underwater Chart")

                        with chart_tab3:
                            render_rolling_sharpe_chart(
                                result_df,
                                f"Window {i} Rolling Sharpe Chart",
                                window=inputs["rolling_sharpe_window"],
                            )

                        with chart_tab4:
                            render_rolling_return_chart(
                                result_df,
                                f"Window {i} Rolling Return Chart",
                                window=inputs["rolling_return_window"],
                            )

                        with chart_tab5:
                            render_trade_log(trade_log_df)

    elif mode == "optimization":
        st.caption(
            "Single strategy analysis with advanced metrics, trade logs, optimization, heatmaps, and walk forward validation."
        )

        st.info(
            f"""
**Asset:** {analysis_data["asset"]}  
**Strategy:** {analysis_data["strategy_name"]}  
**Mode:** Train/Test Optimization  
**Optimization Objective:** {analysis_data["meta"]["optimization_objective"]}  
**Train Ratio:** {int(analysis_data["meta"]["train_ratio"] * 100)}%  
**Best Parameters Found on Train:** {analysis_data["best_params"]}
"""
        )

        st.write(
            f"**Strategy Description:** {get_strategy_description(analysis_data['strategy_name'])}"
        )

        summary_df = pd.DataFrame(analysis_data["summary_df"])
        optimization_table = pd.DataFrame(analysis_data["optimization_table"])

        best_train_result = analysis_data["best_train_result"]
        best_train_results_df = records_to_df(best_train_result["results_df"])
        best_train_trade_log_df = normalize_trade_log_df(records_to_df(best_train_result["trade_log_df"]))

        test_result = analysis_data["test_result"]
        test_results_df = records_to_df(test_result["results_df"])
        test_trade_log_df = normalize_trade_log_df(records_to_df(test_result["trade_log_df"]))

        st.subheader("Training vs Out of Sample Test Summary")
        st.dataframe(
            summary_df.style.format(
                {
                    "Strategy Final Value": "${:,.2f}",
                    "Strategy Return (%)": "{:.2f}",
                    "Buy & Hold Return (%)": "{:.2f}",
                    "Sharpe Ratio": "{:.2f}",
                    "Sortino Ratio": "{:.2f}",
                    "Max Drawdown (%)": "{:.2f}",
                }
            ),
            use_container_width=True,
        )

        render_performance_cards(
            "Best Training Period Metrics",
            best_train_result["strategy_perf"],
            best_train_result["benchmark_perf"],
        )
        render_trade_stats(
            best_train_result["trade_stats"],
            "Trade Statistics for Best Training Period",
        )

        render_performance_cards(
            "Out of Sample Test Metrics",
            test_result["strategy_perf"],
            test_result["benchmark_perf"],
        )
        render_trade_stats(
            test_result["trade_stats"],
            "Trade Statistics for Out of Sample Test",
        )

        render_section_title("Optimization Analysis")

        opt_tab1, opt_tab2, opt_tab3, opt_tab4, opt_tab5, opt_tab6 = st.tabs(
            [
                "Train Charts",
                "Test Charts",
                "Parameter Heatmap",
                "Parameter Search Results",
                "Training Trade Log",
                "Test Trade Log",
            ]
        )

        with opt_tab1:
            train_chart_tab1, train_chart_tab2, train_chart_tab3, train_chart_tab4, train_chart_tab5 = st.tabs(
                ["Portfolio", "Drawdown", "Underwater", "Rolling Sharpe", "Rolling Return"]
            )

            with train_chart_tab1:
                st.subheader("Train Period Portfolio")
                fig_train = go.Figure()
                fig_train.add_trace(
                    go.Scatter(
                        x=best_train_results_df["Date"],
                        y=best_train_results_df["Portfolio_Value"],
                        mode="lines",
                        name="Strategy Portfolio (Train)",
                    )
                )
                fig_train.add_trace(
                    go.Scatter(
                        x=best_train_results_df["Date"],
                        y=best_train_results_df["Buy_Hold_Value"],
                        mode="lines",
                        name="Buy and Hold (Train)",
                    )
                )
                st.plotly_chart(fig_train, use_container_width=True)

            with train_chart_tab2:
                render_drawdown_chart(
                    best_train_results_df,
                    "Train Period Drawdown Chart",
                )

            with train_chart_tab3:
                render_underwater_chart(
                    best_train_results_df,
                    "Train Period Underwater Chart",
                )

            with train_chart_tab4:
                render_rolling_sharpe_chart(
                    best_train_results_df,
                    "Train Period Rolling Sharpe Chart",
                    window=inputs["rolling_sharpe_window"],
                )

            with train_chart_tab5:
                render_rolling_return_chart(
                    best_train_results_df,
                    "Train Period Rolling Return Chart",
                    window=inputs["rolling_return_window"],
                )

        with opt_tab2:
            test_chart_tab1, test_chart_tab2, test_chart_tab3, test_chart_tab4, test_chart_tab5 = st.tabs(
                ["Portfolio", "Drawdown", "Underwater", "Rolling Sharpe", "Rolling Return"]
            )

            with test_chart_tab1:
                st.subheader("Out of Sample Test Portfolio")
                fig_test = go.Figure()
                fig_test.add_trace(
                    go.Scatter(
                        x=test_results_df["Date"],
                        y=test_results_df["Portfolio_Value"],
                        mode="lines",
                        name="Strategy Portfolio (Test)",
                    )
                )
                fig_test.add_trace(
                    go.Scatter(
                        x=test_results_df["Date"],
                        y=test_results_df["Buy_Hold_Value"],
                        mode="lines",
                        name="Buy and Hold (Test)",
                    )
                )
                st.plotly_chart(fig_test, use_container_width=True)

            with test_chart_tab2:
                render_drawdown_chart(
                    test_results_df,
                    "Out of Sample Test Drawdown Chart",
                )

            with test_chart_tab3:
                render_underwater_chart(
                    test_results_df,
                    "Out of Sample Test Underwater Chart",
                )

            with test_chart_tab4:
                render_rolling_sharpe_chart(
                    test_results_df,
                    "Out of Sample Test Rolling Sharpe Chart",
                    window=inputs["rolling_sharpe_window"],
                )

            with test_chart_tab5:
                render_rolling_return_chart(
                    test_results_df,
                    "Out of Sample Test Rolling Return Chart",
                    window=inputs["rolling_return_window"],
                )

        with opt_tab3:
            render_parameter_heatmap(
                optimization_table,
                inputs["strategy_name"],
                inputs["optimization_objective"],
            )

        with opt_tab4:
            st.subheader("Parameter Search Results on Training Data")
            st.dataframe(
                optimization_table.sort_values(
                    by=inputs["optimization_objective"],
                    ascending=False,
                ).style.format(
                    {
                        "Final Value": "${:,.2f}",
                        "Return (%)": "{:.2f}",
                        "Sharpe Ratio": "{:.2f}",
                        "Sortino Ratio": "{:.2f}",
                        "Calmar Ratio": "{:.2f}",
                        "Volatility (%)": "{:.2f}",
                        "Max Drawdown (%)": "{:.2f}",
                        "Win Rate (%)": "{:.2f}",
                    }
                ),
                use_container_width=True,
            )

        with opt_tab5:
            render_trade_log(best_train_trade_log_df)

        with opt_tab6:
            render_trade_log(test_trade_log_df)

    elif mode == "single_strategy":
        st.caption(
            "Single strategy analysis with advanced metrics, trade logs, optimization, heatmaps, and walk forward validation."
        )

        results_df = records_to_df(analysis_data["results_df"])
        trade_log_df = normalize_trade_log_df(records_to_df(analysis_data["trade_log_df"]))
        buy_signals = records_to_df(analysis_data["buy_signals"])
        sell_signals = records_to_df(analysis_data["sell_signals"])

        st.info(
            f"""
**Asset:** {analysis_data["asset"]}  
**Strategy:** {analysis_data["strategy_name"]}  
**Period:** {analysis_data["meta"]["start_date"]} to {analysis_data["meta"]["end_date"]}  
**Stop Loss:** {analysis_data["meta"]["stop_loss_pct"]}%  
"""
        )

        st.write(
            f"**Strategy Description:** {get_strategy_description(analysis_data['strategy_name'])}"
        )

        st.subheader(f"{analysis_data['asset']} Price and Strategy Signals")

        fig_price = go.Figure()
        fig_price.add_trace(
            go.Scatter(
                x=results_df["Date"],
                y=results_df["Close"],
                mode="lines",
                name="Price",
            )
        )

        if analysis_data["strategy_name"] == "Moving Average Crossover":
            if "SMA_short" in results_df.columns:
                fig_price.add_trace(
                    go.Scatter(
                        x=results_df["Date"],
                        y=results_df["SMA_short"],
                        mode="lines",
                        name="Fast MA",
                    )
                )
            if "SMA_long" in results_df.columns:
                fig_price.add_trace(
                    go.Scatter(
                        x=results_df["Date"],
                        y=results_df["SMA_long"],
                        mode="lines",
                        name="Slow MA",
                    )
                )

        elif analysis_data["strategy_name"] == "Momentum":
            if "Momentum" in results_df.columns:
                fig_price.add_trace(
                    go.Scatter(
                        x=results_df["Date"],
                        y=results_df["Momentum"],
                        mode="lines",
                        name="Momentum",
                        yaxis="y2",
                    )
                )
                fig_price.update_layout(
                    yaxis=dict(title="Price"),
                    yaxis2=dict(
                        title="Momentum",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                )

        elif analysis_data["strategy_name"] == "Mean Reversion":
            if "Rolling_Mean" in results_df.columns:
                fig_price.add_trace(
                    go.Scatter(
                        x=results_df["Date"],
                        y=results_df["Rolling_Mean"],
                        mode="lines",
                        name="Rolling Mean",
                    )
                )
            if "Deviation" in results_df.columns:
                fig_price.add_trace(
                    go.Scatter(
                        x=results_df["Date"],
                        y=results_df["Deviation"],
                        mode="lines",
                        name="Deviation",
                        yaxis="y2",
                    )
                )
                fig_price.update_layout(
                    yaxis=dict(title="Price"),
                    yaxis2=dict(
                        title="Deviation",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                )

        if not buy_signals.empty:
            fig_price.add_trace(
                go.Scatter(
                    x=buy_signals["Date"],
                    y=buy_signals["Close"],
                    mode="markers",
                    name="Buy Signal",
                    marker=dict(symbol="triangle-up", size=12, color="green"),
                )
            )

        if not sell_signals.empty:
            fig_price.add_trace(
                go.Scatter(
                    x=sell_signals["Date"],
                    y=sell_signals["Close"],
                    mode="markers",
                    name="Sell Signal",
                    marker=dict(symbol="triangle-down", size=12, color="red"),
                )
            )

        st.plotly_chart(fig_price, use_container_width=True)

        render_performance_cards(
            "Performance Metrics",
            analysis_data["strategy_perf"],
            analysis_data["benchmark_perf"],
        )
        render_trade_stats(analysis_data["trade_stats"])

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "Portfolio",
                "Drawdown",
                "Underwater",
                "Rolling Sharpe",
                "Rolling Return",
            ]
        )

        with tab1:
            st.subheader("Strategy Portfolio vs Buy and Hold")
            fig_portfolio = go.Figure()
            fig_portfolio.add_trace(
                go.Scatter(
                    x=results_df["Date"],
                    y=results_df["Portfolio_Value"],
                    mode="lines",
                    name="Strategy Portfolio",
                )
            )
            fig_portfolio.add_trace(
                go.Scatter(
                    x=results_df["Date"],
                    y=results_df["Buy_Hold_Value"],
                    mode="lines",
                    name="Buy and Hold",
                )
            )
            st.plotly_chart(fig_portfolio, use_container_width=True)

        with tab2:
            render_drawdown_chart(results_df, "Drawdown Chart")

        with tab3:
            render_underwater_chart(results_df, "Underwater Chart")

        with tab4:
            render_rolling_sharpe_chart(
                results_df,
                "Rolling Sharpe Chart",
                window=inputs["rolling_sharpe_window"],
            )

        with tab5:
            render_rolling_return_chart(
                results_df,
                "Rolling Return Chart",
                window=inputs["rolling_return_window"],
            )

        with st.expander("View Trade Log"):
            render_trade_log(trade_log_df)

        with st.expander("View Backtest Data"):
            st.dataframe(results_df.tail(50), use_container_width=True)

    else:
        st.error("Unexpected response mode from backend.")

except Exception as e:
    st.error(f"Error: {e}")