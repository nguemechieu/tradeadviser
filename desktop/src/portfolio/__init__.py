
"""Lazy portfolio package exports."""

from __future__ import annotations

from importlib import import_module

def __getattr__(name: str):
    if name != "PortfolioEngine":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module("portfolio.portfolio_engine"), name)

from portfolio.portfolio_engine import PortfolioEngine

__all__ = ["PortfolioEngine"]
