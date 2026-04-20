import asyncio

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox


def close_all_positions(terminal):
    broker = getattr(terminal.controller, "broker", None)
    if broker is None:
        QMessageBox.warning(terminal, "Close Positions", "Connect a broker before closing positions.")
        return

    confirm = QMessageBox.question(
        terminal,
        "Close Positions",
        "Close all tracked positions with market orders?",
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    controller = getattr(terminal, "controller", None)
    if controller is not None and hasattr(controller, "queue_trade_audit"):
        controller.queue_trade_audit(
            "close_all_positions_requested",
            status="pending",
            source="terminal",
            message="Operator requested close-all positions from the terminal.",
        )

    asyncio.get_event_loop().create_task(terminal._close_all_positions_async())


def export_trades(terminal):
    try:
        try:
            import pandas as pd
        except Exception:
            pd = None

        trades = getattr(terminal, "results", None)
        if trades is None or getattr(trades, "empty", True):
            QMessageBox.information(terminal, "Export Trades", "No trades are available to export yet.")
            return

        path, _ = QFileDialog.getSaveFileName(
            terminal,
            "Export Trades",
            "trades.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        # Backtest results are already dataframe-like, but we normalize defensively
        # so export still works if the table source changes later.
        if pd is not None and not hasattr(trades, "to_csv"):
            trades = pd.DataFrame(trades)
        trades.to_csv(path, index=False)
        terminal.system_console.log(f"Trades exported to {path}", "INFO")
        QMessageBox.information(terminal, "Export Trades", f"Trades exported to:\n{path}")
    except Exception as exc:
        terminal.logger.exception("Export trades failed")
        terminal.system_console.log(f"Trade export failed: {exc}", "ERROR")
        QMessageBox.critical(terminal, "Export Trades Failed", str(exc))


def cancel_all_orders(terminal):
    broker = getattr(terminal.controller, "broker", None)
    if broker is None:
        QMessageBox.warning(terminal, "Cancel Orders", "Connect a broker before canceling orders.")
        return

    confirm = QMessageBox.question(
        terminal,
        "Cancel Orders",
        "Cancel all open orders for the connected broker?",
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    controller = getattr(terminal, "controller", None)
    if controller is not None and hasattr(controller, "queue_trade_audit"):
        controller.queue_trade_audit(
            "cancel_all_orders_requested",
            status="pending",
            source="terminal",
            message="Operator requested cancel-all orders from the terminal.",
        )

    asyncio.get_event_loop().create_task(terminal._cancel_all_orders_async())


def show_async_message(terminal, title, text, icon=QMessageBox.Icon.Information):
    def _open():
        if terminal._ui_shutting_down:
            return
        box = QMessageBox(terminal)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(str(text))
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.open()

    QTimer.singleShot(0, _open)


async def close_all_positions_async(terminal, show_dialog=True):
    broker = getattr(terminal.controller, "broker", None)
    if broker is None:
        return

    try:
        results = []
        if hasattr(broker, "close_all_positions"):
            results = await broker.close_all_positions()

        if not results:
            for position in terminal._tracked_app_positions():
                symbol = position.get("symbol")
                amount = float(position.get("amount", 0) or 0)
                if not symbol or amount <= 0:
                    continue
                close_side = "sell" if position.get("side") != "short" else "buy"
                order = await broker.create_order(
                    symbol=symbol,
                    side=close_side,
                    amount=amount,
                    type="market",
                )
                if order:
                    results.append(order)

        count = len(results or [])
        if count == 0:
            if show_dialog:
                QMessageBox.information(
                    terminal,
                    "Close Positions",
                    "No open positions were found to close.",
                )
            return

        terminal.system_console.log(f"Closed {count} position(s).", "INFO")
        controller = getattr(terminal, "controller", None)
        if controller is not None and hasattr(controller, "queue_trade_audit"):
            controller.queue_trade_audit(
                "close_positions_success",
                status="submitted",
                source="terminal",
                message=f"Submitted {count} close order(s).",
                payload={"count": count},
            )
        if show_dialog:
            QMessageBox.information(
                terminal,
                "Close Positions",
                f"Submitted {count} closing order(s).",
            )
    except Exception as exc:
        terminal.logger.exception("Close-all positions failed")
        terminal.system_console.log(f"Close positions failed: {exc}", "ERROR")
        controller = getattr(terminal, "controller", None)
        if controller is not None and hasattr(controller, "queue_trade_audit"):
            controller.queue_trade_audit(
                "close_positions_error",
                status="error",
                source="terminal",
                message=str(exc),
            )
        if show_dialog:
            QMessageBox.critical(terminal, "Close Positions Failed", str(exc))


async def cancel_all_orders_async(terminal, show_dialog=True):
    broker = getattr(terminal.controller, "broker", None)
    if broker is None:
        return

    try:
        results = await broker.cancel_all_orders()
        if results is True:
            count = 1
        elif isinstance(results, list):
            count = len(results)
        elif results:
            count = 1
        else:
            count = 0

        terminal.system_console.log(f"Canceled {count} open order(s).", "INFO")
        controller = getattr(terminal, "controller", None)
        if controller is not None and hasattr(controller, "queue_trade_audit"):
            controller.queue_trade_audit(
                "cancel_orders_success",
                status="submitted",
                source="terminal",
                message="Canceled all open orders." if count else "No open orders were found.",
                payload={"count": count},
            )
        terminal._latest_open_orders_snapshot = []
        terminal._populate_open_orders_table(terminal._latest_open_orders_snapshot)
        terminal._schedule_open_orders_refresh()
        if show_dialog:
            QMessageBox.information(
                terminal,
                "Cancel Orders",
                "Canceled all open orders." if count else "No open orders were found.",
            )
    except Exception as exc:
        terminal.logger.exception("Cancel-all orders failed")
        terminal.system_console.log(f"Cancel orders failed: {exc}", "ERROR")
        controller = getattr(terminal, "controller", None)
        if controller is not None and hasattr(controller, "queue_trade_audit"):
            controller.queue_trade_audit(
                "cancel_orders_error",
                status="error",
                source="terminal",
                message=str(exc),
            )
        if show_dialog:
            QMessageBox.critical(terminal, "Cancel Orders Failed", str(exc))
