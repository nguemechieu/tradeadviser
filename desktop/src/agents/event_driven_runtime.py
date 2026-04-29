from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any
from uuid import uuid4

try:
    from agents.signal_fanout import run_signal_agents_parallel
except Exception:
    async def run_signal_agents_parallel(signal_agents: list[Any], context: dict[str, Any]) -> dict[str, Any]:
        working = dict(context or {})
        candidates = []

        for agent in list(signal_agents or []):
            if agent is None:
                continue

            result = agent.process(dict(working))
            if inspect.isawaitable(result):
                result = await result

            if isinstance(result, dict):
                if isinstance(result.get("signal"), dict):
                    candidates.append(
                        {
                            "agent": getattr(agent, "name", agent.__class__.__name__),
                            "signal": dict(result["signal"]),
                        }
                    )
                working.update(result)

        if candidates:
            working["signal_candidates"] = candidates
            working.setdefault("signal", dict(candidates[0]["signal"]))

        return working


try:
    from events.event_bus.event_types import EventType
except Exception:
    try:
        from events.event_bus.event_types import EventType  # type: ignore
    except Exception:
        class EventType:  # type: ignore
            MARKET_DATA = "market.data"
            SIGNAL = "signal"
            RISK_APPROVED = "risk.approved"
            RISK_REJECTED = "risk.rejected"
            ORDER_REQUEST = "order.request"
            ORDER_FILLED = "order.filled"
            ORDER_REJECTED = "order.rejected"
            ORDER_FAILED = "order.failed"


def _event_name(name: str, fallback: str) -> Any:
    member = getattr(EventType, name, fallback)

    if hasattr(member, "value"):
        try:
            return member.value
        except Exception:
            pass

    return member


