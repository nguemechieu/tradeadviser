from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):

    def __init__(self, controller):

        super().__init__()

        self.controller = controller

        self.setWindowTitle("TradeAdviser")

        self._create_menu()

    def _create_menu(self):

        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        login_action = QAction("Login", self)

        login_action.triggered.connect(self.controller.show_login_dialog)

        file_menu.addAction(login_action)
