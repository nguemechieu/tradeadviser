class TradingEngine:

    def __init__(
            self,
            market_data_engine,
            strategy,
            risk_engine,
            execution_manager,
            portfolio_manager
    ):
        self.market_data = market_data_engine
        self.strategy = strategy
        self.risk = risk_engine
        self.execution = execution_manager
        self.portfolio = portfolio_manager

    # ===================================
    # PROCESS SYMBOL (🔥 CORE)
    # ===================================
    async def process_symbol(self, symbol, timeframe="1h", limit=200):

        # 1. Get market data
        data = await self.market_data.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit
        )

        if not data:
            return None

        # 2. Generate signal
        signal = await self.strategy.generate_signal(symbol, data)

        if not signal:
            return None

        # 3. Risk validation
        approved = await self.risk.evaluate(signal)

        if not approved:
            return None

        # 4. Execute trade
        order = await self.execution.execute(signal)

        # 5. Update portfolio
        await self.portfolio.update(order)

        return order

    # ===================================
    # START ENGINE
    # ===================================
    async def start(self):
        if hasattr(self.market_data, "start"):
            await self.market_data.start()

    # ===================================
    # STOP ENGINE
    # ===================================
    async def stop(self):
        if hasattr(self.market_data, "stop"):
            await self.market_data.stop()