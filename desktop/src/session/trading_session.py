from __future__ import annotations

import asyncio
import copy
import contextlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
import logging
import re
from typing import Any

from core.account_identity import resolve_account_label
from events.event_bus.event_types import EventType
from market_data.orderbook_buffer import OrderBookBuffer
from market_data.ticker_buffer import TickerBuffer
from  core.trading_core import TradingCore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalized_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _looks_like_native_contract_symbol(symbol: Any) -> bool:
    text = str(symbol or "").strip().upper()
    if not text or "/" in text or "_" in text:
        return False
    if "PERP" in text:
        return True
    return bool(
        re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
        or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
    )


def _normalize_symbol_text(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if _looks_like_native_contract_symbol(text):
        return text
    return text.replace("_", "/").replace("-", "/")


def _normalize_symbol_sequence(symbols: Any) -> list[str]:
    if symbols is None:
        return []
    if isinstance(symbols, str):
        raw_values = [item for item in symbols.split(",")]
    elif isinstance(symbols, Mapping):
        raw_values = list(symbols.keys())
    else:
        raw_values = list(symbols or [])

    normalized = []
    for symbol in raw_values:
        value = _normalize_symbol_text(symbol)
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _normalize_fraction(value: Any, default: float) -> float:
    normalized = _safe_float(value, default)
    if normalized < 0:
        return 0.0
    if normalized > 1.0:
        normalized = normalized / 100.0
    return normalized


def _normalize_exposure_limit(value: Any, default: float) -> float:
    normalized = _safe_float(value, default)
    if normalized < 0:
        return 0.0
    if normalized > 5.0:
        normalized = normalized / 100.0
    return normalized


@dataclass(frozen=True)
class SessionRiskLimits:
    max_drawdown_pct: float
    max_position_size_pct: float
    max_gross_exposure_pct: float
    max_leverage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_position_size_pct": self.max_position_size_pct,
            "max_gross_exposure_pct": self.max_gross_exposure_pct,
            "max_leverage": self.max_leverage,
        }


@dataclass
class SessionRiskState:
    blocked: bool = False
    reason: str = ""
    equity: float = 0.0
    peak_equity: float = 0.0
    drawdown_pct: float = 0.0
    gross_exposure: float = 0.0
    gross_exposure_pct: float = 0.0
    largest_position_notional: float = 0.0
    largest_position_pct: float = 0.0
    max_observed_leverage: float = 0.0
    position_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason": self.reason,
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "drawdown_pct": self.drawdown_pct,
            "gross_exposure": self.gross_exposure,
            "gross_exposure_pct": self.gross_exposure_pct,
            "largest_position_notional": self.largest_position_notional,
            "largest_position_pct": self.largest_position_pct,
            "max_observed_leverage": self.max_observed_leverage,
            "position_count": self.position_count,
        }


@dataclass
class SessionSnapshot:
    session_id: str
    label: str
    exchange: str
    broker_type: str
    mode: str
    strategy: str
    status: str
    connected: bool
    autotrading: bool
    account_label: str | None = None
    equity: float = 0.0
    balance_summary: str = ""
    positions_count: int = 0
    open_orders_count: int = 0
    trade_count: int = 0
    symbols_count: int = 0
    last_error: str = ""
    last_update_at: str = ""
    started_at: str = ""
    risk_blocked: bool = False
    drawdown_pct: float = 0.0
    gross_exposure: float = 0.0
    gross_exposure_pct: float = 0.0
    max_observed_leverage: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "label": self.label,
            "exchange": self.exchange,
            "broker_type": self.broker_type,
            "mode": self.mode,
            "strategy": self.strategy,
            "status": self.status,
            "connected": self.connected,
            "autotrading": self.autotrading,
            "account_label": self.account_label,
            "equity": self.equity,
            "balance_summary": self.balance_summary,
            "positions_count": self.positions_count,
            "open_orders_count": self.open_orders_count,
            "trade_count": self.trade_count,
            "symbols_count": self.symbols_count,
            "last_error": self.last_error,
            "last_update_at": self.last_update_at,
            "started_at": self.started_at,
            "risk_blocked": self.risk_blocked,
            "drawdown_pct": self.drawdown_pct,
            "gross_exposure": self.gross_exposure,
            "gross_exposure_pct": self.gross_exposure_pct,
            "max_observed_leverage": self.max_observed_leverage,
            "metadata": dict(self.metadata or {}),
        }


