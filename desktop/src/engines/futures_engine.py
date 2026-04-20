from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from models.instrument import Instrument, InstrumentType
from models.position import Position


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


class FuturesEngine:
    def __init__(self, brokers=None, *, default_roll_days: int = 5):
        if brokers is None:
            self.brokers = []
        elif isinstance(brokers, Mapping):
            self.brokers = list(brokers.values())
        elif isinstance(brokers, Iterable):
            self.brokers = list(brokers)
        else:
            self.brokers = [brokers]
        self.default_roll_days = max(1, int(default_roll_days))
        self._metadata_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _select_broker(self, broker=None):
        if broker is not None:
            return broker
        for candidate in self.brokers:
            if hasattr(candidate, "supports_instrument_type") and candidate.supports_instrument_type(InstrumentType.FUTURE.value):
                return candidate
        raise RuntimeError("No futures-capable broker is configured")

    async def get_contract_metadata(self, symbol, broker=None, *, refresh: bool = False, **kwargs):
        selected_broker = self._select_broker(broker)
        cache_key = (getattr(selected_broker, "exchange_name", selected_broker.__class__.__name__), str(symbol).strip().upper())
        if not refresh and cache_key in self._metadata_cache:
            return dict(self._metadata_cache[cache_key])
        metadata = await selected_broker.get_contract_metadata(symbol, **kwargs)
        normalized = self.normalize_contract_metadata(symbol, metadata)
        self._metadata_cache[cache_key] = dict(normalized)
        return normalized

    def normalize_contract_metadata(self, symbol, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(metadata or {})
        return {
            "symbol": str(payload.get("symbol") or symbol).strip().upper(),
            "broker": payload.get("broker"),
            "exchange": payload.get("exchange"),
            "currency": payload.get("currency") or "USD",
            "tick_size": _safe_float(payload.get("tick_size", payload.get("tick", 0.0))),
            "multiplier": _safe_float(payload.get("multiplier", payload.get("contract_size", 1.0)), 1.0),
            "initial_margin": _safe_float(payload.get("initial_margin", payload.get("margin", 0.0))),
            "maintenance_margin": _safe_float(payload.get("maintenance_margin", 0.0)),
            "expiry": payload.get("expiry"),
            "last_trade_at": payload.get("last_trade_at"),
            "raw": payload.get("raw", payload),
        }

    def notional_exposure(self, *, quantity: float, price: float, multiplier: float) -> float:
        return abs(_safe_float(quantity, 0.0) * _safe_float(price, 0.0) * _safe_float(multiplier, 1.0))

    def margin_required(self, *, quantity: float, metadata: Mapping[str, Any], price: Optional[float] = None) -> float:
        base_margin = _safe_float(metadata.get("initial_margin", 0.0))
        if base_margin > 0:
            return abs(_safe_float(quantity, 0.0)) * base_margin
        if price is None:
            return 0.0
        notional = self.notional_exposure(quantity=quantity, price=price, multiplier=_safe_float(metadata.get("multiplier", 1.0), 1.0))
        fallback_margin_rate = _safe_float(metadata.get("margin_rate", 0.1), 0.1)
        return notional * fallback_margin_rate

    def maintenance_margin_required(self, *, quantity: float, metadata: Mapping[str, Any], price: Optional[float] = None) -> float:
        maintenance = _safe_float(metadata.get("maintenance_margin", 0.0))
        if maintenance > 0:
            return abs(_safe_float(quantity, 0.0)) * maintenance
        return self.margin_required(quantity=quantity, metadata=metadata, price=price)

    def leverage(self, *, account_equity: float, quantity: float, price: float, multiplier: float) -> float:
        equity = max(_safe_float(account_equity, 0.0), 0.0)
        if equity <= 0:
            return 0.0
        return self.notional_exposure(quantity=quantity, price=price, multiplier=multiplier) / equity

    def liquidation_threshold(
        self,
        *,
        account_equity: float,
        used_margin: float,
        maintenance_margin: float,
        buffer_pct: float = 0.1,
    ) -> dict[str, float]:
        equity = max(_safe_float(account_equity, 0.0), 0.0)
        margin = max(_safe_float(used_margin, 0.0), 0.0)
        maintenance = max(_safe_float(maintenance_margin, 0.0), 0.0)
        trigger_equity = maintenance * (1.0 + max(_safe_float(buffer_pct, 0.0), 0.0))
        cushion = equity - trigger_equity
        return {
            "equity": equity,
            "used_margin": margin,
            "maintenance_margin": maintenance,
            "trigger_equity": trigger_equity,
            "cushion": cushion,
            "margin_call_risk": 1.0 if equity <= 0 else max(0.0, min(1.0, 1.0 - (cushion / max(equity, 1e-9)))),
        }

    def should_roll_contract(
        self,
        metadata: Mapping[str, Any],
        *,
        as_of: Optional[datetime] = None,
        roll_days_before_expiry: Optional[int] = None,
    ) -> bool:
        reference_time = as_of or datetime.now(timezone.utc)
        expiry = _safe_datetime(metadata.get("expiry") or metadata.get("last_trade_at"))
        if expiry is None:
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        roll_days = self.default_roll_days if roll_days_before_expiry is None else max(1, int(roll_days_before_expiry))
        return reference_time >= expiry - timedelta(days=roll_days)

    def next_contract(self, contracts: Iterable[Mapping[str, Any]], *, as_of: Optional[datetime] = None) -> Optional[dict[str, Any]]:
        reference_time = as_of or datetime.now(timezone.utc)
        valid_contracts = []
        for contract in contracts:
            expiry = _safe_datetime(contract.get("expiry") or contract.get("last_trade_at"))
            if expiry is None:
                continue
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry >= reference_time:
                valid_contracts.append((expiry, dict(contract)))
        if not valid_contracts:
            return None
        valid_contracts.sort(key=lambda item: item[0])
        return valid_contracts[0][1]

    def rollover_plan(
        self,
        current_contract: Mapping[str, Any],
        available_contracts: Iterable[Mapping[str, Any]],
        *,
        as_of: Optional[datetime] = None,
        roll_days_before_expiry: Optional[int] = None,
    ) -> dict[str, Any]:
        current = self.normalize_contract_metadata(current_contract.get("symbol"), current_contract)
        should_roll = self.should_roll_contract(current, as_of=as_of, roll_days_before_expiry=roll_days_before_expiry)
        next_contract = self.next_contract(
            [contract for contract in available_contracts if str(contract.get("symbol") or "").upper() != current["symbol"]],
            as_of=as_of,
        )
        return {
            "current_contract": current,
            "should_roll": should_roll,
            "next_contract": next_contract,
            "generated_at": (as_of or datetime.now(timezone.utc)).isoformat(),
        }

    def position_metrics(
        self,
        position: Position | Mapping[str, Any],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
        account_equity: Optional[float] = None,
    ) -> dict[str, Any]:
        normalized_position = position if isinstance(position, Position) else Position.from_mapping(position)
        instrument = normalized_position.instrument or Instrument(
            symbol=normalized_position.symbol,
            type=InstrumentType.FUTURE,
            contract_size=1,
        )
        multiplier = _safe_float(
            (metadata or {}).get("multiplier", instrument.contract_size or instrument.multiplier or 1.0),
            instrument.contract_size or instrument.multiplier or 1.0,
        )
        mark_price = normalized_position.mark_price if normalized_position.mark_price is not None else normalized_position.avg_price
        notional = self.notional_exposure(quantity=normalized_position.quantity, price=mark_price, multiplier=multiplier)
        margin_used = normalized_position.margin_used or self.margin_required(
            quantity=normalized_position.quantity,
            metadata=metadata or {"multiplier": multiplier},
            price=mark_price,
        )
        leverage = normalized_position.leverage
        if leverage is None and account_equity is not None:
            leverage = self.leverage(
                account_equity=account_equity,
                quantity=normalized_position.quantity,
                price=mark_price,
                multiplier=multiplier,
            )
        return {
            "symbol": normalized_position.symbol,
            "quantity": normalized_position.quantity,
            "mark_price": mark_price,
            "multiplier": multiplier,
            "notional_exposure": notional,
            "margin_used": margin_used,
            "leverage": leverage,
            "liquidation_price": normalized_position.liquidation_price,
        }
