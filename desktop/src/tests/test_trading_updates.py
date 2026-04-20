import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QTableWidget, QTableWidgetItem

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.panels.trading_updates import (
    normalize_open_order_entry,
    normalize_position_entry,
    populate_assets_table,
    populate_open_orders_table,
    populate_order_history_table,
    populate_positions_table,
    populate_trade_history_table,
    update_trade_log,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_normalize_position_entry_derives_mark_value_and_pnl():
    fake = SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 1.25)

    result = normalize_position_entry(
        fake,
        {
            "symbol": "EUR/USD",
            "side": "long",
            "amount": 2.0,
            "entry_price": 1.10,
        },
    )

    assert result["mark_price"] == 1.25
    assert result["value"] == 2.5
    assert round(result["pnl"], 2) == 0.30


def test_normalize_open_order_entry_uses_mid_price_and_computes_pnl():
    fake = SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0)

    result = normalize_open_order_entry(
        fake,
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "price": 100.0,
            "amount": 2.0,
            "filled": 0.5,
            "status": "open",
        },
    )

    assert result["mark"] == 105.0
    assert result["remaining"] == 1.5
    assert result["pnl"] == 7.5


def test_populate_assets_table_builds_rows_from_balance_snapshot_and_filters():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        assets_table=table,
        assets_filter_input=search,
        assets_filter_summary=summary,
        _assets_table_signature=None,
    )

    balances = {
        "free": {"USD": 800.0, "BTC": 0.25},
        "used": {"USD": 200.0, "BTC": 0.0},
        "total": {"USD": 1000.0, "BTC": 0.25},
    }

    populate_assets_table(fake, balances)
    search.setText("btc")
    populate_assets_table(fake, balances)

    assert table.rowCount() == 2
    assert table.isRowHidden(0) != table.isRowHidden(1)
    assert summary.text() == "Showing 1 of 2 assets"


def test_populate_order_history_table_filters_rows():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        order_history_table=table,
        order_history_filter_input=search,
        order_history_filter_summary=summary,
        _order_history_table_signature=None,
    )

    rows = [
        {"timestamp": "2026-04-12T12:00:00Z", "symbol": "BTC/USDT", "side": "buy", "type": "limit", "price": 100.0, "filled": 1.0, "remaining": 0.0, "status": "filled", "id": "ord-1"},
        {"timestamp": "2026-04-12T12:01:00Z", "symbol": "ETH/USDT", "side": "sell", "type": "market", "price": 200.0, "filled": 0.5, "remaining": 0.5, "status": "partial", "id": "ord-2"},
    ]

    populate_order_history_table(fake, rows)
    search.setText("eth")
    populate_order_history_table(fake, rows)

    assert table.rowCount() == 2
    hidden_rows = [table.isRowHidden(index) for index in range(table.rowCount())]
    assert hidden_rows.count(True) == 1
    assert hidden_rows.count(False) == 1
    assert summary.text() == "Showing 1 of 2 historical orders"


def test_populate_trade_history_table_reuses_trade_log_normalization_and_filters():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        trade_history_table=table,
        trade_history_filter_input=search,
        trade_history_filter_summary=summary,
        _trade_history_table_signature=None,
        _normalize_trade_log_entry=lambda trade: trade,
        _format_trade_log_value=lambda value: "" if value is None else str(value),
    )

    rows = [
        {"timestamp": "2026-04-12T12:00:00Z", "symbol": "BTC/USDT", "source": "Bot", "side": "buy", "price": 100.0, "size": 1.0, "order_type": "limit", "status": "filled", "order_id": "ord-1", "pnl": 10.0},
        {"timestamp": "2026-04-12T12:01:00Z", "symbol": "ETH/USDT", "source": "Manual", "side": "sell", "price": 200.0, "size": 2.0, "order_type": "market", "status": "closed", "order_id": "ord-2", "pnl": -5.0, "reason": "Fade"},
    ]

    populate_trade_history_table(fake, rows)
    search.setText("manual")
    populate_trade_history_table(fake, rows)

    assert table.rowCount() == 2
    assert table.isRowHidden(0) is True
    assert table.isRowHidden(1) is False
    assert summary.text() == "Showing 1 of 2 trade history rows"


