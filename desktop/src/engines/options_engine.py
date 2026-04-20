from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from models.instrument import Instrument, InstrumentType, OptionRight
from models.order import Order, OrderLeg, OrderSide, OrderType


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


class OptionsEngine:
    def __init__(self, brokers=None, *, risk_free_rate: float = 0.02, default_volatility: float = 0.25):
        if brokers is None:
            self.brokers = []
        elif isinstance(brokers, Mapping):
            self.brokers = list(brokers.values())
        elif isinstance(brokers, Iterable):
            self.brokers = list(brokers)
        else:
            self.brokers = [brokers]
        self.risk_free_rate = float(risk_free_rate)
        self.default_volatility = max(0.0001, float(default_volatility))

    def _select_broker(self, broker=None):
        if broker is not None:
            return broker
        for candidate in self.brokers:
            if hasattr(candidate, "supports_instrument_type") and candidate.supports_instrument_type(InstrumentType.OPTION.value):
                return candidate
        raise RuntimeError("No options-capable broker is configured")

    @staticmethod
    def _normal_pdf(value: float) -> float:
        return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)

    @staticmethod
    def _normal_cdf(value: float) -> float:
        return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))

    def time_to_expiry(self, expiry: Any, *, as_of: Optional[datetime] = None) -> float:
        expiry_dt = _safe_datetime(expiry)
        if expiry_dt is None:
            return 0.0
        now = as_of or datetime.now(timezone.utc)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        seconds = max((expiry_dt - now).total_seconds(), 0.0)
        return max(seconds / (365.0 * 24.0 * 60.0 * 60.0), 0.0)

    def compute_greeks(
        self,
        *,
        underlying_price: float,
        strike: float,
        expiry: Any,
        option_type: str | OptionRight,
        volatility: Optional[float] = None,
        risk_free_rate: Optional[float] = None,
        contract_size: int = 100,
        as_of: Optional[datetime] = None,
    ) -> dict[str, float]:
        spot = max(_safe_float(underlying_price, 0.0), 0.0)
        strike_price = max(_safe_float(strike, 0.0), 0.0)
        rate = self.risk_free_rate if risk_free_rate is None else _safe_float(risk_free_rate, self.risk_free_rate)
        sigma = max(_safe_float(volatility, self.default_volatility), 0.0001)
        time_to_expiry = self.time_to_expiry(expiry, as_of=as_of)
        right = option_type if isinstance(option_type, OptionRight) else OptionRight(str(option_type).strip().lower())

        if spot <= 0 or strike_price <= 0 or time_to_expiry <= 0:
            intrinsic = max(spot - strike_price, 0.0) if right is OptionRight.CALL else max(strike_price - spot, 0.0)
            delta = 1.0 if right is OptionRight.CALL and spot > strike_price else -1.0 if right is OptionRight.PUT and strike_price > spot else 0.0
            return {
                "price": intrinsic * contract_size,
                "delta": delta * contract_size,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
            }

        sqrt_t = math.sqrt(time_to_expiry)
        d1 = (math.log(spot / strike_price) + (rate + 0.5 * sigma * sigma) * time_to_expiry) / (sigma * sqrt_t)
        d2 = d1 - sigma * sqrt_t
        nd1 = self._normal_pdf(d1)
        direction = 1.0 if right is OptionRight.CALL else -1.0

        if right is OptionRight.CALL:
            option_price = spot * self._normal_cdf(d1) - strike_price * math.exp(-rate * time_to_expiry) * self._normal_cdf(d2)
            delta = self._normal_cdf(d1)
            rho = strike_price * time_to_expiry * math.exp(-rate * time_to_expiry) * self._normal_cdf(d2)
            theta = (
                -(spot * nd1 * sigma) / (2.0 * sqrt_t)
                - rate * strike_price * math.exp(-rate * time_to_expiry) * self._normal_cdf(d2)
            )
        else:
            option_price = strike_price * math.exp(-rate * time_to_expiry) * self._normal_cdf(-d2) - spot * self._normal_cdf(-d1)
            delta = self._normal_cdf(d1) - 1.0
            rho = -strike_price * time_to_expiry * math.exp(-rate * time_to_expiry) * self._normal_cdf(-d2)
            theta = (
                -(spot * nd1 * sigma) / (2.0 * sqrt_t)
                + rate * strike_price * math.exp(-rate * time_to_expiry) * self._normal_cdf(-d2)
            )

        gamma = nd1 / (spot * sigma * sqrt_t)
        vega = spot * nd1 * sqrt_t
        return {
            "price": option_price * contract_size,
            "delta": delta * contract_size,
            "gamma": gamma * contract_size,
            "theta": theta * contract_size / 365.0,
            "vega": vega * contract_size / 100.0,
            "rho": rho * contract_size / 100.0,
            "direction": direction,
        }

    def normalize_option_chain(self, chain: Mapping[str, Any] | list[Mapping[str, Any]]) -> dict[str, Any]:
        payload = chain if isinstance(chain, Mapping) else {"contracts": list(chain or [])}
        contracts = []
        for raw_contract in list(payload.get("contracts") or []):
            instrument_payload = raw_contract.get("instrument") or raw_contract
            instrument = Instrument.from_mapping(instrument_payload)
            if instrument.type is not InstrumentType.OPTION:
                instrument = Instrument(
                    symbol=instrument.symbol,
                    type=InstrumentType.OPTION,
                    expiry=instrument.expiry,
                    strike=instrument.strike,
                    option_type=instrument.option_type,
                    contract_size=instrument.contract_size or 100,
                    exchange=instrument.exchange,
                    currency=instrument.currency,
                    multiplier=instrument.multiplier or instrument.contract_size or 100,
                    underlying=instrument.underlying,
                    metadata=instrument.metadata,
                )
            contracts.append(
                {
                    "instrument": instrument.to_dict(),
                    "symbol": instrument.symbol,
                    "expiry": instrument.expiry.isoformat() if instrument.expiry else None,
                    "strike": instrument.strike,
                    "option_type": instrument.option_type.value if instrument.option_type else None,
                    "bid": _safe_float(raw_contract.get("bid", 0.0)),
                    "ask": _safe_float(raw_contract.get("ask", 0.0)),
                    "last": _safe_float(raw_contract.get("last", raw_contract.get("mark", 0.0))),
                    "mark": _safe_float(raw_contract.get("mark", raw_contract.get("last", 0.0))),
                    "volume": int(_safe_float(raw_contract.get("volume", 0.0))),
                    "open_interest": int(_safe_float(raw_contract.get("open_interest", raw_contract.get("openInterest", 0.0)))),
                    "delta": _safe_float(raw_contract.get("delta", 0.0)),
                    "gamma": _safe_float(raw_contract.get("gamma", 0.0)),
                    "theta": _safe_float(raw_contract.get("theta", 0.0)),
                    "vega": _safe_float(raw_contract.get("vega", 0.0)),
                    "broker": raw_contract.get("broker") or payload.get("broker"),
                    "raw": dict(raw_contract),
                }
            )
        return {
            "broker": payload.get("broker"),
            "symbol": str(payload.get("symbol") or "").strip().upper(),
            "underlying_price": _safe_float(payload.get("underlying_price", 0.0)),
            "interest_rate": _safe_float(payload.get("interest_rate", self.risk_free_rate)),
            "volatility": _safe_float(payload.get("volatility", self.default_volatility)),
            "updated_at": payload.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            "contracts": contracts,
            "raw": dict(payload) if isinstance(payload, Mapping) else {"contracts": contracts},
        }

    async def get_option_chain(self, symbol, broker=None, **kwargs):
        selected_broker = self._select_broker(broker)
        chain = await selected_broker.get_option_chain(symbol, **kwargs)
        normalized = self.normalize_option_chain(chain)
        if normalized["contracts"]:
            return normalized
        raise RuntimeError(f"No option contracts returned for {symbol}")

    def enrich_contract_with_greeks(
        self,
        contract: Mapping[str, Any],
        *,
        underlying_price: float,
        risk_free_rate: Optional[float] = None,
        volatility: Optional[float] = None,
        as_of: Optional[datetime] = None,
    ) -> dict[str, Any]:
        instrument = Instrument.from_mapping(contract.get("instrument") or contract)
        if instrument.option_type is None or instrument.strike is None or instrument.expiry is None:
            return dict(contract)
        greeks = self.compute_greeks(
            underlying_price=underlying_price,
            strike=instrument.strike,
            expiry=instrument.expiry,
            option_type=instrument.option_type,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
            contract_size=instrument.contract_size or int(instrument.multiplier or 100),
            as_of=as_of,
        )
        enriched = dict(contract)
        enriched.update(greeks)
        return enriched

    def enrich_chain_with_greeks(
        self,
        chain: Mapping[str, Any] | list[Mapping[str, Any]],
        *,
        underlying_price: Optional[float] = None,
        risk_free_rate: Optional[float] = None,
        volatility: Optional[float] = None,
        as_of: Optional[datetime] = None,
    ) -> dict[str, Any]:
        normalized = self.normalize_option_chain(chain)
        chain_underlying = underlying_price if underlying_price is not None else normalized.get("underlying_price")
        updated_contracts = [
            self.enrich_contract_with_greeks(
                contract,
                underlying_price=chain_underlying,
                risk_free_rate=risk_free_rate or normalized.get("interest_rate"),
                volatility=volatility or normalized.get("volatility"),
                as_of=as_of,
            )
            for contract in normalized["contracts"]
        ]
        normalized["contracts"] = updated_contracts
        return normalized

    def _root_symbol(self, contract: Mapping[str, Any]) -> str:
        return Instrument.from_mapping(contract.get("instrument") or contract).root_symbol

    def build_vertical_spread(
        self,
        long_contract: Mapping[str, Any],
        short_contract: Mapping[str, Any],
        *,
        quantity: float = 1.0,
        limit_price: Optional[float] = None,
        strategy_name: str = "vertical_spread",
    ) -> Order:
        long_instrument = Instrument.from_mapping(long_contract.get("instrument") or long_contract)
        short_instrument = Instrument.from_mapping(short_contract.get("instrument") or short_contract)
        return Order(
            symbol=self._root_symbol(long_contract),
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT if limit_price is not None else OrderType.MARKET,
            price=limit_price,
            instrument=long_instrument,
            strategy_name=strategy_name,
            legs=[
                OrderLeg(instrument=long_instrument, side=OrderSide.BUY, quantity=quantity),
                OrderLeg(instrument=short_instrument, side=OrderSide.SELL, quantity=quantity),
            ],
            params={"complex_order_strategy": "VERTICAL"},
        )

    def build_straddle(
        self,
        call_contract: Mapping[str, Any],
        put_contract: Mapping[str, Any],
        *,
        quantity: float = 1.0,
        limit_price: Optional[float] = None,
        strategy_name: str = "straddle",
    ) -> Order:
        call_instrument = Instrument.from_mapping(call_contract.get("instrument") or call_contract)
        put_instrument = Instrument.from_mapping(put_contract.get("instrument") or put_contract)
        return Order(
            symbol=self._root_symbol(call_contract),
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT if limit_price is not None else OrderType.MARKET,
            price=limit_price,
            instrument=call_instrument,
            strategy_name=strategy_name,
            legs=[
                OrderLeg(instrument=call_instrument, side=OrderSide.BUY, quantity=quantity),
                OrderLeg(instrument=put_instrument, side=OrderSide.BUY, quantity=quantity),
            ],
            params={"complex_order_strategy": "STRADDLE"},
        )

    def build_iron_condor(
        self,
        long_put: Mapping[str, Any],
        short_put: Mapping[str, Any],
        short_call: Mapping[str, Any],
        long_call: Mapping[str, Any],
        *,
        quantity: float = 1.0,
        limit_price: Optional[float] = None,
        strategy_name: str = "iron_condor",
    ) -> Order:
        long_put_instrument = Instrument.from_mapping(long_put.get("instrument") or long_put)
        short_put_instrument = Instrument.from_mapping(short_put.get("instrument") or short_put)
        short_call_instrument = Instrument.from_mapping(short_call.get("instrument") or short_call)
        long_call_instrument = Instrument.from_mapping(long_call.get("instrument") or long_call)
        return Order(
            symbol=self._root_symbol(short_call),
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=OrderType.LIMIT if limit_price is not None else OrderType.MARKET,
            price=limit_price,
            instrument=short_call_instrument,
            strategy_name=strategy_name,
            legs=[
                OrderLeg(instrument=long_put_instrument, side=OrderSide.BUY, quantity=quantity),
                OrderLeg(instrument=short_put_instrument, side=OrderSide.SELL, quantity=quantity),
                OrderLeg(instrument=short_call_instrument, side=OrderSide.SELL, quantity=quantity),
                OrderLeg(instrument=long_call_instrument, side=OrderSide.BUY, quantity=quantity),
            ],
            params={"complex_order_strategy": "IRON_CONDOR"},
        )
