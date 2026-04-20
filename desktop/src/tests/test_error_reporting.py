import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.services.error_reporting import report_uncaught_exception


class _Logger:
    def __init__(self):
        self.calls = []

    def error(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_report_uncaught_exception_writes_log_and_routes_runtime_alerts(tmp_path):
    logger = _Logger()
    console_messages = []
    notifications = []
    fake_terminal = SimpleNamespace(
        logger=logger,
        system_console=SimpleNamespace(log=lambda message, level="INFO": console_messages.append((message, level))),
        _push_notification=lambda *args, **kwargs: notifications.append((args, kwargs)),
    )

    try:
        raise AttributeError("missing backtest handler")
    except AttributeError as exc:
        log_path = report_uncaught_exception(
            type(exc),
            exc,
            exc.__traceback__,
            terminal=fake_terminal,
            log_dir=tmp_path / "logs",
        )

    assert log_path.exists()
    text = log_path.read_text(encoding="utf-8")
    assert "AttributeError: missing backtest handler" in text
    assert logger.calls
    assert console_messages == [("Uncaught UI exception: AttributeError: missing backtest handler", "ERROR")]
    assert notifications
