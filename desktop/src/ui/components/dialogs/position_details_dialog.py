"""Position Details Dialog for viewing and managing open positions.

Displays comprehensive position information similar to Coinbase interface,
with options to close, modify TP/SL, and enable trailing stops.
"""

from typing import Optional, Callable
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGridLayout,
    QWidget,
    QMessageBox,
    QInputDialog,
    QDoubleSpinBox,
    QComboBox,
    QFormLayout,
)


class PositionDetailsDialog(QDialog):
    """Dialog showing detailed position information and management options."""

    def __init__(
        self,
        parent,
        position: dict,
        terminal=None,
        on_close_position: Optional[Callable] = None,
        on_close_all: Optional[Callable] = None,
    ):
        super().__init__(parent)
        self.position = position
        self.terminal = terminal
        self.on_close_position = on_close_position
        self.on_close_all = on_close_all

        self.setWindowTitle(f"Position Details - {position.get('symbol', 'Unknown')}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._setup_ui()

    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title section
        title_layout = QHBoxLayout()
        title = QLabel(self.position.get("symbol", "Unknown"))
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title_layout.addWidget(title)

        side_label = QLabel(str(self.position.get("side", "")).upper())
        side_label.setStyleSheet(self._side_color(self.position.get("side", "")))
        side_font = QFont()
        side_font.setPointSize(12)
        side_font.setBold(True)
        side_label.setFont(side_font)
        title_layout.addWidget(side_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(title_layout)

        # Main details grid
        details_widget = QWidget()
        details_layout = QGridLayout(details_widget)
        details_layout.setSpacing(12)

        row = 0
        # Position info
        details_layout.addWidget(QLabel("Position Details"), 0, 0, 1, 2)
        row = 1

        info_fields = [
            ("Side", self._format_side()),
            ("Amount", self._format_amount()),
            ("Venue", self.position.get("venue", "Unknown")),
            ("Notional Value", self._format_notional()),
            ("Avg Entry", self._format_price(self.position.get("entry_price", 0))),
            ("Current Price", self._format_price(self.position.get("mark_price", 0))),
        ]

        for label_text, value_text in info_fields:
            label = QLabel(label_text + ":")
            label.setStyleSheet("font-weight: bold;")
            value = QLabel(value_text)
            details_layout.addWidget(label, row, 0)
            details_layout.addWidget(value, row, 1)
            row += 1

        # P&L section
        pnl = self.position.get("pnl", 0)
        pnl_color = "#32d296" if pnl >= 0 else "#ef5350"
        pnl_label = QLabel("Unrealized P&L:")
        pnl_label.setStyleSheet("font-weight: bold;")
        pnl_value = QLabel(f"${pnl:,.2f}")
        pnl_value.setStyleSheet(f"color: {pnl_color}; font-weight: bold;")
        details_layout.addWidget(pnl_label, row, 0)
        details_layout.addWidget(pnl_value, row, 1)
        row += 1

        # Funding
        funding = self.position.get("financing", 0)
        funding_label = QLabel("Funding:")
        funding_label.setStyleSheet("font-weight: bold;")
        funding_value = QLabel(f"${funding:,.4f}")
        details_layout.addWidget(funding_label, row, 0)
        details_layout.addWidget(funding_value, row, 1)
        row += 1

        # Liquidation prices section
        liquidation_separator = QLabel("Liquidation Prices")
        liquidation_separator.setStyleSheet("font-weight: bold;")
        details_layout.addWidget(liquidation_separator, row, 0, 1, 2)
        row += 1

        intraday_liq = self.position.get("intraday_liquidation_price", 0)
        overnight_liq = self.position.get("overnight_liquidation_price", 0)

        if intraday_liq:
            intraday_label = QLabel("Intraday (est.):")
            intraday_label.setStyleSheet("font-weight: bold;")
            intraday_value = QLabel(self._format_price(intraday_liq))
            details_layout.addWidget(intraday_label, row, 0)
            details_layout.addWidget(intraday_value, row, 1)
            row += 1

        if overnight_liq:
            overnight_label = QLabel("Overnight (est.):")
            overnight_label.setStyleSheet("font-weight: bold;")
            overnight_value = QLabel(self._format_price(overnight_liq))
            details_layout.addWidget(overnight_label, row, 0)
            details_layout.addWidget(overnight_value, row, 1)
            row += 1

        # Expiry if present
        expiry = self.position.get("expiry", None)
        if expiry:
            expiry_label = QLabel("Expiry:")
            expiry_label.setStyleSheet("font-weight: bold;")
            expiry_value = QLabel(str(expiry))
            details_layout.addWidget(expiry_label, row, 0)
            details_layout.addWidget(expiry_value, row, 1)

        layout.addWidget(details_widget)

        # Risk Management section
        risk_section = self._build_risk_management_section()
        if risk_section:
            layout.addWidget(risk_section)

        # Action buttons
        layout.addStretch()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        close_btn = QPushButton("Close Position")
        close_btn.setStyleSheet(self._button_style("primary"))
        close_btn.clicked.connect(self._on_close_position_clicked)
        buttons_layout.addWidget(close_btn)

        close_all_btn = QPushButton("Close All Positions")
        close_all_btn.setStyleSheet(self._button_style("secondary"))
        close_all_btn.clicked.connect(self._on_close_all_clicked)
        buttons_layout.addWidget(close_all_btn)

        done_btn = QPushButton("Done")
        done_btn.setStyleSheet(self._button_style("tertiary"))
        done_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(done_btn)

        layout.addLayout(buttons_layout)

    def _build_risk_management_section(self) -> Optional[QWidget]:
        """Build risk management controls (TP/SL/trailing stop)."""
        tp = self.position.get("take_profit")
        sl = self.position.get("stop_loss")
        trailing_enabled = self.position.get("trailing_stop_enabled", False)

        if not (tp or sl or trailing_enabled):
            return None

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        title = QLabel("Risk Management")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        risk_layout = QGridLayout()
        risk_layout.setSpacing(10)

        row = 0
        if tp:
            tp_label = QLabel("Take Profit:")
            tp_value = QLabel(self._format_price(tp))
            risk_layout.addWidget(tp_label, row, 0)
            risk_layout.addWidget(tp_value, row, 1)
            row += 1

        if sl:
            sl_label = QLabel("Stop Loss:")
            sl_value = QLabel(self._format_price(sl))
            risk_layout.addWidget(sl_label, row, 0)
            risk_layout.addWidget(sl_value, row, 1)
            row += 1

        if trailing_enabled:
            trailing_label = QLabel("Trailing Stop:")
            trailing_distance = self.position.get("trailing_stop_distance")
            trailing_percent = self.position.get("trailing_stop_percent")
            if trailing_distance:
                trailing_text = f"±${trailing_distance:.2f}"
            elif trailing_percent:
                trailing_text = f"±{trailing_percent:.2f}%"
            else:
                trailing_text = "Enabled"
            trailing_value = QLabel(trailing_text)
            risk_layout.addWidget(trailing_label, row, 0)
            risk_layout.addWidget(trailing_value, row, 1)

        layout.addLayout(risk_layout)
        return widget

    def _format_side(self) -> str:
        """Format side display."""
        side = str(self.position.get("side", "")).upper()
        amount = self.position.get("amount", 0)
        return f"{side} ({amount:.6f})".rstrip("0").rstrip(".")

    def _format_amount(self) -> str:
        """Format amount display."""
        amount = self.position.get("amount", 0)
        return f"{amount:.6f}".rstrip("0").rstrip(".")

    def _format_notional(self) -> str:
        """Format notional value."""
        value = self.position.get("value", 0)
        return f"${value:,.2f}"

    def _format_price(self, price: float) -> str:
        """Format price display."""
        if price <= 0:
            return "N/A"
        return f"${price:,.2f}"

    def _side_color(self, side: str) -> str:
        """Get color for side label."""
        side_lower = str(side).lower()
        if side_lower in {"long", "buy"}:
            return "color: #32d296; font-weight: bold;"
        elif side_lower in {"short", "sell"}:
            return "color: #ef5350; font-weight: bold;"
        return ""

    def _button_style(self, button_type: str) -> str:
        """Get button style."""
        if button_type == "primary":
            return """
                QPushButton {
                    background-color: #1976d2;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """
        elif button_type == "secondary":
            return """
                QPushButton {
                    background-color: #757575;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #616161;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #f5f5f5;
                    color: #424242;
                    padding: 8px 16px;
                    border-radius: 4px;
                    border: 1px solid #e0e0e0;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """

    def _on_close_position_clicked(self):
        """Handle close position button click."""
        symbol = self.position.get("symbol", "Unknown")
        side = str(self.position.get("side", "")).upper()
        amount = self.position.get("amount", 0)

        confirm = QMessageBox.question(
            self,
            "Close Position",
            f"Close {side} {symbol} position ({amount:.6f})?\n\nThis will place a market order.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            if self.on_close_position:
                self.on_close_position(self.position)
            self.accept()

    def _on_close_all_clicked(self):
        """Handle close all positions button click."""
        confirm = QMessageBox.question(
            self,
            "Close All Positions",
            "Close ALL open positions?\n\nThis will place market orders to close each position.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            if self.on_close_all:
                self.on_close_all()
            self.accept()
