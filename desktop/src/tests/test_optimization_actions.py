import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QMainWindow, QPushButton, QSpinBox, QTableWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.actions.optimization_actions import (
    OPTIMIZATION_IDLE_MESSAGE,
    apply_best_optimization_params,
    optimization_selection_changed,
    refresh_optimization_window,
    show_optimization_window,
)
from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_show_optimization_window_creates_workspace_and_refreshes_state():
    _app()
    window = QMainWindow()
    events = {"selectors": 0, "messages": []}

    async def _run_strategy_optimization():
        return None

    async def _run_strategy_ranking():
        return None

    fake = SimpleNamespace(
        controller=SimpleNamespace(max_symbol_strategies=4),
        _get_or_create_tool_window=lambda key, title, width=0, height=0: window,
        _refresh_optimization_selectors=lambda current_window=None: events.__setitem__("selectors", events["selectors"] + 1),
        _refresh_optimization_window=lambda current_window=None, message=None: events["messages"].append(message),
        _run_strategy_optimization=_run_strategy_optimization,
        _run_strategy_ranking=_run_strategy_ranking,
        _apply_best_optimization_params=lambda: None,
        _assign_ranked_strategies_to_symbol=lambda: None,
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
        system_console=SimpleNamespace(log=lambda *_args, **_kwargs: None),
        _show_async_message=lambda *_args, **_kwargs: None,
    )

    returned = show_optimization_window(fake)

    assert returned is window
    assert window._optimization_status.text().startswith("Choose your symbol")
    assert window._optimization_assign_count.value() == 4
    assert window._optimization_table.columnCount() == 8
    assert events["selectors"] == 1
    assert events["messages"] == [OPTIMIZATION_IDLE_MESSAGE]


def test_refresh_optimization_window_populates_summary_and_results_table():
    _app()
    window = SimpleNamespace(
        _optimization_status=QLabel(),
        _optimization_summary=QLabel(),
        _optimization_table=QTableWidget(),
        _optimization_run_btn=QPushButton(),
        _optimization_rank_btn=QPushButton(),
        _optimization_apply_btn=QPushButton(),
        _optimization_assign_btn=QPushButton(),
        _optimization_assign_count=QSpinBox(),
        _optimization_symbol_picker=QComboBox(),
        _optimization_strategy_picker=QComboBox(),
        _optimization_timeframe_picker=QComboBox(),
    )
    window._optimization_symbol_picker.addItem("EUR/USD")
    window._optimization_symbol_picker.setCurrentText("EUR/USD")
    window._optimization_strategy_picker.addItem("Trend Following")
    window._optimization_strategy_picker.setCurrentText("Trend Following")
    window._optimization_timeframe_picker.addItem("1h")
    window._optimization_timeframe_picker.setCurrentText("1h")
    fake = SimpleNamespace(
        detached_tool_windows={"strategy_optimization": window},
        controller=SimpleNamespace(
            strategy_name="Trend Following",
            config=SimpleNamespace(strategy="Trend Following"),
            assigned_strategies_for_symbol=lambda symbol: [{"strategy_name": "EMA Cross"}] if symbol == "EUR/USD" else [],
        ),
        _optimization_context={"symbol": "EUR/USD", "timeframe": "1h", "strategy_name": "Trend Following", "data": [1, 2, 3]},
        _optimization_running=False,
        _optimization_mode="param",
        optimization_best={"rsi_period": 14},
        optimization_results=pd.DataFrame(
            [{"rsi_period": 14, "ema_fast": 20, "ema_slow": 50, "atr_period": 14, "total_profit": 123.45, "sharpe_ratio": 1.234, "win_rate": 0.61, "final_equity": 10123.45}]
        ),
    )

    refresh_optimization_window(fake, message="Ready")

    assert window._optimization_status.text() == "Ready"
    assert "Symbol: EUR/USD" in window._optimization_summary.text()
    assert "Assigned: EMA Cross" in window._optimization_summary.text()
    assert window._optimization_apply_btn.isEnabled() is True
    assert window._optimization_table.rowCount() == 1
    assert window._optimization_table.item(0, 0).text() == "14"


