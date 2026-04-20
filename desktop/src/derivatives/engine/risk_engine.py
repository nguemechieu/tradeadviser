from __future__ import annotations

import logging
from datetime import datetime, timezone

from derivatives.core.config import RiskConfig
from derivatives.core.event_bus import EventBus
from derivatives.core.models import PortfolioState, RiskAssessment
from derivatives.data.live_cache.cache.live_market_cache import LiveMarketCache


class RiskEngine:
    def __init__(
        self,
        event_bus: EventBus,
        cache: LiveMarketCache,
        *,
        config: RiskConfig | None = None,
        starting_equity: float = 100000.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.bus = event_bus
        self.cache = cache
        self.config = config or RiskConfig()
        self.logger = logger or logging.getLogger("DerivativesRiskEngine")
        self.day_start_equity = max(1.0, float(starting_equity))
        self.kill_switch_reason: str | None = None
        self.latest_portfolio = PortfolioState(
            equity=self.day_start_equity,
            cash=self.day_start_equity,
            free_margin=self.day_start_equity,
            used_margin=0.0,
        )
        self.bus.subscribe("portfolio.updated", self._on_portfolio_update)
        self.bus.subscribe("signal.generated", self._on_signal)

    @property
    def kill_switch_active(self) -> bool:
        return bool(self.kill_switch_reason)

    async def _on_portfolio_update(self, event) -> None:
        payload = dict(event.data or {})
        positions_payload = payload.get("positions") if isinstance(payload.get("positions"), dict) else {}
        self.latest_portfolio = PortfolioState(
            equity=float(payload.get("equity") or self.latest_portfolio.equity),
            cash=float(payload.get("cash") or self.latest_portfolio.cash),
            free_margin=float(payload.get("free_margin") or self.latest_portfolio.free_margin),
            used_margin=float(payload.get("used_margin") or self.latest_portfolio.used_margin),
            positions=positions_payload,
            gross_exposure=float(payload.get("gross_exposure") or 0.0),
            net_exposure=float(payload.get("net_exposure") or 0.0),
            realized_pnl=float(payload.get("realized_pnl") or 0.0),
            unrealized_pnl=float(payload.get("unrealized_pnl") or 0.0),
            drawdown_pct=float(payload.get("drawdown_pct") or 0.0),
            timestamp=datetime.now(timezone.utc),
        )
        if self.latest_portfolio.drawdown_pct >= float(self.config.max_daily_drawdown_pct):
            self.kill_switch_reason = "Daily drawdown threshold breached."

    async def _on_signal(self, event) -> None:
        signal = dict(event.data or {})
        assessment = self.review(signal)
        if not assessment.approved:
            await self.bus.publish("risk.alert", assessment.to_dict(), source="risk_engine")
            return
        await self.bus.publish("risk.approved", assessment.to_dict(), source="risk_engine")

    def review(self, signal: dict) -> RiskAssessment:
        symbol = str(signal.get("symbol") or "").strip()
        side = str(signal.get("side") or "buy").strip().lower()
        price = self.cache.latest_price(symbol) or float(signal.get("limit_price") or 0.0)
        confidence = float(signal.get("confidence") or 0.0)
        if price <= 0:
            return RiskAssessment(False, symbol, side, 0.0, confidence, "No valid market price available.")

        if self.kill_switch_active:
            return RiskAssessment(False, symbol, side, 0.0, confidence, self.kill_switch_reason or "Kill switch active.")

        equity = max(1.0, float(self.latest_portfolio.equity or self.day_start_equity))
        daily_loss_pct = max(0.0, (self.day_start_equity - equity) / self.day_start_equity)
        if daily_loss_pct >= float(self.config.kill_switch_loss_pct):
            self.kill_switch_reason = "Kill switch triggered by daily loss threshold."
            return RiskAssessment(False, symbol, side, 0.0, confidence, self.kill_switch_reason)

        current_positions = [
            position
            for position in list((self.latest_portfolio.positions or {}).values())
            if abs(float(position.get("quantity") or 0.0)) > 1e-12
        ]
        same_symbol_exposure = sum(abs(float(position.get("market_value") or 0.0)) for position in current_positions if position.get("symbol") == symbol)
        if len(current_positions) >= int(self.config.max_concurrent_positions) and same_symbol_exposure <= 0.0:
            return RiskAssessment(False, symbol, side, 0.0, confidence, "Max concurrent positions reached.")

        requested_size = max(0.0, float(signal.get("size") or 0.0))
        stop_loss = signal.get("stop_loss")
        feature_map = dict((signal.get("metadata") or {}).get("features") or {})
        volatility = float(feature_map.get("volatility") or 0.0)
        atr = float(feature_map.get("atr") or 0.0)
        stop_distance = abs(price - float(stop_loss)) if stop_loss not in (None, "") else 0.0
        if stop_distance <= 0:
            volatility_proxy = max(volatility, atr / max(price, 1e-9), 0.005)
            stop_distance = max(price * volatility_proxy * float(self.config.default_stop_atr_multiple), price * 0.0025)

        risk_budget = equity * float(self.config.max_risk_per_trade_pct)
        volatility_scale = min(
            float(self.config.volatility_position_ceiling),
            max(float(self.config.volatility_position_floor), 1.0 / max(volatility * 100.0, 1.0)),
        )
        sized_by_risk = (risk_budget / max(stop_distance, 1e-9)) * volatility_scale
        approved_size = min(requested_size, sized_by_risk)
        if approved_size <= 0:
            return RiskAssessment(False, symbol, side, 0.0, confidence, "Risk sizing reduced the order to zero.")

        notional = approved_size * price
        if same_symbol_exposure + abs(notional) > equity * float(self.config.max_exposure_per_asset_pct):
            return RiskAssessment(False, symbol, side, 0.0, confidence, "Per-asset exposure limit would be breached.")
        if self.latest_portfolio.gross_exposure + abs(notional) > equity * float(self.config.max_leverage):
            return RiskAssessment(False, symbol, side, 0.0, confidence, "Portfolio leverage limit would be breached.")

        incremental_margin = abs(notional) / max(float(self.config.max_leverage), 1.0)
        projected_free_margin = float(self.latest_portfolio.free_margin) - incremental_margin
        if projected_free_margin < equity * float(self.config.min_margin_buffer_pct):
            return RiskAssessment(False, symbol, side, 0.0, confidence, "Margin buffer threshold would be breached.")

        return RiskAssessment(
            approved=True,
            symbol=symbol,
            side=side,
            approved_size=approved_size,
            confidence=confidence,
            reason="Approved by derivatives risk engine.",
            order_type=str(signal.get("order_type") or "market"),
            limit_price=signal.get("limit_price"),
            stop_loss=stop_loss,
            take_profit=signal.get("take_profit"),
            broker_key=signal.get("broker_key"),
            exchange=signal.get("exchange"),
            strategy_name=str(signal.get("strategy_name") or "unknown"),
            metadata={
                **dict(signal.get("metadata") or {}),
                "risk_budget": risk_budget,
                "stop_distance": stop_distance,
                "notional": notional,
                "daily_loss_pct": daily_loss_pct,
            },
        )
