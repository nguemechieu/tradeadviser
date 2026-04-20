import numpy as np

from event_bus.event_types import EventType
from strategy.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """Fade stretched moves using rolling mean and z-score confirmation."""

    def __init__(
        self,
        event_bus=None,
        *,
        lookback=20,
        entry_zscore=1.5,
        signal_amount=0.01,
        max_history=250,
    ):
        super().__init__(event_bus, signal_amount=signal_amount, max_history=max_history)
        self.lookback = max(5, int(lookback or 20))
        self.entry_zscore = max(0.5, float(entry_zscore or 1.5))

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
        if len(prices) < self.lookback:
            return None

        window = np.asarray(prices[-self.lookback:], dtype=float)
        mean_price = float(np.mean(window))
        std_price = float(np.std(window))
        latest_price = float(window[-1])
        if mean_price <= 0 or std_price <= 1e-9:
            return None

        zscore = (latest_price - mean_price) / std_price
        confidence = min(abs(zscore) / max(self.entry_zscore, 1e-9), 1.0)

        if zscore <= -self.entry_zscore:
            return self._build_signal(
                symbol,
                "buy",
                reason=(
                    f"Price stretched {zscore:.2f} standard deviations below the "
                    f"{self.lookback}-bar mean ({mean_price:.4f}), favoring reversion."
                ),
                confidence=round(confidence, 4),
            )

        if zscore >= self.entry_zscore:
            return self._build_signal(
                symbol,
                "sell",
                reason=(
                    f"Price stretched {zscore:.2f} standard deviations above the "
                    f"{self.lookback}-bar mean ({mean_price:.4f}), favoring mean reversion."
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
