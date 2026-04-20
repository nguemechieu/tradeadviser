from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from derivatives.core.models import BrokerRoute, TradingSignal


class BaseStrategy(ABC):
    name = "base"

    def __init__(self, *, default_size: float = 1.0, min_history: int = 30, duration: float = 3600.0, **kwargs) -> None:
        self.default_size = max(0.0, float(default_size))
        self.min_history = max(5, int(min_history))
        self.duration = float(duration)
        self.params = dict(kwargs)

    @abstractmethod
    def evaluate(
        self,
        *,
        symbol: str,
        price: float,
        features: dict[str, float],
        history: list[float],
        route: BrokerRoute | None,
        now: datetime,
    ) -> TradingSignal | None:
        raise NotImplementedError


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"

    def evaluate(self, *, symbol, price, features, history, route, now):
        del history, route
        ema_gap = float(features.get("ema_gap", 0.0))
        momentum = float(features.get("momentum_10", 0.0))
        atr = max(float(features.get("atr", 0.0)), price * 0.0025)
        if ema_gap > 0.002 and momentum > 0:
            confidence = min(0.95, 0.55 + abs(ema_gap) * 10.0)
            return TradingSignal(
                symbol=symbol,
                side="buy",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price - atr * 2.0,
                take_profit=price + atr * 4.0,
                duration=self.duration,
                metadata={"features": dict(features), "timestamp": now.isoformat()},
            )
        if ema_gap < -0.002 and momentum < 0:
            confidence = min(0.95, 0.55 + abs(ema_gap) * 10.0)
            return TradingSignal(
                symbol=symbol,
                side="sell",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price + atr * 2.0,
                take_profit=price - atr * 4.0,
                duration=self.duration,
                metadata={"features": dict(features), "timestamp": now.isoformat()},
            )
        return None


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def evaluate(self, *, symbol, price, features, history, route, now):
        del history, route
        rsi = float(features.get("rsi", 50.0))
        ema_gap = float(features.get("ema_gap", 0.0))
        atr = max(float(features.get("atr", 0.0)), price * 0.0025)
        if rsi <= 30.0 and ema_gap < 0:
            confidence = min(0.9, 0.5 + (30.0 - rsi) / 50.0)
            return TradingSignal(
                symbol=symbol,
                side="buy",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price - atr * 1.5,
                take_profit=price + atr * 2.5,
                duration=self.duration / 2.0,
                metadata={"features": dict(features), "timestamp": now.isoformat()},
            )
        if rsi >= 70.0 and ema_gap > 0:
            confidence = min(0.9, 0.5 + (rsi - 70.0) / 50.0)
            return TradingSignal(
                symbol=symbol,
                side="sell",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price + atr * 1.5,
                take_profit=price - atr * 2.5,
                duration=self.duration / 2.0,
                metadata={"features": dict(features), "timestamp": now.isoformat()},
            )
        return None


class BreakoutStrategy(BaseStrategy):
    name = "breakout"

    def evaluate(self, *, symbol, price, features, history, route, now):
        del route
        if len(history) < self.min_history:
            return None
        recent_high = max(history[-self.min_history :])
        recent_low = min(history[-self.min_history :])
        atr = max(float(features.get("atr", 0.0)), price * 0.003)
        if price >= recent_high and recent_high > 0:
            confidence = min(0.92, 0.6 + (price - recent_low) / max(price, 1e-9))
            return TradingSignal(
                symbol=symbol,
                side="buy",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price - atr * 2.0,
                take_profit=price + atr * 3.5,
                duration=self.duration,
                metadata={"features": dict(features), "timestamp": now.isoformat(), "recent_high": recent_high},
            )
        if price <= recent_low and recent_low > 0:
            confidence = min(0.92, 0.6 + (recent_high - price) / max(recent_high, 1e-9))
            return TradingSignal(
                symbol=symbol,
                side="sell",
                confidence=confidence,
                size=max(self.default_size, confidence * self.default_size),
                strategy_name=self.name,
                stop_loss=price + atr * 2.0,
                take_profit=price - atr * 3.5,
                duration=self.duration,
                metadata={"features": dict(features), "timestamp": now.isoformat(), "recent_low": recent_low},
            )
        return None


class MLStrategy(BaseStrategy):
    name = "ml"

    def __init__(self, *, inference_engine=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.inference_engine = inference_engine

    def evaluate(self, *, symbol, price, features, history, route, now):
        del history, route
        if self.inference_engine is None:
            return None
        inference = self.inference_engine.score(features)
        probability = float(inference.get("probability", 0.5))
        confidence = float(inference.get("confidence", 0.0))
        approved = bool(inference.get("approved"))
        if not approved:
            return None
        side = "buy" if float(features.get("ema_gap", 0.0)) >= 0 else "sell"
        atr = max(float(features.get("atr", 0.0)), price * 0.002)
        return TradingSignal(
            symbol=symbol,
            side=side,
            confidence=max(0.55, confidence),
            size=max(self.default_size, probability * self.default_size),
            strategy_name=self.name,
            stop_loss=price - atr * 2.0 if side == "buy" else price + atr * 2.0,
            take_profit=price + atr * 3.0 if side == "buy" else price - atr * 3.0,
            duration=self.duration,
            metadata={
                "features": dict(features),
                "timestamp": now.isoformat(),
                "probability": probability,
                "regime": inference.get("regime"),
                "model_scores": dict(inference.get("model_scores") or {}),
            },
        )
