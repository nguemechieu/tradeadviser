from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet

from frontend.ui.services.platform_sync_service import PlatformSyncService, PlatformSyncStore
from security.encryption import EncryptionManager


def _store(tmp_path):
    return PlatformSyncStore(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "platform_sync.json",
    )


def test_platform_sync_store_encrypts_sensitive_fields(tmp_path):
    store = _store(tmp_path)

    store.save_profile(
        {
            "base_url": "http://127.0.0.1:8000",
            "email": "desk@sopotek.ai",
            "password": "super-secret-password",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        }
    )

    raw = json.loads((tmp_path / "platform_sync.json").read_text(encoding="utf-8"))

    assert raw["password"] != "super-secret-password"
    assert raw["access_token"] != "access-token"
    assert raw["refresh_token"] != "refresh-token"

    loaded = store.load_profile()
    assert loaded["password"] == "super-secret-password"
    assert loaded["access_token"] == "access-token"
    assert loaded["refresh_token"] == "refresh-token"


def test_platform_sync_service_push_logs_in_and_persists_session(tmp_path):
    store = _store(tmp_path)
    calls = []

    async def requester(*, method, url, json_payload, headers, timeout):
        calls.append((method, url, json_payload, headers, timeout))
        if url.endswith("/auth/login"):
            return {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_at": "2026-04-06T22:00:00Z",
                "refresh_expires_at": "2026-04-13T22:00:00Z",
            }
        if url.endswith("/workspace/settings"):
            assert headers["Authorization"] == "Bearer access-1"
            return dict(json_payload or {})
        if url.endswith("/auth/me"):
            return {"email": "desk@sopotek.ai"}
        raise AssertionError(f"Unexpected request {method} {url}")

    service = PlatformSyncService(store=store, requestor=requester, app_version="desktop-test")

    result = asyncio.run(
        service.push_workspace_settings(
            {
                "language": "en",
                "broker_type": "crypto",
                "exchange": "coinbase",
                "customer_region": "us",
                "mode": "paper",
                "market_type": "spot",
                "ibkr_connection_mode": "webapi",
                "ibkr_environment": "gateway",
                "ibkr_base_url": "",
                "ibkr_websocket_url": "",
                "ibkr_host": "",
                "ibkr_port": "",
                "ibkr_client_id": "",
                "schwab_environment": "sandbox",
                "api_key": "coinbase-key",
                "secret": "coinbase-secret",
                "password": "",
                "account_id": "desk-001",
                "risk_percent": 2,
                "remember_profile": True,
                "profile_name": "coinbase_main",
                "solana": {
                    "wallet_address": "",
                    "private_key": "",
                    "rpc_url": "",
                    "jupiter_api_key": "",
                    "okx_api_key": "",
                    "okx_secret": "",
                    "okx_passphrase": "",
                    "okx_project_id": "",
                },
            },
            {
                "base_url": "http://127.0.0.1:8000",
                "email": "desk@sopotek.ai",
                "password": "super-secret-password",
                "sync_enabled": True,
            },
        )
    )

    stored = store.load_profile()
    assert stored["access_token"] == "access-1"
    assert stored["refresh_token"] == "refresh-1"
    assert stored["last_sync_status"] == "success"
    assert result["workspace"]["desktop_sync_enabled"] is True
    assert result["workspace"]["desktop_app_version"] == "desktop-test"
    assert result["workspace"]["desktop_last_sync_source"] == "desktop"
    assert any(url.endswith("/auth/login") for _method, url, _payload, _headers, _timeout in calls)
    assert any(url.endswith("/workspace/settings") for _method, url, _payload, _headers, _timeout in calls)


def test_platform_sync_service_fetch_uses_cached_session_when_still_valid(tmp_path):
    store = _store(tmp_path)
    store.save_profile(
        {
            "base_url": "http://127.0.0.1:8000",
            "email": "desk@sopotek.ai",
            "password": "super-secret-password",
            "sync_enabled": True,
            "access_token": "cached-token",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        }
    )
    calls = []

    async def requester(*, method, url, json_payload, headers, timeout):
        calls.append((method, url, json_payload, headers, timeout))
        if url.endswith("/workspace/settings"):
            assert headers["Authorization"] == "Bearer cached-token"
            return {"exchange": "coinbase", "broker_type": "crypto", "mode": "paper", "risk_percent": 2}
        if url.endswith("/auth/me"):
            return {"email": "desk@sopotek.ai"}
        raise AssertionError(f"Unexpected request {method} {url}")

    service = PlatformSyncService(store=store, requestor=requester)

    result = asyncio.run(service.fetch_workspace_settings())

    assert result["workspace"]["exchange"] == "coinbase"
    assert all(not url.endswith("/auth/login") for _method, url, _payload, _headers, _timeout in calls)
