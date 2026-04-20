
"""Lazy execution package exports."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ExecutionEngine", "OrderLifecycle"]

_EXPORTS = {
    "ExecutionEngine": "execution.execution_engine",
    "OrderLifecycle": "execution.execution_engine",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)

"""Execution package."""

from execution.execution_engine import ExecutionEngine, OrderLifecycle

__all__ = ["ExecutionEngine", "OrderLifecycle"]