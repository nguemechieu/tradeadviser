import warnings

import numpy as np

from engines.performance_engine import PerformanceEngine
from quant.analytics.metrics import Metrics
from quant.analytics.risk_metrics import RiskMetrics


def test_metrics_returns_skip_zero_denominators_and_non_finite_values_without_warnings():
    equity_curve = np.array([0.0, 1000.0, 1100.0, np.inf, 1210.0], dtype=float)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        returns = Metrics.returns(equity_curve)
        volatility = Metrics.volatility(returns)
        sharpe = Metrics.sharpe_ratio(returns)
        sortino = Metrics.sortino_ratio(returns)

    assert caught == []
    assert np.allclose(returns, np.array([0.1, 0.1]))
    assert np.isfinite(volatility)
    assert np.isfinite(sharpe)
    assert np.isfinite(sortino)


def test_performance_engine_report_handles_zero_starting_equity_without_runtime_warnings():
    engine = PerformanceEngine()
    engine.load_equity_history([0.0, 0.0, 100.0, 110.0])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        report = engine.report()

    assert caught == []
    assert report["cumulative_return"] == 0.0
    assert np.isfinite(report["volatility"])
    assert np.isfinite(report["sharpe_ratio"])
    assert np.isfinite(report["sortino_ratio"])
    assert np.isfinite(report["max_drawdown"])
    assert np.isfinite(report["value_at_risk"])
    assert np.isfinite(report["conditional_var"])


def test_performance_engine_report_ignores_non_finite_points_without_runtime_warnings():
    engine = PerformanceEngine()
    engine.load_equity_history([1000.0, np.nan, np.inf, 1100.0, 1210.0])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        report = engine.report()

    assert caught == []
    assert np.isclose(report["cumulative_return"], 0.21)
    assert np.isfinite(report["volatility"])
    assert np.isfinite(report["sharpe_ratio"])
    assert np.isfinite(report["sortino_ratio"])
    assert np.isfinite(report["max_drawdown"])
    assert np.isfinite(report["value_at_risk"])
    assert np.isfinite(report["conditional_var"])


def test_risk_metrics_return_safe_defaults_for_empty_or_invalid_inputs():
    returns = np.array([np.nan, np.inf, -np.inf], dtype=float)
    equity_curve = np.array([0.0, 0.0, np.nan], dtype=float)

    assert RiskMetrics.max_drawdown(equity_curve) == 0.0
    assert RiskMetrics.var(returns) == 0.0
    assert RiskMetrics.cvar(returns) == 0.0
