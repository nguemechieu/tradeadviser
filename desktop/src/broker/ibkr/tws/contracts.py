from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from broker.ibkr.mapper import IBKRMapper
from broker.ibkr.models import IBKRContract


def build_tws_contract(contract: IBKRContract | Mapping[str, Any]) -> dict[str, Any]:
    mapper = IBKRMapper()
    normalized = contract if isinstance(contract, IBKRContract) else mapper.contract_from_payload(contract)
    return {
        "symbol": normalized.symbol,
        "secType": normalized.sec_type,
        "exchange": normalized.exchange,
        "primaryExchange": normalized.primary_exchange,
        "currency": normalized.currency,
        "localSymbol": normalized.local_symbol,
        "lastTradeDateOrContractMonth": normalized.expiry,
        "strike": normalized.strike,
        "right": normalized.right,
        "multiplier": normalized.multiplier,
        "tradingClass": normalized.trading_class,
        "conid": normalized.conid,
    }
