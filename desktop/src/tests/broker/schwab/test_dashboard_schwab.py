import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from PySide6.QtWidgets import QApplication

from frontend.ui.dashboard import Dashboard


class _Settings:
    def __init__(self):
        self.store = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _controller():
    return SimpleNamespace(
        settings=_Settings(),
        strategy_name="Trend Following",
        get_license_status=lambda: {"badge": "TRIAL", "plan_name": "Trial", "summary": "Ready"},
        license_allows=lambda _feature: True,
        set_language=lambda _code: None,
        show_license_dialog=lambda *_args, **_kwargs: None,
    )


def test_dashboard_schwab_shows_oauth_specific_fields(monkeypatch):
    _app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_controller())

    dashboard.exchange_type_box.setCurrentText("options")
    dashboard.exchange_box.setCurrentText("schwab")
    dashboard.mode_box.setCurrentText("paper")
    dashboard._update_optional_fields()

    assert dashboard._field_blocks["schwab_environment"].isHidden() is False
    assert dashboard._field_blocks["api"].label_widget.text() == "App Key / Client ID"
    assert dashboard._field_blocks["password"].label_widget.text() == "Redirect URI"
    assert dashboard.connect_button.text() == "Sign In With Schwab"


def test_dashboard_connect_emits_schwab_oauth_profile(monkeypatch):
    _app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    emitted = []
    dashboard = Dashboard(_controller())
    dashboard.login_requested.connect(emitted.append)

    dashboard.exchange_type_box.setCurrentText("options")
    dashboard.exchange_box.setCurrentText("schwab")
    dashboard.mode_box.setCurrentText("paper")
    dashboard.schwab_environment_box.setCurrentIndex(dashboard.schwab_environment_box.findData("production"))
    dashboard.api_input.setText("client-id")
    dashboard.secret_input.setText("client-secret")
    dashboard.password_input.setText("http://127.0.0.1:8182/callback")
    dashboard.account_id_input.setText("hash-123")

    dashboard._on_connect()

    assert len(emitted) == 1
    broker = emitted[0].broker
    assert broker.exchange == "schwab"
    assert broker.api_key == "client-id"
    assert broker.secret == "client-secret"
    assert broker.password == "http://127.0.0.1:8182/callback"
    assert broker.options["redirect_uri"] == "http://127.0.0.1:8182/callback"
    assert broker.options["environment"] == "production"
    assert broker.options["account_hash"] == "hash-123"
    assert str(broker.options["profile_name"]).startswith("schwab_")


def test_dashboard_load_selected_account_restores_schwab_environment(monkeypatch):
    _app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    monkeypatch.setattr(
        "frontend.ui.dashboard.CredentialManager.load_account",
        lambda _name: {
            "broker": {
                "type": "options",
                "exchange": "schwab",
                "mode": "paper",
                "api_key": "client-id",
                "secret": "client-secret",
                "password": "http://127.0.0.1:8182/callback",
                "options": {
                    "environment": "production",
                    "account_hash": "hash-123",
                    "market_type": "option",
                },
            },
            "risk": {"risk_percent": 1},
        },
    )
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.touch_account", lambda _name: None)

    dashboard = Dashboard(_controller())
    dashboard.saved_account_box.addItem("schwab_main")
    dashboard.saved_account_box.setCurrentText("schwab_main")

    dashboard._load_selected_account("schwab_main")

    assert dashboard.exchange_box.currentText() == "schwab"
    assert dashboard.api_input.text() == "client-id"
    assert dashboard.password_input.text() == "http://127.0.0.1:8182/callback"
    assert dashboard.account_id_input.text() == "hash-123"
    assert dashboard.schwab_environment_box.currentData() == "production"
