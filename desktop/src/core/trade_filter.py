from __future__ import annotations

"""
TradeFilter

Final pre-execution trade approval layer.

This filter should run after:
- strategy signal generation
- decision engine voting
- AI/ML reasoning
- risk scoring
- portfolio snapshot update

It checks:
- HOLD / invalid decisions
- confidence threshold
- dynamic learning threshold
- vote margin
- risk score
- market regime
- portfolio exposure
- optional symbol exposure
- strategy performance
- regime performance

It returns a structured Filter Result that can be shown in the UI,
Telegram, logs, audit trail, and execution pipeline.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from .ai.learning_engine import LearningEngine
except Exception:  # pragma: no cover
    LearningEngine = None  # type: ignore


@dataclass(slots=True)
class FilterResult:
    approved: bool
    reason: str
    score: float
    checks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "score": self.score,
            "checks": list(self.checks),
            "metadata": dict(self.metadata),
        }


def _decision_text(decision: Any) -> str:
    if isinstance(decision, str):
        return decision.strip().upper()

    value = getattr(decision, "decision", None)
    if value is None and isinstance(decision, dict):
        value = decision.get("decision") or decision.get(
            "side") or decision.get("action")

    return str(value or "").strip().upper()


class TradeFilter:
    """Pre-execution trade approval filter."""

    def __init__(
        self,
        min_confidence: float = 0.65,
        min_vote_margin: float = 0.10,
        max_risk_score: float = 0.70,
        allow_ranging: bool = False,
        max_portfolio_exposure: float = 0.85,
        *,
        max_symbol_exposure: Optional[float] = None,
        min_strategy_score: float = 0.0,
        min_regime_score: float = 0.0,
        reject_none_decision: bool = True,
        use_learning_threshold: bool = True,
        use_strategy_learning: bool = True,
        use_regime_learning: bool = True,
        learning_engine: Optional[Any] = None,
    ) -> None:
        self.min_confidence = float(min_confidence)
        self.min_vote_margin = float(min_vote_margin)
        self.max_risk_score = float(max_risk_score)
        self.allow_ranging = bool(allow_ranging)
        self.max_portfolio_exposure = float(max_portfolio_exposure)

        self.max_symbol_exposure = (
            float(max_symbol_exposure)
            if max_symbol_exposure is not None
            else None
        )

        self.min_strategy_score = float(min_strategy_score)
        self.min_regime_score = float(min_regime_score)
        self.reject_none_decision = bool(reject_none_decision)
        self.use_learning_threshold = bool(use_learning_threshold)
        self.use_strategy_learning = bool(use_strategy_learning)
        self.use_regime_learning = bool(use_regime_learning)

        if learning_engine is not None:
            self.learning_engine = learning_engine
        elif LearningEngine is not None:
            self.learning_engine = LearningEngine()
        else:
            self.learning_engine = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, decision: Any, portfolio_snapshot: Optional[Any] = None) -> FilterResult:
        checks: list[str] = []
        metadata: dict[str, Any] = {}

        if decision is None:
            if self.reject_none_decision:
                return FilterResult(
                    approved=False,
                    reason="No decision supplied",
                    score=0.0,
                    checks=["decision:none"],
                    metadata=metadata,
                )

            return FilterResult(
                approved=True,
                reason="No decision supplied but reject_none_decision is disabled",
                score=1.0,
                checks=["decision:none_allowed"],
                metadata=metadata,
            )

        normalized_decision = _decision_text(decision)
        metadata["decision"] = normalized_decision

        if normalized_decision == "HOLD":
            return FilterResult(
                approved=False,
                reason="HOLD decision",
                score=0.0,
                checks=["decision:hold"],
                metadata=metadata,
            )

        if normalized_decision not in {"BUY", "SELL", "LONG", "SHORT"}:
            return FilterResult(
                approved=False,
                reason=f"Unsupported decision: {normalized_decision or 'UNKNOWN'}",
                score=0.0,
                checks=["decision:unsupported"],
                metadata=metadata,
            )

        checks.append("decision:actionable")

        confidence = self._float_attr(
            decision, "confidence", default=1.0 if isinstance(decision, str) else 0.0)
        vote_margin = self._float_attr(
            decision, "vote_margin", default=1.0 if isinstance(decision, str) else 0.0)
        risk_score = self._float_attr(decision, "risk_score", default=0.5)

        confidence = self._clamp(confidence, 0.0, 1.0)
        vote_margin = self._clamp(vote_margin, 0.0, 1.0)
        risk_score = self._clamp(risk_score, 0.0, 1.0)

        metadata.update(
            {
                "confidence": confidence,
                "vote_margin": vote_margin,
                "risk_score": risk_score,
                "min_confidence": self.min_confidence,
                "min_vote_margin": self.min_vote_margin,
                "max_risk_score": self.max_risk_score,
            }
        )

        dynamic_threshold = self._dynamic_confidence_threshold()
        effective_min_confidence = max(self.min_confidence, dynamic_threshold)

        metadata["dynamic_confidence_threshold"] = dynamic_threshold
        metadata["effective_min_confidence"] = effective_min_confidence

        if confidence < effective_min_confidence:
            return FilterResult(
                approved=False,
                reason=f"Low confidence: {confidence:.3f} < {effective_min_confidence:.3f}",
                score=confidence,
                checks=checks + ["confidence:failed"],
                metadata=metadata,
            )

        checks.append("confidence:passed")

        if vote_margin < self.min_vote_margin:
            return FilterResult(
                approved=False,
                reason=f"Weak signal: vote margin {vote_margin:.3f} < {self.min_vote_margin:.3f}",
                score=vote_margin,
                checks=checks + ["vote_margin:failed"],
                metadata=metadata,
            )

        checks.append("vote_margin:passed")

        if risk_score > self.max_risk_score:
            return FilterResult(
                approved=False,
                reason=f"Too risky: risk score {risk_score:.3f} > {self.max_risk_score:.3f}",
                score=1.0 - risk_score,
                checks=checks + ["risk:failed"],
                metadata=metadata,
            )

        checks.append("risk:passed")

        market_regime = self._str_attr(decision, "market_regime", default="")
        normalized_regime = market_regime.strip().upper()
        metadata["market_regime"] = normalized_regime

        if normalized_regime == "RANGING" and not self.allow_ranging:
            return FilterResult(
                approved=False,
                reason="Ranging market is not allowed",
                score=0.3,
                checks=checks + ["regime:ranging_blocked"],
                metadata=metadata,
            )

        checks.append("regime:allowed")

        portfolio_result = self._check_portfolio_exposure(
            decision, portfolio_snapshot)
        metadata["portfolio"] = portfolio_result["metadata"]

        if not portfolio_result["approved"]:
            return FilterResult(
                approved=False,
                reason=portfolio_result["reason"],
                score=portfolio_result["score"],
                checks=checks + portfolio_result["checks"],
                metadata=metadata,
            )

        checks.extend(portfolio_result["checks"])

        strategy_result = self._check_strategy_learning(decision)
        metadata["strategy_learning"] = strategy_result["metadata"]

        if not strategy_result["approved"]:
            return FilterResult(
                approved=False,
                reason=strategy_result["reason"],
                score=strategy_result["score"],
                checks=checks + strategy_result["checks"],
                metadata=metadata,
            )

        checks.extend(strategy_result["checks"])

        regime_result = self._check_regime_learning(normalized_regime)
        metadata["regime_learning"] = regime_result["metadata"]

        if not regime_result["approved"]:
            return FilterResult(
                approved=False,
                reason=regime_result["reason"],
                score=regime_result["score"],
                checks=checks + regime_result["checks"],
                metadata=metadata,
            )

        checks.extend(regime_result["checks"])

        final_score = self._final_score(
            confidence=confidence,
            vote_margin=vote_margin,
            risk_score=risk_score,
            strategy_score=strategy_result["score"],
            regime_score=regime_result["score"],
        )

        return FilterResult(
            approved=True,
            reason="Approved",
            score=final_score,
            checks=checks + ["approved"],
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Portfolio checks
    # ------------------------------------------------------------------

    def _check_portfolio_exposure(self, decision: Any, portfolio_snapshot: Optional[Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        if not portfolio_snapshot:
            return {
                "approved": True,
                "reason": "No portfolio snapshot supplied",
                "score": 1.0,
                "checks": ["portfolio:not_supplied"],
                "metadata": metadata,
            }

        gross_exposure = self._snapshot_float(
            portfolio_snapshot, "gross_exposure", default=0.0)
        equity = self._snapshot_float(
            portfolio_snapshot, "equity", default=1.0)

        exposure_ratio = gross_exposure / max(abs(equity), 1e-12)

        metadata.update(
            {
                "gross_exposure": gross_exposure,
                "equity": equity,
                "exposure_ratio": exposure_ratio,
                "max_portfolio_exposure": self.max_portfolio_exposure,
            }
        )

        if equity <= 0:
            return {
                "approved": False,
                "reason": "Invalid portfolio equity",
                "score": 0.0,
                "checks": ["portfolio:invalid_equity"],
                "metadata": metadata,
            }

        if exposure_ratio > self.max_portfolio_exposure:
            return {
                "approved": False,
                "reason": f"Overexposed portfolio: {exposure_ratio:.3f} > {self.max_portfolio_exposure:.3f}",
                "score": 0.2,
                "checks": ["portfolio:overexposed"],
                "metadata": metadata,
            }

        symbol = self._str_attr(decision, "symbol", default="")
        if self.max_symbol_exposure is not None and symbol:
            symbol_exposure = self._symbol_exposure(portfolio_snapshot, symbol)
            symbol_ratio = symbol_exposure / max(abs(equity), 1e-12)

            metadata.update(
                {
                    "symbol": symbol,
                    "symbol_exposure": symbol_exposure,
                    "symbol_exposure_ratio": symbol_ratio,
                    "max_symbol_exposure": self.max_symbol_exposure,
                }
            )

            if symbol_ratio > self.max_symbol_exposure:
                return {
                    "approved": False,
                    "reason": f"Symbol exposure too high: {symbol_ratio:.3f} > {self.max_symbol_exposure:.3f}",
                    "score": 0.2,
                    "checks": ["portfolio:symbol_overexposed"],
                    "metadata": metadata,
                }

        return {
            "approved": True,
            "reason": "Portfolio exposure passed",
            "score": 1.0,
            "checks": ["portfolio:passed"],
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Learning checks
    # ------------------------------------------------------------------

    def _dynamic_confidence_threshold(self) -> float:
        if not self.use_learning_threshold or self.learning_engine is None:
            return 0.0

        method = getattr(self.learning_engine,
                         "get_dynamic_confidence_threshold", None)

        if not callable(method):
            return 0.0

        try:
            value = float(method().__str__())
        except Exception:
            return 0.0

        return self._clamp(value, 0.0, 1.0)

    def _check_strategy_learning(self, decision: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        if not self.use_strategy_learning or self.learning_engine is None:
            return {
                "approved": True,
                "reason": "Strategy learning disabled",
                "score": 0.0,
                "checks": ["strategy_learning:disabled"],
                "metadata": metadata,
            }

        strategy_name = self._str_attr(decision, "strategy_name", default="")
        if not strategy_name:
            strategy_name = self._str_attr(
                decision, "selected_strategy", default="")
        if not strategy_name:
            strategy_name = self._str_attr(decision, "model_name", default="")
        if not strategy_name:
            strategy_name = "unknown"

        metadata["strategy_name"] = strategy_name

        scores_method = getattr(self.learning_engine, "strategy_scores", None)

        if not callable(scores_method):
            return {
                "approved": True,
                "reason": "Strategy scoring unavailable",
                "score": 0.0,
                "checks": ["strategy_learning:unavailable"],
                "metadata": metadata,
            }

        try:
            scores = scores_method()
        except Exception as exc:
            metadata["error"] = str(exc)
            return {
                "approved": True,
                "reason": "Strategy scoring failed open",
                "score": 0.0,
                "checks": ["strategy_learning:error_failed_open"],
                "metadata": metadata,
            }


        if isinstance(scores, dict):
            strategy_score = self._safe_float(
                scores.get(strategy_name), default=0.0)
            if strategy_name not in scores and "unknown" in scores:
                strategy_score = self._safe_float(
                    scores.get("unknown"), default=0.0)
        else:
            strategy_score = self._safe_float(scores, default=0.0)

        metadata["strategy_score"] = strategy_score

        if strategy_score < self.min_strategy_score:
            return {
                "approved": False,
                "reason": f"Strategy underperforming: {strategy_score:.3f} < {self.min_strategy_score:.3f}",
                "score": max(0.0, 0.5 + strategy_score),
                "checks": ["strategy_learning:failed"],
                "metadata": metadata,
            }

        return {
            "approved": True,
            "reason": "Strategy learning passed",
            "score": strategy_score,
            "checks": ["strategy_learning:passed"],
            "metadata": metadata,
        }

    def _check_regime_learning(self, current_regime: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {"market_regime": current_regime}

        if not self.use_regime_learning or self.learning_engine is None:
            return {
                "approved": True,
                "reason": "Regime learning disabled",
                "score": 0.0,
                "checks": ["regime_learning:disabled"],
                "metadata": metadata,
            }

        if not current_regime:
            return {
                "approved": True,
                "reason": "No current regime supplied",
                "score": 0.0,
                "checks": ["regime_learning:no_regime"],
                "metadata": metadata,
            }

        method = getattr(self.learning_engine, "regime_performance", None)

        if not callable(method):
            return {
                "approved": True,
                "reason": "Regime performance unavailable",
                "score": 0.0,
                "checks": ["regime_learning:unavailable"],
                "metadata": metadata,
            }

        try:
            regime_perf = method()
        except Exception as exc:
            metadata["error"] = str(exc)
            return {
                "approved": True,
                "reason": "Regime scoring failed open",
                "score": 0.0,
                "checks": ["regime_learning:error_failed_open"],
                "metadata": metadata,
            }

        if isinstance(regime_perf, dict):
            regime_score = self._safe_float(
                regime_perf.get(current_regime, regime_perf.get(
                    current_regime.lower(), 0.0)),
                default=0.0,
            )
        else:
            regime_score = self._safe_float(regime_perf, default=0.0)

        metadata["regime_score"] = regime_score

        if regime_score < self.min_regime_score:
            return {
                "approved": False,
                "reason": f"Bad regime performance: {regime_score:.3f} < {self.min_regime_score:.3f}",
                "score": max(0.0, 0.5 + regime_score),
                "checks": ["regime_learning:failed"],
                "metadata": metadata,
            }

        return {
            "approved": True,
            "reason": "Regime learning passed",
            "score": regime_score,
            "checks": ["regime_learning:passed"],
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------

    def _final_score(
        self,
        *,
        confidence: float,
        vote_margin: float,
        risk_score: float,
        strategy_score: float,
        regime_score: float,
    ) -> float:
        base = (
            confidence * 0.55
            + vote_margin * 0.25
            + (1.0 - risk_score) * 0.20
        )

        # Learning scores are performance nudges, not replacements.
        learning_bonus = 0.0
        learning_bonus += self._clamp(strategy_score, -1.0, 1.0) * 0.05
        learning_bonus += self._clamp(regime_score, -1.0, 1.0) * 0.03

        return self._clamp(base + learning_bonus, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _float_attr(self, obj: Any, name: str, default: float = 0.0) -> float:
        value = getattr(obj, name, None)

        if value is None and isinstance(obj, dict):
            value = obj.get(name)

        return self._safe_float(value, default=default)

    def _str_attr(self, obj: Any, name: str, default: str = "") -> str:
        value = getattr(obj, name, None)

        if value is None and isinstance(obj, dict):
            value = obj.get(name)

        return str(value if value is not None else default).strip()

    def _snapshot_float(self, snapshot: Any, key: str, default: float = 0.0) -> float:
        if isinstance(snapshot, dict):
            return self._safe_float(snapshot.get(key), default=default)

        value = getattr(snapshot, key, default)
        return self._safe_float(value, default=default)

    def _symbol_exposure(self, portfolio_snapshot: Any, symbol: str) -> float:
        normalized = str(symbol or "").strip().upper()

        if not normalized:
            return 0.0
        if isinstance(portfolio_snapshot, dict):
            positions = (
                portfolio_snapshot.get("positions")
                or portfolio_snapshot.get("open_positions")
                or portfolio_snapshot.get("holdings")
            )
        else:
            positions = (
                getattr(portfolio_snapshot, "positions", None)
                or getattr(portfolio_snapshot, "open_positions", None)
                or getattr(portfolio_snapshot, "holdings", None)
            )

        if isinstance(positions, dict):
            item = positions.get(normalized)
            if item is None:
                item = positions.get(symbol)

            return abs(
                self._safe_float(
                    self._position_value(item),
                    default=0.0,
                )
            )

        if isinstance(positions, list):
            total = 0.0
            for item in positions:

                if isinstance(item, dict):
                    item_symbol = str(item.get("symbol") or "").strip().upper()
                else:
                    item_symbol = str(
                        getattr(item, "symbol", "") or "").strip().upper()

                if item_symbol != normalized:
                    continue

                total += abs(self._safe_float(self._position_value(item), default=0.0))

            return total

        return 0.0

    def _position_value(self, position: Any) -> float:
        if position is None:
            return 0.0

        if isinstance(position, dict):
            for key in ("notional", "market_value", "exposure", "value"):
                if key in position:
                    return self._safe_float(position.get(key), default=0.0)

            qty = self._safe_float(position.get("quantity", position.get(
                "amount", position.get("size"))), default=0.0)
            price = self._safe_float(position.get("price", position.get(
                "last_price", position.get("mark_price"))), default=0.0)
            return qty * price

        for key in ("notional", "market_value", "exposure", "value"):
            value = getattr(position, key, None)
            if value is not None:
                return self._safe_float(value, default=0.0)

        qty = self._safe_float(
            getattr(position, "quantity", getattr(
                position, "amount", getattr(position, "size", 0.0))),
            default=0.0,
        )
        price = self._safe_float(
            getattr(position, "price", getattr(position, "last_price",
                    getattr(position, "mark_price", 0.0))),
            default=0.0,
        )
        return qty * price

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return float(default)

        if number != number or number in {float("inf"), float("-inf")}:
            return float(default)

        return number

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
