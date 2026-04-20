import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.components.panels.trading_panels import (
    ASSET_HEADERS,
    OPEN_ORDER_HEADERS,
    ORDER_HISTORY_HEADERS,
    POSITION_HEADERS,
    TRADE_HISTORY_HEADERS,
    TRADE_LOG_HEADERS,
    create_open_orders_panel,
    create_positions_panel,
    create_trade_log_panel,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.close_all_requests = 0
        self.assets_filter_runs = 0
        self.positions_filter_runs = 0
        self.open_orders_filter_runs = 0
        self.order_history_filter_runs = 0
        self.trade_history_filter_runs = 0
        self.trade_log_filter_runs = 0

    def _action_button_style(self):
        return ""

    def _close_all_positions(self):
        self.close_all_requests += 1

    def _apply_assets_filter(self):
        self.assets_filter_runs += 1

    def _apply_positions_filter(self):
        self.positions_filter_runs += 1

    def _apply_open_orders_filter(self):
        self.open_orders_filter_runs += 1

    def _apply_order_history_filter(self):
        self.order_history_filter_runs += 1

    def _apply_trade_history_filter(self):
        self.trade_history_filter_runs += 1

    def _apply_trade_log_filter(self):
        self.trade_log_filter_runs += 1


def test_create_positions_panel_builds_tabbed_tables_and_action_button():
    _app()
    terminal = DummyTerminal()

    dock = create_positions_panel(terminal)
    terminal.positions_close_all_button.click()

    assert terminal.close_all_requests == 1
    assert dock.windowTitle() == "Order Book"
    assert dock.widget() is terminal.orderbook_panel
    assert terminal.positions_orders_tabs.count() == 7
    assert terminal.positions_orders_tabs.tabText(0) == "Order Book"
    assert terminal.positions_orders_tabs.tabText(1) == "Assets"
    assert terminal.positions_orders_tabs.tabText(2) == "Open Orders"
    assert terminal.positions_orders_tabs.tabText(3) == "Trade"
    assert terminal.positions_orders_tabs.tabText(4) == "Order History"
    assert terminal.positions_orders_tabs.tabText(5) == "Trade History"
    assert terminal.positions_orders_tabs.tabText(6) == "Positions"
    assert terminal.assets_table.columnCount() == len(ASSET_HEADERS)
    assert [
        terminal.assets_table.horizontalHeaderItem(index).text()
        for index in range(terminal.assets_table.columnCount())
    ] == ASSET_HEADERS
    assert terminal.orderbook_panel.orderbook_table.columnCount() == 6
    assert terminal.orderbook_panel.recent_trades_table.columnCount() == 5
    assert terminal.positions_table.columnCount() == len(POSITION_HEADERS)
    assert [
        terminal.positions_table.horizontalHeaderItem(index).text()
        for index in range(terminal.positions_table.columnCount())
    ] == POSITION_HEADERS
    assert terminal.open_orders_table.columnCount() == len(OPEN_ORDER_HEADERS)
    assert [
        terminal.open_orders_table.horizontalHeaderItem(index).text()
        for index in range(terminal.open_orders_table.columnCount())
    ] == OPEN_ORDER_HEADERS
    assert terminal.order_history_table.columnCount() == len(ORDER_HISTORY_HEADERS)
    assert [
        terminal.order_history_table.horizontalHeaderItem(index).text()
        for index in range(terminal.order_history_table.columnCount())
    ] == ORDER_HISTORY_HEADERS
    assert terminal.trade_history_table.columnCount() == len(TRADE_HISTORY_HEADERS)
    assert [
        terminal.trade_history_table.horizontalHeaderItem(index).text()
        for index in range(terminal.trade_history_table.columnCount())
    ] == TRADE_HISTORY_HEADERS
    assert terminal.open_orders_dock is dock
    assert terminal.assets_filter_input.placeholderText() == "Search assets by symbol or balance values"
    assert terminal.assets_filter_summary.text() == "Showing all assets"
    assert terminal.positions_filter_input.placeholderText() == "Search positions by symbol, side, amount, or PnL"
    assert terminal.positions_filter_summary.text() == "Showing all positions"
    assert terminal.open_orders_filter_input.placeholderText() == "Search orders by symbol, type, status, or order id"
    assert terminal.open_orders_filter_summary.text() == "Showing all open orders"
    assert (
        terminal.order_history_filter_input.placeholderText()
        == "Search historical orders by symbol, status, side, type, or order id"
    )
    assert terminal.order_history_filter_summary.text() == "Showing all historical orders"
    assert terminal.trade_history_filter_input.placeholderText() == "Search trade history by symbol, source, side, status, or order id"
    assert terminal.trade_history_filter_summary.text() == "Showing all trade history rows"
    assert terminal.positions_orders_tabs is terminal.orderbook_panel.tabs


def test_create_open_orders_panel_reuses_combined_positions_dock():
    _app()
    terminal = DummyTerminal()

    first = create_positions_panel(terminal)
    second = create_open_orders_panel(terminal)

    assert second is first
    assert terminal.open_orders_dock is terminal.positions_dock
    assert terminal.orderbook_dock is terminal.positions_dock


def test_create_trade_log_panel_builds_expected_columns():
    _app()
    terminal = DummyTerminal()

    create_trade_log_panel(terminal)

    assert terminal.trade_log.columnCount() == len(TRADE_LOG_HEADERS)
    assert [
        terminal.trade_log.horizontalHeaderItem(index).text()
        for index in range(terminal.trade_log.columnCount())
    ] == TRADE_LOG_HEADERS
    assert terminal.trade_log_filter_input.placeholderText() == "Search trade history by symbol, source, side, status, or order id"
    assert terminal.trade_log_filter_summary.text() == "Showing all trade log rows"
