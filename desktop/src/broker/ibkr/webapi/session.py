from __future__ import annotations

import json
import logging
from typing import Any

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

from broker.ibkr.config import IBKRWebApiConfig
from broker.ibkr.exceptions import (
    IBKRApiError,
    IBKRAuthError,
    IBKRConfigurationError,
    IBKRConnectionError,
    IBKRRateLimitError,
    IBKRSessionError,
)
from broker.ibkr.models import IBKRSessionState, IBKRSessionStatus, IBKRTransport


class IBKRWebApiSession:
    """Owns the HTTP session and state for the IBKR Client Portal Web API."""

    def __init__(self, config: IBKRWebApiConfig, *, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("IBKRWebApiSession")
        self.state = IBKRSessionState(
            transport=IBKRTransport.WEBAPI,
            status=IBKRSessionStatus.DISCONNECTED,
            account_id=config.account_id,
            profile_name=config.profile_name,
        )
        self._client: Any = None

    @property
    def is_open(self) -> bool:
        client = self._client
        return client is not None and not bool(getattr(client, "closed", True))

    async def open(self) -> None:
        if self.is_open:
            return
        if aiohttp is None:
            raise IBKRConfigurationError("aiohttp is required for the IBKR Web API transport.")
        try:
            connector = aiohttp.TCPConnector(ssl=self.config.verify_ssl)
            timeout = aiohttp.ClientTimeout(total=max(1.0, float(self.config.timeout_seconds)))
            self._client = aiohttp.ClientSession(connector=connector, timeout=timeout)
        except Exception as exc:
            self.state.status = IBKRSessionStatus.DEGRADED
            self.state.last_error = str(exc)
            raise IBKRConnectionError(f"Unable to create IBKR Web API session: {exc}") from exc
        self.state.connected = True
        self.state.status = IBKRSessionStatus.CONNECTED

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None and not bool(getattr(client, "closed", True)):
            await client.close()
        self.state.connected = False
        self.state.authenticated = False
        self.state.status = IBKRSessionStatus.DISCONNECTED

    def update_state(self, **kwargs: Any) -> IBKRSessionState:
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        return self.state

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | list[Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        expected_statuses: tuple[int, ...] = (200,),
        allow_empty: bool = True,
    ) -> Any:
        await self.open()
        url = path if str(path).startswith("http") else f"{self.config.base_url.rstrip('/')}/{str(path).lstrip('/')}"
        request_headers = {"Accept": "application/json", **dict(headers or {})}
        if self.config.session_token and "Authorization" not in request_headers:
            request_headers["Authorization"] = f"Bearer {self.config.session_token}"

        self.logger.debug("IBKR Web API request %s %s", method.upper(), url)
        try:
            async with self._client.request(
                method.upper(),
                url,
                params=params,
                json=json_payload,
                data=data,
                headers=request_headers,
            ) as response:
                text = await response.text()
                payload: Any = {}
                if text:
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        payload = {"raw": text}
                elif allow_empty:
                    payload = {}

                if response.status == 429:
                    raise IBKRRateLimitError(f"IBKR Web API rate limit for {method.upper()} {path}")
                if response.status in {401, 403}:
                    self.state.status = IBKRSessionStatus.SESSION_EXPIRED
                    self.state.authenticated = False
                    raise IBKRSessionError(f"IBKR Web API session rejected {method.upper()} {path}: {response.status}")
                if response.status not in expected_statuses:
                    message = payload.get("message") if isinstance(payload, dict) else text
                    if response.status in {400, 422}:
                        raise IBKRAuthError(str(message or f"IBKR request failed: {response.status}"))
                    raise IBKRApiError(str(message or f"IBKR request failed: {response.status}"))
                return payload
        except (IBKRApiError, IBKRAuthError, IBKRRateLimitError, IBKRSessionError):
            raise
        except Exception as exc:
            self.state.status = IBKRSessionStatus.DEGRADED
            self.state.last_error = str(exc)
            raise IBKRConnectionError(f"IBKR Web API request failed: {exc}") from exc
