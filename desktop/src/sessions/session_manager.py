from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from sessions.trading_session import TradingSession


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _session_gross_exposure(session: TradingSession, snapshot: Any) -> float:
    gross_exposure = 0.0
    metadata = getattr(snapshot, "metadata", {}) or {}
    if isinstance(metadata, dict):
        risk_state = metadata.get("risk_state")
        if isinstance(risk_state, dict):
            gross_exposure = _safe_float(risk_state.get("gross_exposure"), 0.0)
    if gross_exposure <= 0 and hasattr(session, "gross_exposure"):
        try:
            gross_exposure = _safe_float(session.gross_exposure(), 0.0)
        except Exception:
            gross_exposure = 0.0
    return gross_exposure


def _session_unrealized_pnl(session: TradingSession) -> float:
    if hasattr(session, "unrealized_pnl"):
        try:
            return _safe_float(session.unrealized_pnl(), 0.0)
        except Exception:
            return 0.0
    return 0.0


class PortfolioAggregator:
    """Aggregate balances and exposure across multiple sessions."""

    def aggregate(self, sessions: Iterable[TradingSession]) -> dict[str, Any]:
        session_list = list(sessions)
        total_equity = 0.0
        total_positions = 0
        total_open_orders = 0
        total_trades = 0
        total_gross_exposure = 0.0
        total_unrealized_pnl = 0.0
        running_sessions = 0
        ready_sessions = 0
        risk_blocked_sessions = 0
        by_exchange: dict[str, dict[str, Any]] = {}

        for session in session_list:
            snapshot = session.snapshot()
            session_status = str(
                getattr(snapshot, "status", getattr(session, "status", "")) or ""
            ).strip().lower()
            total_equity += _safe_float(snapshot.equity, 0.0)
            total_positions += int(snapshot.positions_count or 0)
            total_open_orders += int(snapshot.open_orders_count or 0)
            total_trades += int(snapshot.trade_count or 0)
            total_gross_exposure += _session_gross_exposure(session, snapshot)
            total_unrealized_pnl += _session_unrealized_pnl(session)
            if session_status == "running":
                running_sessions += 1
            elif session_status == "ready":
                ready_sessions += 1
            if bool(getattr(snapshot, "risk_blocked", False)):
                risk_blocked_sessions += 1
            exchange_key = str(snapshot.exchange or "unknown").strip().lower() or "unknown"
            bucket = by_exchange.setdefault(
                exchange_key,
                {
                    "exchange": exchange_key,
                    "sessions": 0,
                    "equity": 0.0,
                    "positions": 0,
                    "open_orders": 0,
                    "trades": 0,
                    "gross_exposure": 0.0,
                    "unrealized_pnl": 0.0,
                },
            )
            bucket["sessions"] += 1
            bucket["equity"] += _safe_float(snapshot.equity, 0.0)
            bucket["positions"] += int(snapshot.positions_count or 0)
            bucket["open_orders"] += int(snapshot.open_orders_count or 0)
            bucket["trades"] += int(snapshot.trade_count or 0)
            bucket["gross_exposure"] += _session_gross_exposure(session, snapshot)
            bucket["unrealized_pnl"] += _session_unrealized_pnl(session)

        return {
            "session_count": len(session_list),
            "ready_sessions": ready_sessions,
            "running_sessions": running_sessions,
            "risk_blocked_sessions": risk_blocked_sessions,
            "total_equity": round(total_equity, 6),
            "total_positions": total_positions,
            "total_open_orders": total_open_orders,
            "total_trades": total_trades,
            "total_gross_exposure": round(total_gross_exposure, 6),
            "total_unrealized_pnl": round(total_unrealized_pnl, 6),
            "by_exchange": list(by_exchange.values()),
        }


