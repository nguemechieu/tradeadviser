import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QProgressBar,
    QLabel
)

from PySide6.QtCore import Signal, Qt, QTimer


class SystemConsole(QWidget):

    log_signal = Signal(str)
    screenshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("System Console")

        self.layout = QVBoxLayout()
        
        # Loading status bar
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.progress_bar)
        self.layout.addLayout(self.status_layout)

        # Console output
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            background-color: black;
            color: #00ff90;
            font-family: Consolas;
            font-size: 11pt;
        """)

        self.layout.addWidget(self.console)

        # Buttons
        btn_layout = QHBoxLayout()

        self.clear_button = QPushButton("Clear")
        self.save_button = QPushButton("Save Logs")
        self.screenshot_button = QPushButton("Screenshot")

        btn_layout.addWidget(self.clear_button)
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.screenshot_button)

        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)

        # Signals
        self.log_signal.connect(self.write_log)

        # Button actions
        self.clear_button.clicked.connect(self.clear_console)
        self.save_button.clicked.connect(self.save_logs)
        self.screenshot_button.clicked.connect(self.screenshot_requested.emit)

    # ------------------------------------------------
    # Write log to console
    # ------------------------------------------------

    def write_log(self, message):

        timestamp = datetime.now().strftime("%H:%M:%S")

        log_line = f"[{timestamp}] {message}"

        self.console.append(log_line)

    # ------------------------------------------------
    # Clear console
    # ------------------------------------------------

    def clear_console(self):

        self.console.clear()

    # ------------------------------------------------
    # Save logs
    # ------------------------------------------------

    def save_logs(self):

        with open("logs/system_console.log", "a") as f:

            f.write(self.console.toPlainText())

        self.log_signal.emit("Logs saved")

    # ------------------------------------------------
    # External logging
    # ------------------------------------------------

    def log(self, message, level=None):

        if level:
            self.log_signal.emit(f"[{level}] {message}")
            return

        self.log_signal.emit(message)

    # ------------------------------------------------
    # Loading status
    # ------------------------------------------------

    def set_loading(self, is_loading: bool, message: str = "", progress: int = 0) -> None:
        """Set loading state and display progress.
        
        Args:
            is_loading: Whether loading is active
            message: Status message to display
            progress: Progress percentage (0-100)
        """
        self.progress_bar.setVisible(is_loading)
        self.status_label.setText(message)
        
        if is_loading:
            self.progress_bar.setValue(progress)
            self.clear_button.setEnabled(False)
            self.save_button.setEnabled(False)
        else:
            self.progress_bar.setValue(0)
            self.clear_button.setEnabled(True)
            self.save_button.setEnabled(True)

    def update_loading_progress(self, progress: int) -> None:
        """Update progress bar during loading.
        
        Args:
            progress: Progress percentage (0-100)
        """
        self.progress_bar.setValue(min(100, max(0, progress)))

    def clear_loading(self) -> None:
        """Clear loading state."""
        self.set_loading(False, "")

