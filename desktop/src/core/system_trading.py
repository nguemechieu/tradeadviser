"""Backward-compatible trading runtime entry point.

Historically the desktop app imported ``core.sopotek_trading.SopotekTrading``.
The runtime implementation now lives in :mod:`core.trading_core`, so this
module keeps the old import path working for the app, tests, and any older
integration code.
"""

import asyncio

from .trading_core import MultiSymbolOrchestrator, TradingCore


__all__ = [
   
    "TradingCore",
    "MultiSymbolOrchestrator",
    "asyncio",
]
