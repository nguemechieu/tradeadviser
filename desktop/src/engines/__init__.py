"""Lazy package exports for engine modules."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ExecutionEngine", "FuturesEngine", "OptionsEngine", "RiskEngine"]

_EXPORTS = {
    "ExecutionEngine": "engines.execution_engine",
    "FuturesEngine": "engines.futures_engine",
    "OptionsEngine": "engines.options_engine",
    "RiskEngine": "engines.risk_engine",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)
