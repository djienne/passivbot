"""
Analytics and metrics calculation functions.
"""
import pandas as pd


def calc_drawdowns(equity_series):
    """
    Calculate the drawdowns of a portfolio of equities over time.

    Parameters:
    equity_series (pandas.Series): A pandas Series containing the portfolio's equity values over time.

    Returns:
    drawdowns (pandas.Series): The drawdowns as a percentage (expressed as a negative value).
    """
    if not isinstance(equity_series, pd.Series):
        equity_series = pd.Series(equity_series)

    # Calculate the cumulative returns of the portfolio
    cumulative_returns = (1 + equity_series.pct_change()).cumprod()

    # Calculate the cumulative maximum value over time
    cumulative_max = cumulative_returns.cummax()

    # Return the drawdown as the percentage decline from the cumulative maximum
    return (cumulative_returns - cumulative_max) / cumulative_max


def calc_max_drawdown(equity_series):
    """Calculate maximum drawdown from equity series."""
    return calc_drawdowns(equity_series).min()


def calc_sharpe_ratio(equity_series):
    """
    Calculate the Sharpe ratio for a portfolio of equities assuming a zero risk-free rate.

    Parameters:
    equity_series (pandas.Series): A pandas Series containing daily equity values.

    Returns:
    float: The Sharpe ratio.
    """
    if not isinstance(equity_series, pd.Series):
        equity_series = pd.Series(equity_series)

    # Calculate the hourly returns
    returns = equity_series.pct_change().dropna()
    std_dev = returns.std()
    return returns.mean() / std_dev if std_dev != 0.0 else 0.0