def test_update_trade_log_inserts_row_and_sets_tooltip():
    _app()
    refreshed = []
    table = QTableWidget()
    table.setColumnCount(10)
    fake = SimpleNamespace(
        trade_log=table,
        MAX_LOG_ROWS=200,
        _normalize_trade_log_entry=lambda trade: trade,
        _trade_log_row_for_entry=lambda _entry: None,
        _format_trade_log_value=lambda value: "" if value is None else str(value),
        _refresh_performance_views=lambda: refreshed.append(True),
    )

    update_trade_log(
        fake,
        {
            "timestamp": "2026-03-15T12:00:00Z",
            "symbol": "EUR/USD",
            "source": "Bot",
            "side": "buy",
            "price": 1.12,
            "size": 1000,
            "order_type": "market",
            "status": "filled",
            "order_id": "ord-1",
            "pnl": 12.5,
            "stop_loss": 1.1,
            "take_profit": 1.15,
            "reason": "Breakout",
            "strategy_name": "Trend Following",
            "confidence": 0.82,
            "spread_bps": 0.9,
            "slippage_bps": 0.2,
            "fee": 0.1,
            "blocked_by_guard": False,
        },
    )

    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "EUR/USD"
    assert "SL: 1.1" in table.item(0, 0).toolTip()
    assert refreshed == [True]


def test_update_trade_log_updates_existing_row_by_order_id():
    _app()
    table = QTableWidget()
    table.setColumnCount(10)
    table.insertRow(0)
    table.setItem(0, 8, QTableWidgetItem("ord-1"))
    fake = SimpleNamespace(
        trade_log=table,
        MAX_LOG_ROWS=200,
        _normalize_trade_log_entry=lambda trade: trade,
        _trade_log_row_for_entry=lambda _entry: 0,
        _format_trade_log_value=lambda value: "" if value is None else str(value),
        _refresh_performance_views=lambda: None,
    )

    update_trade_log(
        fake,
        {
            "timestamp": "2026-03-15T12:05:00Z",
            "symbol": "EUR/USD",
            "source": "Bot",
            "side": "sell",
            "price": 1.13,
            "size": 1000,
            "order_type": "market",
            "status": "closed",
            "order_id": "ord-1",
            "pnl": 20.0,
            "stop_loss": "",
            "take_profit": "",
            "reason": "",
            "strategy_name": "",
            "confidence": "",
            "spread_bps": "",
            "slippage_bps": "",
            "fee": "",
            "blocked_by_guard": False,
        },
    )

    assert table.rowCount() == 1
    assert table.item(0, 3).text() == "sell"


def test_populate_positions_table_applies_query_filter_and_summary():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        positions_table=table,
        positions_filter_input=search,
        positions_filter_summary=summary,
        positions_close_all_button=SimpleNamespace(setEnabled=lambda _value: None),
        controller=SimpleNamespace(broker=object()),
        _normalize_position_entry=lambda payload: normalize_position_entry(
            SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0),
            payload,
        ),
        _build_position_close_button=lambda _position, compact=False: None,
    )

    rows = [
        {"symbol": "BTC/USDT", "side": "long", "amount": 1.0, "entry_price": 100.0},
        {"symbol": "ETH/USDT", "side": "short", "amount": 2.0, "entry_price": 200.0, "mark_price": 190.0},
    ]
    populate_positions_table(fake, rows)
    search.setText("eth")
    populate_positions_table(fake, rows)

    assert table.rowCount() == 2
    assert table.isRowHidden(0) is True
    assert table.isRowHidden(1) is False
    assert summary.text() == "Showing 1 of 2 positions"


def test_populate_positions_table_skips_rebuilding_identical_rows():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    built_buttons = []
    fake = SimpleNamespace(
        positions_table=table,
        positions_filter_input=search,
        positions_filter_summary=summary,
        positions_close_all_button=SimpleNamespace(setEnabled=lambda _value: None),
        controller=SimpleNamespace(broker=object()),
        _positions_table_signature=None,
        _normalize_position_entry=lambda payload: normalize_position_entry(
            SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0),
            payload,
        ),
        _build_position_close_button=lambda position, compact=False: built_buttons.append((position["symbol"], compact)) or None,
    )

    rows = [
        {"symbol": "BTC/USDT", "side": "long", "amount": 1.0, "entry_price": 100.0},
        {"symbol": "ETH/USDT", "side": "short", "amount": 2.0, "entry_price": 200.0, "mark_price": 190.0},
    ]

    populate_positions_table(fake, rows)
    populate_positions_table(fake, rows)

    assert len(built_buttons) == 2


