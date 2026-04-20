import asyncio

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from strategy.strategy import Strategy


OPTIMIZATION_IDLE_MESSAGE = (
    "Optimization is idle. Nothing will run until you click Run Optimization or Rank All Strategies."
)


def show_optimization_window(terminal):
    try:
        setattr(terminal, "_optimization_bootstrapping", True)
        window = terminal._get_or_create_tool_window(
            "strategy_optimization",
            "Strategy Optimization",
            width=980,
            height=640,
        )

        if getattr(window, "_optimization_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)

            status = QLabel("Choose your symbol and click Run Optimization or Rank All Strategies to start.")
            status.setStyleSheet("color: #e6edf7; font-weight: 700;")
            layout.addWidget(status)

            selection_frame = QFrame()
            selection_frame.setStyleSheet(
                "QFrame { background-color: #0f1727; border: 1px solid #24344f; border-radius: 10px; }"
                "QLabel { color: #d7dfeb; font-weight: 700; }"
                "QComboBox { background-color: #0b1220; color: #f4f8ff; border: 1px solid #2a3d5c; border-radius: 6px; padding: 6px 10px; min-width: 180px; }"
            )
            selection_layout = QGridLayout(selection_frame)
            selection_layout.setContentsMargins(14, 12, 14, 12)
            selection_layout.setHorizontalSpacing(16)
            selection_layout.setVerticalSpacing(8)

            symbol_picker = QComboBox()
            strategy_picker = QComboBox()
            timeframe_picker = QComboBox()
            selection_layout.addWidget(QLabel("Optimize Symbol"), 0, 0)
            selection_layout.addWidget(symbol_picker, 0, 1)
            selection_layout.addWidget(QLabel("Optimize Strategy"), 0, 2)
            selection_layout.addWidget(strategy_picker, 0, 3)
            selection_layout.addWidget(QLabel("Timeframe"), 1, 0)
            selection_layout.addWidget(timeframe_picker, 1, 1)
            layout.addWidget(selection_frame)

            controls = QHBoxLayout()
            run_btn = QPushButton("Run Optimization")
            rank_btn = QPushButton("Rank All Strategies")
            apply_btn = QPushButton("Apply Best Params")
            assign_btn = QPushButton("Assign Best To Symbol")
            assign_count = QSpinBox()
            assign_count.setRange(1, 10)
            assign_count.setValue(int(getattr(terminal.controller, "max_symbol_strategies", 3) or 3))
            run_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(terminal._run_strategy_optimization()))
            rank_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(terminal._run_strategy_ranking()))
            apply_btn.clicked.connect(terminal._apply_best_optimization_params)
            assign_btn.clicked.connect(terminal._assign_ranked_strategies_to_symbol)
            controls.addWidget(run_btn)
            controls.addWidget(rank_btn)
            controls.addWidget(apply_btn)
            controls.addWidget(QLabel("Assign Top"))
            controls.addWidget(assign_count)
            controls.addWidget(assign_btn)
            controls.addStretch()
            layout.addLayout(controls)

            summary = QLabel("-")
            summary.setWordWrap(True)
            summary.setStyleSheet("color: #9fb0c7;")
            layout.addWidget(summary)

            table = QTableWidget()
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels(
                [
                    "RSI",
                    "EMA Fast",
                    "EMA Slow",
                    "ATR",
                    "Profit",
                    "Sharpe",
                    "Win Rate",
                    "Final Equity",
                ]
            )
            layout.addWidget(table)

            window.setCentralWidget(container)
            window._optimization_container = container
            window._optimization_status = status
            window._optimization_summary = summary
            window._optimization_table = table
            window._optimization_run_btn = run_btn
            window._optimization_rank_btn = rank_btn
            window._optimization_apply_btn = apply_btn
            window._optimization_assign_btn = assign_btn
            window._optimization_assign_count = assign_count
            window._optimization_symbol_picker = symbol_picker
            window._optimization_strategy_picker = strategy_picker
            window._optimization_timeframe_picker = timeframe_picker
            symbol_picker.currentTextChanged.connect(lambda _text: terminal._optimization_selection_changed())
            strategy_picker.currentTextChanged.connect(lambda _text: terminal._optimization_selection_changed())
            timeframe_picker.currentTextChanged.connect(lambda _text: terminal._optimization_selection_changed())

        try:
            terminal._refresh_optimization_selectors(window)
            terminal._refresh_optimization_window(window, message=OPTIMIZATION_IDLE_MESSAGE)
        except Exception as exc:
            if hasattr(terminal, "logger"):
                terminal.logger.exception("Unable to refresh strategy optimization window")
            status = getattr(window, "_optimization_status", None)
            summary = getattr(window, "_optimization_summary", None)
            if status is not None:
                status.setText("Strategy Optimization opened with limited data.")
            if summary is not None:
                summary.setText(f"Window opened, but some optimization controls could not refresh yet: {exc}")

        window.show()
        window.raise_()
        window.activateWindow()
        return window
    except Exception as exc:
        if hasattr(terminal, "logger"):
            terminal.logger.exception("Unable to open strategy optimization window")
        if hasattr(terminal, "system_console"):
            terminal.system_console.log(f"Strategy Optimization failed to open: {exc}", "ERROR")
        if hasattr(terminal, "_show_async_message"):
            terminal._show_async_message("Strategy Optimization Failed", str(exc), QMessageBox.Icon.Critical)
        return None
    finally:
        setattr(terminal, "_optimization_bootstrapping", False)


