"""Shared Pydantic contracts for the hybrid Sopotek architecture."""

from shared.contracts.base import (
    CorrelationIds,
    SharedModel,
    UserContext,
    utc_now,
    ApiResponseEnvelope,
    BrokerIdentifier,
    SymbolIdentifier,
    SessionContext,
)

# Delay imports of trading, session, and market to avoid circular import with desktop module
def _lazy_import_trading():
    from shared.contracts.trading import StrategySignal, SignalBundle, DecisionIntent
    return StrategySignal, SignalBundle, DecisionIntent

def _lazy_import_session():
    from shared.contracts.session import BrokerSessionSummary, SessionState
    return BrokerSessionSummary, SessionState

def _lazy_import_market():
    from shared.contracts.market import FeatureSnapshot, SymbolSnapshot
    return FeatureSnapshot, SymbolSnapshot

# Import on first access (lazy)
_trading_imports = None
_session_imports = None
_market_imports = None

def __getattr__(name):
    global _trading_imports, _session_imports, _market_imports
    
    if name in ('StrategySignal', 'SignalBundle', 'DecisionIntent'):
        if _trading_imports is None:
            _trading_imports = _lazy_import_trading()
        idx = {'StrategySignal': 0, 'SignalBundle': 1, 'DecisionIntent': 2}[name]
        return _trading_imports[idx]
    
    if name in ('BrokerSessionSummary', 'SessionState'):
        if _session_imports is None:
            _session_imports = _lazy_import_session()
        idx = {'BrokerSessionSummary': 0, 'SessionState': 1}[name]
        return _session_imports[idx]
    
    if name in ('FeatureSnapshot', 'SymbolSnapshot'):
        if _market_imports is None:
            _market_imports = _lazy_import_market()
        idx = {'FeatureSnapshot': 0, 'SymbolSnapshot': 1}[name]
        return _market_imports[idx]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CorrelationIds",
    "SharedModel",
    "UserContext",
    "utc_now",
    "ApiResponseEnvelope",
    "BrokerIdentifier",
    "SymbolIdentifier",
    "SessionContext",
    "StrategySignal",
    "SignalBundle",
    "DecisionIntent",
    "BrokerSessionSummary",
    "SessionState",
    "FeatureSnapshot",
    "SymbolSnapshot",
]

