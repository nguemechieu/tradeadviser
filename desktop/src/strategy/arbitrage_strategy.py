"""Arbitrage strategy that watches market ticks and emits cross-exchange orders."""

import time
from typing import Any

from event_bus.event_types import EventType
from strategy.base_strategy import BaseStrategy


class ArbitrageStrategy(BaseStrategy):
    """Detect short-lived cross-exchange price dislocations for the same symbol."""

    def __init__(
        self,
        event_bus: Any = None,
        *,
        min_spread=0.01,
        max_quote_age_seconds=10.0,
        signal_amount=0.01,
    ):
        super().__init__(event_bus, signal_amount=signal_amount, max_history=50)
        self.min_spread = max(0.0001, float(min_spread or 0.01))
        self.max_quote_age_seconds = max(0.1, float(max_quote_age_seconds or 10.0))
        self.prices: dict[str, dict[str, dict[str, float]]] = {}

        if self.bus is not None:
            self.bus.subscribe(EventType.MARKET_TICK, self.on_tick)

    def _fresh_quotes(self, symbol_prices, *, now=None):
        now_ts = float(now if now is not None else time.time())
        fresh = {}
        for exchange, payload in (symbol_prices or {}).items():
            if not isinstance(payload, dict):
                continue
            timestamp = float(payload.get("timestamp", 0.0) or 0.0)
            if now_ts - timestamp > self.max_quote_age_seconds:
                continue
            price = payload.get("price")
            try:
                numeric_price = float(price)
            except (TypeError, ValueError):
                continue
            if numeric_price <= 0:
                continue
            fresh[str(exchange)] = {"price": numeric_price, "timestamp": timestamp}
        return fresh

    def _signal_from_quotes(self, quotes, *, symbol="BACKTEST", now=None):
        symbol_prices = {}
        if isinstance(quotes, dict):
            if all(isinstance(value, dict) for value in quotes.values()):
                symbol_prices = quotes
            else:
                for exchange, price in quotes.items():
                    symbol_prices[str(exchange)] = {"price": price, "timestamp": float(now or time.time())}
        elif isinstance(quotes, list):
            for quote in quotes:
                if not isinstance(quote, dict):
                    continue
                exchange = quote.get("exchange")
                price = quote.get("price")
                if exchange in (None, "") or price in (None, ""):
                    continue
                symbol_prices[str(exchange)] = {
                    "price": price,
                    "timestamp": float(quote.get("timestamp", now or time.time()) or time.time()),
                }

        fresh_quotes = self._fresh_quotes(symbol_prices, now=now)
        if len(fresh_quotes) < 2:
            return None

        sorted_quotes = sorted(
            fresh_quotes.items(),
            key=lambda item: item[1]["price"],
        )
        low_exchange, low_payload = sorted_quotes[0]
        high_exchange, high_payload = sorted_quotes[-1]
        low_price = float(low_payload["price"])
        high_price = float(high_payload["price"])
        if low_price <= 0 or high_price <= low_price:
            return None

        spread = (high_price - low_price) / low_price
        if spread < self.min_spread:
            return None

        return self._build_signal(
            symbol,
            "buy",
            reason=(
                f"Arbitrage spread of {spread * 100.0:.2f}% detected: buy on {low_exchange} "
                f"at {low_price:.6f} and sell on {high_exchange} at {high_price:.6f}."
            ),
            confidence=round(min(spread / self.min_spread, 1.0), 4),
            spread_abs=round(high_price - low_price, 8),
            spread_bps=round(spread * 10000.0, 2),
            buy_exchange=low_exchange,
            sell_exchange=high_exchange,
            legs=[
                {"exchange": low_exchange, "side": "buy", "price": low_price},
                {"exchange": high_exchange, "side": "sell", "price": high_price},
            ],
        )

    def generate_signal(self, quotes, strategy_name=None):
        return self._signal_from_quotes(quotes)

    async def on_tick(self, event: Any) -> None:
        tick = getattr(event, "data", {}) or {}
        if not isinstance(tick, dict):
            return

        exchange = str(tick.get("exchange") or "").strip().lower()
        symbol = tick.get("symbol")
        price = tick.get("price")
        if not exchange or symbol in (None, "") or price in (None, ""):
            return

        normalized_symbol = self._normalize_symbol(symbol)
        symbol_prices = self.prices.setdefault(normalized_symbol, {})
        try:
            symbol_prices[exchange] = {
                "price": float(price),
                "timestamp": float(tick.get("timestamp", time.time()) or time.time()),
            }
        except (TypeError, ValueError):
            return

        signal = self._signal_from_quotes(symbol_prices, symbol=normalized_symbol)
        if signal is None or not self._should_emit_signal(normalized_symbol, signal.get("side")):
            return

        await self.signal(
            signal["symbol"],
            signal["side"],
            signal.get("amount"),
            reason=signal.get("reason"),
            confidence=signal.get("confidence"),
            spread_abs=signal.get("spread_abs"),
            spread_bps=signal.get("spread_bps"),
            buy_exchange=signal.get("buy_exchange"),
            sell_exchange=signal.get("sell_exchange"),
            legs=signal.get("legs"),
        )
