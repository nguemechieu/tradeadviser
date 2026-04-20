from __future__ import annotations

import logging
from typing import Any

from broker.ibkr.config import build_ibkr_config
from broker.ibkr.registry import create_ibkr_broker_adapter
from broker.ibkr.validators import validate_ibkr_config


class IBKRBroker:
    """Facade that selects the appropriate IBKR transport adapter."""

    def __init__(self, config: Any, event_bus: Any = None) -> None:
        self.config = config
        self.event_bus = event_bus
        self.exchange_name = "ibkr"
        self.mode = str(getattr(config, "mode", "paper") or "paper").strip().lower() or "paper"
        self.logger = logging.getLogger("IBKRBroker")
        self.controller = None
        self._ibkr_config = validate_ibkr_config(build_ibkr_config(config))
        self._delegate = create_ibkr_broker_adapter(
            config,
            event_bus=event_bus,
            ibkr_config=self._ibkr_config,
        )
        self._delegate.logger = self.logger.getChild(self._ibkr_config.transport.value)

    @property
    def transport(self) -> str:
        return self._ibkr_config.transport.value

    @property
    def ibkr_config(self):
        return self._ibkr_config

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        delegate = self.__dict__.get("_delegate")
        if delegate is None:
            return
        if name in {"logger", "controller", "event_bus"}:
            setattr(delegate, name, value)

    def __repr__(self) -> str:
        return f"IBKRBroker(transport={self.transport!r}, mode={self.mode!r})"
