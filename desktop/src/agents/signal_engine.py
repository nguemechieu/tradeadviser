from __future__ import annotations

"""
InvestPro SignalEngine

Strategy-facing signal engine and lifecycle manager.

Responsibilities:
- Resolve strategies from StrategyRegistry
- Call strategy signal APIs safely
- Normalize raw strategy output into Signal-compatible payloads
- Publish signal-created events
- Collect fresh/stale signals by symbol
- Support dict/object/dataclass strategy outputs
- Provide stable compatibility API for TradingCore
"""

import inspect
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from core.event_bus import AsyncEventBus
except Exception:  # pragma: no cover
    AsyncEventBus = Any  # type: ignore

try:
    from core.event_bus.event_types import EventType
except Exception:  # pragma: no cover
    class EventType:  # type: ignore
        SIGNAL_CREATED = "signal.created"
        SIGNAL_FAILED = "signal.failed"

try:
    from core.signal import Signal, SignalStatus
except Exception:  # pragma: no cover
    try:
        from models.signal import Signal, SignalStatus
    except Exception:
        Signal = Any  # type: ignore

        class SignalStatus:  # type: ignore
            CREATED = "created"
            FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if value in (None, ""):
        return _utc_now()

    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number) > 1e11:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)

    text = str(value or "").strip()
    if not text:
        return _utc_now()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return _utc_now()


def _timeframe_to_seconds(value: Any, default: int = 0) -> int:
    text = str(value or "").strip().lower()
    if not text:
        return int(default)

    aliases = {
        "1mn": 60,
        "1min": 60,
        "1minute": 60,
        "1hour": 3600,
        "1day": 86400,
        "1week": 604800,
        "1w": 604800,
    }

    if text in aliases:
        return aliases[text]

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

    if suffix == "w":
        return amount * 604800

    return int(default)


@dataclass(slots=True)
class SignalCollection:
    symbol: str
    signals: list[Any]
    stale_strategies: list[str]
    rejected_strategies: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.rejected_strategies is None:
            self.rejected_strategies = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signals": [
                signal.to_dict() if hasattr(signal, "to_dict") and callable(
                    signal.to_dict) else signal
                for signal in self.signals
            ],
            "stale_strategies": list(self.stale_strategies),
            "rejected_strategies": list(self.rejected_strategies),
        }


@dataclass(slots=True)
class SignalEngineStats:
    generated_count: int = 0
    ingested_count: int = 0
    failed_count: int = 0
    normalized_count: int = 0
    published_count: int = 0
    stale_count: int = 0
    last_generated_at: Optional[str] = None
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_count": self.generated_count,
            "ingested_count": self.ingested_count,
            "failed_count": self.failed_count,
            "normalized_count": self.normalized_count,
            "published_count": self.published_count,
            "stale_count": self.stale_count,
            "last_generated_at": self.last_generated_at,
            "last_error": self.last_error,
        }


