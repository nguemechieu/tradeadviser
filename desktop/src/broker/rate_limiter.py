import asyncio
import time


class RateLimiter:

    def __init__(self, rate=10):

        self.rate = rate
        self.tokens = rate
        self.last = time.time()

    async def wait(self):

        now = time.time()

        elapsed = now - self.last

        self.tokens += elapsed * self.rate

        if self.tokens > self.rate:
            self.tokens = self.rate

        if self.tokens < 1:
            await asyncio.sleep((1 - self.tokens) / self.rate)

        self.tokens -= 1

        self.last = time.time()
