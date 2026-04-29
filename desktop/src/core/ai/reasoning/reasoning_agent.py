from __future__ import annotations

"""
InvestPro ReasoningAgent

Consumes signal contexts, asks DecisionEngine for a final decision,
and publishes decision events.

Typical flow:

    signal.generated
        ↓
    ReasoningAgent.on_signal(ctx)
        ↓
    DecisionEngine.decide(ctx)
        ↓
    decision.made / decision.failed

This agent does not execute trades directly. It only produces a structured
decision event for TradeFilter, RiskEngine, or ExecutionAgent.
"""

import inspect
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(slots=True)
class ReasoningAgentState:
    name: str = "ReasoningAgent"
    running: bool = True
    processed_count: int = 0
    success_count: int = 0
    error_count: int = 0
    last_signal_at: Optional[str] = None
    last_decision_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_error: str = ""
    last_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReasoningAgent:
    """Agent that converts signal contexts into decision events."""

    def __init__(
        self,
        decision_engine: Any,
        event_bus: Any,
        *,
        name: str = "ReasoningAgent",
        input_topic: str = "signal.generated",
        decision_topic: str = "decision.made",
        failed_topic: str = "decision.failed",
        audit_topic: str = "agent.reasoning.audit",
        publish_audit: bool = True,
        logger: Any = None,
    ) -> None:
        if decision_engine is None:
            raise ValueError("decision_engine is required")
        if event_bus is None:
            raise ValueError("event_bus is required")

        self.engine = decision_engine
        self.bus = event_bus

        self.name = str(name or "ReasoningAgent")
        self.input_topic = str(input_topic or "signal.generated")
        self.decision_topic = str(decision_topic or "decision.made")
        self.failed_topic = str(failed_topic or "decision.failed")
        self.audit_topic = str(audit_topic or "agent.reasoning.audit")
        self.publish_audit = bool(publish_audit)
        self.logger = logger

        self.state = ReasoningAgentState(name=self.name)

    # ------------------------------------------------------------------
    # Event subscription lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe this agent to the event bus if subscribe() exists."""
        self.state.running = True

        subscribe = getattr(self.bus, "subscribe", None)
        if callable(subscribe):
            try:
                subscribe(self.input_topic, self.on_signal)
            except Exception as exc:
                self._log_error("Unable to subscribe ReasoningAgent: %s", exc)

    def stop(self) -> None:
        self.state.running = False

        unsubscribe = getattr(self.bus, "unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe(self.input_topic, self.on_signal)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    async def on_signal(self, ctx: Any) -> Optional[Any]:
        """Handle signal context or event object."""
        if not self.state.running:
            return None

        started = time.perf_counter()
        self.state.processed_count += 1
        self.state.last_signal_at = self._utc_now()

        try:
            normalized_ctx = self._extract_context(ctx)
            decision = await self._decide(normalized_ctx)

            latency_ms = (time.perf_counter() - started) * 1000.0
            self.state.last_latency_ms = latency_ms
            self.state.success_count += 1
            self.state.last_decision_at = self._utc_now()

            payload = self._decision_payload(
                decision=decision,
                ctx=normalized_ctx,
                latency_ms=latency_ms,
            )

            await self._publish(
                self.decision_topic,
                payload,
                source=self.name,
            )

            if self.publish_audit:
                await self._publish(
                    self.audit_topic,
                    {
                        "status": "success",
                        "agent": self.name,
                        "topic": self.decision_topic,
                        "symbol": payload.get("symbol"),
                        "decision": payload.get("decision"),
                        "confidence": payload.get("confidence"),
                        "latency_ms": latency_ms,
                        "timestamp": self._utc_now(),
                    },
                    source=self.name,
                )

            return decision

        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            self.state.last_latency_ms = latency_ms
            self.state.error_count += 1
            self.state.last_error_at = self._utc_now()
            self.state.last_error = f"{type(exc).__name__}: {exc}"

            self._log_error("ReasoningAgent failed: %s", exc)

            payload = {
                "agent": self.name,
                "error": self.state.last_error,
                "latency_ms": latency_ms,
                "timestamp": self._utc_now(),
                "context": self._safe_context_preview(ctx),
            }

            await self._publish(
                self.failed_topic,
                payload,
                source=self.name,
            )

            if self.publish_audit:
                await self._publish(
                    self.audit_topic,
                    {
                        "status": "failed",
                        **payload,
                    },
                    source=self.name,
                )

            return None

    async def _decide(self, ctx: Any) -> Any:
        result = self.engine.decide(ctx)
        if inspect.isawaitable(result):
            return await result
        return result

    # ------------------------------------------------------------------
    # Payload normalization
    # ------------------------------------------------------------------

    def _extract_context(self, event_or_ctx: Any) -> Any:
        """Accept direct ctx, dict payload, or Event-like object."""
        if event_or_ctx is None:
            return {}

        # Event object with .data
        data = getattr(event_or_ctx, "data", None)
        if data is not None:
            return data

        # Event object with .payload
        payload = getattr(event_or_ctx, "payload", None)
        if payload is not None:
            return payload

        # Plain dict
        if isinstance(event_or_ctx, dict):
            if "data" in event_or_ctx and isinstance(event_or_ctx.get("data"), dict):
                return event_or_ctx["data"]
            if "payload" in event_or_ctx and isinstance(event_or_ctx.get("payload"), dict):
                return event_or_ctx["payload"]
            return event_or_ctx

        return event_or_ctx

    def _decision_payload(self, *, decision: Any, ctx: Any, latency_ms: float) -> dict[str, Any]:
        decision_dict = self._object_to_dict(decision)
        ctx_dict = self._object_to_dict(ctx)

        symbol = (
            decision_dict.get("symbol")
            or decision_dict.get("metadata", {}).get("symbol")
            or ctx_dict.get("symbol")
            or ""
        )

        payload = {
            "agent": self.name,
            "symbol": str(symbol or "").strip().upper(),
            "decision": str(
                decision_dict.get("decision")
                or decision_dict.get("action")
                or "HOLD"
            ).strip().upper(),
            "confidence": self._coerce_float(decision_dict.get("confidence")),
            "strategy_name": str(
                decision_dict.get("strategy_name")
                or decision_dict.get("selected_strategy")
                or decision_dict.get("metadata", {}).get("selected_strategy")
                or ""
            ).strip(),
            "model_name": str(decision_dict.get("model_name") or "").strip(),
            "reason": self._reason_text(decision_dict),
            "reasons": self._list_of_strings(decision_dict.get("reasons")),
            "risk_score": self._coerce_float(
                decision_dict.get("risk_score")
                or decision_dict.get("factors", {}).get("risk_score")
            ),
            "vote_margin": self._coerce_float(
                decision_dict.get("vote_margin")
                or decision_dict.get("factors", {}).get("vote_margin")
                or decision_dict.get("metadata", {}).get("vote_margin")
            ),
            "market_regime": str(
                decision_dict.get("market_regime")
                or decision_dict.get("metadata", {}).get("market_regime")
                or ""
            ).strip().upper(),
            "timestamp": self._utc_now(),
            "latency_ms": latency_ms,
            "decision_raw": decision_dict,
            "context": ctx_dict,
        }

        signal = decision_dict.get("signal")
        if signal is not None:
            payload["signal"] = self._object_to_dict(signal)

        decision_id = (
            decision_dict.get("decision_id")
            or decision_dict.get("metadata", {}).get("decision_id")
            or ctx_dict.get("decision_id")
        )
        if decision_id:
            payload["decision_id"] = str(decision_id)

        return self._json_safe(payload)

    def _reason_text(self, decision_dict: dict[str, Any]) -> str:
        reason = decision_dict.get("reason")
        if reason:
            return str(reason).strip()

        reasons = decision_dict.get("reasons")
        if isinstance(reasons, list) and reasons:
            return " | ".join(str(item).strip() for item in reasons if str(item).strip())

        metadata = decision_dict.get("metadata")
        if isinstance(metadata, dict):
            override = metadata.get("override_reason")
            if override:
                return str(override).strip()

        return ""

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def _publish(self, topic: str, payload: Any, *, source: str) -> Any:
        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            raise RuntimeError("event_bus does not expose publish()")

        try:
            result = publish(topic, payload, source=source)
        except TypeError:
            result = publish(topic, payload)

        if inspect.isawaitable(result):
            return await result

        return result

    # ------------------------------------------------------------------
    # Snapshot / health
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return self.state.to_dict()

    def healthy(self) -> bool:
        if not self.state.running:
            return True
        if self.state.error_count <= 0:
            return True
        return self.state.error_count <= max(3, self.state.success_count * 2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _object_to_dict(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return self._json_safe(value)

        if is_dataclass(value):
            try:
                return self._json_safe(asdict(value))
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
            "decision",
            "action",
            "confidence",
            "reasons",
            "reason",
            "factors",
            "signal",
            "strategy_name",
            "selected_strategy",
            "model_name",
            "risk_score",
            "vote_margin",
            "market_regime",
            "metadata",
            "decision_id",
        ):
            if hasattr(value, key):
                output[key] = getattr(value, key)

        return self._json_safe(output)

    def _safe_context_preview(self, value: Any) -> dict[str, Any]:
        ctx = self._object_to_dict(self._extract_context(value))
        return {
            "symbol": ctx.get("symbol"),
            "timeframe": ctx.get("timeframe"),
            "decision_id": ctx.get("decision_id"),
            "signal_count": len(ctx.get("signals") or []) if isinstance(ctx.get("signals"), list) else None,
        }

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

    def _coerce_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)
        try:
            number = float(value)
        except Exception:
            return float(default)
        if number != number or number in {float("inf"), float("-inf")}:
            return float(default)
        return number

    def _list_of_strings(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []

        if isinstance(value, (list, tuple, set)):
            return [
                str(item).strip()
                for item in value
                if str(item or "").strip()
            ]

        text = str(value or "").strip()
        return [text] if text else []

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_error(self, message: str, *args: Any) -> None:
        if self.logger is not None:
            try:
                self.logger.error(message, *args)
            except Exception:
                pass
