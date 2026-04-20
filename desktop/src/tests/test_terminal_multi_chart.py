import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QComboBox, QMainWindow, QTabWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.terminal import Terminal


class _SettingsRecorder:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class _MultiChartTerminal(QMainWindow):
    def __init__(self, symbols):
        super().__init__()
        self.controller = SimpleNamespace(symbols=list(symbols), time_frame="1h")
        self.settings = _SettingsRecorder()
        self.logger = SimpleNamespace(error=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None)
        self.system_console = SimpleNamespace(log=lambda *args, **kwargs: None)
        self.current_timeframe = "1h"
        self.candle_up_color = "#26a69a"
        self.candle_down_color = "#ef5350"
        self.show_chart_volume = False
        self.show_bid_ask_lines = True
        self._ui_shutting_down = False
        self._active_chart_widget_ref = None
        self._last_chart_request_key = None
        self.autotrade_watchlist = set()
        self.detached_tool_windows = {}
        self.training_status = {}
        self.timeframe_buttons = {}
        self.chart_tabs = QTabWidget()
        self.symbol_picker = QComboBox()
        self.symbol_picker.addItems(list(symbols))
        self._chart_refresh_requests = []
        self._orderbook_requests = 0

    def _tr(self, key, **kwargs):
        return key

    def _current_chart_symbol(self):
        return ""

    def _set_active_timeframe_button(self, _timeframe):
        return None

    def _request_active_orderbook(self):
        self._orderbook_requests += 1

    def _schedule_chart_data_refresh(self, chart):
        self._chart_refresh_requests.append((getattr(chart, "symbol", ""), getattr(chart, "timeframe", "")))

    def __getattr__(self, name):
        if name.startswith("_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _bind(fake, *names):
    for name in names:
        method = getattr(Terminal, name)
        setattr(fake, name, lambda *args, _method=method, **kwargs: _method(fake, *args, **kwargs))


def test_multi_chart_layout_opens_separate_detached_chart_windows():
    _app()
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
    terminal = _MultiChartTerminal(symbols)
    _bind(
        terminal,
        "_is_qt_object_alive",
        "_chart_tabs_ready",
        "_iter_detached_chart_pages",
        "_chart_widgets_in_page",
        "_is_multi_chart_page",
        "_normalized_chart_symbols",
        "_all_chart_widgets",
        "_multi_chart_symbols",
        "_close_multi_chart_pages",
        "_close_chart_tab",
        "_configure_chart_widget",
        "_multi_chart_layout",
    )

    calls = []

    def _open(symbol, timeframe=None, geometry=None, compact_view=False):
        window = QMainWindow()
        window.setGeometry(geometry)
        calls.append((symbol, timeframe, geometry, compact_view))
        return window

    terminal._open_or_focus_detached_chart = _open

    Terminal._multi_chart_layout(terminal)

    assert terminal.chart_tabs.count() == 0
    assert [symbol for symbol, _timeframe, _geometry, _compact_view in calls] == symbols
    assert all(timeframe == "1h" for _symbol, timeframe, _geometry, _compact_view in calls)
    assert all(compact_view is True for _symbol, _timeframe, _geometry, compact_view in calls)
    assert all(isinstance(geometry, QRect) for _symbol, _timeframe, geometry, _compact_view in calls)
    assert len({(geometry.x(), geometry.y()) for _symbol, _timeframe, geometry, _compact_view in calls}) == len(symbols)


def test_detached_chart_layouts_serialize_grouped_multi_chart_pages():
    _app()
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
    terminal = _MultiChartTerminal(symbols)
    _bind(
        terminal,
        "_is_qt_object_alive",
        "_chart_widgets_in_page",
        "_is_multi_chart_page",
        "_normalized_chart_symbols",
        "_multi_chart_window_key",
        "_build_multi_chart_page",
        "_detached_chart_windows",
        "_detached_chart_layouts",
    )

    page = Terminal._build_multi_chart_page(terminal, symbols, "1h")
    window = QMainWindow()
    window._contains_chart_page = True
    window.setCentralWidget(page)
    window.setGeometry(40, 80, 1200, 760)
    terminal.detached_tool_windows["multi"] = window

    layouts = Terminal._detached_chart_layouts(terminal)

    assert layouts == [
        {
            "timeframe": "1h",
            "x": 40,
            "y": 80,
            "width": 1200,
            "height": 760,
            "kind": "group",
            "symbols": symbols,
        }
    ]


def test_restore_detached_chart_layouts_routes_group_entries_to_group_helper():
    _app()
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]
    terminal = _MultiChartTerminal(symbols)
    terminal.settings.setValue(
        "charts/detached_layouts",
        json.dumps(
            [
                {
                    "kind": "group",
                    "symbols": symbols,
                    "timeframe": "4h",
                    "x": 25,
                    "y": 35,
                    "width": 1100,
                    "height": 720,
                }
            ]
        ),
    )
    _bind(terminal, "_restore_detached_chart_layouts", "_normalized_chart_symbols")

    calls = []
    terminal._open_or_focus_detached_chart_group = (
        lambda group_symbols, timeframe, geometry=None: calls.append((list(group_symbols), timeframe, geometry))
    )
    terminal._open_or_focus_detached_chart = lambda *args, **kwargs: None

    Terminal._restore_detached_chart_layouts(terminal)

    assert len(calls) == 1
    restored_symbols, restored_timeframe, restored_geometry = calls[0]
    assert restored_symbols == symbols
    assert restored_timeframe == "4h"
    assert isinstance(restored_geometry, QRect)
    assert restored_geometry == QRect(25, 35, 1100, 720)
