from __future__ import annotations

import json
import math
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


try:
    import numpy as np
except Exception:  # keeps the engine usable even if numpy is missing
    np = None  # type: ignore


def _now() -> float:
    return time.time()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return float(default)

    try:
        number = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return bool(default)

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _mean(values: Iterable[float], default: float = 0.0) -> float:
    values = [float(v) for v in values if math.isfinite(float(v))]

    if not values:
        return float(default)

    if np is not None:
        return float(np.mean(values))

    return float(statistics.mean(values))


def _median(values: Iterable[float], default: float = 0.0) -> float:
    values = [float(v) for v in values if math.isfinite(float(v))]

    if not values:
        return float(default)

    return float(statistics.median(values))


def _stdev(values: Iterable[float], default: float = 0.0) -> float:
    values = [float(v) for v in values if math.isfinite(float(v))]

    if len(values) < 2:
        return float(default)

    if np is not None:
        return float(np.std(values))

    return float(statistics.pstdev(values))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


@dataclass(slots=True)
class LearningRecord:
    timestamp: float = field(default_factory=_now)
    pnl: float = 0.0
    outcome: str = "breakeven"

    confidence: float = 0.5
    decision: str = "HOLD"
    side: str = ""
    strategy: str = "unknown"
    symbol: str = ""
    timeframe: str = ""

    market_regime: str = "unknown"
    volatility_regime: str = "unknown"

    atr: float = 0.0
    atr_pct: float = 0.0
    sl_hit: bool = False
    tp_hit: bool = False
    duration: float = 0.0

    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    notional: float = 0.0

    risk_score: float = 0.5
    vote_margin: float = 0.0
    model_name: str = ""
    reason: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "LearningRecord":
        data = dict(payload or {})

        pnl = _safe_float(data.get("pnl"), 0.0)
        outcome = str(data.get("outcome") or "").strip().lower()

        if outcome not in {"win", "loss", "breakeven"}:
            outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

        return cls(
            timestamp=_safe_float(data.get("timestamp"), _now()),
            pnl=pnl,
            outcome=outcome,
            confidence=_clamp(_safe_float(data.get("confidence"), 0.5), 0.0, 1.0),
            decision=str(data.get("decision") or data.get("action") or "HOLD").strip().upper(),
            side=str(data.get("side") or "").strip().lower(),
            strategy=str(data.get("strategy") or data.get("strategy_name") or "unknown").strip() or "unknown",
            symbol=str(data.get("symbol") or "").strip().upper(),
            timeframe=str(data.get("timeframe") or "").strip(),
            market_regime=str(data.get("market_regime") or data.get("regime") or "unknown").strip().lower() or "unknown",
            volatility_regime=str(data.get("volatility_regime") or "unknown").strip().lower() or "unknown",
            atr=_safe_float(data.get("atr"), 0.0),
            atr_pct=_safe_float(data.get("atr_pct"), 0.0),
            sl_hit=_safe_bool(data.get("sl_hit"), False),
            tp_hit=_safe_bool(data.get("tp_hit"), False),
            duration=_safe_float(data.get("duration"), 0.0),
            entry_price=_safe_float(data.get("entry_price"), 0.0),
            exit_price=_safe_float(data.get("exit_price"), 0.0),
            quantity=_safe_float(data.get("quantity") or data.get("qty") or data.get("amount"), 0.0),
            notional=_safe_float(data.get("notional"), 0.0),
            risk_score=_clamp(_safe_float(data.get("risk_score"), 0.5), 0.0, 1.0),
            vote_margin=_clamp(_safe_float(data.get("vote_margin"), 0.0), 0.0, 1.0),
            model_name=str(data.get("model_name") or "").strip(),
            reason=str(data.get("reason") or "").strip(),
            metadata=dict(data.get("metadata") or {}),
        )


