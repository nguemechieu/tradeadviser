import asyncio
from datetime import datetime, timedelta, timezone
import logging
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.risk_engine import RiskEngine
from frontend.ui.app_controller import AppController
from market_data.candle_buffer import CandleBuffer
from market_data.orderbook_buffer import OrderBookBuffer


def _make_controller():
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.market_chat")
    controller.symbols = ["BTC/USDT", "ETH/USDT"]
    controller.time_frame = "1h"
    controller.terminal = None
    controller.broker = None

    async def fake_ticker(symbol):
        return {
            "symbol": symbol,
            "price": 105.0,
            "last": 105.0,
            "bid": 104.9,
            "ask": 105.1,
        }

    async def fake_ohlcv(symbol, timeframe="1h", limit=120):
        controller._last_requested_symbol = symbol
        controller._last_requested_timeframe = timeframe
        rows = []
        for index in range(60):
            close = 100.0 + index
            rows.append([index, close - 1.0, close + 1.0, close - 2.0, close, 10.0 + index])
        return rows

    controller._safe_fetch_ticker = fake_ticker
    controller._safe_fetch_ohlcv = fake_ohlcv
    controller.get_market_stream_status = lambda: "Running"
    controller._last_requested_symbol = None
    controller._last_requested_timeframe = None
    return controller


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _prime_trade_safety_buffers(controller, symbol, *, timestamp=None, include_orderbook=False):
    ts = timestamp or _utc_now_iso()
    controller.candle_buffers = {}
    controller.candle_buffer = CandleBuffer()
    controller.candle_buffer.update(
        symbol,
        {
            "timestamp": ts,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10.0,
        },
    )
    controller.orderbook_buffer = OrderBookBuffer()
    if include_orderbook:
        controller.orderbook_buffer.update(
            symbol,
            bids=[[99.5, 1.0]],
            asks=[[100.5, 1.0]],
            updated_at=ts,
        )
    return ts


def _configure_trade_preflight_controller(
    controller,
    *,
    exchange_name,
    mode,
    preference,
    markets,
    balances,
    supports_orderbook=False,
):
    async def fake_create_order(**kwargs):
        return {"status": "submitted", "id": "cert-order-001", **kwargs}

    async def fake_fetch_balance():
        return balances

    broker = SimpleNamespace(
        exchange_name=exchange_name,
        connected=(mode == "live"),
        exchange=SimpleNamespace(markets=markets),
        create_order=fake_create_order,
        fetch_balance=fake_fetch_balance,
        supported_market_venues=lambda: {
            "coinbase": ["auto", "spot", "derivative"],
            "oanda": ["auto", "otc"],
            "alpaca": ["auto", "spot"],
            "stellar": ["auto", "spot"],
            "paper": ["auto", "spot", "derivative", "option", "otc"],
        }.get(exchange_name, ["auto", "spot"]),
    )
    if supports_orderbook:
        async def fake_fetch_orderbook(symbol, limit=None):
            return {"symbol": symbol, "bids": [[99.5, 1.0]], "asks": [[100.5, 1.0]]}

        broker.fetch_orderbook = fake_fetch_orderbook

    controller.broker = broker
    controller.is_live_mode = lambda: mode == "live"
    controller.current_account_label = lambda: "Primary"
    controller.market_trade_preference = preference
    controller.balances = dict(balances)
    controller.balance = dict(balances)
    controller.normalize_trade_quantity = lambda symbol, amount, quantity_mode=None: {
        "symbol": symbol,
        "requested_mode": "units",
        "requested_amount": float(amount),
        "requested_amount_units": float(amount),
        "amount_units": float(amount),
    }
    controller._display_trade_amount = lambda amount_units, quantity: float(amount_units)
    return broker


def test_handle_market_chat_action_returns_native_snapshot_for_symbol_request():
    controller = _make_controller()

    reply = asyncio.run(controller.handle_market_chat_action("BTC/USDT"))

    assert "BTC/USDT snapshot (1h)" in reply
    assert "Trend:" in reply
    assert "RSI14:" in reply
    assert "What do you want me to do" not in reply


def test_handle_market_chat_action_uses_requested_timeframe_for_market_snapshot():
    controller = _make_controller()

    reply = asyncio.run(controller.handle_market_chat_action("price btc/usdt 4h"))

    assert "BTC/USDT snapshot (4h)" in reply
    assert controller._last_requested_timeframe == "4h"


def test_handle_market_chat_action_supports_broker_market_symbols_not_in_loaded_list():
    controller = _make_controller()
    controller.broker = SimpleNamespace(
        symbols=["AAPL", "EUR/JPY"],
        exchange=SimpleNamespace(markets={"AAPL": {}, "EUR/JPY": {}, "XAU-USD": {}}),
    )

    reply = asyncio.run(controller.handle_market_chat_action("price eur/jpy"))

    assert "EUR/JPY snapshot (1h)" in reply
    assert controller._last_requested_symbol == "EUR/JPY"


def test_handle_market_chat_action_supports_single_ticker_symbols():
    controller = _make_controller()
    controller.broker = SimpleNamespace(
        symbols=["AAPL"],
        exchange=SimpleNamespace(markets={"AAPL": {}}),
    )

    reply = asyncio.run(controller.handle_market_chat_action("analyze aapl"))

    assert "AAPL snapshot (1h)" in reply
    assert controller._last_requested_symbol == "AAPL"


def test_handle_market_chat_action_can_start_ai_trading_from_pilot():
    controller = _make_controller()
    terminal = SimpleNamespace(
        autotrading_enabled=False,
        autotrade_scope_value="selected",
    )

    def set_autotrading_enabled(enabled):
        terminal.autotrading_enabled = bool(enabled)

    terminal._set_autotrading_enabled = set_autotrading_enabled
    terminal._autotrade_scope_label = lambda: "Selected Symbol"

    controller.terminal = terminal
    controller.trading_system = object()
    controller.get_active_autotrade_symbols = lambda: ["BTC/USDT"]
    controller.is_emergency_stop_active = lambda: False

    reply = asyncio.run(controller.handle_market_chat_action("start ai trading"))

    assert reply == "AI trading is ON. Scope: Selected Symbol."
    assert terminal.autotrading_enabled is True


def test_handle_market_chat_action_can_stop_ai_trading_from_pilot():
    controller = _make_controller()
    terminal = SimpleNamespace(
        autotrading_enabled=True,
        autotrade_scope_value="all",
    )

    def set_autotrading_enabled(enabled):
        terminal.autotrading_enabled = bool(enabled)

    terminal._set_autotrading_enabled = set_autotrading_enabled
    terminal._autotrade_scope_label = lambda: "All Symbols"

    controller.terminal = terminal

    reply = asyncio.run(controller.handle_market_chat_action("stop ai trading"))

    assert reply == "AI trading is OFF."
    assert terminal.autotrading_enabled is False


def test_handle_market_chat_action_reports_why_ai_trading_cannot_start():
    controller = _make_controller()
    terminal = SimpleNamespace(
        autotrading_enabled=False,
        autotrade_scope_value="watchlist",
    )

    def set_autotrading_enabled(enabled):
        terminal.autotrading_enabled = bool(enabled)

    terminal._set_autotrading_enabled = set_autotrading_enabled
    terminal._autotrade_scope_label = lambda: "Watchlist"

    controller.terminal = terminal
    controller.trading_system = object()
    controller.get_active_autotrade_symbols = lambda: []
    controller.is_emergency_stop_active = lambda: False

    reply = asyncio.run(controller.handle_market_chat_action("start ai trading"))

    assert reply == "AI trading cannot start because the watchlist scope has no checked symbols."
    assert terminal.autotrading_enabled is False


