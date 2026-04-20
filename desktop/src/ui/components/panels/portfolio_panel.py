from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem


class PortfolioPanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.table = QTableWidget(10, 4)

        self.table.setHorizontalHeaderLabels([
            "Symbol",
            "Quantity",
            "Entry",
            "PnL"
        ])

        layout.addWidget(self.table)

        self.setLayout(layout)

    # -----------------------------------

    def update_portfolio(self, positions):
        for i, pos in enumerate(positions):
            self.table.setItem(i, 0, QTableWidgetItem(pos["symbol"]))
            self.table.setItem(i, 1, QTableWidgetItem(str(pos["qty"])))
            self.table.setItem(i, 2, QTableWidgetItem(str(pos["entry"])))
            self.table.setItem(i, 3, QTableWidgetItem(str(pos["pnl"])))
