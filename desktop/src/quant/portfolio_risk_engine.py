from dataclasses import dataclass, field

from quant.data_models import DatasetRequest
from quant.risk_models import (
    annualized_volatility,
    close_returns,
    correlation,
    historical_cvar,
    historical_var,
    kelly_fraction,
    safe_float,
)


@dataclass
class RiskApproval:
    approved: bool
    reason: str
    adjusted_amount: float
    metrics: dict = field(default_factory=dict)


class PortfolioRiskEngine:
    VERSION = "portfolio-risk-v1"

    def __init__(
        self,
        account_equity,
        max_portfolio_risk=0.10,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.10,
        max_gross_exposure_pct=2.0,
        max_symbol_exposure_pct=0.30,
        max_correlation=0.85,
        var_confidence=0.95,
        volatility_target_pct=0.20,
        kelly_fraction_cap=0.25,
    ):
        self.account_equity = max(0.0, safe_float(account_equity, 10000.0))
        self.max_portfolio_risk = max(0.0, safe_float(max_portfolio_risk, 0.10))
        self.max_risk_per_trade = max(0.0, safe_float(max_risk_per_trade, 0.02))
        self.max_position_size_pct = max(0.0, safe_float(max_position_size_pct, 0.10))
        self.max_gross_exposure_pct = max(0.0, safe_float(max_gross_exposure_pct, 2.0))
        self.max_symbol_exposure_pct = max(0.0, safe_float(max_symbol_exposure_pct, 0.30))
        self.max_correlation = max(0.10, min(0.999, safe_float(max_correlation, 0.85)))
        self.var_confidence = max(0.80, min(0.999, safe_float(var_confidence, 0.95)))
        self.volatility_target_pct = max(0.0, safe_float(volatility_target_pct, 0.20))
        self.kelly_fraction_cap = max(0.0, safe_float(kelly_fraction_cap, 0.25))
        self._latest_snapshot = self.status_snapshot()

    def sync_equity(self, equity):
        value = safe_float(equity, self.account_equity)
        if value >= 0:
            self.account_equity = value

    def _trade_direction(self, side):
        normalized = str(side or "").strip().lower()
        return -1.0 if normalized == "sell" else 1.0

    def _portfolio_state(self, portfolio, market_prices):
        positions = getattr(portfolio, "positions", {}) or {}
        state = {}
        gross_exposure = 0.0
        net_exposure = 0.0

        for symbol, position in positions.items():
            quantity = safe_float(getattr(position, "quantity", 0.0), 0.0)
            if quantity == 0:
                continue
            price = safe_float((market_prices or {}).get(symbol), getattr(position, "avg_price", 0.0))
            exposure = quantity * price
            state[str(symbol).upper()] = {
                "quantity": quantity,
                "price": price,
                "signed_exposure": exposure,
                "abs_exposure": abs(exposure),
            }
            gross_exposure += abs(exposure)
            net_exposure += exposure

        return state, gross_exposure, net_exposure

    async def _frame_for_symbol(self, symbol, data_hub=None, timeframe="1h", limit=250, provided_dataset=None):
        normalized = str(symbol or "").strip().upper()
        if provided_dataset is not None and str(getattr(provided_dataset, "symbol", "")).upper() == normalized:
            return getattr(provided_dataset, "frame", None)
        if data_hub is None:
            return None
        snapshot = await data_hub.get_symbol_dataset(
            DatasetRequest(symbol=normalized, timeframe=timeframe, limit=limit, prefer_live=False)
        )
        return getattr(snapshot, "frame", None)

    async def approve_trade(
        self,
        symbol,
        side,
        amount,
        price,
        portfolio=None,
        market_prices=None,
        data_hub=None,
        dataset=None,
        timeframe="1h",
        strategy_name=None,
    ):
        symbol = str(symbol or "").strip().upper()
        side = str(side or "buy").strip().lower()
        requested_amount = abs(safe_float(amount, 0.0))
        trade_price = safe_float(price, 0.0)
        equity = max(0.0, safe_float(self.account_equity, 0.0))

        if not symbol or requested_amount <= 0 or trade_price <= 0:
            approval = RiskApproval(False, "Invalid trade payload for portfolio risk review", 0.0, self.status_snapshot())
            self._latest_snapshot = approval.metrics
            return approval
        if equity <= 0:
            metrics = {
                "version": self.VERSION,
                "symbol": symbol,
                "strategy_name": strategy_name,
                "equity": equity,
                "requested_amount": requested_amount,
                "approved_amount": 0.0,
                "trade_price": trade_price,
                "trade_value": requested_amount * trade_price,
                "adjusted_trade_value": 0.0,
                "approved": False,
                "reason": "Portfolio risk engine cannot size trades because account equity is zero.",
            }
            self._latest_snapshot = metrics
            return RiskApproval(False, metrics["reason"], 0.0, metrics)

        current_positions, current_gross, current_net = self._portfolio_state(portfolio, market_prices)
        current_symbol_state = current_positions.get(symbol, {})
        direction = self._trade_direction(side)
        trade_value = requested_amount * trade_price
        current_symbol_signed = safe_float(current_symbol_state.get("signed_exposure"), 0.0)

        symbol_frame = await self._frame_for_symbol(symbol, data_hub=data_hub, timeframe=timeframe, provided_dataset=dataset)
        returns = close_returns(symbol_frame)
        var_pct = historical_var(returns, confidence=self.var_confidence)
        cvar_pct = historical_cvar(returns, confidence=self.var_confidence)
        annual_vol = annualized_volatility(returns)
        kelly_cap = kelly_fraction(returns, side=side, cap=self.kelly_fraction_cap)

        max_trade_value = min(
            equity * self.max_position_size_pct,
            equity * self.max_risk_per_trade / max(var_pct, 1e-6) if var_pct > 0 else equity * self.max_position_size_pct,
            equity * (self.volatility_target_pct / max(annual_vol, self.volatility_target_pct)) if annual_vol > 0 else equity * self.max_position_size_pct,
        )
        if kelly_cap > 0:
            max_trade_value = min(max_trade_value, equity * kelly_cap)

        adjusted_trade_value = min(trade_value, max_trade_value)
        adjusted_amount = requested_amount if trade_value <= 0 else max(0.0, adjusted_trade_value / trade_price)
        proposed_symbol_signed = current_symbol_signed + (direction * adjusted_trade_value)
        proposed_symbol_abs = abs(proposed_symbol_signed)
        proposed_gross = current_gross + adjusted_trade_value
        proposed_net = current_net + (direction * adjusted_trade_value)

        metrics = {
            "version": self.VERSION,
            "symbol": symbol,
            "strategy_name": strategy_name,
            "equity": equity,
            "requested_amount": requested_amount,
            "approved_amount": adjusted_amount,
            "trade_price": trade_price,
            "trade_value": trade_value,
            "adjusted_trade_value": adjusted_trade_value,
            "trade_var_pct": var_pct,
            "trade_cvar_pct": cvar_pct,
            "trade_var_value": adjusted_trade_value * var_pct,
            "trade_cvar_value": adjusted_trade_value * cvar_pct,
            "annualized_volatility": annual_vol,
            "kelly_fraction_cap": kelly_cap,
            "gross_exposure_pct": proposed_gross / equity,
            "net_exposure_pct": abs(proposed_net) / equity,
            "symbol_exposure_pct": proposed_symbol_abs / equity,
            "correlation_breach": None,
            "portfolio_var_pct": 0.0,
            "portfolio_cvar_pct": 0.0,
            "approved": False,
            "reason": "",
        }

        if adjusted_amount <= 0:
            metrics["reason"] = "Risk engine scaled the trade to zero."
            approval = RiskApproval(False, metrics["reason"], 0.0, metrics)
            self._latest_snapshot = metrics
            return approval

        if metrics["symbol_exposure_pct"] > self.max_symbol_exposure_pct:
            metrics["reason"] = (
                f"Symbol exposure would reach {metrics['symbol_exposure_pct']:.1%} "
                f"(limit {self.max_symbol_exposure_pct:.1%})."
            )
            approval = RiskApproval(False, metrics["reason"], adjusted_amount, metrics)
            self._latest_snapshot = metrics
            return approval

        if metrics["gross_exposure_pct"] > self.max_gross_exposure_pct:
            metrics["reason"] = (
                f"Gross exposure would reach {metrics['gross_exposure_pct']:.1%} "
                f"(limit {self.max_gross_exposure_pct:.1%})."
            )
            approval = RiskApproval(False, metrics["reason"], adjusted_amount, metrics)
            self._latest_snapshot = metrics
            return approval

        if metrics["trade_var_value"] > equity * self.max_risk_per_trade:
            metrics["reason"] = (
                f"Trade VaR would reach {metrics['trade_var_value']:.2f} "
                f"(limit {(equity * self.max_risk_per_trade):.2f})."
            )
            approval = RiskApproval(False, metrics["reason"], adjusted_amount, metrics)
            self._latest_snapshot = metrics
            return approval

        candidate_exposures = {key: value["signed_exposure"] for key, value in current_positions.items()}
        candidate_exposures[symbol] = proposed_symbol_signed
        returns_map = {}
        for candidate_symbol in candidate_exposures.keys():
            frame = symbol_frame if candidate_symbol == symbol else await self._frame_for_symbol(
                candidate_symbol,
                data_hub=data_hub,
                timeframe=timeframe,
                limit=250,
            )
            candidate_returns = close_returns(frame)
            if not candidate_returns.empty:
                returns_map[candidate_symbol] = candidate_returns.reset_index(drop=True)

        for other_symbol, exposure in candidate_exposures.items():
            if other_symbol == symbol or abs(exposure) <= 0:
                continue
            if other_symbol not in returns_map or symbol not in returns_map:
                continue
            corr_value = correlation(returns_map[symbol], returns_map[other_symbol])
            combined_exposure_pct = (abs(exposure) + proposed_symbol_abs) / equity
            if abs(corr_value) >= self.max_correlation and combined_exposure_pct > self.max_symbol_exposure_pct:
                metrics["correlation_breach"] = {
                    "symbol": other_symbol,
                    "correlation": corr_value,
                    "combined_exposure_pct": combined_exposure_pct,
                }
                metrics["reason"] = (
                    f"{symbol} is too correlated with {other_symbol} "
                    f"({corr_value:.2f}) for the proposed combined exposure {combined_exposure_pct:.1%}."
                )
                approval = RiskApproval(False, metrics["reason"], adjusted_amount, metrics)
                self._latest_snapshot = metrics
                return approval

        if returns_map:
            series = []
            for candidate_symbol, exposure in candidate_exposures.items():
                candidate_returns = returns_map.get(candidate_symbol)
                if candidate_returns is None or candidate_returns.empty:
                    continue
                weight = exposure / equity
                series.append(candidate_returns.rename(candidate_symbol) * weight)
            if series:
                aligned = None
                for item in series:
                    aligned = item.to_frame() if aligned is None else aligned.join(item, how="inner")
                if aligned is not None and not aligned.empty:
                    portfolio_returns = aligned.sum(axis=1)
                    metrics["portfolio_var_pct"] = historical_var(portfolio_returns, confidence=self.var_confidence)
                    metrics["portfolio_cvar_pct"] = historical_cvar(portfolio_returns, confidence=self.var_confidence)

        if metrics["portfolio_var_pct"] > self.max_portfolio_risk:
            metrics["reason"] = (
                f"Portfolio VaR would reach {metrics['portfolio_var_pct']:.1%} "
                f"(limit {self.max_portfolio_risk:.1%})."
            )
            approval = RiskApproval(False, metrics["reason"], adjusted_amount, metrics)
            self._latest_snapshot = metrics
            return approval

        metrics["approved"] = True
        if adjusted_amount < requested_amount:
            metrics["reason"] = (
                f"Approved with volatility scaling: amount reduced from {requested_amount:.6g} "
                f"to {adjusted_amount:.6g}."
            )
        else:
            metrics["reason"] = "Approved by institutional portfolio risk engine."
        approval = RiskApproval(True, metrics["reason"], adjusted_amount, metrics)
        self._latest_snapshot = metrics
        return approval

    def status_snapshot(self):
        return {
            "version": self.VERSION,
            "equity": self.account_equity,
            "max_portfolio_risk": self.max_portfolio_risk,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_position_size_pct": self.max_position_size_pct,
            "max_gross_exposure_pct": self.max_gross_exposure_pct,
            "max_symbol_exposure_pct": self.max_symbol_exposure_pct,
            "max_correlation": self.max_correlation,
            "var_confidence": self.var_confidence,
            "volatility_target_pct": self.volatility_target_pct,
            "kelly_fraction_cap": self.kelly_fraction_cap,
        }

    @property
    def latest_snapshot(self):
        return dict(self._latest_snapshot or {})
