from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Optional

from models.instrument import Instrument, InstrumentType
from models.position import Position


class RiskEngine:
    def __init__(
        self,
        account_equity,
        max_portfolio_risk=0.1,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.1,
        max_gross_exposure_pct=2.0,
        max_margin_usage=0.5,
        futures_liquidation_buffer=0.15,
        max_gamma_exposure=10000.0,
        max_theta_decay_pct=0.03,
    ):
        self.account_equity = max(0.0, self._safe_float(account_equity, 10000.0))
        self.max_portfolio_risk = max(0.0, self._safe_float(max_portfolio_risk, 0.1))
        self.max_risk_per_trade = max(0.0, self._safe_float(max_risk_per_trade, 0.02))
        self.max_position_size_pct = max(0.0, self._safe_float(max_position_size_pct, 0.1))
        self.max_gross_exposure_pct = max(0.0, self._safe_float(max_gross_exposure_pct, 2.0))
        self.max_margin_usage = max(0.0, self._safe_float(max_margin_usage, 0.5))
        self.futures_liquidation_buffer = max(0.0, self._safe_float(futures_liquidation_buffer, 0.15))
        self.max_gamma_exposure = max(0.0, self._safe_float(max_gamma_exposure, 10000.0))
        self.max_theta_decay_pct = max(0.0, self._safe_float(max_theta_decay_pct, 0.03))

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def sync_equity(self, equity):
        value = self._safe_float(equity, self.account_equity)
        if value >= 0:
            self.account_equity = value

    def max_position_notional(self):
        return max(0.0, self.account_equity * self.max_position_size_pct)

    def max_position_quantity(self, price):
        trade_price = self._safe_float(price, 0.0)
        if trade_price <= 0:
            return 0.0
        return self.max_position_notional() / trade_price

    def _normalize_quote_to_account_rate(self, value):
        rate = self._safe_float(value, 1.0)
        return rate if rate > 0 else 1.0

    def risk_per_unit(self, entry_price, stop_price, quote_to_account_rate=1.0):
        entry = self._safe_float(entry_price, 0.0)
        stop = self._safe_float(stop_price, 0.0)
        if entry <= 0 or stop <= 0:
            return 0.0
        return abs(entry - stop) * self._normalize_quote_to_account_rate(quote_to_account_rate)

    def max_risk_quantity(self, entry_price, stop_price, quote_to_account_rate=1.0):
        risk_amount = self.account_equity * self.max_risk_per_trade
        if risk_amount <= 0:
            return 0.0
        risk_per_unit = self.risk_per_unit(
            entry_price,
            stop_price,
            quote_to_account_rate=quote_to_account_rate,
        )
        if risk_per_unit <= 0:
            return 0.0
        return risk_amount / risk_per_unit

    def stop_distance_pips(self, entry_price, stop_price, pip_size=None):
        pip_value = self._safe_float(pip_size, 0.0)
        if pip_value <= 0:
            return None
        distance = abs(self._safe_float(entry_price, 0.0) - self._safe_float(stop_price, 0.0))
        if distance <= 0:
            return None
        return distance / pip_value

    def adjust_trade(self, price, quantity, *, stop_price=None, quote_to_account_rate=1.0, pip_size=None, symbol=None):
        trade_price = self._safe_float(price, 0.0)
        requested_quantity = abs(self._safe_float(quantity, 0.0))
        if trade_price <= 0 or requested_quantity <= 0:
            return False, 0.0, "Invalid trade payload"

        requested_notional = trade_price * requested_quantity
        max_notional = self.max_position_notional()
        if max_notional <= 0:
            return False, 0.0, "Position size cap is zero"

        max_quantity = max_notional / trade_price
        limiting_reason = None
        limiting_quantity = max_quantity

        stop_value = self._safe_float(stop_price, 0.0)
        if stop_value > 0 and abs(stop_value - trade_price) > 1e-12:
            max_risk_quantity = self.max_risk_quantity(
                trade_price,
                stop_value,
                quote_to_account_rate=quote_to_account_rate,
            )
            if max_risk_quantity > 0 and max_risk_quantity < limiting_quantity:
                limiting_quantity = max_risk_quantity
                stop_distance_pips = self.stop_distance_pips(trade_price, stop_value, pip_size=pip_size)
                if stop_distance_pips is not None:
                    limiting_reason = (
                        f"Position size reduced to fit {self.max_risk_per_trade:.1%} max risk "
                        f"at {stop_distance_pips:.1f} pip stop"
                    )
                else:
                    limiting_reason = (
                        f"Position size reduced to fit {self.max_risk_per_trade:.1%} max risk "
                        "at the current stop distance"
                    )

        if requested_quantity <= limiting_quantity:
            return True, requested_quantity, "Approved"

        adjusted_quantity = limiting_quantity
        if adjusted_quantity <= 0:
            return False, 0.0, "Position size cap reduced trade to zero"

        return (
            True,
            adjusted_quantity,
            limiting_reason or f"Position size reduced to fit {self.max_position_size_pct:.1%} max position cap",
        )

    def validate_trade(self, price, quantity):
        approved, adjusted_quantity, reason = self.adjust_trade(price, quantity)
        if not approved:
            return False, reason
        if adjusted_quantity + 1e-12 < abs(self._safe_float(quantity, 0.0)):
            return False, "Position size too large"
        return True, reason

    def position_size(self, entry_price, stop_price, *, quote_to_account_rate=1.0, pip_size=None, symbol=None):
        risk_per_unit = self.risk_per_unit(
            entry_price,
            stop_price,
            quote_to_account_rate=quote_to_account_rate,
        )
        if risk_per_unit <= 0:
            return 0

        size = self.max_risk_quantity(
            entry_price,
            stop_price,
            quote_to_account_rate=quote_to_account_rate,
        )
        max_size = self.max_position_quantity(entry_price)
        if max_size > 0:
            size = min(size, max_size)
        return size

    def _normalize_positions(self, positions) -> list[Position]:
        normalized = []
        for position in list(positions or []):
            if isinstance(position, Position):
                normalized.append(position)
            elif isinstance(position, Mapping):
                normalized.append(Position.from_mapping(position))
        return normalized

    def portfolio_exposure(self, positions) -> float:
        return sum(position.notional_exposure() for position in self._normalize_positions(positions))

    def portfolio_exposure_ratio(self, positions) -> float:
        if self.account_equity <= 0:
            return 0.0
        return self.portfolio_exposure(positions) / self.account_equity

    def margin_usage(self, account_info: Optional[Mapping[str, Any]] = None, positions: Optional[Iterable[Mapping[str, Any]]] = None) -> dict[str, float]:
        account = dict(account_info or {})
        equity = max(self._safe_float(account.get("equity", self.account_equity), self.account_equity), 0.0)
        margin_used = self._safe_float(account.get("margin_used", account.get("marginUsed", 0.0)), 0.0)
        if margin_used <= 0 and positions is not None:
            margin_used = sum(position.margin_used for position in self._normalize_positions(positions))
        usage = margin_used / equity if equity > 0 else 0.0
        return {
            "equity": equity,
            "margin_used": margin_used,
            "margin_usage": usage,
            "available_margin": max(equity - margin_used, 0.0),
        }

    def option_greek_exposure(self, positions) -> dict[str, float]:
        totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        for position in self._normalize_positions(positions):
            instrument = position.instrument
            if instrument is None or instrument.type is not InstrumentType.OPTION:
                continue
            totals["delta"] += position.delta
            totals["gamma"] += position.gamma
            totals["theta"] += position.theta
            totals["vega"] += position.vega
        return totals

    def futures_liquidation_risk(self, positions, account_info: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        metrics = self.margin_usage(account_info=account_info, positions=positions)
        highest_risk = 0.0
        flagged = []
        for position in self._normalize_positions(positions):
            instrument = position.instrument
            if instrument is None or instrument.type is not InstrumentType.FUTURE:
                continue
            mark_price = position.mark_price if position.mark_price is not None else position.avg_price
            liquidation_price = position.liquidation_price
            if liquidation_price is None or mark_price <= 0:
                continue
            distance = abs(mark_price - liquidation_price) / mark_price
            risk_score = max(0.0, 1.0 - (distance / max(self.futures_liquidation_buffer, 1e-9)))
            highest_risk = max(highest_risk, risk_score)
            if distance <= self.futures_liquidation_buffer:
                flagged.append(
                    {
                        "symbol": position.symbol,
                        "distance_to_liquidation": distance,
                        "liquidation_price": liquidation_price,
                        "mark_price": mark_price,
                    }
                )
        return {
            "margin_usage": metrics["margin_usage"],
            "highest_position_risk": highest_risk,
            "positions_near_liquidation": flagged,
        }

    def _normalize_instrument(self, order: Mapping[str, Any]) -> Optional[Instrument]:
        instrument_payload = order.get("instrument")
        if instrument_payload:
            return Instrument.from_mapping(instrument_payload)
        instrument_type = str(order.get("instrument_type") or "").strip().lower()
        symbol = order.get("symbol")
        if not symbol or not instrument_type:
            return None
        try:
            return Instrument(symbol=symbol, type=instrument_type)
        except Exception:
            return None

    def validate_derivatives_order(
        self,
        order: Mapping[str, Any],
        *,
        positions=None,
        account_info: Optional[Mapping[str, Any]] = None,
        contract_metadata: Optional[Mapping[str, Any]] = None,
    ) -> tuple[bool, str]:
        instrument = self._normalize_instrument(order)
        if instrument is None or instrument.type not in {InstrumentType.OPTION, InstrumentType.FUTURE}:
            return True, "Not a derivatives order"

        amount = abs(self._safe_float(order.get("quantity", order.get("amount", 0.0)), 0.0))
        price = self._safe_float(order.get("price", order.get("expected_price", 0.0)), 0.0)
        contract_size = self._safe_float(
            (contract_metadata or {}).get("multiplier", instrument.contract_size or instrument.multiplier or 1.0),
            instrument.contract_size or instrument.multiplier or 1.0,
        )
        requested_notional = amount * max(price, 1.0) * contract_size
        if requested_notional > self.max_position_notional():
            return False, "Requested derivatives exposure exceeds max position notional"

        margin_metrics = self.margin_usage(account_info=account_info, positions=positions)
        additional_margin = self._safe_float((contract_metadata or {}).get("initial_margin", 0.0), 0.0) * max(amount, 1.0)
        projected_margin_usage = (margin_metrics["margin_used"] + additional_margin) / max(margin_metrics["equity"], 1e-9)
        if projected_margin_usage > self.max_margin_usage:
            return False, "Projected margin usage exceeds the configured limit"

        exposure_ratio = (self.portfolio_exposure_ratio(positions or []) + (requested_notional / max(self.account_equity, 1e-9)))
        if exposure_ratio > self.max_gross_exposure_pct:
            return False, "Projected portfolio exposure exceeds the configured limit"

        if instrument.type is InstrumentType.OPTION:
            greeks = self.option_greek_exposure(positions or [])
            projected_gamma = abs(greeks["gamma"] + self._safe_float(order.get("gamma", 0.0), 0.0))
            projected_theta = abs(greeks["theta"] + self._safe_float(order.get("theta", 0.0), 0.0))
            if projected_gamma > self.max_gamma_exposure:
                return False, "Projected gamma exposure exceeds the configured limit"
            if self.account_equity > 0 and projected_theta / self.account_equity > self.max_theta_decay_pct:
                return False, "Projected theta decay exceeds the configured limit"

        if instrument.type is InstrumentType.FUTURE:
            liquidation_metrics = self.futures_liquidation_risk(positions or [], account_info=account_info)
            if liquidation_metrics["highest_position_risk"] >= 1.0:
                return False, "Existing futures positions are already at liquidation threshold"

        return True, "Approved"
