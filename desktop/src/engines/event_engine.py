import asyncio


class EventEngine:

    def __init__(self, bus):
        self.bus = bus

        self.running = False


    async def start(self):
        self.running = True

        await self.bus.start()

    async def stop(self):
        self.running = False
