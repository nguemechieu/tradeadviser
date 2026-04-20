import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.panels.manual_trade_updates import (
    default_entry_price_for_symbol,
    manual_trade_default_payload,
    manual_trade_format_context,
    populate_manual_trade_ticket,
    refresh_manual_trade_ticket,
    normalize_manual_trade_amount,
    normalize_manual_trade_price,
    normalize_manual_trade_quantity_mode,
    submit_manual_trade_from_ticket,
    submit_manual_trade_side,
    suggest_manual_trade_levels,
    validate_manual_trade_amount,
)
from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _safe_float(value, default=None):
    return Terminal._safe_float(SimpleNamespace(), value, default)


def _manual_trade_window():
    _app()
    window = SimpleNamespace(
        _manual_trade_symbol_picker=QComboBox(),
        _manual_trade_side_picker=QComboBox(),
        _manual_trade_type_picker=QComboBox(),
        _manual_trade_quantity_picker=QComboBox(),
        _manual_trade_amount_input=QDoubleSpinBox(),
        _manual_trade_price_label=QLabel("Entry Price"),
        _manual_trade_price_input=QLineEdit(),
        _manual_trade_stop_price_label=QLabel("Stop Trigger"),
        _manual_trade_stop_price_input=QLineEdit(),
        _manual_trade_stop_loss_input=QLineEdit(),
        _manual_trade_take_profit_input=QLineEdit(),
        _manual_trade_status=QLabel(),
        _manual_trade_submit_btn=QPushButton("Submit"),
        _manual_trade_buy_limit_btn=QPushButton("Buy Market"),
        _manual_trade_sell_limit_btn=QPushButton("Sell Market"),
        _manual_trade_hint=QLabel(),
        _manual_trade_source="manual",
        _manual_trade_last_quantity_symbol="",
    )
    window._manual_trade_side_picker.addItems(["buy", "sell"])
    window._manual_trade_type_picker.addItems(["market", "limit", "stop_limit"])
    window._manual_trade_quantity_picker.addItems(["Units", "Lots"])
    window._manual_trade_amount_input.setRange(0.0, 1_000_000_000.0)
    window._manual_trade_amount_input.setDecimals(8)
    return window


def test_manual_trade_default_payload_uses_chart_symbol_and_lot_defaults():
    fake = SimpleNamespace(
        controller=SimpleNamespace(symbols=["BTC/USDT"]),
        symbol="ETH/USDT",
        current_timeframe="4h",
        _current_chart_symbol=lambda: "EUR/USD",
        _safe_float=_safe_float,
    )
    fake._manual_trade_quantity_context = lambda symbol: {
        "symbol": symbol,
        "supports_lots": True,
        "default_mode": "lots",
        "lot_units": 100000.0,
    }
    fake._normalize_manual_trade_quantity_mode = lambda value: normalize_manual_trade_quantity_mode(fake, value)

    payload = manual_trade_default_payload(fake, {"source": "chart_context_menu"})

    assert payload["symbol"] == "EUR/USD"
    assert payload["symbol_options"][0] == "EUR/USD"
    assert payload["quantity_mode"] == "lots"
    assert payload["amount"] == 0.01
    assert payload["source"] == "chart_context_menu"
    assert payload["timeframe"] == "4h"


def test_default_entry_price_for_symbol_prefers_side_specific_quote():
    chart = SimpleNamespace(
        _last_df=pd.DataFrame(
            [
                {"bid": 1.1001, "ask": 1.1003, "close": 1.1002},
                {"bid": 1.1011, "ask": 1.1014, "close": 1.1012},
            ]
        )
    )
    fake = SimpleNamespace(
        _chart_for_symbol=lambda symbol: chart if symbol == "EUR/USD" else None,
        _safe_float=_safe_float,
    )

    assert default_entry_price_for_symbol(fake, "EUR/USD", side="buy") == 1.1014
    assert default_entry_price_for_symbol(fake, "EUR/USD", side="sell") == 1.1011


