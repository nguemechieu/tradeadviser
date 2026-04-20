from dataclasses import dataclass, field

from quant.allocation_models import capped_weights, equal_weight_allocation, inverse_volatility_allocation, normalize_weights
from quant.risk_models import annualized_volatility, close_returns, safe_float


@dataclass
class AllocationDecision:
    approved: bool
    reason: str
    adjusted_amount: float
    metrics: dict = field(default_factory=dict)


class PortfolioAllocator:
    VERSION = "portfolio-allocator-v1"

    def __init__(
        self,
        account_equity,
        strategy_weights=None,
        allocation_model="equal_weight",
        max_strategy_allocation_pct=1.0,
        rebalance_threshold_pct=0.05,
        volatility_target_pct=0.20,
        min_trade_allocation_pct=0.005,
    ):
        self.account_equity = max(0.0, safe_float(account_equity, 10000.0))
        self.strategy_weights = normalize_weights(strategy_weights or {})
        self.allocation_model = str(allocation_model or "equal_weight").strip().lower()
        self.max_strategy_allocation_pct = max(0.0, min(1.0, safe_float(max_strategy_allocation_pct, 1.0)))
        self.rebalance_threshold_pct = max(0.0, safe_float(rebalance_threshold_pct, 0.05))
        self.volatility_target_pct = max(0.01, safe_float(volatility_target_pct, 0.20))
        self.min_trade_allocation_pct = max(0.0, safe_float(min_trade_allocation_pct, 0.005))
        self._symbol_strategy_map = {}
        self._latest_snapshot = self.status_snapshot()

    def sync_equity(self, equity):
        value = safe_float(equity, self.account_equity)
        if value >= 0:
            self.account_equity = value

    def configure_strategy_weights(self, strategy_weights=None, allocation_model=None):
        self.strategy_weights = normalize_weights(strategy_weights or {})
        if allocation_model is not None:
            self.allocation_model = str(allocation_model or "equal_weight").strip().lower()
        self._latest_snapshot = self.status_snapshot()

    def register_strategy_symbol(self, symbol, strategy_name):
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_strategy = str(strategy_name or "").strip()
        if normalized_symbol and normalized_strategy:
            self._symbol_strategy_map[normalized_symbol] = normalized_strategy

    def tracked_strategy_for_symbol(self, symbol):
        return self._symbol_strategy_map.get(str(symbol or "").strip().upper())

    def _resolve_weights(self, active_strategies, strategy_volatility_map=None):
        active = [str(name) for name in (active_strategies or []) if str(name).strip()]
        if not active:
            return {}

        explicit = {name: value for name, value in self.strategy_weights.items() if name in active}
        if explicit:
            return capped_weights(explicit, max_weight=self.max_strategy_allocation_pct)

        if self.allocation_model == "inverse_volatility":
            inverse = inverse_volatility_allocation(
                {
                    name: strategy_volatility_map.get(name, 0.0)
                    for name in active
                }
            )
            if inverse:
                return capped_weights(inverse, max_weight=self.max_strategy_allocation_pct)

        return capped_weights(equal_weight_allocation(active), max_weight=self.max_strategy_allocation_pct)

    def _strategy_exposures(self, portfolio, market_prices):
        positions = getattr(portfolio, "positions", {}) or {}
        exposures = {}
        total = 0.0
        for symbol, position in positions.items():
            quantity = safe_float(getattr(position, "quantity", 0.0), 0.0)
            if quantity == 0:
                continue
            price = safe_float((market_prices or {}).get(symbol), getattr(position, "avg_price", 0.0))
            notional = abs(quantity * price)
            strategy_name = self.tracked_strategy_for_symbol(symbol) or "Unassigned"
            exposures[strategy_name] = exposures.get(strategy_name, 0.0) + notional
            total += notional
        return exposures, total

    def _dataset_volatility(self, dataset=None):
        frame = getattr(dataset, "frame", None)
        returns = close_returns(frame)
        if returns.empty:
            return 0.0
        return annualized_volatility(returns)

    async def allocate_trade(
        self,
        symbol,
        strategy_name,
        side,
        amount,
        price,
        portfolio=None,
        market_prices=None,
        dataset=None,
        confidence=None,
        active_strategies=None,
        strategy_volatility_map=None,
    ):
        symbol = str(symbol or "").strip().upper()
        strategy_name = str(strategy_name or "Strategy").strip()
        trade_amount = abs(safe_float(amount, 0.0))
        trade_price = safe_float(price, 0.0)
        equity = max(0.0, safe_float(self.account_equity, 0.0))

        if not symbol or not strategy_name or trade_amount <= 0 or trade_price <= 0:
            decision = AllocationDecision(False, "Invalid trade payload for allocator", 0.0, self.status_snapshot())
            self._latest_snapshot = decision.metrics
            return decision
        if equity <= 0:
            metrics = {
                "version": self.VERSION,
                "approved": False,
                "reason": "Allocator cannot size trades because account equity is zero.",
                "strategy_name": strategy_name,
                "symbol": symbol,
                "equity": equity,
            }
            self._latest_snapshot = metrics
            return AllocationDecision(False, metrics["reason"], 0.0, metrics)

        active = [str(name) for name in (active_strategies or [strategy_name]) if str(name).strip()]
        if strategy_name not in active:
            active.append(strategy_name)

        strategy_weights = self._resolve_weights(active, strategy_volatility_map=strategy_volatility_map or {})
        target_weight = strategy_weights.get(strategy_name, 0.0)
        if target_weight <= 0:
            metrics = {
                "version": self.VERSION,
                "approved": False,
                "reason": f"No capital budget is assigned to {strategy_name}.",
                "strategy_name": strategy_name,
                "symbol": symbol,
            }
            self._latest_snapshot = metrics
            return AllocationDecision(False, metrics["reason"], 0.0, metrics)

        strategy_exposures, total_strategy_exposure = self._strategy_exposures(portfolio, market_prices)
        current_strategy_exposure = safe_float(strategy_exposures.get(strategy_name), 0.0)
        target_budget_value = equity * target_weight
        capped_budget_value = min(target_budget_value, equity * self.max_strategy_allocation_pct)
        available_budget_value = max(0.0, capped_budget_value - current_strategy_exposure)

        requested_trade_value = trade_amount * trade_price
        confidence_value = safe_float(confidence, 0.50)
        confidence_scale = max(0.35, min(1.0, 0.5 + (confidence_value / 2.0)))
        annual_volatility = self._dataset_volatility(dataset)
        volatility_scale = 1.0
        if annual_volatility > 0:
            volatility_scale = max(0.20, min(1.25, self.volatility_target_pct / annual_volatility))

        minimum_ticket_value = equity * self.min_trade_allocation_pct
        scaled_budget_value = capped_budget_value * confidence_scale * volatility_scale
        effective_budget_value = min(available_budget_value, scaled_budget_value)
        adjusted_trade_value = min(requested_trade_value, effective_budget_value)
        adjusted_amount = adjusted_trade_value / trade_price if trade_price > 0 else 0.0

        projected_exposure = current_strategy_exposure + adjusted_trade_value
        drift_pct = abs((projected_exposure / equity) - target_weight)

        metrics = {
            "version": self.VERSION,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "side": side,
            "allocation_model": self.allocation_model,
            "strategy_weights": strategy_weights,
            "target_weight": target_weight,
            "target_budget_value": target_budget_value,
            "capped_budget_value": capped_budget_value,
            "available_budget_value": available_budget_value,
            "requested_trade_value": requested_trade_value,
            "adjusted_trade_value": adjusted_trade_value,
            "requested_amount": trade_amount,
            "approved_amount": adjusted_amount,
            "current_strategy_exposure": current_strategy_exposure,
            "projected_strategy_exposure": projected_exposure,
            "projected_strategy_exposure_pct": projected_exposure / equity,
            "total_strategy_exposure": total_strategy_exposure,
            "confidence": confidence_value,
            "confidence_scale": confidence_scale,
            "annualized_volatility": annual_volatility,
            "volatility_scale": volatility_scale,
            "rebalance_drift_pct": drift_pct,
            "approved": False,
            "reason": "",
        }

        if available_budget_value <= 0:
            metrics["reason"] = (
                f"{strategy_name} has no meaningful capital headroom left "
                f"({available_budget_value:.2f} available)."
            )
            self._latest_snapshot = metrics
            return AllocationDecision(False, metrics["reason"], 0.0, metrics)

        if adjusted_trade_value <= 0 or adjusted_amount <= 0:
            metrics["reason"] = "Allocator scaled the trade to zero."
            self._latest_snapshot = metrics
            return AllocationDecision(False, metrics["reason"], 0.0, metrics)

        if drift_pct > (target_weight + self.rebalance_threshold_pct):
            metrics["reason"] = (
                f"{strategy_name} would drift too far from its target allocation "
                f"({metrics['projected_strategy_exposure_pct']:.1%} vs target {target_weight:.1%})."
            )
            self._latest_snapshot = metrics
            return AllocationDecision(False, metrics["reason"], adjusted_amount, metrics)

        metrics["approved"] = True
        metrics["below_minimum_useful_allocation"] = adjusted_trade_value < minimum_ticket_value
        if metrics["below_minimum_useful_allocation"]:
            metrics["reason"] = (
                f"Approved with remaining available allocation: amount reduced from {trade_amount:.6g} "
                f"to {adjusted_amount:.6g} for {strategy_name} "
                f"({adjusted_trade_value:.2f} < {minimum_ticket_value:.2f})."
            )
        elif adjusted_amount < trade_amount:
            metrics["reason"] = (
                f"Approved with allocation scaling: amount reduced from {trade_amount:.6g} "
                f"to {adjusted_amount:.6g} for {strategy_name}."
            )
        else:
            metrics["reason"] = f"Approved within {strategy_name} capital budget."

        self._latest_snapshot = metrics
        return AllocationDecision(True, metrics["reason"], adjusted_amount, metrics)

    def status_snapshot(self):
        return {
            "version": self.VERSION,
            "allocation_model": self.allocation_model,
            "strategy_weights": dict(self.strategy_weights),
            "max_strategy_allocation_pct": self.max_strategy_allocation_pct,
            "rebalance_threshold_pct": self.rebalance_threshold_pct,
            "volatility_target_pct": self.volatility_target_pct,
            "min_trade_allocation_pct": self.min_trade_allocation_pct,
            "tracked_symbols": len(self._symbol_strategy_map),
            "equity": self.account_equity,
        }

    @property
    def latest_snapshot(self):
        return dict(self._latest_snapshot or {})
