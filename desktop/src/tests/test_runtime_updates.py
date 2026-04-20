import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.components.panels.runtime_updates import (
    load_initial_terminal_data,
    load_persisted_runtime_data,
    refresh_assets_async,
    refresh_open_orders_async,
    refresh_order_history_async,
    refresh_positions_async,
    refresh_trade_history_async,
    schedule_assets_refresh,
    schedule_open_orders_refresh,
    schedule_order_history_refresh,
    schedule_positions_refresh,
    schedule_trade_history_refresh,
)


def test_refresh_positions_async_uses_broker_then_updates_views():
    events = {"positions": None, "analysis": 0}

    async def fetch_positions():
        return [{"symbol": "EUR/USD", "amount": 1.0}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(broker=SimpleNamespace(fetch_positions=fetch_positions)),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _portfolio_positions_snapshot=lambda: [],
        _populate_positions_table=lambda positions: events.__setitem__("positions", positions),
        _refresh_position_analysis_window=lambda: events.__setitem__("analysis", events["analysis"] + 1),
    )

    asyncio.run(refresh_positions_async(fake))

    assert fake._latest_positions_snapshot == [{"symbol": "EUR/USD", "amount": 1.0}]
    assert events["positions"] == [{"symbol": "EUR/USD", "amount": 1.0}]
    assert events["analysis"] == 1


def test_refresh_positions_async_queues_pending_user_trade_reviews():
    events = {"queued": None}

    async def fetch_positions():
        return [{"symbol": "EUR/USD", "amount": 1.0, "position_side": "long"}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(
            broker=SimpleNamespace(fetch_positions=fetch_positions),
            queue_pending_user_trade_position_reviews=lambda positions: events.__setitem__("queued", list(positions)),
        ),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _portfolio_positions_snapshot=lambda: [],
        _populate_positions_table=lambda positions: None,
        _refresh_position_analysis_window=lambda: None,
    )

    asyncio.run(refresh_positions_async(fake))

    assert events["queued"] == [{"symbol": "EUR/USD", "amount": 1.0, "position_side": "long"}]


def test_refresh_open_orders_async_uses_snapshot_api_when_available():
    events = {"orders": None}

    async def fetch_open_orders_snapshot(symbols=None, limit=None):
        return [{"symbol": "BTC/USDT", "id": "ord-1"}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(
            broker=SimpleNamespace(
                fetch_open_orders=lambda **_kwargs: [],
                fetch_open_orders_snapshot=fetch_open_orders_snapshot,
            ),
            symbols=["BTC/USDT"],
        ),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _current_chart_symbol=lambda: "BTC/USDT",
        _populate_open_orders_table=lambda orders: events.__setitem__("orders", orders),
    )

    asyncio.run(refresh_open_orders_async(fake))

    assert fake._latest_open_orders_snapshot == [{"symbol": "BTC/USDT", "id": "ord-1"}]
    assert events["orders"] == [{"symbol": "BTC/USDT", "id": "ord-1"}]


def test_refresh_assets_async_fetches_balance_and_updates_controller_snapshot():
    events = {"balances": None}

    async def fetch_balance():
        return {"free": {"USD": 900.0}, "used": {"USD": 100.0}, "total": {"USD": 1000.0}}

    async def fetch_balances(_broker):
        return await fetch_balance()

    controller = SimpleNamespace(
        broker=SimpleNamespace(fetch_balance=fetch_balance),
        balances={},
        balance={},
        _fetch_balances=fetch_balances,
    )
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=controller,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _populate_assets_table=lambda balances: events.__setitem__("balances", dict(balances)),
    )

    asyncio.run(refresh_assets_async(fake))

    assert fake._latest_assets_snapshot["total"]["USD"] == 1000.0
    assert controller.balances["free"]["USD"] == 900.0
    assert events["balances"]["used"]["USD"] == 100.0


def test_refresh_order_history_async_prefers_broker_fetch_orders():
    events = {"orders": None}

    async def fetch_orders(limit=None):
        return [{"symbol": "BTC/USDT", "status": "filled", "id": "ord-1", "timestamp": "2026-04-12T12:00:00Z"}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(broker=SimpleNamespace(fetch_orders=fetch_orders)),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _populate_order_history_table=lambda orders: events.__setitem__("orders", list(orders)),
    )

    asyncio.run(refresh_order_history_async(fake))

    assert fake._latest_order_history_snapshot == [
        {"symbol": "BTC/USDT", "status": "filled", "id": "ord-1", "timestamp": "2026-04-12T12:00:00Z"}
    ]
    assert events["orders"][0]["id"] == "ord-1"


def test_refresh_trade_history_async_uses_controller_history_when_available():
    events = {"trades": None}

    async def fetch_trade_history(limit=None):
        return [{"symbol": "ETH/USDT", "order_id": "trade-1"}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(fetch_trade_history=fetch_trade_history),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _populate_trade_history_table=lambda trades: events.__setitem__("trades", list(trades)),
    )

    asyncio.run(refresh_trade_history_async(fake))

    assert fake._latest_trade_history_snapshot == [{"symbol": "ETH/USDT", "order_id": "trade-1"}]
    assert events["trades"] == [{"symbol": "ETH/USDT", "order_id": "trade-1"}]


