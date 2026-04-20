import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QTableWidget, QVBoxLayout, QWidget

from ui.components.panels.trading_panels import create_positions_panel


STRATEGY_SCORECARD_HEADERS = [
    "Strategy",
    "Source",
    "Orders",
    "Realized",
    "Win Rate",
    "Net PnL",
    "Avg Trade",
    "Avg Conf",
    "Avg Spread",
    "Avg Slip",
    "Fees",
]
STRATEGY_DEBUG_HEADERS = [
    "Index",
    "Signal",
    "RSI",
    "EMA Fast",
    "EMA Slow",
    "ML Prob",
    "Reason",
]


def create_orderbook_panel(terminal):
    return create_positions_panel(terminal)


def create_strategy_scorecard_panel(terminal):
    dock = QDockWidget("Strategy Scorecard", terminal)
    dock.setObjectName("strategy_scorecard_dock")
    terminal.strategy_scorecard_dock = dock
    terminal.strategy_table = QTableWidget()
    terminal.strategy_table.setColumnCount(len(STRATEGY_SCORECARD_HEADERS))
    terminal.strategy_table.setHorizontalHeaderLabels(STRATEGY_SCORECARD_HEADERS)
    dock.setWidget(terminal.strategy_table)
    terminal.addDockWidget(Qt.BottomDockWidgetArea, dock)
    dock.hide()
    return dock


def create_strategy_debug_panel(terminal):
    dock = QDockWidget("Strategy Debug", terminal)
    dock.setObjectName("strategy_debug_dock")
    terminal.strategy_debug_dock = dock
    terminal.debug_table = QTableWidget()
    terminal.debug_table.setColumnCount(len(STRATEGY_DEBUG_HEADERS))
    terminal.debug_table.setHorizontalHeaderLabels(STRATEGY_DEBUG_HEADERS)
    dock.setWidget(terminal.debug_table)
    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    dock.hide()
    return dock


def create_risk_heatmap_panel(terminal):
    dock = QDockWidget("Risk Heatmap", terminal)
    dock.setObjectName("risk_heatmap_dock")
    terminal.risk_heatmap_dock = dock

    terminal.risk_map = pg.ImageItem()

    plot = pg.PlotWidget()
    plot.setBackground("#0b1220")
    plot.showGrid(x=False, y=False, alpha=0.0)
    plot.hideAxis("bottom")
    plot.hideAxis("left")
    plot.addItem(terminal.risk_map)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(4)
    layout.addWidget(plot)

    terminal.risk_heatmap_status_label = QLabel("Risk heatmap is waiting for portfolio data.")
    terminal.risk_heatmap_status_label.setWordWrap(True)
    layout.addWidget(terminal.risk_heatmap_status_label)
    terminal._set_risk_heatmap_status("Risk heatmap is waiting for portfolio data.", "muted")

    dock.setWidget(container)

    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    return dock
