import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.actions.window_actions import (
    DOCUMENTATION_HTML,
    open_docs,
    open_logs,
    open_ml_monitor,
    open_text_window,
    sync_logs_window,
)
from frontend.ui.panels.system_panels import AI_MONITOR_HEADERS


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_sync_logs_window_copies_console_text():
    _app()
    editor = QTextEdit()
    editor.setPlainText("old")
    fake = SimpleNamespace(
        system_console=SimpleNamespace(console=SimpleNamespace(toPlainText=lambda: "new log line")),
    )

    sync_logs_window(fake, editor)

    assert editor.toPlainText() == "new log line"


def test_open_logs_creates_editor_and_timer():
    _app()
    window = QMainWindow()
    refreshed = {"count": 0}
    console = QTextEdit()
    console.setStyleSheet("color: #fff;")
    console.setPlainText("system text")
    fake = SimpleNamespace(
        system_console=SimpleNamespace(console=console),
        _get_or_create_tool_window=lambda key, title, width=0, height=0: window,
        _sync_logs_window=lambda editor: refreshed.__setitem__("count", refreshed["count"] + 1) or editor.setPlainText("system text"),
    )

    returned = open_logs(fake)

    assert returned is window
    assert window._logs_editor.toPlainText() == "system text"
    assert window._logs_editor.isReadOnly() is True
    assert hasattr(window, "_sync_timer")
    assert refreshed["count"] == 1


def test_open_ml_monitor_creates_table_and_forces_refresh():
    _app()
    window = QMainWindow()
    refreshes = []
    configured = {"count": 0}
    fake = SimpleNamespace(
        _get_or_create_tool_window=lambda key, title, width=0, height=0: window,
        _configure_monitor_table=lambda table: configured.__setitem__("count", configured["count"] + 1),
        _refresh_ai_monitor_table=lambda table, force=False: refreshes.append((table, force)),
    )

    returned = open_ml_monitor(fake)

    assert returned is window
    assert window._monitor_table.columnCount() == len(AI_MONITOR_HEADERS)
    assert window._monitor_table.horizontalHeaderItem(0).text() == AI_MONITOR_HEADERS[0]
    assert configured["count"] == 1
    assert refreshes == [(window._monitor_table, True)]
    assert hasattr(window, "_sync_timer")


def test_open_text_window_creates_browser_and_sets_html():
    _app()
    window = QMainWindow()
    fake = SimpleNamespace(
        _get_or_create_tool_window=lambda key, title, width=0, height=0: window,
    )

    returned = open_text_window(fake, "help", "Help", "<h1>Example</h1>", width=800, height=500)

    assert returned is window
    assert window._browser is window.centralWidget()
    assert "Example" in window._browser.toHtml()


def test_open_docs_delegates_to_text_window_with_documentation_payload():
    captured = {}
    fake = SimpleNamespace(
        _open_text_window=lambda key, title, html, width=0, height=0: captured.update(
            {"key": key, "title": title, "html": html, "width": width, "height": height}
        )
    )

    open_docs(fake)

    assert captured["key"] == "help_documentation"
    assert captured["title"] == "Documentation"
    assert captured["html"] == DOCUMENTATION_HTML
    assert captured["width"] == 940
    assert captured["height"] == 760
