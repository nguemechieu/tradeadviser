from __future__ import annotations

import logging

from broker.ibkr.config import IBKRTwsConfig
from broker.ibkr.models import IBKRSessionState, IBKRSessionStatus, IBKRTransport


class IBKRTwsSession:
    """Tracks TWS/IB Gateway connectivity and lifecycle state."""

    def __init__(self, config: IBKRTwsConfig, *, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("IBKRTwsSession")
        self.state = IBKRSessionState(
            transport=IBKRTransport.TWS,
            status=IBKRSessionStatus.DISCONNECTED,
            account_id=config.account_id,
            profile_name=config.profile_name,
        )

    def update_state(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        return self.state
