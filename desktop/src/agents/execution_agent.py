from events.event import Event
from events.event_bus.event_types import EventType

from agents.base_agent import BaseAgent


class ExecutionAgent(BaseAgent):
    def __init__(self, executor, memory=None, event_bus=None):
        super().__init__("ExecutionAgent", memory=memory, event_bus=event_bus)
        self.executor = executor

    async def process(self, context):
        working = dict(context or {})
        symbol = str(working.get("symbol") or "").strip().upper()
        decision_id = working.get("decision_id")
        review = working.get("trade_review") or {}
        if not review.get("approved"):
            working["halt_pipeline"] = True
            self.remember(
                "skipped",
                {"reason": review.get("reason") or "Trade review was not approved.", "timeframe": review.get("timeframe")},
                symbol=symbol,
                decision_id=decision_id,
            )
            return working

        if self.event_bus is not None:
            await self.event_bus.publish(
                Event(
                    EventType.EXECUTION_PLAN,
                    {
                        "symbol": symbol,
                        "decision_id": decision_id,
                        "strategy_name": review.get("strategy_name"),
                        "timeframe": review.get("timeframe"),
                        "side": review.get("side"),
                        "amount": review.get("amount"),
                        "price": review.get("price"),
                        "execution_strategy": review.get("execution_strategy"),
                        "reason": review.get("reason"),
                    },
                )
            )

        result = await self.executor(review)
        working["execution_result"] = result
        status = str((result or {}).get("status") or "submitted").strip().lower() if isinstance(result, dict) else "submitted"
        self.remember(
            status,
            {
                "amount": review.get("amount"),
                "strategy_name": review.get("strategy_name"),
                "timeframe": review.get("timeframe"),
                "side": review.get("side"),
                "execution_strategy": review.get("execution_strategy"),
                "reason": (result or {}).get("reason") if isinstance(result, dict) else "",
                "approved": True,
            },
            symbol=symbol,
            decision_id=decision_id,
        )
        return working
