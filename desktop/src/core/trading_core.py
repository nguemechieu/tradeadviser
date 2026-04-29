from __future__ import annotations

from events.event_bus import EventBus

"""
Core orchestration and runtime integration for the InvestPro AI trading engine.

This module contains the primary application class that wires together broker
connectivity, strategy registration, signal generation, execution management,
portfolio/risk control, agent runtime, reasoning, and learning pipelines.
"""

import asyncio
import inspect
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4
from agents.agent_memory import AgentMemory
from agents.agent_orchestrator import AgentOrchestrator
from agents.event_driven_runtime import EventDrivenAgentRuntime
from agents.execution_agent import ExecutionAgent as TradingExecutionAgent
from agents.portfolio_agent import PortfolioAgent
from agents.regime_agent import RegimeAgent
from agents.risk_agent import RiskAgent as TradingRiskAgent
from agents.signal_agent import SignalAgent
from agents.signal_aggregation_agent import SignalAggregationAgent
from agents.signal_consensus_agent import SignalConsensusAgent
from agents.signal_fanout import run_signal_agents_parallel
from core.ai.reasoning import (
    HeuristicReasoningProvider,
    OpenAIReasoningProvider,
    ReasoningEngine,
)
from core.multi_symbol_orchestrator import MultiSymbolOrchestrator
from core.trade_filter import TradeFilter
from engines.risk_engine import RiskEngine
from events.event import Event
from events.event_bus.event_types import EventType
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from manager.portfolio_manager import PortfolioManager
from paper_learning import (
    PaperTradeDatasetBuilder,
    PaperTradeLearningRepository,
    PaperTradingLearningService,
)
from quant.data_hub import QuantDataHub
from quant.portfolio_allocator import PortfolioAllocator
from quant.portfolio_risk_engine import PortfolioRiskEngine
from quant.signal_engine import SignalEngine
from risk.trader_behavior_guard import TraderBehaviorGuard
from strategy.strategy_registry import StrategyRegistry
from models.candle import Candle

