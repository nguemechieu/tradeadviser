"""Decision service interface for server-side signal fusion and reasoning handoff."""

from __future__ import annotations

from typing import Protocol

from sopotek.shared.contracts.trading import DecisionIntent, SignalBundle


class DecisionService(Protocol):
    """Server-side decision interface.

    The server is authoritative for creating trade intents from signal bundles.
    Desktop may request reviews but must not construct final autonomous intents.
    """

    async def decide(self, bundle: SignalBundle) -> DecisionIntent:
        ...


class InMemoryDecisionService:
    """Placeholder decision service for the initial server skeleton."""

    async def decide(self, bundle: SignalBundle) -> DecisionIntent:
        first_signal = bundle.signals[0]
        return DecisionIntent(
            intent_id=f"intent_{bundle.bundle_id}",
            identifier=bundle.identifier,
            action="buy" if first_signal.side.value == "buy" else "sell",
            confidence=first_signal.confidence,
            selected_strategy=first_signal.strategy_name,
            supporting_agents=[signal.strategy_name for signal in bundle.signals],
            rejected_agents=[],
            reasons=first_signal.reasons,
        )