def test_suggest_manual_trade_levels_uses_fallback_risk_distance_without_chart_data():
    fake = SimpleNamespace(
        _safe_float=_safe_float,
        _chart_for_symbol=lambda _symbol: None,
        _default_entry_price_for_symbol=lambda symbol, side="buy": 100.0,
        _normalize_manual_trade_price=lambda symbol, value: round(float(value), 2),
    )

    entry, stop_loss, take_profit = suggest_manual_trade_levels(fake, "BTC/USDT", side="buy")

    assert entry == 100.0
    assert stop_loss == 99.8
    assert take_profit == 100.4


def test_manual_trade_format_context_uses_oanda_precision_metadata():
    broker = SimpleNamespace(
        exchange_name="oanda",
        _normalize_symbol=lambda symbol: symbol.replace("/", "_"),
        _instrument_details={
            "EUR_USD": {
                "tradeUnitsPrecision": 0,
                "displayPrecision": 5,
                "minimumTradeSize": 1000,
            }
        },
        _format_units=lambda value, precision: f"{float(value):.{precision}f}",
        _format_price=lambda value, precision: f"{float(value):.{precision}f}",
    )
    fake = SimpleNamespace(controller=SimpleNamespace(broker=broker))

    context = manual_trade_format_context(fake, "EUR/USD")

    assert context["amount_decimals"] == 0
    assert context["price_decimals"] == 5
    assert context["min_amount"] == 1000.0
    assert context["amount_formatter"](1234.9) == 1235.0
    assert math.isclose(context["price_formatter"](1.234567), 1.23457)


def test_validate_manual_trade_amount_respects_minimum_lot_size():
    fake = SimpleNamespace()
    fake._normalize_manual_trade_quantity_mode = lambda value: normalize_manual_trade_quantity_mode(fake, value)
    fake._manual_trade_quantity_context = lambda symbol: {
        "symbol": symbol,
        "supports_lots": True,
        "default_mode": "lots",
        "lot_units": 100000.0,
    }
    fake._manual_trade_format_context = lambda _symbol: {
        "min_amount": 5000.0,
        "amount_formatter": lambda value: value,
    }
    fake._normalize_manual_trade_amount = lambda symbol, amount, quantity_mode="units": normalize_manual_trade_amount(
        fake, symbol, amount, quantity_mode=quantity_mode
    )

    amount, error = validate_manual_trade_amount(fake, "EUR/USD", 0.01, quantity_mode="lots")

    assert amount is None
    assert error == "Amount is below the broker minimum size of 0.05 lots for EUR/USD."


def test_normalize_manual_trade_price_uses_broker_formatter():
    fake = SimpleNamespace()
    fake._manual_trade_format_context = lambda _symbol: {
        "price_formatter": lambda value: round(float(value), 3),
    }

    assert normalize_manual_trade_price(fake, "BTC/USDT", "123.45678") == 123.457