def test_populate_open_orders_table_applies_query_filter_and_summary():
    _app()
    table = QTableWidget()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        open_orders_table=table,
        open_orders_filter_input=search,
        open_orders_filter_summary=summary,
        _normalize_open_order_entry=lambda payload: normalize_open_order_entry(
            SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0),
            payload,
        ),
    )

    rows = [
        {"symbol": "BTC/USDT", "side": "buy", "type": "limit", "price": 100.0, "amount": 1.0, "filled": 0.0, "status": "open"},
        {"symbol": "ETH/USDT", "side": "sell", "type": "market", "amount": 3.0, "filled": 1.0, "status": "pending"},
    ]
    populate_open_orders_table(fake, rows)
    search.setText("pending")
    populate_open_orders_table(fake, rows)

    assert table.rowCount() == 2
    assert table.isRowHidden(0) is True
    assert table.isRowHidden(1) is False
    assert summary.text() == "Showing 1 of 2 open orders"


def test_populate_open_orders_table_skips_rebuilding_identical_rows():
    _app()

    class _CountingTable(QTableWidget):
        def __init__(self):
            super().__init__()
            self.set_item_calls = 0

        def setItem(self, row, column, item):
            self.set_item_calls += 1
            super().setItem(row, column, item)

    table = _CountingTable()
    summary = QLabel()
    search = QLineEdit()
    fake = SimpleNamespace(
        open_orders_table=table,
        open_orders_filter_input=search,
        open_orders_filter_summary=summary,
        _open_orders_table_signature=None,
        _normalize_open_order_entry=lambda payload: normalize_open_order_entry(
            SimpleNamespace(_lookup_symbol_mid_price=lambda _symbol: 105.0),
            payload,
        ),
    )

    rows = [
        {"symbol": "BTC/USDT", "side": "buy", "type": "limit", "price": 100.0, "amount": 1.0, "filled": 0.0, "status": "open"},
        {"symbol": "ETH/USDT", "side": "sell", "type": "market", "amount": 3.0, "filled": 1.0, "status": "pending"},
    ]

    populate_open_orders_table(fake, rows)
    first_pass_calls = table.set_item_calls
    populate_open_orders_table(fake, rows)

    assert table.set_item_calls == first_pass_calls


def test_update_trade_log_applies_query_filter_and_summary():
    _app()
    refreshed = []
    table = QTableWidget()
    table.setColumnCount(10)
    summary = QLabel()
    search = QLineEdit()

    def find_existing_row(entry):
        order_id = str(entry.get("order_id") or "").strip()
        for row in range(table.rowCount()):
            item = table.item(row, 8)
            if item is not None and item.text().strip() == order_id:
                return row
        return None

    fake = SimpleNamespace(
        trade_log=table,
        trade_log_filter_input=search,
        trade_log_filter_summary=summary,
        MAX_LOG_ROWS=200,
        _normalize_trade_log_entry=lambda trade: trade,
        _trade_log_row_for_entry=find_existing_row,
        _format_trade_log_value=lambda value: "" if value is None else str(value),
        _refresh_performance_views=lambda: refreshed.append(True),
    )

    update_trade_log(
        fake,
        {
            "timestamp": "2026-03-15T12:00:00Z",
            "symbol": "EUR/USD",
            "source": "Manual",
            "side": "buy",
            "price": 1.12,
            "size": 1000,
            "order_type": "market",
            "status": "filled",
            "order_id": "ord-1",
            "pnl": 12.5,
            "reason": "Breakout",
            "blocked_by_guard": False,
        },
    )
    update_trade_log(
        fake,
        {
            "timestamp": "2026-03-15T12:01:00Z",
            "symbol": "BTC/USDT",
            "source": "Bot",
            "side": "sell",
            "price": 65000,
            "size": 0.25,
            "order_type": "limit",
            "status": "blocked",
            "order_id": "ord-2",
            "pnl": "",
            "reason": "Stale quote",
            "blocked_by_guard": True,
        },
    )
    search.setText("stale")
    update_trade_log(
        fake,
        {
            "timestamp": "2026-03-15T12:01:00Z",
            "symbol": "BTC/USDT",
            "source": "Bot",
            "side": "sell",
            "price": 65000,
            "size": 0.25,
            "order_type": "limit",
            "status": "blocked",
            "order_id": "ord-2",
            "pnl": "",
            "reason": "Stale quote",
            "blocked_by_guard": True,
        },
    )

    assert table.rowCount() == 2
    assert table.isRowHidden(0) is True
    assert table.isRowHidden(1) is False
    assert summary.text() == "Showing 1 of 2 trade log rows"
    assert refreshed[-1] is True
