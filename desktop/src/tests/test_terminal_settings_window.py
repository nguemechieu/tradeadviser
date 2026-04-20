import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui import terminal as terminal_module


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_wrap_tab_in_scroll_area_keeps_form_widget_inside_scroll_container():
    _app()
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.addWidget(QLabel("General settings"))

    scroll = terminal_module._hotfix_wrap_tab_in_scroll_area(content, minimum_width=600)

    assert isinstance(scroll, QScrollArea)
    assert scroll.widgetResizable() is True
    assert scroll.widget() is not None
    assert scroll.widget().minimumWidth() == 600
    assert scroll.widget().layout().itemAt(0).widget() is content
