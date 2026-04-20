import asyncio
from uuid import uuid4

from agents.signal_fanout import run_signal_agents_parallel
from event_bus.event_types import EventType


class EventDrivenAgentRuntime:
    def __init__(
        self,
        bus,
        signal_agent=None,
        signal_agents=None,
        signal_consensus_agent=None,
        signal_aggregation_agent=None,
        regime_agent=None,
        portfolio_agent=None,
        risk_agent=None,
        execution_agent=None,
    ):
        self.bus = bus
        self.signal_agents = list(signal_agents or ([] if signal_agent is None else [signal_agent]))
        self.signal_agent = self.signal_agents[0] if self.signal_agents else signal_agent
        self.signal_consensus_agent = signal_consensus_agent
        self.signal_aggregation_agent = signal_aggregation_agent
        self.regime_agent = regime_agent
        self.portfolio_agent = portfolio_agent
        self.risk_agent = risk_agent
        self.execution_agent = execution_agent
        self._decision_futures = {}
        self._started = False

        self.bus.subscribe(EventType.MARKET_DATA, self._on_market_data)
        self.bus.subscribe(EventType.SIGNAL, self._on_signal)
        self.bus.subscribe(EventType.RISK_APPROVED, self._on_risk_approved)
        self.bus.subscribe(EventType.ORDER_REQUEST, self._on_order_request)
        self.bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)

    async def _process_optional_agent(self, agent, context):
        if agent is None:
            return dict(context or {})
        return await agent.process(dict(context or {}))

    async def start(self):
        if self._started:
            return
        self.bus.run_in_background()
        self._started = True

    async def stop(self):
        pending = list(self._decision_futures.values())
        self._decision_futures = {}
        for future in pending:
            if future is not None and not future.done():
                future.cancel()
        if self._started:
            await self.bus.shutdown()
        self._started = False

    async def process_market_data(self, context, timeout=None):
        working = dict(context or {})
        decision_id = str(working.get("decision_id") or uuid4().hex).strip() or uuid4().hex
        working["decision_id"] = decision_id

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._decision_futures[decision_id] = future
        await self.bus.publish(EventType.MARKET_DATA, working)
        try:
            if self.bus.is_running:
                return await asyncio.wait_for(future, timeout=timeout)

            while not future.done():
                await self.bus.dispatch_once()
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._decision_futures.pop(decision_id, None)

    async def _on_market_data(self, event):
        context = dict(getattr(event, "data", {}) or {})
        if not context.get("symbol"):
            return
        if len(self.signal_agents) <= 1 and self.signal_aggregation_agent is None:
            if self.signal_agent is None:
                self._complete(context)
                return
            context = await self.signal_agent.process(context)
        else:
            context = await run_signal_agents_parallel(self.signal_agents, context)
            if self.signal_consensus_agent is not None:
                context = await self.signal_consensus_agent.process(context)
            if self.signal_aggregation_agent is not None:
                context = await self.signal_aggregation_agent.process(context)
        if not isinstance(context.get("signal"), dict):
            self._complete(context)
            return
        await self.bus.publish(EventType.SIGNAL, context)

    async def _on_signal(self, event):
        context = dict(getattr(event, "data", {}) or {})
        if not isinstance(context.get("signal"), dict):
            self._complete(context)
            return
        context = await self._process_optional_agent(self.regime_agent, context)
        context = await self._process_optional_agent(self.portfolio_agent, context)
        context = await self._process_optional_agent(self.risk_agent, context)
        review = dict(context.get("trade_review") or {})
        if not review.get("approved"):
            self._complete(context)
            return
        await self.bus.publish(EventType.RISK_APPROVED, context)

    async def _on_risk_approved(self, event):
        context = dict(getattr(event, "data", {}) or {})
        if not context.get("symbol"):
            return
        review = dict(context.get("trade_review") or {})
        if not review.get("approved"):
            self._complete(context)
            return
        await self.bus.publish(EventType.ORDER_REQUEST, context)

    async def _on_order_request(self, event):
        context = dict(getattr(event, "data", {}) or {})
        if not context.get("symbol"):
            return
        if self.execution_agent is None:
            self._complete(context)
            return
        context = await self.execution_agent.process(context)
        if context.get("execution_result") is None:
            self._complete(context)
            return
        await self.bus.publish(EventType.ORDER_FILLED, context)

    async def _on_order_filled(self, event):
        context = dict(getattr(event, "data", {}) or {})
        if not context.get("symbol"):
            return
        self._complete(context)

    def _complete(self, context):
        decision_id = str((context or {}).get("decision_id") or "").strip()
        if not decision_id:
            return
        future = self._decision_futures.get(decision_id)
        if future is not None and not future.done():
            future.set_result(dict(context or {}))