class SessionManager:
    """Async-safe registry for isolated trading sessions."""

    def __init__(
        self,
        *,
        parent_controller: Any,
        logger: logging.Logger | None = None,
        session_factory: type[TradingSession] = TradingSession,
    ) -> None:
        self.parent_controller = parent_controller
        self.logger = logger or logging.getLogger("SessionManager")
        self.session_factory = session_factory
        self._sessions: dict[str, TradingSession] = {}
        self._lock = asyncio.Lock()
        self._counter = 0
        self.active_session_id: str | None = None
        self.portfolio_aggregator = PortfolioAggregator()

    async def create_session(self, config: Any) -> TradingSession:
        async with self._lock:
            session = self.session_factory(
                session_id=self._next_session_id(config),
                config=config,
                parent_controller=self.parent_controller,
                logger=self.logger,
                on_state_change=self._on_session_state_change,
            )
            self._sessions[session.session_id] = session
        try:
            await session.initialize()
        except Exception:
            async with self._lock:
                self._sessions.pop(session.session_id, None)
            try:
                await session.close()
            except Exception:
                self.logger.debug(
                    "Failed to close partially initialized session %s",
                    getattr(session, "session_id", None),
                    exc_info=True,
                )
            raise
        if self.active_session_id is None:
            self.active_session_id = session.session_id
        self.logger.info(
            "Created session id=%s exchange=%s type=%s mode=%s",
            session.session_id,
            session.exchange,
            session.broker_type,
            session.mode,
        )
        self._notify_controller_registry_change()
        return session

    async def activate_session(self, session_id: str) -> TradingSession:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        if not session.connected:
            await session.initialize()
        self.active_session_id = session.session_id
        self._notify_controller_registry_change()
        return session

    async def start_session(self, session_id: str) -> TradingSession:
        session = await self.activate_session(session_id)
        await session.start_trading()
        self._notify_controller_registry_change()
        return session

    async def stop_session(self, session_id: str) -> TradingSession | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        await session.stop_trading()
        self._notify_controller_registry_change()
        return session

    async def destroy_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        await session.close()
        if self.active_session_id == session_id:
            remaining = list(self._sessions.keys())
            self.active_session_id = remaining[0] if remaining else None
        self.logger.info("Destroyed session id=%s", session_id)
        self._notify_controller_registry_change()
        return True

    async def close_all(self) -> None:
        async with self._lock:
            session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.destroy_session(session_id)

    def get_session(self, session_id: str | None) -> TradingSession | None:
        if not session_id:
            return None
        return self._sessions.get(str(session_id))

    def get_active_session(self) -> TradingSession | None:
        return self.get_session(self.active_session_id)

    def list_sessions(self) -> list[TradingSession]:
        return list(self._sessions.values())

    def list_session_snapshots(self) -> list[dict[str, Any]]:
        snapshots = []
        for session in self.list_sessions():
            payload = session.snapshot().to_dict()
            payload["active"] = session.session_id == self.active_session_id
            snapshots.append(payload)
        snapshots.sort(key=lambda row: (not bool(row.get("active")), str(row.get("label") or "")))
        return snapshots

    def aggregate_portfolio(self) -> dict[str, Any]:
        return self.portfolio_aggregator.aggregate(self.list_sessions())

    async def route_order_to_best_session(self, symbol: str, side: str) -> dict[str, Any] | None:

     sessions = [
        s for s in self.list_sessions()
        if s.status in {"ready", "running"}
    ]

     if not sessions:
        return None

     quotes = await asyncio.gather(
        *(s.route_price(symbol, side) for s in sessions),
        return_exceptions=True,
    )

     candidates = []
     for quote, session in zip(quotes, sessions):
        if isinstance(quote, Exception) or quote is None:
            continue

        price = float(quote.get("price") or 0.0)

        # 🔥 Add scoring instead of pure price
        session_score = 1.0

        try:
            snapshot = session.snapshot()
            equity = float(getattr(snapshot, "equity", 1.0))
            exposure = float(getattr(snapshot, "gross_exposure", 0.0))
            exposure_ratio = exposure / equity if equity > 0 else 0

            # penalize high exposure
            session_score -= min(0.5, exposure_ratio)
        except Exception:
            pass

        candidates.append({
            "session": session,
            "price": price,
            "score": session_score,
            "raw": quote,
        })

     if not candidates:
        return None

    # 🔥 smart sort
     if side.lower() == "sell":
        candidates.sort(key=lambda x: (x["score"], x["price"]), reverse=True)
     else:
        candidates.sort(key=lambda x: (x["score"], -x["price"]), reverse=True)

     return candidates[0]["raw"]

    def _next_session_id(self, config: Any) -> str:
        broker_config = getattr(config, "broker", None)
        exchange = str(getattr(broker_config, "exchange", "session") or "session").strip().lower() or "session"
        mode = str(getattr(broker_config, "mode", "paper") or "paper").strip().lower() or "paper"
        self._counter += 1
        return f"{exchange}-{mode}-{self._counter:03d}"

    def _on_session_state_change(self, session: TradingSession) -> None:
        self.logger.debug(
            "Session state changed id=%s status=%s connected=%s autotrading=%s",
            session.session_id,
            session.status,
            session.connected,
            session.autotrading,
        )
        self._notify_controller_registry_change()

    def _notify_controller_registry_change(self) -> None:
        callback = getattr(self.parent_controller, "_handle_session_registry_changed", None)
        if callable(callback):
            callback()

    def global_risk_snapshot(self) -> dict[str, Any]:
     data = self.aggregate_portfolio()

     equity = data.get("total_equity", 0.0)
     exposure = data.get("total_gross_exposure", 0.0)

     exposure_ratio = (exposure / equity) if equity > 0 else 0.0

     return {
        "equity": equity,
        "gross_exposure": exposure,
        "exposure_ratio": exposure_ratio,
        "unrealized_pnl": data.get("total_unrealized_pnl", 0.0),
        "risk_blocked": exposure_ratio > 0.85,
    }

    def should_block_trade(self) -> tuple[bool, str]:

     snapshot = self.global_risk_snapshot()

     if snapshot["risk_blocked"]:
        return True, "Global exposure too high"

     if snapshot["unrealized_pnl"] < -0.05 * snapshot["equity"]:
        return True, "Global drawdown exceeded"

     return False, ""

    def record_trade_outcome(self, trade):

     if hasattr(self.parent_controller, "learning_engine"):
        self.parent_controller.learning_engine.record(
            trade.get("decision"),
            trade.get("pnl"),
        )
    def connection_health(self):

     stats = {
        "sessions": len(self._sessions),
        "active": self.active_session_id,
        "running": 0,
        "errors": 0,
    }

     for s in self.list_sessions():
        if s.status == "running":
            stats["running"] += 1
        if not s.connected:
            stats["errors"] += 1

     return stats