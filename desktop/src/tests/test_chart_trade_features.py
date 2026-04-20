import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.chart.chart_widget import ChartWidget


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_chart_trade_plan_label_reports_risk_reward_ratio():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", SimpleNamespace(broker=None))

    widget.set_trade_overlay(entry=100.0, stop_loss=95.0, take_profit=110.0, side="buy")

    assert "RR 2.00" in widget.trade_plan_label.text()
    assert "Risk 5.00000" in widget.trade_plan_label.text()
    assert "Reward 10.00000" in widget.trade_plan_label.text()


def test_chart_trade_context_menu_definitions_include_market_ticket_actions():
    _app()
    widget = ChartWidget("ETH/USDT", "15m", SimpleNamespace(broker=None))

    actions = [item for item in widget._trade_context_menu_definitions() if item is not None]
    labels = [label for label, _action in actions]
    action_names = [action for _label, action in actions]

    assert "Buy Market Ticket" in labels
    assert "Sell Market Ticket" in labels
    assert "buy_market_ticket" in action_names
    assert "sell_market_ticket" in action_names
    assert "clear_levels" in action_names


def test_chart_toolbar_exposes_requested_drawing_tools():
    _app()
    widget = ChartWidget("SOL/USDT", "1h", SimpleNamespace(broker=None))

    tool_names = [tool_name for _label, tool_name in widget._chart_tool_definitions()]

    assert "long_rr" in tool_names
    assert "short_rr" in tool_names
    assert "trend" in tool_names
    assert "info" in tool_names
    assert "ghost" in tool_names
    assert "arrow" in tool_names
    assert "clear" in tool_names


def test_long_rr_tool_creates_target_view_overlay():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", SimpleNamespace(broker=None))

    widget._place_trade_projection("buy", {"x": 10.0, "y": 100.0})

    state = widget._trade_overlay_state
    assert state["side"] == "buy"
    assert state["entry"] == 100.0
    assert state["stop_loss"] < state["entry"]
    assert state["take_profit"] > state["entry"]
    assert widget.trade_risk_fill.isVisible() is True
    assert widget.trade_reward_fill.isVisible() is True
    assert widget._trade_target_view_summary.startswith("RR ")
    assert widget._selected_annotation == {"kind": "trade_overlay"}


def test_chart_tool_click_commits_trend_line():
    _app()
    widget = ChartWidget("ADA/USDT", "15m", SimpleNamespace(broker=None))
    widget._set_active_chart_tool("trend")

    assert widget._handle_chart_tool_click({"x": 1.0, "y": 10.0}) is True
    assert widget._drawing_anchor == {"x": 1.0, "y": 10.0}
    assert widget._drawing_preview is not None

    assert widget._handle_chart_tool_click({"x": 2.0, "y": 12.5}) is True
    assert widget._drawing_anchor is None
    assert widget._drawing_preview is None
    assert len(widget._chart_drawings) == 1
    assert widget._chart_drawings[0]["tool"] == "trend"
    assert widget._selected_annotation == {"kind": "drawing", "drawing": widget._chart_drawings[0]}


def test_long_rr_overlay_can_be_dragged_after_creation():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", SimpleNamespace(broker=None))

    widget._place_trade_projection("buy", {"x": 10.0, "y": 100.0})
    original = dict(widget._trade_overlay_state)

    assert widget._begin_annotation_drag(widget._selected_annotation, {"x": 10.0, "y": 100.0}) is True
    assert widget._update_annotation_drag({"x": 12.0, "y": 105.0}) is True
    assert widget._finish_annotation_drag() is True

    moved = widget._trade_overlay_state
    assert moved["entry"] == original["entry"] + 5.0
    assert moved["stop_loss"] == original["stop_loss"] + 5.0
    assert moved["take_profit"] == original["take_profit"] + 5.0
    assert moved["anchor_x"] == original["anchor_x"] + 2.0
    assert moved["x_start"] == original["x_start"] + 2.0
    assert moved["x_end"] == original["x_end"] + 2.0


def test_short_rr_overlay_can_be_removed_after_creation():
    _app()
    widget = ChartWidget("ETH/USDT", "15m", SimpleNamespace(broker=None))

    widget._place_trade_projection("sell", {"x": 20.0, "y": 2500.0})

    assert widget._selected_annotation == {"kind": "trade_overlay"}
    assert widget._remove_selected_annotation() is True
    assert widget._trade_overlay_state["entry"] is None
    assert widget._trade_overlay_state["stop_loss"] is None
    assert widget._trade_overlay_state["take_profit"] is None
    assert widget.trade_target_view_label.isVisible() is False
    assert widget._selected_annotation is None


def test_ghost_drawing_can_be_dragged_and_removed_after_creation():
    _app()
    widget = ChartWidget("SOL/USDT", "1h", SimpleNamespace(broker=None))

    widget._commit_chart_drawing("ghost", {"x": 1.0, "y": 10.0}, {"x": 2.5, "y": 12.0})
    drawing = widget._chart_drawings[0]
    original_start = dict(drawing["start"])
    original_end = dict(drawing["end"])

    assert widget._selected_annotation == {"kind": "drawing", "drawing": drawing}
    assert widget._begin_annotation_drag(widget._selected_annotation, {"x": 1.0, "y": 10.0}) is True
    assert widget._update_annotation_drag({"x": 3.0, "y": 13.0}) is True
    assert widget._finish_annotation_drag() is True

    assert drawing["start"] == {"x": original_start["x"] + 2.0, "y": original_start["y"] + 3.0}
    assert drawing["end"] == {"x": original_end["x"] + 2.0, "y": original_end["y"] + 3.0}
    assert widget._remove_selected_annotation() is True
    assert widget._chart_drawings == []
    assert widget._selected_annotation is None


def test_chart_keyboard_shortcuts_arm_tool_and_cancel_cleanly():
    _app()
    widget = ChartWidget("BTC/USDT", "1h", SimpleNamespace(broker=None))

    widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_G, QtCore.Qt.KeyboardModifier.NoModifier, "g"))

    assert widget._active_chart_tool == "ghost"

    widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape, QtCore.Qt.KeyboardModifier.NoModifier))

    assert widget._active_chart_tool is None
    assert widget._drawing_anchor is None


def test_chart_can_cycle_timeframes_from_keyboard():
    _app()
    widget = ChartWidget("ETH/USDT", "1h", SimpleNamespace(broker=None))
    selected = []
    widget.sigTimeframeSelected.connect(selected.append)

    widget._cycle_timeframe(1)
    widget._cycle_timeframe(-1)

    assert widget.timeframe == "1h"
    assert selected == ["4h", "1h"]


def test_chart_keyboard_shortcut_toggles_volume_panel():
    _app()
    widget = ChartWidget("SOL/USDT", "15m", SimpleNamespace(broker=None))

    assert widget.show_volume_panel is False

    widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_V, QtCore.Qt.KeyboardModifier.NoModifier, "v"))
    assert widget.show_volume_panel is True

    widget.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_V, QtCore.Qt.KeyboardModifier.NoModifier, "v"))
    assert widget.show_volume_panel is False
