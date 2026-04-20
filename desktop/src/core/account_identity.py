from __future__ import annotations

from typing import Any


def _normalized_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalized_exchange_name(*values: Any) -> str:
    return _normalized_text(*values).lower()


def _masked_account_label(*values: Any) -> str:
    text = _normalized_text(*values)
    if not text:
        return "Not set"
    if len(text) <= 18:
        return text
    return f"{text[:6]}...{text[-4:]}"


def _masked_sensitive_label(value: Any) -> str:
    text = _normalized_text(value)
    if not text:
        return "Not set"
    if len(text) <= 8:
        return f"{text[:2]}...{text[-2:]}" if len(text) > 4 else "****"
    return f"{text[:4]}...{text[-4:]}"


def _looks_like_project_identifier(value: Any) -> bool:
    text = _normalized_text(value).lower()
    if not text:
        return False
    return text.startswith("project") or text.startswith("proj-") or text.startswith("okx-project")


def resolve_account_label(broker: Any = None, broker_config: Any = None) -> str:
    broker_options = dict(getattr(broker, "options", None) or {}) if broker is not None else {}
    broker_params = dict(getattr(broker, "params", None) or {}) if broker is not None else {}
    config_options = dict(getattr(broker_config, "options", None) or {}) if broker_config is not None else {}
    config_params = dict(getattr(broker_config, "params", None) or {}) if broker_config is not None else {}
    broker_session_state = getattr(broker, "session_state", None) if broker is not None else None

    exchange_name = _normalized_exchange_name(
        getattr(broker, "exchange_name", None) if broker is not None else None,
        getattr(broker_config, "exchange", None) if broker_config is not None else None,
    )

    wallet_identity = _normalized_text(
        getattr(broker, "wallet_address", None) if broker is not None else None,
        getattr(broker_session_state, "wallet_address", None) if broker_session_state is not None else None,
        broker_options.get("wallet_address"),
        broker_params.get("wallet_address"),
        config_options.get("wallet_address"),
        config_params.get("wallet_address"),
        getattr(broker, "public_key", None) if broker is not None else None,
        broker_options.get("public_key"),
        config_options.get("public_key"),
        getattr(broker, "address", None) if broker is not None else None,
        broker_options.get("address"),
        config_options.get("address"),
    )
    account_id = _normalized_text(
        getattr(broker, "account_id", None) if broker is not None else None,
        getattr(broker_session_state, "account_id", None) if broker_session_state is not None else None,
        getattr(broker_config, "account_id", None) if broker_config is not None else None,
        broker_options.get("account_id"),
        broker_params.get("account_id"),
        config_options.get("account_id"),
        config_params.get("account_id"),
    )
    account_hash = _normalized_text(
        getattr(broker, "account_hash", None) if broker is not None else None,
        getattr(broker_session_state, "account_hash", None) if broker_session_state is not None else None,
        broker_options.get("account_hash"),
        broker_params.get("account_hash"),
        config_options.get("account_hash"),
        config_params.get("account_hash"),
    )
    profile_name = _normalized_text(
        getattr(broker, "profile_name", None) if broker is not None else None,
        broker_options.get("profile_name"),
        broker_params.get("profile_name"),
        config_options.get("profile_name"),
        config_params.get("profile_name"),
        getattr(broker, "username", None) if broker is not None else None,
        broker_options.get("username"),
        config_options.get("username"),
    )
    api_identity = _normalized_text(
        getattr(broker, "api_key", None) if broker is not None else None,
        getattr(broker_config, "api_key", None) if broker_config is not None else None,
        getattr(broker, "uid", None) if broker is not None else None,
        getattr(broker_config, "uid", None) if broker_config is not None else None,
        broker_options.get("api_key"),
        broker_params.get("api_key"),
        config_options.get("api_key"),
        config_params.get("api_key"),
        broker_options.get("apiKey"),
        broker_params.get("apiKey"),
        config_options.get("apiKey"),
        config_params.get("apiKey"),
        broker_options.get("uid"),
        broker_params.get("uid"),
        config_options.get("uid"),
        config_params.get("uid"),
        broker_options.get("client_id"),
        broker_params.get("client_id"),
        config_options.get("client_id"),
        config_params.get("client_id"),
    )

    if exchange_name == "solana" and wallet_identity:
        return _masked_account_label(wallet_identity)
    if wallet_identity and _looks_like_project_identifier(account_id):
        return _masked_account_label(wallet_identity)
    resolved = _masked_account_label(
        account_id,
        account_hash,
        wallet_identity,
        profile_name,
    )
    if resolved != "Not set":
        return resolved
    if api_identity:
        return _masked_sensitive_label(api_identity)
    return "Not set"
