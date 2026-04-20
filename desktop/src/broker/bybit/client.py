from __future__ import annotations

from types import SimpleNamespace

from broker.ccxt_broker import CCXTBroker


def _coerce_config(config, *, exchange: str = "bybit", default_subtype: str = "swap"):
    options = dict(getattr(config, "options", None) or {})
    params = dict(getattr(config, "params", None) or {})
    options.setdefault("market_type", "derivative")
    options.setdefault("defaultSubType", options.get("defaultSubType") or params.get("defaultSubType") or default_subtype)
    return SimpleNamespace(
        exchange=exchange,
        api_key=getattr(config, "api_key", None),
        secret=getattr(config, "secret", None),
        password=getattr(config, "password", None),
        passphrase=getattr(config, "password", None),
        uid=getattr(config, "uid", None),
        account_id=getattr(config, "account_id", None),
        wallet=getattr(config, "wallet", None),
        mode=getattr(config, "mode", "live"),
        sandbox=getattr(config, "sandbox", False),
        timeout=int(getattr(config, "timeout_seconds", None) or getattr(config, "timeout", 30000) or 30000),
        options=options,
        params=params,
    )


class BybitBroker(CCXTBroker):
    def __init__(self, config) -> None:
        normalized = _coerce_config(config, exchange=str(getattr(config, "exchange", None) or "bybit").lower())
        super().__init__(normalized)