def test_refresh_manual_trade_ticket_updates_controls_and_status():
    window = _manual_trade_window()
    window._manual_trade_symbol_picker.addItem("EUR/USD")
    window._manual_trade_symbol_picker.setCurrentText("EUR/USD")
    window._manual_trade_side_picker.setCurrentText("buy")
    window._manual_trade_type_picker.setCurrentText("limit")
    window._manual_trade_quantity_picker.setCurrentText("Lots")
    window._manual_trade_amount_input.setValue(0.25)
    window._manual_trade_price_input.setText("1.10123")
    window._manual_trade_stop_loss_input.setText("1.095")
    window._manual_trade_take_profit_input.setText("1.112")
    window._manual_trade_source = "chart_context_menu"

    state = {"synced": 0}
    fake = SimpleNamespace()
    fake._manual_trade_format_context = lambda _symbol: {
        "amount_decimals": 2,
        "price_decimals": 5,
        "min_amount": 1000.0,
    }
    fake._manual_trade_quantity_context = lambda _symbol: {
        "supports_lots": True,
        "default_mode": "lots",
        "lot_units": 100000.0,
    }
    fake._normalize_manual_trade_quantity_mode = lambda value: normalize_manual_trade_quantity_mode(fake, value)
    fake._normalize_manual_trade_amount = lambda symbol, amount, quantity_mode="units": normalize_manual_trade_amount(
        fake, symbol, amount, quantity_mode=quantity_mode
    )
    fake._sync_manual_trade_ticket_to_chart = lambda _window: state.__setitem__("synced", state["synced"] + 1)

    refresh_manual_trade_ticket(fake, window)

    assert window._manual_trade_price_input.isEnabled() is True
    assert window._manual_trade_stop_price_input.isEnabled() is False
    assert window._manual_trade_submit_btn.isEnabled() is True
    assert window._manual_trade_buy_limit_btn.text() == "Buy Limit"
    assert window._manual_trade_sell_limit_btn.text() == "Sell Limit"
    assert "1.00 lot = 100,000 units" in window._manual_trade_quantity_picker.toolTip()
    assert "Chart Context Menu ticket" in window._manual_trade_status.text()
    assert "LIMIT" in window._manual_trade_status.text()
    assert state["synced"] == 1


def test_refresh_manual_trade_ticket_updates_quick_side_labels_for_stop_limit():
    window = _manual_trade_window()
    window._manual_trade_symbol_picker.addItem("EUR/USD")
    window._manual_trade_symbol_picker.setCurrentText("EUR/USD")
    window._manual_trade_side_picker.setCurrentText("sell")
    window._manual_trade_type_picker.setCurrentText("stop_limit")
    window._manual_trade_price_input.setText("1.10123")
    window._manual_trade_stop_price_input.setText("1.102")

    fake = SimpleNamespace()
    fake._manual_trade_format_context = lambda _symbol: {
        "amount_decimals": 2,
        "price_decimals": 5,
        "min_amount": 1.0,
    }
    fake._manual_trade_quantity_context = lambda _symbol: {
        "supports_lots": False,
        "default_mode": "units",
        "lot_units": 100000.0,
    }
    fake._normalize_manual_trade_quantity_mode = lambda value: normalize_manual_trade_quantity_mode(fake, value)
    fake._normalize_manual_trade_amount = lambda symbol, amount, quantity_mode="units": normalize_manual_trade_amount(
        fake, symbol, amount, quantity_mode=quantity_mode
    )
    fake._sync_manual_trade_ticket_to_chart = lambda _window: None

    refresh_manual_trade_ticket(fake, window)

    assert window._manual_trade_buy_limit_btn.text() == "Buy Stop Limit"
    assert window._manual_trade_sell_limit_btn.text() == "Sell Stop Limit"


def test_populate_manual_trade_ticket_keeps_sl_tp_optional_and_sets_hint():
    window = _manual_trade_window()
    state = {"refreshed": 0}
    fake = SimpleNamespace(
        _manual_trade_default_payload=lambda _prefill=None: {
            "symbol_options": ["EUR/USD", "BTC/USDT"],
            "symbol": "EUR/USD",
            "side": "buy",
            "order_type": "limit",
            "amount": 0.5,
            "quantity_mode": "lots",
            "price": None,
            "stop_price": None,
            "stop_loss": None,
            "take_profit": None,
            "source": "chart_context_menu",
            "timeframe": "1h",
        },
        _default_entry_price_for_symbol=lambda symbol, side="buy": 1.2345,
        _refresh_manual_trade_ticket=lambda _window: state.__setitem__("refreshed", state["refreshed"] + 1),
    )

    populate_manual_trade_ticket(fake, window, prefill={"symbol": "EUR/USD"})

    assert window._manual_trade_symbol_picker.currentText() == "EUR/USD"
    assert window._manual_trade_side_picker.currentText() == "buy"
    assert window._manual_trade_type_picker.currentText() == "limit"
    assert window._manual_trade_quantity_picker.currentText() == "Lots"
    assert window._manual_trade_amount_input.value() == 0.5
    assert window._manual_trade_price_input.text() == "1.2345"
    assert window._manual_trade_stop_loss_input.text() == ""
    assert window._manual_trade_take_profit_input.text() == ""
    assert "Chart captured EUR/USD at 1.234500." in window._manual_trade_hint.text()
    assert "Stop loss and take profit are optional." in window._manual_trade_hint.text()
    assert state["refreshed"] == 1


