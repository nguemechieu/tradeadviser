from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem


class TradesPanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.table = QTableWidget(50, 3)

        self.table.setHorizontalHeaderLabels([
            "Time",
            "Price",
            "Size"
        ])

        layout.addWidget(self.table)

        self.setLayout(layout)

    # -------------------------------------

    def add_trade(self, time, price, size):
        row = 0

        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(str(time)))
        self.table.setItem(row, 1, QTableWidgetItem(str(price)))
        self.table.setItem(row, 2, QTableWidgetItem(str(size)))