def test_refresh_trade_history_async_falls_back_to_broker_trade_feed():
    events = {"trades": None}

    async def fetch_my_trades(limit=None):
        return [{"symbol": "SOL/USDT", "id": "trade-2", "side": "buy"}]

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(broker=SimpleNamespace(fetch_my_trades=fetch_my_trades)),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _populate_trade_history_table=lambda trades: events.__setitem__("trades", list(trades)),
    )

    asyncio.run(refresh_trade_history_async(fake))

    assert fake._latest_trade_history_snapshot == [{"symbol": "SOL/USDT", "id": "trade-2", "side": "buy"}]
    assert events["trades"] == [{"symbol": "SOL/USDT", "id": "trade-2", "side": "buy"}]


def test_load_persisted_runtime_data_replays_recent_trades():
    loaded = []

    async def load_recent_trades(limit=None):
        return [{"order_id": "ord-1"}, {"order_id": "ord-2"}]

    fake = SimpleNamespace(
        controller=SimpleNamespace(_load_recent_trades=load_recent_trades),
        MAX_LOG_ROWS=200,
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
        _update_trade_log=lambda trade: loaded.append(trade),
    )

    asyncio.run(load_persisted_runtime_data(fake))

    assert loaded == [{"order_id": "ord-1"}, {"order_id": "ord-2"}]


def test_load_persisted_runtime_data_yields_between_batches(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    loaded = []
    sleep_calls = []

    async def load_recent_trades(limit=None):
        return [{"order_id": f"ord-{index}"} for index in range(1, 6)]

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        controller=SimpleNamespace(_load_recent_trades=load_recent_trades),
        MAX_LOG_ROWS=200,
        STARTUP_TRADE_REPLAY_BATCH_SIZE=2,
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
        _update_trade_log=lambda trade: loaded.append(trade),
    )

    monkeypatch.setattr(runtime_mod.asyncio, "sleep", fake_sleep)

    asyncio.run(load_persisted_runtime_data(fake))

    assert len(loaded) == 5
    assert sleep_calls == [0, 0]


def test_load_initial_terminal_data_runs_account_bootstrap_and_hides_overlay():
    events = []

    async def _record(name):
        events.append(name)

    async def _load_recent_trades(limit=None):
        return []

    fake = SimpleNamespace(
        _ui_shutting_down=False,
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _set_workspace_loading_state=lambda title, detail=None, visible=True: events.append(
            ("overlay", visible, title, detail)
        ),
        _refresh_assets_async=lambda: _record("assets"),
        _refresh_positions_async=lambda: _record("positions"),
        _refresh_open_orders_async=lambda: _record("open_orders"),
        _refresh_order_history_async=lambda: _record("order_history"),
        _refresh_trade_history_async=lambda: _record("trade_history"),
        _load_active_chart_bootstrap_async=lambda: _record("chart"),
        controller=SimpleNamespace(_load_recent_trades=_load_recent_trades),
        MAX_LOG_ROWS=200,
        _update_trade_log=lambda trade: events.append(("trade", trade)),
        _refresh_terminal=lambda: events.append("refresh_terminal"),
    )

    asyncio.run(load_initial_terminal_data(fake))

    assert ("overlay", True, "Loading trading workspace...", "Syncing balances, positions, open orders, and recent account activity.") in events
    assert "assets" in events
    assert "positions" in events
    assert "open_orders" in events
    assert "order_history" in events
    assert "trade_history" in events
    assert "chart" in events
    assert "refresh_terminal" in events
    assert events[-1] == ("overlay", False, None, None)


def test_schedule_positions_refresh_throttles_coinbase(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _positions_refresh_task=None,
        _last_positions_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="coinbase")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_positions_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Coinbase positions refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_positions_refresh(fake)


def test_schedule_positions_refresh_throttles_alpaca(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _positions_refresh_task=None,
        _last_positions_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="alpaca")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_positions_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Alpaca positions refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_positions_refresh(fake)


def test_schedule_open_orders_refresh_throttles_coinbase(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _open_orders_refresh_task=None,
        _last_open_orders_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="coinbase")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_open_orders_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Coinbase open-orders refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_open_orders_refresh(fake)


def test_schedule_open_orders_refresh_throttles_alpaca(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _open_orders_refresh_task=None,
        _last_open_orders_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="alpaca")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_open_orders_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Alpaca open-orders refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_open_orders_refresh(fake)


def test_schedule_assets_refresh_throttles_recent_requests(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _assets_refresh_task=None,
        _last_assets_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="coinbase")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_assets_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Assets refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_assets_refresh(fake)


def test_schedule_order_history_refresh_throttles_recent_requests(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _order_history_refresh_task=None,
        _last_order_history_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="alpaca")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_order_history_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Order-history refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_order_history_refresh(fake)


def test_schedule_trade_history_refresh_throttles_recent_requests(monkeypatch):
    import ui.components.panels.runtime_updates as runtime_mod

    fake = SimpleNamespace(
        _trade_history_refresh_task=None,
        _last_trade_history_refresh_at=runtime_mod.time.monotonic(),
        controller=SimpleNamespace(broker=SimpleNamespace(exchange_name="coinbase")),
        logger=SimpleNamespace(debug=lambda *_args, **_kwargs: None),
        _refresh_trade_history_async=lambda: None,
    )

    def should_not_schedule():
        raise AssertionError("Trade-history refresh should be throttled")

    monkeypatch.setattr(runtime_mod.asyncio, "get_event_loop", should_not_schedule)

    schedule_trade_history_refresh(fake)