def test_telegram_positions_text_uses_normalized_active_positions_snapshot():
    controller = _make_controller()
    controller.terminal = SimpleNamespace(
        _active_positions_snapshot=lambda: [
            {"symbol": "EUR/USD", "side": "long", "amount": 1250.0, "pnl": 12.5}
        ],
        _latest_positions_snapshot=[
            {"symbol": "raw-should-not-appear", "side": "short", "amount": 1.0, "pnl": -1.0}
        ],
    )

    reply = asyncio.run(controller.telegram_positions_text())

    assert "EUR/USD" in reply
    assert "long" in reply
    assert "1250.0" in reply
    assert "raw-should-not-appear" not in reply


def test_telegram_open_orders_text_uses_normalized_active_open_orders_snapshot():
    controller = _make_controller()
    controller.terminal = SimpleNamespace(
        _active_open_orders_snapshot=lambda: [
            {"symbol": "BTC/USDT", "side": "buy", "status": "open", "amount": 0.5, "price": 65000.0}
        ],
        _latest_open_orders_snapshot=[
            {"symbol": "raw-should-not-appear", "side": "sell", "status": "open", "amount": 1.0, "price": 1.0}
        ],
    )

    reply = asyncio.run(controller.telegram_open_orders_text())

    assert "BTC/USDT" in reply
    assert "buy" in reply
    assert "65000.0" in reply
    assert "raw-should-not-appear" not in reply


def test_handle_market_chat_action_can_open_trade_from_pilot():
    controller = _make_controller()
    submitted = {}

    async def fake_submit_market_chat_trade(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "order_id": "pilot-001"}

    controller.submit_market_chat_trade = fake_submit_market_chat_trade

    reply = asyncio.run(
        controller.handle_market_chat_action(
            "trade buy eur/usd amount 1000 type limit price 1.25 sl 1.2 tp 1.3 confirm"
        )
    )

    assert submitted == {
        "symbol": "EUR/USD",
        "side": "buy",
        "amount": 1000.0,
        "order_type": "limit",
        "price": 1.25,
        "stop_price": None,
        "stop_loss": 1.2,
        "take_profit": 1.3,
    }
    assert "Trade command executed." in reply
    assert "Status: FILLED" in reply
    assert "Order ID: pilot-001" in reply


def test_handle_market_chat_action_can_open_stop_limit_trade_from_pilot():
    controller = _make_controller()
    submitted = {}

    async def fake_submit_market_chat_trade(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "order_id": "pilot-stop-limit-001"}

    controller.submit_market_chat_trade = fake_submit_market_chat_trade

    reply = asyncio.run(
        controller.handle_market_chat_action(
            "trade sell eur/usd amount 1000 type stop_limit price 1.25 trigger 1.255 sl 1.26 tp 1.2 confirm"
        )
    )

    assert submitted == {
        "symbol": "EUR/USD",
        "side": "sell",
        "amount": 1000.0,
        "order_type": "stop_limit",
        "price": 1.25,
        "stop_price": 1.255,
        "stop_loss": 1.26,
        "take_profit": 1.2,
    }
    assert "Trade command executed." in reply
    assert "Type: STOP_LIMIT" in reply
    assert "Order ID: pilot-stop-limit-001" in reply


def test_submit_market_chat_trade_converts_oanda_micro_lots_to_units():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "oanda-001"}

    controller.broker = SimpleNamespace(exchange_name="oanda", create_order=fake_create_order)

    order = asyncio.run(
        controller.submit_market_chat_trade(
            symbol="EUR/USD",
            side="buy",
            amount=0.01,
            quantity_mode="lots",
        )
    )

    assert submitted["amount"] == 1000.0
    assert order["requested_amount"] == 0.01
    assert order["requested_quantity_mode"] == "lots"
    assert order["amount_units"] == 1000.0


def test_submit_market_chat_trade_passes_stop_limit_trigger_to_broker():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "stop-limit-001"}

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)

    order = asyncio.run(
        controller.submit_market_chat_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=1.5,
            order_type="stop_limit",
            price=64990.0,
            stop_price=65010.0,
        )
    )

    assert submitted["type"] == "stop_limit"
    assert submitted["price"] == 64990.0
    assert submitted["stop_price"] == 65010.0
    assert order["amount_units"] == 1.5


def test_submit_market_chat_trade_caps_buy_size_to_available_quote_balance():
    controller = _make_controller()
    submitted = {}

    async def fake_fetch_balance():
        return {"free": {"USDT": 100.0}}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "spot-cap-001", "amount": kwargs["amount"]}

    controller.broker = SimpleNamespace(
        exchange_name="paper",
        create_order=fake_create_order,
        fetch_balance=fake_fetch_balance,
    )

    order = asyncio.run(
        controller.submit_market_chat_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=2.0,
        )
    )

    expected_amount = 100.0 * controller.ORDER_SIZE_BUFFER / 105.1
    assert abs(submitted["amount"] - expected_amount) < 1e-9
    assert order["size_adjusted"] is True
    assert abs(float(order["amount_units"]) - expected_amount) < 1e-9


def test_submit_market_chat_trade_applies_smaller_openai_size_recommendation():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "ai-size-001", "amount": kwargs["amount"]}

    async def fake_recommend_trade_size_with_openai(**_kwargs):
        return {"recommended_units": 0.4, "reason": "Reduce size for this symbol volatility."}

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)
    controller._recommend_trade_size_with_openai = fake_recommend_trade_size_with_openai

    order = asyncio.run(
        controller.submit_market_chat_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
        )
    )

    assert submitted["amount"] == 0.4
    assert order["ai_adjusted"] is True
    assert order["size_adjusted"] is True
    assert order["applied_requested_mode_amount"] == 0.4


def test_submit_trade_with_preflight_skips_openai_sizing_for_manual_orders():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "manual-no-ai-001", "amount": kwargs["amount"]}

    async def fail_openai_sizing(**_kwargs):
        raise AssertionError("manual orders should not call OpenAI sizing")

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)
    controller.openai_api_key = "test-key"
    controller._recommend_trade_size_with_openai = fail_openai_sizing

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            source="manual",
        )
    )

    assert submitted["amount"] == 1.0
    assert order["ai_adjusted"] is False


def test_submit_trade_with_preflight_marks_bad_manual_trade_for_pending_review():
    controller = _make_controller()
    controller.user_trade_autocorrect_enabled = True
    controller._pending_user_trade_reviews = {}

    async def fake_create_order(**kwargs):
        return {
            "status": "submitted",
            "id": "manual-review-001",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "type": kwargs["type"],
            "amount": kwargs["amount"],
        }

    async def fake_assess_user_trade_review(**_kwargs):
        return {
            "is_bad": True,
            "action": "correct",
            "summary": "Stop loss was missing, so the trade had no defined downside protection.",
            "reasons": ["Stop loss was missing, so the trade had no defined downside protection."],
            "replacement_side": "buy",
            "replacement_amount_units": 1.0,
            "replacement_stop_loss": 95.0,
            "replacement_take_profit": 107.5,
            "market_context": {},
            "reward_risk": 1.5,
        }

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)
    controller._assess_user_trade_review = fake_assess_user_trade_review
    controller._record_trade_audit = lambda *args, **kwargs: asyncio.sleep(0)
    controller._notify_user_trade_review = lambda *args, **kwargs: None

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            source="manual",
        )
    )

    assert order["review_action"] == "correct"
    assert order["intervention_pending"] is True
    assert order["intervention_taken"] is False
    assert controller._pending_user_trade_reviews


