from __future__ import annotations

import asyncio
import inspect
import logging
import secrets
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

try:
    import aiohttp
except ImportError:  # pragma: no cover
    aiohttp = None

from core.oauth.local_callback_server import LocalOAuthCallbackServer, parse_oauth_callback_url
from core.oauth.models import OAuthTokenSet
from core.oauth.session import OAuthSessionManager

from .config import SchwabConfig
from .exceptions import SchwabAuthError, SchwabConfigurationError, SchwabTokenExpiredError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class SchwabOAuthService:
    """OAuth 2.0 authorization-code flow manager for Schwab."""

    def __init__(
        self,
        config: SchwabConfig,
        *,
        session_manager: OAuthSessionManager,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.session_manager = session_manager
        self.logger = logger or logging.getLogger("SchwabOAuthService")
        self.controller = None

    @property
    def state(self):
        return self.session_manager.state

    def is_authenticated(self) -> bool:
        return self.session_manager.has_valid_access_token(skew_seconds=self.config.refresh_skew_seconds)

    def build_authorization_url(self, *, state: str) -> str:
        query = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "state": state,
        }
        if self.config.scopes:
            query["scope"] = " ".join(self.config.scopes)
        return f"{self.config.auth_url}?{urlencode(query)}"

    async def ensure_session(self, *, interactive: bool) -> OAuthTokenSet:
        tokens = self.session_manager.tokens or self.session_manager.restore()
        if tokens and tokens.has_valid_access_token(skew_seconds=self.config.refresh_skew_seconds):
            self.session_manager.mark_status("authenticated", authenticated=True)
            return tokens
        if tokens and tokens.has_refresh_token():
            try:
                return await self.refresh_tokens(tokens.refresh_token)
            except SchwabAuthError:
                self.logger.info("Stored Schwab refresh token was not accepted; falling back to re-authentication.")
        if not interactive:
            raise SchwabTokenExpiredError("Schwab session is not authenticated and interactive login is disabled.")
        return await self.authorize_interactively()

    async def authorize_interactively(self) -> OAuthTokenSet:
        if aiohttp is None:
            raise SchwabConfigurationError("aiohttp is required for Schwab OAuth flows.")
        self.session_manager.mark_status("authenticating", authenticated=False)
        state = secrets.token_urlsafe(24)
        auth_url = self.build_authorization_url(state=state)
        self.logger.info("Starting Schwab OAuth authorization flow environment=%s", self.config.environment)

        callback_payload = None
        server = None
        if self.config.use_local_callback and self.config.callback_host in {"127.0.0.1", "localhost"}:
            server = LocalOAuthCallbackServer(
                host=self.config.callback_host,
                port=self.config.callback_port,
                path=self.config.callback_path,
                logger=self.logger.getChild("callback"),
            )
            await server.start()
        try:
            await asyncio.to_thread(webbrowser.open, auth_url)
        except Exception:
            self.logger.debug("Failed to open browser for Schwab OAuth", exc_info=True)

        try:
            if server is not None:
                try:
                    callback_payload = await server.wait_for_callback(
                        expected_state=state,
                        timeout_seconds=self.config.callback_timeout_seconds,
                    )
                except Exception:
                    self.logger.info("Schwab OAuth local callback did not complete; requesting manual redirect input.")
            if callback_payload is None:
                callback_payload = await self._manual_callback_payload(auth_url=auth_url, expected_state=state)
        finally:
            if server is not None:
                await server.close()

        tokens = await self.exchange_code_for_tokens(callback_payload.code or "")
        self.logger.info("Schwab OAuth code exchange completed successfully.")
        return tokens

    async def _manual_callback_payload(self, *, auth_url: str, expected_state: str):
        resolver = getattr(self.controller, "prompt_oauth_redirect_url", None)
        if not callable(resolver):
            raise SchwabAuthError(
                "Schwab OAuth requires either a reachable local callback URL or a manual redirect input handler."
            )
        provided = await _maybe_await(
            resolver(
                provider_name="Schwab",
                authorization_url=auth_url,
                redirect_uri=self.config.redirect_uri,
            )
        )
        text = str(provided or "").strip()
        if not text:
            raise SchwabAuthError("Schwab OAuth was canceled before the redirect response was provided.")
        if "://" not in text:
            text = f"{self.config.redirect_uri}?code={text}&state={expected_state}"
        payload = parse_oauth_callback_url(text)
        payload.validate_state(expected_state)
        if payload.error:
            raise SchwabAuthError(str(payload.error_description or payload.error))
        if not payload.code:
            raise SchwabAuthError("Schwab OAuth redirect did not contain an authorization code.")
        return payload

    async def exchange_code_for_tokens(self, code: str) -> OAuthTokenSet:
        payload = {
            "grant_type": "authorization_code",
            "code": str(code or "").strip(),
            "redirect_uri": self.config.redirect_uri,
        }
        if not payload["code"]:
            raise SchwabAuthError("Authorization code is required for Schwab token exchange.")
        tokens = await self._token_request(payload)
        self.session_manager.save(tokens)
        self.session_manager.mark_status("authenticated", authenticated=True)
        return tokens

    async def refresh_tokens(self, refresh_token: str | None = None) -> OAuthTokenSet:
        tokens = self.session_manager.tokens or self.session_manager.restore()
        refresh_value = str(refresh_token or getattr(tokens, "refresh_token", "") or "").strip()
        if not refresh_value:
            raise SchwabTokenExpiredError("No Schwab refresh token is available.")
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_value,
        }
        self.session_manager.mark_status("refreshing", authenticated=bool(tokens and tokens.access_token))
        refreshed = await self._token_request(payload, previous=tokens)
        self.session_manager.save(refreshed)
        self.session_manager.mark_status("authenticated", authenticated=True)
        self.logger.info("Schwab OAuth refresh completed successfully.")
        return refreshed

    def clear(self) -> None:
        self.session_manager.clear()

    async def _token_request(self, form_payload: dict[str, str], *, previous: OAuthTokenSet | None = None) -> OAuthTokenSet:
        if aiohttp is None:
            raise SchwabConfigurationError("aiohttp is required for Schwab OAuth flows.")
        self.logger.info("Submitting Schwab token request grant_type=%s", form_payload.get("grant_type"))
        auth = aiohttp.BasicAuth(self.config.client_id, self.config.client_secret or "") if self.config.client_secret else None
        data = dict(form_payload)
        if auth is None:
            data.setdefault("client_id", self.config.client_id)
        timeout = aiohttp.ClientTimeout(total=max(1.0, float(self.config.timeout_seconds)))
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.config.token_url,
                    data=data,
                    auth=auth,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status not in (200, 201):
                        message = payload.get("error_description") if isinstance(payload, dict) else None
                        raise SchwabAuthError(str(message or f"Schwab token request failed with status {response.status}."))
        except SchwabAuthError:
            self.session_manager.mark_status("auth_failed", authenticated=False, error="token_request_failed")
            raise
        except Exception as exc:
            self.session_manager.mark_status("auth_failed", authenticated=False, error=str(exc))
            raise SchwabAuthError(f"Schwab token request failed: {exc}") from exc
        return self._token_set_from_payload(payload if isinstance(payload, dict) else {}, previous=previous)

    def _token_set_from_payload(self, payload: dict[str, Any], *, previous: OAuthTokenSet | None = None) -> OAuthTokenSet:
        access_expires = _utc_now() + timedelta(seconds=max(0, int(payload.get("expires_in") or 0)))
        refresh_expires = None
        if payload.get("refresh_token_expires_in"):
            refresh_expires = _utc_now() + timedelta(seconds=max(0, int(payload.get("refresh_token_expires_in") or 0)))
        elif previous is not None:
            refresh_expires = previous.refresh_token_expires_at
        return OAuthTokenSet(
            provider="schwab",
            access_token=payload.get("access_token"),
            refresh_token=payload.get("refresh_token") or (previous.refresh_token if previous is not None else None),
            token_type=payload.get("token_type") or "Bearer",
            scope=payload.get("scope"),
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
            environment=self.config.environment,
            metadata={"scope": payload.get("scope")},
        )
