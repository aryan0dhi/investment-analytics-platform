"""
Backtesting engine for the Investment Analytics Platform.

Simulates strategy execution over historical data, including position management,
stop-loss handling, transaction costs, and slippage. Tracks portfolio value,
buy-and-hold benchmark, and trade logs.
"""

import pandas as pd

class Backtester:
    def __init__(
        self,
        initial_capital=10000,
        position_size=1.0,
        stop_loss_pct=0.08,
        commission_per_trade=0.0,
        slippage_pct=0.0,
    ):
        self.initial_capital = float(initial_capital)
        self.position_size = float(position_size)
        self.stop_loss_pct = float(stop_loss_pct)
        self.commission_per_trade = float(commission_per_trade)
        self.slippage_pct = float(slippage_pct)
        self.trade_log = []

    def _close_position(
        self,
        date,
        market_price,
        shares,
        cash,
        entry_date,
        entry_signal_price,
        entry_execution_price,
        entry_total_cost,
        exit_reason,
    ):
        sell_execution_price = market_price * (1 - self.slippage_pct)
        proceeds = (shares * sell_execution_price) - self.commission_per_trade
        cash += proceeds

        net_pnl = proceeds - entry_total_cost
        return_pct = (net_pnl / entry_total_cost) * 100 if entry_total_cost > 0 else 0.0
        holding_days = (pd.to_datetime(date) - pd.to_datetime(entry_date)).days

        trade = {
            "Entry Date": pd.to_datetime(entry_date),
            "Exit Date": pd.to_datetime(date),
            "Entry Signal Price": entry_signal_price,
            "Entry Execution Price": entry_execution_price,
            "Exit Signal Price": market_price,
            "Exit Execution Price": sell_execution_price,
            "Shares": shares,
            "Entry Cost": entry_total_cost,
            "Exit Proceeds": proceeds,
            "Net PnL": net_pnl,
            "Return (%)": return_pct,
            "Holding Days": holding_days,
            "Exit Reason": exit_reason,
        }

        self.trade_log.append(trade)
        return cash

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        required_cols = {"Date", "Close", "Signal"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        data = df.copy().sort_values("Date").reset_index(drop=True)

        cash = float(self.initial_capital)
        shares = 0.0

        entry_date = None
        entry_signal_price = None
        entry_execution_price = None
        entry_total_cost = None

        cash_history = []
        shares_history = []
        holdings_history = []
        portfolio_history = []
        entry_price_history = []
        actual_position_history = []

        self.trade_log = []

        first_price = float(data["Close"].iloc[0])
        initial_buy_hold_investment = max(
            self.initial_capital - self.commission_per_trade,
            0.0,
        )
        buy_hold_entry_price = first_price * (1 + self.slippage_pct)
        buy_hold_shares = (
            initial_buy_hold_investment / buy_hold_entry_price
            if buy_hold_entry_price > 0
            else 0.0
        )
        buy_hold_history = []

        for _, row in data.iterrows():
            date = pd.to_datetime(row["Date"])
            price = float(row["Close"])
            signal = int(row["Signal"])
            exited_this_bar = False

            if shares > 0 and entry_signal_price is not None:
                stop_price = entry_signal_price * (1 - self.stop_loss_pct)
                if price <= stop_price:
                    cash = self._close_position(
                        date=date,
                        market_price=price,
                        shares=shares,
                        cash=cash,
                        entry_date=entry_date,
                        entry_signal_price=entry_signal_price,
                        entry_execution_price=entry_execution_price,
                        entry_total_cost=entry_total_cost,
                        exit_reason="stop_loss",
                    )
                    shares = 0.0
                    entry_date = None
                    entry_signal_price = None
                    entry_execution_price = None
                    entry_total_cost = None
                    exited_this_bar = True

            if signal == 1 and shares == 0 and not exited_this_bar:
                allocation = cash * self.position_size

                if allocation > self.commission_per_trade and price > 0:
                    execution_price = price * (1 + self.slippage_pct)
                    investable_amount = allocation - self.commission_per_trade
                    shares = investable_amount / execution_price
                    cash -= allocation

                    entry_date = date
                    entry_signal_price = price
                    entry_execution_price = execution_price
                    entry_total_cost = allocation

            elif signal == 0 and shares > 0:
                cash = self._close_position(
                    date=date,
                    market_price=price,
                    shares=shares,
                    cash=cash,
                    entry_date=entry_date,
                    entry_signal_price=entry_signal_price,
                    entry_execution_price=entry_execution_price,
                    entry_total_cost=entry_total_cost,
                    exit_reason="signal_exit",
                )
                shares = 0.0
                entry_date = None
                entry_signal_price = None
                entry_execution_price = None
                entry_total_cost = None

            holdings_value = shares * price
            portfolio_value = cash + holdings_value
            buy_hold_value = buy_hold_shares * price

            cash_history.append(cash)
            shares_history.append(shares)
            holdings_history.append(holdings_value)
            portfolio_history.append(portfolio_value)
            entry_price_history.append(entry_execution_price if entry_execution_price is not None else 0.0)
            actual_position_history.append(1 if shares > 0 else 0)
            buy_hold_history.append(buy_hold_value)

        data["Cash"] = cash_history
        data["Shares"] = shares_history
        data["Holdings_Value"] = holdings_history
        data["Portfolio_Value"] = portfolio_history
        data["Entry_Price"] = entry_price_history
        data["Actual_Position"] = actual_position_history
        data["Actual_Position_Change"] = data["Actual_Position"].diff().fillna(0)
        data["Buy_Hold_Value"] = buy_hold_history
        data["Buy_Hold_Shares"] = buy_hold_shares

        return data