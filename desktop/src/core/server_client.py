from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradeAdviserClientError(RuntimeError):
    """Raised when desktop-to-TradeAdviser communication fails."""


class TradeAdviserClient:
    def __init__(
        self,
        base_url: str,
        *,
        email: str = "",
        password: str = "",
        token: str | None = None,
        requestor=None,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.base_url = self._normalize_base_url(base_url)
        self.email = str(email or "").strip()
        self.password = str(password or "").strip()
        self.token = str(token or "").strip()
        self.requestor = requestor
        self.timeout_seconds = float(timeout_seconds)
        self.expires_at: datetime | None = None

    def configure(
        self,
        *,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> None:
        if base_url is not None:
            self.base_url = self._normalize_base_url(base_url)
        if email is not None:
            self.email = str(email or "").strip()
        if password is not None:
            self.password = str(password or "").strip()
        if token is not None:
            self.token = str(token or "").strip()

    def has_credentials(self) -> bool:
        return bool(self.base_url and self.email and self.password)

    def is_authenticated(self) -> bool:
        if not self.token:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at > (_utcnow() + timedelta(seconds=30))

    async def login(self, email: str | None = None, password: str | None = None) -> dict[str, Any]:
        identifier = str(email if email is not None else self.email).strip()
        secret = str(password if password is not None else self.password).strip()
        if not identifier or not secret:
            raise TradeAdviserClientError("TradeAdviser login requires both an email and password.")

        response = await self._request_json(
            "POST",
            "/auth/login",
            payload={"identifier": identifier, "password": secret},
            authenticated=False,
        )
        token = str(response.get("access_token") or "").strip()
        if not token:
            raise TradeAdviserClientError("TradeAdviser login did not return an access token.")

        self.email = identifier
        self.password = secret
        self.token = token

        expires_in = response.get("expires_in")
        try:
            self.expires_at = _utcnow() + timedelta(seconds=max(1, int(expires_in or 0)))
        except Exception:
            self.expires_at = None
        return response

    async def ensure_authenticated(self) -> None:
        if self.is_authenticated():
            return
        await self.login()

    async def send_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_authenticated()
        return await self._request_json("POST", "/trades", payload=dict(trade or {}))

    async def send_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_authenticated()
        return await self._request_json("POST", "/signals", payload=dict(signal or {}))

    async def get_performance(self) -> dict[str, Any]:
        await self.ensure_authenticated()
        return await self._request_json("GET", "/performance")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Desktop/TradeAdviserClient",
        }
        if authenticated:
            if not self.token:
                raise TradeAdviserClientError("TradeAdviser access token is missing.")
            headers["Authorization"] = f"Bearer {self.token}"

        url = f"{self.base_url}{path}"
        if self.requestor is not None:
            result = self.requestor(
                method=method.upper(),
                url=url,
                json_payload=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, dict):
                return result
            return {}

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method.upper(), url, json=payload, headers=headers) as response:
                    text = await response.text()
                    data: dict[str, Any] = {}
                    if text:
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict):
                                data = parsed
                        except json.JSONDecodeError:
                            data = {}
                    if response.status >= 400:
                        detail = str(data.get("detail") or text or response.reason or "Request failed").strip()
                        raise TradeAdviserClientError(f"{response.status}: {detail}")
                    return data
        except aiohttp.ClientError as exc:
            raise TradeAdviserClientError(f"Unable to reach TradeAdviser Server: {exc}") from exc

    @staticmethod
    def _normalize_base_url(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "://" not in text:
            text = f"http://{text}"
        return text.rstrip("/")
