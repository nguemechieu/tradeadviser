import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.agents.trader_agent import InvestorProfile, TraderAgent
from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import FeatureVector, PortfolioSnapshot, PositionUpdate, ReasoningDecision, Signal, TradeFeedback
from sopotek.core.orchestrator import SopotekRuntime
from sopotek.engines.strategy import BaseStrategy


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class ConstantPredictor:
    def __init__(self, probability: float, *, is_fitted: bool = True) -> None:
        self.probability = float(probability)
        self.is_fitted = bool(is_fitted)

    def predict_probability(self, _features) -> float:
        return self.probability


class DummyBroker:
    def __init__(self):
        self.orders = []

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        return []

    async def place_order(self, order):
        self.orders.append(order)
        return {
            "id": f"order-{len(self.orders)}",
            "status": "filled",
            "price": order.price,
            "fill_price": order.price,
            "filled_quantity": order.quantity,
        }

    async def stream_ticks(self, symbol: str):
        if False:
            yield {"symbol": symbol, "price": 0.0}


class HistoricalBroker(DummyBroker):
    def __init__(self):
        super().__init__()
        self.history_requests = []

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        self.history_requests.append((symbol, timeframe, limit))
        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start = end - timedelta(minutes=max(limit - 1, 0))
        rows = []
        for index in range(limit):
            timestamp = start + timedelta(minutes=index)
            close = 100.0 + (index * 0.4)
            rows.append(
                [
                    int(timestamp.timestamp() * 1000),
                    close - 0.25,
                    close + 0.35,
                    close - 0.45,
                    close,
                    100.0 if index < limit - 1 else 240.0,
                ]
            )
        return rows


class TrendStrategy(BaseStrategy):
    name = "trend"

    async def generate_signal(self, *, symbol: str, trigger: str, payload):
        if trigger != EventType.MARKET_TICK:
            return None
        price = float(payload["price"])
        return Signal(
            symbol=symbol,
            side="buy",
            quantity=1.0,
            price=price,
            confidence=0.82,
            strategy_name=self.name,
            reason="trend continuation",
        )


def test_trader_agent_conservative_profile_skips_low_confidence_signal():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "income": InvestorProfile(
                    risk_level="low",
                    goal="income",
                    max_drawdown=0.05,
                    trade_frequency="low",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="long",
                )
            },
            active_profile_id="income",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.65,
                strategy_name="trend_following",
                reason="marginal setup",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders

    decision, orders = asyncio.run(scenario())

    assert decision.action == "SKIP"
    assert "confidence" in decision.reasoning.lower()
    assert orders == []


def test_trader_agent_weighted_vote_and_ml_reduce_order_size():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="high",
                    goal="growth",
                    max_drawdown=0.12,
                    trade_frequency="high",
                    preferred_assets=["ETH/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
            predictor=ConstantPredictor(0.55),
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "ETH/USDT", "price": 101.0}, priority=19)
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="ETH/USDT",
                timeframe="1m",
                values={"rsi": 33.0, "ema_gap": 0.02, "volatility": 0.012, "order_book_imbalance": 0.18},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(symbol="ETH/USDT", side="buy", quantity=2.0, price=101.0, confidence=0.62, strategy_name="trend_following", reason="trend"),
            priority=61,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(symbol="ETH/USDT", side="buy", quantity=1.5, price=101.0, confidence=0.58, strategy_name="breakout", reason="breakout"),
            priority=61,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(symbol="ETH/USDT", side="sell", quantity=1.0, price=101.0, confidence=0.51, strategy_name="mean_reversion", reason="fade"),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert decision.selected_strategy == "trend_following"
    assert decision.model_probability == pytest.approx(0.55)
    assert order.quantity == pytest.approx(3.0)
    assert order.metadata["profile_id"] == "growth"
    assert "growth" in decision.reasoning


def test_trader_agent_uses_signal_metadata_features_when_feature_vector_is_missing():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.81,
                strategy_name="trend_following",
                reason="trend continuation",
                metadata={
                    "timeframe": "1m",
                    "features": {
                        "rsi": 28.0,
                        "ema_gap": 0.018,
                        "volatility": 0.011,
                        "order_book_imbalance": 0.24,
                    },
                },
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1]

    decision = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert decision.features["rsi"] == pytest.approx(28.0)
    assert decision.features["ema_gap"] == pytest.approx(0.018)
    assert "RSI=28.0" in decision.reasoning
    assert "order book imbalance=0.240" in decision.reasoning


