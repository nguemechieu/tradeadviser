import json
import keyring
import traceback
from keyring.errors import NoKeyringError

from security.credential_manager import FileCredentialManager


_credential_manager_instance = None
_legacy_keyring_disabled = False


class CredentialManager:

    SERVICE_NAME = "SopotekTradingAI"
    ACCOUNT_INDEX = "accounts_index"

    @staticmethod
    def _legacy_keyring_enabled():
        return not _legacy_keyring_disabled

    @staticmethod
    def _handle_legacy_keyring_exception(exc):
        global _legacy_keyring_disabled
        if isinstance(exc, NoKeyringError):
            _legacy_keyring_disabled = True
            return
        traceback.print_exc()

    @staticmethod
    def _manager():
        global _credential_manager_instance
        if _credential_manager_instance is None:
            _credential_manager_instance = FileCredentialManager()
        return _credential_manager_instance

    @staticmethod
    def _legacy_read_account_index():
        if not CredentialManager._legacy_keyring_enabled():
            return []
        try:
            data = keyring.get_password(
                CredentialManager.SERVICE_NAME,
                CredentialManager.ACCOUNT_INDEX
            )
            if not data:
                return []
            parsed = json.loads(data)
            return parsed if isinstance(parsed, list) else []
        except Exception as exc:
            CredentialManager._handle_legacy_keyring_exception(exc)
            return []

    @staticmethod
    def _legacy_write_account_index(accounts):
        if not CredentialManager._legacy_keyring_enabled():
            return
        try:
            keyring.set_password(
                CredentialManager.SERVICE_NAME,
                CredentialManager.ACCOUNT_INDEX,
                json.dumps(list(accounts or []))
            )
        except Exception as exc:
            CredentialManager._handle_legacy_keyring_exception(exc)

    @staticmethod
    def _legacy_load_account(account_name: str):
        if not CredentialManager._legacy_keyring_enabled():
            return None
        try:
            data = keyring.get_password(
                CredentialManager.SERVICE_NAME,
                account_name
            )
            if not data:
                return None
            return json.loads(data)
        except Exception as exc:
            CredentialManager._handle_legacy_keyring_exception(exc)
            return None

    @staticmethod
    def _legacy_delete_account(account_name):
        if not CredentialManager._legacy_keyring_enabled():
            return
        try:
            keyring.delete_password(
                CredentialManager.SERVICE_NAME,
                account_name
            )
        except Exception as exc:
            CredentialManager._handle_legacy_keyring_exception(exc)

    @staticmethod
    def _migrate_legacy_account(account_name):
        payload = CredentialManager._legacy_load_account(account_name)
        if payload is None:
            return None
        CredentialManager._manager().save_account(account_name, payload)
        CredentialManager._legacy_delete_account(account_name)
        accounts = [name for name in CredentialManager._legacy_read_account_index() if name != account_name]
        CredentialManager._legacy_write_account_index(accounts)
        return payload

    @staticmethod
    def _migrate_legacy_accounts():
        migrated = False
        manager = CredentialManager._manager()
        existing = set(manager.list_accounts())
        for account_name in CredentialManager._legacy_read_account_index():
            if account_name in existing:
                continue
            payload = CredentialManager._legacy_load_account(account_name)
            if payload is None:
                continue
            manager.save_account(account_name, payload)
            CredentialManager._legacy_delete_account(account_name)
            migrated = True
        if migrated:
            CredentialManager._legacy_write_account_index([])

    # =====================================================
    # SAVE ACCOUNT
    # =====================================================

    @staticmethod
    def save_account(account_name: str, config: dict):

        try:
            CredentialManager._manager().save_account(account_name, config)

        except Exception:
            traceback.print_exc()

    @staticmethod
    def touch_account(account_name: str):

        try:
            CredentialManager._migrate_legacy_accounts()
            if CredentialManager._manager().load_account(account_name) is None:
                CredentialManager._migrate_legacy_account(account_name)
            CredentialManager._manager().touch_account(account_name)

        except Exception:
            traceback.print_exc()

    # =====================================================
    # LOAD ACCOUNT
    # =====================================================

    @staticmethod
    def load_account(account_name: str):

        try:
            CredentialManager._migrate_legacy_accounts()
            account = CredentialManager._manager().load_account(account_name)
            if account is not None:
                return account
            return CredentialManager._migrate_legacy_account(account_name)

        except Exception:
            traceback.print_exc()

            return None

    # =====================================================
    # LIST ACCOUNTS
    # =====================================================

    @staticmethod
    def list_accounts():

        try:
            CredentialManager._migrate_legacy_accounts()
            return CredentialManager._manager().list_accounts()

        except Exception:
            traceback.print_exc()

            return []

    # =====================================================
    # DELETE ACCOUNT
    # =====================================================

    @staticmethod
    def delete_account(account_name):

        try:
            CredentialManager._manager().delete_account(account_name)
            CredentialManager._legacy_delete_account(account_name)
            accounts = [name for name in CredentialManager._legacy_read_account_index() if name != account_name]
            CredentialManager._legacy_write_account_index(accounts)

        except Exception:
            traceback.print_exc()

    # =====================================================
    # LEGACY SUPPORT
    # =====================================================

    @staticmethod
    def save_credentials(exchange, api_key, secret):

        config = {
            "broker": {
                "exchange": exchange,
                "api_key": api_key,
                "secret": secret
            }
        }

        CredentialManager.save_account(exchange, config)

    @staticmethod
    def load_credentials(exchange):

        config = CredentialManager.load_account(exchange)

        if not config:
            return None, None

        broker = config.get("broker", {})

        return broker.get("api_key"), broker.get("secret")

    @staticmethod
    def delete_credentials(exchange):

        CredentialManager.delete_account(exchange)
