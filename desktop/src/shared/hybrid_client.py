from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import websockets


def _normalize_base_url(value: str | None) -> str:
    text = str(value or "").strip().rstrip("/")
    return text


def _ws_url_from_base(base_url: str | None, path: str = "/ws/events") -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@dataclass(slots=True)
class HybridSession:
    session_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    user_id: str = ""
    email: str = ""
    broker: str = ""
    account_id: str = ""
    status: str = "disconnected"
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def authenticated(self) -> bool:
        return bool(self.access_token)

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= float(self.expires_at)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "HybridSession":
        data = dict(payload or {})
        session = data.get("session")
        if isinstance(session, dict):
            data = {**data, **session}

        token = (
                data.get("access_token")
                or data.get("token")
                or data.get("jwt")
                or ""
        )

        return cls(
            session_id=str(data.get("session_id") or data.get("id") or "").strip(),
            access_token=str(token or "").strip(),
            refresh_token=str(data.get("refresh_token") or "").strip(),
            user_id=str(data.get("user_id") or data.get("user") or "").strip(),
            email=str(data.get("email") or "").strip(),
            broker=str(data.get("broker") or data.get("exchange") or "").strip().lower(),
            account_id=str(data.get("account_id") or "").strip(),
            status=str(data.get("status") or "connected").strip().lower(),
            expires_at=_safe_float_or_none(data.get("expires_at")),
            metadata=dict(data.get("metadata") or {}),
        )

    def auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}


def _safe_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