class LearningEngine:
    """Adaptive learning layer for trade feedback.

    Responsibilities:
    - record realized trade outcomes
    - adapt confidence thresholds
    - adapt ATR stop multiplier
    - score strategies by recent profitability
    - score market regimes by recent profitability
    - expose reusable snapshots for dashboards and filters
    """

    def __init__(
            self,
            max_history: int = 50_000,
            *,
            confidence_threshold: float = 0.65,
            min_confidence_threshold: float = 0.50,
            max_confidence_threshold: float = 0.85,
            atr_multiplier: float = 2.0,
            min_atr_multiplier: float = 1.2,
            max_atr_multiplier: float = 3.5,
            recent_window: int = 100,
            warmup_trades: int = 30,
            storage_path: str | Path | None = None,
            autosave: bool = False,
    ) -> None:
        self.history: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_history or 50_000)))

        self.confidence_threshold = _clamp(confidence_threshold, min_confidence_threshold, max_confidence_threshold)
        self.min_confidence_threshold = float(min_confidence_threshold)
        self.max_confidence_threshold = float(max_confidence_threshold)

        self.atr_multiplier = _clamp(atr_multiplier, min_atr_multiplier, max_atr_multiplier)
        self.min_atr_multiplier = float(min_atr_multiplier)
        self.max_atr_multiplier = float(max_atr_multiplier)

        self.recent_window = max(10, int(recent_window or 100))
        self.warmup_trades = max(1, int(warmup_trades or 30))

        self.storage_path = Path(storage_path) if storage_path else None
        self.autosave = bool(autosave)

        if self.storage_path is not None and self.storage_path.exists():
            self.load(self.storage_path)

    # =========================
    # RECORD TRADE OUTCOME
    # =========================

    def record_trade(self, trade_data: dict[str, Any]) -> dict[str, Any]:
        """Record one completed trade outcome.

        Accepts your old payload keys and newer TradeAdviser keys.
        """
        record = LearningRecord.from_mapping(dict(trade_data or {})).to_dict()

        # If notional is absent, infer it.
        if _safe_float(record.get("notional"), 0.0) <= 0:
            entry_price = _safe_float(record.get("entry_price"), 0.0)
            quantity = abs(_safe_float(record.get("quantity"), 0.0))

            if entry_price > 0 and quantity > 0:
                record["notional"] = entry_price * quantity

        self.history.append(record)

        # Gradually adapt after each new trade.
        self.get_dynamic_confidence_threshold()
        self.update_atr_multiplier()

        if self.autosave and self.storage_path is not None:
            self.save(self.storage_path)

        return record

    def record_many(self, trades: Iterable[dict[str, Any]]) -> int:
        count = 0

        for trade in trades or []:
            if not isinstance(trade, dict):
                continue

            self.record_trade(trade)
            count += 1

        return count

    # =========================
    # DYNAMIC CONFIDENCE THRESHOLD
    # =========================

    def get_dynamic_confidence_threshold(self) -> float:
        if len(self.history) < self.warmup_trades:
            return float(self.confidence_threshold)

        recent = self._recent(self.recent_window)

        wins = [h for h in recent if h.get("outcome") == "win"]
        losses = [h for h in recent if h.get("outcome") == "loss"]

        if not wins or not losses:
            return float(self.confidence_threshold)

        win_conf = _mean([_safe_float(h.get("confidence"), 0.5) for h in wins], 0.5)
        loss_conf = _mean([_safe_float(h.get("confidence"), 0.5) for h in losses], 0.5)

        win_rate = len(wins) / max(1, len(wins) + len(losses))
        avg_recent_pnl = _mean([_safe_float(h.get("pnl"), 0.0) for h in recent], 0.0)

        # Base threshold between average losing confidence and winning confidence.
        new_threshold = (win_conf + loss_conf) / 2.0

        # If recent performance is bad, demand stronger confidence.
        if win_rate < 0.45 or avg_recent_pnl < 0:
            new_threshold += 0.03

        # If recent performance is strong, allow slightly more trades.
        elif win_rate > 0.58 and avg_recent_pnl > 0:
            new_threshold -= 0.02

        new_threshold = _clamp(
            new_threshold,
            self.min_confidence_threshold,
            self.max_confidence_threshold,
        )

        # Smooth update to avoid jumps.
        self.confidence_threshold = _clamp(
            0.85 * self.confidence_threshold + 0.15 * new_threshold,
            self.min_confidence_threshold,
            self.max_confidence_threshold,
            )

        return float(self.confidence_threshold)

    # =========================
    # ATR ADAPTATION
    # =========================

    def update_atr_multiplier(self) -> float:
        if len(self.history) < max(50, self.warmup_trades):
            return float(self.atr_multiplier)

        recent = self._recent(self.recent_window)

        sl_losses = [h for h in recent if _safe_bool(h.get("sl_hit"), False)]
        tp_wins = [h for h in recent if _safe_bool(h.get("tp_hit"), False)]

        losses = [h for h in recent if h.get("outcome") == "loss"]
        wins = [h for h in recent if h.get("outcome") == "win"]

        if len(sl_losses) > len(tp_wins) and len(losses) >= len(wins):
            # Too many stop-outs: widen stop distance.
            self.atr_multiplier *= 1.035
        elif len(tp_wins) > len(sl_losses) and len(wins) > len(losses):
            # Good take-profit behavior: tighten slightly.
            self.atr_multiplier *= 0.985
        else:
            # Mean-revert gently toward default.
            self.atr_multiplier = 0.98 * self.atr_multiplier + 0.02 * 2.0

        self.atr_multiplier = _clamp(
            self.atr_multiplier,
            self.min_atr_multiplier,
            self.max_atr_multiplier,
        )

        return float(self.atr_multiplier)

    # =========================
    # STRATEGY PERFORMANCE
    # =========================

    def strategy_scores(
            self,
            *,
            recent: int | None = None,
            min_samples: int = 1,
            include_details: bool = False,
    ) -> dict[str, float] | dict[str, dict[str, Any]]:
        rows = self._recent(recent or len(self.history))

        grouped: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            strategy = str(row.get("strategy") or "unknown").strip() or "unknown"
            grouped.setdefault(strategy, []).append(row)

        result: dict[str, Any] = {}

        for strategy, items in grouped.items():
            if len(items) < max(1, int(min_samples or 1)):
                continue

            pnls = [_safe_float(item.get("pnl"), 0.0) for item in items]
            wins = [item for item in items if item.get("outcome") == "win"]
            losses = [item for item in items if item.get("outcome") == "loss"]

            avg_pnl = _mean(pnls, 0.0)
            total_pnl = sum(pnls)
            win_rate = len(wins) / max(1, len(wins) + len(losses))

            # Score combines profitability, consistency, and hit rate.
            score = avg_pnl
            score += total_pnl / max(1, len(items)) * 0.25
            score += (win_rate - 0.5) * abs(avg_pnl if avg_pnl else 1.0)

            if include_details:
                result[strategy] = {
                    "score": float(score),
                    "avg_pnl": float(avg_pnl),
                    "total_pnl": float(total_pnl),
                    "win_rate": float(win_rate),
                    "trades": len(items),
                    "wins": len(wins),
                    "losses": len(losses),
                    "pnl_stdev": _stdev(pnls, 0.0),
                }
            else:
                result[strategy] = float(score)

        return result

    def best_strategy(self, *, recent: int | None = None, min_samples: int = 3) -> str | None:
        scores = self.strategy_scores(recent=recent, min_samples=min_samples)

        if not scores:
            return None

        return max(scores.items(), key=lambda item: float(item[1]))[0]

    def strategy_weight(
            self,
            strategy_name: str,
            *,
            recent: int | None = None,
            min_weight: float = 0.70,
            max_weight: float = 1.35,
    ) -> float:
        strategy = str(strategy_name or "unknown").strip() or "unknown"
        details = self.strategy_scores(recent=recent, include_details=True)

        payload = details.get(strategy) if isinstance(details, dict) else None

        if not isinstance(payload, dict):
            return 1.0

        score = _safe_float(payload.get("score"), 0.0)
        win_rate = _safe_float(payload.get("win_rate"), 0.5)
        trades = _safe_int(payload.get("trades"), 0)

        confidence = min(1.0, trades / 20.0)
        raw_weight = 1.0 + confidence * ((win_rate - 0.5) * 0.7)

        if score < 0:
            raw_weight -= 0.10 * confidence
        elif score > 0:
            raw_weight += 0.05 * confidence

        return _clamp(raw_weight, min_weight, max_weight)

    # =========================
    # REGIME PERFORMANCE
    # =========================

    def regime_performance(
            self,
            *,
            recent: int | None = None,
            include_details: bool = False,
    ) -> dict[str, float] | dict[str, dict[str, Any]]:
        rows = self._recent(recent or len(self.history))

        grouped: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            regime = str(row.get("market_regime") or "unknown").strip().lower() or "unknown"
            grouped.setdefault(regime, []).append(row)

        result: dict[str, Any] = {}

        for regime, items in grouped.items():
            pnls = [_safe_float(item.get("pnl"), 0.0) for item in items]
            wins = [item for item in items if item.get("outcome") == "win"]
            losses = [item for item in items if item.get("outcome") == "loss"]

            avg_pnl = _mean(pnls, 0.0)
            total_pnl = sum(pnls)
            win_rate = len(wins) / max(1, len(wins) + len(losses))

            if include_details:
                result[regime] = {
                    "avg_pnl": float(avg_pnl),
                    "total_pnl": float(total_pnl),
                    "win_rate": float(win_rate),
                    "trades": len(items),
                    "wins": len(wins),
                    "losses": len(losses),
                }
            else:
                result[regime] = float(avg_pnl)

        return result

    def should_avoid_regime(self, regime: str, *, recent: int = 100, min_samples: int = 5) -> bool:
        regime_key = str(regime or "unknown").strip().lower() or "unknown"
        details = self.regime_performance(recent=recent, include_details=True)
        payload = details.get(regime_key) if isinstance(details, dict) else None

        if not isinstance(payload, dict):
            return False

        if _safe_int(payload.get("trades"), 0) < min_samples:
            return False

        return _safe_float(payload.get("avg_pnl"), 0.0) < 0 and _safe_float(payload.get("win_rate"), 0.5) < 0.45

    # =========================
    # EXTRA DASHBOARD / FILTER HELPERS
    # =========================

    def recent_win_rate(self, recent: int = 100) -> float:
        rows = self._recent(recent)
        wins = [row for row in rows if row.get("outcome") == "win"]
        losses = [row for row in rows if row.get("outcome") == "loss"]

        return len(wins) / max(1, len(wins) + len(losses))

    def recent_pnl(self, recent: int = 100) -> float:
        return float(sum(_safe_float(row.get("pnl"), 0.0) for row in self._recent(recent)))

    def avg_trade_pnl(self, recent: int = 100) -> float:
        rows = self._recent(recent)
        return _mean([_safe_float(row.get("pnl"), 0.0) for row in rows], 0.0)

    def confidence_buckets(self, *, bucket_size: float = 0.10, recent: int | None = None) -> dict[str, dict[str, Any]]:
        rows = self._recent(recent or len(self.history))
        bucket_size = _clamp(bucket_size, 0.01, 1.0)

        buckets: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            confidence = _clamp(_safe_float(row.get("confidence"), 0.0), 0.0, 1.0)
            low = math.floor(confidence / bucket_size) * bucket_size
            high = min(1.0, low + bucket_size)
            label = f"{low:.2f}-{high:.2f}"
            buckets.setdefault(label, []).append(row)

        result: dict[str, dict[str, Any]] = {}

        for label, items in buckets.items():
            pnls = [_safe_float(item.get("pnl"), 0.0) for item in items]
            wins = [item for item in items if item.get("outcome") == "win"]
            losses = [item for item in items if item.get("outcome") == "loss"]

            result[label] = {
                "trades": len(items),
                "avg_pnl": _mean(pnls, 0.0),
                "total_pnl": sum(pnls),
                "win_rate": len(wins) / max(1, len(wins) + len(losses)),
            }

        return result

    def snapshot(self, recent: int = 100) -> dict[str, Any]:
        rows = self._recent(recent)

        wins = [row for row in rows if row.get("outcome") == "win"]
        losses = [row for row in rows if row.get("outcome") == "loss"]
        breakeven = [row for row in rows if row.get("outcome") == "breakeven"]
        pnls = [_safe_float(row.get("pnl"), 0.0) for row in rows]

        return {
            "history_size": len(self.history),
            "recent_window": len(rows),
            "confidence_threshold": float(self.confidence_threshold),
            "atr_multiplier": float(self.atr_multiplier),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate": len(wins) / max(1, len(wins) + len(losses)),
            "recent_pnl": float(sum(pnls)),
            "avg_trade_pnl": _mean(pnls, 0.0),
            "median_trade_pnl": _median(pnls, 0.0),
            "pnl_stdev": _stdev(pnls, 0.0),
            "best_strategy": self.best_strategy(recent=recent, min_samples=3),
            "strategy_scores": self.strategy_scores(recent=recent, include_details=True),
            "regime_performance": self.regime_performance(recent=recent, include_details=True),
        }

    def export_records(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.history]

    def clear(self) -> None:
        self.history.clear()

    # =========================
    # SAVE / LOAD
    # =========================

    def save(self, path: str | Path = "learning.json") -> bool:
        target = Path(path)

        payload = {
            "version": 2,
            "saved_at": _now(),
            "confidence_threshold": self.confidence_threshold,
            "atr_multiplier": self.atr_multiplier,
            "history": list(self.history),
        }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            return True
        except Exception:
            return False

    def load(self, path: str | Path = "learning.json") -> bool:
        target = Path(path)

        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return False

        try:
            if isinstance(raw, dict):
                history = raw.get("history") or []
                self.confidence_threshold = _clamp(
                    _safe_float(raw.get("confidence_threshold"), self.confidence_threshold),
                    self.min_confidence_threshold,
                    self.max_confidence_threshold,
                )
                self.atr_multiplier = _clamp(
                    _safe_float(raw.get("atr_multiplier"), self.atr_multiplier),
                    self.min_atr_multiplier,
                    self.max_atr_multiplier,
                )
            elif isinstance(raw, list):
                history = raw
            else:
                return False

            cleaned = []
            for item in history:
                if not isinstance(item, dict):
                    continue
                cleaned.append(LearningRecord.from_mapping(item).to_dict())

            self.history = deque(cleaned, maxlen=self.history.maxlen)
            return True

        except Exception:
            return False

    # =========================
    # INTERNAL
    # =========================

    def _recent(self, count: int | None = None) -> list[dict[str, Any]]:
        if count is None:
            return list(self.history)

        count = max(1, int(count or 1))
        return list(self.history)[-count:]


__all__ = ["LearningEngine", "LearningRecord"]