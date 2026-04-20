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


def test_dashboard_ibkr_switches_between_webapi_and_tws_field_sets(monkeypatch):
    _app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_controller())

    dashboard.exchange_type_box.setCurrentText("futures")
    dashboard.exchange_box.setCurrentText("ibkr")
    dashboard.mode_box.setCurrentText("paper")
    dashboard.ibkr_connection_mode_box.setCurrentIndex(dashboard.ibkr_connection_mode_box.findData("webapi"))
    dashboard._update_optional_fields()

    assert dashboard._field_blocks["ibkr_connection_mode"].isHidden() is False
    assert dashboard._field_blocks["ibkr_environment"].isHidden() is False
    assert dashboard.api_input.text() == "https://127.0.0.1:5000/v1/api"
    assert dashboard._field_blocks["api"].label_widget.text() == "Base URL"
    assert dashboard._field_blocks["password"].label_widget.text() == "WebSocket URL"

    dashboard.ibkr_connection_mode_box.setCurrentIndex(dashboard.ibkr_connection_mode_box.findData("tws"))
    dashboard._update_optional_fields()

    assert dashboard._field_blocks["ibkr_environment"].isHidden() is True
    assert dashboard.api_input.text() == "127.0.0.1"
    assert dashboard.secret_input.text() == "7497"
    assert dashboard.password_input.text() == "1"
    assert dashboard._field_blocks["api"].label_widget.text() == "Host"
    assert dashboard._field_blocks["secret"].label_widget.text() == "Port"
    assert dashboard._field_blocks["password"].label_widget.text() == "Client ID"


def test_dashboard_connect_emits_ibkr_transport_specific_options(monkeypatch):
    _app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    emitted = []
    dashboard = Dashboard(_controller())
    dashboard.login_requested.connect(emitted.append)

    dashboard.exchange_type_box.setCurrentText("futures")
    dashboard.exchange_box.setCurrentText("ibkr")
    dashboard.mode_box.setCurrentText("paper")
    dashboard.ibkr_connection_mode_box.setCurrentIndex(dashboard.ibkr_connection_mode_box.findData("tws"))
    dashboard._update_optional_fields()

    dashboard._on_connect()

    assert len(emitted) == 1
    broker = emitted[0].broker
    assert broker.exchange == "ibkr"
    assert broker.options["connection_mode"] == "tws"
    assert broker.options["host"] == "127.0.0.1"
    assert broker.options["port"] == "7497"
    assert broker.options["client_id"] == "1"
