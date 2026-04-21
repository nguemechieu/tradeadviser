"""In-memory service container for the browser/server integration shell.

This server currently acts as an authoritative demo/runtime shell for:
- user registration and password reset
- REST authentication and desktop session bootstrap
- portfolio, positions, orders, trades, and signals
- admin overview and lightweight user management
- WebSocket event fanout for desktop/browser runtime updates

The implementation stays intentionally self-contained so the React frontend and
desktop client can share a stable contract while the broader platform is still
being migrated.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from secrets import token_hex
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_username(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _symbol_key(value: str) -> str:
    return str(value or "").strip().upper()


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "trader": [
        "trading",
        "auto_trading",
        "ml_signals",
        "multi_exchange",
        "portfolio_view",
    ],
    "admin": [
        "trading",
        "auto_trading",
        "ml_signals",
        "multi_exchange",
        "portfolio_view",
        "admin",
        "user_management",
        "agent_network",
        "server_control",
    ],
}


@dataclass(slots=True)
class ServerUser:
    user_id: str
    email: str
    username: str
    display_name: str
    password: str
    account_id: str
    role: str = "trader"
    is_active: bool = True
    permissions: list[str] = field(default_factory=list)
    starting_balance: float = 100_000.0
    cash_balance: float = 100_000.0
    created_at: datetime = field(default_factory=_utcnow)
    last_login_at: datetime | None = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.user_id,
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "display_name": self.display_name,
            "account_id": self.account_id,
            "role": self.role,
            "is_admin": self.role == "admin",
            "is_active": self.is_active,
            "permissions": list(self.permissions),
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "cash_balance": round(float(self.cash_balance or 0.0), 2),
            "starting_balance": round(float(self.starting_balance or 0.0), 2),
        }


@dataclass(slots=True)
class ServerSession:
    session_id: str
    user_id: str
    email: str
    account_id: str
    permissions: list[str] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=_utcnow)

    def as_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "user": {
                "user_id": self.user_id,
                "account_id": self.account_id,
                "permissions": list(self.permissions),
            },
        }


@dataclass(slots=True)
class TokenRecord:
    token: str
    user_id: str
    email: str
    expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(slots=True)
class PasswordResetRecord:
    token: str
    user_id: str
    email: str
    expires_at: datetime
    requested_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class ServerServiceContainer:
    users: dict[str, ServerUser] = field(default_factory=dict)
    users_by_id: dict[str, ServerUser] = field(default_factory=dict)
    tokens: dict[str, TokenRecord] = field(default_factory=dict)
    refresh_tokens: dict[str, TokenRecord] = field(default_factory=dict)
    password_reset_tokens: dict[str, PasswordResetRecord] = field(default_factory=dict)
    sessions: dict[str, ServerSession] = field(default_factory=dict)
    market_data_subscriptions: dict[str, dict[str, object]] = field(default_factory=dict)
    workspace_settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    orders_by_user: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    positions_by_user: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ws_connections: dict[str, set[Any]] = field(default_factory=dict)
    event_sequences: dict[str, int] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        if self.users:
            return
        self._seed_demo_state()

    async def authenticate_access(
        self,
        identifier: str,
        password: str,
        *,
        remember_me: bool = True,
    ) -> dict[str, Any]:
        user = self._resolve_user(identifier, password)
        user.last_login_at = _utcnow()
        expires_at = _utcnow() + timedelta(minutes=30)
        refresh_expires_at = _utcnow() + timedelta(days=30 if remember_me else 1)
        token = token_hex(24)
        refresh_token = token_hex(24)
        record = TokenRecord(
            token=token,
            user_id=user.user_id,
            email=user.email,
            expires_at=expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires_at,
        )
        self.tokens[token] = record
        self.refresh_tokens[refresh_token] = record
        return {
            "access_token": token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": max(1, int((expires_at - _utcnow()).total_seconds())),
            "expires_at": expires_at.isoformat(),
            "refresh_expires_at": refresh_expires_at.isoformat(),
            "user": user.as_public_dict(),
        }

    async def refresh_access(self, refresh_token: str) -> dict[str, Any]:
        record = self.refresh_tokens.get(str(refresh_token or "").strip())
        if record is None or record.refresh_expires_at <= _utcnow():
            raise ValueError("Refresh token is invalid or expired.")
        user = self.users.get(record.email)
        if user is None:
            raise ValueError("User no longer exists.")
        return await self.authenticate_access(user.email, user.password, remember_me=True)

    async def register_user(
        self,
        payload: dict[str, Any],
        *,
        role: str = "trader",
    ) -> dict[str, Any]:
        email = _normalize_email(payload.get("email") or payload.get("identifier"))
        password = str(payload.get("password") or "").strip()
        username = _normalize_username(payload.get("username") or email.split("@", 1)[0])
        display_name = str(payload.get("display_name") or payload.get("name") or username or "Trader").strip()

        if not email:
            raise ValueError("Email is required.")
        if "@" not in email:
            raise ValueError("Please provide a valid email address.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        if email in self.users:
            raise ValueError("An account with this email already exists.")

        normalized_role = "admin" if str(role or "").strip().lower() == "admin" else "trader"
        user = self._create_user_record(
            email=email,
            password=password,
            username=username,
            display_name=display_name,
            role=normalized_role,
            starting_balance=250_000.0 if normalized_role == "admin" else 100_000.0,
        )
        self._seed_workspace(user)
        self.record_signal(
            user,
            {
                "symbol": "WELCOME",
                "strategy": "Onboarding",
                "confidence": 1.0,
                "timeframe": "now",
                "message": "Account created successfully.",
            },
        )
        return {
            "user": user.as_public_dict(),
            "message": "Account created successfully.",
        }

    async def issue_reset_token(self, identifier: str) -> dict[str, Any]:
        user = self.find_user(identifier)
        if user is None:
            raise ValueError("No account matches that email or username.")
        token = token_hex(16)
        record = PasswordResetRecord(
            token=token,
            user_id=user.user_id,
            email=user.email,
            expires_at=_utcnow() + timedelta(minutes=15),
        )
        self.password_reset_tokens[token] = record
        return {
            "message": "Password reset token issued.",
            "reset_token": token,
            "expires_at": record.expires_at.isoformat(),
            "email": user.email,
        }

    async def reset_password(self, reset_token: str, new_password: str) -> dict[str, Any]:
        normalized_token = str(reset_token or "").strip()
        record = self.password_reset_tokens.get(normalized_token)
        if record is None or record.expires_at <= _utcnow():
            raise ValueError("Reset token is invalid or expired.")
        if len(str(new_password or "").strip()) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        user = self.users.get(record.email)
        if user is None:
            raise ValueError("User no longer exists.")
        user.password = str(new_password).strip()
        self.password_reset_tokens.pop(normalized_token, None)
        return {"message": "Password updated successfully.", "user": user.as_public_dict()}

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        user = self._resolve_user(username, password)
        user.last_login_at = _utcnow()
        session = ServerSession(
            session_id=f"session_{token_hex(8)}",
            user_id=user.user_id,
            email=user.email,
            account_id=user.account_id,
            permissions=list(user.permissions),
        )
        self.sessions[session.session_id] = session
        return self._success(session.as_payload(), "Session authenticated.")

    async def resume(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.get(str(session_id or "").strip())
        if session is None:
            return self._error("session_not_found", "Session not found or expired.")
        return self._success(session.as_payload(), "Session resumed.")

    async def register_connection(self, session_id: str, websocket: Any) -> None:
        normalized = str(session_id or "").strip()
        if not normalized:
            return
        async with self._lock:
            self.ws_connections.setdefault(normalized, set()).add(websocket)

    async def unregister_connection(self, session_id: str, websocket: Any) -> None:
        normalized = str(session_id or "").strip()
        if not normalized:
            return
        async with self._lock:
            connections = self.ws_connections.get(normalized)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self.ws_connections.pop(normalized, None)

    async def send_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any] | list[Any] | None = None,
        *,
        correlation_id: str | None = None,
    ) -> None:
        normalized = str(session_id or "").strip()
        if not normalized:
            return
        sequence = self._next_sequence(normalized)
        message = {
            "event_type": str(event_type or "").strip(),
            "session_id": normalized,
            "correlation_id": str(correlation_id or "").strip() or None,
            "sequence": sequence,
            "payload": payload or {},
        }
        connections = list(self.ws_connections.get(normalized, set()))
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                await self.unregister_connection(normalized, websocket)

    async def connect_broker(self, session_context: dict[str, Any], *, user: ServerUser | None = None) -> dict[str, Any]:
        actor = self._resolve_actor(session_context, user=user)
        context_payload = dict(session_context.get("session_context") or session_context)
        session_id = str(session_context.get("session_id") or context_payload.get("session_id") or "").strip()
        broker_payload = dict(session_context.get("broker") or context_payload.get("broker") or {})
        payload = {
            "user": actor.as_public_dict(),
            "session_id": session_id,
            "broker": broker_payload,
            "status": "connected",
        }
        if session_id:
            await self.send_event(
                session_id,
                "broker_status_updated",
                {
                    "status": "connected",
                    "summary": f"{str(broker_payload.get('broker') or 'broker').upper()} authority connected.",
                    "broker": broker_payload,
                },
            )
        return self._success(payload, "Broker registration accepted.")

    async def update_market_subscription(
        self,
        subscription: dict[str, Any],
        *,
        user: ServerUser | None = None,
    ) -> dict[str, Any]:
        actor = self._resolve_actor(subscription, user=user)
        session_id = str(subscription.get("session_id") or "").strip()
        data = {
            "user_id": actor.user_id,
            "symbols": list(subscription.get("symbols") or []),
            "timeframe": str(subscription.get("timeframe") or "1m").strip() or "1m",
            "include_candles": bool(subscription.get("include_candles", True)),
            "include_quotes": bool(subscription.get("include_quotes", True)),
        }
        self.market_data_subscriptions[session_id] = data
        if session_id:
            await self.send_event(session_id, "market_subscription_updated", dict(data))
        return self._success(dict(data), "Market data subscription updated.")

    async def place_order(self, command: dict[str, Any], *, user: ServerUser | None = None) -> dict[str, Any]:
        actor = self._resolve_actor(command, user=user)
        execution_request = dict(command.get("execution_request") or command)

        symbol = _symbol_key(
            ((execution_request.get("identifier") or {}).get("symbol"))
            or execution_request.get("symbol")
        )
        side = str(execution_request.get("side") or execution_request.get("order_side") or "buy").strip().lower()
        order_type = str(execution_request.get("type") or execution_request.get("order_type") or "market").strip().lower()
        amount = float(execution_request.get("amount") or execution_request.get("quantity") or 0.0)
        price = float(
            execution_request.get("limit_price")
            or execution_request.get("price")
            or execution_request.get("market_price")
            or 100.0
        )
        session_id = str(execution_request.get("session_id") or command.get("session_id") or "").strip()
        correlation_id = str(execution_request.get("correlation_id") or "").strip() or None

        if not symbol:
            raise ValueError("A symbol is required.")
        if side not in {"buy", "sell"}:
            raise ValueError("Trade side must be buy or sell.")
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        if price <= 0:
            raise ValueError("A valid price is required.")

        order_id = f"order_{token_hex(6)}"
        timestamp = _utcnow().isoformat()
        order = {
            "id": order_id,
            "order_id": order_id,
            "user_id": actor.user_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": round(amount, 8),
            "filled": 0.0,
            "remaining": round(amount, 8),
            "price": round(price, 6),
            "status": "open",
            "timestamp": timestamp,
            "source": str(execution_request.get("source") or "web").strip() or "web",
        }

        if order_type == "market":
            order["status"] = "filled"
            order["filled"] = round(amount, 8)
            order["remaining"] = 0.0
            order["average_fill_price"] = round(price, 6)
            self._apply_fill(
                actor,
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                order_id=order_id,
                order_type=order_type,
                source=order["source"],
            )

        self.orders_by_user.setdefault(actor.user_id, []).insert(0, dict(order))

        if session_id:
            await self.send_event(
                session_id,
                "order_updated",
                {
                    "order_id": order["order_id"],
                    "client_order_id": str(execution_request.get("client_order_id") or order["order_id"]),
                    "status": order["status"],
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                },
                correlation_id=correlation_id,
            )

        return self._success(dict(order), "Order accepted.")

    async def cancel_order(self, command: dict[str, Any], *, user: ServerUser | None = None) -> dict[str, Any]:
        actor = self._resolve_actor(command, user=user)
        order_id = str(command.get("order_id") or "").strip()
        if not order_id:
            raise ValueError("Order id is required.")

        updated = None
        for order in self.orders_by_user.get(actor.user_id, []):
            if str(order.get("order_id") or order.get("id") or "").strip() == order_id:
                if str(order.get("status") or "").lower() in {"filled", "canceled", "cancelled"}:
                    updated = dict(order)
                    break
                order["status"] = "canceled"
                order["remaining"] = float(order.get("remaining") or order.get("amount") or 0.0)
                order["updated_at"] = _utcnow().isoformat()
                updated = dict(order)
                break

        if updated is None:
            raise ValueError("Order not found.")

        session_id = str(command.get("session_id") or "").strip()
        if session_id:
            await self.send_event(session_id, "order_updated", dict(updated))
        return self._success(updated, "Cancel request accepted.")

    async def close_position(self, command: dict[str, Any], *, user: ServerUser | None = None) -> dict[str, Any]:
        actor = self._resolve_actor(command, user=user)
        symbol = _symbol_key(command.get("symbol") or command.get("position_id"))
        close_amount = float(command.get("amount") or 0.0)
        positions = self.positions_by_user.get(actor.user_id, [])
        target = None
        for position in positions:
            if _symbol_key(position.get("symbol")) == symbol:
                target = position
                break
        if target is None:
            raise ValueError("Position not found.")

        target_amount = float(target.get("amount") or 0.0)
        if target_amount <= 0:
            raise ValueError("Position is already closed.")
        if close_amount <= 0 or close_amount > target_amount:
            close_amount = target_amount

        price = float(target.get("mark_price") or target.get("entry_price") or 100.0)
        side = "sell" if str(target.get("side") or "long").lower() == "long" else "buy"
        trade = self._apply_fill(
            actor,
            symbol=symbol,
            side=side,
            amount=close_amount,
            price=price,
            order_id=f"close_{token_hex(5)}",
            order_type="market",
            source="close_position",
        )
        payload = {
            "position_id": target.get("position_id") or symbol,
            "status": "closed" if close_amount >= target_amount else "partially_closed",
            "symbol": symbol,
            "amount": close_amount,
            "trade": trade,
        }
        session_id = str(command.get("session_id") or "").strip()
        if session_id:
            await self.send_event(session_id, "position_updated", dict(payload))
        return self._success(payload, "Close position request accepted.")

    async def trigger_kill_switch(self, command: dict[str, Any], *, user: ServerUser | None = None) -> dict[str, Any]:
        actor = self._resolve_actor(command, user=user)
        canceled_orders = 0
        closed_positions = 0

        for order in self.orders_by_user.get(actor.user_id, []):
            if str(order.get("status") or "").lower() in {"open", "submitted", "accepted", "new"}:
                order["status"] = "canceled"
                order["updated_at"] = _utcnow().isoformat()
                canceled_orders += 1

        for position in list(self.positions_by_user.get(actor.user_id, [])):
            amount = float(position.get("amount") or 0.0)
            if amount <= 0:
                continue
            close_side = "sell" if str(position.get("side") or "long").lower() == "long" else "buy"
            price = float(position.get("mark_price") or position.get("entry_price") or 100.0)
            self._apply_fill(
                actor,
                symbol=_symbol_key(position.get("symbol")),
                side=close_side,
                amount=amount,
                price=price,
                order_id=f"kill_{token_hex(5)}",
                order_type="market",
                source="kill_switch",
            )
            closed_positions += 1

        payload = {
            "state": "engaged",
            "reason": str(command.get("reason") or "Emergency kill switch active").strip()
            or "Emergency kill switch active",
            "canceled_orders": canceled_orders,
            "closed_positions": closed_positions,
        }
        session_id = str(command.get("session_id") or "").strip()
        if session_id:
            await self.send_event(session_id, "broker_status_updated", {"status": "halted", **payload})
        return self._success(payload, "Kill switch engaged.")

    def resolve_token(self, token: str) -> ServerUser | None:
        """Resolve a token string to its associated user.
        
        Returns the ServerUser if token is valid and not expired.
        Returns None if token is missing, expired, or user no longer exists.
        
        Token Format: 48-character hexadecimal string (from secrets.token_hex(24))
        Lifetime: 30 minutes from creation
        """
        # Normalize the token
        normalized_token = str(token or "").strip()
        
        if not normalized_token:
            return None
        
        # Look up the token record
        record = self.tokens.get(normalized_token)
        
        if record is None:
            # Token doesn't exist (never issued or already expired/revoked)
            return None
        
        # Check if token has expired
        current_time = _utcnow()
        if record.expires_at <= current_time:
            # Token is expired, optionally clean it up
            self.tokens.pop(normalized_token, None)
            return None
        
        # Get the user associated with this token
        user = self.users_by_id.get(record.user_id)
        
        if user is None:
            # User no longer exists (deleted or ID mismatch)
            self.tokens.pop(normalized_token, None)
            return None
        
        # Everything is valid
        return user

    def resolve_session_user(self, session_id: str) -> ServerUser | None:
        session = self.sessions.get(str(session_id or "").strip())
        if session is None:
            return None
        return self.users_by_id.get(session.user_id)

    def find_user(self, identifier: str) -> ServerUser | None:
        normalized = _normalize_email(identifier)
        if normalized in self.users:
            return self.users[normalized]
        username = _normalize_username(identifier)
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def record_trade(self, user: ServerUser, payload: dict[str, Any]) -> dict[str, Any]:
        trade = {
            "id": f"trade_{token_hex(6)}",
            "trade_db_id": f"trade_{token_hex(5)}",
            "user_id": user.user_id,
            "symbol": _symbol_key(payload.get("symbol")),
            "side": str(payload.get("side") or "").strip().lower(),
            "size": round(float(payload.get("amount") or payload.get("size") or 0.0), 8),
            "amount": round(float(payload.get("amount") or payload.get("size") or 0.0), 8),
            "price": round(float(payload.get("price") or 0.0), 6),
            "pnl": round(float(payload.get("pnl") or 0.0), 2),
            "strategy_name": str(payload.get("strategy") or "Execution").strip() or "Execution",
            "source": str(payload.get("source") or "server").strip() or "server",
            "status": str(payload.get("status") or "filled").strip() or "filled",
            "order_id": str(payload.get("order_id") or "").strip(),
            "timestamp": str(payload.get("timestamp") or _utcnow().isoformat()).strip(),
        }
        self.trades.insert(0, trade)
        return trade

    def record_signal(self, user: ServerUser, payload: dict[str, Any]) -> dict[str, Any]:
        signal = {
            "id": f"signal_{token_hex(6)}",
            "user_id": user.user_id,
            "symbol": _symbol_key(payload.get("symbol")),
            "strategy": str(payload.get("strategy") or "Signal Engine").strip() or "Signal Engine",
            "confidence": float(payload.get("confidence") or 0.0),
            "timeframe": str(payload.get("timeframe") or "1h").strip() or "1h",
            "message": str(payload.get("message") or "").strip(),
            "timestamp": str(payload.get("timestamp") or _utcnow().isoformat()).strip(),
        }
        self.signals.insert(0, signal)
        return signal

    def performance(self, user: ServerUser) -> dict[str, Any]:
        rows = self.list_trades(user, limit=200)
        total_trades = len(rows)
        pnl = round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
        wins = sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0.0)
        win_rate = round((wins / total_trades), 4) if total_trades else 0.0

        strategy_stats: dict[str, dict[str, Any]] = {}
        for row in rows:
            strategy = str(row.get("strategy_name") or "Execution").strip() or "Execution"
            stats = strategy_stats.setdefault(
                strategy,
                {"total_trades": 0, "win_rate": 0.0, "pnl": 0.0, "avg_pnl": 0.0, "_wins": 0},
            )
            stats["total_trades"] += 1
            stats["pnl"] += float(row.get("pnl") or 0.0)
            if float(row.get("pnl") or 0.0) > 0.0:
                stats["_wins"] += 1

        for stats in strategy_stats.values():
            trade_count = int(stats["total_trades"] or 0)
            pnl_total = float(stats["pnl"] or 0.0)
            stats["avg_pnl"] = round((pnl_total / trade_count), 4) if trade_count else 0.0
            stats["win_rate"] = round((int(stats.pop("_wins", 0)) / trade_count), 4) if trade_count else 0.0
            stats["pnl"] = round(pnl_total, 2)

        return {
            "pnl": pnl,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "strategy_stats": strategy_stats,
            "summary": {
                "total_pnl": pnl,
                "win_rate": win_rate,
                "total_trades": total_trades,
            },
        }

    def get_workspace_settings(self, user: ServerUser) -> dict[str, Any]:
        payload = dict(self.workspace_settings.get(user.user_id, {}) or {})
        payload.setdefault("profile_name", f"{user.display_name} Workspace")
        payload.setdefault("desktop_sync_enabled", True)
        payload.setdefault("desktop_device_name", user.account_id)
        payload.setdefault("default_watchlist", ["EUR/USD", "BTC/USDT", "XAU/USD"])
        payload.setdefault("default_timeframe", "1h")
        return payload

    def save_workspace_settings(self, user: ServerUser, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.workspace_settings.get(user.user_id, {}) or {})
        merged.update(dict(payload or {}))
        merged["desktop_last_sync_at"] = _utcnow().isoformat()
        self.workspace_settings[user.user_id] = merged
        return dict(merged)

    def get_portfolio_dashboard(self, user: ServerUser) -> dict[str, Any]:
        positions = self.list_positions(user)
        active_orders = self.list_orders(user, active_only=True)
        trades = self.list_trades(user, limit=12)
        signals = self.list_signals(user, limit=8)
        summary = self._portfolio_summary(user)
        performance = self.performance(user)
        return {
            "user": user.as_public_dict(),
            "portfolio": summary,
            "performance": performance["summary"],
            "positions": positions,
            "open_orders": active_orders,
            "recent_trades": trades,
            "recent_signals": signals,
        }

    def list_positions(self, user: ServerUser) -> list[dict[str, Any]]:
        positions = []
        for raw in list(self.positions_by_user.get(user.user_id, []) or []):
            item = dict(raw)
            entry = float(item.get("entry_price") or 0.0)
            mark = float(item.get("mark_price") or entry or 0.0)
            quantity = float(item.get("quantity") or item.get("amount") or 0.0)
            if quantity <= 0:
                continue
            side = str(item.get("side") or "long").lower()
            direction = 1.0 if side == "long" else -1.0
            pnl = (mark - entry) * quantity * direction
            item["amount"] = round(quantity, 8)
            item["quantity"] = round(quantity, 8)
            item["value"] = round(mark * quantity, 2)
            item["pnl"] = round(pnl, 2)
            positions.append(item)
        return positions

    def list_orders(self, user: ServerUser, *, active_only: bool = False) -> list[dict[str, Any]]:
        rows = [dict(order) for order in list(self.orders_by_user.get(user.user_id, []) or [])]
        if active_only:
            rows = [
                row
                for row in rows
                if str(row.get("status") or "").lower() in {"open", "submitted", "accepted", "new"}
            ]
        return rows

    def list_trades(self, user: ServerUser, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.trades if row.get("user_id") == user.user_id]
        return rows[: max(1, int(limit or 100))]

    def list_signals(self, user: ServerUser, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.signals if row.get("user_id") == user.user_id]
        return rows[: max(1, int(limit or 100))]

    def admin_overview(self, admin_user: ServerUser) -> dict[str, Any]:
        self._require_admin(admin_user)
        open_positions = sum(len(self.list_positions(user)) for user in self.users_by_id.values())
        open_orders = sum(len(self.list_orders(user, active_only=True)) for user in self.users_by_id.values())
        active_sessions = sum(1 for session in self.sessions.values() if session.status == "active")
        return {
            "summary": {
                "users": len(self.users_by_id),
                "active_users": sum(1 for user in self.users_by_id.values() if user.is_active),
                "admin_users": sum(1 for user in self.users_by_id.values() if user.role == "admin"),
                "active_sessions": active_sessions,
                "trades": len(self.trades),
                "signals": len(self.signals),
                "open_positions": open_positions,
                "open_orders": open_orders,
                "reset_requests": len(self.password_reset_tokens),
            },
            "recent_users": [user.as_public_dict() for user in list(self.users_by_id.values())[:8]],
        }

    def admin_list_users(self, admin_user: ServerUser) -> list[dict[str, Any]]:
        self._require_admin(admin_user)
        rows = []
        for user in self.users_by_id.values():
            summary = self._portfolio_summary(user)
            rows.append(
                {
                    **user.as_public_dict(),
                    "portfolio": summary,
                    "positions": len(self.list_positions(user)),
                    "open_orders": len(self.list_orders(user, active_only=True)),
                    "trades": len(self.list_trades(user, limit=500)),
                }
            )
        rows.sort(key=lambda item: (item["role"] != "admin", item["email"]))
        return rows

    async def admin_create_user(self, admin_user: ServerUser, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_admin(admin_user)
        role = str(payload.get("role") or "trader").strip().lower()
        return await self.register_user(payload, role=role)

    def admin_update_user_status(self, admin_user: ServerUser, user_id: str, is_active: bool) -> dict[str, Any]:
        self._require_admin(admin_user)
        target = self.users_by_id.get(str(user_id or "").strip())
        if target is None:
            raise ValueError("User not found.")
        target.is_active = bool(is_active)
        return target.as_public_dict()

    def admin_update_user_role(self, admin_user: ServerUser, user_id: str, role: str) -> dict[str, Any]:
        self._require_admin(admin_user)
        target = self.users_by_id.get(str(user_id or "").strip())
        if target is None:
            raise ValueError("User not found.")
        normalized_role = str(role or "").strip().lower()
        if normalized_role not in ROLE_PERMISSIONS:
            raise ValueError("Unsupported role.")
        target.role = normalized_role
        target.permissions = list(ROLE_PERMISSIONS[normalized_role])
        return target.as_public_dict()

    def health_snapshot(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "SQS Server",
            "users": len(self.users_by_id),
            "sessions": len(self.sessions),
            "tokens": len(self.tokens),
            "password_resets": len(self.password_reset_tokens),
            "trades": len(self.trades),
            "signals": len(self.signals),
            "open_orders": sum(len(rows) for rows in self.orders_by_user.values()),
            "open_positions": sum(len(rows) for rows in self.positions_by_user.values()),
        }

    def _seed_demo_state(self) -> None:
        seeded_users = [
            self._create_user_record(
                email="operator@sopotek.local",
                password="changeme",
                username="operator",
                display_name="Sopotek Operator",
                role="trader",
                starting_balance=120_000.0,
            ),
            self._create_user_record(
                email="trader@sopotek.local",
                password="changeme",
                username="trader",
                display_name="Desk Trader",
                role="trader",
                starting_balance=95_000.0,
            ),
            self._create_user_record(
                email="admin@sopotek.local",
                password="admin123",
                username="admin",
                display_name="Desk Administrator",
                role="admin",
                starting_balance=250_000.0,
            ),
        ]

        for user in seeded_users:
            self._seed_workspace(user)

        operator = self.find_user("operator@sopotek.local")
        trader = self.find_user("trader@sopotek.local")
        admin = self.find_user("admin@sopotek.local")
        if operator is not None:
            self._seed_positions(
                operator,
                [
                    {"symbol": "EUR/USD", "side": "long", "quantity": 1800, "entry_price": 1.0825, "mark_price": 1.0862},
                    {"symbol": "BTC/USDT", "side": "long", "quantity": 0.45, "entry_price": 64250, "mark_price": 65140},
                ],
            )
            self._seed_orders(
                operator,
                [
                    {"symbol": "XAU/USD", "side": "buy", "type": "limit", "amount": 2, "price": 2342.5, "status": "open"},
                ],
            )
            self.record_trade(
                operator,
                {"symbol": "EUR/USD", "side": "buy", "amount": 1800, "price": 1.0825, "pnl": 0.0, "strategy": "Momentum", "source": "seed"},
            )
            self.record_trade(
                operator,
                {"symbol": "BTC/USDT", "side": "buy", "amount": 0.45, "price": 64250, "pnl": 420.5, "strategy": "Breakout", "source": "seed"},
            )
            self.record_signal(
                operator,
                {"symbol": "XAU/USD", "strategy": "Macro Overlay", "confidence": 0.74, "timeframe": "4h", "message": "Gold breakout setup forming."},
            )

        if trader is not None:
            self._seed_positions(
                trader,
                [
                    {"symbol": "AAPL", "side": "long", "quantity": 60, "entry_price": 197.4, "mark_price": 201.1},
                ],
            )
            self._seed_orders(
                trader,
                [
                    {"symbol": "NVDA", "side": "buy", "type": "limit", "amount": 15, "price": 882.0, "status": "open"},
                ],
            )
            self.record_trade(
                trader,
                {"symbol": "AAPL", "side": "buy", "amount": 60, "price": 197.4, "pnl": 135.0, "strategy": "Trend Following", "source": "seed"},
            )
            self.record_signal(
                trader,
                {"symbol": "NVDA", "strategy": "AI Momentum", "confidence": 0.81, "timeframe": "1d", "message": "Watch for continuation above 890."},
            )

        if admin is not None:
            self.record_signal(
                admin,
                {"symbol": "DESK", "strategy": "Admin Pulse", "confidence": 1.0, "timeframe": "live", "message": "Admin dashboard seeded successfully."},
            )

    def _seed_workspace(self, user: ServerUser) -> None:
        self.workspace_settings[user.user_id] = {
            "profile_name": f"{user.display_name} Workspace",
            "desktop_sync_enabled": True,
            "desktop_device_name": user.account_id,
            "default_watchlist": ["EUR/USD", "BTC/USDT", "XAU/USD"],
            "default_timeframe": "1h",
            "theme": "midnight",
            "risk_mode": "balanced" if user.role != "admin" else "oversight",
        }

    def _seed_positions(self, user: ServerUser, rows: list[dict[str, Any]]) -> None:
        normalized_rows = []
        for row in rows:
            normalized_rows.append(
                {
                    "position_id": f"pos_{token_hex(5)}",
                    "user_id": user.user_id,
                    "symbol": _symbol_key(row.get("symbol")),
                    "side": str(row.get("side") or "long").strip().lower(),
                    "quantity": round(float(row.get("quantity") or row.get("amount") or 0.0), 8),
                    "amount": round(float(row.get("quantity") or row.get("amount") or 0.0), 8),
                    "entry_price": round(float(row.get("entry_price") or 0.0), 6),
                    "mark_price": round(float(row.get("mark_price") or row.get("entry_price") or 0.0), 6),
                    "opened_at": _utcnow().isoformat(),
                }
            )
        self.positions_by_user[user.user_id] = normalized_rows

    def _seed_orders(self, user: ServerUser, rows: list[dict[str, Any]]) -> None:
        normalized_rows = []
        for row in rows:
            amount = round(float(row.get("amount") or 0.0), 8)
            normalized_rows.append(
                {
                    "id": f"order_{token_hex(5)}",
                    "order_id": f"order_{token_hex(5)}",
                    "user_id": user.user_id,
                    "symbol": _symbol_key(row.get("symbol")),
                    "side": str(row.get("side") or "buy").strip().lower(),
                    "type": str(row.get("type") or "limit").strip().lower(),
                    "amount": amount,
                    "filled": float(row.get("filled") or 0.0),
                    "remaining": max(0.0, amount - float(row.get("filled") or 0.0)),
                    "price": round(float(row.get("price") or 0.0), 6),
                    "status": str(row.get("status") or "open").strip().lower(),
                    "timestamp": _utcnow().isoformat(),
                    "source": "seed",
                }
            )
        self.orders_by_user[user.user_id] = normalized_rows

    def _resolve_user(self, identifier: str, password: str) -> ServerUser:
        user = self.find_user(identifier)
        if user is None:
            raise ValueError("Invalid credentials.")
        if not user.is_active:
            raise ValueError("This account has been deactivated.")
        if user.password != str(password or ""):
            raise ValueError("Invalid credentials.")
        return user

    def _resolve_actor(self, payload: dict[str, Any], *, user: ServerUser | None = None) -> ServerUser:
        if user is not None:
            return user
        session_id = str(payload.get("session_id") or (payload.get("execution_request") or {}).get("session_id") or "").strip()
        if session_id:
            session_user = self.resolve_session_user(session_id)
            if session_user is not None:
                return session_user
        raise ValueError("Authenticated user or active session is required.")

    def _portfolio_summary(self, user: ServerUser) -> dict[str, Any]:
        positions = self.list_positions(user)
        orders = self.list_orders(user, active_only=True)
        performance = self.performance(user)["summary"]
        long_value = sum(float(row.get("value") or 0.0) for row in positions if str(row.get("side") or "").lower() == "long")
        short_value = sum(float(row.get("value") or 0.0) for row in positions if str(row.get("side") or "").lower() == "short")
        equity = float(user.cash_balance or 0.0) + long_value - short_value
        unrealized_pnl = sum(float(row.get("pnl") or 0.0) for row in positions)
        return {
            "cash_balance": round(float(user.cash_balance or 0.0), 2),
            "equity": round(equity, 2),
            "starting_balance": round(float(user.starting_balance or 0.0), 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(float(performance.get("total_pnl") or 0.0), 2),
            "open_positions": len(positions),
            "open_orders": len(orders),
            "exposure": round(long_value + short_value, 2),
            "long_exposure": round(long_value, 2),
            "short_exposure": round(short_value, 2),
            "win_rate": float(performance.get("win_rate") or 0.0),
            "total_trades": int(performance.get("total_trades") or 0),
        }

    def _apply_fill(
        self,
        user: ServerUser,
        *,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        order_id: str,
        order_type: str,
        source: str,
    ) -> dict[str, Any]:
        signed_trade_qty = amount if side == "buy" else -amount
        user.cash_balance += (-price * amount) if side == "buy" else (price * amount)

        positions = self.positions_by_user.setdefault(user.user_id, [])
        target = None
        for position in positions:
            if _symbol_key(position.get("symbol")) == symbol:
                target = position
                break

        realized_pnl = 0.0
        current_qty = 0.0
        entry_price = price
        if target is not None:
            current_qty = float(target.get("quantity") or target.get("amount") or 0.0)
            if str(target.get("side") or "long").lower() == "short":
                current_qty *= -1.0
            entry_price = float(target.get("entry_price") or price)

        new_qty = current_qty + signed_trade_qty
        if current_qty != 0.0 and (current_qty > 0 > signed_trade_qty or current_qty < 0 < signed_trade_qty):
            closing_qty = min(abs(current_qty), abs(signed_trade_qty))
            if current_qty > 0:
                realized_pnl = (price - entry_price) * closing_qty
            else:
                realized_pnl = (entry_price - price) * closing_qty

        if target is None and new_qty != 0.0:
            target = {
                "position_id": f"pos_{token_hex(5)}",
                "user_id": user.user_id,
                "symbol": symbol,
                "side": "long" if new_qty > 0 else "short",
                "quantity": abs(new_qty),
                "amount": abs(new_qty),
                "entry_price": round(price, 6),
                "mark_price": round(price, 6),
                "opened_at": _utcnow().isoformat(),
            }
            positions.insert(0, target)
        elif target is not None:
            if new_qty == 0.0:
                positions.remove(target)
            else:
                old_abs = abs(current_qty)
                new_abs = abs(new_qty)
                if current_qty == 0 or (current_qty > 0 and signed_trade_qty > 0) or (current_qty < 0 and signed_trade_qty < 0):
                    weighted_entry = (
                        ((entry_price * old_abs) + (price * abs(signed_trade_qty))) / new_abs if new_abs else price
                    )
                elif abs(signed_trade_qty) > old_abs:
                    weighted_entry = price
                else:
                    weighted_entry = entry_price

                target["side"] = "long" if new_qty > 0 else "short"
                target["quantity"] = round(new_abs, 8)
                target["amount"] = round(new_abs, 8)
                target["entry_price"] = round(weighted_entry, 6)
                target["mark_price"] = round(price, 6)
                target["updated_at"] = _utcnow().isoformat()

        trade = self.record_trade(
            user,
            {
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "pnl": realized_pnl,
                "strategy": "Manual Execution" if source == "web" else "Execution",
                "source": source,
                "status": "filled",
                "order_id": order_id,
            },
        )
        return trade

    def _create_user_record(
        self,
        *,
        email: str,
        password: str,
        username: str,
        display_name: str,
        role: str,
        starting_balance: float,
    ) -> ServerUser:
        normalized_role = str(role or "trader").strip().lower()
        permissions = list(ROLE_PERMISSIONS.get(normalized_role, ROLE_PERMISSIONS["trader"]))
        normalized_email = _normalize_email(email)
        normalized_username = _normalize_username(username or normalized_email.split("@", 1)[0])
        user = ServerUser(
            user_id=f"user_{token_hex(6)}",
            email=normalized_email,
            username=normalized_username,
            display_name=str(display_name or normalized_username or "Trader").strip(),
            password=str(password),
            account_id=f"acct_{token_hex(4)}",
            role=normalized_role,
            permissions=permissions,
            starting_balance=float(starting_balance),
            cash_balance=float(starting_balance),
        )
        self.users[normalized_email] = user
        self.users_by_id[user.user_id] = user
        return user

    def _require_admin(self, user: ServerUser) -> None:
        if user.role != "admin":
            raise ValueError("Administrator access is required.")

    async def update_user_profile(
        self,
        user: ServerUser,
        payload: dict[str, Any],
    ) -> ServerUser:
        """Update user profile fields."""
        user.first_name = str(payload.get("first_name") or user.first_name or "").strip()
        user.last_name = str(payload.get("last_name") or user.last_name or "").strip()
        user.display_name = str(payload.get("display_name") or user.display_name or "").strip()
        # Email update would require more validation in a real app
        return user

    async def save_broker_config(
        self,
        user: ServerUser,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Save broker configuration for user."""
        config_name = str(payload.get("name") or "").strip()
        if not config_name:
            raise ValueError("Configuration name is required.")
        
        # Store in user's workspace settings
        if "broker_configs" not in self.workspace_settings:
            self.workspace_settings["broker_configs"] = {}
        
        self.workspace_settings["broker_configs"][f"{user.user_id}_{config_name}"] = {
            "name": config_name,
            "broker": str(payload.get("broker") or "").strip(),
            "config": dict(payload.get("config") or {}),
            "description": str(payload.get("description") or "").strip(),
        }
        
        return {
            "profile_id": user.user_id,
            "message": f"Configuration '{config_name}' saved successfully"
        }

    async def get_broker_config(
        self,
        user: ServerUser,
        name: str,
    ) -> dict[str, Any]:
        """Retrieve broker configuration by name."""
        config_key = f"{user.user_id}_{name}"
        if "broker_configs" not in self.workspace_settings or config_key not in self.workspace_settings["broker_configs"]:
            raise ValueError(f"Configuration '{name}' not found.")
        
        return self.workspace_settings["broker_configs"][config_key]

    async def list_broker_configs(
        self,
        user: ServerUser,
    ) -> list[dict[str, Any]]:
        """List all broker configurations for user."""
        if "broker_configs" not in self.workspace_settings:
            return []
        
        configs = []
        prefix = f"{user.user_id}_"
        for key, config in self.workspace_settings["broker_configs"].items():
            if key.startswith(prefix):
                configs.append(config)
        
        return configs

    async def delete_broker_config(
        self,
        user: ServerUser,
        name: str,
    ) -> None:
        """Delete broker configuration."""
        config_key = f"{user.user_id}_{name}"
        if "broker_configs" not in self.workspace_settings or config_key not in self.workspace_settings["broker_configs"]:
            raise ValueError(f"Configuration '{name}' not found.")
        
        self.workspace_settings["broker_configs"].pop(config_key, None)

    async def test_broker_connection(
        self,
        user: ServerUser,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Test broker connection (mock implementation)."""
        broker = str(payload.get("broker") or "").strip()
        if not broker:
            raise ValueError("Broker name is required.")
        
        # In a real implementation, this would test actual connection
        return {
            "success": True,
            "message": f"Connected to {broker} successfully"
        }

    def _next_sequence(self, session_id: str) -> int:
        current = int(self.event_sequences.get(session_id, 0) or 0) + 1
        self.event_sequences[session_id] = current
        return current

    @staticmethod
    def _success(data: Any, message: str) -> dict[str, Any]:
        return {"success": True, "data": data, "message": str(message or "").strip()}

    @staticmethod
    def _error(code: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "data": None,
            "message": "",
            "error": {"code": str(code or "error"), "message": str(message or "Request failed").strip()},
        }


_services = ServerServiceContainer()


def get_services() -> ServerServiceContainer:
    """Get the global service container instance."""
    return _services


# ==================== FastAPI Database & Auth Dependencies ====================

from app.backend.db.session import get_db_session
from app.backend.schemas import UserSchema
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated


async def get_db() -> AsyncSession:
    """Dependency to get database session for route handlers.
    
    Usage in route:
        async def get_items(db: AsyncSession = Depends(get_db)):
            pass
    """
    async for session in get_db_session():
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Dependency to get current authenticated user.
    
    Validates Bearer token and returns user information.
    
    Usage in route:
        async def get_profile(current_user: UserSchema = Depends(get_current_user)):
            pass
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse Bearer token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # For demo: use in-memory service container to validate token
    # In production: validate JWT properly
    services = get_services()
    user = services.resolve_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return UserSchema(
        user_id=user.user_id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        permissions=list(user.permissions) if hasattr(user, 'permissions') else [],
    )


# ==================== Database Dependencies ====================

from app.backend.db.session import get_db_session
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session as SyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated


async def get_db() -> AsyncSession:
    """Dependency to get database session for route handlers.
    
    Usage in route:
        async def get_items(db: Session = Depends(get_db)):
            pass
    """
    async for session in get_db_session():
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Dependency to get current authenticated user.
    
    Validates Bearer token and returns user information.
    
    Usage in route:
        async def get_profile(current_user = Depends(get_current_user)):
            pass
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse Bearer token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # For demo: use in-memory service container to validate token
    # In production: validate JWT properly
    services = get_services()
    user = services.resolve_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": user.user_id,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": list(user.permissions),
    }
    """Return the singleton service container for the application shell."""
    return _services
