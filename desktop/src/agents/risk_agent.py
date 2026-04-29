from events.event_bus.event_types import EventType
from events.event import Event


from agents.base_agent import BaseAgent


class RiskAgent(BaseAgent):
    """Coordinate risk review for trade signals before they proceed through the pipeline. Acts as
    a gatekeeper that can approve, modify, or block trades based on an external reviewer and
    current context.

    The agent inspects the working decision context, normalizes the embedded signal, and delegates
    to a reviewer callable to perform domain-specific risk checks. It then updates the context with
    approval status, reasons, and memory traces, and optionally emits risk alerts on the event bus
    when trades are blocked."""

    def __init__(self, reviewer, memory=None, event_bus=None):
        super().__init__("RiskAgent", memory=memory, event_bus=event_bus)
        self.reviewer = reviewer

    async def process(self, context):
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        signal = working.get("signal")

        # 🚨 FIX 1: NEVER return False → always return context
        if not working.get("trade_allowed", True):
            reason = working.get("block_reason", "Blocked by regime")
            print(f"🚫 Blocked by regime for {symbol}: {reason}")

            working["halt_pipeline"] = True
            working["risk_blocked"] = True
            working["risk_reason"] = reason

            self.remember(
                "blocked_by_regime",
                {"reason": reason},
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        # ❌ No valid signal → stop pipeline
        if not isinstance(signal, dict):
            working["halt_pipeline"] = True

            self.remember(
                "skipped",
                {
                    "reason": working.get("news_bias_reason") or "No active signal.",
                    "timeframe": working.get("timeframe"),
                },
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        # Normalize signal
        signal = dict(signal)
        signal.setdefault("decision_id", decision_id)
        working["signal"] = signal

        # 🚀 Run risk reviewer
        review = await self.reviewer(
            symbol=symbol,
            signal=signal,
            dataset=working.get("dataset"),
            timeframe=working.get("timeframe"),
            regime_snapshot=working.get("regime_snapshot"),
            portfolio_snapshot=working.get("portfolio_snapshot"),
        )

        working["trade_review"] = review

        # 🔍 DEBUG (VERY IMPORTANT)
        print(f"🧠 Risk review for {symbol}: {review}")

        # 🚨 FIX 2: Safe approval check
        approved = bool((review or {}).get("approved"))

        # ❌ REJECTED
        if not approved:
            reason = (review or {}).get("reason", "Unknown risk rejection")

            print(f"❌ Risk rejected {symbol}: {reason}")

            working["halt_pipeline"] = True
            working["risk_blocked"] = True
            working["risk_reason"] = reason

            if self.event_bus is not None:
                await self.event_bus.publish(
                    Event(
                        EventType.RISK_ALERT,
                        {
                            "symbol": symbol,
                            "decision_id": decision_id,
                            "stage": (review or {}).get("stage"),
                            "reason": reason,
                            "strategy_name": signal.get("strategy_name"),
                            "timeframe": (review or {}).get("timeframe") or working.get("timeframe"),
                            "side": signal.get("side"),
                        },
                    )
                )

            self.remember(
                "rejected",
                {
                    "stage": (review or {}).get("stage"),
                    "reason": reason,
                    "strategy_name": signal.get("strategy_name"),
                    "timeframe": (review or {}).get("timeframe") or working.get("timeframe"),
                    "approved": False,
                },
                symbol=symbol,
                decision_id=decision_id,
            )

            return working

        # ✅ APPROVED
        print(f"✅ Risk approved for {symbol}")

        working["risk_blocked"] = False
        working["risk_reason"] = None

        self.remember(
            "approved",
            {
                "amount": (review or {}).get("amount"),
                "price": (review or {}).get("price"),
                "strategy_name": (review or {}).get("strategy_name"),
                "timeframe": (review or {}).get("timeframe"),
                "side": (review or {}).get("side"),
                "execution_strategy": (review or {}).get("execution_strategy"),
                "approved": True,
            },
            symbol=symbol,
            decision_id=decision_id,
        )

        return working