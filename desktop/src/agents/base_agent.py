class BaseAgent:
    def __init__(self, name, memory=None, event_bus=None):
        self.name = str(name or self.__class__.__name__).strip() or self.__class__.__name__
        self.memory = memory
        self.event_bus = event_bus

    async def process(self, context):
        raise NotImplementedError

    def remember(self, stage, payload=None, symbol=None, decision_id=None):
        if self.memory is None:
            return None
        return self.memory.store(
            agent=self.name,
            stage=stage,
            payload=payload or {},
            symbol=symbol,
            decision_id=decision_id,
        )