def test_submit_manual_trade_from_ticket_normalizes_and_schedules_submit():
    window = _manual_trade_window()
    window._manual_trade_symbol_picker.addItem("EUR/USD")
    window._manual_trade_symbol_picker.setCurrentText("EUR/USD")
    window._manual_trade_side_picker.setCurrentText("sell")
    window._manual_trade_type_picker.setCurrentText("stop_limit")
    window._manual_trade_quantity_picker.setCurrentText("Lots")
    window._manual_trade_amount_input.setValue(0.01)
    window._manual_trade_price_input.setText("1.23456")
    window._manual_trade_stop_price_input.setText("1.23567")
    window._manual_trade_stop_loss_input.setText("1.24")
    window._manual_trade_take_profit_input.setText("1.22")

    captured = {"kwargs": None, "refreshes": 0, "tasks": 0}

    async def _submit_manual_trade(**kwargs):
        captured["kwargs"] = kwargs

    class _Loop:
        def create_task(self, coro):
            captured["tasks"] += 1
            import asyncio

            asyncio.run(coro)
            return SimpleNamespace()

    fake = SimpleNamespace(
        _normalize_manual_trade_quantity_mode=lambda value: normalize_manual_trade_quantity_mode(SimpleNamespace(), value),
        _validate_manual_trade_amount=lambda symbol, amount, quantity_mode="units": (1000.0, None),
        _normalize_manual_trade_price=lambda symbol, value: round(float(value), 3),
        _refresh_manual_trade_ticket=lambda _window: captured.__setitem__("refreshes", captured["refreshes"] + 1),
        _submit_manual_trade=_submit_manual_trade,
    )

    with patch("frontend.ui.panels.manual_trade_updates.asyncio.get_event_loop", return_value=_Loop()):
        submit_manual_trade_from_ticket(fake, window)

    assert window._manual_trade_price_input.text() == "1.235"
    assert window._manual_trade_stop_price_input.text() == "1.236"
    assert window._manual_trade_stop_loss_input.text() == "1.24"
    assert window._manual_trade_take_profit_input.text() == "1.22"
    assert captured["refreshes"] == 1
    assert captured["tasks"] == 1
    assert captured["kwargs"] == {
        "symbol": "EUR/USD",
        "side": "sell",
        "amount": 1000.0,
        "requested_amount": 0.01,
        "quantity_mode": "lots",
        "order_type": "stop_limit",
        "price": 1.235,
        "stop_price": 1.236,
        "stop_loss": 1.24,
        "take_profit": 1.22,
    }


def test_submit_manual_trade_side_sets_side_and_delegates():
    window = _manual_trade_window()
    window._manual_trade_type_picker.setCurrentText("stop_limit")
    events = {"refresh": 0, "submitted": 0}
    fake = SimpleNamespace(
        _refresh_manual_trade_ticket=lambda _window: events.__setitem__("refresh", events["refresh"] + 1),
        _submit_manual_trade_from_ticket=lambda _window: events.__setitem__("submitted", events["submitted"] + 1),
    )

    submit_manual_trade_side(fake, window, "sell")

    assert window._manual_trade_side_picker.currentText() == "sell"
    assert window._manual_trade_type_picker.currentText() == "stop_limit"
    assert events["refresh"] == 1
    assert events["submitted"] == 1
