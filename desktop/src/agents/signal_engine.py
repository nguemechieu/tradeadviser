from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from core.event_bus import AsyncEventBus
from core.event_bus.event_types import EventType
from core.models import Signal, SignalStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return _utc_now()


def _timeframe_to_seconds(value: Any, default: int = 0) -> int:
    text = str(value or "").strip().lower()
    if not text:
        return int(default)
    try:
        amount = int(text[:-1] or 1)
    except Exception:
        return int(default)

    suffix = text[-1]
    if suffix == "s":
        return amount
    if suffix == "m":
        return amount * 60
    if suffix == "h":
        return amount * 3600
    if suffix == "d":
        return amount * 86400
    return int(default)


@dataclass(slots=True)
class SignalCollection:
    symbol: str
    signals: list[Signal]
    stale_strategies: list[str]


class SignalEngine:
    """
    Strategy-facing signal engine + lifecycle manager.

    Responsibilities:
    - call strategies to generate raw signals
    - normalize strategy output into Signal objects
    - publish signal-created events
    - collect fresh/stale signals by symbol
    """

    def __init__(
            self,
            strategy_registry: Any | None = None,
            *,
            event_bus: AsyncEventBus | None = None,
            signal_ttl_seconds: float = 900.0,
    ) -> None:
        self.strategy_registry = strategy_registry
        self.bus = event_bus
        self.signal_ttl_seconds = max(30.0, float(signal_ttl_seconds))

        # Optional compat attributes expected elsewhere in your app
        self.alpha_aggregator = getattr(strategy_registry, "alpha_aggregator", None)
        self.regime_engine = getattr(strategy_registry, "regime_engine", None)

    def attach(self, event_bus: AsyncEventBus) -> None:
        self.bus = event_bus

    async def ingest(
            self,
            signal: Signal | Mapping[str, Any],
            *,
            source: str = "signal_engine",
    ) -> Signal:
        normalized = self.normalize(signal)
        if self.bus is not None:
            await self.bus.publish(
                EventType.SIGNAL_CREATED,
                normalized,
                priority=58,
                source=source,
            )
        return normalized

    def normalize(self, signal: Signal | Mapping[str, Any]) -> Signal:
        if not isinstance(signal, Signal):
            signal = Signal(**dict(signal or {}))

        metadata = dict(signal.metadata or {})
        metadata.setdefault("source_strategy", signal.source_strategy or signal.strategy_name)
        metadata.setdefault("signal_id", signal.id)

        return signal.transition(
            stage="normalized",
            status=SignalStatus.CREATED,
            metadata=metadata,
            note=f"Normalized signal from {signal.source_strategy or signal.strategy_name}",
            timestamp=signal.timestamp,
        )

    def collect(
            self,
            symbol: str,
            strategy_signals: Mapping[str, Mapping[str, Signal] | dict[str, Signal]],
            *,
            now: datetime | None = None,
    ) -> SignalCollection:
        reference_time = now or _utc_now()
        bucket = strategy_signals.get(symbol, {})
        fresh: list[Signal] = []
        stale_strategies: list[str] = []

        for strategy_name, signal in dict(bucket or {}).items():
            normalized = self.normalize(signal)
            timestamp = _coerce_datetime(getattr(normalized, "timestamp", None))
            freshness_window = timedelta(seconds=self.signal_ttl(normalized))

            if reference_time - timestamp > freshness_window:
                stale_strategies.append(str(strategy_name))
                continue

            fresh.append(normalized)

        return SignalCollection(
            symbol=str(symbol or "").strip(),
            signals=fresh,
            stale_strategies=stale_strategies,
        )

    def signal_ttl(self, signal: Signal) -> float:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        timeframe_seconds = _timeframe_to_seconds(metadata.get("timeframe"), default=0)
        if timeframe_seconds > 0:
            return max(self.signal_ttl_seconds, float(timeframe_seconds) * 1.5)
        return self.signal_ttl_seconds

    def _resolve_strategy(self, strategy_name: str) -> Any | None:
        registry = self.strategy_registry
        if registry is None:
            return None

        # Preferred internal resolver
        resolver = getattr(registry, "_resolve_strategy", None)
        if callable(resolver):
            try:
                strategy = resolver(strategy_name)
                if strategy is not None:
                    return strategy
            except Exception:
                pass

        # Common public APIs
        for attr in ("get", "get_strategy", "resolve", "resolve_strategy"):
            fn = getattr(registry, attr, None)
            if callable(fn):
                try:
                    strategy = fn(strategy_name)
                    if strategy is not None:
                        return strategy
                except Exception:
                    continue

        return None

    async def generate_signal(
            self,
            *,
            candles: list[dict[str, Any]] | list[Any],
            dataset: Any = None,
            strategy_name: str,
            symbol: str,

    ) -> dict[str, Any] | None:
        """
        Compatibility API for TradingCore.

        Returns a normalized dict signal or None.
        """
        strategy = self._resolve_strategy(strategy_name)
        if strategy is None:
            return None

        timeframe = str(
            getattr(dataset, "timeframe", "1h")
            or ""
        ).strip()

        raw_signal = None

        # Try common strategy APIs in descending order of preference.
        for method_name in (
                "generate_signal",
                "create_signal",
                "evaluate_signal",
                "signal",
                "run",
        ):
            method = getattr(strategy, method_name, None)
            if not callable(method):
                continue

            try:
                raw_signal = method(
                    candles=candles,
                    dataset=dataset,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            except TypeError:
                try:
                    raw_signal = method(candles, dataset=dataset, symbol=symbol, timeframe=timeframe)
                except TypeError:
                    try:
                        raw_signal = method(candles)
                    except Exception:
                        continue
                except Exception:
                    continue
            except Exception:
                continue

            if raw_signal is not None:
                break

        if raw_signal is None:
            return None

        if hasattr(raw_signal, "__await__"):
            raw_signal = await raw_signal

        if raw_signal is None:
            return None

        if isinstance(raw_signal, Signal):
            normalized_signal = self.normalize(raw_signal)
            signal_dict = self._signal_to_dict(normalized_signal)
        elif isinstance(raw_signal, Mapping):
            raw_payload = dict(raw_signal)
            raw_payload.setdefault("symbol", str(symbol or "").strip().upper())
            raw_payload.setdefault("strategy_name", strategy_name)
            raw_payload.setdefault("source_strategy", strategy_name)
            raw_payload.setdefault("timestamp", _utc_now())
            raw_payload.setdefault("metadata", {})
            raw_payload["metadata"] = dict(raw_payload.get("metadata") or {})
            raw_payload["metadata"].setdefault("timeframe", timeframe)

            normalized_signal = self.normalize(Signal(**raw_payload))
            signal_dict = self._signal_to_dict(normalized_signal)
        else:
            return None

        if self.bus is not None:
            await self.bus.publish(
                EventType.SIGNAL_CREATED,
                signal_dict,
                priority=58,
                source=strategy_name,
            )

        return signal_dict

    def _signal_to_dict(self, signal: Signal) -> dict[str, Any]:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        return {
            "id": getattr(signal, "id", None),
            "symbol": getattr(signal, "symbol", None),
            "side": getattr(signal, "side", None),
            "amount": getattr(signal, "amount", None),
            "price": getattr(signal, "price", None),
            "confidence": getattr(signal, "confidence", 0.0),
            "reason": getattr(signal, "note", None) or metadata.get("reason"),
            "strategy_name": getattr(signal, "strategy_name", None),
            "source_strategy": getattr(signal, "source_strategy", None),
            "timestamp": getattr(signal, "timestamp", None),
            "status": getattr(signal, "status", None),
            "stage": getattr(signal, "stage", None),
            "type": metadata.get("type", "market"),
            "metadata": metadata,
        }
