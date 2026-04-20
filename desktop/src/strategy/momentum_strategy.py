import numpy as np

from event_bus.event_types import EventType
from strategy.base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Trend-following strategy using MA alignment plus price momentum confirmation."""

    def __init__(
        self,
        event_bus=None,
        *,
        short_window=5,
        long_window=20,
        momentum_window=5,
        min_momentum=0.01,
        signal_amount=0.01,
        max_history=250,
    ):
        super().__init__(event_bus, signal_amount=signal_amount, max_history=max_history)
        self.short_window = max(2, int(short_window or 5))
        self.long_window = max(self.short_window + 1, int(long_window or 20))
        self.momentum_window = max(2, int(momentum_window or 5))
        self.min_momentum = abs(float(min_momentum or 0.01))

        if self.bus is not None:
            self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    @staticmethod
    def _extract_prices(candles):
        prices = []
        for candle in candles or []:
            if hasattr(candle, "get"):
                price = candle.get("close", candle.get("price"))
            else:
                try:
                    price = candle[4]
                except Exception:
                    try:
                        price = candle[0]
                    except Exception:
                        price = None
            if price is None:
                continue
            try:
                prices.append(float(price))
            except (TypeError, ValueError):
                continue
        return prices

    def _signal_from_prices(self, prices, *, symbol="BACKTEST"):
        minimum_history = max(self.long_window, self.momentum_window + 1)
        if len(prices) < minimum_history:
            return None

        short_ma = float(np.mean(prices[-self.short_window:]))
        long_ma = float(np.mean(prices[-self.long_window:]))
        baseline_price = float(prices[-self.momentum_window - 1] or 0.0)
        if baseline_price <= 0:
            return None

        latest_price = float(prices[-1])
        momentum = (latest_price / baseline_price) - 1.0
        confidence = min(max(abs(momentum) / max(self.min_momentum, 1e-9), 0.0), 1.0)

        if short_ma > long_ma and momentum >= self.min_momentum:
            return self._build_signal(
                symbol,
                "buy",
                reason=(
                    f"Momentum confirmed higher highs: short MA {short_ma:.4f} above "
                    f"long MA {long_ma:.4f} with {momentum * 100.0:.2f}% follow-through."
                ),
                confidence=round(confidence, 4),
            )

        if short_ma < long_ma and momentum <= -self.min_momentum:
            return self._build_signal(
                symbol,
                "sell",
                reason=(
                    f"Momentum confirmed downside continuation: short MA {short_ma:.4f} below "
                    f"long MA {long_ma:.4f} with {momentum * 100.0:.2f}% drift."
                ),
                confidence=round(confidence, 4),
            )

        return None

    def generate_signal(self, candles, strategy_name=None):
        prices = self._extract_prices(candles)
        return self._signal_from_prices(prices)

    async def on_tick(self, event):
        tick = getattr(event, "data", {}) or {}
        if not isinstance(tick, dict):
            return

        symbol = tick.get("symbol")
        price = tick.get("price", tick.get("close"))
        if symbol in (None, "") or price in (None, ""):
            return

        try:
            prices = self._append_price(symbol, price)
        except (TypeError, ValueError):
            return

        signal = self._signal_from_prices(prices, symbol=symbol)
        if signal is None or not self._should_emit_signal(symbol, signal.get("side")):
            return

        await self.signal(
            signal["symbol"],
            signal["side"],
            signal.get("amount"),
            reason=signal.get("reason"),
            confidence=signal.get("confidence"),
        )
