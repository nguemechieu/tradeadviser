import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QMainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.panels.manual_trade_panels import ensure_manual_trade_ticket_window


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_manual_trade_ticket_builder_creates_expected_widgets():
    _app()
    window = QMainWindow()
    fake = SimpleNamespace(
        _refresh_manual_trade_ticket=lambda _window: None,
        _apply_manual_trade_price_field_format=lambda _window, _attr: None,
        _populate_manual_trade_ticket=lambda _window, _prefill=None: None,
        _submit_manual_trade_from_ticket=lambda _window: None,
        _submit_manual_trade_side=lambda _window, _side: None,
        _clear_trade_overlays=lambda: None,
    )

    ensure_manual_trade_ticket_window(fake, window)

    assert window.centralWidget() is window._manual_trade_container
    assert window._manual_trade_symbol_picker.isEditable() is True
    assert window._manual_trade_side_picker.count() == 2
    assert window._manual_trade_type_picker.count() == 3
    assert window._manual_trade_quantity_picker.count() == 2
    assert window._manual_trade_amount_input.value() == 1.0
    assert window._manual_trade_submit_btn.text() == "Submit Order"
    assert window._manual_trade_buy_limit_btn.text() == "Buy Market"
    assert window._manual_trade_sell_limit_btn.text() == "Sell Market"
    assert "Stop loss and take profit are optional." in window._manual_trade_hint.text()
    assert window._manual_trade_source == "manual"


def test_manual_trade_ticket_builder_wires_signal_handlers():
    app = _app()
    window = QMainWindow()
    events = {
        "refresh": 0,
        "format": [],
        "populate": [],
        "submit": 0,
        "sides": [],
    }
    fake = SimpleNamespace(
        _refresh_manual_trade_ticket=lambda _window: events.__setitem__("refresh", events["refresh"] + 1),
        _apply_manual_trade_price_field_format=lambda _window, attr: events["format"].append(attr),
        _populate_manual_trade_ticket=lambda _window, prefill=None: events["populate"].append(prefill),
        _submit_manual_trade_from_ticket=lambda _window: events.__setitem__("submit", events["submit"] + 1),
        _submit_manual_trade_side=lambda _window, side: events["sides"].append(side),
        _clear_trade_overlays=lambda: None,
    )

    ensure_manual_trade_ticket_window(fake, window)

    window._manual_trade_symbol_picker.setEditText("EUR/USD")
    window._manual_trade_price_input.setText("1.2345")
    window._manual_trade_price_input.editingFinished.emit()
    window._manual_trade_reset_btn.click()
    window._manual_trade_submit_btn.click()
    window._manual_trade_buy_limit_btn.click()
    window._manual_trade_sell_limit_btn.click()
    app.processEvents()

    assert events["refresh"] >= 2
    assert events["format"] == ["_manual_trade_price_input"]
    assert events["populate"] == [None]
    assert events["submit"] == 1
    assert events["sides"] == ["buy", "sell"]


def test_manual_trade_ticket_builder_is_idempotent():
    _app()
    window = QMainWindow()
    fake = SimpleNamespace(
        _refresh_manual_trade_ticket=lambda _window: None,
        _apply_manual_trade_price_field_format=lambda _window, _attr: None,
        _populate_manual_trade_ticket=lambda _window, _prefill=None: None,
        _submit_manual_trade_from_ticket=lambda _window: None,
        _submit_manual_trade_side=lambda _window, _side: None,
        _clear_trade_overlays=lambda: None,
    )

    ensure_manual_trade_ticket_window(fake, window)
    first_container = window._manual_trade_container

    ensure_manual_trade_ticket_window(fake, window)

    assert window._manual_trade_container is first_container