def test_submit_trade_with_preflight_cancels_open_manual_order_and_replaces_it():
    controller = _make_controller()
    controller.user_trade_autocorrect_enabled = True
    controller._pending_user_trade_reviews = {}
    create_calls = []
    cancel_calls = []

    async def fake_create_order(**kwargs):
        create_calls.append(dict(kwargs))
        if len(create_calls) == 1:
            return {
                "status": "open",
                "id": "manual-bad-001",
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "type": kwargs["type"],
                "price": kwargs.get("price"),
                "amount": kwargs["amount"],
            }
        return {
            "status": "submitted",
            "id": "manual-good-001",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "type": kwargs["type"],
            "price": kwargs.get("price"),
            "amount": kwargs["amount"],
        }

    async def fake_cancel_order(order_id, symbol=None):
        cancel_calls.append((order_id, symbol))
        return {"id": order_id, "symbol": symbol, "status": "canceled"}

    async def fake_assess_user_trade_review(**_kwargs):
        return {
            "is_bad": True,
            "action": "correct",
            "summary": "Take profit was missing, so the trade had no defined exit target.",
            "reasons": ["Take profit was missing, so the trade had no defined exit target."],
            "replacement_side": "buy",
            "replacement_amount_units": 1.0,
            "replacement_stop_loss": 95.0,
            "replacement_take_profit": 108.0,
            "market_context": {},
            "reward_risk": 1.5,
        }

    controller.broker = SimpleNamespace(
        exchange_name="paper",
        create_order=fake_create_order,
        cancel_order=fake_cancel_order,
    )
    controller._assess_user_trade_review = fake_assess_user_trade_review
    controller._record_trade_audit = lambda *args, **kwargs: asyncio.sleep(0)
    controller._notify_user_trade_review = lambda *args, **kwargs: None

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            order_type="limit",
            price=100.0,
            source="manual",
        )
    )

    assert cancel_calls == [("manual-bad-001", "BTC/USDT")]
    assert len(create_calls) == 2
    assert order["id"] == "manual-good-001"
    assert order["intervention_taken"] is True
    assert order["review_replaced_order_id"] == "manual-bad-001"


def test_submit_trade_with_preflight_warns_and_monitors_oversized_manual_trade():
    controller = _make_controller()
    controller.user_trade_autocorrect_enabled = True
    controller.user_trade_risk_monitor_enabled = True
    controller._pending_user_trade_reviews = {}
    controller._monitored_user_trade_positions = {}

    async def fake_create_order(**kwargs):
        return {
            "status": "submitted",
            "id": "manual-risk-watch-001",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "type": kwargs["type"],
            "amount": kwargs["amount"],
        }

    async def fake_assess_user_trade_review(**_kwargs):
        return {
            "is_bad": False,
            "monitor_only": True,
            "action": "warn",
            "summary": "Risk controls require a smaller position size.",
            "reasons": ["Risk controls require a smaller position size."],
            "structural_reasons": [],
            "monitor_reasons": ["Risk controls require a smaller position size."],
            "replacement_side": "buy",
            "replacement_amount_units": 0.4,
            "replacement_stop_loss": 95.0,
            "replacement_take_profit": 110.0,
            "market_context": {"risk_distance": 5.0},
            "reward_risk": 2.0,
        }

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)
    controller._assess_user_trade_review = fake_assess_user_trade_review
    controller._record_trade_audit = lambda *args, **kwargs: asyncio.sleep(0)
    controller._notify_user_trade_review = lambda *args, **kwargs: None

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            source="manual",
        )
    )

    assert order["review_action"] == "warn"
    assert order["risk_monitoring_active"] is True
    assert order["intervention_taken"] is False
    assert order["intervention_pending"] is False
    assert controller._monitored_user_trade_positions


def test_process_monitored_user_trade_positions_reduces_oversized_position_after_adverse_move():
    controller = _make_controller()
    controller.user_trade_risk_monitor_enabled = True
    controller.user_trade_risk_monitor_grace_seconds = 15.0
    controller._monitored_user_trade_positions = {
        "manual-risk-watch-001": {
            "created_at": time.time() - 120.0,
            "symbol": "BTC/USDT",
            "position_side": "long",
            "original_order_id": "manual-risk-watch-001",
            "original_side": "buy",
            "current_amount_units": 2.0,
            "recommended_amount_units": 1.0,
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "risk_distance": 5.0,
            "adverse_threshold": 1.5,
            "summary": "Risk controls require a smaller position size.",
            "reasons": ["Risk controls require a smaller position size."],
            "market_context": {"trend": "mixed"},
            "timeframe": "1h",
            "warnings_sent": 1,
            "last_warning_at": time.time() - 30.0,
            "ai_recommendation": "",
            "ai_reason": "",
            "ai_consulted": False,
            "last_price": 100.0,
        }
    }
    captured = {}
    notifications = []

    async def fake_close_position(symbol, amount=None, order_type="market", position=None, position_side=None, position_id=None):
        captured["symbol"] = symbol
        captured["amount"] = amount
        captured["order_type"] = order_type
        captured["position_side"] = position_side
        captured["position_id"] = position_id
        return {"id": "risk-trim-001", "status": "submitted", "symbol": symbol, "amount": amount}

    async def fake_openai_risk_note(**_kwargs):
        return {
            "recommendation": "trim",
            "reason": "Momentum is moving against the long while the position is still larger than the recommended size.",
        }

    controller.broker = SimpleNamespace(exchange_name="paper", close_position=fake_close_position)
    controller._recommend_user_trade_monitor_action_with_openai = fake_openai_risk_note
    controller._record_trade_audit = lambda *args, **kwargs: asyncio.sleep(0)
    controller._notify_user_trade_review = lambda title, message, level="WARN": notifications.append((title, message, level))

    asyncio.run(
        controller._process_monitored_user_trade_positions(
            [
                {
                    "symbol": "BTC/USDT",
                    "position_id": "BTC/USDT:long",
                    "position_side": "long",
                    "side": "long",
                    "amount": 2.0,
                    "entry_price": 100.0,
                    "mark_price": 98.0,
                    "pnl": -4.0,
                }
            ]
        )
    )

    assert captured["symbol"] == "BTC/USDT"
    assert abs(float(captured["amount"]) - 1.0) < 1e-9
    assert captured["position_side"] == "long"
    assert controller._monitored_user_trade_positions == {}
    assert notifications
    assert notifications[-1][0] == "User Trade Risk Controlled"
    assert "ChatGPT risk note" in notifications[-1][1]


def test_submit_trade_with_preflight_resolves_coinbase_derivative_contract_symbol():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "coinbase-derivative-001", **kwargs}

    markets = {
        "SLP/USD": {
            "symbol": "SLP/USD",
            "base": "SLP",
            "quote": "USD",
            "spot": True,
            "active": True,
        },
        "SLP-20DEC30-CDE": {
            "symbol": "SLP-20DEC30-CDE",
            "base": "SLP",
            "quote": "USD",
            "settle": "USD",
            "contract": True,
            "future": True,
            "native_symbol": "SLP-20DEC30-CDE",
            "underlying_symbol": "SLP/USD",
            "active": True,
        },
    }
    controller.market_trade_preference = "derivative"
    controller.broker = SimpleNamespace(
        exchange_name="coinbase",
        market_preference="derivative",
        resolved_market_preference="derivative",
        symbols=["SLP-20DEC30-CDE"],
        exchange=SimpleNamespace(markets=markets),
        create_order=fake_create_order,
        supported_market_venues=lambda: ["auto", "spot", "derivative"],
    )

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="SLP/USD",
            side="buy",
            amount=1.0,
            source="manual",
        )
    )

    assert submitted["symbol"] == "SLP-20DEC30-CDE"
    assert order["symbol"] == "SLP-20DEC30-CDE"
    assert order["requested_symbol"] == "SLP/USD"


