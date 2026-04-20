from __future__ import annotations

import asyncio
import inspect
import json
import platform
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiohttp

from security.encryption import EncryptionManager


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class PlatformSyncError(RuntimeError):
    """Raised when desktop-to-server sync cannot complete cleanly."""


class PlatformSyncStore:
    SENSITIVE_FIELDS = ("password", "access_token", "refresh_token")

    def __init__(self, encryption: EncryptionManager | None = None, path: str | Path | None = None):
        self.encryption = encryption or EncryptionManager.from_environment()
        self.path = Path(path) if path else Path(__file__).resolve().parents[4] / "platform_sync.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_store(self._default_profile())

    @staticmethod
    def _default_profile() -> dict[str, Any]:
        return {
            "base_url": "http://127.0.0.1:8000",
            "email": "",
            "password": "",
            "sync_enabled": False,
            "remember_me": True,
            "device_name": platform.node() or "desktop",
            "access_token": "",
            "refresh_token": "",
            "expires_at": "",
            "refresh_expires_at": "",
            "last_sync_at": "",
            "last_sync_status": "idle",
            "last_sync_message": "Ready to sync this desktop with Sopotek server.",
        }

    def load_profile(self) -> dict[str, Any]:
        stored = self._decrypt_payload(self._read_store())
        merged = self._default_profile()
        merged.update({key: value for key, value in stored.items() if value is not None})
        return merged

    def save_profile(self, profile: dict[str, Any] | None) -> dict[str, Any]:
        current = self.load_profile()
        incoming = deepcopy(profile or {})
        merged = self._default_profile()
        merged.update(current)
        merged.update(incoming)

        if self._credentials_changed(current, merged):
            for field in ("access_token", "refresh_token", "expires_at", "refresh_expires_at"):
                if field not in incoming:
                    merged[field] = ""

        merged["base_url"] = str(merged.get("base_url") or "").strip()
        merged["email"] = str(merged.get("email") or "").strip()
        merged["password"] = str(merged.get("password") or "").strip()
        merged["device_name"] = str(merged.get("device_name") or platform.node() or "desktop").strip() or "desktop"
        merged["sync_enabled"] = bool(merged.get("sync_enabled"))
        merged["remember_me"] = bool(merged.get("remember_me", True))
        merged["last_sync_status"] = str(merged.get("last_sync_status") or "idle").strip().lower() or "idle"
        merged["last_sync_message"] = str(merged.get("last_sync_message") or "").strip()

        self._write_store(self._encrypt_payload(merged))
        return self.load_profile()

    def record_status(self, status: str, message: str) -> dict[str, Any]:
        return self.save_profile(
            {
                "last_sync_status": str(status or "idle").strip().lower() or "idle",
                "last_sync_message": str(message or "").strip(),
                "last_sync_at": _utcnow().isoformat(),
            }
        )

    def _credentials_changed(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        for field in ("base_url", "email", "password"):
            if str(previous.get(field) or "").strip() != str(current.get(field) or "").strip():
                return True
        return False

    def _read_store(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _write_store(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _encrypt_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        encrypted = deepcopy(payload)
        for field in self.SENSITIVE_FIELDS:
            value = str(encrypted.get(field) or "").strip()
            if value:
                encrypted[field] = self.encryption.encrypt(value)
        return encrypted

    def _decrypt_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        decrypted = deepcopy(payload)
        for field in self.SENSITIVE_FIELDS:
            value = str(decrypted.get(field) or "").strip()
            if not value:
                continue
            try:
                decrypted[field] = self.encryption.decrypt(value)
            except Exception:
                decrypted[field] = ""
        return decrypted


class PlatformSyncService:
    def __init__(
        self,
        store: PlatformSyncStore | None = None,
        *,
        requestor=None,
        timeout_seconds: float = 12.0,
        app_version: str = "desktop-2026.04",
    ):
        self.store = store or PlatformSyncStore()
        self.requestor = requestor
        self.timeout_seconds = float(timeout_seconds)
        self.app_version = str(app_version or "desktop").strip() or "desktop"
        # Lock to prevent concurrent authentication attempts
        self._auth_lock = asyncio.Lock()
        # Cache for access token validation
        self._last_auth_error: str | None = None

    def load_profile(self) -> dict[str, Any]:
        profile = self.store.load_profile()
        profile["base_url"] = self._normalize_base_url(profile.get("base_url"))
        return profile
    
    def validate_credentials(self, profile: dict[str, Any] | None = None) -> tuple[bool, str]:
        """
        Validate that profile has required credentials.
        
        Returns:
            (is_valid, error_message)
        """
        p = profile or self.load_profile()
        
        # Check server URL
        base_url = str(p.get("base_url") or "").strip()
        if not base_url:
            return False, "Server URL not configured"
        if not base_url.startswith(("http://", "https://")):
            return False, "Invalid server URL format (must start with http:// or https://)"
        
        # Check email/identifier
        identifier = str(p.get("email") or "").strip()
        if not identifier:
            return False, "Email/username not configured"
        if len(identifier) < 3:
            return False, "Email/username is too short"
        
        # Check password
        password = str(p.get("password") or "").strip()
        if not password:
            return False, "Password not configured"
        if len(password) < 1:
            return False, "Password is empty"
        
        return True, "Credentials are valid"

    def save_profile(self, profile: dict[str, Any] | None) -> dict[str, Any]:
        normalized = dict(profile or {})
        if "base_url" in normalized:
            normalized["base_url"] = self._normalize_base_url(normalized.get("base_url"))
        return self.store.save_profile(normalized)

    async def fetch_workspace_settings(self, profile_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        profile = self.save_profile(profile_overrides)
        try:
            workspace = await self._authorized_request("GET", "/workspace/settings", profile=profile)
            user = await self._authorized_request("GET", "/auth/me", profile=profile)
            updated_profile = self.store.record_status(
                "success",
                f"Loaded workspace from server for {str(user.get('email') or profile.get('email') or 'user').strip()}.",
            )
            return {
                "profile": updated_profile,
                "workspace": workspace,
                "user": user,
            }
        except Exception as exc:
            self.store.record_status("error", str(exc))
            raise

    async def push_workspace_settings(
        self,
        workspace_payload: dict[str, Any],
        profile_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = self.save_profile(profile_overrides)
        
        # Validate credentials before attempting sync
        is_valid, error_msg = self.validate_credentials(profile)
        if not is_valid:
            raise PlatformSyncError(f"Sync configuration error: {error_msg}")
        
        payload = self._workspace_payload_for_sync(workspace_payload, profile=profile)
        try:
            workspace = await self._authorized_request("PUT", "/workspace/settings", payload=payload, profile=profile)
            user = await self._authorized_request("GET", "/auth/me", profile=profile)
            updated_profile = self.store.record_status(
                "success",
                f"Synced desktop workspace to server for {str(user.get('email') or profile.get('email') or 'user').strip()}.",
            )
            return {
                "profile": updated_profile,
                "workspace": workspace,
                "user": user,
            }
        except Exception as exc:
            self.store.record_status("error", str(exc))
            raise

    async def _authorized_request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        active_profile = await self._ensure_access_token(profile)
        try:
            return await self._request_json(
                method=method,
                url=f"{active_profile['base_url']}{path}",
                payload=payload,
                access_token=str(active_profile.get("access_token") or "").strip(),
            )
        except PlatformSyncError as exc:
            if "401" not in str(exc):
                raise
        active_profile = await self._refresh_or_login(active_profile, force_login=True)
        return await self._request_json(
            method=method,
            url=f"{active_profile['base_url']}{path}",
            payload=payload,
            access_token=str(active_profile.get("access_token") or "").strip(),
        )

    async def _ensure_access_token(self, profile: dict[str, Any]) -> dict[str, Any]:
        access_token = str(profile.get("access_token") or "").strip()
        expires_at = _parse_datetime(profile.get("expires_at"))
        
        # If we have a valid token that doesn't expire soon, return it
        if access_token and expires_at and expires_at > (_utcnow() + timedelta(seconds=30)):
            return profile
        
        # Use lock to prevent concurrent authentication attempts
        async with self._auth_lock:
            # Double-check after acquiring lock (might have been refreshed by another task)
            access_token = str(profile.get("access_token") or "").strip()
            expires_at = _parse_datetime(profile.get("expires_at"))
            if access_token and expires_at and expires_at > (_utcnow() + timedelta(seconds=30)):
                return profile
            
            return await self._refresh_or_login(profile)

    async def _refresh_or_login(self, profile: dict[str, Any], *, force_login: bool = False) -> dict[str, Any]:
        # Try refresh token first if available
        if not force_login and str(profile.get("refresh_token") or "").strip():
            try:
                session_payload = await self._request_json(
                    method="POST",
                    url=f"{profile['base_url']}/auth/refresh",
                    payload={
                        "refresh_token": str(profile.get("refresh_token") or "").strip(),
                        "remember_me": bool(profile.get("remember_me", True)),
                    },
                )
                if isinstance(session_payload, dict) and session_payload.get("access_token"):
                    return self._store_session(profile, session_payload)
            except Exception as refresh_exc:
                # Refresh failed, will try login instead
                pass

        # Fall back to login with email/password
        password = str(profile.get("password") or "").strip()
        identifier = str(profile.get("email") or "").strip()
        
        # Validate credentials are present
        if not identifier or not password:
            raise PlatformSyncError(
                "Cannot authenticate: Enter your Sopotek server URL, email, and password in sync settings."
            )
        
        # Validate base URL
        base_url = str(profile.get("base_url") or "").strip()
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise PlatformSyncError(
                "Cannot authenticate: Invalid server URL. Use format: http://localhost:8000 or https://server.com"
            )
        
        try:
            session_payload = await self._request_json(
                method="POST",
                url=f"{base_url}/auth/login",
                payload={
                    "identifier": identifier,
                    "password": password,
                    "remember_me": bool(profile.get("remember_me", True)),
                },
            )
            
            # Validate response has required fields
            if not isinstance(session_payload, dict):
                raise PlatformSyncError("Server returned invalid response format")
            
            if not session_payload.get("access_token"):
                detail = session_payload.get("detail", "Authentication failed: no access token in response")
                raise PlatformSyncError(detail)
            
            self._last_auth_error = None
            return self._store_session(profile, session_payload)
            
        except PlatformSyncError:
            raise
        except Exception as exc:
            error_msg = f"Authentication failed: {str(exc)}"
            self._last_auth_error = error_msg
            raise PlatformSyncError(error_msg) from exc

    def _store_session(self, profile: dict[str, Any], session_payload: dict[str, Any]) -> dict[str, Any]:
        persisted = self.save_profile(
            {
                **profile,
                "access_token": str(session_payload.get("access_token") or "").strip(),
                "refresh_token": str(session_payload.get("refresh_token") or "").strip(),
                "expires_at": str(session_payload.get("expires_at") or "").strip(),
                "refresh_expires_at": str(session_payload.get("refresh_expires_at") or "").strip(),
            }
        )
        return persisted

    async def _request_json(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"SopotekDesktop/{self.app_version}",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        if self.requestor is not None:
            result = self.requestor(method=method, url=url, json_payload=payload, headers=headers, timeout=self.timeout_seconds)
            if inspect.isawaitable(result):
                result = await result
            return result if isinstance(result, dict) else {}

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method.upper(), url, json=payload, headers=headers) as response:
                    body_text = await response.text()
                    data = {}
                    if body_text:
                        try:
                            parsed = json.loads(body_text)
                            if isinstance(parsed, dict):
                                data = parsed
                        except json.JSONDecodeError:
                            data = {}
                    if response.status >= 400:
                        detail = str(data.get("detail") or body_text or response.reason or "Request failed").strip()
                        raise PlatformSyncError(f"{response.status}: {detail}")
                    return data
        except aiohttp.ClientError as exc:
            raise PlatformSyncError(f"Unable to reach Sopotek server: {exc}") from exc

    def _workspace_payload_for_sync(self, payload: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(payload or {})
        merged["profile_name"] = str(merged.get("profile_name") or "").strip()
        merged["desktop_sync_enabled"] = bool(profile.get("sync_enabled"))
        merged["desktop_device_name"] = str(profile.get("device_name") or platform.node() or "desktop").strip() or "desktop"
        merged["desktop_app_version"] = self.app_version
        merged["desktop_last_sync_at"] = _utcnow().isoformat()
        merged["desktop_last_sync_source"] = "desktop"
        return merged

    @staticmethod
    def _normalize_base_url(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "http://127.0.0.1:8000"
        if "://" not in text:
            text = f"http://{text}"
        return text.rstrip("/")
