class ReasoningAgent:
    def __init__(self, decision_engine, event_bus):
        self.engine = decision_engine
        self.bus = event_bus

    async def on_signal(self, ctx):
        decision = await self.engine.decide(ctx)
        await self.bus.publish("decision.made", decision)