@pytest.mark.parametrize(
    ("exchange_name", "mode", "preference", "request_symbol", "expected_symbol", "expected_venue", "markets", "balances"),
    [
        (
            "paper",
            "paper",
            "spot",
            "BTC/USDT",
            "BTC/USDT",
            "spot",
            {"BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True, "active": True}},
            {"free": {"USDT": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "paper",
            "paper",
            "derivative",
            "BTC/USD:USD",
            "BTC/USD:USD",
            "derivative",
            {"BTC/USD:USD": {"symbol": "BTC/USD:USD", "base": "BTC", "quote": "USD", "settle": "USD", "contract": True, "future": True, "active": True}},
            {"free": {"USD": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "coinbase",
            "live",
            "spot",
            "BTC/USD",
            "BTC/USD",
            "spot",
            {
                "BTC/USD": {"symbol": "BTC/USD", "base": "BTC", "quote": "USD", "spot": True, "active": True},
                "BTC/USD:USD": {"symbol": "BTC/USD:USD", "base": "BTC", "quote": "USD", "settle": "USD", "contract": True, "future": True, "active": True},
            },
            {"free": {"USD": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "coinbase",
            "live",
            "derivative",
            "BTC/USD",
            "BTC/USD:USD",
            "derivative",
            {
                "BTC/USD": {"symbol": "BTC/USD", "base": "BTC", "quote": "USD", "spot": True, "active": True},
                "BTC/USD:USD": {"symbol": "BTC/USD:USD", "base": "BTC", "quote": "USD", "settle": "USD", "contract": True, "future": True, "active": True},
            },
            {"free": {"USD": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "oanda",
            "live",
            "otc",
            "EUR/USD",
            "EUR/USD",
            "otc",
            {"EUR/USD": {"symbol": "EUR/USD", "base": "EUR", "quote": "USD", "otc": True, "active": True}},
            {"free": {"USD": 100000.0, "EUR": 50000.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "alpaca",
            "live",
            "spot",
            "AAPL",
            "AAPL",
            "spot",
            {"AAPL": {"symbol": "AAPL", "base": "AAPL", "quote": "USD", "spot": True, "active": True}},
            {"free": {"USD": 100000.0, "AAPL": 50.0}, "cash": 100000.0, "equity": 100000.0},
        ),
        (
            "stellar",
            "live",
            "spot",
            "BTC/XLM",
            "BTC/XLM",
            "spot",
            {"BTC/XLM": {"symbol": "BTC/XLM", "base": "BTC", "quote": "XLM", "spot": True, "active": True}},
            {"free": {"XLM": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        ),
    ],
)
def test_broker_certification_matrix_smoke_preflight(
    exchange_name,
    mode,
    preference,
    request_symbol,
    expected_symbol,
    expected_venue,
    markets,
    balances,
):
    controller = _make_controller()
    fresh_timestamp = _prime_trade_safety_buffers(controller, expected_symbol)
    _configure_trade_preflight_controller(
        controller,
        exchange_name=exchange_name,
        mode=mode,
        preference=preference,
        markets=markets,
        balances=balances,
    )

    async def fresh_ticker(symbol):
        return {
            "symbol": expected_symbol if preference == "derivative" else symbol,
            "price": 105.0,
            "last": 105.0,
            "bid": 104.9,
            "ask": 105.1,
            "timestamp": fresh_timestamp,
            "_received_at": fresh_timestamp,
        }

    controller._safe_fetch_ticker = fresh_ticker

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol=request_symbol,
            side="buy",
            amount=1.0,
            source="manual",
            timeframe="1h",
        )
    )

    assert preflight["symbol"] == expected_symbol
    assert preflight["resolved_venue"] == expected_venue
    assert preflight["eligibility_check"]["ok"] is True
    assert preflight["market_data_guard"]["blocked"] is False


def test_assess_trade_market_data_guard_refreshes_missing_orderbook_before_blocking():
    controller = _make_controller()
    fresh_timestamp = _prime_trade_safety_buffers(controller, "BTC/USDT", include_orderbook=False)
    _configure_trade_preflight_controller(
        controller,
        exchange_name="paper",
        mode="live",
        preference="spot",
        markets={"BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True, "active": True}},
        balances={"free": {"USDT": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
        supports_orderbook=True,
    )

    guard = asyncio.run(
        controller._assess_trade_market_data_guard(
            "BTC/USDT",
            timeframe="1h",
            ticker={
                "symbol": "BTC/USDT",
                "price": 105.0,
                "last": 105.0,
                "bid": 104.9,
                "ask": 105.1,
                "timestamp": fresh_timestamp,
                "_received_at": fresh_timestamp,
            },
        )
    )

    assert guard["blocked"] is False
    assert guard["orderbook"]["supported"] is True
    assert guard["orderbook"]["fresh"] is True


def test_assess_trade_market_data_guard_refreshes_missing_candles_before_blocking():
    controller = _make_controller()
    fresh_timestamp = _utc_now_iso()
    controller.candle_buffers = {}
    controller.candle_buffer = CandleBuffer()
    controller.orderbook_buffer = OrderBookBuffer()
    controller.orderbook_buffer.update(
        "EUR/CHF",
        bids=[[0.95, 1.0]],
        asks=[[0.96, 1.0]],
        updated_at=fresh_timestamp,
    )
    _configure_trade_preflight_controller(
        controller,
        exchange_name="oanda",
        mode="live",
        preference="otc",
        markets={"EUR/CHF": {"symbol": "EUR/CHF", "base": "EUR", "quote": "CHF", "otc": True, "active": True}},
        balances={"free_margin": 100000.0, "equity": 100000.0, "cash": 100000.0, "currency": "USD"},
    )

    calls = []

    async def fake_request_candle_data(symbol, timeframe="1h", limit=None, start_time=None, end_time=None, history_scope="runtime"):
        calls.append((symbol, timeframe, history_scope))
        controller.candle_buffer.update(
            symbol,
            {
                "timestamp": fresh_timestamp,
                "open": 0.95,
                "high": 0.97,
                "low": 0.94,
                "close": 0.96,
                "volume": 10.0,
            },
        )
        return True

    controller.request_candle_data = fake_request_candle_data

    guard = asyncio.run(
        controller._assess_trade_market_data_guard(
            "EUR/CHF",
            timeframe="1h",
            ticker={
                "symbol": "EUR/CHF",
                "price": 0.96,
                "last": 0.96,
                "bid": 0.9599,
                "ask": 0.9601,
                "timestamp": fresh_timestamp,
                "_received_at": fresh_timestamp,
            },
        )
    )

    assert calls == [("EUR/CHF", "1h", "runtime")]
    assert guard["blocked"] is False
    assert guard["candles"]["fresh"] is True


def test_preview_trade_submission_blocks_live_trade_when_quote_is_stale():
    controller = _make_controller()
    _prime_trade_safety_buffers(controller, "BTC/USDT")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="paper",
        mode="live",
        preference="spot",
        markets={"BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True, "active": True}},
        balances={"free": {"USDT": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
    )

    stale_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    async def stale_ticker(symbol):
        return {
            "symbol": symbol,
            "price": 105.0,
            "last": 105.0,
            "bid": 104.9,
            "ask": 105.1,
            "timestamp": stale_timestamp,
            "_received_at": stale_timestamp,
        }

    controller._safe_fetch_ticker = stale_ticker

    try:
        asyncio.run(
            controller.preview_trade_submission(
                symbol="BTC/USDT",
                side="buy",
                amount=1.0,
                source="manual",
                timeframe="1h",
            )
        )
    except RuntimeError as exc:
        assert "quote data" in str(exc).lower()
    else:
        raise AssertionError("Expected stale live quote data to block the trade")


def test_preview_trade_submission_refreshes_stale_quote_before_blocking():
    controller = _make_controller()
    _prime_trade_safety_buffers(controller, "AUD/CAD")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="oanda",
        mode="live",
        preference="otc",
        markets={"AUD/CAD": {"symbol": "AUD/CAD", "base": "AUD", "quote": "CAD", "otc": True, "active": True}},
        balances={"free_margin": 100000.0, "equity": 100000.0, "cash": 100000.0, "currency": "USD"},
    )
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    fresh_timestamp = datetime.now(timezone.utc).isoformat()
    calls = []

    async def rotating_ticker(symbol):
        calls.append(symbol)
        timestamp = stale_timestamp if len(calls) == 1 else fresh_timestamp
        return {
            "symbol": symbol,
            "price": 0.9050,
            "last": 0.9050,
            "bid": 0.9049,
            "ask": 0.9051,
            "timestamp": timestamp,
            "_received_at": timestamp,
        }

    controller._safe_fetch_ticker = rotating_ticker

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol="AUD/CAD",
            side="buy",
            amount=1000.0,
            order_type="market",
            source="manual",
            timeframe="1h",
        )
    )

    assert calls == ["AUD/CAD", "AUD/CAD"]
    assert preflight["market_data_guard"]["blocked"] is False
    assert preflight["market_data_guard"]["quote"]["fresh"] is True


def test_preview_trade_submission_fetches_fresh_quote_for_live_limit_order_without_cached_ticker():
    controller = _make_controller()
    _prime_trade_safety_buffers(controller, "GBP/SGD")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="oanda",
        mode="live",
        preference="otc",
        markets={"GBP/SGD": {"symbol": "GBP/SGD", "base": "GBP", "quote": "SGD", "otc": True, "active": True}},
        balances={"free_margin": 100000.0, "equity": 100000.0, "cash": 100000.0, "currency": "USD"},
    )
    fetched = []
    fresh_timestamp = datetime.now(timezone.utc).isoformat()

    async def fresh_ticker(symbol):
        fetched.append(symbol)
        return {
            "symbol": symbol,
            "price": 1.7060,
            "last": 1.7060,
            "bid": 1.7058,
            "ask": 1.7062,
            "timestamp": fresh_timestamp,
            "_received_at": fresh_timestamp,
        }

    controller._safe_fetch_ticker = fresh_ticker

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol="GBP/SGD",
            side="buy",
            amount=0.1,
            quantity_mode="lots",
            order_type="limit",
            price=1.7055,
            source="manual",
            timeframe="1h",
        )
    )

    assert fetched == ["GBP/SGD"]
    assert preflight["market_data_guard"]["blocked"] is False
    assert preflight["market_data_guard"]["quote"]["fresh"] is True


def test_preview_trade_submission_rejects_unsupported_market_venue():
    controller = _make_controller()
    _prime_trade_safety_buffers(controller, "BTC/USDT")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="alpaca",
        mode="live",
        preference="derivative",
        markets={"BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True, "active": True}},
        balances={"free": {"USDT": 100000.0, "BTC": 5.0}, "cash": 100000.0, "equity": 100000.0},
    )

    try:
        asyncio.run(
            controller.preview_trade_submission(
                symbol="BTC/USDT",
                side="buy",
                amount=1.0,
                source="manual",
                timeframe="1h",
            )
        )
    except RuntimeError as exc:
        assert "not supported by this broker profile" in str(exc).lower()
    else:
        raise AssertionError("Expected unsupported venue selection to fail preflight")


def test_preview_trade_submission_uses_alpaca_buying_power_for_stock_buys():
    controller = _make_controller()
    fresh_timestamp = _prime_trade_safety_buffers(controller, "AAPL")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="alpaca",
        mode="live",
        preference="spot",
        markets={"AAPL": {"symbol": "AAPL", "base": "AAPL", "quote": "USD", "spot": True, "active": True}},
        balances={
            "cash": 5000.0,
            "buying_power": 7000.0,
            "available_funds": 7000.0,
            "equity": 5200.0,
            "free": {"USD": 7000.0},
            "raw": {"cash": 5000.0, "buying_power": 7000.0, "equity": 5200.0},
        },
    )

    async def fresh_ticker(symbol):
        return {
            "symbol": symbol,
            "price": 105.0,
            "last": 105.0,
            "bid": 104.9,
            "ask": 105.1,
            "timestamp": fresh_timestamp,
            "_received_at": fresh_timestamp,
        }

    controller._safe_fetch_ticker = fresh_ticker

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol="AAPL",
            side="buy",
            amount=60.0,
            source="manual",
            timeframe="1h",
        )
    )

    assert preflight["symbol"] == "AAPL"
    assert preflight["amount_units"] == 60.0
    assert all("cash balance reduced" not in str(note).lower() for note in preflight.get("sizing_notes", []))


def test_submit_market_chat_trade_ignores_invalid_ai_risk_param_rejection():
    controller = _make_controller()
    submitted = {}

    async def fake_create_order(**kwargs):
        submitted.update(kwargs)
        return {"status": "submitted", "id": "ai-invalid-risk-001", "amount": kwargs["amount"]}

    async def fake_recommend_trade_size_with_openai(**_kwargs):
        return {
            "recommended_units": 0.0,
            "reason": "Invalid risk params: stop_loss is greater than current price for a buy order.",
        }

    controller.broker = SimpleNamespace(exchange_name="paper", create_order=fake_create_order)
    controller._recommend_trade_size_with_openai = fake_recommend_trade_size_with_openai

    order = asyncio.run(
        controller.submit_market_chat_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            stop_loss=999.0,
        )
    )

    assert submitted["amount"] == 1.0
    assert order["ai_adjusted"] is False


def test_submit_trade_with_preflight_surfaces_execution_manager_skip_reason():
    controller = _make_controller()

    async def fake_preflight_trade_submission(**_kwargs):
        return {
            "requested_amount": 1.0,
            "requested_mode": "units",
            "requested_amount_units": 1.0,
            "deterministic_amount_units": 1.0,
            "amount_units": 1.0,
            "applied_requested_mode_amount": 1.0,
            "size_adjusted": False,
            "ai_adjusted": False,
            "sizing_summary": "Preflight kept the requested size.",
            "sizing_notes": [],
            "ai_sizing_reason": "",
            "reference_price": 105.1,
            "closeout_guard": {},
        }

    class FakeExecutionManager:
        async def execute(self, **_kwargs):
            return None

        def last_skip_reason(self, _symbol):
            return "No available USDT balance to buy BTC/USDT."

    controller._preflight_trade_submission = fake_preflight_trade_submission
    controller.trading_system = SimpleNamespace(execution_manager=FakeExecutionManager())
    controller.broker = SimpleNamespace(exchange_name="paper")

    try:
        asyncio.run(
            controller.submit_trade_with_preflight(
                symbol="BTC/USDT",
                side="buy",
                amount=1.0,
                source="manual",
            )
        )
    except RuntimeError as exc:
        assert str(exc) == "No available USDT balance to buy BTC/USDT."
    else:
        raise AssertionError("Expected manual trade skip reason to be surfaced")


def test_submit_trade_with_preflight_retries_manual_order_with_smaller_balance_sized_amount():
    controller = _make_controller()
    audit_events = []

    async def fake_record_trade_audit(stage, **payload):
        audit_events.append((stage, payload))

    async def fake_preflight_trade_submission(**_kwargs):
        rows = getattr(fake_preflight_trade_submission, "_rows", None)
        return dict(rows.pop(0))

    fake_preflight_trade_submission._rows = [
        {
            "symbol": "EUR/PLN",
            "requested_symbol": "EUR/PLN",
            "requested_amount": 1.35,
            "requested_mode": "lots",
            "requested_amount_units": 135000.0,
            "amount_units": 135000.0,
            "deterministic_amount_units": 135000.0,
            "applied_requested_mode_amount": 1.35,
            "size_adjusted": False,
            "ai_adjusted": False,
            "sizing_summary": "Preflight kept the requested size.",
            "sizing_notes": [],
            "ai_sizing_reason": "",
            "reference_price": 4.29385,
            "closeout_guard": {},
            "market_data_guard": {"blocked": False},
            "eligibility_check": {"ok": True},
            "resolved_venue": "otc",
            "trade_timeframe": "1h",
        },
        {
            "symbol": "EUR/PLN",
            "requested_symbol": "EUR/PLN",
            "requested_amount": 1.35,
            "requested_mode": "lots",
            "requested_amount_units": 135000.0,
            "amount_units": 50000.0,
            "deterministic_amount_units": 50000.0,
            "applied_requested_mode_amount": 0.5,
            "size_adjusted": True,
            "ai_adjusted": False,
            "sizing_summary": "Preflight reduced the order to 0.5 lots using balance, margin, or risk limits.",
            "sizing_notes": ["Available account balance reduced the order size."],
            "ai_sizing_reason": "",
            "reference_price": 4.29385,
            "closeout_guard": {},
            "market_data_guard": {"blocked": False},
            "eligibility_check": {"ok": True},
            "resolved_venue": "otc",
            "trade_timeframe": "1h",
        },
    ]

    async def passthrough_review(order, **_kwargs):
        return order

    class FakeExecutionManager:
        def __init__(self):
            self.calls = []

        async def execute(self, **kwargs):
            self.calls.append(dict(kwargs))
            if len(self.calls) == 1:
                return {
                    "status": "rejected",
                    "reason": "400 Bad Request: Order rejected | INSUFFICIENT_MARGIN",
                    "symbol": kwargs["symbol"],
                    "side": kwargs["side"],
                    "type": kwargs["type"],
                    "amount": kwargs["amount"],
                }
            return {
                "status": "submitted",
                "id": "retry-001",
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "type": kwargs["type"],
                "amount": kwargs["amount"],
            }

    execution_manager = FakeExecutionManager()
    controller._record_trade_audit = fake_record_trade_audit
    controller._preflight_trade_submission = fake_preflight_trade_submission
    controller._handle_user_trade_review = passthrough_review
    controller.trading_system = SimpleNamespace(execution_manager=execution_manager)
    controller.broker = SimpleNamespace(exchange_name="oanda")

    order = asyncio.run(
        controller.submit_trade_with_preflight(
            symbol="EUR/PLN",
            side="sell",
            amount=1.35,
            quantity_mode="lots",
            source="manual",
            timeframe="1h",
        )
    )

    assert execution_manager.calls[0]["amount"] == 135000.0
    assert execution_manager.calls[1]["amount"] == 50000.0
    assert order["status"] == "submitted"
    assert order["retried_after_rejection"] is True
    assert order["requested_amount"] == 1.35
    assert order["applied_requested_mode_amount"] == 0.5
    assert "insufficient_margin" in order["initial_rejection_reason"].lower()
    assert any(stage == "submit_retry" for stage, _payload in audit_events)


def test_preview_trade_submission_caps_usdjpy_by_stop_risk():
    controller = _make_controller()
    controller.max_position_size_pct = 10000.0
    controller.max_risk_per_trade = 0.02
    controller.balances = {
        "free": {"USD": 10000.0},
        "total": {"USD": 10000.0},
        "equity": 10000.0,
        "currency": "USD",
    }
    controller.balance = dict(controller.balances)
    controller.market_trade_preference = "otc"
    controller.margin_closeout_snapshot = lambda _balances: {}
    controller._evaluate_trade_eligibility = lambda symbol: {
        "ok": True,
        "issues": [],
        "warnings": [],
        "resolved_venue": "otc",
        "supported_market_venues": ["auto", "otc"],
    }

    async def fake_market_data_guard(*_args, **_kwargs):
        return {
            "blocked": False,
            "quote": {"supported": True, "fresh": True},
            "candles": {"supported": True, "fresh": True},
            "orderbook": {"supported": False},
        }

    async def fake_fetch_balance():
        return dict(controller.balances)

    async def fake_instrument_meta(_symbol):
        return {"pipLocation": -2}

    controller._assess_trade_market_data_guard = fake_market_data_guard
    controller.normalize_trade_quantity = lambda symbol, amount, quantity_mode=None: {
        "symbol": symbol,
        "requested_mode": "units",
        "requested_amount": float(amount),
        "requested_amount_units": float(amount),
        "amount_units": float(amount),
    }
    controller._display_trade_amount = lambda amount_units, quantity: float(amount_units)
    controller.broker = SimpleNamespace(
        exchange_name="oanda",
        fetch_balance=fake_fetch_balance,
        _get_instrument_meta=fake_instrument_meta,
    )
    controller.trading_system = SimpleNamespace(
        risk_engine=RiskEngine(
            account_equity=10000,
            max_risk_per_trade=0.02,
            max_position_size_pct=10000.0,
        )
    )

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol="USD/JPY",
            side="buy",
            amount=100000.0,
            price=150.0,
            stop_loss=149.5,
            source="manual",
            timeframe="1h",
        )
    )

    assert preflight["amount_units"] == pytest.approx(60000.0)
    assert preflight["size_adjusted"] is True
    assert any("max risk" in note.lower() for note in preflight["sizing_notes"])


def test_preview_trade_submission_caps_oanda_manual_trade_by_available_balance_when_margin_missing():
    controller = _make_controller()
    _prime_trade_safety_buffers(controller, "EUR/PLN")
    _configure_trade_preflight_controller(
        controller,
        exchange_name="oanda",
        mode="live",
        preference="otc",
        markets={"EUR/PLN": {"symbol": "EUR/PLN", "base": "EUR", "quote": "PLN", "otc": True, "active": True}},
        balances={"free": {"PLN": 500.0}, "equity": 500.0, "currency": "PLN"},
    )
    controller.max_position_size_pct = 1000.0

    async def fixed_ticker(symbol):
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "symbol": symbol,
            "price": 4.29385,
            "last": 4.29385,
            "bid": 4.29375,
            "ask": 4.29395,
            "timestamp": timestamp,
            "_received_at": timestamp,
        }

    controller._safe_fetch_ticker = fixed_ticker

    preflight = asyncio.run(
        controller.preview_trade_submission(
            symbol="EUR/PLN",
            side="sell",
            amount=1000.0,
            source="manual",
            timeframe="1h",
        )
    )

    expected_cap = 500.0 * controller.ORDER_SIZE_BUFFER / 4.29385
    assert preflight["amount_units"] == pytest.approx(expected_cap)
    assert preflight["size_adjusted"] is True
    assert any("available account balance" in note.lower() for note in preflight["sizing_notes"])


def test_get_market_stream_status_recovers_oanda_polling_when_task_is_missing():
    controller = _make_controller()
    controller.get_market_stream_status = AppController.get_market_stream_status.__get__(controller, AppController)
    controller.connected = True
    controller.broker = SimpleNamespace(exchange_name="oanda")
    controller._ws_task = None
    controller._ticker_task = None
    controller._market_stream_recovery_task = None

    async def fake_start_ticker_polling():
        return None

    scheduled = []

    def fake_create_task(coro, name):
        scheduled.append(name)
        coro.close()
        return SimpleNamespace(done=lambda: False)

    controller._start_ticker_polling = fake_start_ticker_polling
    controller._create_task = fake_create_task

    async def run_check():
        return controller.get_market_stream_status()

    status = asyncio.run(run_check())

    assert status == "Restarting"
    assert scheduled == ["ticker_poll_recovery"]


def test_handle_trade_execution_logs_rejection_reason_to_console():
    controller = _make_controller()
    emitted = []
    console_rows = []
    controller.trade_signal = SimpleNamespace(emit=lambda trade: emitted.append(dict(trade)))
    controller.terminal = SimpleNamespace(
        system_console=SimpleNamespace(log=lambda message, level: console_rows.append((message, level)))
    )
    controller.telegram_service = None
    controller.performance_engine = None

    controller.handle_trade_execution(
        {
            "symbol": "EUR/PLN",
            "source": "bot",
            "status": "rejected",
            "reason": "Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old).",
        }
    )

    assert emitted[-1]["status"] == "rejected"
    assert console_rows[-1][1] == "ERROR"
    assert console_rows[-1][0] == (
        "Bot trade rejected for EUR/PLN: Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old)."
    )


def test_handle_trade_execution_dispatches_trade_close_notifications_with_entry_context():
    controller = _make_controller()
    emitted = []
    scheduled = []
    telegram_close_notifications = []
    email_close_notifications = []
    sms_close_notifications = []
    general_trade_notifications = []
    controller.trade_signal = SimpleNamespace(emit=lambda trade: emitted.append(dict(trade)))
    controller.terminal = None
    controller.performance_engine = None
    controller._performance_recorded_orders = set()
    controller.active_session_id = ""
    controller.trade_close_notifications_enabled = True
    controller.trade_close_notify_telegram = True
    controller.trade_close_notify_email = True
    controller.trade_close_notify_sms = True
    controller._trade_close_entry_cache = {}

    async def _record(container, trade):
        container.append(dict(trade))
        return True

    class _TelegramService:
        async def notify_trade(self, trade):
            general_trade_notifications.append(dict(trade))
            return True

        async def notify_trade_close(self, trade):
            return await _record(telegram_close_notifications, trade)

    class _EmailService:
        async def send_trade_close(self, trade):
            return await _record(email_close_notifications, trade)

    class _SmsService:
        async def send_trade_close(self, trade):
            return await _record(sms_close_notifications, trade)

    def fake_create_task(coro, name):
        scheduled.append(name)
        return asyncio.run(coro)

    controller.telegram_service = _TelegramService()
    controller.email_trade_notification_service = _EmailService()
    controller.sms_trade_notification_service = _SmsService()
    controller._create_task = fake_create_task

    controller.handle_trade_execution(
        {
            "symbol": "BTC/USDT",
            "status": "filled",
            "side": "buy",
            "price": 100.0,
            "size": 0.5,
            "strategy_name": "EMA Cross",
        }
    )
    controller.handle_trade_execution(
        {
            "symbol": "BTC/USDT",
            "status": "closed",
            "side": "sell",
            "price": 105.0,
            "size": 0.5,
            "pnl": 2.5,
            "strategy_name": "EMA Cross",
            "order_id": "close-1",
        }
    )

    assert emitted[-1]["status"] == "closed"
    assert "telegram_trade_notify" in scheduled
    assert scheduled[-3:] == [
        "telegram_trade_close_notify",
        "email_trade_close_notify",
        "sms_trade_close_notify",
    ]
    assert general_trade_notifications[0]["status"] == "filled"
    assert telegram_close_notifications[-1]["entry_price"] == 100.0
    assert telegram_close_notifications[-1]["exit_price"] == 105.0
    assert telegram_close_notifications[-1]["strategy_name"] == "EMA Cross"
    assert email_close_notifications[-1]["pnl"] == 2.5
    assert sms_close_notifications[-1]["order_id"] == "close-1"
    assert controller._trade_close_entry_cache == {}


def test_handle_market_chat_action_surfaces_chatgpt_size_note():
    controller = _make_controller()

    async def fake_submit_market_chat_trade(**_kwargs):
        return {
            "status": "submitted",
            "order_id": "ai-size-note-001",
            "requested_quantity_mode": "units",
            "requested_amount": 1.0,
            "applied_requested_mode_amount": 0.4,
            "size_adjusted": True,
            "sizing_summary": "Preflight reduced the order size.",
            "ai_sizing_reason": "Reduce size for this symbol volatility.",
        }

    controller.submit_market_chat_trade = fake_submit_market_chat_trade

    reply = asyncio.run(
        controller.handle_market_chat_action(
            "trade buy btc/usdt amount 1 confirm"
        )
    )

    assert "Amount: 0.4 units" in reply
    assert "Requested Amount: 1.0 units" in reply
    assert "ChatGPT Size Note: Reduce size for this symbol volatility." in reply


def test_submit_market_chat_trade_blocks_when_margin_closeout_guard_trips():
    controller = _make_controller()
    controller.margin_closeout_guard_enabled = True
    controller.max_margin_closeout_pct = 0.50

    async def fake_fetch_balance():
        return {
            "equity": 1000.0,
            "used": {"USD": 620.0},
            "raw": {"marginCloseoutPercent": "0.62", "NAV": "1000", "marginUsed": "620"},
        }

    async def fake_create_order(**_kwargs):
        raise AssertionError("create_order should not run when the closeout guard blocks the trade")

    controller.broker = SimpleNamespace(
        exchange_name="oanda",
        create_order=fake_create_order,
        fetch_balance=fake_fetch_balance,
    )

    try:
        asyncio.run(
            controller.submit_market_chat_trade(
                symbol="EUR/USD",
                side="buy",
                amount=1000.0,
            )
        )
    except RuntimeError as exc:
        assert "blocked" in str(exc).lower()
    else:
        raise AssertionError("Expected margin closeout guard to block the trade")


def test_handle_market_chat_action_can_open_trade_from_pilot_in_lots():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="oanda")
    submitted = {}

    async def fake_submit_market_chat_trade(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "order_id": "pilot-lot-001"}

    controller.submit_market_chat_trade = fake_submit_market_chat_trade

    reply = asyncio.run(
        controller.handle_market_chat_action(
            "trade buy eur/usd amount 0.01 lots confirm"
        )
    )

    assert submitted == {
        "symbol": "EUR/USD",
        "side": "buy",
        "amount": 0.01,
        "quantity_mode": "lots",
        "order_type": "market",
        "price": None,
        "stop_price": None,
        "stop_loss": None,
        "take_profit": None,
    }
    assert "Amount: 0.01 lots" in reply
    assert "Order ID: pilot-lot-001" in reply


def test_handle_market_chat_action_can_close_position_from_pilot():
    controller = _make_controller()
    closed = {}

    async def fake_close_market_chat_position(symbol, amount=None, quantity_mode=None):
        closed["symbol"] = symbol
        closed["amount"] = amount
        closed["quantity_mode"] = quantity_mode
        return {"status": "submitted", "order_id": "close-123"}

    controller.close_market_chat_position = fake_close_market_chat_position

    reply = asyncio.run(
        controller.handle_market_chat_action(
            "close position btc/usdt amount 0.5 confirm"
        )
    )

    assert closed == {"symbol": "BTC/USDT", "amount": 0.5, "quantity_mode": None}
    assert "Close-position command executed." in reply
    assert "Symbol: BTC/USDT" in reply
    assert "Amount: 0.5" in reply
    assert "Order ID: close-123" in reply


def test_close_market_chat_position_rejects_ambiguous_hedge_symbol_without_side():
    controller = _make_controller()
    controller.hedging_enabled = True
    controller.hedging_is_active = lambda broker=None: True
    controller.broker = SimpleNamespace()
    controller._market_chat_positions_snapshot = lambda: [
        {"symbol": "EUR/USD", "position_id": "EUR/USD:long", "position_side": "long", "amount": 1000.0, "side": "long"},
        {"symbol": "EUR/USD", "position_id": "EUR/USD:short", "position_side": "short", "amount": 1000.0, "side": "short"},
    ]

    try:
        asyncio.run(controller.close_market_chat_position("EUR/USD"))
    except RuntimeError as exc:
        assert "multiple hedge legs" in str(exc).lower()
    else:
        raise AssertionError("Expected ambiguous hedge close to raise RuntimeError")


def test_close_market_chat_position_treats_selected_position_amount_as_units():
    controller = _make_controller()
    captured = {}

    async def fake_close_position(symbol, amount=None, order_type="market", position=None, position_side=None, position_id=None):
        captured["symbol"] = symbol
        captured["amount"] = amount
        captured["position"] = position
        captured["position_side"] = position_side
        captured["position_id"] = position_id
        return {"status": "submitted", "id": "close-raw-units"}

    controller.broker = SimpleNamespace(exchange_name="oanda", close_position=fake_close_position)
    position = {
        "symbol": "USD_HUF",
        "position_id": "USD_HUF:long",
        "position_side": "long",
        "amount": 1250.0,
        "side": "long",
    }
    controller._market_chat_positions_snapshot = lambda: [position]

    result = asyncio.run(
        controller.close_market_chat_position(
            "USD_HUF",
            amount=1250.0,
            position=position,
        )
    )

    assert result["status"] == "submitted"
    assert captured["symbol"] == "USD_HUF"
    assert captured["amount"] == 1250.0
    assert captured["position_side"] == "long"
    assert captured["position_id"] == "usd_huf:long"


def test_close_market_chat_position_falls_back_for_legacy_brokers():
    controller = _make_controller()
    captured = {}

    async def legacy_close_position(symbol, amount=None):
        captured["symbol"] = symbol
        captured["amount"] = amount
        return {"status": "submitted", "id": "legacy-close-001"}

    controller.broker = SimpleNamespace(exchange_name="paper", close_position=legacy_close_position)
    position = {
        "symbol": "EUR/USD",
        "position_id": "EUR/USD:long",
        "position_side": "long",
        "amount": 1000.0,
        "side": "long",
    }
    controller._market_chat_positions_snapshot = lambda: [position]

    result = asyncio.run(
        controller.close_market_chat_position(
            "EUR/USD",
            amount=1000.0,
            position=position,
        )
    )

    assert result["status"] == "submitted"
    assert captured["symbol"] == "EUR/USD"
    assert captured["amount"] == 1000.0


def test_close_market_chat_position_does_not_retry_internal_type_errors():
    controller = _make_controller()
    calls = {"count": 0}

    async def fake_close_position(symbol, amount=None, order_type="market", position=None, position_side=None, position_id=None):
        calls["count"] += 1
        raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")

    controller.broker = SimpleNamespace(exchange_name="coinbase", close_position=fake_close_position)
    position = {
        "symbol": "BTC/USDT",
        "position_id": "BTC/USDT:long",
        "position_side": "long",
        "amount": 2.0,
        "side": "long",
    }
    controller._market_chat_positions_snapshot = lambda: [position]

    with pytest.raises(TypeError, match="unsupported operand type"):
        asyncio.run(
            controller.close_market_chat_position(
                "BTC/USDT",
                amount=2.0,
                position=position,
            )
        )

    assert calls["count"] == 1


def test_handle_market_chat_action_can_summarize_recent_bug_logs():
    controller = _make_controller()
    opened = []
    controller.terminal = SimpleNamespace(_open_logs=lambda: opened.append(True))

    with tempfile.TemporaryDirectory() as tmpdir:
        crash_path = Path(tmpdir) / "native_crash.log"
        crash_path.write_text(
            "\n".join(
                [
                    "Current thread 0x00002f8c (most recent call first):",
                    '  File "C:\\\\repo\\\\src\\\\frontend\\\\ui\\\\terminal.py", line 9199 in _update_ai_signal',
                    '  File "C:\\\\repo\\\\src\\\\frontend\\\\ui\\\\app_controller.py", line 4491 in publish_ai_signal',
                    "",
                    "=== Native crash trace session pid=27368 ===",
                ]
            ),
            encoding="utf-8",
        )
        app_log_path = Path(tmpdir) / "app.log"
        app_log_path.write_text(
            "INFO broker ready\n"
            "Error calling Python override of QObject::timerEvent()\n",
            encoding="utf-8",
        )

        controller._market_chat_log_file_paths = lambda: [crash_path, app_log_path]

        reply = asyncio.run(controller.handle_market_chat_action("show bug summary"))

    assert opened == [True]
    assert "Bug summary from local logs:" in reply
    assert "native_crash.log" in reply
    assert "terminal.py:9199 in _update_ai_signal" in reply
    assert "app.log" in reply


def test_margin_closeout_snapshot_uses_reported_or_derived_balance_metrics():
    controller = _make_controller()
    controller.margin_closeout_guard_enabled = True
    controller.max_margin_closeout_pct = 0.50
    controller.balances = {
        "equity": 1000.0,
        "used": {"USD": 400.0},
        "raw": {"marginCloseoutPercent": "0.62", "NAV": "1000", "marginUsed": "620"},
    }

    snapshot = controller.margin_closeout_snapshot()

    assert snapshot["available"] is True
    assert abs(float(snapshot["ratio"]) - 0.62) < 1e-9
    assert snapshot["blocked"] is True
    assert "blocked" in snapshot["reason"].lower()


def test_assign_ranked_strategies_to_symbol_persists_top_ranked_variants():
    stored = {}
    controller = AppController.__new__(AppController)
    controller.settings = SimpleNamespace(setValue=lambda key, value: stored.__setitem__(key, value))
    controller.multi_strategy_enabled = True
    controller.max_symbol_strategies = 3
    controller.symbol_strategy_assignments = {}
    controller.symbol_strategy_rankings = {}
    controller.time_frame = "1h"
    controller.trading_system = None

    assigned = controller.assign_ranked_strategies_to_symbol(
        "eur_usd",
        [
            {"strategy_name": "EMA Cross | London Session Aggressive", "score": 9.0, "total_profit": 120.0},
            {"strategy_name": "Trend Following | Scalp Conservative", "score": 6.0, "total_profit": 90.0},
            {"strategy_name": "MACD Trend", "score": 3.0, "total_profit": 40.0},
        ],
        top_n=2,
        timeframe="4h",
    )

    assert len(assigned) == 2
    assert assigned[0]["strategy_name"] == "EMA Cross | London Session Aggressive"
    assert assigned[1]["strategy_name"] == "Trend Following | Scalp Conservative"
    assert abs(sum(item["weight"] for item in assigned) - 1.0) < 1e-9
    assert "EUR/USD" in controller.symbol_strategy_assignments
    assert "strategy/symbol_assignments" in stored


def test_assign_strategy_to_symbol_persists_manual_symbol_override_and_can_clear_it():
    stored = {}
    controller = AppController.__new__(AppController)
    controller.settings = SimpleNamespace(setValue=lambda key, value: stored.__setitem__(key, value))
    controller.multi_strategy_enabled = False
    controller.max_symbol_strategies = 3
    controller.symbol_strategy_assignments = {}
    controller.symbol_strategy_rankings = {}
    controller.time_frame = "1h"
    controller.strategy_name = "Trend Following"
    controller.trading_system = None

    assigned = controller.assign_strategy_to_symbol(
        "eur_usd",
        "EMA Cross | London Session Aggressive",
        timeframe="4h",
    )

    assert controller.multi_strategy_enabled is True
    assert assigned == controller.assigned_strategies_for_symbol("EUR/USD")
    assert assigned[0]["strategy_name"] == "EMA Cross | London Session Aggressive"
    assert assigned[0]["assignment_mode"] == "single"
    assert assigned[0]["timeframe"] == "4h"

    removed = controller.clear_symbol_strategy_assignment("EUR/USD")

    assert removed[0]["strategy_name"] == "EMA Cross | London Session Aggressive"
    assert controller.assigned_strategies_for_symbol("EUR/USD")[0]["strategy_name"] == "Trend Following"
    assert "strategy/symbol_assignments" in stored
