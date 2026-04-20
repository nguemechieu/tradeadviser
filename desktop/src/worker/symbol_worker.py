"""Worker layer for symbol-specific trading execution and signal orchestration.

This module defines `SymbolWorker`, an asyncio-driven task that fetches OHLCV
candles, generates strategy signals, publishes debug telemetry, and delegates
trade execution through either a centralized controller or a direct execution
manager.
"""

import asyncio
import inspect
import logging
import traceback


class SymbolWorker:
    """Async worker that evaluates a single symbol and routes signals to execution.

    The worker supports an optional centralized signal pipeline exposed by the
    controller. When no centralized processor is available, it fetches OHLCV data
    from the broker and runs the configured strategy directly.

    Optional controller integration points:
    - `is_symbol_enabled_for_autotrade(symbol)` to gate execution.
    - `_safe_fetch_ohlcv(symbol, timeframe, limit)` to retrieve candle data.
    - `publish_ai_signal(symbol, signal, candles=...)` for AI signal telemetry.
    - `publish_strategy_debug(symbol, signal, candles=..., features=...)` for debug output.
    - `trading_system.process_symbol(...)` or `trading_system.process_signal(...)` for centralized signal handling.
    """

    def __init__(
        self,
        symbol,
        broker,
        strategy,
        execution_manager,
        timeframe,
        limit,
        controller=None,
        startup_delay=0.0,
        poll_interval=2.0,
        signal_processor=None,
    ):
        """Initialize the worker for a symbol and trading context.

        Parameters:
            symbol: Symbol string to evaluate.
            broker: Broker implementation used to fetch OHLCV data.
            strategy: Strategy object with `generate_signal(candles)`.
            execution_manager: Execution manager used for direct trade execution.
            timeframe: Candle timeframe used for signal generation.
            limit: Number of candles to request for each evaluation.
            controller: Optional controller exposing centralized signal and telemetry hooks.
            startup_delay: Delay in seconds before the first loop iteration.
            poll_interval: Minimum delay between loop iterations (enforced as >= 2.0).
            signal_processor: Optional custom processor that can handle symbol signal evaluation.
        """
        self.logger = logging.getLogger("SymbolWorker")

        self.symbol = symbol
        self.broker = broker
        self.strategy = strategy
        self.execution_manager = execution_manager
        self.timeframe = timeframe
        self.limit = limit
        self.controller = controller
        self.running = True
        self.startup_delay = max(0.0, float(startup_delay))
        self.poll_interval = max(2.0, float(poll_interval))
        self.signal_processor = signal_processor

    async def _run_centralized_signal_pipeline(self):
        """Attempt a centralized controller signal processing step.

        If the worker was configured with `signal_processor`, it is used first.
        Otherwise, the controller's `trading_system.process_symbol` handler is
        used when available.
        """
        processor = self.signal_processor
        if processor is None and self.controller is not None:
            trading_system = getattr(self.controller, "trading_system", None)
            candidate = getattr(trading_system, "process_symbol", None)
            if callable(candidate):
                processor = candidate

        if not callable(processor):
            return False

        result = processor(
            self.symbol,
            timeframe=self.timeframe,
            limit=self.limit,
            publish_debug=True,
        )
        if inspect.isawaitable(result):
            await result
        return True


    async def run(self):
        """Run the symbol worker loop until `self.running` is stopped.

        The loop optionally respects controller-level autotrade enablement, then
        either processes a centralized signal pipeline or fetches OHLCV data,
        generates strategy signals, emits debug events, and executes trades.
        """
        if self.startup_delay > 0:
            await asyncio.sleep(self.startup_delay)

        while self.running:

            try:
                if self.controller and hasattr(self.controller, "is_symbol_enabled_for_autotrade"):
                    try:
                        enabled = self.controller.is_symbol_enabled_for_autotrade(self.symbol)
                    except Exception:
                        enabled = True
                    if not enabled:
                        await asyncio.sleep(self.poll_interval)
                        continue

                if await self._run_centralized_signal_pipeline():
                    await asyncio.sleep(self.poll_interval)
                    continue

                if self.controller and hasattr(self.controller, "_safe_fetch_ohlcv"):
                    fetch_ohlcv = self.controller._safe_fetch_ohlcv
                    try:
                        candles = await fetch_ohlcv(
                            self.symbol,
                            timeframe=self.timeframe,
                            limit=self.limit,
                        )
                    except TypeError:
                        candles = await fetch_ohlcv(self.symbol, self.timeframe, self.limit)
                else:
                    candles = await self.broker.fetch_ohlcv(
                        self.symbol,
                        timeframe=self.timeframe,
                        limit=self.limit
                    )

                signal = self.strategy.generate_signal(candles)
                features = None
                if hasattr(self.strategy, "compute_features"):
                    try:
                        features = self.strategy.compute_features(candles)
                    except Exception:
                        features = None

                display_signal = signal or {
                    "side": "hold",
                    "amount": 0.0,
                    "confidence": 0.0,
                    "reason": "No entry signal on the latest scan.",
                }
                if self.controller and hasattr(self.controller, "publish_ai_signal"):
                    self.controller.publish_ai_signal(self.symbol, display_signal, candles=candles)
                if self.controller and hasattr(self.controller, "publish_strategy_debug"):
                    self.controller.publish_strategy_debug(
                        self.symbol,
                        display_signal,
                        candles=candles,
                        features=features,
                    )

                if signal:
                    trading_system = getattr(self.controller, "trading_system", None) if self.controller is not None else None
                    process_signal = getattr(trading_system, "process_signal", None) if trading_system is not None else None
                    if callable(process_signal):
                        result = process_signal(self.symbol, signal, timeframe=self.timeframe)
                        if inspect.isawaitable(result):
                            result = await result
                        if result is False:
                            raise TypeError("process_signal failed")
                    else:
                        await self.execution_manager.execute(
                            symbol=self.symbol,
                            side=signal["side"],
                            amount=signal["amount"],
                            price=signal.get("price")
                        )

                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                self.logger.error("Worker error %s: %s", self.symbol, e)
                retry_delay = self.poll_interval
                if "429" in str(e):
                    retry_delay = max(self.poll_interval, 20.0)
                await asyncio.sleep(retry_delay)
                traceback.print_exc()

