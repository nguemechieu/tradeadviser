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
from shared.contracts.trading import (
    StrategySignal,
    SignalBundle,
    DecisionIntent,
)
from shared.contracts.session import (
    BrokerSessionSummary,
    SessionState,
)
from shared.contracts.market import (
    FeatureSnapshot,
    SymbolSnapshot,
)

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

