import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sopotek.core.event_bus import AsyncEventBus, InMemoryEventStore
from sopotek.core.event_types import EventType
from sopotek.core.models import TradeFeedback
from sopotek.services import MobileDashboardService, TradeJournalAIEngine


async def _drain(bus: AsyncEventBus) -> None:
    while not bus.queue.empty():
        await bus.dispatch_once()


class MemoryQuantRepository:
    def __init__(self) -> None:
        self.entries = []
        self.summaries = []

    def save_trade_journal_entry(self, entry):
        self.entries.append(entry)
        return entry

    def save_trade_journal_summary(self, summary):
        self.summaries.append(summary)
        return summary

    def load_trade_journal_entries(self, *, limit=100, symbol=None):
        rows = list(self.entries)
        if symbol:
            rows = [row for row in rows if row.symbol == symbol]
        return rows[-int(limit):]


class MemoryTradeRepository:
    def __init__(self) -> None:
        self.updates = []

    def update_trade_journal(self, **kwargs):
        self.updates.append(kwargs)
        return kwargs


def test_trade_journal_ai_diagnoses_loss_and_records_improvements():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        quant_repository = MemoryQuantRepository()
        trade_repository = MemoryTradeRepository()
        engine = TradeJournalAIEngine(
            bus,
            quant_repository=quant_repository,
            trade_repository=trade_repository,
            publish_summary_every=1,
            summary_window=10,
        )
        entries = []
        summaries = []
        bus.subscribe(EventType.TRADE_JOURNAL_ENTRY, lambda event: entries.append(event.data))
        bus.subscribe(EventType.TRADE_JOURNAL_SUMMARY, lambda event: summaries.append(event.data))

        await bus.publish(
            EventType.TRADE_FEEDBACK,
            TradeFeedback(
                symbol="BTC/USDT",
                strategy_name="breakout",
                side="buy",
                quantity=1.0,
                entry_price=100.0,
                exit_price=96.0,
                pnl=-4.0,
                success=False,
                model_probability=0.35,
                features={
                    "rsi": 74.0,
                    "ema_gap": -0.03,
                    "volatility": 0.028,
                    "order_book_imbalance": -0.24,
                },
                metadata={
                    "market_session": "tokyo",
                    "high_liquidity_session": False,
                    "exit_order_id": "order-loss-1",
                },
            ),
            priority=91,
        )
        await _drain(bus)
        return entries[-1], summaries[-1], quant_repository, trade_repository, engine

    entry, summary, quant_repository, trade_repository, engine = asyncio.run(scenario())

    assert entry.outcome == "Loss"
    assert any("trend" in reason.lower() for reason in entry.why_it_lost)
    assert any("rsi" in reason.lower() for reason in entry.why_it_lost)
    assert any("volatility" in reason.lower() for reason in entry.why_it_lost)
    assert any("ml" in improvement.lower() for improvement in entry.what_to_improve)
    assert any("session" in bit.lower() or "liquidity" in bit.lower() for bit in entry.what_to_improve)
    assert quant_repository.entries
    assert quant_repository.summaries
    assert trade_repository.updates[-1]["order_id"] == "order-loss-1"
    assert summary.losses == 1
    assert summary.recurring_loss_patterns
    assert engine.entries[-1].symbol == "BTC/USDT"


def test_trade_journal_ai_updates_mobile_dashboard_summary():
    async def scenario():
        bus = AsyncEventBus(store=InMemoryEventStore(), enable_persistence=True)
        quant_repository = MemoryQuantRepository()
        trade_repository = MemoryTradeRepository()
        with tempfile.TemporaryDirectory() as temp_dir:
            dashboard = MobileDashboardService(bus, base_dir=temp_dir)
            TradeJournalAIEngine(
                bus,
                quant_repository=quant_repository,
                trade_repository=trade_repository,
                publish_summary_every=1,
                summary_window=10,
            )

            await bus.publish(
                EventType.TRADE_FEEDBACK,
                TradeFeedback(
                    symbol="ETH/USDT",
                    strategy_name="trend_following",
                    side="buy",
                    quantity=1.5,
                    entry_price=2000.0,
                    exit_price=2055.0,
                    pnl=55.0,
                    success=True,
                    model_probability=0.81,
                    features={
                        "rsi": 58.0,
                        "ema_gap": 0.02,
                        "volatility": 0.009,
                        "order_book_imbalance": 0.22,
                    },
                    metadata={
                        "market_session": "overlap",
                        "high_liquidity_session": True,
                        "exit_order_id": "order-win-1",
                    },
                ),
                priority=91,
            )
            await _drain(bus)
            return dashboard.read_snapshot()

    snapshot = asyncio.run(scenario())

    assert snapshot["latest_trade_journal_summary"]["trades_analyzed"] == 1
    assert "Best edges" in snapshot["latest_trade_journal_summary"]["summary"]
    assert snapshot["latest_trade_journal_summary"]["wins"] == 1
