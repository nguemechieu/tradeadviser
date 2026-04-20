import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QTableWidget, QTextEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.actions.backtest_actions import (
    generate_report,
    load_backtest_history_clicked,
    refresh_backtest_window,
    show_backtest_window,
    start_backtest,
    stop_backtest,
)
from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_show_backtest_window_builds_workspace_and_wires_buttons():
    _app()
    window = QMainWindow()
    events = {"selectors": 0, "refreshes": 0, "start": 0, "load": 0, "report": 0}
    fake = SimpleNamespace(
        controller=SimpleNamespace(limit=2500),
        _get_or_create_tool_window=lambda key, title, width=0, height=0: window,
        _refresh_backtest_selectors=lambda current_window=None: events.__setitem__("selectors", events["selectors"] + 1),
        _refresh_backtest_window=lambda current_window=None, message=None: events.__setitem__("refreshes", events["refreshes"] + 1),
        _backtest_selection_changed=lambda: None,
        _tick_backtest_graph_animation=lambda current_window=None: None,
        start_backtest=lambda: events.__setitem__("start", events["start"] + 1),
        _load_backtest_history_clicked=lambda: events.__setitem__("load", events["load"] + 1),
        _generate_report=lambda: events.__setitem__("report", events["report"] + 1),
    )

    returned = show_backtest_window(fake)
    window._backtest_toggle_btn.click()
    window._backtest_load_btn.click()
    window._backtest_report_btn.click()

    assert returned is window
    assert window._backtest_history_limit.value() == 2500
    assert window._backtest_tabs.count() == 4
    assert "Profit Factor" in window._backtest_metric_labels
    assert "Closed Trades" in window._backtest_metric_labels
    assert events["selectors"] == 1
    assert events["refreshes"] == 1
    assert events["start"] == 1
    assert events["load"] == 1
    assert events["report"] == 1


def test_terminal_exposes_load_backtest_history_handler():
    assert callable(getattr(Terminal, "_load_backtest_history_clicked", None))


def test_refresh_backtest_window_renders_results_and_metrics():
    _app()

    class _Curve:
        def __init__(self):
            self.calls = []

        def setData(self, *args):
            self.calls.append(args)

    window = SimpleNamespace(
        _backtest_status=QLabel(),
        _backtest_summary=QLabel(),
        _backtest_results=QTableWidget(),
        _backtest_setting_labels={name: QLabel() for name in ["Expert", "Symbol", "Period", "Model", "Spread", "Initial Deposit", "Target Bars", "Bars", "Range"]},
        _backtest_metric_labels={
            name: QLabel()
            for name in [
                "Total Net Profit",
                "Profit Factor",
                "Sharpe Ratio",
                "Trades",
                "Closed Trades",
                "Win Rate",
                "Max Drawdown",
                "Final Equity",
            ]
        },
        _backtest_graph_curve=_Curve(),
        _backtest_graph_animation_curve=_Curve(),
        _backtest_report=QTextEdit(),
        _backtest_journal=QTextEdit(),
        _backtest_toggle_btn=QPushButton(),
        _backtest_load_btn=QPushButton(),
        _backtest_report_btn=QPushButton(),
        _backtest_symbol_picker=SimpleNamespace(currentText=lambda: "EUR/USD", setEnabled=lambda value: None),
        _backtest_strategy_picker=SimpleNamespace(currentText=lambda: "Trend Following", setEnabled=lambda value: None),
        _backtest_timeframe_picker=SimpleNamespace(currentText=lambda: "1h", setEnabled=lambda value: None),
        _backtest_start_date=SimpleNamespace(setEnabled=lambda value: None),
        _backtest_end_date=SimpleNamespace(setEnabled=lambda value: None),
        _backtest_history_limit=SimpleNamespace(setEnabled=lambda value: None),
    )
    rows = []
    fake = SimpleNamespace(
        detached_tool_windows={"backtesting_workspace": window},
        controller=SimpleNamespace(spread_pct=0.12, initial_capital=5000, limit=1000, strategy_name="Trend Following", config=SimpleNamespace(strategy="Trend Following")),
        _backtest_context={"symbol": "EUR/USD", "timeframe": "1h", "strategy_name": "Trend Following", "data": [1, 2, 3]},
        _backtest_running=False,
        _backtest_stop_requested=False,
        _backtest_history_task=None,
        results=pd.DataFrame([{"timestamp": 1, "symbol": "EUR/USD", "side": "BUY", "type": "ENTRY", "price": 1.1, "amount": 1, "pnl": 10.0, "equity": 5010, "reason": "entry"}]),
        backtest_report={
            "total_profit": 10.0,
            "profit_factor": 2.0,
            "sharpe_ratio": 1.5,
            "total_trades": 1,
            "closed_trades": 1,
            "win_rate": 1.0,
            "max_drawdown": 2.5,
            "final_equity": 5010.0,
        },
        backtest_engine=SimpleNamespace(equity_curve=[5000, 5010]),
        _format_backtest_range=lambda data: "2026-01-01 -> 2026-01-10",
        _backtest_requested_range_text=lambda window=None, context=None: "2026-01-01 -> 2026-01-10",
        _backtest_requested_limit=lambda window=None, context=None, fallback=None: 1000,
        _populate_backtest_results_table=lambda table, trades_df: rows.append((table, trades_df)),
        _stop_backtest_graph_animation=lambda current_window=None, clear=False: None,
        _start_backtest_graph_animation=lambda current_window=None: None,
        _tick_backtest_graph_animation=lambda current_window=None: None,
        _build_backtest_report_text=lambda context, report, results_df: "Backtest summary",
        _backtest_journal_lines=["entry"],
    )

    refresh_backtest_window(fake, message="Ready")

    assert window._backtest_status.text() == "Ready"
    assert "Expert: Trend Following" in window._backtest_summary.text()
    assert window._backtest_metric_labels["Total Net Profit"].text() == "10.00"
    assert window._backtest_metric_labels["Profit Factor"].text() == "2.00"
    assert window._backtest_metric_labels["Sharpe Ratio"].text() == "1.50"
    assert window._backtest_metric_labels["Trades"].text() == "1"
    assert window._backtest_metric_labels["Closed Trades"].text() == "1"
    assert window._backtest_metric_labels["Win Rate"].text() == "100.00%"
    assert window._backtest_report.toPlainText() == "Backtest summary"
    assert rows and rows[0][1] is fake.results
    assert window._backtest_graph_curve.calls[-1] == ([0, 1], [5000, 5010])


