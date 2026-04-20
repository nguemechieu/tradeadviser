import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.components.panels.workspace_panels import (
    STRATEGY_DEBUG_HEADERS,
    STRATEGY_SCORECARD_HEADERS,
    create_orderbook_panel,
    create_risk_heatmap_panel,
    create_strategy_debug_panel,
    create_strategy_scorecard_panel,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.status_updates = []
        self.close_all_requests = 0
        self.assets_filter_runs = 0
        self.positions_filter_runs = 0
        self.open_orders_filter_runs = 0
        self.order_history_filter_runs = 0
        self.trade_history_filter_runs = 0

    def _set_risk_heatmap_status(self, message, tone="muted"):
        self.status_updates.append((message, tone))
        if getattr(self, "risk_heatmap_status_label", None) is not None:
            self.risk_heatmap_status_label.setText(str(message))

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


def test_create_orderbook_panel_sets_orderbook_widget():
    _app()
    terminal = DummyTerminal()

    dock = create_orderbook_panel(terminal)

    assert terminal.orderbook_panel is not None
    assert terminal.orderbook_dock is dock
    assert terminal.orderbook_dock is terminal.positions_dock
    assert dock.widget() is terminal.orderbook_panel
    assert terminal.positions_orders_tabs is terminal.orderbook_panel.tabs
    assert terminal.positions_orders_tabs.tabText(0) == "Order Book"
    assert terminal.positions_orders_tabs.tabText(3) == "Trade"


def test_create_strategy_scorecard_panel_builds_expected_columns():
    _app()
    terminal = DummyTerminal()

    create_strategy_scorecard_panel(terminal)

    assert terminal.strategy_table.columnCount() == len(STRATEGY_SCORECARD_HEADERS)
    assert [
        terminal.strategy_table.horizontalHeaderItem(index).text()
        for index in range(terminal.strategy_table.columnCount())
    ] == STRATEGY_SCORECARD_HEADERS


def test_create_strategy_debug_panel_builds_expected_columns():
    _app()
    terminal = DummyTerminal()

    create_strategy_debug_panel(terminal)

    assert terminal.debug_table.columnCount() == len(STRATEGY_DEBUG_HEADERS)
    assert [
        terminal.debug_table.horizontalHeaderItem(index).text()
        for index in range(terminal.debug_table.columnCount())
    ] == STRATEGY_DEBUG_HEADERS


def test_create_risk_heatmap_panel_initializes_map_and_status():
    _app()
    terminal = DummyTerminal()

    create_risk_heatmap_panel(terminal)

    assert terminal.risk_map is not None
    assert terminal.risk_heatmap_status_label.text() == "Risk heatmap is waiting for portfolio data."
    assert terminal.status_updates[-1] == ("Risk heatmap is waiting for portfolio data.", "muted")
