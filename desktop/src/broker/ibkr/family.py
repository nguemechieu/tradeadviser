from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from broker.base_broker import BaseDerivativeBroker
from broker.ibkr.config import IBKRConfig, build_ibkr_config
from broker.ibkr.mapper import IBKRMapper
from broker.ibkr.models import IBKRContract, IBKROrderRequest


class IBKRBrokerFamilyAdapter(BaseDerivativeBroker):
    """Shared canonical surface for all Interactive Brokers transports.

    Web API and TWS remain separate transport implementations, but both use
    this family layer to normalize transport payloads into Sopotek's canonical
    broker model before strategy, risk, portfolio, UI, or reporting code sees
    them.
    """

    def __init__(self, config: Any, *, ibkr_config: IBKRConfig | None = None, event_bus: Any = None) -> None:
        super().__init__(config, event_bus=event_bus)
        self.exchange_name = "ibkr"
        self.ibkr_config = ibkr_config or build_ibkr_config(config)
        self.mapper = IBKRMapper()
        self.account_id = self.ibkr_config.account_id

    def _canonical_account_payload(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        return self.mapper.canonical_account(self.mapper.account_from_accounts_payload(raw))

    def _canonical_balance_payload(self, raw: Mapping[str, Any], *, account_id: str) -> dict[str, Any]:
        return self.mapper.canonical_balance(self.mapper.balance_from_summary(raw, account_id=account_id))

    def _canonical_position_payload(self, raw: Mapping[str, Any], *, account_id: str) -> dict[str, Any]:
        position = self.mapper.position_from_payload(raw, account_id=account_id)
        return self.mapper.canonical_position(position)

    def _canonical_quote_payload(
        self,
        raw: Mapping[str, Any],
        *,
        symbol: str | None = None,
        contract: IBKRContract | None = None,
    ) -> dict[str, Any]:
        quote = self.mapper.quote_from_snapshot(raw, symbol=symbol, contract=contract)
        return self.mapper.canonical_quote(quote)

    def _canonical_order_payload(
        self,
        raw: Mapping[str, Any],
        *,
        request: IBKROrderRequest,
    ) -> dict[str, Any]:
        response = self.mapper.order_response_from_payload(raw, request=request)
        return self.mapper.canonical_order_response(response)

    def _canonical_accounts(self, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [self._canonical_account_payload(row) for row in rows if isinstance(row, Mapping)]

    def _canonical_positions(self, rows: Iterable[Mapping[str, Any]], *, account_id: str) -> list[dict[str, Any]]:
        return [self._canonical_position_payload(row, account_id=account_id) for row in rows if isinstance(row, Mapping)]

    def _canonical_quotes(self, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        quotes = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol") or row.get("ticker") or row.get("localSymbol") or "").strip().upper() or None
            quotes.append(self._canonical_quote_payload(row, symbol=symbol))
        return quotes
