"""Regime classification agent for symbol-level decision enrichment.

This module exposes a lightweight agent that builds a regime snapshot from the
current market context, enriches the incoming signal payload when possible,
publishes a regime event, and records the classification in agent memory.
"""

from events.event import Event
from events.event_bus.event_types import EventType

from agents.base_agent import BaseAgent


class RegimeAgent(BaseAgent):
    """Agent that computes, enriches, and records regime metadata.

    This agent runs after signal generation and before execution decisions. It
    computes a regime snapshot from the current market context, attaches that
    snapshot to the working context, enriches the signal payload when possible,
    emits a regime event to the event bus, and stores a memory record for audit
    or replay use cases.
    """

    def __init__(self, snapshot_builder, memory=None, event_bus=None):
        """Create a new regime agent.

        Parameters:
            snapshot_builder: Callable that returns a regime snapshot from the
                provided symbol, signal, candles, dataset, and timeframe.
            memory: Optional memory store used to remember classification events.
            event_bus: Optional event bus used to publish regime events.
        """
        super().__init__("RegimeAgent", memory=memory, event_bus=event_bus)
        self.snapshot_builder = snapshot_builder

    async def process(self, context):
        """Process the incoming context and attach regime classification data.

        The agent expects a working context containing keys such as `symbol`,
        `signal`, `candles`, `dataset`, and `timeframe`. It preserves the input
        context by copying it, then returns the enriched context for downstream
        agents.
        """
        working = dict(context or {})

        # Normalize the symbol and preserve the original decision ID for memory.
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        signal = working.get("signal")

        snapshot = self.snapshot_builder(
            symbol=symbol,
            signal=signal,
            candles=working.get("candles") or [],
            dataset=working.get("dataset"),
            timeframe=working.get("timeframe"),
        )

        # Store the raw snapshot on the working context for later agents.
        working["regime_snapshot"] = snapshot

        # If the incoming signal is a dict, enrich it with regime details so
        # downstream components can consume both the summary regime and full
        # snapshot without altering the original signal object.
        if isinstance(signal, dict) and snapshot:
            enriched = dict(signal)
            enriched.setdefault("regime", snapshot.get("regime"))
            enriched["regime_snapshot"] = dict(snapshot)
            working["signal"] = enriched
            signal = enriched
            # 🚨 NEW: Regime-based trade filter
            regime = (snapshot or {}).get("regime")

            if regime in ["SIDEWAYS", "LOW_VOLATILITY"]:
             working["trade_allowed"] = False
             working["block_reason"] = f"Bad regime: {regime}"
            else:
              working["trade_allowed"] = True

        # Publish a regime classification event for external listeners.
        if self.event_bus is not None:
            await self.event_bus.publish(Event(EventType.REGIME, dict(snapshot or {})))

        # Record the classification event in memory for debugging and replay.
        self.remember(
            "classified",
            {
                "regime": (snapshot or {}).get("regime"),
                "volatility": (snapshot or {}).get("volatility"),
                "timeframe": (snapshot or {}).get("timeframe"),
                "strategy_name": signal.get("strategy_name") if isinstance(signal, dict) else None,
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working
