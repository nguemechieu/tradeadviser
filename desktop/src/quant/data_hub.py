import asyncio

from quant.data_models import DatasetRequest, SymbolDatasetSnapshot
from quant.feature_pipeline import FeaturePipeline


class QuantDataHub:
    def __init__(self, controller=None, market_data_repository=None, broker=None, feature_pipeline=None):
        self.controller = controller
        self.market_data_repository = market_data_repository
        self.broker = broker or getattr(controller, "broker", None)
        self.feature_pipeline = feature_pipeline or FeaturePipeline()

    def _controller_exchange(self):
        controller = self.controller
        if controller is None:
            return None
        resolver = getattr(controller, "_active_exchange_code", None)
        if callable(resolver):
            try:
                return resolver()
            except Exception:
                return None
        return None

    def _cached_frame(self, symbol, timeframe):
        controller = self.controller
        if controller is None:
            return None
        caches = getattr(controller, "candle_buffers", None)
        if hasattr(caches, "get"):
            symbol_bucket = caches.get(symbol)
            if hasattr(symbol_bucket, "get"):
                frame = symbol_bucket.get(timeframe)
                if frame is not None:
                    return self.feature_pipeline.normalize_candles(frame.values.tolist() if hasattr(frame, "values") else frame)

        legacy = getattr(controller, "candle_buffer", None)
        if hasattr(legacy, "get"):
            symbol_bucket = legacy.get(symbol)
            if hasattr(symbol_bucket, "get"):
                frame = symbol_bucket.get(timeframe)
                if frame is not None:
                    return self.feature_pipeline.normalize_candles(frame.values.tolist() if hasattr(frame, "values") else frame)
        return None

    async def _fetch_live_candles(self, symbol, timeframe, limit):
        controller = self.controller
        if controller is not None and hasattr(controller, "_safe_fetch_ohlcv"):
            data = await controller._safe_fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if data:
                return data, "live_controller"

        broker = self.broker
        if broker is not None and hasattr(broker, "fetch_ohlcv"):
            data = await broker.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if data:
                return data, "live_broker"
        return [], ""

    async def _load_repository_candles(self, symbol, timeframe, limit, exchange):
        controller = self.controller
        if controller is not None and hasattr(controller, "_load_candles_from_db"):
            rows = await controller._load_candles_from_db(symbol, timeframe=timeframe, limit=limit)
            if rows:
                return rows, "repository"

        repository = self.market_data_repository
        if repository is None:
            return [], ""
        rows = await asyncio.to_thread(repository.get_candles, symbol, timeframe, limit, exchange)
        return (rows or []), ("repository" if rows else "")

    async def _persist_live_candles(self, symbol, timeframe, candles, exchange):
        if not candles:
            return
        controller = self.controller
        if controller is not None and hasattr(controller, "_persist_candles_to_db"):
            try:
                await controller._persist_candles_to_db(symbol, timeframe, candles)
                return
            except Exception:
                return
        repository = self.market_data_repository
        if repository is not None:
            try:
                await asyncio.to_thread(repository.save_candles, symbol, timeframe, candles, exchange)
            except Exception:
                return

    async def get_symbol_dataset(self, request: DatasetRequest | None = None, **kwargs):
        req = request or DatasetRequest(**kwargs)
        symbol = str(req.symbol or "").strip().upper()
        timeframe = str(req.timeframe or "1h").strip() or "1h"
        limit = max(1, int(req.limit or 300))
        exchange = req.exchange or self._controller_exchange()

        cached = self._cached_frame(symbol, timeframe)
        if cached is not None and not cached.empty:
            return SymbolDatasetSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                exchange=exchange,
                source="cache",
                frame=cached.tail(limit).reset_index(drop=True),
                metadata={"rows": int(len(cached.tail(limit))), "feature_version": self.feature_pipeline.FEATURE_VERSION},
            )

        candles = []
        source = ""
        if req.prefer_live:
            candles, source = await self._fetch_live_candles(symbol, timeframe, limit)
            if candles:
                await self._persist_live_candles(symbol, timeframe, candles, exchange)

        if not candles:
            candles, source = await self._load_repository_candles(symbol, timeframe, limit, exchange)

        frame = self.feature_pipeline.normalize_candles(candles)
        metadata = {
            "rows": int(len(frame)) if not frame.empty else 0,
            "feature_version": self.feature_pipeline.FEATURE_VERSION,
        }
        if not frame.empty:
            metadata["start_timestamp"] = frame.iloc[0]["timestamp"]
            metadata["end_timestamp"] = frame.iloc[-1]["timestamp"]

        return SymbolDatasetSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            exchange=exchange,
            source=source or "empty",
            frame=frame.reset_index(drop=True),
            metadata=metadata,
        )
