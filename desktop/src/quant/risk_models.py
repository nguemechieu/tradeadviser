import math

import pandas as pd


"""Quantitative risk model helpers for returns, volatility, and risk metrics."""


def safe_float(value, default=0.0):
    """Convert a value to float, returning a safe default on invalid input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def to_series(values):
    """Normalize input to a pandas Series of floats and drop missing values.

    Supports pandas Series, dictionaries, iterables, and scalar values.
    Returns an empty Series for None or invalid input.
    """
    if isinstance(values, pd.Series):
        return values.dropna().astype(float)

    if values is None:
        return pd.Series(dtype="float64")

    if isinstance(values, dict):
        values = list(values.values())

    try:
        series = pd.Series(values, dtype="float64")
    except (TypeError, ValueError):
        series = pd.Series([values], dtype="float64")

    return series.dropna()


def close_returns(frame):
    """Compute returns from a frame with a `close` series.

    Returns an empty Series when the input frame is invalid, missing the
    `close` column, or has insufficient data for percentage returns.
    """
    if frame is None or getattr(frame, "empty", True):
        return pd.Series(dtype="float64")
    if "close" not in frame.columns:
        return pd.Series(dtype="float64")
    closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if len(closes) < 3:
        return pd.Series(dtype="float64")
    return closes.pct_change().dropna()


def historical_var(returns, confidence=0.95):
    """Compute historical Value at Risk (VaR) at the given confidence level.

    The returned VaR is expressed as a non-negative loss number. Confidence is
    clamped to the range [0.01, 0.99] to avoid extreme quantile lookups.
    """
    series = to_series(returns)
    if series.empty:
        return 0.0
    alpha = max(0.01, min(0.99, 1.0 - float(confidence)))
    quantile = float(series.quantile(alpha))
    return max(0.0, -quantile)


def historical_cvar(returns, confidence=0.95):
    """Compute historical Conditional Value at Risk (CVaR).

    CVaR is the average loss in the worst alpha tail, where alpha is derived
    from the requested confidence level.
    """
    series = to_series(returns)
    if series.empty:
        return 0.0
    alpha = max(0.01, min(0.99, 1.0 - float(confidence)))
    cutoff = float(series.quantile(alpha))
    tail = series[series <= cutoff]
    if tail.empty:
        return historical_var(series, confidence=confidence)
    return max(0.0, -float(tail.mean()))


def annualized_volatility(returns, periods_per_year=252):
    """Annualize the standard deviation of returns using a year-length factor."""
    series = to_series(returns)
    if len(series) < 2:
        return 0.0
    return max(0.0, float(series.std(ddof=0)) * math.sqrt(max(1, int(periods_per_year))))


def correlation(left_returns, right_returns):
    """Compute the Pearson correlation between two return series.

    Returns 0.0 for missing or insufficient data, and avoids NaN results.
    """
    left = to_series(left_returns)
    right = to_series(right_returns)
    if left.empty or right.empty:
        return 0.0
    aligned = pd.concat([left.reset_index(drop=True), right.reset_index(drop=True)], axis=1).dropna()
    if len(aligned) < 5:
        return 0.0
    corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
    if pd.isna(corr):
        return 0.0
    return float(corr)


def kelly_fraction(returns, side="buy", cap=0.25):
    """Estimate the Kelly sizing fraction from historical returns.

    The function returns a non-negative value capped by `cap`. If returns are
    insufficient or the estimated edge is not positive, it returns 0.0.
    """
    series = to_series(returns)
    if len(series) < 5:
        return 0.0

    signed = series if str(side).lower() == "buy" else -series
    edge = float(signed.mean())
    variance = float(signed.var(ddof=0))
    if variance <= 0:
        return 0.0

    raw = edge / variance
    if raw <= 0:
        return 0.0
    return max(0.0, min(float(cap), float(raw)))
