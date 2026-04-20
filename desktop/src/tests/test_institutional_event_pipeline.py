import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.event_bus import AsyncEventBus
from execution.execution_engine import ExecutionEngine
from market_data.market_data_engine import MarketDataEngine
from portfolio.portfolio_engine import PortfolioEngine
from risk.risk_engine import RiskEngine
from sopotek.core.event_types import EventType
from sopotek.core.models import Signal


class RecordingBroker:
    def __init__(self) -> None:
        self.orders = []
        self.latest_prices = {}

    def update_market_price(self, symbol: str, price: float) -> None:
        self.latest_prices[str(symbol)] = float(price)

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200):
        return []

    async def fetch_ticker(self, symbol: str):
        return {"symbol": symbol, "price": self.latest_prices.get(symbol, 100.0)}

    async def create_order(self, symbol, type, side, amount, price=None, params=None):
        return await self.place_order(
            {
                "symbol": symbol,
                "type": type,
                "side": side,
                "amount": amount,
                "price": price,
                "params": dict(params or {}),
            }
        )

    async def place_order(self, order):
        payload = dict(order or {})
        symbol = str(payload.get("symbol"))
        quantity = float(payload.get("amount") or payload.get("quantity") or 0.0)
        price = float(payload.get("price") or self.latest_prices.get(symbol) or 0.0)
        response = {
            "id": f"test-order-{len(self.orders) + 1}",
            "status": "filled",
            "price": price,
            "fill_price": price,
            "filled_quantity": quantity,
            "remaining_quantity": 0.0,
            "partial": False,
            "latency_ms": 1.0,
            "slippage_bps": 0.0,
            "fee": 0.0,
        }
        self.orders.append(payload)
        return response


class ThresholdMomentumStrategy:
    def __init__(self, bus: AsyncEventBus, *, trigger_price: float = 101.0) -> None:
        self.bus = bus
        self.trigger_price = float(trigger_price)
        self.emitted = False
        self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    async def on_tick(self, event) -> None:
        if self.emitted:
            return
        payload = dict(getattr(event, "data", {}) or {})
        price = float(payload.get("price") or 0.0)
        if price < self.trigger_price:
            return
        self.emitted = True
        await self.bus.publish(
            EventType.SIGNAL,
            Signal(
                symbol=str(payload.get("symbol") or "BTC/USDT"),
                side="buy",
                quantity=2.0,
                price=price,
                confidence=0.81,
                strategy_name="threshold_momentum",
                reason="Price breakout",
                metadata={"sector": "crypto", "asset_class": "crypto"},
            ),
            priority=60,
            source="test_strategy",
        )


def test_institutional_pipeline_processes_market_data_to_portfolio_update():
    async def scenario():
        bus = AsyncEventBus(queue_maxsize=128)
        broker = RecordingBroker()
        market_data = MarketDataEngine(broker, bus)
        portfolio = PortfolioEngine(bus, starting_cash=100000.0, symbol_sectors={"BTC/USDT": "crypto"})
        risk = RiskEngine(
            bus,
            portfolio_engine=portfolio,
            starting_equity=100000.0,
            max_risk_per_trade=0.02,
            max_portfolio_exposure=1.0,
            per_symbol_exposure_cap=0.25,
            max_drawdown_limit=0.25,
            daily_loss_limit=0.20,
        )
        execution = ExecutionEngine(broker, bus, queue_maxsize=32)
        strategy = ThresholdMomentumStrategy(bus)

        approved_reviews = []
        execution_reports = []
        bus.subscribe(EventType.RISK_APPROVED, lambda event: approved_reviews.append(event.data))
        bus.subscribe(EventType.EXECUTION_REPORT, lambda event: execution_reports.append(event.data))

        bus.run_in_background()
        await market_data.publish_tick("BTC/USDT", {"symbol": "BTC/USDT", "price": 101.5})

        for _ in range(50):
            if execution_reports:
                break
            await asyncio.sleep(0.01)

        await execution.flush()
        await asyncio.sleep(0.05)

        snapshot = portfolio.snapshot()

        await execution.shutdown()
        await bus.shutdown()

        return {
            "strategy": strategy,
            "risk": risk,
            "approved_reviews": approved_reviews,
            "execution_reports": execution_reports,
            "snapshot": snapshot,
            "orders": list(broker.orders),
        }

    result = asyncio.run(scenario())

    assert result["strategy"].emitted is True
    assert len(result["approved_reviews"]) == 1
    assert len(result["execution_reports"]) == 1
    assert len(result["orders"]) == 1
    assert result["snapshot"].equity > 0.0
    assert result["snapshot"].gross_exposure > 0.0
    assert "BTC/USDT" in result["snapshot"].positions
    assert result["snapshot"].positions["BTC/USDT"].quantity > 0.0


def test_risk_engine_rejects_trade_that_breaches_symbol_exposure_cap():
    bus = AsyncEventBus()
    portfolio = PortfolioEngine(bus, starting_cash=100000.0, symbol_sectors={"BTC/USDT": "crypto"})
    risk = RiskEngine(
        bus,
        portfolio_engine=portfolio,
        starting_equity=100000.0,
        max_risk_per_trade=0.05,
        max_portfolio_exposure=1.0,
        per_symbol_exposure_cap=0.05,
        max_drawdown_limit=0.20,
        daily_loss_limit=0.20,
    )

    review = risk.review_signal(
        Signal(
            symbol="BTC/USDT",
            side="buy",
            quantity=100.0,
            price=1000.0,
            confidence=0.9,
            strategy_name="oversized_trade",
            reason="Intentional stress test",
            metadata={"asset_class": "crypto"},
        )
    )

    assert review.approved is False
    assert "exposure" in review.reason.lower()
