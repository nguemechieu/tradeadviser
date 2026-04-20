import asyncio
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from core.server_client import SQSClient
from event_bus.event_types import EventType
from ui.components.app_controller import AppController
from ui.components.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_sqs_client_login_uses_identifier_and_bearer_headers():
    calls = []

    async def requester(*, method, url, json_payload=None, headers=None, timeout=None):
        calls.append(
            {
                "method": method,
                "url": url,
                "json_payload": dict(json_payload or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if url.endswith("/auth/login"):
            return {"access_token": "token-123", "expires_in": 300}
        if url.endswith("/performance"):
            assert headers["Authorization"] == "Bearer token-123"
            return {"summary": {"total_pnl": 1250.0}}
        raise AssertionError(f"Unexpected URL: {url}")

    async def run_test():
        client = SQSClient(
            "http://localhost:8010",
            email="desk@sopotek.ai",
            password="secret",
            requestor=requester,
        )
        await client.login()
        performance_data = await client.get_performance()
        assert performance_data["summary"]["total_pnl"] == 1250.0

    asyncio.run(run_test())

    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "http://localhost:8010/auth/login"
    assert calls[0]["json_payload"] == {"identifier": "desk@sopotek.ai", "password": "secret"}
    assert "Authorization" not in calls[0]["headers"]
    assert calls[1]["method"] == "GET"
    assert calls[1]["url"] == "http://localhost:8010/performance"
    assert calls[1]["headers"]["Authorization"] == "Bearer token-123"


def test_app_controller_exposes_open_workspace_features():
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.sqs.feature_gate")
    controller.platform_sync_service = SimpleNamespace(
        load_profile=lambda: {
            "base_url": "http://localhost:8010",
            "email": "desk@sopotek.ai",
            "password": "secret",
        }
    )
    controller.allowed_features = {"trading", "ml_signals"}
    controller.server_feature_gate_enabled = True
    controller.license_status = {}

    assert AppController.license_allows(controller, "live_trading") is True
    assert AppController.is_feature_enabled(controller, "ml_signals") is True
    assert AppController.is_feature_enabled(controller, "manual_trading") is True
    assert "available" in AppController.feature_message(controller, "auto_trading").lower()


def test_app_controller_active_strategy_weight_map_applies_sqs_feedback():
    controller = AppController.__new__(AppController)
    controller.multi_strategy_enabled = True
    controller.symbol_strategy_assignments = {
        "BTC-USD": [
            {"strategy_name": "Trend Following", "weight": 1.0},
            {"strategy_name": "Mean Reversion", "weight": 1.0},
        ]
    }
    controller.server_strategy_feedback = {
        "Trend Following": 1.05,
        "Mean Reversion": 0.90,
    }
    controller.strategy_name = "Trend Following"

    weights = AppController.active_strategy_weight_map(controller)

    assert weights["Trend Following"] > weights["Mean Reversion"]
    assert round(sum(weights.values()), 6) == 1.0


def test_app_controller_builds_signal_payload_from_runtime_event():
    controller = AppController.__new__(AppController)
    controller.time_frame = "15m"
    controller._normalize_strategy_symbol_key = AppController._normalize_strategy_symbol_key.__get__(
        controller, AppController
    )

    payload = AppController._server_signal_payload_from_runtime_event(
        controller,
        EventType.SIGNAL,
        {
            "symbol": "btc/usd",
            "timeframe": "1h",
            "confidence": 0.83,
            "signal": {"strategy_name": "Momentum"},
        },
    )

    assert payload["symbol"] == "BTC/USD"
    assert payload["strategy"] == "Momentum"
    assert payload["confidence"] == 0.83
    assert payload["timeframe"] == "1h"


def test_terminal_toggle_autotrading_starts_when_requested(monkeypatch):
    _app()
    created = []

    def _create_task(coro):
        created.append(coro)
        coro.close()
        return SimpleNamespace()

    loop = SimpleNamespace(create_task=_create_task)
    fake_terminal = SimpleNamespace(
        autotrading_enabled=False,
        controller=SimpleNamespace(
            trading_system=SimpleNamespace(start=lambda: asyncio.sleep(0)),
            get_active_autotrade_symbols=lambda: ["BTC/USD"],
            is_live_mode=lambda: False,
        ),
        autotrade_scope_value="all",
        _autotrade_enable_task=None,
        _update_autotrade_button=lambda: None,
        autotrade_toggle=SimpleNamespace(emit=lambda value: None),
        _autotrade_scope_label=lambda: "All Symbols",
    )
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: loop)

    Terminal._toggle_autotrading(fake_terminal)

    assert created
