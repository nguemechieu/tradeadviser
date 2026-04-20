import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from quant.allocation_models import equal_weight_allocation, inverse_volatility_allocation, normalize_weights
from quant.portfolio_allocator import PortfolioAllocator


class FakeDataset:
    def __init__(self, frame):
        self.frame = frame
        self.empty = frame is None or frame.empty


def _frame_from_closes(closes):
    rows = []
    for index, close in enumerate(closes):
        value = float(close)
        rows.append(
            {
                "timestamp": index,
                "open": value,
                "high": value * 1.01,
                "low": value * 0.99,
                "close": value,
                "volume": 1000.0 + index,
            }
        )
    return pd.DataFrame(rows)


def test_equal_weight_allocation_balances_strategies():
    weights = equal_weight_allocation(["Trend Following", "Mean Reversion", "AI Hybrid"])

    assert weights["Trend Following"] == weights["Mean Reversion"] == weights["AI Hybrid"]
    assert round(sum(weights.values()), 6) == 1.0


def test_inverse_volatility_allocation_overweights_lower_volatility():
    weights = inverse_volatility_allocation({"Trend Following": 0.20, "Mean Reversion": 0.10})

    assert weights["Mean Reversion"] > weights["Trend Following"]
    assert round(sum(weights.values()), 6) == 1.0


def test_normalize_weights_handles_arbitrary_values():
    weights = normalize_weights({"Trend Following": 3, "Mean Reversion": 1})

    assert weights["Trend Following"] == 0.75
    assert weights["Mean Reversion"] == 0.25


def test_portfolio_allocator_approves_trade_within_strategy_budget():
    allocator = PortfolioAllocator(
        account_equity=10000,
        strategy_weights={"Trend Following": 0.60, "Mean Reversion": 0.40},
        max_strategy_allocation_pct=0.70,
    )
    allocator.register_strategy_symbol("ETH/USDT", "Mean Reversion")
    portfolio = SimpleNamespace(
        positions={"ETH/USDT": SimpleNamespace(quantity=10, avg_price=100)},
    )
    decision = asyncio.run(
        allocator.allocate_trade(
            symbol="BTC/USDT",
            strategy_name="Trend Following",
            side="buy",
            amount=5,
            price=100,
            portfolio=portfolio,
            market_prices={"ETH/USDT": 100, "BTC/USDT": 100},
            dataset=FakeDataset(_frame_from_closes([100, 101, 102, 103, 104, 105, 106])),
            confidence=0.8,
            active_strategies=["Trend Following", "Mean Reversion"],
        )
    )

    assert decision.approved is True
    assert decision.adjusted_amount > 0


def test_portfolio_allocator_rejects_when_strategy_budget_is_used_up():
    allocator = PortfolioAllocator(
        account_equity=10000,
        strategy_weights={"Trend Following": 0.20, "Mean Reversion": 0.80},
        max_strategy_allocation_pct=0.80,
    )
    allocator.register_strategy_symbol("BTC/USDT", "Trend Following")
    portfolio = SimpleNamespace(
        positions={"BTC/USDT": SimpleNamespace(quantity=20, avg_price=100)},
    )
    decision = asyncio.run(
        allocator.allocate_trade(
            symbol="SOL/USDT",
            strategy_name="Trend Following",
            side="buy",
            amount=2,
            price=100,
            portfolio=portfolio,
            market_prices={"BTC/USDT": 100, "SOL/USDT": 100},
            dataset=FakeDataset(_frame_from_closes([100, 100.5, 101, 101.5, 102, 102.5])),
            confidence=0.7,
            active_strategies=["Trend Following", "Mean Reversion"],
        )
    )

    assert decision.approved is False
    assert "headroom" in decision.reason.lower()


def test_portfolio_allocator_scales_down_large_trade_in_high_volatility():
    allocator = PortfolioAllocator(
        account_equity=10000,
        strategy_weights={"Trend Following": 1.0},
        max_strategy_allocation_pct=1.0,
        volatility_target_pct=0.12,
    )
    volatile_frame = _frame_from_closes([100, 120, 90, 130, 85, 135, 80, 140, 78, 142])
    decision = asyncio.run(
        allocator.allocate_trade(
            symbol="BTC/USDT",
            strategy_name="Trend Following",
            side="buy",
            amount=20,
            price=100,
            portfolio=SimpleNamespace(positions={}),
            market_prices={"BTC/USDT": 100},
            dataset=FakeDataset(volatile_frame),
            confidence=0.9,
            active_strategies=["Trend Following"],
        )
    )

    assert decision.approved is True
    assert decision.adjusted_amount < 20
    assert "reduced" in decision.reason.lower()


def test_portfolio_allocator_uses_small_remaining_budget_instead_of_rejecting():
    allocator = PortfolioAllocator(
        account_equity=10000,
        strategy_weights={"Trend Following": 0.20, "Mean Reversion": 0.80},
        max_strategy_allocation_pct=0.80,
    )
    allocator.register_strategy_symbol("BTC/USDT", "Trend Following")
    portfolio = SimpleNamespace(
        positions={"BTC/USDT": SimpleNamespace(quantity=19.7, avg_price=100)},
    )
    decision = asyncio.run(
        allocator.allocate_trade(
            symbol="SOL/USDT",
            strategy_name="Trend Following",
            side="buy",
            amount=2,
            price=100,
            portfolio=portfolio,
            market_prices={"BTC/USDT": 100, "SOL/USDT": 100},
            dataset=FakeDataset(_frame_from_closes([100, 100.5, 101, 101.5, 102, 102.5])),
            confidence=0.7,
            active_strategies=["Trend Following", "Mean Reversion"],
        )
    )

    assert decision.approved is True
    assert 0 < decision.adjusted_amount < 2
    assert "remaining available allocation" in decision.reason.lower()
    assert decision.metrics["below_minimum_useful_allocation"] is True


def test_portfolio_allocator_uses_actual_tiny_equity_for_budgeting():
    allocator = PortfolioAllocator(
        account_equity=0.25,
        strategy_weights={"Trend Following": 1.0},
        max_strategy_allocation_pct=1.0,
    )

    decision = asyncio.run(
        allocator.allocate_trade(
            symbol="BTC/USDT",
            strategy_name="Trend Following",
            side="buy",
            amount=1.0,
            price=100.0,
            portfolio=SimpleNamespace(positions={}),
            market_prices={"BTC/USDT": 100.0},
            dataset=FakeDataset(_frame_from_closes([100, 100.2, 100.4, 100.3, 100.5, 100.6])),
            confidence=1.0,
            active_strategies=["Trend Following"],
        )
    )

    assert decision.approved is True
    assert decision.adjusted_amount == pytest.approx(0.0025)