class SessionControllerProxy:
    """Session-scoped facade used by the legacy trading runtime."""

    _COPIED_ATTRS = (
        "logger",
        "order_type",
        "time_frame",
        "limit",
        "strategy_name",
        "strategy_params",
        "multi_strategy_enabled",
        "symbol_strategy_assignments",
        "symbol_strategy_rankings",
        "symbol_strategy_locks",
        "max_signal_agents",
        "minimum_signal_votes",
        "reasoning_enabled",
        "reasoning_mode",
        "reasoning_min_confidence",
        "reasoning_timeout_seconds",
        "reasoning_provider",
        "openai_api_key",
        "openai_model",
        "max_portfolio_risk",
        "max_risk_per_trade",
        "max_position_size_pct",
        "max_gross_exposure_pct",
        "hedging_enabled",
        "margin_closeout_guard_enabled",
        "max_margin_closeout_pct",
        "runtime_history_limit",
        "market_trade_preference",
        "forex_candle_price_component",
        "risk_profile_name",
        "market_data_repository",
        "trade_repository",
        "trade_audit_repository",
        "equity_repository",
        "agent_decision_repository",
    )

    def __init__(self, parent_controller: Any, session: "TradingSession") -> None:
        self._parent = parent_controller
        self._session = session
        for attr in self._COPIED_ATTRS:
            if hasattr(parent_controller, attr):
                setattr(self, attr, getattr(parent_controller, attr))
        self.logger = session.logger
        self.config = session.config
        self.exchange = session.exchange
        self.broker_type = session.broker_type
        self.broker = session.broker
        self.symbols = list(session.symbols)
        self.balances = dict(session.balances)
        self.balance = dict(session.balances)
        self.session_id = session.session_id
        self.session_label = session.label
        self.autotrade_scope = str(getattr(session, "autotrade_scope", getattr(parent_controller, "autotrade_scope", "all")) or "all").strip().lower() or "all"
        self.autotrade_watchlist = set(getattr(session, "autotrade_watchlist", set()) or set())
        self.symbol_strategy_assignments = copy.deepcopy(getattr(session, "symbol_strategy_assignments", {}) or {})
        self.symbol_strategy_rankings = copy.deepcopy(getattr(session, "symbol_strategy_rankings", {}) or {})
        self.symbol_strategy_locks = set(getattr(session, "symbol_strategy_locks", set()) or set())
        self.candle_buffers = getattr(session, "candle_buffers", {})
        self.orderbook_buffer = getattr(session, "orderbook_buffer", None)
        self.ticker_buffer = getattr(session, "ticker_buffer", None)
        self._recent_trades_cache = getattr(session, "recent_trades_cache", {})
        self._recent_trades_last_request_at = getattr(session, "recent_trades_last_request_at", {})
        self._live_agent_runtime_feed = getattr(session, "live_agent_runtime_feed", [])
        self._live_agent_decision_events = getattr(session, "live_agent_decision_events", {})
        self.trading_system = None
        self.portfolio = None
        self.behavior_guard = None
        self.event_bus = None
        self.agent_event_runtime = None
        self.agent_memory = None
        self.signal_agents = []
        self.signal_consensus_agent = None
        self.signal_aggregation_agent = None
        self.reasoning_engine = None
        self.paper_trade_learning_repository = None
        self.paper_trade_dataset_builder = None
        self.paper_trade_learning_service = None
        self.quant_allocation_snapshot = {}
        self.quant_risk_snapshot = {}
        self.agent_portfolio_snapshot = {}
        self.historical_data = getattr(parent_controller, "historical_data", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._parent, name)

    def _active_exchange_code(self, exchange: str | None = None) -> str | None:
        normalized = str(exchange or self.exchange or "").strip().lower()
        return normalized or None

    @staticmethod
    def _normalize_symbol_key(symbol: Any) -> str:
        return _normalize_symbol_text(symbol)

    def symbol_strategy_assignment_locked(self, symbol: str) -> bool:
        normalized_symbol = self._normalize_symbol_key(symbol)
        return normalized_symbol in set(getattr(self, "symbol_strategy_locks", set()) or set())

    def ranked_strategies_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        normalized_symbol = self._normalize_symbol_key(symbol)
        return list((getattr(self, "symbol_strategy_rankings", {}) or {}).get(normalized_symbol, []) or [])

    def raw_assigned_strategies_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        normalized_symbol = self._normalize_symbol_key(symbol)
        return list((getattr(self, "symbol_strategy_assignments", {}) or {}).get(normalized_symbol, []) or [])

    def assigned_strategies_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        normalized_symbol = self._normalize_symbol_key(symbol)
        assigned = list((getattr(self, "symbol_strategy_assignments", {}) or {}).get(normalized_symbol, []) or [])
        if assigned:
            if bool(getattr(self, "multi_strategy_enabled", True)) or len(assigned) <= 1:
                return assigned
            primary = dict(assigned[0])
            primary["weight"] = 1.0
            primary["rank"] = 1
            return [primary]
        fallback_name = str(getattr(self, "strategy_name", "Trend Following") or "Trend Following").strip() or "Trend Following"
        timeframe_value = str(getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        return [
            {
                "strategy_name": fallback_name,
                "score": 1.0,
                "weight": 1.0,
                "symbol": normalized_symbol,
                "timeframe": timeframe_value,
                "rank": 1,
            }
        ]

    def strategy_portfolio_profile_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.assigned_strategies_for_symbol(symbol)]

    def _best_ranked_autotrade_symbols(
            self,
            available_symbols=None,
            catalog_symbols=None,
            broker_type=None,
            exchange=None,
            limit=None,
    ) -> list[str]:
        available = [
            self._normalize_symbol_key(symbol)
            for symbol in list(available_symbols or self._session.symbols or [])
            if self._normalize_symbol_key(symbol)
        ]
        catalog = [
            self._normalize_symbol_key(symbol)
            for symbol in list(catalog_symbols or getattr(self._session, "symbol_catalog", []) or available)
            if self._normalize_symbol_key(symbol)
        ]
        candidates = list(catalog or available)
        if not candidates:
            return []

        policy_resolver = getattr(self._parent, "_symbol_universe_policy", None)
        if callable(policy_resolver):
            policy = policy_resolver(broker_type=broker_type, exchange=exchange)
        else:
            policy = {}
        resolved_limit = int(limit or policy.get("auto_assignment_limit", 0) or 0)
        if resolved_limit <= 0:
            resolved_limit = len(candidates)

        scored = []
        for index, symbol in enumerate(candidates):
            ranked_rows = self.ranked_strategies_for_symbol(symbol)
            top_row = ranked_rows[0] if ranked_rows else {}
            scored.append(
                {
                    "symbol": symbol,
                    "index": index,
                    "ranked": bool(ranked_rows),
                    "score": float(top_row.get("score", 0.0) or 0.0),
                    "sharpe_ratio": float(top_row.get("sharpe_ratio", 0.0) or 0.0),
                    "total_profit": float(top_row.get("total_profit", 0.0) or 0.0),
                    "win_rate": float(top_row.get("win_rate", 0.0) or 0.0),
                }
            )

        ranked_symbols = []
        if any(item["ranked"] for item in scored):
            ranked_symbols = [
                item["symbol"]
                for item in sorted(
                    [item for item in scored if item["ranked"]],
                    key=lambda item: (
                        -item["score"],
                        -item["sharpe_ratio"],
                        -item["total_profit"],
                        -item["win_rate"],
                        item["index"],
                    ),
                )
            ]

        prioritize = getattr(self._parent, "_prioritize_symbols_for_trading", None)
        fallback_source = list(available or candidates)
        if callable(prioritize):
            try:
                fallback_source = list(
                    prioritize(
                        available or candidates,
                        top_n=len(available or candidates),
                        )
                    or fallback_source
                )
            except Exception:
                fallback_source = list(available or candidates)

        resolved = []
        for source in (ranked_symbols, fallback_source, candidates):
            for symbol in source:
                if symbol and symbol not in resolved:
                    resolved.append(symbol)
                if len(resolved) >= resolved_limit:
                    return resolved
        return resolved[:resolved_limit]

    def current_account_label(self) -> str:
        broker = getattr(self, "broker", None)
        broker_config = getattr(getattr(self, "config", None), "broker", None)
        return resolve_account_label(broker, broker_config)

    def is_live_mode(self) -> bool:
        broker_config = getattr(getattr(self, "config", None), "broker", None)
        mode = str(getattr(broker_config, "mode", "paper") or "paper").strip().lower()
        exchange = str(getattr(broker_config, "exchange", "") or "").strip().lower()
        return mode == "live" and exchange != "paper"

    def get_active_autotrade_symbols(self) -> list[str]:
        available = [
            self._normalize_symbol_key(symbol)
            for symbol in list(self._session.symbols or [])
            if self._normalize_symbol_key(symbol)
        ]
        catalog = [
            self._normalize_symbol_key(symbol)
            for symbol in list(getattr(self._session, "symbol_catalog", []) or available)
            if self._normalize_symbol_key(symbol)
        ]
        if not available and not catalog:
            return []

        resolver = getattr(self._parent, "get_active_autotrade_symbols", None)
        if callable(resolver):
            try:
                resolved = resolver(
                    available_symbols=available,
                    catalog_symbols=catalog,
                    broker_type=self.broker_type,
                    exchange=self.exchange,
                )
                if resolved is not None:
                    return [
                        self._normalize_symbol_key(symbol)
                        for symbol in list(resolved or [])
                        if self._normalize_symbol_key(symbol)
                    ]
            except TypeError:
                pass

        scope_normalizer = getattr(self._parent, "_normalize_autotrade_scope", None)
        if callable(scope_normalizer):
            scope = str(scope_normalizer(getattr(self, "autotrade_scope", "all")) or "all").lower()
        else:
            scope = str(getattr(self, "autotrade_scope", "all") or "all").strip().lower()
        if scope == "selected":
            selected_resolver = getattr(self._parent, "_current_autotrade_selected_symbol", None)
            selected = str(selected_resolver() if callable(selected_resolver) else "").upper().strip()
            candidate_pool = set(catalog or available)
            return [selected] if selected and selected in candidate_pool else []
        if scope == "watchlist":
            watchlist = set(getattr(self, "autotrade_watchlist", set()) or set())
            return [symbol for symbol in (catalog or available) if symbol in watchlist]
        if scope == "ranked":
            return self._best_ranked_autotrade_symbols(
                available_symbols=available,
                catalog_symbols=catalog,
                broker_type=self.broker_type,
                exchange=self.exchange,
            )
        return available

    def is_symbol_enabled_for_autotrade(self, symbol: str) -> bool:
        normalized = self._normalize_symbol_key(symbol)
        if not normalized:
            return False
        available = {
            self._normalize_symbol_key(item)
            for item in list(self._session.symbols or [])
            if self._normalize_symbol_key(item)
        }
        catalog = {
            self._normalize_symbol_key(item)
            for item in list(getattr(self._session, "symbol_catalog", []) or available)
            if self._normalize_symbol_key(item)
        }

        resolver = getattr(self._parent, "is_symbol_enabled_for_autotrade", None)
        if callable(resolver):
            try:
                return bool(
                    resolver(
                        normalized,
                        available_symbols=list(available),
                        catalog_symbols=list(catalog),
                        broker_type=self.broker_type,
                        exchange=self.exchange,
                    )
                )
            except TypeError:
                pass

        scope_normalizer = getattr(self._parent, "_normalize_autotrade_scope", None)
        if callable(scope_normalizer):
            scope = str(scope_normalizer(getattr(self, "autotrade_scope", "all")) or "all").lower()
        else:
            scope = str(getattr(self, "autotrade_scope", "all") or "all").strip().lower()
        if scope == "selected":
            selected_resolver = getattr(self._parent, "_current_autotrade_selected_symbol", None)
            selected = str(selected_resolver() if callable(selected_resolver) else "").upper().strip()
            candidate_pool = catalog or available
            return bool(selected) and normalized == selected and normalized in candidate_pool
        if scope == "watchlist":
            return normalized in set(getattr(self, "autotrade_watchlist", set()) or set()) and normalized in (catalog or available)
        if scope == "ranked":
            ranked_symbols = self._best_ranked_autotrade_symbols(
                available_symbols=list(available),
                catalog_symbols=list(catalog),
                broker_type=self.broker_type,
                exchange=self.exchange,
            )
            return normalized in set(ranked_symbols)
        return normalized in available

    def publish_ai_signal(self, symbol: str, signal: dict[str, Any], candles: list[Any] | None = None) -> None:
        payload = dict(signal or {})
        payload["session_id"] = self.session_id
        payload["session_label"] = self.session_label
        self._session.last_ai_signal = dict(payload)
        if hasattr(self._parent, "publish_ai_signal"):
            self._parent.publish_ai_signal(symbol, payload, candles=candles)

    def publish_strategy_debug(
            self,
            symbol: str,
            signal: dict[str, Any],
            candles: list[Any] | None = None,
            features: Any = None,
    ) -> None:
        payload = dict(signal or {})
        payload["session_id"] = self.session_id
        payload["session_label"] = self.session_label
        self._session.last_strategy_debug = dict(payload)
        if hasattr(self._parent, "publish_strategy_debug"):
            self._parent.publish_strategy_debug(symbol, payload, candles=candles, features=features)

    async def apply_news_bias_to_signal(self, symbol: str, signal: dict[str, Any]) -> dict[str, Any] | None:
        return signal

    def handle_trade_execution(self, trade: dict[str, Any]) -> None:
        payload = dict(trade or {})
        payload.setdefault("exchange", self.exchange)
        payload["session_id"] = self.session_id
        payload["session_label"] = self.session_label
        self._session.trade_history.append(payload)
        self._session.trade_history = self._session.trade_history[-500:]
        if hasattr(self._parent, "handle_trade_execution"):
            self._parent.handle_trade_execution(payload)

    def trade_quantity_context(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = _normalize_symbol_text(symbol)
        broker = getattr(self, "broker", None)
        exchange_name = str(getattr(broker, "exchange_name", "") or "").strip().lower()
        compact = _normalize_symbol_text(normalized_symbol)
        parts = compact.split("/", 1) if "/" in compact else []
        supports_lots = False
        forex_quotes = set(getattr(self._parent, "FOREX_SYMBOL_QUOTES", set()) or set())
        if exchange_name == "oanda" and len(parts) == 2:
            base, quote = parts
            supports_lots = (
                    len(base) == 3
                    and len(quote) == 3
                    and base.isalpha()
                    and quote.isalpha()
                    and base in forex_quotes
                    and quote in forex_quotes
            )
        lot_units = float(getattr(self._parent, "FOREX_STANDARD_LOT_UNITS", 100000.0) or 100000.0)
        return {
            "symbol": normalized_symbol,
            "supports_lots": supports_lots,
            "default_mode": "lots" if supports_lots else "units",
            "lot_units": lot_units,
        }

    async def _preflight_trade_submission(self, **kwargs: Any) -> dict[str, Any] | None:
        active_session_id = getattr(self._parent, "active_session_id", None)
        if active_session_id != self.session_id:
            return None
        preflight = getattr(self._parent, "_preflight_trade_submission", None)
        if not callable(preflight):
            return None
        return await preflight(**kwargs)


class TradingSession:
    """One isolated broker connection and trading runtime."""

    def __init__(
            self,
            *,
            session_id: str,
            config: Any,
            parent_controller: Any,
            logger: logging.Logger | None = None,
            snapshot_interval_seconds: float = 10.0,
            on_state_change: Any = None,
    ) -> None:
        self.session_id = str(session_id or "").strip()
        if not self.session_id:
            raise ValueError("session_id is required")
        self.config = config
        self.parent_controller = parent_controller
        self.logger = (logger or logging.getLogger("TradingSession")).getChild(self.session_id)
        self.snapshot_interval_seconds = max(2.0, float(snapshot_interval_seconds or 10.0))
        self.on_state_change = on_state_change

        broker_config = getattr(config, "broker", None)
        self.exchange = str(getattr(broker_config, "exchange", "broker") or "broker").strip().lower() or "broker"
        self.mode = str(getattr(broker_config, "mode", "paper") or "paper").strip().lower() or "paper"
        self.broker_type = str(getattr(broker_config, "type", "paper") or "paper").strip().lower() or "paper"
        self.strategy_name = str(getattr(config, "strategy", "Trend Following") or "Trend Following").strip() or "Trend Following"
        self.label = f"{self.exchange.upper()} {self.mode.upper()} {self.session_id.split('-')[-1].upper()}"

        self.status = "created"
        self.connected = False
        self.autotrading = False
        self.started_at = _utc_now()
        self.last_update_at = self.started_at
        self.last_error = ""

        self.broker = None
        self.trading_system = None
        self.session_controller = None
        self.event_bus = None
        self.portfolio = None

        self.symbols: list[str] = []
        self.symbol_catalog: list[str] = []
        self.balances: dict[str, Any] = {}
        self.positions: list[dict[str, Any]] = []
        self.open_orders: list[dict[str, Any]] = []
        self.trade_history: list[dict[str, Any]] = []
        self.latest_tickers: dict[str, dict[str, Any]] = {}
        self.last_ai_signal: dict[str, Any] = {}
        self.last_strategy_debug: dict[str, Any] = {}
        self.autotrade_scope = str(getattr(parent_controller, "autotrade_scope", "all") or "all").strip().lower() or "all"
        self.autotrade_watchlist = {
            _normalize_symbol_text(symbol)
            for symbol in list(getattr(parent_controller, "autotrade_watchlist", set()) or set())
            if _normalize_symbol_text(symbol)
        }
        self.symbol_strategy_assignments = copy.deepcopy(getattr(parent_controller, "symbol_strategy_assignments", {}) or {})
        self.symbol_strategy_rankings = copy.deepcopy(getattr(parent_controller, "symbol_strategy_rankings", {}) or {})
        self.symbol_strategy_locks = set(getattr(parent_controller, "symbol_strategy_locks", set()) or set())
        self.candle_buffers: dict[str, Any] = {}
        self.orderbook_buffer = OrderBookBuffer()
        self.ticker_buffer = TickerBuffer(max_length=int(getattr(parent_controller, "limit", 1000) or 1000))
        self.recent_trades_cache: dict[str, Any] = {}
        self.recent_trades_last_request_at: dict[str, Any] = {}
        self.live_agent_runtime_feed: list[dict[str, Any]] = []
        self.live_agent_decision_events: dict[str, list[dict[str, Any]]] = {}
        self.risk_limits = self._resolve_risk_limits(config)
        self.risk_state = SessionRiskState()

        self._lock = asyncio.Lock()
        self._snapshot_task: asyncio.Task[Any] | None = None
        self._runtime_task: asyncio.Task[Any] | None = None
        self._peak_equity = 0.0
        self._runtime_streams_bound = False
        self._runtime_memory_sink = None
        self._runtime_bus_subscriptions: list[tuple[str, Any]] = []

    def _account_identity_candidates(self, payload: Any) -> list[Mapping[str, Any]]:
        queue = [payload]
        candidates: list[Mapping[str, Any]] = []
        seen: set[int] = set()
        while queue:
            current = queue.pop(0)
            marker = id(current)
            if marker in seen:
                continue
            seen.add(marker)
            if isinstance(current, Mapping):
                candidates.append(current)
                for key in ("raw", "account", "selected_account", "primary_account"):
                    nested = current.get(key)
                    if isinstance(nested, Mapping):
                        queue.append(nested)
                for key in ("accounts", "items", "results", "data"):
                    nested = current.get(key)
                    if isinstance(nested, (list, tuple)):
                        queue.extend(nested)
            elif isinstance(current, (list, tuple)):
                queue.extend(current)
        return candidates

    def _account_identity_from_payload(
            self,
            payload: Any,
            *,
            allow_generic_identifiers: bool = False,
    ) -> tuple[str | None, str | None]:
        for candidate in self._account_identity_candidates(payload):
            account_id_values = [
                candidate.get("account_id"),
                candidate.get("accountId"),
                candidate.get("account"),
                candidate.get("acctId"),
                candidate.get("accountNumber"),
            ]
            if allow_generic_identifiers:
                account_id_values.extend([candidate.get("id"), candidate.get("name")])
            account_id = _normalized_text(*account_id_values)
            account_hash = _normalized_text(
                candidate.get("account_hash"),
                candidate.get("accountHash"),
                candidate.get("hash"),
            )
            if account_id or account_hash:
                return account_id or None, account_hash or None
        return None, None

    def _apply_account_identity(self, *, account_id: str | None = None, account_hash: str | None = None) -> None:
        broker = self.broker
        broker_config = getattr(self.config, "broker", None)

        resolved_account_id = _normalized_text(account_id)
        resolved_account_hash = _normalized_text(account_hash)

        if resolved_account_id and broker is not None and hasattr(broker, "account_id"):
            broker.account_id = resolved_account_id
        if resolved_account_hash and broker is not None and hasattr(broker, "account_hash"):
            broker.account_hash = resolved_account_hash

        broker_state = getattr(broker, "session_state", None) if broker is not None else None
        if broker_state is not None:
            if resolved_account_id and hasattr(broker_state, "account_id"):
                broker_state.account_id = resolved_account_id
            if resolved_account_hash and hasattr(broker_state, "account_hash"):
                broker_state.account_hash = resolved_account_hash

        if broker_config is None:
            return

        if resolved_account_id:
            broker_config.account_id = resolved_account_id

        config_options = dict(getattr(broker_config, "options", None) or {})
        config_params = dict(getattr(broker_config, "params", None) or {})
        broker_options = dict(getattr(broker, "options", None) or {}) if broker is not None else {}
        broker_params = dict(getattr(broker, "params", None) or {}) if broker is not None else {}

        if resolved_account_id:
            config_options["account_id"] = resolved_account_id
            config_params["account_id"] = resolved_account_id
            broker_options["account_id"] = resolved_account_id
            broker_params["account_id"] = resolved_account_id
        if resolved_account_hash:
            config_options["account_hash"] = resolved_account_hash
            config_params["account_hash"] = resolved_account_hash
            broker_options["account_hash"] = resolved_account_hash
            broker_params["account_hash"] = resolved_account_hash

        broker_config.options = config_options
        broker_config.params = config_params
        if broker is not None and hasattr(broker, "options"):
            broker.options = broker_options
        if broker is not None and hasattr(broker, "params"):
            broker.params = broker_params

    def _configured_symbol_hints(self) -> list[str]:
        broker = self.broker
        broker_config = getattr(self.config, "broker", None)
        normalized = []
        sources = (
            getattr(self, "symbol_catalog", None),
            getattr(self, "symbols", None),
            getattr(broker, "symbols", None) if broker is not None else None,
            getattr(broker, "params", None) if broker is not None else None,
            getattr(broker, "options", None) if broker is not None else None,
            getattr(broker_config, "params", None) if broker_config is not None else None,
            getattr(broker_config, "options", None) if broker_config is not None else None,
        )
        for source in sources:
            if isinstance(source, Mapping):
                candidates = (
                    source.get("symbols"),
                    source.get("default_symbols"),
                    source.get("watchlist_symbols"),
                )
            else:
                candidates = (source,)
            for candidate in candidates:
                for symbol in _normalize_symbol_sequence(candidate):
                    if symbol not in normalized:
                        normalized.append(symbol)
        return normalized

    async def _synchronize_account_identity(self, payload: Any = None) -> None:
        broker = self.broker
        broker_config = getattr(self.config, "broker", None)
        if broker is None and broker_config is None:
            return

        broker_options = dict(getattr(broker, "options", None) or {}) if broker is not None else {}
        broker_params = dict(getattr(broker, "params", None) or {}) if broker is not None else {}
        config_options = dict(getattr(broker_config, "options", None) or {}) if broker_config is not None else {}
        config_params = dict(getattr(broker_config, "params", None) or {}) if broker_config is not None else {}

        account_id, account_hash = self._account_identity_from_payload(payload)
        account_id = _normalized_text(
            account_id,
            getattr(broker, "account_id", None) if broker is not None else None,
            getattr(broker_config, "account_id", None) if broker_config is not None else None,
            broker_options.get("account_id"),
            broker_params.get("account_id"),
            config_options.get("account_id"),
            config_params.get("account_id"),
        ) or None
        account_hash = _normalized_text(
            account_hash,
            getattr(broker, "account_hash", None) if broker is not None else None,
            broker_options.get("account_hash"),
            broker_params.get("account_hash"),
            config_options.get("account_hash"),
            config_params.get("account_hash"),
        ) or None

        if (not account_id or not account_hash) and broker is not None:
            get_accounts = getattr(broker, "get_accounts", None)
            if callable(get_accounts):
                try:
                    discovered = await get_accounts()
                except Exception:
                    self.logger.debug(
                        "Account discovery failed for session %s",
                        self.session_id,
                        exc_info=True,
                    )
                else:
                    discovered_account_id, discovered_account_hash = self._account_identity_from_payload(
                        discovered,
                        allow_generic_identifiers=True,
                    )
                    account_id = _normalized_text(discovered_account_id, account_id) or None
                    account_hash = _normalized_text(discovered_account_hash, account_hash) or None

        self._apply_account_identity(account_id=account_id, account_hash=account_hash)

    async def initialize(self) -> "TradingSession":
        async with self._lock:
            if self.connected and self.broker is not None and self.trading_system is not None:
                return self
            self.status = "connecting"
            self.last_error = ""
            self._notify_state_change()

            self.broker = self.parent_controller._build_broker_for_login(self.config)
            if self.broker is None:
                raise RuntimeError("Broker creation failed")
            if hasattr(self.broker, "controller"):
                self.broker.controller = self.parent_controller
            if hasattr(self.broker, "logger"):
                self.broker.logger = self.logger

            await self.broker.connect()
            await self._synchronize_account_identity()
            self.connected = True
            self.balances = await self._fetch_balances_safe()
            await self._synchronize_account_identity(self.balances)
            self.symbols = await self._fetch_symbols_safe()
            self._prune_symbol_scoped_state()

            self.session_controller = SessionControllerProxy(self.parent_controller, self)
            self.trading_system = TradingCore(self.session_controller)
            self.event_bus = getattr(self.trading_system, "event_bus", None)
            self.portfolio = getattr(getattr(self.trading_system, "portfolio", None), "portfolio", None)
            self.session_controller.trading_system = self.trading_system
            self.session_controller.portfolio = self.portfolio
            self.session_controller.event_bus = self.event_bus
            if hasattr(self.broker, "controller"):
                self.broker.controller = self.session_controller
            self._bind_runtime_monitor_streams()
            if self.event_bus is not None and hasattr(self.event_bus, "subscribe"):
                self.event_bus.subscribe("*", self._capture_event)
            self.positions = await self._fetch_positions_safe()
            await self._synchronize_account_identity(self.positions)
            self.open_orders = await self._fetch_open_orders_safe()
            self._update_risk_state()

            self.status = "risk_blocked" if self.risk_state.blocked else "ready"
            self.last_update_at = _utc_now()
            self._ensure_snapshot_task()
            self._notify_state_change()
            return self

    def _prune_symbol_scoped_state(self) -> None:
        catalog = {
            _normalize_symbol_text(symbol)
            for symbol in list(self.symbol_catalog or self.symbols or [])
            if _normalize_symbol_text(symbol)
        }
        if not catalog:
            return
        self.autotrade_watchlist = {symbol for symbol in set(self.autotrade_watchlist or set()) if symbol in catalog}
        self.symbol_strategy_assignments = {
            _normalize_symbol_text(symbol): copy.deepcopy(rows)
            for symbol, rows in dict(self.symbol_strategy_assignments or {}).items()
            if _normalize_symbol_text(symbol) in catalog
        }
        self.symbol_strategy_rankings = {
            _normalize_symbol_text(symbol): copy.deepcopy(rows)
            for symbol, rows in dict(self.symbol_strategy_rankings or {}).items()
            if _normalize_symbol_text(symbol) in catalog
        }
        self.symbol_strategy_locks = {
            _normalize_symbol_text(symbol)
            for symbol in set(self.symbol_strategy_locks or set())
            if _normalize_symbol_text(symbol) in catalog
        }

    async def start_trading(self) -> "TradingSession":
        await self.initialize()
        await self.refresh_state()
        async with self._lock:
            if self.trading_system is None:
                raise RuntimeError("Trading system is not initialized")
            if self.autotrading:
                return self
            if self.risk_state.blocked:
                self.status = "risk_blocked"
                self.last_error = self.risk_state.reason
                self.last_update_at = _utc_now()
                self._notify_state_change()
                raise RuntimeError(self.risk_state.reason or "Session risk controls blocked trading.")
            runtime_task = asyncio.create_task(self._run_trading_runtime(), name=f"session_runtime:{self.session_id}")
            runtime_task.add_done_callback(self._on_runtime_task_done)
            self._runtime_task = runtime_task
        await asyncio.sleep(0)
        runtime_task = self._runtime_task
        if runtime_task is not None and runtime_task.done():
            exception = runtime_task.exception()
            if exception is not None:
                raise exception
        async with self._lock:
            self.autotrading = True
            self.status = "running"
            self.last_update_at = _utc_now()
            self._notify_state_change()
            return self

    async def stop_trading(self, *, reason: str | None = None, risk_blocked: bool = False) -> "TradingSession":
        runtime_task = None
        async with self._lock:
            runtime_task = self._runtime_task
            self._runtime_task = None
            if self.trading_system is not None and (self.autotrading or runtime_task is not None):
                try:
                    await self.trading_system.stop(wait_for_background_workers=True)
                except TypeError:
                    await self.trading_system.stop()
        if runtime_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await runtime_task
        async with self._lock:
            self.autotrading = False
            if risk_blocked:
                self.status = "risk_blocked"
                self.last_error = str(reason or self.risk_state.reason or "").strip()
            else:
                self.status = "ready" if self.connected else "stopped"
            self.last_update_at = _utc_now()
            self._notify_state_change()
            return self

    async def close(self) -> None:
        snapshot_task = None
        runtime_task = None
        trading_system = None
        broker = None
        event_bus = None
        async with self._lock:
            self.status = "stopping"
            self._notify_state_change()
            snapshot_task = self._snapshot_task
            self._snapshot_task = None
            runtime_task = self._runtime_task
            self._runtime_task = None
            trading_system = self.trading_system
            broker = self.broker
            event_bus = self.event_bus
        if snapshot_task is not None and not snapshot_task.done():
            snapshot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await snapshot_task
        self._unbind_runtime_monitor_streams()
        if event_bus is not None and hasattr(event_bus, "unsubscribe"):
            event_bus.unsubscribe("*", self._capture_event)
        if trading_system is not None:
            try:
                await trading_system.stop(wait_for_background_workers=True)
            except TypeError:
                await trading_system.stop()
        if runtime_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await runtime_task
        if broker is not None and hasattr(broker, "close"):
            await broker.close()
        async with self._lock:
            self.trading_system = None
            self.broker = None
            self.event_bus = None
            self.connected = False
            self.autotrading = False
            self.status = "closed"
            self.last_update_at = _utc_now()
            self._notify_state_change()

    @staticmethod
    def _normalize_runtime_symbol(symbol: Any) -> str:
        return _normalize_symbol_text(symbol)

    @staticmethod
    def _normalize_runtime_timestamp(timestamp: Any) -> tuple[float | None, str]:
        if isinstance(timestamp, datetime):
            normalized = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
            return normalized.timestamp(), normalized.strftime("%Y-%m-%d %H:%M:%S UTC")
        text = str(timestamp or "").strip()
        if not text:
            return None, ""
        try:
            normalized = datetime.fromisoformat(text.replace("Z", "+00:00"))
            normalized = normalized.replace(tzinfo=timezone.utc) if normalized.tzinfo is None else normalized.astimezone(timezone.utc)
            return normalized.timestamp(), normalized.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return None, text

    @staticmethod
    def _coerce_runtime_event_payload(data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            return dict(data)
        if is_dataclass(data):
            try:
                return asdict(data)
            except Exception:
                return {}
        if hasattr(data, "__dict__"):
            try:
                return {
                    str(key): value
                    for key, value in vars(data).items()
                    if not str(key).startswith("_")
                }
            except Exception:
                return {}
        try:
            return dict(data or {})
        except Exception:
            return {}

    def _append_live_agent_decision_event(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        symbol = self._normalize_runtime_symbol(payload.get("symbol"))
        if not symbol:
            return
        events = self.live_agent_decision_events.setdefault(symbol, [])
        events.append(dict(payload, symbol=symbol))
        if len(events) > 250:
            del events[:-250]

    def _append_live_agent_runtime_feed(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        row = dict(payload)
        symbol = self._normalize_runtime_symbol(row.get("symbol"))
        if symbol:
            row["symbol"] = symbol
        row["kind"] = str(row.get("kind") or "runtime").strip().lower() or "runtime"
        row["message"] = str(row.get("message") or row.get("reason") or "").strip()
        row["stage"] = str(row.get("stage") or "").strip()
        row["agent_name"] = str(row.get("agent_name") or "").strip()
        row["event_type"] = str(row.get("event_type") or "").strip()
        row["strategy_name"] = str(row.get("strategy_name") or "").strip()
        row["timeframe"] = str(row.get("timeframe") or "").strip()
        row["decision_id"] = str(row.get("decision_id") or "").strip()
        row["profile_id"] = str(row.get("profile_id") or "").strip()

        timestamp_value, timestamp_label = self._normalize_runtime_timestamp(
            row.get("timestamp") if row.get("timestamp") not in (None, "") else datetime.now(timezone.utc)
        )
        row["timestamp"] = timestamp_value
        row["timestamp_label"] = str(row.get("timestamp_label") or timestamp_label or "").strip()
        if not row["timestamp_label"] and timestamp_value is not None:
            row["timestamp_label"] = datetime.fromtimestamp(timestamp_value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        self.live_agent_runtime_feed.append(row)
        if len(self.live_agent_runtime_feed) > 500:
            del self.live_agent_runtime_feed[:-500]
        return dict(row)

    def _emit_runtime_signal_to_parent(self, payload: dict[str, Any]) -> None:
        parent = self.parent_controller
        active_session_id = str(getattr(parent, "active_session_id", "") or "").strip()
        if active_session_id and active_session_id != self.session_id:
            return
        signal = getattr(parent, "agent_runtime_signal", None)
        if signal is None:
            return
        try:
            signal.emit(dict(payload or {}))
        except Exception:
            self.logger.debug("Unable to emit session runtime signal", exc_info=True)

    def _runtime_bus_message(self, event_type: str, data: dict[str, Any]) -> str:
        payload = dict(data or {})
        signal_payload = dict(payload.get("signal") or {}) if isinstance(payload.get("signal"), dict) else {}
        review_payload = dict(payload.get("trade_review") or {}) if isinstance(payload.get("trade_review"), dict) else {}
        symbol = self._normalize_runtime_symbol(payload.get("symbol"))
        strategy_name = str(
            signal_payload.get("strategy_name")
            or review_payload.get("strategy_name")
            or payload.get("strategy_name")
            or ""
        ).strip()
        timeframe = str(payload.get("timeframe") or review_payload.get("timeframe") or "").strip()
        side = str(signal_payload.get("side") or review_payload.get("side") or payload.get("side") or "").strip().upper()
        reason = str(review_payload.get("reason") or signal_payload.get("reason") or payload.get("reason") or "").strip()
        if event_type == EventType.SIGNAL:
            detail = f"{side or 'HOLD'} via {strategy_name or 'strategy'}"
            if timeframe:
                detail = f"{detail} ({timeframe})"
            return f"Signal selected for {symbol}: {detail}."
        if event_type == EventType.REASONING_DECISION:
            decision = str(payload.get("decision") or "NEUTRAL").strip().upper() or "NEUTRAL"
            confidence = payload.get("confidence")
            try:
                return f"Reasoning engine marked {symbol} as {decision} at {float(confidence):.2f} confidence."
            except Exception:
                return f"Reasoning engine marked {symbol} as {decision}."
        if event_type == EventType.DECISION_EVENT:
            action = str(payload.get("action") or "HOLD").strip().upper() or "HOLD"
            profile_id = str(payload.get("profile_id") or "").strip()
            selected_strategy = str(payload.get("selected_strategy") or strategy_name or "").strip() or "strategy blend"
            confidence = payload.get("confidence")
            profile_text = f" for profile {profile_id}" if profile_id else ""
            try:
                return f"TraderAgent chose {action} on {symbol} via {selected_strategy}{profile_text} at {float(confidence):.2f} confidence."
            except Exception:
                return f"TraderAgent chose {action} on {symbol} via {selected_strategy}{profile_text}."
        if event_type == EventType.RISK_APPROVED:
            return f"Risk approved {side or 'trade'} for {symbol}."
        if event_type == EventType.EXECUTION_PLAN:
            execution_strategy = str(payload.get("execution_strategy") or "").strip() or "default routing"
            return f"Execution plan ready for {symbol}: {execution_strategy}."
        if event_type == EventType.ORDER_FILLED:
            status = str((payload.get("execution_result") or {}).get("status") or payload.get("status") or "filled").strip().lower()
            return f"Execution {status} for {symbol}."
        if event_type == EventType.RISK_ALERT:
            return reason or f"Risk blocked the trade for {symbol}."
        return reason or f"{event_type} for {symbol}."

    def _handle_live_agent_memory_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict):
            return {}
        symbol = self._normalize_runtime_symbol(event.get("symbol"))
        if not symbol:
            return {}
        payload = dict(event.get("payload") or {})
        timestamp_value, timestamp_label = self._normalize_runtime_timestamp(event.get("timestamp"))
        row = {
            "kind": "memory",
            "decision_id": str(event.get("decision_id") or "").strip(),
            "symbol": symbol,
            "agent_name": str(event.get("agent") or "").strip(),
            "stage": str(event.get("stage") or "").strip(),
            "strategy_name": str(payload.get("strategy_name") or "").strip(),
            "timeframe": str(payload.get("timeframe") or "").strip(),
            "side": str(payload.get("side") or "").strip().lower(),
            "confidence": payload.get("confidence"),
            "approved": payload.get("approved"),
            "reason": str(payload.get("reason") or "").strip(),
            "timestamp": timestamp_value,
            "timestamp_label": timestamp_label,
            "payload": payload,
            "message": f"{str(event.get('agent') or 'Agent').strip() or 'Agent'} {str(event.get('stage') or 'updated').strip() or 'updated'} for {symbol}.",
        }
        if row["reason"]:
            row["message"] = f"{row['message']} | {row['reason']}"
        self._append_live_agent_decision_event(row)
        normalized = self._append_live_agent_runtime_feed(row)
        self._emit_runtime_signal_to_parent(normalized)
        return normalized

    async def _handle_trading_agent_bus_event(self, event: Any) -> dict[str, Any]:
        data = self._coerce_runtime_event_payload(getattr(event, "data", {}) or {})
        symbol = self._normalize_runtime_symbol(data.get("symbol"))
        if not symbol:
            return {}
        event_type = str(getattr(event, "type", "") or "").strip()
        signal_payload = dict(data.get("signal") or {}) if isinstance(data.get("signal"), dict) else {}
        review_payload = dict(data.get("trade_review") or {}) if isinstance(data.get("trade_review"), dict) else {}
        metadata = dict(data.get("metadata") or {}) if isinstance(data.get("metadata"), dict) else {}
        applied_constraints = data.get("applied_constraints")
        if isinstance(applied_constraints, (list, tuple, set)):
            applied_constraints = [str(item).strip() for item in applied_constraints if str(item).strip()]
        elif str(applied_constraints or "").strip():
            applied_constraints = [str(applied_constraints).strip()]
        else:
            applied_constraints = []
        votes = dict(data.get("votes") or {}) if isinstance(data.get("votes"), dict) else {}
        features = dict(data.get("features") or {}) if isinstance(data.get("features"), dict) else {}
        selected_strategy = str(
            data.get("selected_strategy")
            or signal_payload.get("strategy_name")
            or review_payload.get("strategy_name")
            or data.get("strategy_name")
            or ""
        ).strip()
        action = str(data.get("action") or "").strip().upper()
        side = str(signal_payload.get("side") or review_payload.get("side") or data.get("side") or "").strip().lower()
        if not side and action in {"BUY", "SELL"}:
            side = action.lower()
        row = {
            "kind": "bus",
            "event_type": event_type,
            "agent_name": str(getattr(event, "source", "") or data.get("agent_name") or "").strip(),
            "symbol": symbol,
            "decision_id": str(data.get("decision_id") or review_payload.get("decision_id") or "").strip(),
            "profile_id": str(data.get("profile_id") or metadata.get("profile_id") or "").strip(),
            "strategy_name": selected_strategy,
            "timeframe": str(data.get("timeframe") or review_payload.get("timeframe") or metadata.get("timeframe") or "").strip(),
            "stage": str(data.get("stage") or (action.lower() if action else "")).strip(),
            "action": action,
            "side": side,
            "price": data.get("price"),
            "quantity": data.get("quantity"),
            "confidence": data.get("confidence"),
            "model_probability": data.get("model_probability"),
            "applied_constraints": applied_constraints,
            "votes": votes,
            "features": features,
            "metadata": metadata,
            "reason": str(data.get("reasoning") or review_payload.get("reason") or signal_payload.get("reason") or data.get("reason") or "").strip(),
            "approved": data.get("approved"),
            "timestamp": data.get("timestamp") or getattr(event, "timestamp", None),
            "message": self._runtime_bus_message(event_type, data),
            "payload": data,
        }
        self._append_live_agent_decision_event(row)
        normalized = self._append_live_agent_runtime_feed(row)
        self._emit_runtime_signal_to_parent(normalized)
        return normalized

    def _bind_runtime_monitor_streams(self) -> None:
        if self._runtime_streams_bound:
            return
        trading_system = self.trading_system
        if trading_system is None:
            return
        memory = getattr(trading_system, "agent_memory", None)
        if memory is not None and hasattr(memory, "add_sink"):
            self._runtime_memory_sink = memory.add_sink(self._handle_live_agent_memory_event)
        event_bus = getattr(trading_system, "event_bus", None)
        if event_bus is not None and hasattr(event_bus, "subscribe"):
            for event_type in (
                    EventType.SIGNAL,
                    EventType.REASONING_DECISION,
                    EventType.DECISION_EVENT,
                    EventType.RISK_APPROVED,
                    EventType.RISK_ALERT,
                    EventType.EXECUTION_PLAN,
                    EventType.ORDER_FILLED,
            ):
                handler = event_bus.subscribe(event_type, self._handle_trading_agent_bus_event)
                self._runtime_bus_subscriptions.append((event_type, handler))
        self._runtime_streams_bound = True

    def _unbind_runtime_monitor_streams(self) -> None:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None and hasattr(event_bus, "unsubscribe"):
            for event_type, handler in list(self._runtime_bus_subscriptions):
                with contextlib.suppress(Exception):
                    event_bus.unsubscribe(event_type, handler)
        self._runtime_bus_subscriptions = []
        self._runtime_memory_sink = None
        self._runtime_streams_bound = False

    async def refresh_state(self) -> None:
        if self.broker is None:
            return
        balances = await self._fetch_balances_safe()
        if balances:
            self.balances = balances
            await self._synchronize_account_identity(balances)
            if self.session_controller is not None:
                self.session_controller.balances = dict(balances)
                self.session_controller.balance = dict(balances)
        self.positions = await self._fetch_positions_safe()
        await self._synchronize_account_identity(self.positions)
        self.open_orders = await self._fetch_open_orders_safe()
        self._update_risk_state()
        if self.risk_state.blocked:
            await self.stop_trading(reason=self.risk_state.reason, risk_blocked=True)
        elif self.status == "risk_blocked" and not self.autotrading:
            self.status = "ready"
            self.last_error = ""
        self.last_update_at = _utc_now()
        self._notify_state_change()

    async def route_price(self, symbol: str, side: str) -> dict[str, Any] | None:
        ticker = await self._fetch_ticker_safe(symbol)
        if not isinstance(ticker, dict):
            return None
        keys = ("ask", "price", "last", "close") if str(side or "").strip().lower() == "buy" else ("bid", "price", "last", "close")
        for key in keys:
            price = _safe_float(ticker.get(key), 0.0)
            if price > 0:
                return {
                    "session_id": self.session_id,
                    "exchange": self.exchange,
                    "symbol": str(symbol or "").strip().upper(),
                    "side": str(side or "").strip().lower(),
                    "price": price,
                    "source": key,
                    "session_label": self.label,
                }
        return None

    def snapshot(self) -> SessionSnapshot:
        account_label = self.session_controller.current_account_label() if self.session_controller is not None else "Not set"
        return SessionSnapshot(
            session_id=self.session_id,
            label=self.label,
            exchange=self.exchange,
            broker_type=self.broker_type,
            mode=self.mode,
            strategy=self.strategy_name,
            status=self.status,
            connected=self.connected,
            autotrading=self.autotrading,
            account_label=account_label,
            equity=self._extract_equity_value(),
            balance_summary=self._balance_summary_text(),
            positions_count=len(self.positions),
            open_orders_count=len(self.open_orders),
            trade_count=len(self.trade_history),
            symbols_count=len(self.symbols),
            last_error=self.last_error,
            last_update_at=self.last_update_at.isoformat(),
            started_at=self.started_at.isoformat(),
            risk_blocked=self.risk_state.blocked,
            drawdown_pct=self.risk_state.drawdown_pct,
            gross_exposure=self.risk_state.gross_exposure,
            gross_exposure_pct=self.risk_state.gross_exposure_pct,
            max_observed_leverage=self.risk_state.max_observed_leverage,
            metadata={
                "last_ai_signal": dict(self.last_ai_signal or {}),
                "last_strategy_debug": dict(self.last_strategy_debug or {}),
                "risk_limits": self.risk_limits.to_dict(),
                "risk_state": self.risk_state.to_dict(),
            },
        )

    async def publish_event(self, event_type: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        if self.event_bus is None or not hasattr(self.event_bus, "publish"):
            raise RuntimeError("Session event bus is not available.")
        metadata = dict(kwargs.pop("metadata", {}) or {})
        metadata.setdefault("session_id", self.session_id)
        metadata.setdefault("session_label", self.label)
        body = dict(payload or {})
        body.setdefault("session_id", self.session_id)
        body.setdefault("session_label", self.label)
        return await self.event_bus.publish(event_type, body, metadata=metadata, **kwargs)

    def subscribe_event(self, event_type: str, handler: Any) -> Any:
        if self.event_bus is None or not hasattr(self.event_bus, "subscribe"):
            raise RuntimeError("Session event bus is not available.")
        return self.event_bus.subscribe(event_type, handler)

    def gross_exposure(self) -> float:
        return self.risk_state.gross_exposure

    def unrealized_pnl(self) -> float:
        return self._positions_unrealized_pnl()

    def _ensure_snapshot_task(self) -> None:
        if self._snapshot_task is not None and not self._snapshot_task.done():
            return
        self._snapshot_task = asyncio.create_task(self._snapshot_loop(), name=f"session_snapshot:{self.session_id}")

    async def _run_trading_runtime(self) -> None:
        if self.trading_system is None:
            raise RuntimeError("Trading system is not initialized")
        await self.trading_system.start()

    def _on_runtime_task_done(self, task: asyncio.Task[Any]) -> None:
        if self._runtime_task is not task:
            return
        self._runtime_task = None
        if self.status in {"closed", "stopping"}:
            return
        self.autotrading = False
        exception = None
        if not task.cancelled():
            exception = task.exception()
        if exception is not None:
            self.last_error = str(exception)
            self.status = "risk_blocked" if self.risk_state.blocked else ("error" if self.connected else "stopped")
            self.logger.error("Session runtime failed", exc_info=(type(exception), exception, exception.__traceback__))
        else:
            self.status = "risk_blocked" if self.risk_state.blocked else ("ready" if self.connected else "stopped")
        self.last_update_at = _utc_now()
        self._notify_state_change()

    async def _snapshot_loop(self) -> None:
        try:
            while self.connected:
                await asyncio.sleep(self.snapshot_interval_seconds)
                await self.refresh_state()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            self.logger.exception("Session snapshot loop failed")
            self._notify_state_change()

    async def _capture_event(self, event: Any) -> None:
        metadata = getattr(event, "metadata", None)
        if isinstance(metadata, dict):
            metadata.setdefault("session_id", self.session_id)
        payload = dict(getattr(event, "data", {}) or {}) if isinstance(getattr(event, "data", None), dict) else {}
        if payload:
            payload.setdefault("session_id", self.session_id)

        event_type = str(getattr(event, "type", "") or "").strip()
        if event_type in {EventType.ORDER_EVENT, EventType.ORDER_UPDATE, EventType.ORDER_FILLED, EventType.FILL, EventType.EXECUTION_REPORT}:
            if payload:
                self.trade_history.append(dict(payload))
                self.trade_history = self.trade_history[-500:]
        elif event_type in {EventType.POSITION_EVENT, EventType.POSITION_UPDATE} and isinstance(payload.get("positions"), list):
            self.positions = [dict(item) for item in payload.get("positions", []) if isinstance(item, dict)]
        elif event_type in {EventType.MARKET_DATA_EVENT, EventType.PRICE_UPDATE, EventType.MARKET_TICK}:
            symbol = str(payload.get("symbol") or "").strip().upper()
            if symbol:
                self.latest_tickers[symbol] = dict(payload)
                self.latest_tickers = dict(list(self.latest_tickers.items())[-250:])
        elif event_type in {EventType.RISK_ALERT, EventType.RISK_REJECTED} and payload:
            self.last_error = str(payload.get("reason") or payload.get("message") or self.last_error).strip()
        self.last_update_at = _utc_now()
        self._notify_state_change()

    async def _fetch_balances_safe(self) -> dict[str, Any]:
        if self.broker is None or not hasattr(self.broker, "fetch_balance"):
            return dict(self.balances or {})
        try:
            balances = await self.broker.fetch_balance()
        except Exception as exc:
            self.last_error = str(exc)
            self.logger.debug("Balance refresh failed for session %s: %s", self.session_id, exc)
            return dict(self.balances or {})
        return dict(balances or {}) if isinstance(balances, dict) else {"raw": balances}

    async def _fetch_symbols_safe(self) -> list[str]:
        symbols = None
        if self.broker is None:
            return list(self._configured_symbol_hints())
        try:
            if hasattr(self.broker, "fetch_symbol"):
                symbols = await self.broker.fetch_symbol()
            elif hasattr(self.broker, "fetch_symbols"):
                symbols = await self.broker.fetch_symbols()
        except Exception as exc:
            self.last_error = str(exc)
            self.logger.debug("Symbol discovery failed for session %s: %s", self.session_id, exc)
            fallback = self._configured_symbol_hints()
            self.symbol_catalog = list(fallback)
            return fallback
        if isinstance(symbols, dict):
            instruments = symbols.get("instruments", [])
            normalized = []
            for item in instruments:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("displayName")
                    if name:
                        normalized.append(str(name).strip())
            symbols = normalized
        normalized = _normalize_symbol_sequence(symbols)
        if not normalized:
            normalized = self._configured_symbol_hints()
        self.symbol_catalog = list(normalized)
        return normalized

    async def _fetch_positions_safe(self) -> list[dict[str, Any]]:
        if self.broker is None or not hasattr(self.broker, "fetch_positions"):
            return list(self.positions)
        try:
            positions = await self.broker.fetch_positions()
        except TypeError:
            positions = await self.broker.fetch_positions(symbols=list(self.symbols or []))
        except Exception as exc:
            self.logger.debug("Position refresh failed for session %s: %s", self.session_id, exc)
            return list(self.positions)
        return [dict(item) for item in list(positions or []) if isinstance(item, dict)]

    async def _fetch_open_orders_safe(self) -> list[dict[str, Any]]:
        if self.broker is None or not hasattr(self.broker, "fetch_open_orders"):
            return list(self.open_orders)
        try:
            orders = await self.broker.fetch_open_orders(limit=100)
        except TypeError:
            try:
                orders = await self.broker.fetch_open_orders()
            except Exception as exc:
                self.logger.debug("Open-order refresh failed for session %s: %s", self.session_id, exc)
                return list(self.open_orders)
        except Exception as exc:
            self.logger.debug("Open-order refresh failed for session %s: %s", self.session_id, exc)
            return list(self.open_orders)
        return [dict(item) for item in list(orders or []) if isinstance(item, dict)]

    async def _fetch_ticker_safe(self, symbol: str) -> dict[str, Any] | None:
        normalized_symbol = str(symbol or "").strip().upper()
        if normalized_symbol in self.latest_tickers:
            return dict(self.latest_tickers[normalized_symbol])
        if self.broker is None or not hasattr(self.broker, "fetch_ticker"):
            return None
        try:
            ticker = await self.broker.fetch_ticker(normalized_symbol)
        except Exception as exc:
            self.logger.debug("Ticker refresh failed for session %s %s: %s", self.session_id, normalized_symbol, exc)
            return None
        if isinstance(ticker, dict):
            payload = dict(ticker)
            payload.setdefault("symbol", normalized_symbol)
            self.latest_tickers[normalized_symbol] = dict(payload)
            return payload
        return None

    def _extract_equity_value(self) -> float:
        balances = dict(self.balances or {})
        for key in ("nav", "equity", "net_liquidation", "account_value", "balance", "cash"):
            value = _safe_float(balances.get(key), 0.0)
            if value > 0:
                return value
        total = balances.get("total")
        if isinstance(total, dict):
            for currency in ("USD", "USDT", "USDC", "BUSD", "EUR", "GBP"):
                value = _safe_float(total.get(currency), 0.0)
                if value > 0:
                    return value
            if len(total) == 1:
                only_value = _safe_float(next(iter(total.values())), 0.0)
                if only_value > 0:
                    return only_value
        free_bucket = balances.get("free")
        if isinstance(free_bucket, dict):
            for currency in ("USD", "USDT", "USDC", "BUSD", "EUR", "GBP"):
                value = _safe_float(free_bucket.get(currency), 0.0)
                if value > 0:
                    return value
        return 0.0

    def _balance_summary_text(self) -> str:
        total = dict(self.balances or {}).get("total")
        if isinstance(total, dict):
            parts = []
            for currency in ("USD", "USDT", "USDC", "EUR", "GBP", "BTC"):
                value = _safe_float(total.get(currency), 0.0)
                if value > 0:
                    parts.append(f"{currency} {value:,.2f}")
                if len(parts) >= 2:
                    break
            if parts:
                return " | ".join(parts)
        equity = self._extract_equity_value()
        return f"Equity {equity:,.2f}" if equity > 0 else "Balance unavailable"

    def _resolve_risk_limits(self, config: Any) -> SessionRiskLimits:
        risk_config = getattr(config, "risk", None)
        broker_options = dict(getattr(getattr(config, "broker", None), "options", None) or {})
        return SessionRiskLimits(
            max_drawdown_pct=_normalize_fraction(
                broker_options.get(
                    "max_drawdown_pct",
                    getattr(risk_config, "max_daily_drawdown", getattr(risk_config, "max_drawdown", 0.10)),
                ),
                0.10,
            ),
            max_position_size_pct=_normalize_fraction(
                broker_options.get(
                    "max_position_size_pct",
                    getattr(risk_config, "max_position_size_pct", 0.10),
                ),
                0.10,
            ),
            max_gross_exposure_pct=_normalize_exposure_limit(
                broker_options.get(
                    "max_gross_exposure_pct",
                    getattr(risk_config, "max_gross_exposure_pct", 2.0),
                ),
                2.0,
            ),
            max_leverage=(
                    _safe_float(broker_options.get("max_leverage", getattr(risk_config, "max_leverage", None)), 0.0) or None
            ),
        )

    def _position_notional(self, position: dict[str, Any]) -> float:
        for key in ("notional", "notional_value", "position_value", "market_value", "exposure", "value", "cost"):
            value = _safe_float(position.get(key), 0.0)
            if value > 0:
                return abs(value)
        quantity = 0.0
        for key in ("contracts", "contract_size", "size", "qty", "quantity", "amount", "units"):
            quantity = _safe_float(position.get(key), 0.0)
            if quantity > 0:
                break
        price = 0.0
        for key in ("markPrice", "mark_price", "price", "entryPrice", "entry_price", "avgPrice", "average"):
            price = _safe_float(position.get(key), 0.0)
            if price > 0:
                break
        return abs(quantity * price)

    def _position_leverage(self, position: dict[str, Any]) -> float:
        for key in ("leverage", "effective_leverage"):
            value = _safe_float(position.get(key), 0.0)
            if value > 0:
                return value
        return 0.0

    def _position_unrealized_pnl(self, position: dict[str, Any]) -> float:
        for key in ("unrealizedPnl", "unrealized_pnl", "floatingProfit", "floating_profit", "pnl", "profit"):
            if key not in position:
                continue
            return _safe_float(position.get(key), 0.0)
        return 0.0

    def _positions_unrealized_pnl(self) -> float:
        return round(sum(self._position_unrealized_pnl(position) for position in self.positions), 6)

    def _update_risk_state(self) -> None:
        equity = max(self._extract_equity_value(), 0.0)
        if equity > self._peak_equity:
            self._peak_equity = equity
        peak_equity = max(self._peak_equity, equity)
        drawdown_pct = ((peak_equity - equity) / peak_equity) if peak_equity > 0 else 0.0

        gross_exposure = 0.0
        largest_position_notional = 0.0
        max_observed_leverage = 0.0
        for position in self.positions:
            if not isinstance(position, dict):
                continue
            notional = self._position_notional(position)
            leverage = self._position_leverage(position)
            gross_exposure += abs(notional)
            largest_position_notional = max(largest_position_notional, abs(notional))
            max_observed_leverage = max(max_observed_leverage, leverage)

        gross_exposure_pct = (gross_exposure / equity) if equity > 0 else 0.0
        largest_position_pct = (largest_position_notional / equity) if equity > 0 else 0.0

        reasons = []
        if drawdown_pct > self.risk_limits.max_drawdown_pct + 1e-12:
            reasons.append(
                f"Drawdown {drawdown_pct:.2%} exceeded session limit {self.risk_limits.max_drawdown_pct:.2%}."
            )
        if largest_position_pct > self.risk_limits.max_position_size_pct + 1e-12:
            reasons.append(
                f"Largest position {largest_position_pct:.2%} exceeded session position cap {self.risk_limits.max_position_size_pct:.2%}."
            )
        if gross_exposure_pct > self.risk_limits.max_gross_exposure_pct + 1e-12:
            reasons.append(
                f"Gross exposure {gross_exposure_pct:.2f}x exceeded session exposure cap {self.risk_limits.max_gross_exposure_pct:.2f}x."
            )
        if self.risk_limits.max_leverage is not None and max_observed_leverage > self.risk_limits.max_leverage + 1e-12:
            reasons.append(
                f"Observed leverage {max_observed_leverage:.2f}x exceeded session leverage cap {self.risk_limits.max_leverage:.2f}x."
            )

        self.risk_state = SessionRiskState(
            blocked=bool(reasons),
            reason=" ".join(reasons).strip(),
            equity=equity,
            peak_equity=peak_equity,
            drawdown_pct=drawdown_pct,
            gross_exposure=round(gross_exposure, 6),
            gross_exposure_pct=round(gross_exposure_pct, 6),
            largest_position_notional=round(largest_position_notional, 6),
            largest_position_pct=round(largest_position_pct, 6),
            max_observed_leverage=round(max_observed_leverage, 6),
            position_count=len(self.positions),
        )
        if self.risk_state.blocked and self.status not in {"closed", "stopping"}:
            self.last_error = self.risk_state.reason

    def _notify_state_change(self) -> None:
        if callable(self.on_state_change):
            try:
                self.on_state_change(self)
            except Exception:
                self.logger.debug("Session state callback failed", exc_info=True)