def refresh_optimization_window(terminal, window=None, message=None):
    window = window or terminal.detached_tool_windows.get("strategy_optimization")
    if window is None:
        return

    status = getattr(window, "_optimization_status", None)
    summary = getattr(window, "_optimization_summary", None)
    table = getattr(window, "_optimization_table", None)
    run_btn = getattr(window, "_optimization_run_btn", None)
    rank_btn = getattr(window, "_optimization_rank_btn", None)
    apply_btn = getattr(window, "_optimization_apply_btn", None)
    assign_btn = getattr(window, "_optimization_assign_btn", None)
    assign_count = getattr(window, "_optimization_assign_count", None)
    symbol_picker = getattr(window, "_optimization_symbol_picker", None)
    strategy_picker = getattr(window, "_optimization_strategy_picker", None)
    timeframe_picker = getattr(window, "_optimization_timeframe_picker", None)
    if status is None or summary is None or table is None:
        return

    context = getattr(terminal, "_optimization_context", {}) or {}
    selected_symbol = str(symbol_picker.currentText()).strip() if symbol_picker is not None else ""
    selected_strategy = str(strategy_picker.currentText()).strip() if strategy_picker is not None else ""
    selected_timeframe = str(timeframe_picker.currentText()).strip() if timeframe_picker is not None else ""
    symbol = context.get("symbol", selected_symbol or "-")
    timeframe = context.get("timeframe", selected_timeframe or "-")
    strategy_name = (
        context.get("strategy_name", None)
        or selected_strategy
        or getattr(terminal.controller, "strategy_name", None)
        or getattr(getattr(terminal.controller, "config", None), "strategy", "Trend Following")
    )
    dataset = context.get("data")
    candle_count = len(dataset) if hasattr(dataset, "__len__") else 0
    assigned = []
    if hasattr(terminal.controller, "assigned_strategies_for_symbol"):
        try:
            assigned = list(terminal.controller.assigned_strategies_for_symbol(symbol) or [])
        except Exception:
            assigned = []
    assigned_text = ", ".join(
        str(row.get("strategy_name") or "").strip()
        for row in assigned[:3]
        if str(row.get("strategy_name") or "").strip()
    )
    mode = str(getattr(terminal, "_optimization_mode", "param") or "param")

    if message is not None:
        terminal._optimization_status_message = message

    running = bool(getattr(terminal, "_optimization_running", False))
    status_message = getattr(terminal, "_optimization_status_message", None)
    status.setText(status_message or ("Optimization running..." if running else "Optimization workspace ready."))
    summary.setText(
        f"Symbol: {symbol} | Timeframe: {timeframe} | Strategy: {strategy_name} | "
        f"Mode: {'Rank All' if mode == 'ranking' else 'Parameter Optimize'} | Candles: {candle_count}"
        + (f" | Assigned: {assigned_text}" if assigned_text else "")
    )
    if run_btn is not None:
        run_btn.setEnabled(not running)
        run_btn.setText("Running..." if running else "Run Optimization")
    if rank_btn is not None:
        rank_btn.setEnabled(not running)
        rank_btn.setText("Running..." if running and mode == "ranking" else "Rank All Strategies")
    if apply_btn is not None:
        apply_btn.setEnabled((not running) and mode == "param" and isinstance(getattr(terminal, "optimization_best", None), dict))
    if assign_btn is not None:
        assign_btn.setEnabled(
            (not running)
            and mode == "ranking"
            and getattr(terminal, "strategy_ranking_results", None) is not None
            and not getattr(getattr(terminal, "strategy_ranking_results", None), "empty", True)
        )
    if assign_count is not None:
        assign_count.setEnabled(not running)
    if symbol_picker is not None:
        symbol_picker.setEnabled(not running)
    if strategy_picker is not None:
        strategy_picker.setEnabled(not running)
    if timeframe_picker is not None:
        timeframe_picker.setEnabled(not running)

    results = getattr(terminal, "strategy_ranking_results", None) if mode == "ranking" else getattr(terminal, "optimization_results", None)
    if results is None or getattr(results, "empty", True):
        table.setRowCount(0)
        return

    display = results.head(25).reset_index(drop=True)
    table.setRowCount(len(display))
    if mode == "ranking":
        columns = [
            ("strategy_name", "{}"),
            ("score", "{:.3f}"),
            ("total_profit", "{:.2f}"),
            ("sharpe_ratio", "{:.3f}"),
            ("win_rate", "{:.2%}"),
            ("max_drawdown", "{:.2f}"),
            ("final_equity", "{:.2f}"),
            ("closed_trades", "{:g}"),
        ]
        headers = ["Strategy", "Score", "Profit", "Sharpe", "Win Rate", "Drawdown", "Final Equity", "Closed Trades"]
    else:
        columns = [
            ("rsi_period", "{:g}"),
            ("ema_fast", "{:g}"),
            ("ema_slow", "{:g}"),
            ("atr_period", "{:g}"),
            ("total_profit", "{:.2f}"),
            ("sharpe_ratio", "{:.3f}"),
            ("win_rate", "{:.2%}"),
            ("final_equity", "{:.2f}"),
        ]
        headers = ["RSI", "EMA Fast", "EMA Slow", "ATR", "Profit", "Sharpe", "Win Rate", "Final Equity"]
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)

    for row_idx, (_, row) in enumerate(display.iterrows()):
        for col_idx, (column, fmt) in enumerate(columns):
            value = row.get(column, "")
            try:
                text = fmt.format(float(value))
            except Exception:
                text = str(value)
            table.setItem(row_idx, col_idx, QTableWidgetItem(text))

    table.resizeColumnsToContents()


