import os
import sys
from types import SimpleNamespace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from broker.market_venues import supported_market_venues_for_profile
from broker.solana_broker import SolanaBroker
from frontend.ui.dashboard import Dashboard


def test_coinbase_validation_accepts_valid_pem_with_org_key_name():
    error = Dashboard._coinbase_validation_error(
        "organizations/test/apiKeys/key-1",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIExamplePrivateKeyMaterial1234567890\n-----END EC PRIVATE KEY-----\n",
        password=None,
    )

    assert error is None


def test_coinbase_validation_accepts_uuid_key_id_with_pem():
    error = Dashboard._coinbase_validation_error(
        "2ffe3f58-d600-47a8-a147-1c55854eddc8",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIExamplePrivateKeyMaterial1234567890\n-----END EC PRIVATE KEY-----\n",
        password=None,
    )

    assert error is None


def test_coinbase_validation_accepts_json_bundle_with_private_key_body():
    error = Dashboard._coinbase_validation_error(
        "",
        '{"id":"2ffe3f58-d600-47a8-a147-1c55854eddc8","privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}',
        password=None,
    )

    assert error is None


def test_dashboard_resolved_inputs_prefer_coinbase_key_name_from_json_bundle(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()

    dashboard = Dashboard(controller)
    dashboard.exchange_type_box.setCurrentText("crypto")
    dashboard.exchange_box.setCurrentText("coinbase")
    dashboard.api_input.clear()
    dashboard.secret_input.setText(
        (
            '{"name":"organizations/test/apiKeys/key-1",'
            '"id":"2ffe3f58-d600-47a8-a147-1c55854eddc8",'
            '"privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}'
        )
    )

    resolved = dashboard._resolved_broker_inputs()

    assert resolved["api_key"] == "organizations/test/apiKeys/key-1"


def test_coinbase_validation_rejects_non_advanced_trade_api_key_name():
    error = Dashboard._coinbase_validation_error(
        "GA4CIZX3QJADGZZKI7HUS6WVHBNIX3EUNUW4MZUDW7VR7UIFV6D4CQW4",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIExamplePrivateKeyMaterial1234567890\n-----END EC PRIVATE KEY-----\n",
        password=None,
    )

    assert "format is not recognized" in error


def test_coinbase_validation_rejects_truncated_private_key():
    error = Dashboard._coinbase_validation_error(
        "organizations/test/apiKeys/key-1",
        "H\\nM6aXBtEitse01mWyswFekSdYpm9s7nha3w==\\n-----END EC PRIVATE KEY-----",
        password=None,
    )

    assert "malformed" in error.lower()


def test_coinbase_validation_rejects_passphrase_usage():
    error = Dashboard._coinbase_validation_error(
        "organizations/test/apiKeys/key-1",
        "\"-----BEGIN EC PRIVATE KEY-----\\nMHcCAQEEIExamplePrivateKeyMaterial1234567890\\n-----END EC PRIVATE KEY-----\\n\"",
        password="legacy-passphrase",
    )

    assert "does not use the passphrase field" in error


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


def _make_controller():
    return SimpleNamespace(
        settings=_Settings(),
        strategy_name="EMA Cross",
        get_license_status=lambda: {"badge": "FREE", "plan_name": "Free", "summary": "Ready"},
        license_allows=lambda _feature: True,
        set_language=lambda _code: None,
        show_license_dialog=lambda *_args, **_kwargs: None,
    )


def _combo_texts(combo_box):
    return [combo_box.itemText(index) for index in range(combo_box.count())]


def _make_solana_wallet(seed_byte=21):
    seed = bytes([seed_byte]) * 32
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        "wallet": SolanaBroker._base58_encode(public_key),
        "secret": SolanaBroker._base58_encode(seed),
    }