def test_trader_agent_reverses_a_losing_position_when_the_new_direction_is_stronger():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
            predictor=ConstantPredictor(0.83),
        )
        agent.attach(bus)
        decisions = []
        close_requests = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        agent.suspend_evaluations()
        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 104.0}, priority=19)
        await bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="BTC/USDT",
                quantity=-1.0,
                average_price=100.0,
                current_price=104.0,
                unrealized_pnl=-4.0,
            ),
            priority=88,
        )
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={"rsi": 29.0, "ema_gap": 0.026, "volatility": 0.012, "order_book_imbalance": 0.21},
            ),
            priority=45,
        )
        await _drain(bus)

        agent.resume_evaluations()
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=104.0,
                confidence=0.91,
                strategy_name="trend_following",
                reason="trend resumed higher",
            ),
            priority=61,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="sell",
                quantity=0.8,
                price=104.0,
                confidence=0.51,
                strategy_name="mean_reversion",
                reason="weak fade",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], close_requests[-1], orders[-1]

    decision, close_request, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert decision.metadata["position_management"]["action"] == "reverse"
    assert close_request.side == "buy"
    assert close_request.quantity == pytest.approx(1.0)
    assert order.side == "buy"
    assert order.metadata["position_management"]["action"] == "reverse"


def test_trader_agent_reduces_risk_on_a_bad_trade_even_without_a_fresh_signal():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.08,
                    trade_frequency="medium",
                    preferred_assets=["ETH/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        close_requests = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        agent.suspend_evaluations()
        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "ETH/USDT", "price": 94.0}, priority=19)
        await bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="ETH/USDT",
                quantity=2.0,
                average_price=100.0,
                current_price=94.0,
                unrealized_pnl=-12.0,
            ),
            priority=88,
        )
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="ETH/USDT",
                timeframe="1m",
                values={"rsi": 78.0, "ema_gap": -0.031, "volatility": 0.015, "order_book_imbalance": -0.24},
            ),
            priority=45,
        )
        await _drain(bus)

        agent.resume_evaluations()
        await agent.queue_evaluation("ETH/USDT", profile_id="growth", force=True)
        await _drain(bus)
        return decisions[-1], close_requests[-1], orders

    decision, close_request, orders = asyncio.run(scenario())

    assert decision.action == "REDUCE"
    assert decision.metadata["position_management"]["action"] == "reduce"
    assert close_request.side == "sell"
    assert close_request.quantity == pytest.approx(1.0)
    assert orders == []


def test_trader_agent_reduces_same_side_entry_size_when_position_is_already_open():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="BTC/USDT",
                quantity=0.6,
                average_price=98.0,
                current_price=100.0,
                unrealized_pnl=1.2,
            ),
            priority=88,
        )
        await _drain(bus)
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.84,
                strategy_name="trend_following",
                reason="trend continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert "existing_position_reduce" in decision.applied_constraints
    assert order.quantity == pytest.approx(0.4)


def test_trader_agent_reduces_new_order_size_when_same_side_order_is_already_active():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["ETH/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "ETH/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.ORDER_SUBMITTED,
            {
                "order_id": "ord-1",
                "symbol": "ETH/USDT",
                "side": "buy",
                "quantity": 0.35,
                "remaining_quantity": 0.35,
                "status": "submitted",
            },
            priority=75,
        )
        await _drain(bus)
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="ETH/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.84,
                strategy_name="trend_following",
                reason="trend continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert "active_order_reduce" in decision.applied_constraints
    assert order.quantity == pytest.approx(0.65)


def test_trader_agent_skips_wide_spread_entries_even_with_a_directional_signal():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={
                    "rsi": 42.0,
                    "ema_gap": 0.018,
                    "volatility": 0.010,
                    "order_book_imbalance": 0.17,
                    "order_book_spread_bps": 31.0,
                    "volume_ratio": 1.08,
                },
            ),
            priority=45,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.83,
                strategy_name="trend_following",
                reason="breakout continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders

    decision, orders = asyncio.run(scenario())

    assert decision.action == "SKIP"
    assert "spread" in decision.reasoning.lower()
    assert "wide_spread" in decision.applied_constraints
    assert orders == []


def test_trader_agent_scales_down_new_entries_when_portfolio_is_near_exposure_limit():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["ETH/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(
            EventType.PORTFOLIO_SNAPSHOT,
            PortfolioSnapshot(
                cash=3500.0,
                equity=10000.0,
                gross_exposure=6500.0,
                net_exposure=6500.0,
            ),
            priority=52,
        )
        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "ETH/USDT", "price": 1000.0}, priority=19)
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="ETH/USDT",
                timeframe="1m",
                values={"rsi": 39.0, "ema_gap": 0.020, "volatility": 0.011, "order_book_imbalance": 0.16},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="ETH/USDT",
                side="buy",
                quantity=2.0,
                price=1000.0,
                confidence=0.84,
                strategy_name="trend_following",
                reason="buyers in control",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert "portfolio_reduce" not in decision.applied_constraints
    assert order.quantity == pytest.approx(2.0)