def refresh_optimization_selectors(terminal, window=None):
    window = window or getattr(terminal, "detached_tool_windows", {}).get("strategy_optimization")
    if window is None:
        return

    symbol_picker = getattr(window, "_optimization_symbol_picker", None)
    strategy_picker = getattr(window, "_optimization_strategy_picker", None)
    timeframe_picker = getattr(window, "_optimization_timeframe_picker", None)
    if symbol_picker is None or strategy_picker is None or timeframe_picker is None:
        return

    context = getattr(terminal, "_optimization_context", {}) or {}
    current_symbol = str(symbol_picker.currentText()).strip()
    current_strategy = str(strategy_picker.currentText()).strip()
    current_timeframe = str(timeframe_picker.currentText()).strip()

    symbol_candidates = terminal._backtest_symbol_candidates()
    timeframe_candidates = terminal._backtest_timeframe_candidates()
    target_symbol = context.get("symbol") or current_symbol or (symbol_candidates[0] if symbol_candidates else "")
    target_strategy = Strategy.normalize_strategy_name(
        context.get("strategy_name")
        or current_strategy
        or getattr(terminal.controller, "strategy_name", None)
        or getattr(getattr(terminal.controller, "config", None), "strategy", "Trend Following")
    )
    target_timeframe = str(
        context.get("timeframe")
        or current_timeframe
        or getattr(terminal, "current_timeframe", getattr(terminal.controller, "time_frame", "1h"))
    ).strip()

    symbol_picker.blockSignals(True)
    symbol_picker.clear()
    for symbol in symbol_candidates:
        symbol_picker.addItem(symbol)
    if target_symbol and symbol_picker.findText(target_symbol) < 0:
        symbol_picker.addItem(target_symbol)
    if target_symbol:
        symbol_picker.setCurrentText(target_symbol)
    symbol_picker.blockSignals(False)

    terminal._populate_strategy_picker(strategy_picker, selected_strategy=target_strategy)

    timeframe_picker.blockSignals(True)
    timeframe_picker.clear()
    for timeframe in timeframe_candidates:
        timeframe_picker.addItem(timeframe)
    if target_timeframe and timeframe_picker.findText(target_timeframe) < 0:
        timeframe_picker.addItem(target_timeframe)
    timeframe_picker.setCurrentText(target_timeframe)
    timeframe_picker.blockSignals(False)


