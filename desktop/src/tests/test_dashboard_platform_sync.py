import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from frontend.ui.dashboard import Dashboard


class _Settings:
    def __init__(self):
        self.store = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value


def _get_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _controller(sync_profile=None):
    return SimpleNamespace(
        settings=_Settings(),
        strategy_name="EMA Cross",
        language_code="en",
        get_license_status=lambda: {"badge": "FREE", "plan_name": "Free", "summary": "Ready"},
        license_allows=lambda _feature: True,
        set_language=lambda _code: None,
        show_license_dialog=lambda *_args, **_kwargs: None,
        platform_sync_profile=lambda: sync_profile
        or {
            "base_url": "http://127.0.0.1:8000",
            "email": "",
            "password": "",
            "sync_enabled": False,
            "last_sync_status": "idle",
            "last_sync_message": "Ready",
        },
        save_platform_sync_profile=lambda profile: profile,
        request_platform_workspace_pull=lambda profile: profile,
        request_platform_workspace_push=lambda payload, profile, interactive=False: (payload, profile, interactive),
    )


def test_dashboard_loads_platform_sync_profile_from_controller(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(
        _controller(
            {
                "base_url": "http://sync.sopotek.local:8000",
                "email": "desk@sopotek.ai",
                "password": "topsecret",
                "sync_enabled": True,
                "last_sync_status": "success",
                "last_sync_message": "Last sync succeeded.",
            }
        )
    )

    assert dashboard.server_url_input.text() == "http://sync.sopotek.local:8000"
    assert dashboard.server_email_input.text() == "desk@sopotek.ai"
    assert dashboard.server_password_input.text() == "topsecret"
    assert dashboard.sync_workspace_checkbox.isChecked() is True
    assert dashboard.platform_sync_status_label.text() == "Last sync succeeded."


def test_dashboard_workspace_settings_payload_captures_ibkr_sync_fields(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_controller())

    dashboard.exchange_type_box.setCurrentText("futures")
    dashboard.exchange_box.setCurrentText("ibkr")
    dashboard.ibkr_connection_mode_box.setCurrentIndex(dashboard.ibkr_connection_mode_box.findData("tws"))
    dashboard._update_optional_fields()
    dashboard.api_input.setText("127.0.0.1")
    dashboard.secret_input.setText("7497")
    dashboard.password_input.setText("7")
    dashboard.account_id_input.setText("DU1234567")
    dashboard.sync_workspace_checkbox.setChecked(True)

    payload = dashboard._workspace_settings_payload()

    assert payload["broker_type"] == "futures"
    assert payload["exchange"] == "ibkr"
    assert payload["ibkr_connection_mode"] == "tws"
    assert payload["ibkr_host"] == "127.0.0.1"
    assert payload["ibkr_port"] == "7497"
    assert payload["ibkr_client_id"] == "7"
    assert payload["desktop_sync_enabled"] is True


def test_dashboard_apply_workspace_settings_restores_ibkr_transport_fields(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_controller())

    dashboard.apply_workspace_settings(
        {
            "language": "en",
            "broker_type": "futures",
            "exchange": "ibkr",
            "customer_region": "us",
            "mode": "paper",
            "market_type": "derivative",
            "ibkr_connection_mode": "tws",
            "ibkr_environment": "gateway",
            "ibkr_base_url": "",
            "ibkr_websocket_url": "",
            "ibkr_host": "127.0.0.1",
            "ibkr_port": "7497",
            "ibkr_client_id": "9",
            "schwab_environment": "sandbox",
            "api_key": "",
            "secret": "",
            "password": "",
            "account_id": "DU7654321",
            "risk_percent": 4,
            "remember_profile": True,
            "profile_name": "ibkr_main",
            "desktop_sync_enabled": True,
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
        }
    )

    assert dashboard.exchange_type_box.currentText() == "futures"
    assert dashboard.exchange_box.currentText() == "ibkr"
    assert dashboard.ibkr_connection_mode_box.currentData() == "tws"
    assert dashboard.api_input.text() == "127.0.0.1"
    assert dashboard.secret_input.text() == "7497"
    assert dashboard.password_input.text() == "9"
    assert dashboard.account_id_input.text() == "DU7654321"
    assert dashboard.risk_input.value() == 4
