from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ExposureManager:
    """Tracks current portfolio exposure and projects concentration checks."""

    def __init__(self) -> None:
        self.positions: dict[str, float] = {}
        self.asset_class_map: dict[str, str] = {}

    def update(self, symbol: str, value: float, asset_class: str | None = None) -> None:
        key = self._normalize_symbol(symbol)
        self.positions[key] = float(value or 0.0)
        if asset_class is not None:
            self.asset_class_map[key] = str(asset_class or "unknown")

    def update_position(
        self,
        symbol: str,
        *,
        quantity: float,
        price: float,
        asset_class: str | None = None,
    ) -> None:
        self.update(symbol, float(quantity or 0.0) * float(price or 0.0), asset_class=asset_class)

    def remove(self, symbol: str) -> None:
        key = self._normalize_symbol(symbol)
        self.positions.pop(key, None)
        self.asset_class_map.pop(key, None)

    def clear(self) -> None:
        self.positions.clear()
        self.asset_class_map.clear()

    def total_exposure(self) -> float:
        return sum(abs(value) for value in self.positions.values())

    def net_exposure(self) -> float:
        return sum(float(value or 0.0) for value in self.positions.values())

    def symbol_exposure(self, symbol: str) -> float:
        return abs(float(self.positions.get(self._normalize_symbol(symbol), 0.0) or 0.0))

    def exposure_by_asset_class(self) -> dict[str, float]:
        exposures: dict[str, float] = {}
        for symbol, value in self.positions.items():
            asset_class = self.asset_class_map.get(symbol, "unknown")
            exposures[asset_class] = exposures.get(asset_class, 0.0) + abs(float(value or 0.0))
        return exposures

    def snapshot(self) -> dict[str, float]:
        return dict(self.positions)

    def update_from_portfolio(self, positions: Mapping[str, Any] | None) -> None:
        self.clear()
        for symbol, position in dict(positions or {}).items():
            payload = position
            if not isinstance(payload, Mapping):
                payload = getattr(position, "__dict__", {})
            quantity = float(getattr(position, "quantity", payload.get("quantity", 0.0)) or 0.0)
            current_price = float(
                getattr(position, "last_price", payload.get("last_price", payload.get("current_price", 0.0))) or 0.0
            )
            average_price = float(getattr(position, "average_price", payload.get("average_price", 0.0)) or 0.0)
            reference_price = current_price or average_price
            asset_class = getattr(position, "asset_class", payload.get("asset_class"))
            self.update_position(symbol, quantity=quantity, price=reference_price, asset_class=asset_class)

    def projected_total_exposure(self, proposed_delta: float = 0.0) -> float:
        return self.total_exposure() + abs(float(proposed_delta or 0.0))

    def projected_symbol_exposure(self, symbol: str, proposed_delta: float = 0.0) -> float:
        return self.symbol_exposure(symbol) + abs(float(proposed_delta or 0.0))

    def evaluate_position(
        self,
        equity: float,
        *,
        symbol: str,
        proposed_notional: float,
        max_symbol_exposure_pct: float,
        max_total_exposure_pct: float | None = None,
    ) -> tuple[bool, str, dict[str, float]]:
        account_equity = max(0.0, float(equity or 0.0))
        proposed = abs(float(proposed_notional or 0.0))
        current_symbol = self.symbol_exposure(symbol)
        current_total = self.total_exposure()
        metrics = {
            "equity": account_equity,
            "current_symbol_exposure": current_symbol,
            "projected_symbol_exposure": current_symbol + proposed,
            "current_total_exposure": current_total,
            "projected_total_exposure": current_total + proposed,
        }
        if account_equity <= 0.0:
            return False, "Account equity is unavailable", metrics

        symbol_limit = account_equity * max(0.0, float(max_symbol_exposure_pct or 0.0))
        metrics["symbol_exposure_limit"] = symbol_limit
        if current_symbol + proposed > symbol_limit + 1e-12:
            return False, "Single-position exposure limit breached", metrics

        if max_total_exposure_pct is not None:
            total_limit = account_equity * max(0.0, float(max_total_exposure_pct or 0.0))
            metrics["total_exposure_limit"] = total_limit
            if current_total + proposed > total_limit + 1e-12:
                return False, "Portfolio exposure limit breached", metrics

        return True, "Exposure approved", metrics

    def check(
        self,
        equity: float,
        max_exposure_pct: float,
        *,
        symbol: str | None = None,
        proposed_delta: float = 0.0,
        max_symbol_exposure_pct: float | None = None,
    ) -> bool:
        account_equity = max(0.0, float(equity or 0.0))
        if account_equity <= 0.0:
            return False

        projected_total = self.projected_total_exposure(proposed_delta=proposed_delta)
        if projected_total > account_equity * float(max_exposure_pct or 0.0):
            return False

        if symbol and max_symbol_exposure_pct is not None:
            projected_symbol = self.projected_symbol_exposure(symbol, proposed_delta=proposed_delta)
            if projected_symbol > account_equity * float(max_symbol_exposure_pct or 0.0):
                return False

        return True

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper()