class SignalEngine:
    """
    Strategy-facing signal engine + lifecycle manager.

    This engine calls strategies and normalizes their outputs into a stable
    dict payload expected by TradingCore, SignalAgent, and DecisionEngine.
    """

    STRATEGY_METHODS = (
        "generate_signal",
        "create_signal",
        "evaluate_signal",
        "signal",
        "run",
    )

    VALID_SIDES = {"buy", "sell", "hold"}

    def __init__(
        self,
        strategy_registry: Any | None = None,
        *,
        event_bus: AsyncEventBus | None = None,
        signal_ttl_seconds: float = 900.0,
        min_confidence: float = 0.0,
        publish_events: bool = True,
        logger: Any = None,
    ) -> None:
        self.strategy_registry = strategy_registry
        self.bus = event_bus
        self.signal_ttl_seconds = max(30.0, float(signal_ttl_seconds))
        self.min_confidence = self._clamp(min_confidence, 0.0, 1.0)
        self.publish_events = bool(publish_events)
        self.logger = logger

        self.stats = SignalEngineStats()

        # Optional compat attributes expected elsewhere in your app.
        self.alpha_aggregator = getattr(
            strategy_registry, "alpha_aggregator", None)
        self.regime_engine = getattr(strategy_registry, "regime_engine", None)

    # ------------------------------------------------------------------
    # Bus
    # ------------------------------------------------------------------

    def attach(self, event_bus: AsyncEventBus) -> None:
        self.bus = event_bus

    async def _publish(self, event_type: Any, payload: Any, *, priority: int = 58, source: str = "signal_engine") -> None:
        if not self.publish_events or self.bus is None:
            return

        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            return

        try:
            try:
                result = publish(
                    event_type,
                    payload,
                    priority=priority,
                    source=source,
                )
            except TypeError:
                result = publish(event_type, payload)

            if inspect.isawaitable(result):
                await result

            self.stats.published_count += 1

        except Exception as exc:
            self._log_debug("Signal publish failed: %s", exc)

    # ------------------------------------------------------------------
    # Ingest / normalize
    # ------------------------------------------------------------------

    async def ingest(
        self,
        signal: Any,
        *,
        source: str = "signal_engine",
    ) -> Any:
        normalized = self.normalize(signal)

        self.stats.ingested_count += 1

        await self._publish(
            getattr(EventType, "SIGNAL_CREATED", "signal.created"),
            self._signal_to_dict(normalized),
            priority=58,
            source=source,
        )

        return normalized

    def normalize(self, signal: Any) -> Any:
        """Normalize raw signal into Signal object when possible."""
        if not self._is_signal_instance(signal):
            signal = self._build_signal(signal)

        metadata = dict(getattr(signal, "metadata", {}) or {})
        source_strategy = getattr(signal, "source_strategy", None) or getattr(
            signal, "strategy_name", None)

        metadata.setdefault("source_strategy", source_strategy)
        metadata.setdefault("signal_id", getattr(signal, "id", None))
        metadata.setdefault("normalized_at", _utc_now().isoformat())

        self.stats.normalized_count += 1

        transition = getattr(signal, "transition", None)
        if callable(transition):
            return transition(
                stage="normalized",
                status=getattr(SignalStatus, "CREATED", "created"),
                metadata=metadata,
                note=f"Normalized signal from {source_strategy}",
                timestamp=_coerce_datetime(getattr(signal, "timestamp", None)),
            )

        # Fallback for plain objects/signals without transition().
        with self._suppress_attr_error():
            setattr(signal, "metadata", metadata)
        with self._suppress_attr_error():
            setattr(signal, "stage", "normalized")
        with self._suppress_attr_error():
            setattr(signal, "status", getattr(
                SignalStatus, "CREATED", "created"))

        return signal

    def _build_signal(self, raw: Any) -> Any:
        payload = self._raw_to_payload(raw)

        try:
            return Signal(**payload)
        except Exception:
            # If the local Signal class is strict or unavailable, return payload.
            return payload

    def _raw_to_payload(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}

        if isinstance(raw, Mapping):
            payload = dict(raw)
        elif is_dataclass(raw):
            payload = asdict(raw)
        elif hasattr(raw, "to_dict") and callable(raw.to_dict):
            result = raw.to_dict()
            payload = dict(result or {}) if isinstance(result, Mapping) else {}
        else:
            payload = {}
            for key in (
                "id",
                "symbol",
                "side",
                "action",
                "decision",
                "amount",
                "price",
                "confidence",
                "reason",
                "note",
                "strategy_name",
                "source_strategy",
                "timestamp",
                "status",
                "stage",
                "metadata",
                "type",
                "stop_loss",
                "take_profit",
                "stop_price",
                "expected_return",
                "risk_estimate",
                "alpha_score",
            ):
                if hasattr(raw, key):
                    payload[key] = getattr(raw, key)

        side = self._normalize_side(
            payload.get("side")
            or payload.get("action")
            or payload.get("decision")
        )

        if side:
            payload["side"] = side

        payload["confidence"] = self._clamp(
            self._safe_float(payload.get("confidence"), 0.0),
            0.0,
            1.0,
        )

        payload.setdefault("timestamp", _utc_now())
        payload.setdefault("metadata", {})
        payload["metadata"] = dict(payload.get("metadata") or {})

        # Keep non-Signal fields in metadata so they don't get lost.
        for key in (
            "type",
            "stop_loss",
            "take_profit",
            "stop_price",
            "expected_return",
            "risk_estimate",
            "alpha_score",
            "horizon",
            "feature_snapshot",
            "feature_version",
        ):
            if key in payload:
                payload["metadata"].setdefault(key, payload.get(key))

        if payload.get("reason") and not payload.get("note"):
            payload["note"] = payload.get("reason")

        return payload

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect(
        self,
        symbol: str,
        strategy_signals: Mapping[str, Mapping[str, Any] | dict[str, Any]],
        *,
        now: datetime | None = None,
    ) -> SignalCollection:
        reference_time = now or _utc_now()
        normalized_symbol = str(symbol or "").strip()
        bucket = strategy_signals.get(normalized_symbol, {}) or strategy_signals.get(
            normalized_symbol.upper(), {}) or {}

        fresh: list[Any] = []
        stale_strategies: list[str] = []
        rejected_strategies: list[str] = []

        for strategy_name, signal in dict(bucket or {}).items():
            try:
                normalized = self.normalize(signal)
            except Exception:
                rejected_strategies.append(str(strategy_name))
                continue

            timestamp = _coerce_datetime(getattr(normalized, "timestamp", None) if not isinstance(
                normalized, dict) else normalized.get("timestamp"))
            freshness_window = timedelta(seconds=self.signal_ttl(normalized))

            if reference_time - timestamp > freshness_window:
                stale_strategies.append(str(strategy_name))
                self.stats.stale_count += 1
                continue

            confidence = self._safe_float(
                getattr(normalized, "confidence", None) if not isinstance(
                    normalized, dict) else normalized.get("confidence"),
                0.0,
            )

            if confidence < self.min_confidence:
                rejected_strategies.append(str(strategy_name))
                continue

            fresh.append(normalized)

        return SignalCollection(
            symbol=normalized_symbol,
            signals=fresh,
            stale_strategies=stale_strategies,
            rejected_strategies=rejected_strategies,
        )

    def signal_ttl(self, signal: Any) -> float:
        metadata = dict(getattr(signal, "metadata", {}) or {}) if not isinstance(
            signal, dict) else dict(signal.get("metadata") or {})
        timeframe_seconds = _timeframe_to_seconds(
            metadata.get("timeframe"), default=0)

        if timeframe_seconds > 0:
            return max(self.signal_ttl_seconds, float(timeframe_seconds) * 1.5)

        return self.signal_ttl_seconds

    # ------------------------------------------------------------------
    # Strategy resolution
    # ------------------------------------------------------------------

    def _resolve_strategy(self, strategy_name: str) -> Any | None:
        registry = self.strategy_registry
        if registry is None:
            return None

        # Preferred internal resolver.
        resolver = getattr(registry, "_resolve_strategy", None)
        if callable(resolver):
            try:
                strategy = resolver(strategy_name)
                if strategy is not None:
                    return strategy
            except Exception:
                pass

        # Common public APIs.
        for attr in ("get", "get_strategy", "resolve", "resolve_strategy"):
            fn = getattr(registry, attr, None)
            if callable(fn):
                try:
                    strategy = fn(strategy_name)
                    if strategy is not None:
                        return strategy
                except Exception:
                    continue

        # Registry dict fallback.
        if isinstance(registry, Mapping):
            return registry.get(strategy_name)

        return None

    # ------------------------------------------------------------------
    # Strategy signal generation
    # ------------------------------------------------------------------

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
        strategy_name_text = str(strategy_name or "").strip()
        normalized_symbol = str(symbol or "").strip().upper()

        if not strategy_name_text:
            return None

        strategy = self._resolve_strategy(strategy_name_text)
        if strategy is None:
            self.stats.failed_count += 1
            self.stats.last_error = f"Strategy not found: {strategy_name_text}"
            return None

        timeframe = str(getattr(dataset, "timeframe", "1h")
                        or "1h").strip() or "1h"

        raw_signal = await self._call_strategy(
            strategy=strategy,
            candles=candles,
            dataset=dataset,
            symbol=normalized_symbol,
            timeframe=timeframe,
        )

        if raw_signal is None:
            return None

        raw_payload = self._raw_to_payload(raw_signal)

        raw_payload.setdefault("symbol", normalized_symbol)
        raw_payload.setdefault("strategy_name", strategy_name_text)
        raw_payload.setdefault("source_strategy", strategy_name_text)
        raw_payload.setdefault("timestamp", _utc_now())

        raw_payload.setdefault("metadata", {})
        raw_payload["metadata"] = dict(raw_payload.get("metadata") or {})
        raw_payload["metadata"].setdefault("timeframe", timeframe)
        raw_payload["metadata"].setdefault("strategy_name", strategy_name_text)

        side = self._normalize_side(
            raw_payload.get("side")
            or raw_payload.get("action")
            or raw_payload.get("decision")
        )

        if not side:
            side = "hold"

        raw_payload["side"] = side

        confidence = self._clamp(
            self._safe_float(raw_payload.get("confidence"), 0.0),
            0.0,
            1.0,
        )
        raw_payload["confidence"] = confidence

        if confidence < self.min_confidence:
            return None

        try:
            normalized_signal = self.normalize(raw_payload)
            signal_dict = self._signal_to_dict(normalized_signal)
        except Exception as exc:
            self.stats.failed_count += 1
            self.stats.last_error = f"Normalize failed: {type(exc).__name__}: {exc}"
            await self._publish_failed(
                symbol=normalized_symbol,
                strategy_name=strategy_name_text,
                reason=self.stats.last_error,
            )
            return None

        signal_dict.setdefault("symbol", normalized_symbol)
        signal_dict.setdefault("strategy_name", strategy_name_text)
        signal_dict.setdefault("source_strategy", strategy_name_text)
        signal_dict.setdefault("timeframe", timeframe)
        signal_dict.setdefault("side", side)
        signal_dict.setdefault("confidence", confidence)

        await self._publish(
            getattr(EventType, "SIGNAL_CREATED", "signal.created"),
            signal_dict,
            priority=58,
            source=strategy_name_text,
        )

        self.stats.generated_count += 1
        self.stats.last_generated_at = _utc_now().isoformat()

        return signal_dict

    async def _call_strategy(
        self,
        *,
        strategy: Any,
        candles: list[Any],
        dataset: Any,
        symbol: str,
        timeframe: str,
    ) -> Any:
        last_error: Optional[Exception] = None

        for method_name in self.STRATEGY_METHODS:
            method = getattr(strategy, method_name, None)
            if not callable(method):
                continue

            call_attempts = (
                lambda: method(candles=candles, dataset=dataset,
                               symbol=symbol, timeframe=timeframe),
                lambda: method(candles=candles,
                               dataset=dataset, symbol=symbol),
                lambda: method(candles=candles, symbol=symbol,
                               timeframe=timeframe),
                lambda: method(candles, dataset=dataset,
                               symbol=symbol, timeframe=timeframe),
                lambda: method(candles, dataset=dataset),
                lambda: method(candles),
            )

            for call in call_attempts:
                try:
                    result = call()
                    if inspect.isawaitable(result):
                        result = await result
                    if result is not None:
                        return result
                except TypeError as exc:
                    last_error = exc
                    continue
                except Exception as exc:
                    last_error = exc
                    break

        if last_error is not None:
            self.stats.failed_count += 1
            self.stats.last_error = f"{type(last_error).__name__}: {last_error}"

        return None

    async def _publish_failed(self, *, symbol: str, strategy_name: str, reason: str) -> None:
        event_type = getattr(EventType, "SIGNAL_FAILED", "signal.failed")
        await self._publish(
            event_type,
            {
                "symbol": symbol,
                "strategy_name": strategy_name,
                "reason": reason,
                "timestamp": _utc_now().isoformat(),
            },
            priority=60,
            source="signal_engine",
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _signal_to_dict(self, signal: Any) -> dict[str, Any]:
        if isinstance(signal, Mapping):
            payload = dict(signal)
            metadata = dict(payload.get("metadata") or {})
        else:
            metadata = dict(getattr(signal, "metadata", {}) or {})
            payload = {
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
                "metadata": metadata,
            }

        metadata = dict(metadata or {})

        side = self._normalize_side(
            payload.get("side")
            or payload.get("action")
            or payload.get("decision")
        )

        payload["side"] = side or "hold"
        payload["confidence"] = self._clamp(
            self._safe_float(payload.get("confidence"), 0.0), 0.0, 1.0)
        payload["reason"] = payload.get("reason") or payload.get(
            "note") or metadata.get("reason")
        payload["type"] = payload.get("type") or metadata.get("type", "market")
        payload["metadata"] = metadata

        for key in (
            "stop_loss",
            "take_profit",
            "stop_price",
            "expected_return",
            "risk_estimate",
            "alpha_score",
            "horizon",
            "feature_snapshot",
            "feature_version",
        ):
            if key in metadata and key not in payload:
                payload[key] = metadata[key]

        timestamp = payload.get("timestamp")
        if isinstance(timestamp, datetime):
            payload["timestamp"] = timestamp.isoformat()

        status = payload.get("status")
        if hasattr(status, "value"):
            payload["status"] = status.value

        return self._json_safe(payload)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "signal_ttl_seconds": self.signal_ttl_seconds,
            "min_confidence": self.min_confidence,
            "publish_events": self.publish_events,
            "has_event_bus": self.bus is not None,
            "stats": self.stats.to_dict(),
        }

    def healthy(self) -> bool:
        if self.stats.failed_count <= 0:
            return True
        return self.stats.failed_count <= max(5, self.stats.generated_count * 2)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _is_signal_instance(self, value: Any) -> bool:
        try:
            return isinstance(value, Signal)
        except Exception:
            return False

    def _normalize_side(self, value: Any) -> str:
        text = str(value or "").strip().lower()

        if text in {"buy", "long"}:
            return "buy"

        if text in {"sell", "short"}:
            return "sell"

        if text in {"hold", "wait", "neutral", "none", ""}:
            return "hold"

        return "hold"

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)

        try:
            number = float(value)
        except Exception:
            return float(default)

        if not math.isfinite(number):
            return float(default)

        return number

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, bool)):
            return value

        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Mapping):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._json_safe(item)
                for item in value
            ]

        if hasattr(value, "value"):
            return self._json_safe(value.value)

        return str(value)

    def _log_debug(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            try:
                self.logger.debug(message, *args)
            except Exception:
                pass

    class _suppress_attr_error:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return exc_type is AttributeError
