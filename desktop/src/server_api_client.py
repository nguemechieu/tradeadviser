"""
Server API Client for Desktop - Handles communication with TradeAdviser Server

Provides:
- Authentication API calls
- Broker configuration sync
- User profile management
- Settings persistence
- graceful 405 handling
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class APIEndpoint(Enum):
    LOGIN = "/api/v3/auth/login"
    SIGNUP = "/api/v3/auth/signup"
    LOGOUT = "/api/v3/auth/logout"
    REFRESH_TOKEN = "/api/v3/auth/refresh"

    GET_PROFILE = "/api/v3/users/profile"
    UPDATE_PROFILE = "/api/v3/users/profile"

    GET_BROKER_CONFIG = "/api/v3/users/broker-config"
    SAVE_BROKER_CONFIG = "/api/v3/users/broker-config"
    TEST_BROKER_CONNECTION = "/api/v3/users/broker-config/test"
    LIST_BROKER_CONFIGS = "/api/v3/users/broker-configs"
    DELETE_BROKER_CONFIG = "/api/v3/users/broker-config/{broker_id}"

    GET_ADMIN_OPERATIONS = "/api/v3/admin/operations/health"
    GET_ADMIN_RISK = "/api/v3/admin/risk/overview"
    GET_ADMIN_USERS = "/api/v3/admin/users-licenses/users"


class ServerAPIClient:
    def __init__(
        self,
        server_url: str = "http://localhost:8000",
        *,
        api_prefix: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.server_url = str(server_url or "http://localhost:8000").rstrip("/")
        self.api_prefix = str(api_prefix or "").strip().strip("/")
        self.timeout_seconds = max(1.0, float(timeout_seconds or 10.0))

        self.session_token: Optional[str] = None
        self.refresh_session_token: Optional[str] = None
        self.user_id: Optional[str] = None

        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available - async server operations are disabled")

    def set_auth_token(
        self,
        token: str | None,
        user_id: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        self.session_token = token
        if refresh_token:
            self.refresh_session_token = refresh_token
        if user_id:
            self.user_id = user_id

    def get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TradeAdviserDesktopClient/1.0",
        }

        if include_auth and self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"

        return headers

    def get_url(self, endpoint: APIEndpoint | str) -> str:
        raw_path = endpoint.value if isinstance(endpoint, APIEndpoint) else str(endpoint)
        raw_path = raw_path.strip()

        if not raw_path.startswith("/"):
            raw_path = f"/{raw_path}"

        if self.api_prefix:
            raw_path = f"/{self.api_prefix}{raw_path}"

        return f"{self.server_url}{raw_path}"

    async def _request(
        self,
        method: str,
        endpoint: APIEndpoint | str,
        *,
        json_payload: dict[str, Any] | None = None,
        include_auth: bool = True,
        alternative_endpoints: list[str] | None = None,
        form_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not AIOHTTP_AVAILABLE:
            return {"success": False, "message": "aiohttp not available"}

        endpoints = [endpoint]
        endpoints.extend(alternative_endpoints or [])

        last_error = ""

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)  # type: ignore[union-attr]

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for candidate in endpoints:
                url = self.get_url(candidate)

                try:
                    request_kwargs: dict[str, Any] = {
                        "headers": self.get_headers(include_auth=include_auth),
                    }

                    if form_payload is not None:
                        request_kwargs["data"] = form_payload
                        request_kwargs["headers"] = {
                            key: value
                            for key, value in request_kwargs["headers"].items()
                            if key.lower() != "content-type"
                        }
                    elif json_payload is not None:
                        request_kwargs["json"] = json_payload

                    async with session.request(
                        method.upper(),
                        url,
                        **request_kwargs,
                    ) as response:
                        data = await self._read_response_json(response)

                        if response.status < 400:
                            data.setdefault("success", True)
                            data.setdefault("status", response.status)
                            data.setdefault("url", url)
                            return data

                        allow_header = response.headers.get("Allow", "")
                        detail = data.get("detail") or data.get("message") or response.reason
                        last_error = f"HTTP {response.status} {detail} at {url}"

                        if response.status == 405:
                            logger.warning(
                                "Server endpoint rejected method. method=%s url=%s allow=%s detail=%s",
                                method.upper(),
                                url,
                                allow_header,
                                detail,
                            )
                            continue

                        return {
                            "success": False,
                            "status": response.status,
                            "message": str(detail),
                            "detail": detail,
                            "url": url,
                            "allow": allow_header,
                        }

                except asyncio.TimeoutError:
                    last_error = f"Server not responding timeout at {url}"
                    logger.error(last_error)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    logger.error("Server request failed method=%s url=%s error=%s", method, url, exc)

        return {
            "success": False,
            "message": last_error or "Server request failed",
        }

    async def _read_response_json(self, response: Any) -> dict[str, Any]:
        try:
            data = await response.json()
            return dict(data or {}) if isinstance(data, dict) else {"data": data}
        except Exception:
            try:
                text = await response.text()
            except Exception:
                text = ""
            return {"message": text or response.reason}

    # ==================== Authentication ====================

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        email = (email or "").strip()
        password = (password or "").strip()

        if not email or not password:
            return {"success": False, "message": "Email and password are required"}

        json_payload = {
            "identifier": email,
            "email": email,
            "username": email,
            "password": password,
        }

        # Try common FastAPI auth paths.
        result = await self._request(
            "POST",
            APIEndpoint.LOGIN,
            json_payload=json_payload,
            include_auth=False,
            alternative_endpoints=[
                "/api/v3/auth/login",
                "/api/v3/auth/token",
                "/api/v3/token",
            ],
        )

        # Some FastAPI OAuth2 routes expect form data at /token.
        if not result.get("success"):
            form_result = await self._request(
                "POST",
                "/token",
                form_payload={
                    "username": email,
                    "password": password,
                },
                include_auth=False,
                alternative_endpoints=[
                    "/api/v3/auth/token",
                    "/api/v3/token",
                ],
            )
            if form_result.get("success"):
                result = form_result

        if result.get("success"):
            access_token = (
                result.get("access_token")
                or result.get("token")
                or result.get("session_token")
            )
            refresh_token = result.get("refresh_token")
            user_id = result.get("user_id") or result.get("id")

            self.set_auth_token(access_token, user_id=user_id, refresh_token=refresh_token)

            return {
                **result,
                "success": True,
                "token": access_token,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_id": user_id,
                "message": result.get("message") or "Login successful",
            }

        return result

    async def signup(self, name: str, email: str, password: str) -> Dict[str, Any]:
        payload = {
            "name": name,
            "username": name,
            "email": email,
            "password": password,
        }

        result = await self._request(
            "POST",
            APIEndpoint.SIGNUP,
            json_payload=payload,
            include_auth=False,
            alternative_endpoints=[
                "/api/auth/signup",
                "/auth/register",
                "/register",
                "/api/register",
            ],
        )

        if result.get("success"):
            access_token = result.get("access_token") or result.get("token")
            self.set_auth_token(
                access_token,
                user_id=result.get("user_id") or result.get("id"),
                refresh_token=result.get("refresh_token"),
            )

        return result

    async def logout(self) -> Dict[str, Any]:
        result = await self._request(
            "POST",
            APIEndpoint.LOGOUT,
            include_auth=True,
            alternative_endpoints=[
                "/api/auth/logout",
                "/logout",
            ],
        )

        self.session_token = None
        self.refresh_session_token = None
        self.user_id = None

        if not result.get("success"):
            return {"success": True, "message": "Local logout completed"}

        return result

    async def refresh_token(self) -> Dict[str, Any]:
        """Refresh the current authentication session using the stored access or refresh token.

        The method sends a refresh request to the server with the available refresh token (falling
        back to the current session token) and, on success, updates the client's stored tokens.

        Returns:
            Dict[str, Any]: The server response describing the refresh outcome, including any
                new access or refresh tokens when successful.
        """
        global new_token
        if not self.session_token and not self.refresh_session_token:
            return {"success": False, "message": "No active session to refresh"}

        payload = {
            "refresh_token": self.refresh_session_token or self.session_token,
        }

        result = await self._request(
            "POST",
            APIEndpoint.REFRESH_TOKEN,
            json_payload=payload,
            include_auth=True,
            alternative_endpoints=[
                "/api/auth/refresh",
                "/refresh",
                "/auth/token/refresh",
                "/api/token/refresh",
            ],
        )

        if result.get("success"):
            if new_token := result.get("access_token") or result.get("token"):
                self.set_auth_token(
                    new_token,
                    refresh_token=result.get("refresh_token"),
                )

        return result

    # ==================== Broker Configuration ====================

    async def save_broker_config(
        self,
        broker: str,
        config: Dict[str, Any],
        mode: str = "local",
    ) -> Dict[str, Any]:
        payload = {
            "broker": broker,
            "config": config,
            "mode": mode,
        }

        return await self._request(
            "POST",
            APIEndpoint.SAVE_BROKER_CONFIG,
            json_payload=payload,
            include_auth=True,
            alternative_endpoints=[
                "/api/users/broker-config",
                "/broker-config",
                "/broker/config",
                "/api/broker/config",
            ],
        )

    async def get_broker_configs(self) -> Dict[str, Any]:
        result = await self._request(
            "GET",
            APIEndpoint.LIST_BROKER_CONFIGS,
            include_auth=True,
            alternative_endpoints=[
                "/api/users/broker-configs",
                "/users/broker-config",
                "/api/users/broker-config",
                "/broker-configs",
                "/broker/configs",
            ],
        )

        if result.get("success") and "configs" not in result:
            if isinstance(result.get("data"), list):
                result["configs"] = result["data"]
            elif isinstance(result.get("items"), list):
                result["configs"] = result["items"]
            else:
                result.setdefault("configs", [])

        return result

    async def test_broker_connection(self, broker: str, config: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "broker": broker,
            "config": config,
        }

        return await self._request(
            "POST",
            APIEndpoint.TEST_BROKER_CONNECTION,
            json_payload=payload,
            include_auth=True,
            alternative_endpoints=[
                "/api/users/broker-config/test",
                "/broker-config/test",
                "/broker/test",
                "/api/broker/test",
            ],
        )

    # ==================== User Profile ====================

    async def get_profile(self) -> Dict[str, Any]:
        """Fetch the current user's profile from the server.

        The method calls the profile endpoint (with several fallback paths) using the current
        authentication token and returns the server's JSON response as a dictionary.

        Returns:
            Dict[str, Any]: The decoded JSON response containing profile data or error details.
        """
        return await self._request(
            "GET",
            APIEndpoint.GET_PROFILE,
            include_auth=True,
            alternative_endpoints=[
                "/api/users/profile",
                "/me",
                "/users/me",
                "/api/users/me",
            ],
        )

    async def update_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the user profile with the provided data."""
        return await self._request(
            "PUT",
            APIEndpoint.UPDATE_PROFILE,
            json_payload=dict(profile_data or {}),
            include_auth=True,
            alternative_endpoints=[
                "/api/users/profile",
                "/me",
                "/users/me",
                "/api/users/me",
            ],
        )

    # ==================== Health / workspace ====================

    async def health(self) -> Dict[str, Any]:
        return await self._request(
            "GET",
            "/health",
            include_auth=False,
            alternative_endpoints=[
                "/api/health",
                "/admin/operations/health",
                "/api/admin/operations/health",
                "/",
            ],
        )


_api_client: Optional[ServerAPIClient] = None


def get_api_client(
    server_url: str = "http://localhost:8000",
) -> ServerAPIClient:
    global _api_client
    server_url = server_url.rstrip("/")
    if _api_client is None or _api_client.server_url != server_url:
        _api_client = ServerAPIClient(server_url)
    return _api_client