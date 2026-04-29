from __future__ import annotations

"""
InvestPro BaseAgent

Shared base class for all event-driven agents.

Used by:
- SignalAgent
- ReasoningAgent
- RiskAgent
- ExecutionAgent
- PortfolioAgent
- RegimeAgent
- LearningAgent

Provides:
- memory integration
- event bus publishing
- lifecycle state
- guarded process wrapper
- metrics/snapshot
- JSON-safe payload normalization
"""

import inspect
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(slots=True)
class AgentState:
    name: str
    running: bool = True
    processed_count: int = 0
    success_count: int = 0
    error_count: int = 0
    emitted_count: int = 0
    remembered_count: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_process_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_emit_at: Optional[str] = None
    last_memory_at: Optional[str] = None
    last_latency_ms: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseAgent:
    """Base class for InvestPro agents."""

    def __init__(
        self,
        name: str | None = None,
        memory: Any = None,
        event_bus: Any = None,
        *,
        logger: Any = None,
        enabled: bool = True,
        fail_silent: bool = False,
    ) -> None:
        self.name = str(name or self.__class__.__name__).strip() or self.__class__.__name__
        self.memory = memory
        self.event_bus = event_bus
        self.logger = logger
        self.enabled = bool(enabled)
        self.fail_silent = bool(fail_silent)
        self.state = AgentState(name=self.name, running=self.enabled)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self.enabled = True
        self.state.running = True

    def stop(self) -> None:
        self.enabled = False
        self.state.running = False

    @property
    def running(self) -> bool:
        return self.enabled and self.state.running

    # ------------------------------------------------------------------
    # Main processing API
    # ------------------------------------------------------------------

    async def process(self, context: Any) -> Any:
        raise NotImplementedError

    async def process_guarded(self, context: Any) -> Any:
        """Run process() with metrics, timing, memory, and error protection."""
        if not self.running:
            return context

        started = time.perf_counter()
        self.state.processed_count += 1
        self.state.last_process_at = self._utc_now()

        try:
            result = self.process(context)
            result = await self._maybe_await(result)

            self.state.success_count += 1
            self.state.last_success_at = self._utc_now()
            self.state.last_latency_ms = (time.perf_counter() - started) * 1000.0

            return result

        except Exception as exc:
            self.state.error_count += 1
            self.state.last_error_at = self._utc_now()
            self.state.last_latency_ms = (time.perf_counter() - started) * 1000.0
            self.state.last_error = f"{type(exc).__name__}: {exc}"

            self._log_error("%s process failed: %s", self.name, exc)

            await self.emit(
                "agent.failed",
                {
                    "agent": self.name,
                    "error": self.state.last_error,
                    "timestamp": self._utc_now(),
                    "context": self.context_preview(context),
                },
            )

            self.remember(
                "error",
                {
                    "error": self.state.last_error,
                    "context": self.context_preview(context),
                },
                symbol=self._extract_symbol(context),
                decision_id=self._extract_decision_id(context),
            )

            if self.fail_silent:
                return context

            raise

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def remember(
        self,
        stage: str,
        payload: Any = None,
        symbol: str | None = None,
        decision_id: str | None = None,
        **metadata: Any,
    ) -> Any:
        """Store an agent event in memory if memory is configured."""
        if self.memory is None:
            return None

        safe_payload = self._json_safe(payload or {})

        if metadata:
            if isinstance(safe_payload, dict):
                safe_payload.setdefault("metadata", {}).update(self._json_safe(metadata))
            else:
                safe_payload = {
                    "value": safe_payload,
                    "metadata": self._json_safe(metadata),
                }

        try:
            result = self.memory.store(
                agent=self.name,
                stage=str(stage or "unknown"),
                payload=safe_payload,
                symbol=symbol,
                decision_id=decision_id,
            )

            self.state.remembered_count += 1
            self.state.last_memory_at = self._utc_now()

            return result

        except Exception as exc:
            self._log_error("%s memory store failed: %s", self.name, exc)
            return None

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    async def emit(
        self,
        topic: str,
        payload: Any = None,
        *,
        source: str | None = None,
        remember: bool = False,
        stage: str | None = None,
        symbol: str | None = None,
        decision_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Publish an event if an event bus is configured."""
        if self.event_bus is None:
            return None

        safe_payload = self._json_safe(payload or {})

        if kwargs:
            if isinstance(safe_payload, dict):
                safe_payload.update(self._json_safe(kwargs))
            else:
                safe_payload = {
                    "value": safe_payload,
                    **self._json_safe(kwargs),
                }

        publish = getattr(self.event_bus, "publish", None)
        if not callable(publish):
            return None

        try:
            try:
                result = publish(
                    str(topic),
                    safe_payload,
                    source=source or self.name,
                )
            except TypeError:
                result = publish(str(topic), safe_payload)

            result = await self._maybe_await(result)

            self.state.emitted_count += 1
            self.state.last_emit_at = self._utc_now()

            if remember:
                self.remember(
                    stage or f"emit:{topic}",
                    safe_payload,
                    symbol=symbol or self._extract_symbol(safe_payload),
                    decision_id=decision_id or self._extract_decision_id(safe_payload),
                )

            return result

        except Exception as exc:
            self._log_error("%s emit failed [%s]: %s", self.name, topic, exc)
            return None

    async def publish_event(self, topic: str, payload: Any = None, **kwargs: Any) -> Any:
        """Compatibility alias."""
        return await self.emit(topic, payload, **kwargs)

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def context_preview(self, context: Any) -> dict[str, Any]:
        data = self._object_to_dict(context)
        signals = data.get("signals")

        return {
            "symbol": data.get("symbol"),
            "timeframe": data.get("timeframe"),
            "decision_id": data.get("decision_id"),
            "signal_count": len(signals) if isinstance(signals, list) else None,
            "keys": list(data.keys())[:20],
        }

    def get_context_value(self, context: Any, key: str, default: Any = None) -> Any:
        if isinstance(context, dict):
            return context.get(key, default)
        return getattr(context, key, default)

    def set_context_value(self, context: Any, key: str, value: Any) -> Any:
        if isinstance(context, dict):
            context[key] = value
            return context

        try:
            setattr(context, key, value)
        except Exception:
            pass

        return context

    def _extract_symbol(self, context: Any) -> str | None:
        data = self._object_to_dict(context)
        symbol = data.get("symbol")

        if not symbol and isinstance(data.get("signal"), dict):
            symbol = data["signal"].get("symbol")

        text = str(symbol or "").strip().upper()
        return text or None

    def _extract_decision_id(self, context: Any) -> str | None:
        data = self._object_to_dict(context)
        decision_id = data.get("decision_id")

        if not decision_id and isinstance(data.get("signal"), dict):
            decision_id = data["signal"].get("decision_id")

        text = str(decision_id or "").strip()
        return text or None

    # ------------------------------------------------------------------
    # Health / status
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return self.state.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return self.snapshot()

    def healthy(self) -> bool:
        if not self.running:
            return True

        if self.state.error_count <= 0:
            return True

        # If the agent has had some success, tolerate occasional failures.
        return self.state.error_count <= max(3, self.state.success_count * 2)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _object_to_dict(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return self._json_safe(value)

        if is_dataclass(value):
            try:
                result = asdict(value)
                return self._json_safe(result)
            except Exception:
                pass

        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                result = value.to_dict()
                if isinstance(result, dict):
                    return self._json_safe(result)
            except Exception:
                pass

        output: dict[str, Any] = {}

        for key in (
            "symbol",
            "timeframe",
            "decision_id",
            "signal",
            "signals",
            "candles",
            "dataset",
            "portfolio_snapshot",
            "risk_limits",
            "metadata",
        ):
            if hasattr(value, key):
                output[key] = getattr(value, key)

        return self._json_safe(output)

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (str, int, bool)):
            return value

        if isinstance(value, float):
            if value != value or value in {float("inf"), float("-inf")}:
                return None
            return value

        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._json_safe(item)
                for item in value
            ]

        if is_dataclass(value):
            try:
                return self._json_safe(asdict(value))
            except Exception:
                pass

        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                return self._json_safe(value.to_dict())
            except Exception:
                pass

        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass

        return str(value)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            try:
                self.logger.error(message, *args)
                return
            except Exception:
                traceback = getattr(self.logger, "traceback", None)
                if callable(traceback):
                    self.logger.traceback()
                return