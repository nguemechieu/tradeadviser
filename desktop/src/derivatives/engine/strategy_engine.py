from __future__ import annotations

import importlib
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from derivatives.core.config import StrategyConfig
from derivatives.core.live_market_cache import LiveMarketCache
from derivatives.core.models import BrokerRoute, TradingSignal
from derivatives.engine.strategies import BaseStrategy, MLStrategy
from derivatives.ml.feature_engineering.features import build_feature_vector

if TYPE_CHECKING:
    from events.event_bus import EventBus


class StrategyEngine:
    def __init__(
        self,
        event_bus: EventBus,
        cache: LiveMarketCache,
        *,
        config: StrategyConfig | None = None,
        inference_engine=None,
        route: BrokerRoute | Mapping[str, BrokerRoute] | Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.config = config or StrategyConfig()
        self.inference_engine = inference_engine
        self.route = route
        self.logger = logger or logging.getLogger("DerivativesStrategyEngine")
        self.strategies: list[BaseStrategy] = []
        self._cooldowns: dict[tuple[str, str], datetime] = {}

        self.bus.subscribe("market.ticker", self._on_market_ticker)
        self.bus.subscribe("scheduler.tick", self._on_scheduler_tick)

    def register_strategy(self, strategy: BaseStrategy) -> BaseStrategy:
        self.strategies.append(strategy)
        return strategy

    def load_plugins(self, class_paths: list[str] | None = None) -> list[BaseStrategy]:
        loaded: list[BaseStrategy] = []
        for class_path in list(class_paths or self.config.strategy_classes):
            module_name, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            strategy_class = getattr(module, class_name)
            params = dict(
                self.config.strategy_params.get(class_name)
                or self.config.strategy_params.get(getattr(strategy_class, "name", ""), {})
                or {}
            )
            if issubclass(strategy_class, MLStrategy):
                params.setdefault("inference_engine", self.inference_engine)
            loaded.append(self.register_strategy(strategy_class(**params)))
        return loaded

    async def _on_market_ticker(self, event) -> None:
        payload = dict(event.data or {})
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            return
        if self.config.symbols and symbol not in set(self.config.symbols):
            return

        price = float(payload.get("price") or 0.0)
        if price <= 0.0:
            return

        now = datetime.now(timezone.utc)
        for signal in self._evaluate_symbol_signals(symbol, price=price, now=now):
            if signal.confidence < float(self.config.min_confidence):
                continue
            self._cooldowns[(signal.strategy_name, symbol)] = now
            await self.bus.publish(
                "signal.generated",
                signal.to_dict(),
                source=f"strategy:{signal.strategy_name}",
            )

    async def evaluate_symbol(self, symbol: str) -> list[TradingSignal]:
        price = self.cache.latest_price(symbol)
        if price is None:
            return []
        return self._evaluate_symbol_signals(symbol, price=float(price), now=datetime.now(timezone.utc))

    async def _on_scheduler_tick(self, event) -> None:
        payload = dict(event.data or {})
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            return
        for signal in await self.evaluate_symbol(symbol):
            if signal.confidence < float(self.config.min_confidence):
                continue
            await self.bus.publish(
                "signal.generated",
                signal.to_dict(),
                source=f"strategy:{signal.strategy_name}",
            )

    def _evaluate_symbol_signals(self, symbol: str, *, price: float, now: datetime) -> list[TradingSignal]:
        features = build_feature_vector(symbol, self.cache)
        history = self.cache.price_series(symbol)
        signals: list[TradingSignal] = []
        route = self._resolve_route(symbol)
        for strategy in self.strategies:
            if len(history) < strategy.min_history:
                continue
            last_signal_at = self._cooldowns.get((strategy.name, symbol))
            if last_signal_at is not None:
                elapsed = (now - last_signal_at).total_seconds()
                if elapsed < float(self.config.signal_cooldown_seconds):
                    continue
            signal = strategy.evaluate(
                symbol=symbol,
                price=price,
                features=features,
                history=history,
                route=route,
                now=now,
            )
            if signal is not None:
                signals.append(signal)
        return signals

    def _resolve_route(self, symbol: str) -> BrokerRoute | None:
        if callable(self.route):
            try:
                resolved = self.route(symbol)
            except Exception:
                self.logger.exception("strategy_route_resolution_failed symbol=%s", symbol)
                return None
            return resolved if isinstance(resolved, BrokerRoute) else None
        if isinstance(self.route, Mapping):
            candidate = self.route.get(symbol) or self.route.get(str(symbol).upper())
            return candidate if isinstance(candidate, BrokerRoute) else None
        return self.route if isinstance(self.route, BrokerRoute) else None
