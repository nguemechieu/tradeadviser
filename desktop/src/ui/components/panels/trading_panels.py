from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.panels.orderbook_panel import OrderBookPanel


POSITION_HEADERS = ["Symbol", "Side", "Amount", "Entry", "Mark", "Value", "PnL", "Action"]
ASSET_HEADERS = ["Asset", "Free", "Used", "Total"]
OPEN_ORDER_HEADERS = [
    "Symbol",
    "Side",
    "Type",
    "Price",
    "Mark",
    "Amount",
    "Filled",
    "Remaining",
    "Status",
    "PnL",
    "Order ID",
]
ORDER_HISTORY_HEADERS = [
    "Timestamp",
    "Symbol",
    "Side",
    "Type",
    "Price",
    "Filled",
    "Remaining",
    "Status",
    "Order ID",
]
TRADE_LOG_HEADERS = [
    "Timestamp",
    "Symbol",
    "Source",
    "Side",
    "Price",
    "Size",
    "Order Type",
    "Status",
    "Order ID",
    "PnL",
]
TRADE_HISTORY_HEADERS = list(TRADE_LOG_HEADERS)


def _ensure_orderbook_dock(terminal):
    dock = getattr(terminal, "orderbook_dock", None)
    panel = getattr(terminal, "orderbook_panel", None)
    if dock is not None and panel is not None:
        terminal.positions_dock = dock
        terminal.open_orders_dock = dock
        return dock, panel

    dock = QDockWidget("Order Book", terminal)
    dock.setObjectName("orderbook_dock")
    panel = OrderBookPanel()
    terminal.orderbook_dock = dock
    terminal.positions_dock = dock
    terminal.open_orders_dock = dock
    terminal.orderbook_panel = panel
    dock.setWidget(panel)
    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    return dock, panel


def _build_assets_tab(terminal):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search assets by symbol or balance values")
    filter_summary = QLabel("Showing all assets")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.assets_table = QTableWidget()
    terminal.assets_table.setColumnCount(len(ASSET_HEADERS))
    terminal.assets_table.setHorizontalHeaderLabels(ASSET_HEADERS)
    layout.addWidget(terminal.assets_table)
    terminal.assets_filter_input = filter_input
    terminal.assets_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_assets_filter())
    return container


def _build_positions_tab(terminal):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    actions = QHBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    actions.addStretch()
    close_all_btn = QPushButton("Close All Positions")
    close_all_btn.setStyleSheet(terminal._action_button_style())
    close_all_btn.clicked.connect(terminal._close_all_positions)
    actions.addWidget(close_all_btn)
    layout.addLayout(actions)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search positions by symbol, side, amount, or PnL")
    filter_summary = QLabel("Showing all positions")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.positions_table = QTableWidget()
    terminal.positions_table.setColumnCount(len(POSITION_HEADERS))
    terminal.positions_table.setHorizontalHeaderLabels(POSITION_HEADERS)
    layout.addWidget(terminal.positions_table)
    terminal.positions_filter_input = filter_input
    terminal.positions_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_positions_filter())
    terminal.positions_close_all_button = close_all_btn
    return container


def _build_open_orders_tab(terminal):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search orders by symbol, type, status, or order id")
    filter_summary = QLabel("Showing all open orders")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.open_orders_table = QTableWidget()
    terminal.open_orders_table.setColumnCount(len(OPEN_ORDER_HEADERS))
    terminal.open_orders_table.setHorizontalHeaderLabels(OPEN_ORDER_HEADERS)
    layout.addWidget(terminal.open_orders_table)
    terminal.open_orders_filter_input = filter_input
    terminal.open_orders_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_open_orders_filter())
    return container


def _build_order_history_tab(terminal):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search historical orders by symbol, status, side, type, or order id")
    filter_summary = QLabel("Showing all historical orders")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.order_history_table = QTableWidget()
    terminal.order_history_table.setColumnCount(len(ORDER_HISTORY_HEADERS))
    terminal.order_history_table.setHorizontalHeaderLabels(ORDER_HISTORY_HEADERS)
    layout.addWidget(terminal.order_history_table)
    terminal.order_history_filter_input = filter_input
    terminal.order_history_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_order_history_filter())
    return container