def test_optimization_selection_changed_updates_context_and_clears_results():
    _app()
    window = SimpleNamespace(
        _optimization_symbol_picker=QComboBox(),
        _optimization_strategy_picker=QComboBox(),
        _optimization_timeframe_picker=QComboBox(),
    )
    window._optimization_symbol_picker.addItem("BTC/USDT")
    window._optimization_symbol_picker.setCurrentText("BTC/USDT")
    window._optimization_strategy_picker.addItem("EMA Cross")
    window._optimization_strategy_picker.setCurrentText("EMA Cross")
    window._optimization_timeframe_picker.addItem("4h")
    window._optimization_timeframe_picker.setCurrentText("4h")
    state = {"messages": []}
    dataset = pd.DataFrame([{"close": 1.0}])
    fake = SimpleNamespace(
        _optimization_bootstrapping=False,
        _optimization_running=False,
        detached_tool_windows={"strategy_optimization": window},
        controller=SimpleNamespace(candle_buffers={"BTC/USDT": {"4h": dataset}}, time_frame="1h"),
        current_timeframe="1h",
        _optimization_context={"symbol": "ETH/USDT", "timeframe": "1h", "strategy_name": "Trend Following", "strategy": object()},
        optimization_results=object(),
        optimization_best={"x": 1},
        strategy_ranking_results=object(),
        strategy_ranking_best={"y": 2},
        _refresh_optimization_window=lambda message=None: state["messages"].append(message),
    )

    optimization_selection_changed(fake)

    assert fake._optimization_context["symbol"] == "BTC/USDT"
    assert fake._optimization_context["timeframe"] == "4h"
    assert fake._optimization_context["strategy_name"] == "EMA Cross"
    assert fake._optimization_context["data"] is not dataset
    assert fake.optimization_results is None
    assert fake.optimization_best is None
    assert fake.strategy_ranking_results is None
    assert fake.strategy_ranking_best is None
    assert state["messages"] == ["Selection updated. Nothing runs until you click Run Optimization or Rank All Strategies."]


def test_apply_best_optimization_params_updates_strategy_and_settings():
    logs = []
    messages = []
    settings_writes = []
    target = SimpleNamespace(rsi_period=10, ema_fast=12, ema_slow=26, atr_period=8)
    fake = SimpleNamespace(
        optimization_best={"rsi_period": 14, "ema_fast": 20, "ema_slow": 50, "atr_period": 9},
        _optimization_context={"strategy": target, "strategy_name": "Trend Following"},
        controller=SimpleNamespace(strategy_params={}),
        settings=SimpleNamespace(setValue=lambda key, value: settings_writes.append((key, value))),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        _refresh_optimization_window=lambda message=None: messages.append(message),
    )

    apply_best_optimization_params(fake)

    assert (target.rsi_period, target.ema_fast, target.ema_slow, target.atr_period) == (14, 20, 50, 9)
    assert fake.controller.strategy_params == {"rsi_period": 14, "ema_fast": 20, "ema_slow": 50, "atr_period": 9}
    assert settings_writes == [
        ("strategy/rsi_period", 14),
        ("strategy/ema_fast", 20),
        ("strategy/ema_slow", 50),
        ("strategy/atr_period", 9),
    ]
    assert logs == [("Applied optimized params: rsi_period=14, ema_fast=20, ema_slow=50, atr_period=9", "INFO")]
    assert messages == ["Applied best optimization parameters."]


def test_terminal_exposes_optimization_bindings():
    assert hasattr(Terminal, "_refresh_optimization_selectors")
    assert hasattr(Terminal, "_optimization_selection_changed")
    assert hasattr(Terminal, "_backtest_symbol_candidates")
    assert hasattr(Terminal, "_backtest_timeframe_candidates")