def _event_data(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        if isinstance(event.get("data"), dict):
            return dict(event["data"])
        if isinstance(event.get("payload"), dict):
            return dict(event["payload"])
        return dict(event)

    if hasattr(event, "data") and isinstance(event.data, dict):
        return dict(event.data)

    if hasattr(event, "payload") and isinstance(event.payload, dict):
        return dict(event.payload)

    return {}


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class EventDrivenAgentRuntime:
    """Event-driven orchestration layer for the agent decision pipeline."""

    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(
            self,
            bus: Any,
            signal_agent: Any = None,
            signal_agents: list[Any] | None = None,
            signal_consensus_agent: Any = None,
            signal_aggregation_agent: Any = None,
            regime_agent: Any = None,
            portfolio_agent: Any = None,
            risk_agent: Any = None,
            execution_agent: Any = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

        self.bus = bus
        self.signal_agents = list(signal_agents or ([] if signal_agent is None else [signal_agent]))
        self.signal_agent = self.signal_agents[0] if self.signal_agents else signal_agent
        self.signal_consensus_agent = signal_consensus_agent
        self.signal_aggregation_agent = signal_aggregation_agent
        self.regime_agent = regime_agent
        self.portfolio_agent = portfolio_agent
        self.risk_agent = risk_agent
        self.execution_agent = execution_agent

        self._decision_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._started = False
        self._subscriptions: list[tuple[Any, Any]] = []

        self._subscribe_events()

    # ------------------------------------------------------------------
    # Bus helpers
    # ------------------------------------------------------------------

    @property
    def is_started(self) -> bool:
        return bool(self._started)

    def _bus_has_method(self, name: str) -> bool:
        return self.bus is not None and callable(getattr(self.bus, name, None))

    def _subscribe_events(self) -> None:
        if not self._bus_has_method("subscribe"):
            self.logger.warning(
                "EventDrivenAgentRuntime received invalid bus=%r; runtime will only work through direct process_market_data dispatch.",
                self.bus,
            )
            return

        self._safe_subscribe(_event_name("MARKET_DATA", "market.data"), self._on_market_data)
        self._safe_subscribe(_event_name("SIGNAL", "signal"), self._on_signal)
        self._safe_subscribe(_event_name("RISK_APPROVED", "risk.approved"), self._on_risk_approved)
        self._safe_subscribe(_event_name("RISK_REJECTED", "risk.rejected"), self._on_terminal_event)
        self._safe_subscribe(_event_name("ORDER_REQUEST", "order.request"), self._on_order_request)
        self._safe_subscribe(_event_name("ORDER_FILLED", "order.filled"), self._on_order_filled)
        self._safe_subscribe(_event_name("ORDER_REJECTED", "order.rejected"), self._on_terminal_event)
        self._safe_subscribe(_event_name("ORDER_FAILED", "order.failed"), self._on_terminal_event)

    def _safe_subscribe(self, event_type: Any, handler: Any) -> None:
        try:
            self.bus.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))
        except Exception:
            self.logger.debug("Unable to subscribe to event_type=%s", event_type, exc_info=True)

    def unsubscribe_all(self) -> None:
        unsubscribe = getattr(self.bus, "unsubscribe", None)
        if not callable(unsubscribe):
            self._subscriptions.clear()
            return

        for event_type, handler in list(self._subscriptions):
            try:
                unsubscribe(event_type, handler)
            except Exception:
                pass

        self._subscriptions.clear()

    async def _publish(self, event_type: Any, context: dict[str, Any]) -> Any:
        publish = getattr(self.bus, "publish", None)

        if not callable(publish):
            # No bus available: directly route by event type fallback.
            return None

        try:
            result = publish(event_type, context)
            return await _maybe_await(result)
        except TypeError:
            try:
                from events.event import Event
            except Exception:
                from events.event import Event  # type: ignore

            result = publish(Event(event_type, context))
            return await _maybe_await(result)
        except Exception:
            self.logger.debug("Failed to publish event_type=%s", event_type, exc_info=True)
            raise

    async def _dispatch_until_future_done(
            self,
            future: asyncio.Future[dict[str, Any]],
            *,
            timeout: float | None,
    ) -> dict[str, Any]:
        deadline = None if timeout is None else asyncio.get_running_loop().time() + float(timeout)

        while not future.done():
            if deadline is not None and asyncio.get_running_loop().time() >= deadline:
                raise asyncio.TimeoutError

            dispatch_once = getattr(self.bus, "dispatch_once", None)
            if callable(dispatch_once):
                result = dispatch_once()
                await _maybe_await(result)
            else:
                await asyncio.sleep(0)

        return await future

    # ------------------------------------------------------------------
    # Runtime lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._started:
            return

        run_in_background = getattr(self.bus, "run_in_background", None)

        if callable(run_in_background):
            try:
                run_in_background()
            except RuntimeError:
                # No running loop or bus does not need background mode.
                self.logger.debug("Event bus run_in_background was skipped", exc_info=True)
            except Exception:
                self.logger.debug("Event bus run_in_background failed", exc_info=True)

        self._started = True

    async def stop(self) -> None:
        pending = list(self._decision_futures.values())
        self._decision_futures = {}

        for future in pending:
            if future is not None and not future.done():
                future.cancel()

        self.unsubscribe_all()

        shutdown = getattr(self.bus, "shutdown", None)
        if self._started and callable(shutdown):
            try:
                result = shutdown()
                await _maybe_await(result)
            except Exception:
                self.logger.debug("Event bus shutdown failed", exc_info=True)

        self._started = False

    # ------------------------------------------------------------------
    # Direct API
    # ------------------------------------------------------------------

    async def process_market_data(
            self,
            context: dict[str, Any],
            timeout: float | None = None,
    ) -> dict[str, Any]:
        working = dict(context or {})
        decision_id = str(working.get("decision_id") or uuid4().hex).strip() or uuid4().hex
        working["decision_id"] = decision_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._decision_futures[decision_id] = future

        resolved_timeout = self.DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout

        try:
            await self._publish(_event_name("MARKET_DATA", "market.data"), working)

            if getattr(self.bus, "is_running", False):
                return await asyncio.wait_for(future, timeout=resolved_timeout)

            return await asyncio.wait_for(
                self._dispatch_until_future_done(future, timeout=resolved_timeout),
                timeout=resolved_timeout,
            )

        except asyncio.TimeoutError:
            working["runtime_error"] = "agent_runtime_timeout"
            working["status"] = "timeout"
            self._complete(working)
            return dict(working)

        except Exception as exc:
            working["runtime_error"] = f"{type(exc).__name__}: {exc}"
            working["status"] = "error"
            self.logger.debug("process_market_data failed for decision_id=%s", decision_id, exc_info=True)
            self._complete(working)
            return dict(working)

        finally:
            await self._decision_futures.pop(decision_id, None)

    # ------------------------------------------------------------------
    # Pipeline handlers
    # ------------------------------------------------------------------

    async def _process_optional_agent(self, agent: Any, context: dict[str, Any]) -> dict[str, Any]:
        if agent is None:
            return dict(context or {})

        try:
            result = agent.process(dict(context or {}))
            result = await _maybe_await(result)

            if isinstance(result, dict):
                return result

            return dict(context or {})

        except Exception as exc:
            working = dict(context or {})
            working["agent_error"] = f"{agent.__class__.__name__}: {type(exc).__name__}: {exc}"
            working["status"] = "agent_error"
            self.logger.debug("Agent failed: %s", agent, exc_info=True)
            return working

    async def _on_market_data(self, event: Any) -> None:
        context = _event_data(event)

        if not context.get("symbol"):
            self._complete(context)
            return

        try:
            if len(self.signal_agents) <= 1 and self.signal_aggregation_agent is None:
                if self.signal_agent is None:
                    self._complete(context)
                    return

                context = await self._process_optional_agent(self.signal_agent, context)
            else:
                context = await run_signal_agents_parallel(self.signal_agents, context)

                if self.signal_consensus_agent is not None:
                    context = await self._process_optional_agent(self.signal_consensus_agent, context)

                if self.signal_aggregation_agent is not None:
                    context = await self._process_optional_agent(self.signal_aggregation_agent, context)

            if not isinstance(context.get("signal"), dict):
                context.setdefault("status", "hold")
                self._complete(context)
                return

            await self._publish(_event_name("SIGNAL", "signal"), context)

        except Exception as exc:
            context["runtime_error"] = f"market_data_stage: {type(exc).__name__}: {exc}"
            context["status"] = "error"
            self.logger.debug("Market data stage failed", exc_info=True)
            self._complete(context)

    async def _on_signal(self, event: Any) -> None:
        context = _event_data(event)

        if not isinstance(context.get("signal"), dict):
            context.setdefault("status", "hold")
            self._complete(context)
            return

        try:
            context = await self._process_optional_agent(self.regime_agent, context)
            context = await self._process_optional_agent(self.portfolio_agent, context)
            context = await self._process_optional_agent(self.risk_agent, context)

            review = dict(context.get("trade_review") or {})

            if not review.get("approved"):
                context.setdefault("status", "risk_rejected")
                await self._publish(_event_name("RISK_REJECTED", "risk.rejected"), context)
                self._complete(context)
                return

            context["status"] = "risk_approved"
            await self._publish(_event_name("RISK_APPROVED", "risk.approved"), context)

        except Exception as exc:
            context["runtime_error"] = f"signal_stage: {type(exc).__name__}: {exc}"
            context["status"] = "error"
            self.logger.debug("Signal stage failed", exc_info=True)
            self._complete(context)

    async def _on_risk_approved(self, event: Any) -> None:
        context = _event_data(event)

        if not context.get("symbol"):
            self._complete(context)
            return

        review = dict(context.get("trade_review") or {})
        if not review.get("approved"):
            context.setdefault("status", "risk_rejected")
            self._complete(context)
            return

        try:
            await self._publish(_event_name("ORDER_REQUEST", "order.request"), context)
        except Exception as exc:
            context["runtime_error"] = f"order_request_publish: {type(exc).__name__}: {exc}"
            context["status"] = "error"
            self._complete(context)

    async def _on_order_request(self, event: Any) -> None:
        context = _event_data(event)

        if not context.get("symbol"):
            self._complete(context)
            return

        if self.execution_agent is None:
            context.setdefault("status", "execution_skipped")
            self._complete(context)
            return

        try:
            context = await self._process_optional_agent(self.execution_agent, context)

            execution_result = context.get("execution_result")
            if execution_result is None:
                context.setdefault("status", "execution_skipped")
                self._complete(context)
                return

            if isinstance(execution_result, dict):
                result_status = str(execution_result.get("status") or "").strip().lower()
                if result_status in {"rejected", "failed", "canceled", "cancelled"}:
                    context["status"] = "order_rejected"
                    await self._publish(_event_name("ORDER_REJECTED", "order.rejected"), context)
                    self._complete(context)
                    return

            context["status"] = "order_filled"
            await self._publish(_event_name("ORDER_FILLED", "order.filled"), context)

        except Exception as exc:
            context["runtime_error"] = f"execution_stage: {type(exc).__name__}: {exc}"
            context["status"] = "error"
            self.logger.debug("Execution stage failed", exc_info=True)

            with_context = dict(context)
            await self._publish(_event_name("ORDER_FAILED", "order.failed"), with_context)
            self._complete(context)

    async def _on_order_filled(self, event: Any) -> None:
        context = _event_data(event)

        if not context.get("symbol"):
            self._complete(context)
            return

        context.setdefault("status", "completed")
        self._complete(context)

    async def _on_terminal_event(self, event: Any) -> None:
        context = _event_data(event)
        self._complete(context)

    # ------------------------------------------------------------------
    # Completion / snapshot
    # ------------------------------------------------------------------

    def _complete(self, context: dict[str, Any]) -> None:
        decision_id = str((context or {}).get("decision_id") or "").strip()
        if not decision_id:
            return

        future = self._decision_futures.get(decision_id)
        if future is not None and not future.done():
            future.set_result(dict(context or {}))

    def snapshot(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "pending_decisions": len(self._decision_futures),
            "signal_agents": len(self.signal_agents),
            "has_consensus_agent": self.signal_consensus_agent is not None,
            "has_aggregation_agent": self.signal_aggregation_agent is not None,
            "has_regime_agent": self.regime_agent is not None,
            "has_portfolio_agent": self.portfolio_agent is not None,
            "has_risk_agent": self.risk_agent is not None,
            "has_execution_agent": self.execution_agent is not None,
            "subscriptions": [
                str(event_type.value if hasattr(event_type, "value") else event_type)
                for event_type, _handler in self._subscriptions
            ],
        }


__all__ = ["EventDrivenAgentRuntime"]