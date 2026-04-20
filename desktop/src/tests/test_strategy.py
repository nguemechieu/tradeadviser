import asyncio
import time

from event_bus.event_bus import EventBus
from strategy.arbitrage_strategy import ArbitrageStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.momentum_strategy import MomentumStrategy


def test_momentum_strategy_emits_order_after_enough_ticks():
    async def scenario():
        bus = EventBus()
        strategy = MomentumStrategy(bus)

        for price in range(100, 120):
            event = type("Event", (), {"data": {"symbol": "BTC/USDT", "price": float(price)}})()
            await strategy.on_tick(event)

        order_event = await bus.queue.get()
        assert order_event.data["symbol"] == "BTC/USDT"
        assert order_event.data["side"] in {"BUY", "SELL"}

    asyncio.run(scenario())


def test_momentum_strategy_generate_signal_supports_backtest_usage_without_event_bus():
    strategy = MomentumStrategy(
        None,
        short_window=3,
        long_window=5,
        momentum_window=2,
        min_momentum=0.005,
    )

    candles = [
        [1, 100.0, 101.0, 99.0, 100.0, 10.0],
        [2, 100.2, 101.2, 100.0, 100.8, 10.0],
        [3, 100.8, 101.5, 100.5, 101.2, 10.0],
        [4, 101.3, 102.0, 101.0, 101.9, 10.0],
        [5, 101.8, 103.0, 101.7, 102.8, 10.0],
        [6, 102.7, 104.0, 102.6, 103.9, 10.0],
    ]

    signal = strategy.generate_signal(candles)

    assert signal is not None
    assert signal["side"] == "buy"
    assert signal["amount"] == 0.01
    assert "Momentum confirmed" in signal["reason"]


def test_mean_reversion_strategy_flags_stretched_move():
    strategy = MeanReversionStrategy(None, lookback=5, entry_zscore=1.25)

    candles = [
        [1, 100.0, 100.5, 99.5, 100.0, 10.0],
        [2, 100.0, 100.4, 99.8, 100.1, 10.0],
        [3, 100.1, 100.5, 99.9, 100.0, 10.0],
        [4, 100.0, 100.3, 99.7, 100.2, 10.0],
        [5, 100.2, 100.6, 100.0, 100.1, 10.0],
        [6, 100.1, 104.0, 100.0, 103.8, 10.0],
    ]

    signal = strategy.generate_signal(candles)

    assert signal is not None
    assert signal["side"] == "sell"
    assert "standard deviations above" in signal["reason"]


def test_arbitrage_strategy_emits_cross_exchange_signal_with_legs():
    async def scenario():
        bus = EventBus()
        strategy = ArbitrageStrategy(bus, min_spread=0.01, max_quote_age_seconds=60.0)
        now = time.time()

        first = type(
            "Event",
            (),
            {"data": {"symbol": "BTC/USDT", "exchange": "binance", "price": 100.0, "timestamp": now}},
        )()
        second = type(
            "Event",
            (),
            {"data": {"symbol": "BTC/USDT", "exchange": "coinbase", "price": 102.0, "timestamp": now}},
        )()

        await strategy.on_tick(first)
        await strategy.on_tick(second)

        order_event = await bus.queue.get()
        assert order_event.data["side"] == "BUY"
        assert order_event.data["buy_exchange"] == "binance"
        assert order_event.data["sell_exchange"] == "coinbase"
        assert len(order_event.data["legs"]) == 2
        assert order_event.data["spread_bps"] >= 100.0

    asyncio.run(scenario())
