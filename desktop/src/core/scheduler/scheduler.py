import asyncio

class Scheduler:

    def __init__(self):
        self.tasks = []

    # ===================================
    # ADD TASK
    # ===================================

    def add_task(self, coro):
        self.tasks.append(coro)

    # ===================================
    # START
    # ===================================

    async def start(self):
        await asyncio.gather(*self.tasks)
