import asyncio
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.actions.trading_actions import (
    cancel_all_orders,
    cancel_all_orders_async,
    close_all_positions,
    close_all_positions_async,
    export_trades,
    show_async_message,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_close_all_positions_schedules_task_after_confirmation():
    scheduled = {"count": 0}

    async def _close_all_positions_async():
        return None

    class _Loop:
        def create_task(self, coro):
            scheduled["count"] += 1
            coro.close()
            return SimpleNamespace()

    fake = SimpleNamespace(
        controller=SimpleNamespace(broker=object()),
        _close_all_positions_async=_close_all_positions_async,
    )

    with patch("frontend.ui.actions.trading_actions.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        with patch("frontend.ui.actions.trading_actions.asyncio.get_event_loop", return_value=_Loop()):
            close_all_positions(fake)

    assert scheduled["count"] == 1


def test_cancel_all_orders_schedules_task_after_confirmation():
    scheduled = {"count": 0}

    async def _cancel_all_orders_async():
        return None

    class _Loop:
        def create_task(self, coro):
            scheduled["count"] += 1
            coro.close()
            return SimpleNamespace()

    fake = SimpleNamespace(
        controller=SimpleNamespace(broker=object()),
        _cancel_all_orders_async=_cancel_all_orders_async,
    )

    with patch("frontend.ui.actions.trading_actions.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        with patch("frontend.ui.actions.trading_actions.asyncio.get_event_loop", return_value=_Loop()):
            cancel_all_orders(fake)

    assert scheduled["count"] == 1


def test_close_all_positions_async_falls_back_to_tracked_positions():
    created_orders = []
    logs = []

    async def create_order(symbol, side, amount, type):
        created_orders.append((symbol, side, amount, type))
        return {"symbol": symbol, "side": side, "amount": amount}

    fake = SimpleNamespace(
        controller=SimpleNamespace(broker=SimpleNamespace(create_order=create_order)),
        _tracked_app_positions=lambda: [
            {"symbol": "EUR/USD", "amount": 2.0, "side": "long"},
            {"symbol": "USD/JPY", "amount": 1.5, "side": "short"},
        ],
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
    )

    asyncio.run(close_all_positions_async(fake, show_dialog=False))

    assert created_orders == [
        ("EUR/USD", "sell", 2.0, "market"),
        ("USD/JPY", "buy", 1.5, "market"),
    ]
    assert logs == [("Closed 2 position(s).", "INFO")]


def test_cancel_all_orders_async_clears_snapshot_and_schedules_refresh():
    populated = []
    state = {"scheduled": 0}
    logs = []

    async def cancel_all_orders_impl():
        return [{"id": "1"}, {"id": "2"}]

    fake = SimpleNamespace(
        controller=SimpleNamespace(broker=SimpleNamespace(cancel_all_orders=cancel_all_orders_impl)),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
        _latest_open_orders_snapshot=[{"id": "old"}],
        _populate_open_orders_table=lambda rows: populated.append(list(rows)),
        _schedule_open_orders_refresh=lambda: state.__setitem__("scheduled", state["scheduled"] + 1),
    )

    asyncio.run(cancel_all_orders_async(fake, show_dialog=False))

    assert fake._latest_open_orders_snapshot == []
    assert populated == [[]]
    assert state["scheduled"] == 1
    assert logs == [("Canceled 2 open order(s).", "INFO")]


def test_export_trades_writes_csv_and_reports_success():
    class _Trades:
        empty = False

        def to_csv(self, path, index=False):
            Path(path).write_text("symbol,pnl\nEUR/USD,12\n", encoding="utf-8")

    logs = []
    info_messages = []
    fake = SimpleNamespace(
        results=_Trades(),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        logger=SimpleNamespace(exception=lambda *_args, **_kwargs: None),
    )

    with TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "trades.csv")
        with patch("frontend.ui.actions.trading_actions.QFileDialog.getSaveFileName", return_value=(output_path, "CSV Files (*.csv)")):
            with patch("frontend.ui.actions.trading_actions.QMessageBox.information", side_effect=lambda *args: info_messages.append(args[2])):
                export_trades(fake)

        assert Path(output_path).read_text(encoding="utf-8") == "symbol,pnl\nEUR/USD,12\n"

    assert logs == [(f"Trades exported to {output_path}", "INFO")]
    assert info_messages == [f"Trades exported to:\n{output_path}"]


def test_show_async_message_opens_non_modal_box():
    _app()
    opened = {}

    class _FakeBox:
        StandardButton = QMessageBox.StandardButton

        def __init__(self, parent):
            opened["parent"] = parent

        def setIcon(self, icon):
            opened["icon"] = icon

        def setWindowTitle(self, title):
            opened["title"] = title

        def setText(self, text):
            opened["text"] = text

        def setStandardButtons(self, buttons):
            opened["buttons"] = buttons

        def setModal(self, modal):
            opened["modal"] = modal

        def setAttribute(self, attribute, value=True):
            opened["attribute"] = (attribute, value)

        def open(self):
            opened["opened"] = True

    fake = SimpleNamespace(_ui_shutting_down=False)

    with patch("frontend.ui.actions.trading_actions.QMessageBox", _FakeBox):
        with patch("frontend.ui.actions.trading_actions.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
            show_async_message(fake, "Manual Order", "Submitted.")

    assert opened["parent"] is fake
    assert opened["title"] == "Manual Order"
    assert opened["text"] == "Submitted."
    assert opened["modal"] is False
    assert opened["opened"] is True