def test_start_backtest_schedules_runner_after_showing_window():
    events = {"shown": 0, "tasks": []}

    async def _prepare_and_run_backtest():
        return None

    def _create_task(coro, name):
        events["tasks"].append((coro, name))
        coro.close()
        return SimpleNamespace(done=lambda: False)

    fake = SimpleNamespace(
        _backtest_running=False,
        _show_backtest_window=lambda: events.__setitem__("shown", events["shown"] + 1),
        _prepare_and_run_backtest=_prepare_and_run_backtest,
        controller=SimpleNamespace(_create_task=_create_task),
        system_console=SimpleNamespace(log=lambda *_args, **_kwargs: None),
        _append_backtest_journal=lambda *_args, **_kwargs: None,
        _refresh_backtest_window=lambda *_args, **_kwargs: None,
    )

    start_backtest(fake)

    assert events["shown"] == 1
    assert len(events["tasks"]) == 1
    assert events["tasks"][0][1] == "backtest_run"


def test_load_backtest_history_clicked_schedules_runner():
    events = {"shown": 0, "messages": [], "tasks": []}

    async def _runner(window=None, force=True):
        return None

    def _create_task(coro, name):
        events["tasks"].append((coro, name))
        coro.close()
        return SimpleNamespace(done=lambda: False)

    task = SimpleNamespace(done=lambda: True)
    fake = SimpleNamespace(
        _backtest_running=False,
        detached_tool_windows={"backtesting_workspace": object()},
        _show_backtest_window=lambda: events.__setitem__("shown", events["shown"] + 1),
        _refresh_backtest_window=lambda message=None, **_kwargs: events["messages"].append(message),
        _load_backtest_history_runner=_runner,
        _backtest_history_task=task,
        controller=SimpleNamespace(_create_task=_create_task),
    )

    load_backtest_history_clicked(fake)

    assert events["shown"] == 0
    assert events["messages"] == ["Loading exchange history for backtesting..."]
    assert len(events["tasks"]) == 1
    assert events["tasks"][0][1] == "backtest_history_load"


def test_stop_backtest_marks_stop_requested_and_logs():
    logs = []
    journals = []
    messages = []
    stop_state = {"called": 0}
    fake = SimpleNamespace(
        _backtest_running=True,
        _backtest_stop_requested=False,
        _backtest_stop_event=SimpleNamespace(set=lambda: stop_state.__setitem__("called", stop_state["called"] + 1)),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        _append_backtest_journal=lambda message, level="INFO": journals.append((message, level)),
        _refresh_backtest_window=lambda message=None: messages.append(message),
    )

    stop_backtest(fake)

    assert fake._backtest_stop_requested is True
    assert stop_state["called"] == 1
    assert logs == [("Backtest stop requested.", "INFO")]
    assert journals == [("Backtest stop requested.", "WARN")]
    assert messages == ["Backtest stop requested..."]


def test_generate_report_exports_report_and_updates_state():
    logs = []
    journals = []
    messages = []
    settings_writes = []

    class _Generator:
        def __init__(self, trades, equity_history, output_dir):
            self.output_dir = output_dir

        def export_pdf(self, path):
            Path(path).write_text("pdf", encoding="utf-8")
            return path

        def export_excel(self, path):
            Path(path).write_text("xlsx", encoding="utf-8")
            return path

        def generate(self):
            return {"total_profit": 12.0}

    fake = SimpleNamespace(
        results=pd.DataFrame([{"symbol": "EUR/USD"}]),
        settings=SimpleNamespace(
            value=lambda key, default=None: default,
            setValue=lambda key, value: settings_writes.append((key, value)),
        ),
        _backtest_context={"symbol": "EUR/USD", "timeframe": "1h"},
        backtest_engine=SimpleNamespace(equity_curve=[1000, 1012]),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        _append_backtest_journal=lambda message, level="INFO": journals.append((message, level)),
        _refresh_backtest_window=lambda message=None: messages.append(message),
    )

    with TemporaryDirectory() as tmpdir:
        with patch("frontend.ui.actions.backtest_actions.QFileDialog.getExistingDirectory", return_value=tmpdir):
            with patch("frontend.ui.actions.backtest_actions.ReportGenerator", _Generator):
                generate_report(fake)

        exported = list(Path(tmpdir).iterdir())

    assert fake.backtest_report == {"total_profit": 12.0}
    assert settings_writes == [("backtest/report_dir", tmpdir)]
    assert len(exported) == 2
    assert any(path.suffix == ".pdf" for path in exported)
    assert any(path.suffix == ".xlsx" for path in exported)
    assert logs and "Backtest report generated:" in logs[0][0]
    assert journals and journals[0][1] == "INFO"
    assert messages == ["Backtest report generated."]
