import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QTableWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.components.panels.trading_updates import (
    normalize_open_order_entry,
    normalize_order_history_entry,
    normalize_position_entry,
    normalize_trade_log_entry,
    populate_open_orders_table,
    populate_positions_table,
    populate_trade_history_table,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_normalize_open_order_entry_accepts_object_payload():
    fake = SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0)
    order = SimpleNamespace(
        symbol="BTC/USDT",
        side="buy",
        type="limit",
        price="100",
        amount="2",
        filled="0.5",
        status="open",
        id="ord-1",
    )

    result = normalize_open_order_entry(fake, order)

    assert result is not None
    assert result["symbol"] == "BTC/USDT"
    assert result["remaining"] == 1.5
    assert result["order_id"] == "ord-1"
    assert result["pnl"] == 7.5


def test_normalize_order_history_entry_accepts_object_payload():
    order = SimpleNamespace(
        datetime="2026-04-12T12:00:00Z",
        instrument="ETH/USDT",
        side="sell",
        order_type="market",
        average="200",
        quantity="2",
        filled_quantity="1.25",
        remaining="0.75",
        state="partial",
        client_order_id="hist-1",
    )

    result = normalize_order_history_entry(order)

    assert result is not None
    assert result["symbol"] == "ETH/USDT"
    assert result["type"] == "market"
    assert result["filled"] == 1.25
    assert result["remaining"] == 0.75
    assert result["order_id"] == "hist-1"


def test_normalize_trade_log_entry_accepts_object_payload():
    fake = SimpleNamespace(_format_trade_source_label=lambda value: str(value or "").title())
    trade = SimpleNamespace(
        datetime="2026-04-12T12:01:00Z",
        instrument="SOL/USDT",
        source="broker",
        side="sell",
        average="150.5",
        quantity="3",
        type="market",
        state="filled",
        order="trade-1",
        realizedPL="12.4",
        message="Take profit hit",
        blocked_by_guard=False,
    )

    result = normalize_trade_log_entry(fake, trade)

    assert result is not None
    assert result["symbol"] == "SOL/USDT"
    assert result["timestamp"] == "2026-04-12T12:01:00Z"
    assert result["price"] == "150.5"
    assert result["size"] == "3"
    assert result["order_id"] == "trade-1"
    assert result["pnl"] == "12.4"


def test_populate_account_tabs_accept_object_rows():
    _app()
    open_orders_table = QTableWidget()
    open_orders_summary = QLabel()
    open_orders_search = QLineEdit()
    positions_table = QTableWidget()
    positions_summary = QLabel()
    positions_search = QLineEdit()
    trade_history_table = QTableWidget()
    trade_history_summary = QLabel()
    trade_history_search = QLineEdit()

    fake = SimpleNamespace(
        controller=SimpleNamespace(broker=object()),
        open_orders_table=open_orders_table,
        open_orders_filter_input=open_orders_search,
        open_orders_filter_summary=open_orders_summary,
        positions_table=positions_table,
        positions_filter_input=positions_search,
        positions_filter_summary=positions_summary,
        positions_close_all_button=SimpleNamespace(setEnabled=lambda _value: None),
        trade_history_table=trade_history_table,
        trade_history_filter_input=trade_history_search,
        trade_history_filter_summary=trade_history_summary,
        _lookup_symbol_mid_price=lambda _symbol: 105.0,
        _normalize_open_order_entry=lambda payload: normalize_open_order_entry(fake, payload),
        _normalize_position_entry=lambda payload: normalize_position_entry(fake, payload),
        _normalize_trade_log_entry=lambda payload: normalize_trade_log_entry(fake, payload),
        _format_trade_source_label=lambda value: str(value or "").title(),
        _format_trade_log_value=lambda value: "" if value is None else str(value),
        _build_position_close_button=lambda _position, compact=False: None,
    )

    populate_open_orders_table(
        fake,
        [
            SimpleNamespace(
                symbol="BTC/USDT",
                side="buy",
                type="limit",
                price="100",
                amount="2",
                filled="0.5",
                status="open",
                id="ord-1",
            )
        ],
    )
    populate_positions_table(
        fake,
        [
            SimpleNamespace(
                symbol="ETH/USDT",
                side="long",
                amount="1.5",
                entry_price="95",
                mark_price="105",
                pnl="15",
            )
        ],
    )
    populate_trade_history_table(
        fake,
        [
            SimpleNamespace(
                datetime="2026-04-12T12:01:00Z",
                instrument="SOL/USDT",
                source="broker",
                side="sell",
                average="150.5",
                quantity="3",
                type="market",
                state="filled",
                order="trade-1",
                realizedPL="12.4",
            )
        ],
    )

    assert open_orders_table.rowCount() == 1
    assert positions_table.rowCount() == 1
    assert trade_history_table.rowCount() == 1
