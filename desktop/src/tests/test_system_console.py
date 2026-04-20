import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from frontend.console.system_console import SystemConsole


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_screenshot_button_emits_request_signal():
    _app()
    console = SystemConsole()
    requested = []

    console.screenshot_requested.connect(lambda: requested.append(True))
    console.screenshot_button.click()

    assert requested == [True]