def test_trader_agent_de_risks_after_two_losses_in_a_row():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["SOL/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        for exit_price in (96.0, 94.0):
            await bus.publish(
                EventType.TRADE_FEEDBACK,
                TradeFeedback(
                    symbol="SOL/USDT",
                    strategy_name="trend_following",
                    side="buy",
                    quantity=1.0,
                    entry_price=100.0,
                    exit_price=exit_price,
                    pnl=exit_price - 100.0,
                    success=False,
                    metadata={"profile_id": "growth"},
                ),
                priority=90,
            )
        await _drain(bus)
        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "SOL/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="SOL/USDT",
                timeframe="1m",
                values={"rsi": 41.0, "ema_gap": 0.016, "volatility": 0.010, "order_book_imbalance": 0.14},
            ),
            priority=45,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="SOL/USDT",
                side="buy",
                quantity=2.0,
                price=100.0,
                confidence=0.82,
                strategy_name="trend_following",
                reason="trend resuming",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert "loss_streak_reduce" not in decision.applied_constraints
    assert decision.metadata["performance_context"]["loss_streak"] == 2
    assert order.quantity == pytest.approx(2.0)


def test_trader_agent_uses_openai_reasoning_as_a_bounded_confirmation_layer():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.REASONING_DECISION,
            ReasoningDecision(
                symbol="BTC/USDT",
                strategy_name="trend_following",
                side="buy",
                decision="APPROVE",
                confidence=0.91,
                reasoning="OpenAI sees supportive trend and controlled risk.",
                risk="low",
                metadata={"provider": "openai"},
            ),
            priority=58,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.82,
                strategy_name="trend_following",
                reason="trend continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders[-1]

    decision, order = asyncio.run(scenario())

    assert decision.action == "BUY"
    assert "openai_reasoning_confirmed" in decision.applied_constraints
    assert decision.confidence > 0.82
    assert order.quantity == pytest.approx(1.0)
    assert decision.metadata["reasoning_contribution"]["provider"] == "openai"
    assert decision.metadata["reasoning_contribution"]["applied"] is True
    assert decision.metadata["reasoning_contribution"]["quantity_multiplier"] == pytest.approx(1.1)
    assert "OpenAI confirmed the BUY thesis" in decision.reasoning


def test_trader_agent_skips_when_openai_rejects_the_selected_trade():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["ETH/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
        )
        agent.attach(bus)
        decisions = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "ETH/USDT", "price": 100.0}, priority=19)
        await bus.publish(
            EventType.REASONING_DECISION,
            ReasoningDecision(
                symbol="ETH/USDT",
                strategy_name="trend_following",
                side="buy",
                decision="REJECT",
                confidence=0.92,
                reasoning="OpenAI sees too much event risk for a fresh long.",
                risk="high",
                warnings=["macro event risk"],
                metadata={"provider": "openai"},
            ),
            priority=58,
        )
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="ETH/USDT",
                side="buy",
                quantity=1.0,
                price=100.0,
                confidence=0.84,
                strategy_name="trend_following",
                reason="trend continuation",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], orders

    decision, orders = asyncio.run(scenario())

    assert decision.action == "SKIP"
    assert "openai_reasoning_reject" in decision.applied_constraints
    assert decision.metadata["reasoning_contribution"]["provider"] == "openai"
    assert decision.metadata["reasoning_contribution"]["decision"] == "REJECT"
    assert orders == []
    assert "OpenAI rejected" in decision.reasoning


def test_trader_agent_closes_but_does_not_reopen_reverse_when_execution_is_poor():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        agent = TraderAgent(
            profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_profile_id="growth",
            predictor=ConstantPredictor(0.82),
        )
        agent.attach(bus)
        decisions = []
        close_requests = []
        orders = []
        bus.subscribe(EventType.DECISION_EVENT, lambda event: decisions.append(event.data))
        bus.subscribe(EventType.CLOSE_POSITION, lambda event: close_requests.append(event.data))
        bus.subscribe(EventType.ORDER_EVENT, lambda event: orders.append(event.data))

        agent.suspend_evaluations()
        await bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 104.0}, priority=19)
        await bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="BTC/USDT",
                quantity=-1.0,
                average_price=100.0,
                current_price=104.0,
                unrealized_pnl=-4.0,
            ),
            priority=88,
        )
        await bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={
                    "rsi": 32.0,
                    "ema_gap": 0.020,
                    "volatility": 0.012,
                    "order_book_imbalance": 0.18,
                    "order_book_spread_bps": 32.0,
                },
            ),
            priority=45,
        )
        await _drain(bus)

        agent.resume_evaluations()
        await bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=104.0,
                confidence=0.90,
                strategy_name="trend_following",
                reason="buyers regained control",
            ),
            priority=61,
        )
        await _drain(bus)
        return decisions[-1], close_requests[-1], orders

    decision, close_request, orders = asyncio.run(scenario())

    assert decision.action == "CLOSE"
    assert decision.metadata["position_management"]["action"] == "close"
    assert "do not reopen" in decision.reasoning.lower()
    assert close_request.quantity == pytest.approx(1.0)
    assert orders == []