class HybridApiClient:
    """Async HTTP client for TradeAdviser hybrid/server mode."""

    def __init__(
            self,
            base_url: str,
            *,
            email: str = "",
            password: str = "",
            token: str = "",
            timeout_seconds: float = 15.0,
            logger: logging.Logger | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.email = str(email or "").strip()
        self.password = str(password or "")
        self.token = str(token or "").strip()
        self.timeout_seconds = max(2.0, float(timeout_seconds or 15.0))
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._session: aiohttp.ClientSession | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def __aenter__(self) -> "HybridApiClient":
        await self.open()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.close()

    async def open(self) -> None:
        if self._session is not None and not self._session.closed:
            return

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None and not session.closed:
            await session.close()

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", "/health", auth=False)

    async def login(self, email: str | None = None, password: str | None = None) -> HybridSession:
        payload = {
            "email": str(email if email is not None else self.email).strip(),
            "password": str(password if password is not None else self.password),
        }

        # Supports either common route. First try /auth/login, then /login.
        try:
            data = await self.request("POST", "/auth/login", json_data=payload, auth=False)
        except Exception:
            data = await self.request("POST", "/login", json_data=payload, auth=False)

        session = HybridSession.from_payload(data)
        if session.access_token:
            self.token = session.access_token
        return session

    async def refresh(self, refresh_token: str) -> HybridSession:
        data = await self.request(
            "POST",
            "/auth/refresh",
            json_data={"refresh_token": refresh_token},
            auth=False,
        )
        session = HybridSession.from_payload(data)
        if session.access_token:
            self.token = session.access_token
        return session

    async def register_broker_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/runtime/broker-session", json_data=dict(payload or {}))

    async def request_market_data_subscription(
            self,
            *,
            symbols: list[str],
            timeframe: str = "1h",
            session_id: str = "",
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/runtime/market-data/subscribe",
            json_data={
                "symbols": list(symbols or []),
                "timeframe": str(timeframe or "1h"),
                "session_id": str(session_id or ""),
            },
        )

    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/orders", json_data=dict(payload or {}))

    async def cancel_order(self, order_id: str, *, session_id: str = "") -> dict[str, Any]:
        return await self.request(
            "POST",
            f"/orders/{order_id}/cancel",
            json_data={"session_id": str(session_id or "")},
        )

    async def close_position(self, position_id: str, *, session_id: str = "") -> dict[str, Any]:
        return await self.request(
            "POST",
            f"/positions/{position_id}/close",
            json_data={"session_id": str(session_id or "")},
        )

    async def trigger_kill_switch(self, reason: str, *, session_id: str = "") -> dict[str, Any]:
        return await self.request(
            "POST",
            "/risk/kill-switch",
            json_data={
                "reason": str(reason or "Manual kill switch"),
                "session_id": str(session_id or ""),
            },
        )

    async def request(
            self,
            method: str,
            path: str,
            *,
            json_data: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
            auth: bool = True,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Hybrid API base_url is not configured.")

        await self.open()

        assert self._session is not None

        endpoint = path if str(path).startswith("http") else f"{self.base_url}/{str(path).lstrip('/')}"
        headers = {"Accept": "application/json"}

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with self._session.request(
                str(method or "GET").upper(),
                endpoint,
                json=json_data,
                params=params,
                headers=headers,
        ) as response:
            text = await response.text()

            try:
                payload = json.loads(text) if text else {}
            except Exception:
                payload = {"raw": text}

            if response.status >= 400:
                raise RuntimeError(f"Hybrid API {response.status} {endpoint}: {payload}")

            if isinstance(payload, dict):
                return payload

            return {"data": payload}


class HybridWsClient:
    """WebSocket client for TradeAdviser hybrid/server events."""

    def __init__(
            self,
            ws_url: str,
            *,
            token: str = "",
            event_callback: Callable[[dict[str, Any]], Any] | None = None,
            logger: logging.Logger | None = None,
            reconnect_delay: float = 3.0,
            max_reconnect_delay: float = 30.0,
    ) -> None:
        self.ws_url = str(ws_url or "").strip()
        self.token = str(token or "").strip()
        self.event_callback = event_callback
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.reconnect_delay = max(0.5, float(reconnect_delay or 3.0))
        self.max_reconnect_delay = max(self.reconnect_delay, float(max_reconnect_delay or 30.0))
        self.running = False
        self._task: asyncio.Task[Any] | None = None
        self._ws: Any = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and self.running

    def start(self) -> asyncio.Task[Any]:
        if self._task is not None and not self._task.done():
            return self._task

        loop = asyncio.get_running_loop()
        self.running = True
        self._task = loop.create_task(self.run(), name="HybridWsClient.run")
        return self._task

    async def stop(self) -> None:
        self.running = False

        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("Hybrid WebSocket is not connected.")
        await self._ws.send(json.dumps(dict(payload or {}), default=str))

    async def run(self) -> None:
        if not self.ws_url:
            raise RuntimeError("Hybrid WebSocket URL is not configured.")

        delay = self.reconnect_delay

        while self.running:
            try:
                await self._connect_once()
                delay = self.reconnect_delay

            except asyncio.CancelledError:
                self.running = False
                raise

            except Exception as exc:
                self.logger.warning("Hybrid WebSocket disconnected: %s", exc)

                if not self.running:
                    break

                await asyncio.sleep(delay)
                delay = min(self.max_reconnect_delay, delay * 1.5)

    async def _connect_once(self) -> None:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with websockets.connect(
                self.ws_url,
                additional_headers=headers or None,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
        ) as ws:
            self._ws = ws
            self.logger.info("Hybrid WebSocket connected: %s", self.ws_url)

            while self.running:
                raw = await ws.recv()

                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {"type": "raw", "data": raw}

                callback = self.event_callback
                if callable(callback):
                    await _maybe_await(callback(payload))


class HybridSessionController:
    """High-level coordinator for hybrid API + WebSocket runtime."""

    def __init__(
            self,
            api_client: HybridApiClient | None = None,
            ws_client: HybridWsClient | None = None,
            *,
            logger: logging.Logger | None = None,
    ) -> None:
        self.api_client = api_client
        self.ws_client = ws_client
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.event_callback: Callable[[dict[str, Any]], Any] | None = None
        self.session = HybridSession()

    @property
    def connected(self) -> bool:
        return bool(self.session.authenticated and not self.session.expired)

    async def connect(
            self,
            profile: dict[str, Any] | None = None,
            *,
            interactive: bool = False,
    ) -> HybridSession | None:
        active_profile = dict(profile or {})
        base_url = _normalize_base_url(active_profile.get("base_url") or active_profile.get("api_url"))
        email = str(active_profile.get("email") or "").strip()
        password = str(active_profile.get("password") or "")
        token = str(active_profile.get("token") or active_profile.get("access_token") or "").strip()

        if self.api_client is None:
            self.api_client = HybridApiClient(
                base_url,
                email=email,
                password=password,
                token=token,
                logger=self.logger,
            )

        if token:
            self.api_client.token = token
            self.session = HybridSession.from_payload(
                {
                    "access_token": token,
                    "email": email,
                    "status": "connected",
                }
            )
        else:
            self.session = await self.api_client.login(email=email, password=password)

        ws_url = str(active_profile.get("ws_url") or "").strip() or _ws_url_from_base(base_url)

        if ws_url:
            self.ws_client = HybridWsClient(
                ws_url,
                token=self.session.access_token,
                event_callback=self._handle_ws_event,
                logger=self.logger,
            )
            self.ws_client.start()

        return self.session

    async def start(self, profile: dict[str, Any] | None = None, *, interactive: bool = False) -> HybridSession | None:
        return await self.connect(profile=profile, interactive=interactive)

    async def login(self, profile: dict[str, Any] | None = None, *, interactive: bool = False) -> HybridSession | None:
        return await self.connect(profile=profile, interactive=interactive)

    async def close(self) -> None:
        if self.ws_client is not None:
            await self.ws_client.stop()
            self.ws_client = None

        if self.api_client is not None:
            await self.api_client.close()

        self.session = HybridSession(status="disconnected")

    async def _handle_ws_event(self, payload: dict[str, Any]) -> None:
        callback = self.event_callback
        if callable(callback):
            await _maybe_await(callback(payload))

    async def register_broker_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")
        return await self.api_client.register_broker_session(payload)

    async def request_market_data_subscription(
            self,
            *,
            symbols: list[str],
            timeframe: str = "1h",
    ) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")
        return await self.api_client.request_market_data_subscription(
            symbols=symbols,
            timeframe=timeframe,
            session_id=self.session.session_id,
        )

    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")

        enriched = dict(payload or {})
        enriched.setdefault("session_id", self.session.session_id)
        return await self.api_client.place_order(enriched)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")
        return await self.api_client.cancel_order(order_id, session_id=self.session.session_id)

    async def close_position(self, position_id: str) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")
        return await self.api_client.close_position(position_id, session_id=self.session.session_id)

    async def trigger_kill_switch(self, reason: str) -> dict[str, Any]:
        if self.api_client is None:
            raise RuntimeError("Hybrid API client is not connected.")
        return await self.api_client.trigger_kill_switch(reason, session_id=self.session.session_id)


__all__ = [
    "HybridApiClient",
    "HybridSession",
    "HybridSessionController",
    "HybridWsClient",
]