"""Portfolio Optimization and Risk Analysis Tools."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class RiskMetric(Enum):
    """Risk analysis metrics."""
    VALUE_AT_RISK = "var"
    EXPECTED_SHORTFALL = "es"
    SHARPE_RATIO = "sharpe"
    SORTINO_RATIO = "sortino"
    MAX_DRAWDOWN = "max_drawdown"
    CALMAR_RATIO = "calmar"


@dataclass
class Portfolio:
    """Portfolio representation."""
    symbols: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    positions: dict[str, float] = field(default_factory=dict)
    cash: float = 0.0
    total_value: float = 0.0

    def normalized_weights(self) -> dict[str, float]:
        """Get normalized portfolio weights."""
        total = sum(self.weights.values())
        return {} if total <= 0 else {s: w / total for s, w in self.weights.items()}

    def gross_exposure(self) -> float:
        """Calculate total gross exposure."""
        return sum(abs(w) for w in self.weights.values())

    def net_exposure(self) -> float:
        """Calculate net exposure."""
        return sum(self.weights.values())

    def concentration(self) -> float:
        """Calculate portfolio concentration (HHI index)."""
        weights = self.normalized_weights()
        return sum(w ** 2 for w in weights.values())


@dataclass
class RiskAnalysis:
    """Risk analysis results."""
    var_95: float = 0.0  # Value at Risk (95%)
    var_99: float = 0.0  # Value at Risk (99%)
    es_95: float = 0.0   # Expected Shortfall (95%)
    es_99: float = 0.0   # Expected Shortfall (99%)
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    beta: float = 0.0
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if portfolio risk profile is healthy."""
        return (
            abs(self.var_95) < 0.1 and  # Less than 10% VaR
            abs(self.max_drawdown) < 0.2 and  # Less than 20% max drawdown
            self.sharpe_ratio > 0.5  # Positive Sharpe ratio
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "var_95": round(self.var_95, 4),
            "var_99": round(self.var_99, 4),
            "es_95": round(self.es_95, 4),
            "es_99": round(self.es_99, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "beta": round(self.beta, 4),
            "is_healthy": self.is_healthy(),
        }


class PortfolioAnalyzer(ABC):
    """Base class for portfolio analysis."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def analyze(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Analyze portfolio risk."""
        return RiskAnalysis()


class RiskAnalyzer(PortfolioAnalyzer):
    """Comprehensive risk analysis."""

    def __init__(self, logger: logging.Logger | None = None, risk_free_rate: float = 0.02):
        super().__init__(logger)
        self.risk_free_rate = risk_free_rate

    def analyze(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Analyze portfolio risk metrics."""
        if not returns or len(returns) < 2:
            self.logger.warning("Insufficient return data for analysis")
            return RiskAnalysis()

        returns_array = np.array(returns)
        analysis = RiskAnalysis()

        try:
            # Value at Risk
            analysis.var_95 = np.percentile(returns_array, 5)
            analysis.var_99 = np.percentile(returns_array, 1)

            # Expected Shortfall
            analysis.es_95 = returns_array[returns_array <= analysis.var_95].mean()
            analysis.es_99 = returns_array[returns_array <= analysis.var_99].mean()

            # Max Drawdown
            analysis.max_drawdown = self._calculate_max_drawdown(returns_array)

            # Sharpe Ratio
            excess_returns = returns_array - self.risk_free_rate / 252
            analysis.sharpe_ratio = (
                (excess_returns.mean() / excess_returns.std() * np.sqrt(252))
                if excess_returns.std() > 0 else 0
            )

            # Sortino Ratio
            downside_returns = excess_returns[excess_returns < 0]
            downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
            analysis.sortino_ratio = (
                (excess_returns.mean() / downside_std * np.sqrt(252))
                if downside_std > 0 else 0
            )

            # Calmar Ratio
            analysis.calmar_ratio = (
                (excess_returns.mean() * 252 / abs(analysis.max_drawdown))
                if analysis.max_drawdown < 0 else 0
            )

            self.logger.debug(
                "Risk analysis complete: VaR95=%.4f, Sharpe=%.4f, MaxDD=%.4f",
                analysis.var_95, analysis.sharpe_ratio, analysis.max_drawdown
            )
        except Exception as e:
            self.logger.error("Error in risk analysis: %s", e, exc_info=True)

        return analysis

    @staticmethod
    def _calculate_max_drawdown(returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        return float(np.min(drawdown))


class PortfolioOptimizer(PortfolioAnalyzer):
    """Mean-variance portfolio optimization."""

    def __init__(self, logger: logging.Logger | None = None, target_return: float = 0.15):
        super().__init__(logger)
        self.target_return = target_return

    def optimize(self, assets: dict[str, list[float]]) -> dict[str, float]:
        """Optimize portfolio weights using mean-variance.
        
        Args:
            assets: Dict of asset_name -> returns_list
            
        Returns:
            Dict of asset_name -> weight
        """
        if not assets or len(assets) < 2:
            self.logger.warning("Need at least 2 assets to optimize")
            return {}

        try:
            asset_names = list(assets.keys())
            returns_matrix = np.array([assets[name] for name in asset_names])

            # Calculate expected returns and covariance
            expected_returns = np.mean(returns_matrix, axis=1)
            cov_matrix = np.cov(returns_matrix)

            # Simple equal-weight optimization
            n = len(asset_names)
            weights = np.ones(n) / n

            # Try to adjust for risk
            try:
                inv_cov = np.linalg.inv(cov_matrix)
                ones = np.ones(n)
                weights = inv_cov @ ones
                weights /= weights.sum()
            except np.linalg.LinAlgError:
                self.logger.warning("Covariance matrix singular, using equal weights")

            result = dict(zip(asset_names, weights))
            self.logger.info("Portfolio optimized: %s", result)
            return result
        except Exception as e:
            self.logger.error("Optimization failed: %s", e, exc_info=True)
            return {}

    def analyze(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Not used for optimizer."""
        return RiskAnalysis()


class StressTestAnalyzer(PortfolioAnalyzer):
    """Stress test portfolio under extreme scenarios."""

    def analyze(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Analyze portfolio under stress scenarios."""
        if not returns or len(returns) < 2:
            return RiskAnalysis()

        returns_array = np.array(returns)
        analysis = RiskAnalysis()

        try:
            # Get worst case scenarios
            worst_days = np.sort(returns_array)[:int(len(returns_array) * 0.05)]
            analysis.var_95 = worst_days.mean()

            # Black swan scenarios (1%)
            extreme_days = np.sort(returns_array)[:int(len(returns_array) * 0.01)]
            if len(extreme_days) > 0:
                analysis.var_99 = extreme_days.mean()

            self.logger.debug(
                "Stress test: VaR95=%.4f, VaR99=%.4f",
                analysis.var_95, analysis.var_99
            )
        except Exception as e:
            self.logger.error("Stress test failed: %s", e)

        return analysis


class RiskManager:
    """Unified risk management interface."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("RiskManager")
        self.risk_analyzer = RiskAnalyzer(logger)
        self.optimizer = PortfolioOptimizer(logger)
        self.stress_tester = StressTestAnalyzer(logger)

    def analyze_portfolio(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Comprehensive portfolio risk analysis."""
        return self.risk_analyzer.analyze(portfolio, returns)

    def optimize_weights(self, assets: dict[str, list[float]]) -> dict[str, float]:
        """Optimize portfolio weights."""
        return self.optimizer.optimize(assets)

    def stress_test(self, portfolio: Portfolio, returns: list[float]) -> RiskAnalysis:
        """Stress test portfolio."""
        return self.stress_tester.analyze(portfolio, returns)

    def recommend_rebalance(
        self,
        portfolio: Portfolio,
        target_concentration: float = 0.15
    ) -> dict[str, float]:
        """Recommend portfolio rebalancing.
        
        Args:
            portfolio: Current portfolio
            target_concentration: Target HHI concentration
            
        Returns:
            Recommended weight changes
        """
        concentration = portfolio.concentration()
        if concentration <= target_concentration:
            self.logger.debug("Portfolio concentration acceptable: %.4f", concentration)
            return {}

        # Recommend equal-weight rebalancing
        n_symbols = len(portfolio.symbols)
        if n_symbols == 0:
            return {}

        target_weight = 1.0 / n_symbols
        changes = {}
        for symbol in portfolio.symbols:
            current = portfolio.weights.get(symbol, 0)
            change = target_weight - current
            if abs(change) > 0.01:  # Only report significant changes
                changes[symbol] = change

        self.logger.info("Rebalancing recommended: %s", changes)
        return changes