def test_runtime_trader_agent_routes_orders_through_risk_and_execution():
    async def scenario():
        runtime = SopotekRuntime(
            broker=DummyBroker(),
            starting_equity=100000.0,
            enable_default_agents=False,
            enable_trader_agent=True,
            trader_profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_trader_profile="growth",
        )
        runtime.register_strategy(TrendStrategy(), active=True)

        await runtime.market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 100.0})
        await _drain(runtime.bus)

        return runtime

    runtime = asyncio.run(scenario())

    assert runtime.trader_agent is not None
    assert runtime.broker.orders
    order = runtime.broker.orders[0]
    assert order.metadata["profile_id"] == "growth"
    assert runtime.execution_monitor.reports
    assert runtime.trader_agent.recent_decisions["growth"][-1].action == "BUY"


def test_runtime_trader_agent_flattens_then_reopens_when_reversing_a_bad_trade():
    async def scenario():
        runtime = SopotekRuntime(
            broker=DummyBroker(),
            starting_equity=100000.0,
            enable_default_agents=False,
            enable_trader_agent=True,
            trader_profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_trader_profile="growth",
        )

        runtime.trader_agent.suspend_evaluations()
        await runtime.bus.publish(
            EventType.POSITION_UPDATE,
            PositionUpdate(
                symbol="BTC/USDT",
                quantity=-1.0,
                average_price=100.0,
                current_price=104.0,
                unrealized_pnl=-4.0,
            ),
            priority=88,
        )
        await runtime.bus.publish(EventType.MARKET_DATA_EVENT, {"symbol": "BTC/USDT", "price": 104.0}, priority=19)
        await runtime.bus.publish(
            EventType.FEATURE_VECTOR,
            FeatureVector(
                symbol="BTC/USDT",
                timeframe="1m",
                values={"rsi": 28.0, "ema_gap": 0.024, "volatility": 0.011, "order_book_imbalance": 0.19},
            ),
            priority=45,
        )
        await runtime.bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="buy",
                quantity=1.0,
                price=104.0,
                confidence=0.89,
                strategy_name="trend_following",
                reason="buyers regained control",
            ),
            priority=61,
        )
        await _drain(runtime.bus)
        runtime.trader_agent.resume_evaluations()
        await runtime.bus.publish(
            EventType.SIGNAL_EVENT,
            Signal(
                symbol="BTC/USDT",
                side="sell",
                quantity=0.8,
                price=104.0,
                confidence=0.52,
                strategy_name="mean_reversion",
                reason="weak fade",
            ),
            priority=61,
        )
        await _drain(runtime.bus)
        orders = list(runtime.broker.orders)
        reports = list(runtime.execution_monitor.reports)
        decision = runtime.trader_agent.recent_decisions["growth"][-1]
        return decision, orders, reports

    decision, orders, reports = asyncio.run(scenario())

    assert decision.metadata["position_management"]["action"] == "reverse"
    assert len(orders) == 2
    assert orders[0].metadata["close_position"] is True
    assert orders[1].metadata.get("close_position") is not True
    assert len(reports) == 2


def test_runtime_start_warms_up_trader_agent_before_live_ticks():
    async def scenario():
        broker = HistoricalBroker()
        runtime = SopotekRuntime(
            broker=broker,
            starting_equity=100000.0,
            enable_default_agents=True,
            enable_trader_agent=True,
            trader_profiles={
                "growth": InvestorProfile(
                    risk_level="medium",
                    goal="growth",
                    max_drawdown=0.10,
                    trade_frequency="medium",
                    preferred_assets=["BTC/USDT"],
                    time_horizon="medium",
                )
            },
            active_trader_profile="growth",
            warmup_history_limit=40,
        )

        await runtime.start(["BTC/USDT"])
        await runtime.bus.queue.join()

        decision = runtime.trader_agent.recent_decisions["growth"][-1]
        orders = list(runtime.broker.orders)
        reports = list(runtime.execution_monitor.reports)
        history_requests = list(broker.history_requests)
        await runtime.stop()
        return decision, orders, reports, history_requests

    decision, orders, reports, history_requests = asyncio.run(scenario())

    assert history_requests == [("BTC/USDT", "1m", 40)]
    assert decision.action == "BUY"
    assert decision.features["ema_gap"] > 0.0
    assert orders
    assert orders[0].metadata["profile_id"] == "growth"
    assert reports