def optimization_selection_changed(terminal):
    if bool(getattr(terminal, "_optimization_bootstrapping", False)):
        return
    if getattr(terminal, "_optimization_running", False):
        return

    window = getattr(terminal, "detached_tool_windows", {}).get("strategy_optimization")
    if window is None:
        return

    symbol_picker = getattr(window, "_optimization_symbol_picker", None)
    strategy_picker = getattr(window, "_optimization_strategy_picker", None)
    timeframe_picker = getattr(window, "_optimization_timeframe_picker", None)
    if symbol_picker is None or strategy_picker is None or timeframe_picker is None:
        return

    selected_symbol = str(symbol_picker.currentText()).strip()
    selected_strategy = Strategy.normalize_strategy_name(strategy_picker.currentText())
    selected_timeframe = str(timeframe_picker.currentText()).strip() or getattr(
        terminal, "current_timeframe", getattr(terminal.controller, "time_frame", "1h")
    )
    previous = getattr(terminal, "_optimization_context", {}) or {}

    dataset = None
    buffers = getattr(terminal.controller, "candle_buffers", {})
    if hasattr(buffers, "get"):
        dataset = (buffers.get(selected_symbol) or {}).get(selected_timeframe)

    selection_changed = (
        selected_symbol != str(previous.get("symbol") or "").strip()
        or selected_strategy != Strategy.normalize_strategy_name(previous.get("strategy_name"))
        or selected_timeframe != str(previous.get("timeframe") or "").strip()
    )

    terminal._optimization_context = {
        "symbol": selected_symbol,
        "timeframe": selected_timeframe,
        "data": dataset.copy() if hasattr(dataset, "copy") else dataset,
        "strategy": previous.get("strategy"),
        "strategy_name": selected_strategy,
    }

    if selection_changed:
        terminal.optimization_results = None
        terminal.optimization_best = None
        terminal.strategy_ranking_results = None
        terminal.strategy_ranking_best = None

    info = "Selection updated. Nothing runs until you click Run Optimization or Rank All Strategies."
    if dataset is None or getattr(dataset, "empty", False):
        info = "Selection updated. Candle data will load only after you start Optimization or Rank All Strategies."
    terminal._refresh_optimization_window(message=info)


def apply_best_optimization_params(terminal):
    try:
        best = getattr(terminal, "optimization_best", None)
        if not isinstance(best, dict):
            raise RuntimeError("Run optimization before applying parameters")

        context = getattr(terminal, "_optimization_context", {}) or {}
        strategy_source = context.get("strategy")
        strategy_name = context.get("strategy_name")

        if strategy_source is None:
            raise RuntimeError("No strategy context available")

        if hasattr(strategy_source, "_resolve_strategy"):
            target = strategy_source._resolve_strategy(strategy_name)
        else:
            target = strategy_source

        applied = []
        for key in ["rsi_period", "ema_fast", "ema_slow", "atr_period"]:
            if key in best and hasattr(target, key):
                setattr(target, key, int(best[key]))
                applied.append(f"{key}={int(best[key])}")

        strategy_params = dict(getattr(terminal.controller, "strategy_params", {}) or {})
        for key in ["rsi_period", "ema_fast", "ema_slow", "atr_period"]:
            if key in best:
                strategy_params[key] = int(best[key])
        terminal.controller.strategy_params = strategy_params
        terminal.settings.setValue("strategy/rsi_period", strategy_params.get("rsi_period", 14))
        terminal.settings.setValue("strategy/ema_fast", strategy_params.get("ema_fast", 20))
        terminal.settings.setValue("strategy/ema_slow", strategy_params.get("ema_slow", 50))
        terminal.settings.setValue("strategy/atr_period", strategy_params.get("atr_period", 14))

        if not applied:
            raise RuntimeError("No compatible strategy parameters were available to apply")

        terminal.system_console.log(f"Applied optimized params: {', '.join(applied)}", "INFO")
        terminal._refresh_optimization_window(message="Applied best optimization parameters.")

    except Exception as exc:
        terminal.system_console.log(f"Apply optimization failed: {exc}", "ERROR")
        terminal._refresh_optimization_window(message=f"Apply optimization failed: {exc}")


def optimize_strategy(terminal):
    try:
        terminal._show_optimization_window()
        if hasattr(terminal, "_refresh_optimization_window"):
            terminal._refresh_optimization_window(message=OPTIMIZATION_IDLE_MESSAGE)
        return
    except Exception as exc:
        if hasattr(terminal, "logger"):
            terminal.logger.exception("Strategy Optimization open failed")
        if hasattr(terminal, "system_console"):
            terminal.system_console.log(f"Strategy Optimization failed to open: {exc}", "ERROR")
        if hasattr(terminal, "_show_async_message"):
            terminal._show_async_message("Strategy Optimization Failed", str(exc), QMessageBox.Icon.Critical)
        return
