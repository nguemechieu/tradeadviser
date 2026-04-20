from __future__ import annotations

import logging

from broker.ibkr.models import IBKRSessionStatus
from broker.ibkr.webapi import endpoints


class IBKRWebApiAuthenticator:
    """Bootstrap and refresh the brokerage session behind the Client Portal API."""

    def __init__(self, session, *, logger: logging.Logger | None = None) -> None:
        self.session = session
        self.logger = logger or logging.getLogger("IBKRWebApiAuthenticator")

    async def status(self) -> dict:
        payload = await self.session.request_json("GET", endpoints.AUTH_STATUS, expected_statuses=(200,))
        authenticated = bool(payload.get("authenticated"))
        connected = bool(payload.get("connected") or payload.get("competing") is False)
        status = IBKRSessionStatus.AUTHENTICATED if authenticated else IBKRSessionStatus.CONNECTED if connected else IBKRSessionStatus.CONNECTING
        self.session.update_state(
            status=status,
            authenticated=authenticated,
            connected=connected or self.session.state.connected,
            last_error="",
        )
        return dict(payload or {})

    async def refresh(self) -> dict:
        try:
            await self.session.request_json("GET", endpoints.TICKLE, expected_statuses=(200,))
        except Exception:
            self.logger.debug("IBKR tickle failed", exc_info=True)
        try:
            await self.session.request_json("GET", endpoints.VALIDATE_SSO, expected_statuses=(200,))
        except Exception:
            self.logger.debug("IBKR SSO validate failed", exc_info=True)
        try:
            await self.session.request_json("POST", endpoints.REAUTHENTICATE, expected_statuses=(200, 202))
        except Exception:
            self.logger.debug("IBKR reauthenticate failed", exc_info=True)
        return await self.status()

    async def bootstrap(self) -> dict:
        self.session.update_state(status=IBKRSessionStatus.AUTHENTICATING)
        status = await self.status()
        if bool(status.get("authenticated")):
            return status
        return await self.refresh()
