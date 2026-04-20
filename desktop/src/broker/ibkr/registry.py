from __future__ import annotations

from typing import Any

from broker.ibkr.config import IBKRConfig, build_ibkr_config
from broker.ibkr.models import IBKRTransport
from broker.ibkr.validators import validate_ibkr_config


def resolve_ibkr_transport(config: Any) -> IBKRTransport:
    return validate_ibkr_config(build_ibkr_config(config)).transport


def create_ibkr_broker_adapter(
    config: Any,
    *,
    event_bus: Any = None,
    ibkr_config: IBKRConfig | None = None,
):
    resolved_config = validate_ibkr_config(ibkr_config or build_ibkr_config(config))
    if resolved_config.transport is IBKRTransport.WEBAPI:
        from broker.ibkr.webapi.broker import IBKRWebApiBroker

        return IBKRWebApiBroker(config, ibkr_config=resolved_config, event_bus=event_bus)

    from broker.ibkr.tws.broker import IBKRTwsBroker

    return IBKRTwsBroker(config, ibkr_config=resolved_config, event_bus=event_bus)
