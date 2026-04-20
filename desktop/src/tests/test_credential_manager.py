import json
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from keyring.errors import NoKeyringError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config.credential_manager as credential_manager_module
from config.credential_manager import CredentialManager
from security.credential_manager import FileCredentialManager
from security.encryption import EncryptionManager


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def get_password(self, service, username):
        return self.store.get((service, username))

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


class FailingKeyring:
    def get_password(self, service, username):
        raise NoKeyringError("no backend")

    def set_password(self, service, username, password):
        raise NoKeyringError("no backend")

    def delete_password(self, service, username):
        raise NoKeyringError("no backend")


def test_save_account_moves_latest_profile_to_front(monkeypatch, tmp_path):
    fake_keyring = FakeKeyring()
    monkeypatch.setattr("config.credential_manager.keyring", fake_keyring)
    manager = FileCredentialManager(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "credentials_latest.json",
    )
    monkeypatch.setattr(credential_manager_module, "_credential_manager_instance", manager)

    CredentialManager.save_account("binanceus_abc123", {"broker": {"exchange": "binanceus"}})
    CredentialManager.save_account("stellar_GD37VD", {"broker": {"exchange": "stellar"}})

    accounts = CredentialManager.list_accounts()

    assert accounts == ["stellar_GD37VD", "binanceus_abc123"]


def test_touch_account_promotes_existing_profile(monkeypatch, tmp_path):
    fake_keyring = FakeKeyring()
    monkeypatch.setattr("config.credential_manager.keyring", fake_keyring)
    manager = FileCredentialManager(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "credentials_touch.json",
    )
    monkeypatch.setattr(credential_manager_module, "_credential_manager_instance", manager)

    CredentialManager.save_account("binanceus_abc123", {"broker": {"exchange": "binanceus"}})
    CredentialManager.save_account("stellar_GD37VD", {"broker": {"exchange": "stellar"}})
    CredentialManager.touch_account("binanceus_abc123")

    accounts = CredentialManager.list_accounts()

    assert accounts == ["binanceus_abc123", "stellar_GD37VD"]


def test_save_account_encrypts_broker_credentials(monkeypatch, tmp_path):
    fake_keyring = FakeKeyring()
    monkeypatch.setattr("config.credential_manager.keyring", fake_keyring)
    manager = FileCredentialManager(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "credentials.json",
    )
    monkeypatch.setattr(credential_manager_module, "_credential_manager_instance", manager)

    CredentialManager.save_account(
        "coinbase_main",
        {
            "broker": {
                "exchange": "coinbase",
                "api_key": "organizations/test/apiKeys/key-1",
                "secret": "-----BEGIN EC PRIVATE KEY-----\nABCDEF1234567890ABCDEF1234567890\n-----END EC PRIVATE KEY-----\n",
            }
        },
    )

    raw_store = json.loads(manager.path.read_text(encoding="utf-8"))
    payload = raw_store["accounts"]["coinbase_main"]["broker"]

    assert payload["api_key"] != "organizations/test/apiKeys/key-1"
    assert "BEGIN EC PRIVATE KEY" not in payload["secret"]
    loaded = CredentialManager.load_account("coinbase_main")
    assert loaded["broker"]["api_key"] == "organizations/test/apiKeys/key-1"


def test_list_accounts_migrates_legacy_keyring_profiles(monkeypatch, tmp_path):
    fake_keyring = FakeKeyring()
    monkeypatch.setattr("config.credential_manager.keyring", fake_keyring)
    manager = FileCredentialManager(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "credentials.json",
    )
    monkeypatch.setattr(credential_manager_module, "_credential_manager_instance", manager)

    fake_keyring.set_password(
        CredentialManager.SERVICE_NAME,
        "coinbase_main",
        json.dumps({"broker": {"exchange": "coinbase", "api_key": "organizations/test/apiKeys/key-1", "secret": "pem-value"}}),
    )
    fake_keyring.set_password(
        CredentialManager.SERVICE_NAME,
        CredentialManager.ACCOUNT_INDEX,
        json.dumps(["coinbase_main"]),
    )

    accounts = CredentialManager.list_accounts()

    assert accounts == ["coinbase_main"]
    loaded = CredentialManager.load_account("coinbase_main")
    assert loaded["broker"]["api_key"] == "organizations/test/apiKeys/key-1"
    assert fake_keyring.get_password(CredentialManager.SERVICE_NAME, "coinbase_main") is None


def test_list_accounts_ignores_missing_system_keyring_backend(monkeypatch, tmp_path):
    manager = FileCredentialManager(
        encryption=EncryptionManager(Fernet.generate_key()),
        path=tmp_path / "credentials.json",
    )
    manager.save_account("paper_demo", {"broker": {"exchange": "paper"}})
    monkeypatch.setattr("config.credential_manager.keyring", FailingKeyring())
    monkeypatch.setattr(credential_manager_module, "_credential_manager_instance", manager)
    monkeypatch.setattr(credential_manager_module, "_legacy_keyring_disabled", False)

    printed = []
    monkeypatch.setattr(credential_manager_module.traceback, "print_exc", lambda: printed.append("traceback"))

    accounts = CredentialManager.list_accounts()

    assert accounts == ["paper_demo"]
    assert printed == []
    assert credential_manager_module._legacy_keyring_disabled is True