def _build_trade_history_tab(terminal):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search trade history by symbol, source, side, status, or order id")
    filter_summary = QLabel("Showing all trade history rows")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.trade_history_table = QTableWidget()
    terminal.trade_history_table.setColumnCount(len(TRADE_HISTORY_HEADERS))
    terminal.trade_history_table.setHorizontalHeaderLabels(TRADE_HISTORY_HEADERS)
    layout.addWidget(terminal.trade_history_table)
    terminal.trade_history_filter_input = filter_input
    terminal.trade_history_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_trade_history_filter())
    return container


def create_positions_panel(terminal):
    dock, panel = _ensure_orderbook_dock(terminal)
    tabs = panel.tabs
    if getattr(terminal, "positions_orders_tabs", None) is tabs:
        return dock

    tabs.setObjectName("positions_orders_tabs")
    tabs.setDocumentMode(True)
    tabs.setUsesScrollButtons(True)
    # Set tab position to bottom (South) for better viewing like MT4
    tabs.setTabPosition(QTabWidget.TabPosition.South)
    apply_tab_chrome = getattr(terminal, "_apply_workspace_tab_chrome", None)
    if callable(apply_tab_chrome):
        apply_tab_chrome(tabs)

    trade_index = tabs.indexOf(panel.trade_page)
    if trade_index < 0:
        trade_index = tabs.count()

    tabs.insertTab(1, _build_assets_tab(terminal), "Assets")
    tabs.insertTab(2, _build_open_orders_tab(terminal), "Open Orders")
    trade_index = tabs.indexOf(panel.trade_page)
    if trade_index < 0:
        trade_index = tabs.count()
    tabs.insertTab(trade_index + 1, _build_order_history_tab(terminal), "Order History")
    tabs.insertTab(trade_index + 2, _build_trade_history_tab(terminal), "Trade History")
    tabs.addTab(_build_positions_tab(terminal), "Positions")

    terminal.positions_orders_tabs = tabs
    terminal.execution_tabs = tabs
    
    # Move the orderbook tabs to system console if available
    system_console = getattr(terminal, "system_console", None)
    if system_console:
        try:
            # Remove from dock and add to system console
            if dock and not dock.isFloating():
                parent = dock.parent()
                if parent:
                    terminal.removeDockWidget(dock)
            system_console.set_orderbook_widget(tabs)
        except Exception:
            pass  # Fall back to normal dock display
    
    return dock


def create_open_orders_panel(terminal):
    dock = getattr(terminal, "orderbook_dock", None)
    if dock is None:
        dock = create_positions_panel(terminal)
    terminal.positions_dock = dock
    terminal.open_orders_dock = dock
    return dock


def create_trade_log_panel(terminal):
    dock = QDockWidget("Trade Log", terminal)
    dock.setObjectName("trade_log_dock")
    terminal.trade_log_dock = dock
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)
    filter_label = QLabel("Filter")
    filter_input = QLineEdit()
    filter_input.setPlaceholderText("Search trade history by symbol, source, side, status, or order id")
    filter_summary = QLabel("Showing all trade log rows")
    filter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    filter_row.addWidget(filter_label)
    filter_row.addWidget(filter_input, 1)
    filter_row.addWidget(filter_summary)
    layout.addLayout(filter_row)

    terminal.trade_log = QTableWidget()
    terminal.trade_log.setColumnCount(len(TRADE_LOG_HEADERS))
    terminal.trade_log.setHorizontalHeaderLabels(TRADE_LOG_HEADERS)
    layout.addWidget(terminal.trade_log)
    terminal.trade_log_filter_input = filter_input
    terminal.trade_log_filter_summary = filter_summary
    filter_input.textChanged.connect(lambda *_: terminal._apply_trade_log_filter())
    dock.setWidget(container)
    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    return dock
