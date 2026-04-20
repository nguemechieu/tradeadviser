from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class OrderBookPanel(QWidget):
    ROWS = 15
    TRADE_ROWS = 24

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.orderbook_table = QTableWidget(self.ROWS, 6)
        self.orderbook_table.setHorizontalHeaderLabels(
            ["Bid Depth", "Bid Size", "Bid Price", "Ask Price", "Ask Size", "Ask Depth"]
        )
        self.orderbook_table.verticalHeader().setVisible(False)
        self.orderbook_table.setAlternatingRowColors(True)
        self.orderbook_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.orderbook_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.orderbook_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.orderbook_page = QWidget()
        orderbook_layout = QVBoxLayout(self.orderbook_page)
        orderbook_layout.setContentsMargins(0, 0, 0, 0)
        orderbook_layout.addWidget(self.orderbook_table)
        self.tabs.addTab(self.orderbook_page, "Order Book")

        self.recent_trades_table = QTableWidget(self.TRADE_ROWS, 5)
        self.recent_trades_table.setHorizontalHeaderLabels(["Time", "Side", "Price", "Size", "Notional"])
        self.recent_trades_table.verticalHeader().setVisible(False)
        self.recent_trades_table.setAlternatingRowColors(True)
        self.recent_trades_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_trades_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_trades_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.recent_trades_status = QLabel("Waiting for market trades.")
        self.recent_trades_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.recent_trades_status.setStyleSheet("color: #8ca8cc; padding: 4px 2px;")

        self.trade_page = QWidget()
        recent_trades_layout = QVBoxLayout(self.trade_page)
        recent_trades_layout.setContentsMargins(0, 0, 0, 0)
        recent_trades_layout.setSpacing(6)
        recent_trades_layout.addWidget(self.recent_trades_status)
        recent_trades_layout.addWidget(self.recent_trades_table)
        self.tabs.addTab(self.trade_page, "Trade")

    def take_execution_pages(self):
        orderbook_page = self.orderbook_page
        trade_page = self.trade_page

        while self.tabs.count():
            self.tabs.removeTab(0)

        return orderbook_page, trade_page

    def update_orderbook(self, bids, asks):
        self.orderbook_table.clearContents()

        bid_depth = 0.0
        ask_depth = 0.0

        for i, level in enumerate((bids or [])[: self.ROWS]):
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                continue

            price, size = level[0], level[1]
            bid_depth += float(size)

            self._set_item(self.orderbook_table, i, 0, f"{bid_depth:.6f}", QColor("#d8ffea"))
            self._set_item(self.orderbook_table, i, 1, f"{float(size):.6f}", QColor("#b6f5d5"))
            self._set_item(self.orderbook_table, i, 2, f"{float(price):.8f}", QColor("#7ee2a8"))

        for i, level in enumerate((asks or [])[: self.ROWS]):
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                continue

            price, size = level[0], level[1]
            ask_depth += float(size)

            self._set_item(self.orderbook_table, i, 3, f"{float(price):.8f}", QColor("#ff9ea8"))
            self._set_item(self.orderbook_table, i, 4, f"{float(size):.6f}", QColor("#ffd0d5"))
            self._set_item(self.orderbook_table, i, 5, f"{ask_depth:.6f}", QColor("#ffe6e9"))

    def update_recent_trades(self, trades):
        rows = list(trades or [])[: self.TRADE_ROWS]
        self.recent_trades_table.clearContents()
        self.recent_trades_table.setRowCount(self.TRADE_ROWS)

        if not rows:
            self.recent_trades_status.setText("Recent public trades are unavailable for this symbol right now.")
            return

        self.recent_trades_status.setText(f"Showing {len(rows)} most recent market trade(s).")

        for row_index, trade in enumerate(rows):
            if not isinstance(trade, dict):
                continue

            side = str(trade.get("side") or "unknown").strip().lower()
            side_text = side.upper() if side else "-"
            side_color = QColor("#7ee2a8" if side == "buy" else "#ff9ea8" if side == "sell" else "#d8e6ff")

            self._set_item(
                self.recent_trades_table,
                row_index,
                0,
                str(trade.get("time") or trade.get("timestamp") or "-"),
                QColor("#8ca8cc"),
            )
            self._set_item(self.recent_trades_table, row_index, 1, side_text, side_color)
            self._set_item(
                self.recent_trades_table,
                row_index,
                2,
                self._format_numeric(trade.get("price"), 8),
                QColor("#d8e6ff"),
            )
            self._set_item(
                self.recent_trades_table,
                row_index,
                3,
                self._format_numeric(trade.get("amount"), 6),
                QColor("#c7d7f0"),
            )
            self._set_item(
                self.recent_trades_table,
                row_index,
                4,
                self._format_numeric(trade.get("notional"), 6),
                QColor("#9dd6ff"),
            )

    def _set_item(self, table, row, column, value, color):
        item = QTableWidgetItem(value)
        item.setForeground(color)
        table.setItem(row, column, item)

    def _format_numeric(self, value, digits):
        try:
            numeric = float(value)
        except Exception:
            return "-"
        if abs(numeric) >= 1000:
            return f"{numeric:,.2f}"
        if abs(numeric) >= 1:
            return f"{numeric:,.{min(digits, 4)}f}"
        return f"{numeric:,.{digits}f}"
