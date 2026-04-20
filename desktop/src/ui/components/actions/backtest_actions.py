import asyncio
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backtesting.report_generator import ReportGenerator


def show_backtest_window(terminal):
    window = terminal._get_or_create_tool_window(
        "backtesting_workspace",
        "Strategy Tester",
        width=1180,
        height=760,
    )

    if getattr(window, "_backtest_container", None) is None:
        container = QWidget()
        layout = QVBoxLayout(container)

        status = QLabel("Strategy tester ready.")
        status.setStyleSheet("color: #e6edf7; font-weight: 700; font-size: 14px;")
        layout.addWidget(status)

        summary = QLabel("-")
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #9fb0c7;")
        layout.addWidget(summary)

        selection_frame = QFrame()
        selection_frame.setStyleSheet(
            "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
            "QLabel { color: #d7dfeb; font-weight: 700; }"
            "QComboBox, QDateEdit, QDoubleSpinBox { background-color: #0b1220; color: #f4f8ff; border: 1px solid #2a3d5c; border-radius: 6px; padding: 6px 10px; min-width: 180px; }"
        )
        selection_layout = QGridLayout(selection_frame)
        selection_layout.setContentsMargins(14, 12, 14, 12)
        selection_layout.setHorizontalSpacing(16)
        selection_layout.setVerticalSpacing(8)

        symbol_picker = QComboBox()
        symbol_picker.setEditable(False)
        strategy_picker = QComboBox()
        strategy_picker.setEditable(False)
        timeframe_picker = QComboBox()
        timeframe_picker.setEditable(False)
        start_date_edit = QDateEdit()
        start_date_edit.setCalendarPopup(True)
        start_date_edit.setDisplayFormat("yyyy-MM-dd")
        start_date_edit.setDate(QDate.currentDate().addDays(-90))
        end_date_edit = QDateEdit()
        end_date_edit.setCalendarPopup(True)
        end_date_edit.setDisplayFormat("yyyy-MM-dd")
        end_date_edit.setDate(QDate.currentDate())
        history_limit = QDoubleSpinBox()
        history_limit.setDecimals(0)
        history_limit.setRange(100, float(getattr(terminal.controller, "MAX_BACKTEST_HISTORY_LIMIT", 1000000)))
        history_limit.setSingleStep(500)
        history_limit.setSuffix(" bars")
        history_limit.setValue(float(getattr(terminal.controller, "limit", 50000) or 50000))
        history_limit.setToolTip(
            "Maximum number of bars to use for the backtest. The newest bars inside the selected date range are used, "
            "and deep backtests can load much more history than the live chart cache."
        )

        selection_layout.addWidget(QLabel("Backtest Symbol"), 0, 0)
        selection_layout.addWidget(symbol_picker, 0, 1)
        selection_layout.addWidget(QLabel("Backtest Strategy"), 0, 2)
        selection_layout.addWidget(strategy_picker, 0, 3)
        selection_layout.addWidget(QLabel("Timeframe"), 1, 0)
        selection_layout.addWidget(timeframe_picker, 1, 1)
        selection_layout.addWidget(QLabel("Start Date"), 1, 2)
        selection_layout.addWidget(start_date_edit, 1, 3)
        selection_layout.addWidget(QLabel("End Date"), 2, 0)
        selection_layout.addWidget(end_date_edit, 2, 1)
        selection_layout.addWidget(QLabel("Target Bars"), 2, 2)
        selection_layout.addWidget(history_limit, 2, 3)
        layout.addWidget(selection_frame)

        settings_frame = QFrame()
        settings_frame.setStyleSheet(
            "QFrame { background-color: #101b2d; border: 1px solid #24344f; border-radius: 10px; }"
            "QLabel { color: #d7dfeb; }"
        )
        settings_layout = QGridLayout(settings_frame)
        settings_layout.setContentsMargins(14, 12, 14, 12)
        settings_layout.setHorizontalSpacing(16)
        settings_layout.setVerticalSpacing(8)

        setting_names = [
            "Expert",
            "Symbol",
            "Period",
            "Model",
            "Spread",
            "Initial Deposit",
            "Target Bars",
            "Bars",
            "Range",
        ]
        setting_labels = {}
        for index, name in enumerate(setting_names):
            title = QLabel(name)
            title.setStyleSheet("color: #8fa3bf; font-weight: 700;")
            value = QLabel("-")
            value.setStyleSheet("color: #f4f8ff; font-weight: 600;")
            row = index // 4
            col = (index % 4) * 2
            settings_layout.addWidget(title, row, col)
            settings_layout.addWidget(value, row, col + 1)
            setting_labels[name] = value
        layout.addWidget(settings_frame)

        controls = QHBoxLayout()
        toggle_btn = QPushButton("Start Backtest")
        load_btn = QPushButton("Load Exchange Data")
        report_btn = QPushButton("Generate Report")
        toggle_btn.clicked.connect(terminal.start_backtest)
        load_btn.clicked.connect(lambda: terminal._load_backtest_history_clicked())
        report_btn.clicked.connect(terminal._generate_report)
        controls.addWidget(toggle_btn)
        controls.addWidget(load_btn)
        controls.addWidget(report_btn)
        controls.addStretch()
        layout.addLayout(controls)

        metrics_frame = QFrame()
        metrics_frame.setStyleSheet(
            "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
        )
        metrics_layout = QGridLayout(metrics_frame)
        metrics_layout.setContentsMargins(12, 10, 12, 10)
        metrics_layout.setHorizontalSpacing(18)
        metrics_layout.setVerticalSpacing(6)

        metric_names = [
            "Total Net Profit",
            "Profit Factor",
            "Sharpe Ratio",
            "Trades",
            "Closed Trades",
            "Win Rate",
            "Max Drawdown",
            "Final Equity",
        ]
        metric_labels = {}
        for index, name in enumerate(metric_names):
            title = QLabel(name)
            title.setStyleSheet("color: #8fa3bf; font-weight: 700;")
            value = QLabel("-")
            value.setStyleSheet("color: #f5fbff; font-weight: 700; font-size: 16px;")
            row = (index // 4) * 2
            column = index % 4
            metrics_layout.addWidget(title, row, column)
            metrics_layout.addWidget(value, row + 1, column)
            metric_labels[name] = value
        layout.addWidget(metrics_frame)

        tabs = QTabWidget()

        results_table = QTableWidget()
        results_table.setAlternatingRowColors(True)
        tabs.addTab(results_table, "Results")

        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)
        graph_layout.setContentsMargins(8, 8, 8, 8)
        graph_plot = pg.PlotWidget()
        graph_plot.setBackground("#0b1220")
        graph_plot.showGrid(x=True, y=True, alpha=0.2)
        graph_plot.setLabel("left", "Equity")
        graph_plot.setLabel("bottom", "Bar")
        graph_curve = graph_plot.plot(pen=pg.mkPen("#2a7fff", width=2))
        graph_animation_curve = graph_plot.plot(
            pen=pg.mkPen("#4fd1c5", width=2, style=Qt.PenStyle.DashLine)
        )
        graph_layout.addWidget(graph_plot)
        tabs.addTab(graph_tab, "Graph")

        report_text = QTextEdit()
        report_text.setReadOnly(True)
        report_text.setStyleSheet(
            "QTextEdit { background-color: #0b1220; color: #d7dfeb; font-family: Consolas; }"
        )
        tabs.addTab(report_text, "Report")

        journal_text = QTextEdit()
        journal_text.setReadOnly(True)
        journal_text.setStyleSheet(
            "QTextEdit { background-color: #0b1220; color: #d7dfeb; font-family: Consolas; }"
        )
        tabs.addTab(journal_text, "Journal")

        layout.addWidget(tabs)

        window.setCentralWidget(container)
        window._backtest_container = container
        window._backtest_status = status
        window._backtest_summary = summary
        window._backtest_symbol_picker = symbol_picker
        window._backtest_strategy_picker = strategy_picker
        window._backtest_timeframe_picker = timeframe_picker
        window._backtest_start_date = start_date_edit
        window._backtest_end_date = end_date_edit
        window._backtest_history_limit = history_limit
        window._backtest_setting_labels = setting_labels
        window._backtest_metric_labels = metric_labels
        window._backtest_tabs = tabs
        window._backtest_results = results_table
        window._backtest_graph_plot = graph_plot
        window._backtest_graph_curve = graph_curve
        window._backtest_graph_animation_curve = graph_animation_curve
        window._backtest_report = report_text
        window._backtest_journal = journal_text
        window._backtest_toggle_btn = toggle_btn
        window._backtest_load_btn = load_btn
        window._backtest_report_btn = report_btn
        window._backtest_graph_phase = 0.0
        window._backtest_graph_timer = QTimer(window)
        window._backtest_graph_timer.setInterval(180)
        window._backtest_graph_timer.timeout.connect(lambda: terminal._tick_backtest_graph_animation(window))
        symbol_picker.currentTextChanged.connect(lambda _text: terminal._backtest_selection_changed())
        strategy_picker.currentTextChanged.connect(lambda _text: terminal._backtest_selection_changed())
        timeframe_picker.currentTextChanged.connect(lambda _text: terminal._backtest_selection_changed())
        start_date_edit.dateChanged.connect(lambda _date: terminal._backtest_selection_changed())
        end_date_edit.dateChanged.connect(lambda _date: terminal._backtest_selection_changed())
        history_limit.valueChanged.connect(lambda _value: terminal._backtest_selection_changed())

    terminal._refresh_backtest_selectors(window)
    terminal._refresh_backtest_window(window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def refresh_backtest_window(terminal, window=None, message=None):
    window = window or terminal.detached_tool_windows.get("backtesting_workspace")
    if window is None:
        return

    status = getattr(window, "_backtest_status", None)
    summary = getattr(window, "_backtest_summary", None)
    results = getattr(window, "_backtest_results", None)
    settings = getattr(window, "_backtest_setting_labels", None)
    metrics = getattr(window, "_backtest_metric_labels", None)
    graph_curve = getattr(window, "_backtest_graph_curve", None)
    report_view = getattr(window, "_backtest_report", None)
    journal_view = getattr(window, "_backtest_journal", None)
    toggle_btn = getattr(window, "_backtest_toggle_btn", None)
    load_btn = getattr(window, "_backtest_load_btn", None)
    report_btn = getattr(window, "_backtest_report_btn", None)
    symbol_picker = getattr(window, "_backtest_symbol_picker", None)
    strategy_picker = getattr(window, "_backtest_strategy_picker", None)
    timeframe_picker = getattr(window, "_backtest_timeframe_picker", None)
    start_date_edit = getattr(window, "_backtest_start_date", None)
    end_date_edit = getattr(window, "_backtest_end_date", None)
    history_limit_widget = getattr(window, "_backtest_history_limit", None)
    graph_animation_curve = getattr(window, "_backtest_graph_animation_curve", None)
    if (
        status is None
        or summary is None
        or results is None
        or settings is None
        or metrics is None
        or graph_curve is None
        or report_view is None
        or journal_view is None
    ):
        return

    backtest_context = getattr(terminal, "_backtest_context", {}) or {}
    dataset = backtest_context.get("data")
    candle_count = len(dataset) if hasattr(dataset, "__len__") else 0
    has_engine = hasattr(terminal, "backtest_engine")
    selected_symbol = str(symbol_picker.currentText()).strip() if symbol_picker is not None else ""
    selected_strategy = str(strategy_picker.currentText()).strip() if strategy_picker is not None else ""
    symbol = backtest_context.get("symbol", selected_symbol or "-")
    timeframe = backtest_context.get("timeframe", "-")
    strategy_name = (
        backtest_context.get("strategy_name")
        or selected_strategy
        or getattr(terminal.controller, "strategy_name", None)
        or getattr(getattr(terminal.controller, "config", None), "strategy", "Trend Following")
    )
    spread_pct = float(getattr(terminal.controller, "spread_pct", 0.0) or 0.0)
    initial_deposit = float(getattr(terminal.controller, "initial_capital", 10000) or 10000)
    range_text = terminal._format_backtest_range(dataset)
    requested_range_text = terminal._backtest_requested_range_text(window, backtest_context) or range_text
    requested_history_limit = terminal._backtest_requested_limit(
        window=window,
        context=backtest_context,
        fallback=getattr(terminal.controller, "limit", 50000),
    )
    running = bool(getattr(terminal, "_backtest_running", False))
    stop_requested = bool(getattr(terminal, "_backtest_stop_requested", False))
    history_loading = bool(getattr(getattr(terminal, "_backtest_history_task", None), "done", lambda: True)() is False)

    if toggle_btn is not None:
        toggle_btn.setText("Stop Backtest" if running else "Start Backtest")
    if load_btn is not None:
        load_btn.setEnabled((not running) and (not history_loading))
        load_btn.setText("Loading Exchange Data..." if history_loading else "Load Exchange Data")
    if report_btn is not None:
        report_btn.setEnabled((not running) and getattr(terminal, "results", None) is not None)
    if symbol_picker is not None:
        symbol_picker.setEnabled(not running)
    if strategy_picker is not None:
        strategy_picker.setEnabled(not running)
    if timeframe_picker is not None:
        timeframe_picker.setEnabled(not running)
    if start_date_edit is not None:
        start_date_edit.setEnabled(not running)
    if end_date_edit is not None:
        end_date_edit.setEnabled(not running)
    if history_limit_widget is not None:
        history_limit_widget.setEnabled(not running)

    default_message = (
        "Backtest stop requested..."
        if stop_requested
        else ("Backtest running..." if running else ("Strategy tester ready." if has_engine else "Backtest engine not initialized."))
    )
    status.setText(message or default_message)
    summary.setText(
        f"Expert: {strategy_name} | Symbol: {symbol} | Period: {timeframe} | Bars: {candle_count} / {requested_history_limit} | Dates: {requested_range_text}"
    )

    settings["Expert"].setText(str(strategy_name))
    settings["Symbol"].setText(str(symbol))
    settings["Period"].setText(str(timeframe))
    settings["Model"].setText("Bar-close simulation")
    settings["Spread"].setText(f"{spread_pct:.4f}%")
    settings["Initial Deposit"].setText(f"{initial_deposit:.2f}")
    settings["Target Bars"].setText(str(int(requested_history_limit)))
    settings["Bars"].setText(str(candle_count))
    settings["Range"].setText(range_text)

    results_df = getattr(terminal, "results", None)
    report = getattr(terminal, "backtest_report", None)
    equity_curve = getattr(getattr(terminal, "backtest_engine", None), "equity_curve", []) or []

    if results_df is None:
        terminal._populate_backtest_results_table(results, None)
        if running:
            terminal._start_backtest_graph_animation(window)
            terminal._tick_backtest_graph_animation(window)
        else:
            terminal._stop_backtest_graph_animation(window, clear=True)
        for label in metrics.values():
            label.setText("-")
        report_view.setPlainText("No backtest results yet.")
        journal_view.setPlainText("\n".join(getattr(terminal, "_backtest_journal_lines", []) or []))
        journal_view.moveCursor(QTextCursor.MoveOperation.End)
        return

    try:
        terminal._populate_backtest_results_table(results, results_df)
        terminal._stop_backtest_graph_animation(window)

        if not isinstance(report, dict):
            report = ReportGenerator(
                trades=results_df,
                equity_history=equity_curve,
            ).generate()

        metrics["Total Net Profit"].setText(f"{float(report.get('total_profit', 0.0) or 0.0):.2f}")
        metrics["Profit Factor"].setText(f"{float(report.get('profit_factor', 0.0) or 0.0):.2f}")
        metrics["Sharpe Ratio"].setText(f"{float(report.get('sharpe_ratio', 0.0) or 0.0):.2f}")
        metrics["Trades"].setText(str(int(report.get('total_trades', 0) or 0)))
        metrics["Closed Trades"].setText(str(int(report.get('closed_trades', 0) or 0)))
        metrics["Win Rate"].setText(f"{float(report.get('win_rate', 0.0) or 0.0) * 100.0:.2f}%")
        metrics["Max Drawdown"].setText(f"{float(report.get('max_drawdown', 0.0) or 0.0):.2f}")
        metrics["Final Equity"].setText(f"{float(report.get('final_equity', initial_deposit) or initial_deposit):.2f}")

        if equity_curve:
            graph_curve.setData(list(range(len(equity_curve))), equity_curve)
        else:
            graph_curve.setData([])
        if graph_animation_curve is not None:
            graph_animation_curve.setData([])
        report_view.setPlainText(terminal._build_backtest_report_text(backtest_context, report, results_df))
        journal_view.setPlainText("\n".join(getattr(terminal, "_backtest_journal_lines", []) or []))
        journal_view.moveCursor(QTextCursor.MoveOperation.End)
    except Exception as exc:
        report_view.setPlainText(f"Unable to render backtest results: {exc}")


def load_backtest_history_clicked(terminal):
    if getattr(terminal, "_backtest_running", False):
        terminal._refresh_backtest_window(message="Stop the active backtest before loading a new history range.")
        return

    window = getattr(terminal, "detached_tool_windows", {}).get("backtesting_workspace")
    if window is None:
        terminal._show_backtest_window()
        window = getattr(terminal, "detached_tool_windows", {}).get("backtesting_workspace")

    current_task = getattr(terminal, "_backtest_history_task", None)
    if current_task is not None and not current_task.done():
        terminal._refresh_backtest_window(message="Exchange history load is already in progress.")
        return

    terminal._refresh_backtest_window(message="Loading exchange history for backtesting...")
    runner = terminal._load_backtest_history_runner(window=window, force=True)
    create_task = getattr(terminal.controller, "_create_task", None)
    if callable(create_task):
        terminal._backtest_history_task = create_task(runner, "backtest_history_load")
    else:
        terminal._backtest_history_task = asyncio.create_task(runner)


def start_backtest(terminal):
    if getattr(terminal, "_backtest_running", False):
        terminal.stop_backtest()
        return

    try:
        terminal._show_backtest_window()
        runner = terminal._prepare_and_run_backtest()
        create_task = getattr(terminal.controller, "_create_task", None)
        if callable(create_task):
            terminal._backtest_task = create_task(runner, "backtest_run")
        else:
            terminal._backtest_task = asyncio.create_task(runner)
    except Exception as exc:
        terminal._backtest_running = False
        terminal._backtest_stop_event = None
        terminal.system_console.log(f"Backtest failed to start: {exc}", "ERROR")
        terminal._append_backtest_journal(f"Backtest failed to start: {exc}", "ERROR")
        terminal._refresh_backtest_window(message=f"Backtest failed to start: {exc}")


def stop_backtest(terminal):
    if not getattr(terminal, "_backtest_running", False):
        terminal._refresh_backtest_window(message="No backtest is currently running.")
        return

    terminal._backtest_stop_requested = True
    stop_event = getattr(terminal, "_backtest_stop_event", None)
    if stop_event is not None:
        stop_event.set()
    terminal.system_console.log("Backtest stop requested.", "INFO")
    terminal._append_backtest_journal("Backtest stop requested.", "WARN")
    terminal._refresh_backtest_window(message="Backtest stop requested...")


def generate_report(terminal):
    try:
        trades = getattr(terminal, "results", None)
        if trades is None:
            raise RuntimeError("Run a backtest before generating a report")

        default_dir = str(
            terminal.settings.value(
                "backtest/report_dir",
                str(Path.cwd() / "reports"),
            )
        )
        output_dir = QFileDialog.getExistingDirectory(
            terminal,
            "Select Backtest Report Folder",
            default_dir,
        )
        if not output_dir:
            terminal._refresh_backtest_window(message="Report export cancelled.")
            return
        terminal.settings.setValue("backtest/report_dir", output_dir)
        context = getattr(terminal, "_backtest_context", {}) or {}
        symbol_slug = str(context.get("symbol", "BACKTEST") or "BACKTEST").replace("/", "_").replace(":", "_").replace(" ", "_")
        timeframe_slug = str(context.get("timeframe", "custom") or "custom").replace("/", "_").replace(" ", "_")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_stem = f"backtest_report_{symbol_slug}_{timeframe_slug}_{stamp}"
        pdf_target = Path(output_dir) / f"{file_stem}.pdf"
        excel_target = Path(output_dir) / f"{file_stem}.xlsx"
        generator = ReportGenerator(
            trades=trades,
            equity_history=getattr(terminal.backtest_engine, "equity_curve", []),
            output_dir=output_dir,
        )
        pdf_path = generator.export_pdf(pdf_target)
        excel_path = generator.export_excel(excel_target)
        terminal.backtest_report = generator.generate()
        terminal.system_console.log(f"Backtest report generated: {pdf_path} | {excel_path}", "INFO")
        terminal._append_backtest_journal(
            f"Report exported to {pdf_path} and {excel_path}.",
            "INFO",
        )
        terminal._refresh_backtest_window(message="Backtest report generated.")
    except Exception as exc:
        terminal.system_console.log(f"Report generation failed: {exc}")
        terminal._append_backtest_journal(f"Report generation failed: {exc}", "ERROR")