def test_dashboard_strategy_is_terminal_or_auto_managed(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()

    dashboard = Dashboard(controller)

    assert not hasattr(dashboard, "strategy_box")
    assert "auto" in dashboard.market_secondary.body_label.text().lower()
    assert "terminal" in dashboard.market_secondary.body_label.text().lower()
    assert "auto" in dashboard.check_strategy.state_label.text().lower()
    assert "auto per symbol" in dashboard.summary_meta.text().lower()


def test_dashboard_connect_emits_controller_strategy_without_dashboard_override(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()
    emitted = []

    dashboard = Dashboard(controller)
    dashboard.login_requested.connect(emitted.append)
    dashboard.exchange_type_box.setCurrentText("paper")
    dashboard.exchange_box.setCurrentText("paper")
    dashboard.mode_box.setCurrentText("paper")

    dashboard._on_connect()

    assert len(emitted) == 1
    assert emitted[0].strategy == "EMA Cross"


def test_dashboard_resolved_inputs_normalize_coinbase_json_bundle(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()

    dashboard = Dashboard(controller)
    dashboard.exchange_type_box.setCurrentText("crypto")
    dashboard.exchange_box.setCurrentText("coinbase")
    dashboard.api_input.clear()
    dashboard.secret_input.setText(
        '{"id":"2ffe3f58-d600-47a8-a147-1c55854eddc8","privateKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}'
    )

    resolved = dashboard._resolved_broker_inputs()

    assert resolved["api_key"] == "2ffe3f58-d600-47a8-a147-1c55854eddc8"
    assert resolved["secret"].startswith("-----BEGIN EC PRIVATE KEY-----\n")
    assert resolved["secret"].endswith("\n-----END EC PRIVATE KEY-----\n")


def test_dashboard_connect_defaults_coinbase_derivative_sessions_to_futures(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()
    emitted = []

    dashboard = Dashboard(controller)
    dashboard.login_requested.connect(emitted.append)
    dashboard.exchange_type_box.setCurrentText("crypto")
    dashboard.exchange_box.setCurrentText("coinbase")
    dashboard.mode_box.setCurrentText("paper")
    derivative_index = dashboard.market_type_box.findData("derivative")
    dashboard.market_type_box.setCurrentIndex(derivative_index)
    dashboard.api_input.setText("organizations/test/apiKeys/key-1")
    dashboard.secret_input.setText(
        "-----BEGIN EC PRIVATE KEY-----\n"
        "MHcCAQEEIExamplePrivateKeyMaterial1234567890\n"
        "-----END EC PRIVATE KEY-----\n"
    )

    dashboard._on_connect()

    assert len(emitted) == 1
    assert emitted[0].broker.options["market_type"] == "derivative"
    assert emitted[0].broker.options["defaultSubType"] == "future"


def test_dashboard_broker_type_list_includes_all_available_broker_families(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_make_controller())

    assert _combo_texts(dashboard.exchange_type_box) == [
        "crypto",
        "forex",
        "stocks",
        "options",
        "futures",
        "derivatives",
        "paper",
    ]


def test_dashboard_exchange_lists_include_derivative_broker_options(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_make_controller())

    dashboard.exchange_type_box.setCurrentText("options")
    assert _combo_texts(dashboard.exchange_box) == ["schwab"]

    dashboard.exchange_type_box.setCurrentText("futures")
    assert _combo_texts(dashboard.exchange_box) == ["ibkr", "amp", "tradovate"]

    dashboard.exchange_type_box.setCurrentText("derivatives")
    assert _combo_texts(dashboard.exchange_box) == ["ibkr", "schwab", "amp", "tradovate"]


def test_dashboard_exchange_lists_include_solana_for_crypto_profiles(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_make_controller())

    dashboard.exchange_type_box.setCurrentText("crypto")
    assert "solana" in _combo_texts(dashboard.exchange_box)

    dashboard.customer_region_box.setCurrentIndex(1)
    assert "solana" in _combo_texts(dashboard.exchange_box)


def test_supported_market_venues_cover_derivative_profiles():
    assert supported_market_venues_for_profile("options", "schwab") == ["auto", "option"]
    assert supported_market_venues_for_profile("futures", "tradovate") == ["auto", "derivative"]
    assert supported_market_venues_for_profile("derivatives", "ibkr") == ["auto", "derivative", "option"]


def test_supported_market_venues_mark_solana_as_spot_only():
    assert supported_market_venues_for_profile("crypto", "solana") == ["auto", "spot"]


def test_dashboard_connect_emits_schwab_oauth_fields_in_broker_options(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    controller = _make_controller()
    emitted = []

    dashboard = Dashboard(controller)
    dashboard.login_requested.connect(emitted.append)
    dashboard.exchange_type_box.setCurrentText("options")
    dashboard.exchange_box.setCurrentText("schwab")
    dashboard.mode_box.setCurrentText("paper")
    dashboard.api_input.setText("client-id")
    dashboard.secret_input.setText("client-secret")
    dashboard.password_input.setText("http://127.0.0.1:8182/callback")
    dashboard.account_id_input.setText("account-hash")

    dashboard._on_connect()

    assert len(emitted) == 1
    broker = emitted[0].broker
    assert broker.type == "options"
    assert broker.exchange == "schwab"
    assert broker.api_key == "client-id"
    assert broker.secret == "client-secret"
    assert broker.password == "http://127.0.0.1:8182/callback"
    assert broker.options["redirect_uri"] == "http://127.0.0.1:8182/callback"
    assert broker.options["environment"] == "sandbox"
    assert broker.options["account_hash"] == "account-hash"


def test_dashboard_load_selected_account_maps_derivative_profile_fields(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    monkeypatch.setattr(
        "frontend.ui.dashboard.CredentialManager.load_account",
        lambda _name: {
            "broker": {
                "type": "futures",
                "exchange": "tradovate",
                "mode": "paper",
                "password": "desk-pass",
                "options": {
                    "username": "desk-user",
                    "market_type": "derivative",
                },
                "api_key": "company-id",
                "secret": "security-code",
            },
            "risk": {"risk_percent": 1},
        },
    )
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.touch_account", lambda _name: None)
    controller = _make_controller()

    dashboard = Dashboard(controller)
    dashboard.saved_account_box.addItem("tradovate_main")
    dashboard.saved_account_box.setCurrentText("tradovate_main")

    dashboard._load_selected_account("tradovate_main")

    assert dashboard.exchange_type_box.currentText() == "futures"
    assert dashboard.exchange_box.currentText() == "tradovate"
    assert dashboard.api_input.text() == "desk-user"
    assert dashboard.secret_input.text() == "desk-pass"
    assert dashboard.password_input.text() == "company-id"
    assert dashboard.account_id_input.text() == "security-code"


def test_dashboard_solana_shows_dedicated_routing_fields(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_make_controller())

    dashboard.exchange_type_box.setCurrentText("crypto")
    dashboard.exchange_box.setCurrentText("solana")
    dashboard.mode_box.setCurrentText("paper")
    dashboard._update_optional_fields()

    assert dashboard.solana_credentials_panel.isHidden() is False
    assert dashboard._field_blocks["api"].isHidden() is True
    assert dashboard._field_blocks["secret"].isHidden() is True
    assert dashboard._field_blocks["solana_okx_api_key"].label_widget.text() == "OKX API Key"
    assert dashboard._field_blocks["solana_wallet_address"].label_widget.text() == "Wallet Address"


def test_dashboard_resolved_inputs_map_dedicated_solana_fields(monkeypatch):
    _get_app()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    dashboard = Dashboard(_make_controller())

    dashboard.exchange_type_box.setCurrentText("crypto")
    dashboard.exchange_box.setCurrentText("solana")
    dashboard.mode_box.setCurrentText("paper")
    dashboard.solana_wallet_address_input.setText("wallet-abc")
    dashboard.solana_private_key_input.setText("private-xyz")
    dashboard.solana_rpc_url_input.setText("https://rpc.example")
    dashboard.solana_jupiter_api_key_input.setText("legacy-jupiter")
    dashboard.solana_okx_api_key_input.setText("okx-key")
    dashboard.solana_okx_secret_input.setText("okx-secret")
    dashboard.solana_okx_passphrase_input.setText("okx-pass")
    dashboard.solana_okx_project_id_input.setText("project-1")

    resolved = dashboard._resolved_broker_inputs()

    assert resolved["api_key"] == "okx-key"
    assert resolved["secret"] == "okx-secret"
    assert resolved["password"] == "okx-pass"
    assert resolved["account_id"] == "project-1"
    assert resolved["options"]["wallet_address"] == "wallet-abc"
    assert resolved["options"]["private_key"] == "private-xyz"
    assert resolved["options"]["rpc_url"] == "https://rpc.example"
    assert resolved["options"]["jupiter_api_key"] == "legacy-jupiter"


def test_dashboard_load_selected_account_restores_new_solana_fields(monkeypatch):
    _get_app()
    wallet = _make_solana_wallet()
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    monkeypatch.setattr(
        "frontend.ui.dashboard.CredentialManager.load_account",
        lambda _name: {
            "broker": {
                "type": "crypto",
                "exchange": "solana",
                "mode": "paper",
                "api_key": "okx-key",
                "secret": "okx-secret",
                "password": "okx-pass",
                "account_id": "project-1",
                "options": {
                    "wallet_address": wallet["wallet"],
                    "private_key": wallet["secret"],
                    "rpc_url": "https://rpc.example",
                    "jupiter_api_key": "legacy-jupiter",
                },
            },
            "risk": {"risk_percent": 2},
        },
    )
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.touch_account", lambda _name: None)
    dashboard = Dashboard(_make_controller())
    dashboard.saved_account_box.addItem("solana_okx")
    dashboard.saved_account_box.setCurrentText("solana_okx")

    dashboard._load_selected_account("solana_okx")

    assert dashboard.exchange_box.currentText() == "solana"
    assert dashboard.solana_wallet_address_input.text() == wallet["wallet"]
    assert dashboard.solana_private_key_input.text() == wallet["secret"]
    assert dashboard.solana_rpc_url_input.text() == "https://rpc.example"
    assert dashboard.solana_jupiter_api_key_input.text() == "legacy-jupiter"
    assert dashboard.solana_okx_api_key_input.text() == "okx-key"
    assert dashboard.solana_okx_secret_input.text() == "okx-secret"
    assert dashboard.solana_okx_passphrase_input.text() == "okx-pass"
    assert dashboard.solana_okx_project_id_input.text() == "project-1"


def test_dashboard_load_selected_account_migrates_legacy_solana_fields(monkeypatch):
    _get_app()
    wallet = _make_solana_wallet(seed_byte=22)
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.list_accounts", lambda: [])
    monkeypatch.setattr(
        "frontend.ui.dashboard.CredentialManager.load_account",
        lambda _name: {
            "broker": {
                "type": "crypto",
                "exchange": "solana",
                "mode": "paper",
                "api_key": wallet["wallet"],
                "secret": wallet["secret"],
                "password": "legacy-jupiter",
                "options": {
                    "rpc_url": "https://legacy-rpc.example",
                },
            },
            "risk": {"risk_percent": 2},
        },
    )
    monkeypatch.setattr("frontend.ui.dashboard.CredentialManager.touch_account", lambda _name: None)
    dashboard = Dashboard(_make_controller())
    dashboard.saved_account_box.addItem("solana_legacy")
    dashboard.saved_account_box.setCurrentText("solana_legacy")

    dashboard._load_selected_account("solana_legacy")

    assert dashboard.exchange_box.currentText() == "solana"
    assert dashboard.solana_wallet_address_input.text() == wallet["wallet"]
    assert dashboard.solana_private_key_input.text() == wallet["secret"]
    assert dashboard.solana_rpc_url_input.text() == "https://legacy-rpc.example"
    assert dashboard.solana_jupiter_api_key_input.text() == "legacy-jupiter"
    assert dashboard.solana_okx_api_key_input.text() == ""
    assert dashboard.solana_okx_secret_input.text() == ""
