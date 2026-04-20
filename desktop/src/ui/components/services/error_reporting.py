from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import traceback
import weakref


_ACTIVE_TERMINAL_REF: weakref.ReferenceType | None = None


def set_active_terminal(terminal) -> None:
    global _ACTIVE_TERMINAL_REF
    try:
        _ACTIVE_TERMINAL_REF = weakref.ref(terminal)
    except TypeError:
        _ACTIVE_TERMINAL_REF = None


def get_active_terminal():
    if _ACTIVE_TERMINAL_REF is None:
        return None
    try:
        return _ACTIVE_TERMINAL_REF()
    except Exception:
        return None


def format_exception_text(exctype, value, tb) -> str:
    return "".join(traceback.format_exception(exctype, value, tb)).strip()


def append_exception_log(exctype, value, tb, log_dir="logs") -> Path:
    log_root = Path(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "errors.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = (
        f"\n=== Uncaught exception @ {timestamp} ===\n"
        f"{format_exception_text(exctype, value, tb)}\n"
    )
    with log_path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(payload)
    return log_path


def report_uncaught_exception(exctype, value, tb, terminal=None, log_dir="logs") -> Path:
    log_path = append_exception_log(exctype, value, tb, log_dir=log_dir)
    active_terminal = terminal or get_active_terminal()
    if active_terminal is None:
        return log_path

    formatted = format_exception_text(exctype, value, tb)
    headline = f"{getattr(exctype, '__name__', 'Exception')}: {value}"

    logger = getattr(active_terminal, "logger", None)
    if logger is not None and hasattr(logger, "error"):
        try:
            logger.error("Uncaught UI exception\n%s", formatted)
        except Exception:
            pass

    system_console = getattr(active_terminal, "system_console", None)
    if system_console is not None and hasattr(system_console, "log"):
        try:
            system_console.log(f"Uncaught UI exception: {headline}", "ERROR")
        except Exception:
            pass

    notifier = getattr(active_terminal, "_push_notification", None)
    if callable(notifier):
        try:
            notifier(
                "Uncaught UI exception",
                f"{headline}. Details were written to {log_path}.",
                level="ERROR",
                source="runtime",
                dedupe_seconds=10.0,
            )
        except Exception:
            pass

    return log_path