class TradingCore:
    """Main runtime orchestrator for live trading and simulated execution."""

    MAX_RUNTIME_ANALYSIS_BARS = 50_000
    ADAPTIVE_TRADE_HISTORY_LIMIT = 300
    ADAPTIVE_TRADE_CACHE_TTL_SECONDS = 15.0
    ADAPTIVE_WEIGHT_MIN = 0.75
    ADAPTIVE_WEIGHT_MAX = 1.35

    def __init__(self, controller: Optional[Any] = None) -> None:
        self.max_concurrent_symbols = None
        self.broker_name = None
        self.exchange_name = None
        self.controller = controller
        self.logger = logging.getLogger(__name__)

        self.broker = getattr(controller, "broker", None)
        self.candles: list[Candle] = []
        self.dataset = None
        self.normalized_symbol: Optional[str] = None

        if self.broker is None:
            raise RuntimeError("Broker not initialized")

        required_methods = ("fetch_ohlcv", "fetch_balance", "create_order")
        missing = [name for name in required_methods if not hasattr(
            self.broker, name)]
        if missing:
            raise RuntimeError(
                "Controller broker is missing required capabilities: "
                + ", ".join(missing)
            )

        self.symbols = list(getattr(controller, "symbols", ["USDCAD","EURUSD"
                            "BTC/USDT", "ETH/USDT"]) or [])

        # =========================
        # Core components
        # =========================

        self.strategy = StrategyRegistry()
        self._apply_strategy_preferences()

        self.data_hub = QuantDataHub(
            controller=self.controller,
            market_data_repository=getattr(
                controller, "market_data_repository", None),
            broker=self.broker,
        )

        self.session_manager = getattr(controller, "session_manager", None)
        self.signal_engine = SignalEngine(self.strategy)
        self.alpha_aggregator = getattr(
            self.signal_engine, "alpha_aggregator", None)

        self.event_bus = EventBus()
        self.portfolio = PortfolioManager(event_bus=self.event_bus)
        self.router = OrderRouter(broker=self.broker)

        self.behavior_guard = TraderBehaviorGuard(
            max_orders_per_hour=100,
            max_orders_per_day=200,
            max_consecutive_losses=4,
            cooldown_after_loss_seconds=900,
            same_symbol_reentry_cooldown_seconds=300,
            max_size_jump_ratio=3.0,
            daily_drawdown_limit_pct=0.06,
        )

        if self.controller is not None:
            self.controller.behavior_guard = self.behavior_guard

        self.execution_manager = ExecutionManager(
            broker=self.broker,
            event_bus=self.event_bus,
            router=self.router,
            trade_repository=getattr(controller, "trade_repository", None),
            trade_notifier=getattr(controller, "handle_trade_execution", None),
            behavior_guard=self.behavior_guard,
        )

        self.paper_trade_learning_repository = PaperTradeLearningRepository()
        self.paper_trade_dataset_builder = PaperTradeDatasetBuilder(
            repository=self.paper_trade_learning_repository
        )
        self.paper_trade_learning_service = PaperTradingLearningService(
            event_bus=self.event_bus,
            repository=self.paper_trade_learning_repository,
            exchange_resolver=self._active_exchange_code,
            tracked_sources={"bot"},
        )

        self.risk_engine: Optional[Any] = None
        self.portfolio_allocator: Optional[Any] = None
        self.portfolio_risk_engine: Optional[Any] = None
        self.orchestrator: Optional[Any] = None

        self.agent_decision_repository = None
        self.agent_memory = AgentMemory(max_events=2000)
        self.agent_memory.add_sink(self._persist_agent_memory_event)

        self.reasoning_engine = self._build_reasoning_engine()

        self.signal_agent_slots = max(
            1,
            int(getattr(controller, "max_signal_agents", 3) or 3),
        )

        self.signal_agents: list[SignalAgent] = []
        self.signal_agents.extend(
            SignalAgent(
                selector=self._select_strategy_signal_for_slot(slot_index),
                name=(
                    "SignalAgent"
                    if slot_index == 0
                    else f"SignalAgent{slot_index + 1}"
                ),
                news_bias_applier=self._apply_news_bias,
                memory=self.agent_memory,
                event_bus=self.event_bus,
                candidate_mode=True,
            )
            for slot_index in range(self.signal_agent_slots)
        )
        self.signal_aggregation_agent = SignalAggregationAgent(
            display_builder=self._build_display_signal,
            publisher=self._publish_signal_context,
            memory=self.agent_memory,
            event_bus=self.event_bus,
        )

        self.signal_consensus_agent = SignalConsensusAgent(
            minimum_votes=max(
                1,
                int(getattr(controller, "minimum_signal_votes", 2) or 2),
            ),
            memory=self.agent_memory,
            event_bus=self.event_bus,
        )

        self.signal_agent = self.signal_agents[0]

        self.agent_orchestrator = AgentOrchestrator(
            agents=[
                RegimeAgent(
                    snapshot_builder=self._build_regime_snapshot,
                    memory=self.agent_memory,
                    event_bus=self.event_bus,
                ),
                PortfolioAgent(
                    snapshot_builder=self._build_portfolio_snapshot,
                    memory=self.agent_memory,
                    event_bus=self.event_bus,
                ),
                TradingRiskAgent(
                    reviewer=self.review_signal,
                    memory=self.agent_memory,
                    event_bus=self.event_bus,
                ),
                TradingExecutionAgent(
                    executor=self.execute_review,
                    memory=self.agent_memory,
                    event_bus=self.event_bus,
                ),
            ]
        )

        self.event_driven_runtime = EventDrivenAgentRuntime(
            bus=self.event_bus,
            signal_agents=self.signal_agents,
            signal_consensus_agent=self.signal_consensus_agent,
            signal_aggregation_agent=self.signal_aggregation_agent,
            regime_agent=self.agent_orchestrator.agents[0],
            portfolio_agent=self.agent_orchestrator.agents[1],
            risk_agent=self.agent_orchestrator.agents[2],
            execution_agent=self.agent_orchestrator.agents[3],
        )

        # =========================
        # Runtime settings
        # =========================

        self.time_frame = getattr(controller, "time_frame", "1h")
        self.limit = getattr(controller, "limit", 50_000)
        self.running = False

        self._pipeline_status: dict[str, dict[str, Any]] = {}
        self._rejection_log_cache: dict[tuple[str, str, str], datetime] = {}
        self._adaptive_trade_cache = {
            "expires_at": 0.0,
            "limit": 0,
            "exchange": None,
            "rows": [],
        }
        self._signal_selection_executor: Optional[ThreadPoolExecutor] = None

        if self.controller is not None:
            self.controller.agent_memory = self.agent_memory
            self.controller.agent_orchestrator = self.agent_orchestrator
            self.controller.event_bus = self.event_bus
            self.controller.agent_event_runtime = self.event_driven_runtime
            self.controller.signal_agents = self.signal_agents
            self.controller.signal_consensus_agent = self.signal_consensus_agent
            self.controller.signal_aggregation_agent = self.signal_aggregation_agent
            self.controller.reasoning_engine = self.reasoning_engine
            self.controller.alpha_aggregator = self.alpha_aggregator
            self.controller.paper_trade_learning_repository = self.paper_trade_learning_repository
            self.controller.paper_trade_dataset_builder = self.paper_trade_dataset_builder
            self.controller.paper_trade_learning_service = self.paper_trade_learning_service

        self.trade_filter = TradeFilter(
            min_confidence=getattr(controller, "min_confidence", 0.65) or 0.65,
            min_vote_margin=getattr(
                controller, "min_vote_margin", 0.10) or 0.10,
            max_risk_score=getattr(controller, "max_risk_score", 0.7) or 0.7,
            allow_ranging=False,
            max_portfolio_exposure=getattr(
                controller, "max_portfolio_exposure", 0.85) or 0.85,
        )

        self.bind_agent_decision_repository(
            getattr(self.controller, "agent_decision_repository", None)
        )

        self.logger.info("InvestPro Trading System initialized")
    def configure_from_runtime_payload(self, payload: dict | None = None) -> None:
        """Configure TradingCore from a multiprocessing-safe runtime payload.
    
        This is used by DistributedOrchestrator child processes. Do not pass
        AppController, Qt widgets, broker sessions, or database sessions through
        multiprocessing. Pass only plain strings, numbers, bools, lists, and dicts.
        """
        payload = dict(payload or {})

        symbols = payload.get("symbols") or payload.get("watchlist") or []
        if isinstance(symbols, str):
          symbols = [
            item.strip().upper()
            for item in symbols.split(",")
            if item.strip()
        ]
        else:
                 symbols = [
            str(item).strip().upper()
            for item in symbols
            if str(item).strip()
        ]

        self.symbols = symbols

        self.broker_name = str(
        payload.get("broker_name")
        or payload.get("broker")
        or getattr(self, "broker_name", "")
        or ""
    ).strip().lower()

        self.exchange_name = str(
        payload.get("exchange_name")
        or payload.get("exchange")
        or self.broker_name
        or getattr(self, "exchange_name", "")
        or ""
    ).strip().lower()

        self.paper_mode = bool(
        payload.get("paper_mode", getattr(self, "paper_mode", False))
    )

        self.timeframe = str(
        payload.get("timeframe")
        or getattr(self, "timeframe", "1h")
        or "1h"
    ).strip() or "1h"

        self.limit = int(
        payload.get("limit")
        or getattr(self, "limit", 240)
        or 240
    )

        self.poll_interval = float(
        payload.get("poll_interval")
        or getattr(self, "poll_interval", 6.0)
        or 6.0
    )

        self.max_concurrent_symbols = int(
        payload.get("max_concurrent_symbols")
        or getattr(self, "max_concurrent_symbols", 5)
        or 5
    )

       
    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _safe_numeric_value(self, value: Any, fallback: float) -> float:
        if value in (None, ""):
            return float(fallback)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return float(fallback)
            value = cleaned
        try:
            return float(value)
        except Exception:
            return float(fallback)

    def _flag_enabled(self, value: Any, default: bool = False) -> bool:
        if value in (None, ""):
            return bool(default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    # ------------------------------------------------------------------
    # Strategy config
    # ------------------------------------------------------------------

    def _apply_strategy_preferences(self) -> None:
        strategy_name = getattr(self.controller, "strategy_name", None)
        strategy_params = getattr(self.controller, "strategy_params", None)
        self.strategy.configure(
            strategy_name=strategy_name, params=strategy_params)

    def refresh_strategy_preferences(self) -> None:
        self._apply_strategy_preferences()
        if self.portfolio_allocator is not None:
            weight_resolver = (
                getattr(self.controller, "active_strategy_weight_map", None)
                if self.controller is not None
                else None
            )
            weights = (
                weight_resolver()
                if callable(weight_resolver)
                else {str(getattr(self.controller, "strategy_name", "Trend Following")): 1.0}
            )
            self.portfolio_allocator.configure_strategy_weights(
                strategy_weights=weights,
                allocation_model="equal_weight",
            )

    def _resolve_runtime_history_limit(self, limit: Optional[int] = None) -> int:
        requested = max(1, int(limit or self.limit or 300))

        configured_cap = (
            getattr(self.controller, "runtime_history_limit", None)
            if self.controller is not None
            else None
        )

        try:
            runtime_cap = max(
                100, int(configured_cap or self.MAX_RUNTIME_ANALYSIS_BARS))
        except Exception:
            runtime_cap = self.MAX_RUNTIME_ANALYSIS_BARS

        broker_cap = getattr(self.broker, "MAX_OHLCV_COUNT", None)
        try:
            broker_cap = max(1, int(broker_cap)
                             ) if broker_cap is not None else None
        except Exception:
            broker_cap = None

        effective_cap = runtime_cap if broker_cap is None else min(
            runtime_cap, broker_cap)
        return max(1, min(requested, effective_cap))

    # ------------------------------------------------------------------
    # Reasoning
    # ------------------------------------------------------------------

    def _build_reasoning_engine(self) -> ReasoningEngine:
        controller = self.controller

        enabled = self._flag_enabled(
            getattr(controller, "reasoning_enabled", True),
            default=True,
        )
        mode = str(
            getattr(controller, "reasoning_mode", "assistive") or "assistive"
        ).strip().lower() or "assistive"

        minimum_confidence = self._safe_numeric_value(
            getattr(controller, "reasoning_min_confidence", 0.75),
            0.75,
        )
        timeout_seconds = self._safe_numeric_value(
            getattr(controller, "reasoning_timeout_seconds", 8.0),
            8.0,
        )
        provider_name = str(
            getattr(controller, "reasoning_provider", "auto") or "auto"
        ).strip().lower() or "auto"

        api_key = str(getattr(controller, "openai_api_key", "") or "").strip()
        model_name = str(
            getattr(controller, "openai_model", "gpt-5-mini") or "gpt-5-mini"
        ).strip() or "gpt-5-mini"

        provider = None
        if provider_name in {"auto", "openai"} and api_key:
            provider = OpenAIReasoningProvider(
                api_key=api_key,
                model=model_name,
                timeout_seconds=timeout_seconds,
                logger=self.logger,
            )
        elif provider_name == "heuristic":
            provider = HeuristicReasoningProvider()

        return ReasoningEngine(
            provider=provider,
            fallback_provider=HeuristicReasoningProvider(),
            enabled=enabled,
            mode=mode,
            minimum_confidence=minimum_confidence,
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Strategy assignment / adaptive weighting
    # ------------------------------------------------------------------

    def _assigned_strategies_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        portfolio_resolver = (
            getattr(self.controller, "strategy_portfolio_profile_for_symbol", None)
            if self.controller is not None
            else None
        )

        if callable(portfolio_resolver):
            try:
                assigned = list(portfolio_resolver(symbol) or [])
            except Exception:
                assigned = []
            if assigned:
                return assigned

        resolver = (
            getattr(self.controller, "assigned_strategies_for_symbol", None)
            if self.controller is not None
            else None
        )

        if callable(resolver):
            try:
                assigned = list(resolver(symbol) or [])
            except Exception:
                assigned = []
            if assigned:
                return assigned

        fallback_name = str(
            getattr(self.controller, "strategy_name",
                    None) or "Trend Following"
        ).strip() or "Trend Following"

        return [
            {
                "strategy_name": fallback_name,
                "score": 1.0,
                "weight": 1.0,
                "rank": 1,
                "timeframe": self.time_frame or "1h",
            }
        ]

    def _assigned_timeframe_for_symbol(self, symbol: str, fallback: Optional[str] = None) -> str:
        assigned = self._assigned_strategies_for_symbol(symbol)
        for row in list(assigned or []):
            timeframe = str(row.get("timeframe") or "").strip()
            if timeframe:
                return timeframe
        return str(fallback or self.time_frame or "1h").strip() or "1h"

    async def _strategy_signal_candidates(
        self,
        normalized_symbol: str,
        candles: list[Any],
        dataset: Any,
        assignments: list[dict[str, Any]],
    ) -> list[tuple[float, float, dict[str, Any]]]:
        candidates: list[tuple[float, float, dict[str, Any]]] = []

        for assignment in list(assignments or []):
            strategy_name = str(assignment.get("strategy_name") or "").strip()
            if not strategy_name:
                continue

            assignment_timeframe = str(
                assignment.get("timeframe")
                or getattr(dataset, "timeframe", None)
                or self.time_frame
                or "1h"
            ).strip() or "1h"

            signal_result = self.signal_engine.generate_signal(
                candles=candles,
                dataset=dataset,
                strategy_name=strategy_name,
                symbol=normalized_symbol,
            )
            signal = await self._maybe_await(signal_result)

            if not signal:
                continue

            if not isinstance(signal, dict):
                continue

            assignment_weight = max(0.0001, float(
                assignment.get("weight", 0.0) or 0.0))
            weighted_confidence = float(signal.get(
                "confidence", 0.0) or 0.0) * assignment_weight

            adaptive_profile = self._adaptive_profile_for_strategy(
                normalized_symbol,
                strategy_name,
                timeframe=assignment_timeframe,
            )

            enriched = dict(signal)
            enriched["strategy_name"] = strategy_name
            enriched["timeframe"] = assignment_timeframe
            enriched["strategy_assignment_weight"] = assignment_weight
            enriched["strategy_assignment_score"] = float(
                assignment.get("score", 0.0) or 0.0)
            enriched["strategy_assignment_rank"] = int(
                assignment.get("rank", 0) or 0)
            enriched["adaptive_weight"] = float(
                adaptive_profile.get("adaptive_weight", 1.0) or 1.0)
            enriched["adaptive_score"] = weighted_confidence * \
                enriched["adaptive_weight"]
            enriched["adaptive_sample_size"] = int(
                adaptive_profile.get("sample_size", 0) or 0)
            enriched["adaptive_win_rate"] = adaptive_profile.get("win_rate")
            enriched["adaptive_avg_pnl"] = adaptive_profile.get("average_pnl")
            enriched["adaptive_feedback_scope"] = adaptive_profile.get("scope")

            candidates.append(
                (
                    enriched["adaptive_score"],
                    float(assignment.get("score", 0.0) or 0.0),
                    enriched,
                )
            )

        return candidates

    async def _select_strategy_signal(self, normalized_symbol: str, candles: list[Any], dataset: Any) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
        assigned = self._assigned_strategies_for_symbol(normalized_symbol)
        candidates = await self._strategy_signal_candidates(
            normalized_symbol,
            candles,
            dataset,
            assigned,
        )
        if not candidates:
            return None, assigned

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2], assigned

    def _select_strategy_signal_for_slot(self, slot_index: int):
        async def selector(normalized_symbol: str, candles: list[Any], dataset: Any):
            assigned = self._assigned_strategies_for_symbol(normalized_symbol)
            scoped_assignments = list(assigned[slot_index: slot_index + 1])

            candidates = await self._strategy_signal_candidates(
                normalized_symbol,
                candles,
                dataset,
                scoped_assignments,
            )

            if not candidates:
                return None, scoped_assignments

            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return candidates[0][2], scoped_assignments

        return selector

    def _normalized_symbol_aliases(self, symbol: str) -> set[str]:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return set()

        aliases = {normalized}
        if "/" in normalized:
            aliases.add(normalized.replace("/", "_"))
        if "_" in normalized:
            aliases.add(normalized.replace("_", "/"))

        return aliases

    def _row_exchange_value(self, trade: Any) -> Optional[str]:
        if isinstance(trade, dict):
            exchange = trade.get("exchange")
        else:
            exchange = getattr(trade, "exchange", None)
        return str(exchange or "").strip().lower() or None

    def _recent_trade_history(self, limit: Optional[int] = None) -> list[Any]:
        requested_limit = max(
            10, int(limit or self.ADAPTIVE_TRADE_HISTORY_LIMIT))
        repository = (
            getattr(self.controller, "trade_repository", None)
            if self.controller is not None
            else None
        )

        if repository is None or not hasattr(repository, "get_trades"):
            return []

        exchange_code = self._active_exchange_code()

        now = time.monotonic()
        cache = dict(self._adaptive_trade_cache or {})
        cached_rows = list(cache.get("rows") or [])

        if (
            cached_rows
            and now < float(cache.get("expires_at", 0.0) or 0.0)
            and int(cache.get("limit", 0) or 0) >= requested_limit
            and str(cache.get("exchange") or "").strip().lower() == str(exchange_code or "").strip().lower()
        ):
            return cached_rows[:requested_limit]

        try:
            rows = list(repository.get_trades(
                limit=requested_limit, exchange=exchange_code) or [])
        except TypeError:
            try:
                rows = list(repository.get_trades(limit=requested_limit) or [])
            except Exception:
                self.logger.debug(
                    "Unable to load recent trade history for adaptive scoring", exc_info=True)
                rows = []

            row_exchanges = [self._row_exchange_value(row) for row in rows]
            if exchange_code and any(value for value in row_exchanges):
                rows = [
                    row
                    for row, row_exchange in zip(rows, row_exchanges)
                    if row_exchange == exchange_code
                ]
        except Exception:
            self.logger.debug(
                "Unable to load recent trade history for adaptive scoring", exc_info=True)
            rows = []

        self._adaptive_trade_cache = {
            "expires_at": now + self.ADAPTIVE_TRADE_CACHE_TTL_SECONDS,
            "limit": requested_limit,
            "exchange": exchange_code,
            "rows": list(rows),
        }

        return rows

    def _trade_feedback_signal(self, trade: Any) -> Optional[dict[str, Any]]:
        pnl_value = getattr(trade, "pnl", None)
        if isinstance(trade, dict):
            pnl_value = trade.get("pnl", pnl_value)

        pnl = None
        if pnl_value not in (None, ""):
            try:
                pnl = float(pnl_value)
            except Exception:
                pnl = None

        if pnl is not None:
            if pnl > 0:
                return {"score": 1.0, "pnl": pnl}
            if pnl < 0:
                return {"score": -1.0, "pnl": pnl}
            return {"score": 0.0, "pnl": pnl}

        outcome = str(getattr(trade, "outcome", None) or "").strip().lower()
        if isinstance(trade, dict):
            outcome = str(trade.get("outcome") or outcome).strip().lower()

        if outcome:
            if any(token in outcome for token in ("win", "profit", "target", "take profit")):
                return {"score": 1.0, "pnl": None}
            if any(token in outcome for token in ("loss", "losing", "stop", "stopped")):
                return {"score": -1.0, "pnl": None}
            if "break even" in outcome or "breakeven" in outcome:
                return {"score": 0.0, "pnl": None}

        return None

    def _trade_timestamp_value(self, value: Any) -> Optional[float]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc).timestamp()
            return value.astimezone(timezone.utc).timestamp()

        if value in (None, ""):
            return None

        try:
            numeric = float(value)
        except Exception:
            numeric = None

        if numeric is not None:
            if abs(numeric) > 1e11:
                numeric = numeric / 1000.0
            return float(numeric)

        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(text)
        except Exception:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).timestamp()

    def _adaptive_profile_for_strategy(self, normalized_symbol: str, strategy_name: str, timeframe: Optional[str]) -> dict[str, Any]:
        strategy_text = str(strategy_name or "").strip().lower()
        if not strategy_text:
            return {
                "adaptive_weight": 1.0,
                "sample_size": 0,
                "win_rate": None,
                "average_pnl": None,
                "scope": "none",
            }

        symbol_aliases = self._normalized_symbol_aliases(normalized_symbol)
        timeframe_text = str(timeframe or "").strip().lower()

        matched_exact = []
        matched_fallback = []

        for trade in self._recent_trade_history():
            trade_symbol = str(
                (trade.get("symbol") if isinstance(trade, dict)
                 else getattr(trade, "symbol", None))
                or ""
            ).strip().upper()

            if symbol_aliases and trade_symbol not in symbol_aliases:
                continue

            trade_strategy = str(
                (trade.get("strategy_name") if isinstance(trade, dict)
                 else getattr(trade, "strategy_name", None))
                or ""
            ).strip().lower()

            if trade_strategy != strategy_text:
                continue

            trade_timeframe = str(
                (trade.get("timeframe") if isinstance(trade, dict)
                 else getattr(trade, "timeframe", None))
                or ""
            ).strip().lower()

            if timeframe_text and trade_timeframe == timeframe_text:
                matched_exact.append(trade)
            elif not timeframe_text or not trade_timeframe:
                matched_fallback.append(trade)

        scoped_rows = matched_exact or matched_fallback
        feedback = [
            row
            for row in (self._trade_feedback_signal(trade) for trade in scoped_rows)
            if row is not None
        ]

        if not feedback:
            return {
                "adaptive_weight": 1.0,
                "sample_size": 0,
                "win_rate": 0,
                "average_pnl": 0,
                "scope": "timeframe" if matched_exact else "strategy",
            }

        sample_size = len(feedback)
        average_score = sum(float(item.get("score", 0.0) or 0.0)
                            for item in feedback) / float(sample_size)
        sample_strength = min(1.0, float(sample_size) / 6.0)

        adaptive_weight = 1.0 + (0.35 * average_score * sample_strength)
        adaptive_weight = max(
            self.ADAPTIVE_WEIGHT_MIN,
            min(self.ADAPTIVE_WEIGHT_MAX, adaptive_weight),
        )

        pnl_samples = [
            float(item["pnl"])
            for item in feedback
            if item.get("pnl") is not None
        ]
        wins = sum(1 for item in feedback if float(
            item.get("score", 0.0) or 0.0) > 0)

        return {
            "adaptive_weight": adaptive_weight,
            "sample_size": sample_size,
            "win_rate": wins / float(sample_size),
            "average_pnl": (sum(pnl_samples) / float(len(pnl_samples))) if pnl_samples else None,
            "scope": "timeframe" if matched_exact else "strategy",
        }

    def adaptive_profile_for_strategy(self, symbol: str, strategy_name: str, timeframe: Optional[str] = None) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        self.normalized_symbol = normalized_symbol

        timeframe_value = str(
            timeframe or self.time_frame or "1h").strip() or "1h"

        profile = dict(
            self._adaptive_profile_for_strategy(
                normalized_symbol,
                strategy_name,
                timeframe=timeframe_value,
            )
        )

        profile["symbol"] = normalized_symbol
        profile["strategy_name"] = str(strategy_name or "").strip()
        profile["timeframe"] = timeframe_value
        profile["exchange"] = self._active_exchange_code()

        return profile

    def adaptive_trade_samples_for_strategy(
        self,
        symbol: str,
        strategy_name: str,
        timeframe: Optional[str] = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        self.normalized_symbol = normalized_symbol

        strategy_text = str(strategy_name or "").strip()
        timeframe_value = str(
            timeframe or self.time_frame or "1h").strip() or "1h"

        if not normalized_symbol or not strategy_text:
            return {
                "symbol": normalized_symbol,
                "strategy_name": strategy_text,
                "timeframe": timeframe_value,
                "scope": "none",
                "samples": [],
                "profile": {},
            }

        strategy_key = strategy_text.lower()
        symbol_aliases = self._normalized_symbol_aliases(normalized_symbol)

        exact_matches: list[dict[str, Any]] = []
        fallback_matches: list[dict[str, Any]] = []

        scan_limit = max(max(1, int(limit or 8)) * 10,
                         self.ADAPTIVE_TRADE_HISTORY_LIMIT)

        for trade in self._recent_trade_history(limit=scan_limit):
            trade_symbol = str(
                (trade.get("symbol") if isinstance(trade, dict)
                 else getattr(trade, "symbol", None))
                or ""
            ).strip().upper()

            if symbol_aliases and trade_symbol not in symbol_aliases:
                continue

            trade_strategy = str(
                (trade.get("strategy_name") if isinstance(trade, dict)
                 else getattr(trade, "strategy_name", None))
                or ""
            ).strip().lower()

            if trade_strategy != strategy_key:
                continue

            feedback = self._trade_feedback_signal(trade)
            if feedback is None:
                continue

            getter = trade.get if isinstance(
                trade, dict) else lambda key, default=None: getattr(trade, key, default)

            trade_timeframe = str(getter("timeframe", "") or "").strip()

            sample = {
                "timestamp": getter("timestamp", None),
                "status": str(getter("status", "") or "").strip(),
                "side": str(getter("side", "") or "").strip(),
                "timeframe": trade_timeframe,
                "pnl": feedback.get("pnl"),
                "score": float(feedback.get("score", 0.0) or 0.0),
                "outcome": str(getter("outcome", "") or "").strip(),
                "reason": str(getter("reason", "") or "").strip(),
                "source_agent": str(getter("signal_source_agent", "") or "").strip(),
                "consensus_status": str(getter("consensus_status", "") or "").strip(),
                "adaptive_weight": getter("adaptive_weight", None),
                "adaptive_score": getter("adaptive_score", None),
            }

            if trade_timeframe.lower() == timeframe_value.lower():
                exact_matches.append(sample)
            elif not trade_timeframe:
                fallback_matches.append(sample)

        samples = list((exact_matches or fallback_matches)
                       [: max(1, int(limit or 8))])

        return {
            "symbol": normalized_symbol,
            "strategy_name": strategy_text,
            "timeframe": timeframe_value,
            "exchange": self._active_exchange_code(),
            "scope": "timeframe" if exact_matches else "strategy",
            "samples": samples,
            "profile": self.adaptive_profile_for_strategy(
                normalized_symbol,
                strategy_text,
                timeframe=timeframe_value,
            ),
        }

    def adaptive_weight_timeline_for_strategy(
        self,
        symbol: str,
        strategy_name: str,
        timeframe: Optional[str] = None,
        limit: int = 16,
    ) -> dict[str, Any]:
        detail = self.adaptive_trade_samples_for_strategy(
            symbol,
            strategy_name,
            timeframe=timeframe,
            limit=max(8, int(limit or 16)),
        )

        sample_rows = list(detail.get("samples") or [])
        if not sample_rows:
            return {
                "symbol": detail.get("symbol"),
                "strategy_name": detail.get("strategy_name"),
                "timeframe": detail.get("timeframe"),
                "scope": detail.get("scope"),
                "timeline": [],
                "profile": dict(detail.get("profile") or {}),
            }

        ordered_samples = list(sample_rows)
        ordered_samples.sort(
            key=lambda row: self._trade_timestamp_value(
                row.get("timestamp")) or 0.0
        )

        timeline = []
        running_scores = []

        for index, sample in enumerate(ordered_samples, start=1):
            score = float(sample.get("score", 0.0) or 0.0)
            running_scores.append(score)
            average_score = sum(running_scores) / float(len(running_scores))
            sample_strength = min(1.0, float(len(running_scores)) / 6.0)

            adaptive_weight = 1.0 + (0.35 * average_score * sample_strength)
            adaptive_weight = max(
                self.ADAPTIVE_WEIGHT_MIN,
                min(self.ADAPTIVE_WEIGHT_MAX, adaptive_weight),
            )

            timeline.append(
                {
                    "timestamp": sample.get("timestamp"),
                    "timestamp_value": self._trade_timestamp_value(sample.get("timestamp")),
                    "adaptive_weight": adaptive_weight,
                    "score": score,
                    "pnl": sample.get("pnl"),
                    "reason": sample.get("reason"),
                    "side": sample.get("side"),
                    "sample_index": index,
                }
            )

        return {
            "symbol": detail.get("symbol"),
            "strategy_name": detail.get("strategy_name"),
            "timeframe": detail.get("timeframe"),
            "scope": detail.get("scope"),
            "timeline": timeline[-max(1, int(limit or 16)):],
            "profile": dict(detail.get("profile") or {}),
        }

    # ------------------------------------------------------------------
    # Pipeline status / repositories
    # ------------------------------------------------------------------

    def _record_pipeline_status(
        self,
        symbol: str,
        stage: Any,
        status: Any,
        detail: Any = None,
        signal: Optional[dict[str, Any]] = None,
    ) -> None:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return

        snapshot = {
            "symbol": normalized_symbol,
            "stage": str(stage or "").strip() or "unknown",
            "status": str(status or "").strip() or "unknown",
            "detail": str(detail or "").strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if isinstance(signal, dict):
            snapshot["strategy_name"] = signal.get("strategy_name") or getattr(
                self.controller, "strategy_name", None)
            snapshot["side"] = signal.get("side")
            snapshot["confidence"] = signal.get("confidence")

        self._pipeline_status[normalized_symbol] = snapshot

    def pipeline_status_snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            symbol: dict(payload)
            for symbol, payload in (self._pipeline_status or {}).items()
        }

    def agent_memory_snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.agent_memory.snapshot(limit=limit) if self.agent_memory is not None else []

    def bind_agent_decision_repository(self, repository: Any) -> Any:
        self.agent_decision_repository = repository
        if self.controller is not None:
            self.controller.agent_decision_repository = repository
        return repository

    def _active_exchange_code(self) -> Optional[str]:
        resolver = (
            getattr(self.controller, "_active_exchange_code", None)
            if self.controller is not None
            else None
        )

        if callable(resolver):
            try:
                exchange_name = resolver()
            except Exception:
                exchange_name = None
            normalized = str(exchange_name or "").strip().lower()
            if normalized:
                return normalized

        exchange_name = getattr(
            self.broker, "exchange_name", None) if self.broker is not None else None
        normalized = str(exchange_name or "").strip().lower()
        if normalized:
            return normalized

        if self.controller is not None:
            exchange_name = getattr(self.controller, "exchange", None)
            normalized = str(exchange_name or "").strip().lower()
            if normalized:
                return normalized

            broker_config = getattr(
                getattr(self.controller, "config", None), "broker", None)
            normalized = str(
                getattr(broker_config, "exchange", None) or "").strip().lower()
            if normalized:
                return normalized

        return None

    def _current_account_label(self) -> Optional[str]:
        resolver = (
            getattr(self.controller, "current_account_label", None)
            if self.controller is not None
            else None
        )

        if callable(resolver):
            try:
                label = resolver()
            except Exception:
                label = None
        else:
            label = None

        if str(label or "").strip().lower() == "not set":
            label = None

        return str(label or "").strip() or None

    def _persist_agent_memory_event(self, event: dict[str, Any]) -> Any:
        repository = getattr(self, "agent_decision_repository", None)

        if repository is None or not hasattr(repository, "save_decision") or not isinstance(event, dict):
            return None

        payload = dict(event.get("payload") or {})

        try:
            return repository.save_decision(
                agent_name=event.get("agent"),
                stage=event.get("stage"),
                symbol=event.get("symbol"),
                decision_id=event.get("decision_id"),
                exchange=self._active_exchange_code(),
                account_label=self._current_account_label(),
                strategy_name=payload.get("strategy_name"),
                timeframe=payload.get("timeframe"),
                side=payload.get("side"),
                confidence=payload.get("confidence"),
                approved=payload.get("approved"),
                reason=payload.get("reason"),
                payload=payload,
                timestamp=event.get("timestamp"),
            )
        except Exception:
            self.logger.debug(
                "Unable to persist agent decision ledger entry", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Reasoning events
    # ------------------------------------------------------------------

    def _reasoning_risk_limits(self) -> dict[str, float]:
        controller = self.controller
        return {
            "max_risk_per_trade": self._safe_numeric_value(getattr(controller, "max_risk_per_trade", 0.02), 0.02),
            "max_portfolio_risk": self._safe_numeric_value(getattr(controller, "max_portfolio_risk", 0.10), 0.10),
            "max_position_size_pct": self._safe_numeric_value(getattr(controller, "max_position_size_pct", 0.10), 0.10),
            "max_gross_exposure_pct": self._safe_numeric_value(getattr(controller, "max_gross_exposure_pct", 2.0), 2.0),
        }

    async def _publish_reasoning_event(self, review: dict[str, Any], reasoning: dict[str, Any]) -> None:
        if self.event_bus is None or not isinstance(review, dict) or not isinstance(reasoning, dict):
            return

        payload = {
            "symbol": review.get("symbol"),
            "decision_id": review.get("decision_id"),
            "strategy_name": review.get("strategy_name"),
            "timeframe": review.get("timeframe"),
            "side": review.get("side"),
            "amount": review.get("amount"),
            "price": review.get("price"),
            "reason": reasoning.get("reasoning"),
            "decision": reasoning.get("decision"),
            "confidence": reasoning.get("confidence"),
            "risk": reasoning.get("risk"),
            "warnings": list(reasoning.get("warnings") or []),
            "provider": reasoning.get("provider"),
            "mode": reasoning.get("mode"),
        }

        if self.event_bus:

         result = self.event_bus.publish(
            Event(EventType.REASONING_DECISION, payload))
         await self._maybe_await(result)

    def _remember_reasoning(self, review: dict[str, Any], reasoning: dict[str, Any]) -> Any:
        if self.agent_memory is None or not isinstance(review, dict) or not isinstance(reasoning, dict):
            return None

        stage = "assistive"
        if not review.get("approved") and str(review.get("stage") or "").strip().lower() == "reasoning_engine":
            stage = "rejected"
        elif str(reasoning.get("mode") or "").strip().lower() != "assistive":
            stage = "approved"

        payload = {
            "strategy_name": review.get("strategy_name"),
            "timeframe": review.get("timeframe"),
            "side": review.get("side"),
            "approved": review.get("approved"),
            "confidence": reasoning.get("confidence"),
            "reason": reasoning.get("reasoning"),
            "decision": reasoning.get("decision"),
            "risk": reasoning.get("risk"),
            "warnings": list(reasoning.get("warnings") or []),
            "provider": reasoning.get("provider"),
            "mode": reasoning.get("mode"),
            "latency_ms": reasoning.get("latency_ms"),
        }
        return self.agent_memory.store(
            agent="ReasoningEngine",
            stage=stage,
            payload=payload,
            symbol=review.get("symbol"),
            decision_id=review.get("decision_id"),
        )

    def _publish_reasoning_signal(self, review: dict[str, Any]) -> None:
        if self.controller is None or not hasattr(self.controller, "publish_ai_signal") or not isinstance(review, dict):
            return

        signal = dict(review.get("signal") or {})
        reasoning = dict(review.get("reasoning") or {})
        if not signal or not reasoning:
            return

        dataset = review.get("dataset")
        candles = dataset.to_candles() if dataset is not None and hasattr(
            dataset, "to_candles") else []

        self.dataset = dataset
        self.candles = list(candles or [])

        summary = str(reasoning.get("reasoning")
                      or signal.get("reason") or "").strip()
        warnings = [str(item).strip() for item in list(
            reasoning.get("warnings") or []) if str(item).strip()]

        if warnings:
            warning_text = "Warnings: " + " | ".join(warnings[:3])
            summary = f"{summary} {warning_text}".strip()

        enriched = dict(signal)
        enriched["reason"] = summary or signal.get("reason")
        enriched["confidence"] = reasoning.get(
            "confidence", signal.get("confidence"))
        enriched["reasoning"] = dict(reasoning)
        enriched["risk"] = reasoning.get("risk")
        enriched["warnings"] = warnings
        enriched["reasoning_decision"] = reasoning.get("decision")

        self.controller.publish_ai_signal(
            review.get("symbol"), enriched, candles=candles)

    async def _apply_reasoning_review(self, review: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(review, dict) or not review.get("symbol"):
            return review

        reasoning_engine = self.reasoning_engine
        filter_score = 1.0

        if reasoning_engine and getattr(reasoning_engine, "enabled", False):
            reasoning_decision = await reasoning_engine.evaluate(
                symbol=review.get("symbol"),
                signal=review.get("signal") or {},
                dataset=review.get("dataset"),
                timeframe=review.get("timeframe"),
                regime_snapshot=review.get("regime_snapshot"),
                portfolio_snapshot=review.get("portfolio_snapshot"),
                risk_limits=self._reasoning_risk_limits(),
            )

            if reasoning_decision:
                reasoning = reasoning_decision.to_dict()
                review["reasoning"] = reasoning
                review["decision"] = reasoning_decision.decision
                review["confidence"] = reasoning_decision.confidence
                review["reasoning_decision"] = reasoning_decision.decision
                review["reasoning_confidence"] = reasoning_decision.confidence
                review["reasoning_provider"] = reasoning.get("provider")
                review["reasoning_mode"] = reasoning.get("mode")

                self._remember_reasoning(review, reasoning)
                await self._publish_reasoning_event(review, reasoning)
                self._publish_reasoning_signal(review)

                mode = str(reasoning.get("mode")
                           or "assistive").strip().lower() or "assistive"

                if mode != "assistive":
                    if (
                        not getattr(reasoning_decision, "should_execute", True)
                        or reasoning_decision.decision == "REJECT"
                    ):
                        review["approved"] = False
                        review["stage"] = "reasoning_engine"
                        review["reason"] = reasoning.get(
                            "reasoning") or "Reasoning engine rejected the trade."
                        return review

                    portfolio_snapshot = review.get("portfolio_snapshot") or {}
                    filter_result = self.trade_filter.evaluate(
                        reasoning_decision,
                        portfolio_snapshot=portfolio_snapshot,
                    )

                    if not filter_result.approved:
                        review["approved"] = False
                        review["stage"] = "trade_filter"
                        review["reason"] = filter_result.reason
                        review["filter_score"] = filter_result.score
                        return review

                    filter_score = float(filter_result.score or 1.0)

        if getattr(self, "daily_drawdown", 0) > getattr(self, "max_daily_drawdown", 1):
            review["approved"] = False
            review["stage"] = "kill_switch"
            review["reason"] = "Max daily drawdown exceeded"
            return review

        base_amount = float(review.get("amount") or 0.0)
        review["amount"] = base_amount * max(0.2, min(1.5, filter_score))
        review["filter_score"] = filter_score
        review["approved"] = True

        if str(review.get("stage") or "").strip().lower() in {"", "review", "approved"}:
            review["stage"] = "approved"

        return review

    # ------------------------------------------------------------------
    # Agents / signal context
    # ------------------------------------------------------------------

    def _custom_process_signal_handler(self):
        handler = getattr(self, "process_signal", None)
        if not callable(handler):
            return None

        # If process_signal was overridden in a monkey patch, use it.
        if getattr(handler, "__func__", handler) is not TradingCore.process_signal:
            return handler

        return None

    async def _run_signal_agents(self, context: dict[str, Any]) -> dict[str, Any]:
        working = dict(context or {})

        if len(list(self.signal_agents or [])) <= 1 and self.signal_aggregation_agent is None:
            signal_agent = self.signal_agent
            return await signal_agent.process(working) if signal_agent is not None else working

        working = await run_signal_agents_parallel(self.signal_agents, working)

        if self.signal_consensus_agent is not None:
            working = await self.signal_consensus_agent.process(working)

        if self.signal_aggregation_agent is not None:
            working = await self.signal_aggregation_agent.process(working)

        return working

    def _build_display_signal(
        self,
        context: dict[str, Any],
        signal: Optional[dict[str, Any]],
        assigned_strategies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbol = str((context or {}).get("symbol") or "").strip().upper()
        default_strategy_name = str(
            getattr(self.controller, "strategy_name",
                    None) or "Trend Following"
        ).strip() or "Trend Following"

        display_strategy_name = signal.get(
            "strategy_name") if isinstance(signal, dict) else None
        if not display_strategy_name:
            display_strategy_name = ", ".join(
                str(item.get("strategy_name") or "").strip()
                for item in list(assigned_strategies or [])[:3]
                if str(item.get("strategy_name") or "").strip()
            ) or default_strategy_name

        if isinstance(signal, dict):
            display_signal = dict(signal)
            display_signal.setdefault("symbol", symbol)
            display_signal.setdefault("strategy_name", display_strategy_name)
            return display_signal

        hold_reason = str((context or {}).get(
            "signal_hold_reason") or "").strip()

        if (context or {}).get("blocked_by_news_bias"):
            reason = str(
                (context or {}).get("news_bias_reason")
                or "Signal was neutralized by news bias controls."
            ).strip()
        elif hold_reason:
            reason = hold_reason
        else:
            reason = "No entry signal on the latest scan."

        return {
            "symbol": symbol,
            "side": "hold",
            "amount": 0.0,
            "confidence": 0.0,
            "reason": reason,
            "strategy_name": display_strategy_name,
        }

    def _publish_signal_context(self, context: dict[str, Any], display_signal: dict[str, Any]) -> None:
        if not (context or {}).get("publish_debug"):
            return

        features = (context or {}).get("features")
        self.candles = list((context or {}).get("candles") or [])
        symbol = str((context or {}).get("symbol") or "").strip().upper()

        if self.controller and hasattr(self.controller, "publish_ai_signal"):
            self.controller.publish_ai_signal(
                symbol, display_signal, candles=self.candles)

        if self.controller and hasattr(self.controller, "publish_strategy_debug"):
            self.controller.publish_strategy_debug(
                symbol,
                display_signal,
                candles=self.candles,
                features=features,
            )

    async def _apply_news_bias(self, symbol: str, signal: dict[str, Any]) -> dict[str, Any]:
        if self.controller and hasattr(self.controller, "apply_news_bias_to_signal"):
            return await self.controller.apply_news_bias_to_signal(symbol, signal)
        return signal

    def _feature_frame_for_context(
        self,
        candles: Optional[list[Any]] = None,
        dataset: Any = None,
        strategy_name: Optional[str] = None,
    ) -> Any:
        strategy = (
            self.strategy._resolve_strategy(strategy_name)
            if hasattr(self.strategy, "_resolve_strategy")
            else self.strategy
        )

        if strategy is None or not hasattr(strategy, "compute_features"):
            return getattr(dataset, "frame", None)

        candle_rows = candles or self.candles or []

        if not candle_rows and dataset is not None:
            try:
                candle_rows = dataset.to_candles()
            except Exception:
                candle_rows = []

        try:
            return strategy.compute_features(candle_rows)
        except Exception:
            return getattr(dataset, "frame", None)

    # ------------------------------------------------------------------
    # Snapshot builders
    # ------------------------------------------------------------------

    def _build_regime_snapshot(
        self,
        symbol: Optional[str] = None,
        signal: Optional[dict[str, Any]] = None,
        candles: Optional[list[Any]] = None,
        dataset: Any = None,
        timeframe: Optional[str] = None,
    ) -> dict[str, Any]:
        if isinstance(signal, dict) and isinstance(signal.get("regime_snapshot"), dict):
            snapshot = dict(signal.get("regime_snapshot") or {})
            primary = str(snapshot.get("primary") or signal.get(
                "regime") or "unknown").strip()

            return {
                "symbol": str(symbol or "").strip().upper(),
                "timeframe": str(timeframe or self.time_frame or "1h").strip() or "1h",
                "regime": primary,
                "volatility": str(
                    snapshot.get("volatility")
                    or (
                        "high"
                        if "HIGH_VOLATILITY" in list(snapshot.get("active_regimes") or [])
                        else "low"
                    )
                ).strip(),
                "atr_pct": self._safe_numeric_value(snapshot.get("atr_pct"), 0.0),
                "trend_strength": self._safe_numeric_value(snapshot.get("metadata", {}).get("trend_strength"), 0.0),
                "momentum": self._safe_numeric_value(snapshot.get("metadata", {}).get("momentum"), 0.0),
                "band_position": self._safe_numeric_value(snapshot.get("metadata", {}).get("band_position"), 0.5),
                "active_regimes": list(snapshot.get("active_regimes") or []),
                "adx": self._safe_numeric_value(snapshot.get("adx"), 0.0),
                "realized_volatility": self._safe_numeric_value(snapshot.get("realized_volatility"), 0.0),
                "liquidity_score": self._safe_numeric_value(snapshot.get("liquidity_score"), 0.0),
                "metadata": dict(snapshot.get("metadata") or {}),
            }

        feature_frame = self._feature_frame_for_context(
            candles or self.candles or [],
            dataset=dataset,
            strategy_name=(signal or {}).get(
                "strategy_name") if isinstance(signal, dict) else None,
        )

        regime_engine = getattr(self.signal_engine, "regime_engine", None)

        try:
            regime = regime_engine.classify_frame(
                feature_frame) if regime_engine is not None else "unknown"
        except Exception:
            regime = "unknown"

        atr_pct = 0.0
        trend_strength = 0.0
        momentum = 0.0
        band_position = 0.5

        if feature_frame is not None and not getattr(feature_frame, "empty", True):
            try:
                row = feature_frame.iloc[-1]
                atr_pct = self._safe_numeric_value(row.get("atr_pct"), 0.0)
                trend_strength = self._safe_numeric_value(
                    row.get("trend_strength"), 0.0)
                momentum = self._safe_numeric_value(row.get("momentum"), 0.0)
                band_position = self._safe_numeric_value(
                    row.get("band_position"), 0.5)
            except Exception:
                pass

        if atr_pct >= 0.03:
            volatility_label = "high"
        elif atr_pct >= 0.015:
            volatility_label = "medium"
        else:
            volatility_label = "low"

        return {
            "symbol": str(symbol or "").strip().upper(),
            "timeframe": str(timeframe or self.time_frame or "1h").strip() or "1h",
            "regime": regime,
            "volatility": volatility_label,
            "atr_pct": atr_pct,
            "trend_strength": trend_strength,
            "momentum": momentum,
            "band_position": band_position,
        }

    def _build_portfolio_snapshot(self, symbol: Optional[str] = None) -> dict[str, Any]:
        portfolio = getattr(self.portfolio, "portfolio", None)
        positions = getattr(portfolio, "positions", {}) or {}
        market_prices = dict(
            getattr(self.portfolio, "market_prices", {}) or {})

        rows = []
        gross_exposure = 0.0
        net_exposure = 0.0

        for position_symbol, position in positions.items():
            quantity = self._safe_numeric_value(
                getattr(position, "quantity", 0.0), 0.0)
            if quantity == 0:
                continue

            price = self._safe_numeric_value(
                market_prices.get(position_symbol),
                getattr(position, "avg_price", 0.0),
            )
            exposure = quantity * price
            gross_exposure += abs(exposure)
            net_exposure += exposure

            rows.append(
                {
                    "symbol": str(position_symbol).strip().upper(),
                    "quantity": quantity,
                    "avg_price": self._safe_numeric_value(getattr(position, "avg_price", 0.0), 0.0),
                    "last_price": price,
                    "signed_exposure": exposure,
                    "absolute_exposure": abs(exposure),
                }
            )

        try:
            equity = self._safe_numeric_value(
                self.portfolio.equity(),
                getattr(self.risk_engine, "account_equity", 0.0) or 0.0,
            )
        except Exception:
            equity = self._safe_numeric_value(
                getattr(self.risk_engine, "account_equity", 0.0),
                0.0,
            )

        try:
            cash = self._safe_numeric_value(
                getattr(portfolio, "cash", 0.0), 0.0)
        except Exception:
            cash = 0.0

        snapshot = {
            "symbol": str(symbol or "").strip().upper(),
            "equity": equity,
            "cash": cash,
            "gross_exposure": gross_exposure,
            "net_exposure": net_exposure,
            "position_count": len(rows),
            "positions": rows,
        }

        if self.controller is not None:
            self.controller.agent_portfolio_snapshot = dict(snapshot)

        return snapshot

    # ------------------------------------------------------------------
    # Broker/account guards
    # ------------------------------------------------------------------

    def _margin_closeout_guard_snapshot(self, balances: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resolver = (
            getattr(self.controller, "margin_closeout_snapshot", None)
            if self.controller is not None
            else None
        )

        if not callable(resolver):
            return {}

        try:
            snapshot = resolver(balances)
        except TypeError:
            try:
                snapshot = resolver()
            except Exception:
                return {}
        except Exception:
            return {}

        return dict(snapshot or {}) if isinstance(snapshot, dict) else {}

    def _log_rejection_once(self, stage: Any, symbol: Any, reason: Any, template: str) -> None:
        normalized_stage = str(stage or "").strip().lower() or "unknown"
        normalized_symbol = str(symbol or "").strip().upper()
        self.normalized_symbol = normalized_symbol
        normalized_reason = str(reason or "").strip() or "Trade rejected."

        cooldown_seconds = float(
            getattr(self.controller, "rejection_log_cooldown_seconds", 60.0) or 60.0)
        now = datetime.now(timezone.utc)

        cache_key = (normalized_stage, normalized_symbol, normalized_reason)
        previous = self._rejection_log_cache.get(cache_key)

        if previous is not None and (now - previous).total_seconds() < cooldown_seconds:
            return

        stale_before = now - \
            timedelta(seconds=max(cooldown_seconds * 4.0, 300.0))
        self._rejection_log_cache = {
            key: timestamp
            for key, timestamp in self._rejection_log_cache.items()
            if timestamp >= stale_before
        }

        self._rejection_log_cache[cache_key] = now
        self.logger.warning(template, normalized_reason)

    def _symbols_match(self, left: Any, right: Any) -> bool:
        def normalize(value: Any) -> str:
            text = str(value or "").strip().upper()
            if not text:
                return ""
            if "/" not in text and "_" not in text:
                if (
                    "PERP" in text
                    or re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
                    or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
                ):
                    return text
            return text.replace("-", "/").replace("_", "/")

        left_text = normalize(left)
        right_text = normalize(right)

        return bool(left_text and right_text and left_text == right_text)

    def _position_side(self, position: Any) -> str:
        if hasattr(self.broker, "_position_side"):
            try:
                side = self.broker._position_side(position)
                if side:
                    return str(side).strip().lower()
            except Exception:
                pass

        if isinstance(position, dict):
            side = position.get("side")
            if side is not None:
                return str(side).strip().lower()

            for key in ("amount", "qty", "quantity", "size", "contracts"):
                value = position.get(key)
                try:
                    numeric = float(value)
                except Exception:
                    continue
                if numeric < 0:
                    return "short"
                if numeric > 0:
                    return "long"

        return ""

    def _position_amount(self, position: Any) -> float:
        if hasattr(self.broker, "_position_amount"):
            try:
                return float(self.broker._position_amount(position) or 0.0)
            except Exception:
                pass

        if isinstance(position, dict):
            for key in ("amount", "qty", "quantity", "size", "contracts"):
                value = position.get(key)
                try:
                    return abs(float(value))
                except Exception:
                    continue

        return 0.0

    def _hedging_mode_active(self) -> bool:
        resolver = (
            getattr(self.controller, "hedging_is_active", None)
            if self.controller is not None
            else None
        )

        if callable(resolver):
            try:
                return bool(resolver(self.broker))
            except Exception:
                return False

        return bool(getattr(self.controller, "hedging_enabled", False)) and bool(
            getattr(self.broker, "hedging_supported", False)
        )

    def _signal_requests_position_reduction(self, signal: dict[str, Any]) -> bool:
        signal = signal if isinstance(signal, dict) else {}
        action = str(signal.get("action") or signal.get(
            "intent") or "").strip().lower()

        if action in {"exit", "close", "flatten", "reduce"}:
            return True

        reason = str(signal.get("reason") or "").strip().lower()
        return any(
            token in reason
            for token in ("exit", " close", "flatten", "reduce", "take profit", "stop out")
        )

    def _execution_params_for_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        params = dict((signal or {}).get("params") or {})

        if not self._hedging_mode_active():
            return params

        params.setdefault(
            "positionFill",
            "REDUCE_ONLY" if self._signal_requests_position_reduction(
                signal) else "OPEN_ONLY",
        )
        return params

    def _is_exit_like_signal(self, signal_side: Any, position_side: Any, signal: dict[str, Any]) -> bool:
        normalized_signal = str(signal_side or "").strip().lower()
        normalized_position = str(position_side or "").strip().lower()

        if not normalized_signal or not normalized_position:
            return False

        if normalized_position in {"long", "buy"} and normalized_signal == "sell":
            return True

        if normalized_position in {"short", "sell"} and normalized_signal == "buy":
            return True

        reason = str((signal or {}).get("reason") or "").strip().lower()
        return any(token in reason for token in ("exit", "close", "flatten", "reduce"))

    async def _fetch_symbol_positions(self, symbol: str) -> list[dict[str, Any]]:
        if not hasattr(self.broker, "fetch_positions"):
            return []

        try:
            positions_result = self.broker.fetch_positions(symbols=[symbol])
            positions = await self._maybe_await(positions_result)
        except TypeError:
            positions = await self.broker.fetch_positions()
        except Exception:
            return []

        return [
            position
            for position in (positions or [])
            if isinstance(position, dict)
            and self._symbols_match(position.get("symbol"), symbol)
            and self._position_amount(position) > 0
        ]

    async def _fetch_symbol_open_orders(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        if not hasattr(self.broker, "fetch_open_orders"):
            return []

        snapshot = getattr(self.broker, "fetch_open_orders_snapshot", None)

        try:
            if callable(snapshot):
                orders = snapshot(symbols=[symbol], limit=limit)
            else:
                orders_result = self.broker.fetch_open_orders(symbol=symbol, limit=limit)
                orders = await self._maybe_await(orders_result)
        except TypeError:
            try:
                orders = await self.broker.fetch_open_orders(symbol)
            except Exception:
                return []
        except Exception:
            return []

        active_statuses = {
            "open",
            "pending",
            "submitted",
            "accepted",
            "new",
            "partially_filled",
            "partially-filled",
        }

        filtered = []
        for order in orders or []:
            if not isinstance(order, dict):
                continue
            if not self._symbols_match(order.get("symbol"), symbol):
                continue
            status = str(order.get("status") or "open").strip().lower()
            if status and status not in active_statuses:
                continue
            filtered.append(order)

        return filtered

    async def _cancel_stale_exit_orders(self, symbol: str, side: Any, signal: dict[str, Any]) -> tuple[int, str]:
        if self._hedging_mode_active() and not self._signal_requests_position_reduction(signal):
            return 0, "Hedging mode keeps opposite-side entries open."

        positions = await self._fetch_symbol_positions(symbol)
        if not positions:
            return 0, "No live broker position to clean up."

        has_exit_like_position = any(
            self._is_exit_like_signal(
                side, self._position_side(position), signal)
            for position in positions
        )

        if not has_exit_like_position:
            return 0, "Signal does not oppose a live broker position."

        open_orders = await self._fetch_symbol_open_orders(symbol)
        if not open_orders:
            return 0, "No stale open orders were found for the symbol."

        if hasattr(self.broker, "cancel_all_orders"):
            try:
                await self.broker.cancel_all_orders(symbol=symbol)
                return len(open_orders), f"Canceled {len(open_orders)} stale open order(s) before exit handling."
            except TypeError:
                try:
                    await self.broker.cancel_all_orders(symbol)
                    return len(open_orders), f"Canceled {len(open_orders)} stale open order(s) before exit handling."
                except Exception:
                    pass
            except Exception:
                pass

        if not hasattr(self.broker, "cancel_order"):
            return 0, "Broker does not support cancel_order for exit cleanup."

        canceled = 0
        for order in open_orders:
            order_id = str(
                order.get("id")
                or order.get("order_id")
                or order.get("clientOrderId")
                or ""
            ).strip()

            if not order_id:
                continue

            try:
                await self.broker.cancel_order(order_id, symbol=symbol)
                canceled += 1
            except TypeError:
                try:
                    await self.broker.cancel_order(order_id)
                    canceled += 1
                except Exception:
                    continue
            except Exception:
                continue

        if canceled:
            return canceled, f"Canceled {canceled} stale open order(s) before exit handling."

        return 0, "Unable to cancel stale open orders before exit handling."

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def process_symbol(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        limit: Optional[int] = None,
        publish_debug: bool = True,
        allow_execution: bool = True,
    ) -> Optional[dict[str, Any]]:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise ValueError("Symbol is required")

        target_timeframe = str(
            timeframe or self.time_frame or "1h").strip() or "1h"
        target_limit = self._resolve_runtime_history_limit(limit)

        dataset = await self.data_hub.get_symbol_dataset(
            symbol=normalized_symbol,
            timeframe=target_timeframe,
            limit=target_limit,
        )

        self.dataset = dataset
        candles = dataset.to_candles()
        self.candles = list(candles or [])

        if not self.candles:
            self._record_pipeline_status(
                normalized_symbol,
                "data_hub",
                "empty",
                "No candles returned for symbol",
            )
            return None

        context = {
            "decision_id": uuid4().hex,
            "symbol": normalized_symbol,
            "timeframe": target_timeframe,
            "limit": target_limit,
            "dataset": dataset,
            "candles": self.candles,
            "features": getattr(dataset, "frame", None),
            "publish_debug": bool(publish_debug),
        }

        if not bool(allow_execution):
            runtime_result = self.event_driven_runtime.process_market_data(context)
            context = await self._maybe_await(runtime_result)
            signal = context.get("signal")

            if isinstance(signal, dict):
                signal.setdefault("decision_id", context.get("decision_id"))

            display_signal = context.get("display_signal") or self._build_display_signal(
                context,
                signal,
                context.get("assigned_strategies") or [],
            )

            if signal:
                self._record_pipeline_status(
                    normalized_symbol,
                    "signal_engine",
                    "signal",
                    signal.get("reason"),
                    signal=signal,
                )
                return {
                    "status": "signal",
                    "symbol": normalized_symbol,
                    "decision_id": context.get("decision_id"),
                    "signal": dict(signal),
                    "display_signal": dict(display_signal or signal),
                }

            if context.get("blocked_by_news_bias"):
                self._record_pipeline_status(
                    normalized_symbol,
                    "news_bias",
                    "blocked",
                    context.get("news_bias_reason"),
                    signal=display_signal,
                )
            else:
                self._record_pipeline_status(
                    normalized_symbol,
                    "signal_engine",
                    "hold",
                    display_signal.get("reason")
                    if isinstance(display_signal, dict)
                    else "No entry signal on the latest scan.",
                    signal=display_signal if isinstance(
                        display_signal, dict) else None,
                )

            return {
                "status": "hold",
                "symbol": normalized_symbol,
                "decision_id": context.get("decision_id"),
                "signal": "hold",
                "display_signal": dict(display_signal or {}),
            }

        custom_handler = self._custom_process_signal_handler()

        if custom_handler is not None:
            context = await self._run_signal_agents(context)
            signal = context.get("signal")

            if isinstance(signal, dict):
                signal.setdefault("decision_id", context.get("decision_id"))

            display_signal = context.get("display_signal") or self._build_display_signal(
                context,
                signal,
                context.get("assigned_strategies") or [],
            )

            if signal:
                self._record_pipeline_status(
                    normalized_symbol,
                    "signal_engine",
                    "signal",
                    signal.get("reason"),
                    signal=signal,
                )
            else:
                if context.get("blocked_by_news_bias"):
                    self._record_pipeline_status(
                        normalized_symbol,
                        "news_bias",
                        "blocked",
                        context.get("news_bias_reason"),
                        signal=display_signal,
                    )
                else:
                    self._record_pipeline_status(
                        normalized_symbol,
                        "signal_engine",
                        "hold",
                        display_signal.get("reason")
                        if isinstance(display_signal, dict)
                        else "No entry signal on the latest scan.",
                        signal=display_signal if isinstance(
                            display_signal, dict) else None,
                    )
                return None

            try:
                result = custom_handler(
                    normalized_symbol,
                    signal,
                    dataset=dataset,
                    timeframe=target_timeframe,
                    candles=self.candles,
                )
            except TypeError:
                result = custom_handler(
                    normalized_symbol, signal, dataset=dataset)

            result = await self._maybe_await(result)

        else:
            context = await self.event_driven_runtime.process_market_data(context)
            signal = context.get("signal")

            if isinstance(signal, dict):
                signal.setdefault("decision_id", context.get("decision_id"))

            display_signal = context.get("display_signal") or self._build_display_signal(
                context,
                signal,
                context.get("assigned_strategies") or [],
            )

            latest_stage = str(
                (self._pipeline_status.get(normalized_symbol) or {}).get("stage") or ""
            ).strip()

            if signal:
                if latest_stage in {"", "signal_engine"}:
                    self._record_pipeline_status(
                        normalized_symbol,
                        "signal_engine",
                        "signal",
                        signal.get("reason"),
                        signal=signal,
                    )
            else:
                if context.get("blocked_by_news_bias"):
                    self._record_pipeline_status(
                        normalized_symbol,
                        "news_bias",
                        "blocked",
                        context.get("news_bias_reason"),
                        signal=display_signal,
                    )
                else:
                    self._record_pipeline_status(
                        normalized_symbol,
                        "signal_engine",
                        "hold",
                        display_signal.get("reason")
                        if isinstance(display_signal, dict)
                        else "No entry signal on the latest scan.",
                        signal=display_signal if isinstance(
                            display_signal, dict) else None,
                    )
                return None

            result = context.get("execution_result")

        if result is None:
            review = dict(context.get("trade_review") or {}
                          ) if isinstance(context, dict) else {}

            if review and not review.get("approved"):
                self._record_pipeline_status(
                    normalized_symbol,
                    review.get("stage"),
                    "rejected",
                    review.get("reason"),
                    signal=review.get("signal") if isinstance(
                        review.get("signal"), dict) else signal,
                )
                return None

            latest = self._pipeline_status.get(normalized_symbol, {})
            if latest.get("status") in {"rejected", "blocked"}:
                return None

            self._record_pipeline_status(
                normalized_symbol,
                "execution_manager",
                "skipped",
                "Signal did not result in an executable order.",
                signal=signal,
            )
            return None

        execution_status = (
            str(result.get("status") or "submitted").strip().lower()
            if isinstance(result, dict)
            else "submitted"
        )

        self._record_pipeline_status(
            normalized_symbol,
            "execution_manager",
            execution_status,
            result.get("reason") if isinstance(result, dict) else "",
            signal=signal,
        )

        return result

    # ------------------------------------------------------------------
    # Start / run
    # ------------------------------------------------------------------

    def _resolve_starting_equity(self, balance: Optional[dict[str, Any]] = None) -> float:
        default_equity = self._safe_numeric_value(
            getattr(self.controller, "initial_capital", 10_000),
            10_000,
        )

        if not isinstance(balance, dict):
            return default_equity

        total = balance.get("total")
        if isinstance(total, dict):
            for currency in ("USDT", "USD", "USDC", "BUSD", "BTC", "XLM"):
                numeric = self._safe_numeric_value(total.get(currency), 0.0)
                if numeric > 0:
                    return numeric

            for value in total.values():
                numeric = self._safe_numeric_value(value, 0.0)
                if numeric > 0:
                    return numeric

        return default_equity

    async def start(self) -> None:
        if self.running:
            self.logger.info("Trading system already running")
            return

        if self.broker is None:
            raise RuntimeError("Broker not initialized")

        balance = getattr(self.controller, "balances", {}) or {}
        equity = self._resolve_starting_equity(balance)

        self.risk_engine = RiskEngine(
            account_equity=equity,
            max_portfolio_risk=getattr(
                self.controller, "max_portfolio_risk", 100),
            max_risk_per_trade=getattr(
                self.controller, "max_risk_per_trade", 50),
            max_position_size_pct=getattr(
                self.controller, "max_position_size_pct", 25),
            max_gross_exposure_pct=getattr(
                self.controller, "max_gross_exposure_pct", 30),
        )

        active_strategy = getattr(
            self.controller, "strategy_name", None) or "Trend Following"
        weight_resolver = (
            getattr(self.controller, "active_strategy_weight_map", None)
            if self.controller is not None
            else None
        )
        strategy_weights = weight_resolver() if callable(
            weight_resolver) else {str(active_strategy): 1.0}

        self.portfolio_allocator = PortfolioAllocator(
            account_equity=equity,
            strategy_weights=strategy_weights,
            allocation_model="equal_weight",
            max_strategy_allocation_pct=1.0,
            rebalance_threshold_pct=0.15,
            volatility_target_pct=0.20,
        )

        self.portfolio_risk_engine = PortfolioRiskEngine(
            account_equity=equity,
            max_portfolio_risk=getattr(
                self.controller, "max_portfolio_risk", 0.10),
            max_risk_per_trade=getattr(
                self.controller, "max_risk_per_trade", 0.02),
            max_position_size_pct=getattr(
                self.controller, "max_position_size_pct", 0.10),
            max_gross_exposure_pct=getattr(
                self.controller, "max_gross_exposure_pct", 2.0),
            max_symbol_exposure_pct=min(
                0.30,
                max(
                    0.05,
                    float(getattr(self.controller,
                          "max_position_size_pct", 0.10) or 0.10) * 1.5,
                ),
            ),
        )

        if self.controller is not None:
            self.controller.portfolio_allocator = self.portfolio_allocator
            self.controller.institutional_risk_engine = self.portfolio_risk_engine

        if self.behavior_guard is not None:
            self.behavior_guard.record_equity(equity)

        self.orchestrator = MultiSymbolOrchestrator(
            controller=self.controller,
            broker=self.broker,
            strategy=self.strategy,
            execution_manager=self.execution_manager,
            risk_engine=self.risk_engine,
            signal_processor=self.process_symbol,
            event_bus=self.event_bus,
            portfolio_manager=self.portfolio,
            logger=self.logger,
            default_timeframe=self.time_frame,
            default_limit=self.limit,
        )

        self.running = True
        self.logger.info("Loaded %s symbols", len(self.symbols))

        await self.execution_manager.start()
        await self.event_driven_runtime.start()

        # Important: start orchestrator in background so desktop/runtime remains responsive.
        start_result = self.orchestrator.start(symbols=self.symbols, background=True)
        await self._maybe_await(start_result)
    async def run(self) -> None:
        self.logger.info("Trading loop started")

        while self.running:
            try:
                active_symbols = list(self.symbols)

                if self.controller and hasattr(self.controller, "get_active_autotrade_symbols"):
                    try:
                        resolved = self.controller.get_active_autotrade_symbols()
                    except Exception:
                        resolved = []
                    if resolved:
                        active_symbols = list(resolved)

                for symbol in active_symbols:
                    await self.process_symbol(
                        symbol,
                        timeframe=self._assigned_timeframe_for_symbol(
                            symbol, fallback=self.time_frame),
                        limit=self.limit,
                        publish_debug=True,
                    )

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("Trading loop error")

    # ------------------------------------------------------------------
    # Review / execution
    # ------------------------------------------------------------------

    async def review_signal(
        self,
        symbol: str,
        signal: dict[str, Any],
        dataset: Any = None,
        timeframe: Optional[str] = None,
        regime_snapshot: Optional[dict[str, Any]] = None,
        portfolio_snapshot: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        self.normalized_symbol = normalized_symbol

        normalized_signal = dict(signal or {})
        review_timeframe = str(
            timeframe or self.time_frame or "1h").strip() or "1h"

        decision_id = str(normalized_signal.get(
            "decision_id") or "").strip() or None
        side = normalized_signal.get("side")
        price = normalized_signal.get("price")
        amount = normalized_signal.get("amount")

        strategy_name = normalized_signal.get("strategy_name") or getattr(
            self.controller,
            "strategy_name",
            "Bot",
        )
        reduction_request = self._signal_requests_position_reduction(
            normalized_signal)

        review = {
            "approved": False,
            "symbol": normalized_symbol,
            "signal": normalized_signal,
            "timeframe": review_timeframe,
            "dataset": dataset,
            "strategy_name": strategy_name,
            "decision_id": decision_id,
            "stage": "review",
            "reason": "",
            "type": str(normalized_signal.get("type") or "market").strip().lower() or "market",
            "stop_price": normalized_signal.get("stop_price"),
            "stop_loss": normalized_signal.get("stop_loss"),
            "take_profit": normalized_signal.get("take_profit"),
            "signal_source_agent": normalized_signal.get("signal_source_agent"),
            "consensus_status": normalized_signal.get("consensus_status"),
            "adaptive_weight": normalized_signal.get("adaptive_weight"),
            "adaptive_score": normalized_signal.get("adaptive_score"),
            "portfolio_snapshot": dict(
                portfolio_snapshot or self._build_portfolio_snapshot(
                    normalized_symbol)
            ),
            "regime_snapshot": dict(
                regime_snapshot
                or self._build_regime_snapshot(
                    normalized_symbol,
                    signal=normalized_signal,
                    candles=(dataset.to_candles() if dataset and hasattr(
                        dataset, "to_candles") else []),
                    dataset=dataset,
                    timeframe=review_timeframe,
                )
            ),
        }

        # Price validation
        if (price is None or float(price or 0) <= 0) and dataset is not None:
            try:
                price = float(dataset.frame.iloc[-1]["close"])
            except Exception:
                price = None

        if price is None or float(price or 0) <= 0:
            review["stage"] = "price_validation"
            review["reason"] = "Invalid price"
            return review

        # Basic risk engine
        if self.risk_engine:
            allowed, adjusted_amount, reason = self.risk_engine.adjust_trade(
                float(price),
                float(amount or 0.0),
            )
            if not allowed:
                review["stage"] = "risk_engine"
                review["reason"] = reason
                return review

            amount = adjusted_amount
            review["stage"] = "risk_engine"
            review["reason"] = reason

        # Global risk/session block
        session_manager = self.session_manager
        if session_manager is not None and hasattr(session_manager, "should_block_trade"):
            blocked, reason = session_manager.should_block_trade()
        else:
            blocked, reason = False, ""

        if blocked:
            review["stage"] = "global_risk"
            review["reason"] = reason
            return review

        margin_closeout_guard = self._margin_closeout_guard_snapshot(
            getattr(self.controller, "balances", {}
                    ) if self.controller is not None else {}
        )

        if margin_closeout_guard:
            review["margin_closeout_guard"] = margin_closeout_guard
            if margin_closeout_guard.get("blocked") and not reduction_request:
                review["stage"] = "margin_closeout_guard"
                review["reason"] = str(
                    margin_closeout_guard.get("reason")
                    or "Margin closeout guard blocked the trade."
                ).strip()
                return review

        # Portfolio allocation
        if self.portfolio_allocator is not None and not reduction_request:
            portfolio_state = review.get("portfolio_snapshot") or {}
            equity_value = self._safe_numeric_value(
                portfolio_state.get("equity"),
                getattr(self.risk_engine, "account_equity", 0.0) or 0.0,
            )

            sync_equity = getattr(
                self.portfolio_allocator, "sync_equity", None)
            if callable(sync_equity):
                try:
                    sync_equity(equity_value)
                except Exception:
                    self.logger.debug(
                        "Unable to sync allocator equity for %s", normalized_symbol, exc_info=True)

            register_strategy_symbol = getattr(
                self.portfolio_allocator, "register_strategy_symbol", None)
            if callable(register_strategy_symbol):
                try:
                    register_strategy_symbol(normalized_symbol, strategy_name)
                except Exception:
                    self.logger.debug(
                        "Unable to register allocator symbol mapping for %s",
                        normalized_symbol,
                        exc_info=True,
                    )

            active_strategies = [
                str(item.get("strategy_name") or "").strip()
                for item in list(self._assigned_strategies_for_symbol(normalized_symbol) or [])
                if str(item.get("strategy_name") or "").strip()
            ] or [str(strategy_name).strip()]


            allocation_result = self.portfolio_allocator.allocate_trade(
                symbol=normalized_symbol,
                strategy_name=strategy_name,
                side=side,
                amount=amount,
                price=price,
                portfolio=getattr(self.portfolio, "portfolio", None),
                market_prices=getattr(self.portfolio, "market_prices", {}),
                dataset=dataset,
                confidence=normalized_signal.get("confidence"),
                active_strategies=active_strategies,
            )
            allocation = await self._maybe_await(allocation_result)

            allocation_approved = bool(
                allocation.get("approved")
                if isinstance(allocation, dict)
                else getattr(allocation, "approved", False)
            )
            allocation_reason = str(
                allocation.get("reason")
                if isinstance(allocation, dict)
                else getattr(allocation, "reason", "")
            ).strip()
            allocation_amount = self._safe_numeric_value(
                allocation.get("adjusted_amount")
                if isinstance(allocation, dict)
                else getattr(allocation, "adjusted_amount", amount),
                amount or 0.0,
            )
            allocation_metrics = (
                allocation.get("metrics")
                if isinstance(allocation, dict)
                else getattr(allocation, "metrics", None)
            )

            review["portfolio_allocation"] = (
                dict(allocation_metrics or {})
                if isinstance(allocation_metrics, dict)
                else {}
            )

            if not allocation_approved:
                rejection_reason = allocation_reason or "Portfolio allocator rejected the trade."
                review["stage"] = "portfolio_allocator"
                review["reason"] = rejection_reason
                self._log_rejection_once(
                    "portfolio_allocator",
                    normalized_symbol,
                    rejection_reason,
                    "Trade rejected by portfolio allocator: %s",
                )
                return review

            amount = allocation_amount
            review["stage"] = "portfolio_allocator"
            review["reason"] = allocation_reason

        # Portfolio risk engine
        if self.portfolio_risk_engine:
            approval_result = self.portfolio_risk_engine.approve_trade(
                symbol=normalized_symbol,
                side=side,
                amount=amount,
                price=price,
                portfolio=getattr(self.portfolio, "portfolio", None),
                market_prices=getattr(self.portfolio, "market_prices", {}),
                data_hub=self.data_hub,
                dataset=dataset,
                timeframe=review_timeframe,
                strategy_name=strategy_name,
            )
            approval = await self._maybe_await(approval_result)

            if not approval.approved:
                review["stage"] = "portfolio_risk_engine"
                review["reason"] = approval.reason
                return review

            amount = approval.adjusted_amount

        review["amount"] = amount
        review["price"] = price
        review["side"] = side
        review["execution_strategy"] = self._resolve_execution_strategy(
            normalized_symbol,
            side,
            amount,
            price,
            normalized_signal,
        )
        review["execution_params"] = self._execution_params_for_signal(
            normalized_signal)

        review = await self._apply_reasoning_review(review)
        return review

    def _resolve_execution_strategy(
        self,
        symbol: str,
        side: Any,
        amount: Any,
        price: Any,
        signal: dict[str, Any],
    ) -> str:
        requested = str(signal.get("execution_strategy") or "").strip().lower()
        if requested:
            return requested

        order_type = str(signal.get("type") or "market").strip().lower()


        try:
            portfolio_equity = self.portfolio.equity()
        except Exception:
            portfolio_equity = None

        equity = float(portfolio_equity or getattr(
            self.risk_engine, "account_equity", 0.0) or 0.0)
        notional = abs(float(amount or 0.0) * float(price or 0.0))

        if equity <= 0 or notional <= 0:
            return order_type

        notional_pct = notional / equity

        if order_type in {"limit", "stop_limit"} and notional_pct >= 0.08:
            return "iceberg"

        if order_type == "market" and notional_pct >= 0.05:
            return "twap"

        return order_type

    def _review_quantity_mode(self, review: dict[str, Any], signal: dict[str, Any]) -> Optional[str]:
        for payload in (review, signal):
            if not isinstance(payload, dict):
                continue
            value = str(payload.get("quantity_mode") or "").strip().lower()
            if value:
                return value

        resolver = (
            getattr(self.controller, "trade_quantity_context", None)
            if self.controller is not None
            else None
        )

        if not callable(resolver):
            return None

        symbol = (review or {}).get("symbol") or (
            signal or {}).get("symbol") or ""

        try:
            context = resolver(symbol)
        except Exception:
            self.logger.debug(
                "Unable to resolve quantity mode for %s", symbol, exc_info=True)
            return None

        if isinstance(context, dict) and context.get("supports_lots"):
            value = str(context.get("default_mode") or "lots").strip().lower()
            return value or "lots"

        return None

    async def _preflight_execution_review(self, review: dict[str, Any], signal: dict[str, Any]) -> Any:
        preflight = (
            getattr(self.controller, "_preflight_trade_submission", None)
            if self.controller is not None
            else None
        )

        if not callable(preflight):
            return None

        result = preflight(
            symbol=review.get("symbol"),
            side=review.get("side"),
            amount=review.get("amount"),
            quantity_mode=self._review_quantity_mode(review, signal),
            order_type=review.get("type", "market"),
            price=review.get("price"),
            stop_price=review.get("stop_price"),
            stop_loss=review.get("stop_loss"),
            take_profit=review.get("take_profit"),
        )
        return await self._maybe_await(result)

    async def _reject_execution_review(
        self,
        review: dict[str, Any],
        signal: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        normalized_reason = str(
            reason or "Automated order preflight rejected the trade."
        ).strip()

        submitted_order = {
            "symbol": review.get("symbol"),
            "side": review.get("side"),
            "source": "bot",
            "amount": review.get("amount"),
            "type": review.get("type", "market"),
            "price": review.get("price"),
            "stop_price": review.get("stop_price"),
            "stop_loss": review.get("stop_loss"),
            "take_profit": review.get("take_profit"),
            "strategy_name": review.get("strategy_name"),
            "timeframe": review.get("timeframe"),
            "signal_source_agent": review.get("signal_source_agent"),
            "consensus_status": review.get("consensus_status"),
            "adaptive_weight": review.get("adaptive_weight"),
            "adaptive_score": review.get("adaptive_score"),
            "reason": signal.get("reason") or normalized_reason,
            "confidence": signal.get("confidence"),
            "expected_price": signal.get("price"),
            "pnl": signal.get("pnl"),
            "execution_strategy": review.get("execution_strategy"),
        }
        rejected_execution = {
            "symbol": review.get("symbol"),
            "side": review.get("side"),
            "source": "bot",
            "amount": review.get("amount"),
            "type": review.get("type", "market"),
            "price": review.get("price"),
            "status": "rejected",
            "reason": normalized_reason,
            "raw": {"error": normalized_reason},
        }

        self._record_pipeline_status(
            review.get("symbol"),
            "execution_preflight",
            "rejected",
            normalized_reason,
            signal=signal,
        )

        update_result = self.execution_manager._handle_order_update(
            rejected_execution,
            submitted_order,
            allow_tracking=False,
        )
        await self._maybe_await(update_result)

        return rejected_execution

    async def execute_review(self, review: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not isinstance(review, dict) or not review.get("approved"):
            return None

        signal = dict(review.get("signal") or {})

        order_payload = {
            "symbol": review.get("symbol"),
            "side": review.get("side"),
            "amount": review.get("amount"),
            "price": review.get("price"),
            "source": "bot",
            "exchange": self._active_exchange_code(),
            "strategy_name": review.get("strategy_name"),
            "timeframe": review.get("timeframe"),
            "decision_id": review.get("decision_id") or signal.get("decision_id"),
            "signal_timestamp": signal.get("timestamp"),
            "feature_snapshot": signal.get("feature_snapshot"),
            "feature_version": signal.get("feature_version"),
            "regime_snapshot": review.get("regime_snapshot"),
            "market_regime": (review.get("regime_snapshot") or {}).get("regime"),
            "volatility_regime": (review.get("regime_snapshot") or {}).get("volatility"),
            "signal_source_agent": review.get("signal_source_agent"),
            "consensus_status": review.get("consensus_status"),
            "adaptive_weight": review.get("adaptive_weight"),
            "adaptive_score": review.get("adaptive_score"),
            "reason": signal.get("reason"),
            "confidence": signal.get("confidence"),
            "expected_price": signal.get("price"),
            "expected_return": signal.get("expected_return"),
            "risk_estimate": signal.get("risk_estimate"),
            "alpha_score": signal.get("alpha_score"),
            "alpha_models": list(signal.get("alpha_models") or []),
            "alpha_horizon": signal.get("horizon"),
            "pnl": signal.get("pnl"),
            "execution_strategy": review.get("execution_strategy"),
            "reasoning_decision": review.get("reasoning_decision"),
            "reasoning_confidence": review.get("reasoning_confidence"),
            "reasoning_provider": review.get("reasoning_provider"),
            "reasoning_mode": review.get("reasoning_mode"),
            "type": review.get("type", "market"),
            "stop_price": review.get("stop_price"),
            "stop_loss": review.get("stop_loss"),
            "take_profit": review.get("take_profit"),
            "params": dict(review.get("execution_params") or {}),
        }

        reasoning = dict(review.get("reasoning") or {})
        if reasoning:
            order_payload["reasoning_risk"] = reasoning.get("risk")
            order_payload["reasoning_summary"] = reasoning.get("reasoning")
            order_payload["reasoning_warnings"] = list(
                reasoning.get("warnings") or [])

        try:
            canceled_orders, cleanup_reason = await self._cancel_stale_exit_orders(
                review.get("symbol"),
                review.get("side"),
                signal,
            )
            review["exit_cleanup"] = {
                "canceled": int(canceled_orders or 0),
                "reason": cleanup_reason,
            }
        except Exception:
            self.logger.debug("Exit cleanup failed for %s",
                              review.get("symbol"), exc_info=True)

        try:
            preflight = await self._preflight_execution_review(review, signal)
        except RuntimeError as exc:
            return await self._reject_execution_review(review, signal, str(exc))
        except Exception as exc:
            self.logger.exception(
                "Automated order preflight failed for %s",
                review.get("symbol"),
            )
            return await self._reject_execution_review(
                review,
                signal,
                f"Automated order preflight failed before broker submission: {exc}",
            )

        if isinstance(preflight, dict):
            order_payload["amount"] = float(preflight.get(
                "amount_units", order_payload["amount"]))
            for key in (
                "requested_amount",
                "requested_mode",
                "requested_amount_units",
                "deterministic_amount_units",
                "amount_units",
                "applied_requested_mode_amount",
                "size_adjusted",
                "ai_adjusted",
                "sizing_summary",
                "sizing_notes",
                "ai_sizing_reason",
            ):
                value = preflight.get(key)
                if value not in (None, "", []):
                    payload_key = "requested_quantity_mode" if key == "requested_mode" else key
                    order_payload[payload_key] = value

        order_result = self.execution_manager.execute(**order_payload)
        order = await self._maybe_await(order_result)
        return order

    async def process_signal(
        self,
        symbol: str,
        signal: dict[str, Any],
        dataset: Any = None,
        timeframe: Optional[str] = None,
        regime_snapshot: Optional[dict[str, Any]] = None,
        portfolio_snapshot: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        review = await self.review_signal(
            symbol=symbol,
            signal=signal,
            dataset=dataset,
            timeframe=timeframe,
            regime_snapshot=regime_snapshot,
            portfolio_snapshot=portfolio_snapshot,
        )

        normalized_symbol = str(symbol or "").strip().upper()

        self._record_pipeline_status(
            normalized_symbol,
            review.get("stage"),
            "approved" if review.get("approved") else "rejected",
            review.get("reason"),
            signal=review.get("signal"),
        )
        if not review.get("approved"):
            return None

        return await self.execute_review(review)

    # ------------------------------------------------------------------
    # Stop / snapshot
    # ------------------------------------------------------------------

    async def stop(self, wait_for_background_workers: bool = False) -> None:
        self.logger.info("Stopping trading system")
        self.running = False

        orchestrator = getattr(self, "orchestrator", None)
        if orchestrator is not None:
            shutdown = getattr(orchestrator, "shutdown", None)
            if callable(shutdown):
                try:
                    result = shutdown()
                    if hasattr(result, "__await__"):
                       await self._maybe_await(result)
                except Exception:
                    self.logger.exception("Orchestrator shutdown failed")

        event_runtime = getattr(self, "event_driven_runtime", None)
        if event_runtime is not None:
            try:
                await event_runtime.stop()
            except Exception:
                self.logger.exception("Event-driven runtime stop failed")

        execution_manager = getattr(self, "execution_manager", None)
        if execution_manager is not None:
            try:
                await execution_manager.stop()
            except Exception:
                self.logger.exception("Execution manager stop failed")

        self._shutdown_signal_selection_executor(
            wait=wait_for_background_workers)

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "symbols": list(self.symbols),
            "time_frame": self.time_frame,
            "limit": self.limit,
            "exchange": self._active_exchange_code(),
            "pipeline_status": self.pipeline_status_snapshot(),
            "agent_memory": self.agent_memory_snapshot(limit=25),
            "orchestrator": self.orchestrator.snapshot() if self.orchestrator and hasattr(self.orchestrator, "snapshot") else {},
        }

    def _get_signal_selection_executor(self) -> ThreadPoolExecutor:
        executor = getattr(self, "_signal_selection_executor", None)
        if executor is None:
            executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="signal-selection",
            )
            self._signal_selection_executor = executor
        return executor

    def _shutdown_signal_selection_executor(self, wait: bool = False) -> None:
        executor = getattr(self, "_signal_selection_executor", None)
        if executor is None:
            return

        self._signal_selection_executor = None

        try:
            executor.shutdown(wait=bool(wait), cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=bool(wait))
