from __future__ import annotations

import asyncio
import json
import logging

import traceback
from datetime import datetime, timezone
from typing import Any

import websockets

from zones_engine import Candle


logger = logging.getLogger("zones.mt4_adapter")


class MT4WebSocketAdapterError(RuntimeError):
    pass


class MT4WebSocketAdapter:
    """
    Adapter between ZonesEngine and your MT4/Python WebSocket bridge.

    This replaces MQL4 terminal functions such as:
      - AccountNumber()
      - Symbol()
      - MarketInfo()
      - iOpen/iHigh/iLow/iClose/iTime
      - OrderSend()
      - OrderClose()
      - OrderDelete()
      - OrderModify()

    Expected bridge pattern:
      request:
        {"action": "...", "...": "..."}

      success reply:
        {"status": "ok", ...}

      error reply:
        {"status": "error", "message": "..."}
    """

    def __init__(
            self,
            url: str = "ws://127.0.0.1:8090/ws",
            *,
            default_symbol: str = "EURUSD",
            account_id_value: str = "mt4",
            timeout_seconds: float = 8.0,
            retries: int = 2,
            retry_delay_seconds: float = 0.15,
            cache_ttl_seconds: float = 1.0,
    ) -> None:
        self.url = url
        self.default_symbol = default_symbol
        self.account_id_value = account_id_value
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds
        self.cache_ttl_seconds = cache_ttl_seconds

        self._cache: dict[str, tuple[float, Any]] = {}

    # ============================================================
    # LOW-LEVEL WEBSOCKET
    # ============================================================

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                async with websockets.connect(self.url) as ws:
                    await asyncio.wait_for(
                        ws.send(json.dumps(payload)),
                        timeout=self.timeout_seconds,
                    )
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout_seconds)

                data = json.loads(raw)

                if not isinstance(data, dict):
                    raise MT4WebSocketAdapterError(f"Bridge returned non-object JSON: {data!r}")

                status = data.get("status", "ok")
                if status not in {"ok", "success"}:
                    message = data.get("message") or data.get("error") or "Unknown bridge error"
                    raise MT4WebSocketAdapterError(str(message))

                return data

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "MT4 adapter request failed attempt=%s action=%s error=%s",
                    attempt + 1,
                    payload.get("action"),
                    exc,
                    )

                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay_seconds)

        raise MT4WebSocketAdapterError(
            f"WebSocket request failed after {self.retries + 1} attempts: {last_error}"
        )

    async def cached_request(
            self,
            key: str,
            payload: dict[str, Any],
            *,
            ttl: float | None = None,
    ) -> dict[str, Any]:
        ttl = self.cache_ttl_seconds if ttl is None else ttl
        now = asyncio.get_running_loop().time()

        cached = self._cache.get(key)
        if cached:
            cached_at, value = cached
            if now - cached_at <= ttl:
                return value

        value = await self.request(payload)
        self._cache[key] = (now, value)
        return value

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            if value is None or value == "":
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)

        text = str(value or "").strip()

        if not text:
            return datetime.now(timezone.utc)

        # Handles ISO strings like 2026-04-24T13:10:05Z
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception as ex:
            logger.warning("Could not parse time: %s", ex)
            traceback.print_exc()

        # Handles MT4 datetime strings if your bridge sends them.
        for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                continue

        return datetime.now(timezone.utc)

    # ============================================================
    # ACCOUNT / SYMBOL
    # ============================================================

    async def account_id(self) -> str:
        try:
            data = await self.cached_request(
                "account",
                {"action": "account_info"},
                ttl=5.0,
            )
            return str(
                data.get("account_id")
                or data.get("account")
                or data.get("account_number")
                or self.account_id_value
            )
        except Exception:
            return self.account_id_value

    async def symbol(self) -> str:
        try:
            data = await self.cached_request(
                "current_symbol",
                {"action": "current_symbol"},
                ttl=2.0,
            )
            return str(data.get("symbol") or self.default_symbol)
        except Exception:
            return self.default_symbol

    async def market_watch_symbols(self) -> list[str]:
        try:
            data = await self.cached_request(
                "market_watch_symbols",
                {"action": "market_watch_symbols"},
                ttl=10.0,
            )
            symbols = data.get("symbols") or []
            if isinstance(symbols, list):
                return [str(s) for s in symbols if str(s).strip()]
        except Exception as exc:
            logger.warning("Could not load market watch symbols: %s", exc)

        return [self.default_symbol]

    # ============================================================
    # QUOTES / SYMBOL INFO
    # ============================================================

    async def quote(self, symbol: str) -> dict[str, Any]:
        return await self.cached_request(
            f"quote:{symbol}",
            {"action": "quote", "symbol": symbol},
            ttl=0.25,
        )

    async def symbol_info(self, symbol: str) -> dict[str, Any]:
        return await self.cached_request(
            f"symbol_info:{symbol}",
            {"action": "symbol_info", "symbol": symbol},
            ttl=10.0,
        )

    async def bid(self, symbol: str) -> float:
        data = await self.quote(symbol)
        return self._to_float(data.get("bid"))

    async def ask(self, symbol: str) -> float:
        data = await self.quote(symbol)
        return self._to_float(data.get("ask"))

    async def spread_points(self, symbol: str) -> float:
        data = await self.quote(symbol)

        if "spread_points" in data:
            return self._to_float(data.get("spread_points"))

        bid = self._to_float(data.get("bid"))
        ask = self._to_float(data.get("ask"))
        point = await self.point(symbol)

        if point <= 0:
            return 0.0

        return abs(ask - bid) / point

    async def point(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        value = self._to_float(data.get("point") or data.get("tick_size"))

        if value <= 0:
            digits = await self.digits(symbol)
            return 10 ** (-digits)

        return value

    async def digits(self, symbol: str) -> int:
        data = await self.symbol_info(symbol)
        digits = self._to_int(data.get("digits"), default=5)
        return max(0, digits)

    async def min_lot(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        return self._to_float(data.get("min_lot"), 0.01)

    async def max_lot(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        return self._to_float(data.get("max_lot"), 100.0)

    async def lot_step(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        return self._to_float(data.get("lot_step"), 0.01)

    async def stop_level_points(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        return self._to_float(data.get("stop_level_points") or data.get("stop_level"), 0.0)

    async def tick_value(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        return self._to_float(data.get("tick_value"), 0.0)

    async def tick_size(self, symbol: str) -> float:
        data = await self.symbol_info(symbol)
        value = self._to_float(data.get("tick_size"), 0.0)
        if value <= 0:
            value = await self.point(symbol)
        return value

    # ============================================================
    # ACCOUNT RISK
    # ============================================================

    async def account_info(self) -> dict[str, Any]:
        return await self.cached_request(
            "account_info",
            {"action": "account_info"},
            ttl=2.0,
        )

    async def equity(self) -> float:
        data = await self.account_info()
        return self._to_float(data.get("equity"))

    async def margin(self) -> float:
        data = await self.account_info()
        return self._to_float(data.get("margin"))

    async def free_margin(self) -> float:
        data = await self.account_info()
        return self._to_float(data.get("free_margin"))

    async def trading_allowed(self, symbol: str) -> bool:
        try:
            data = await self.cached_request(
                f"trading_allowed:{symbol}",
                {"action": "trading_allowed", "symbol": symbol},
                ttl=1.0,
            )
            value = data.get("allowed", data.get("trading_allowed", True))
            return bool(value)
        except Exception as exc:
            logger.warning("Trading allowed check failed for %s: %s", symbol, exc)
            return False

    async def count_open_trades(self, symbol: str, magic_number: int) -> int:
        try:
            data = await self.cached_request(
                f"positions:{symbol}:{magic_number}",
                {
                    "action": "positions",
                    "symbol": symbol,
                    "magic_number": magic_number,
                },
                ttl=1.0,
            )
            positions = data.get("positions") or data.get("orders") or []

            if isinstance(positions, list):
                return len(
                    [
                        p
                        for p in positions
                        if str(p.get("symbol", symbol)) == symbol
                           and self._to_int(p.get("magic_number", magic_number)) == magic_number
                    ]
                )

        except Exception as exc:
            logger.warning("Could not count open trades for %s: %s", symbol, exc)

        return 0

    # ============================================================
    # CANDLES / INDICATORS
    # ============================================================

    async def bars(self, symbol: str, timeframe: str) -> list[Candle]:
        timeframe = timeframe.upper()

        data = await self.cached_request(
            f"bars:{symbol}:{timeframe}",
            {
                "action": "bars",
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": 250,
            },
            ttl=0.75,
        )

        raw_bars = data.get("bars") or data.get("candles") or []

        candles: list[Candle] = []

        if not isinstance(raw_bars, list):
            return candles

        for item in raw_bars:
            if not isinstance(item, dict):
                continue

            timestamp = (
                    item.get("timestamp")
                    or item.get("time")
                    or item.get("datetime")
                    or item.get("t")
            )

            candles.append(
                Candle(
                    timestamp=self._parse_time(timestamp),
                    open=self._to_float(item.get("open") or item.get("o")),
                    high=self._to_float(item.get("high") or item.get("h")),
                    low=self._to_float(item.get("low") or item.get("l")),
                    close=self._to_float(item.get("close") or item.get("c")),
                    volume=self._to_float(item.get("volume") or item.get("v")),
                )
            )

        candles.sort(key=lambda c: c.timestamp)
        return candles

    async def zigzag_pivots(
            self,
            symbol: str,
            timeframe: str,
            depth: int,
            deviation: int,
            backstep: int,
    ) -> list[tuple[int, float]]:
        """
        Preferred bridge reply:
          {
            "status": "ok",
            "pivots": [
              {"shift": 12, "price": 1.0845},
              {"shift": 25, "price": 1.0782}
            ]
          }

        Fallback:
          Calculates simple local swing pivots from candles.
          This is not identical to MT4 ZigZag, but it keeps the engine running.
        """
        try:
            data = await self.cached_request(
                f"zigzag:{symbol}:{timeframe}:{depth}:{deviation}:{backstep}",
                {
                    "action": "zigzag",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "depth": depth,
                    "deviation": deviation,
                    "backstep": backstep,
                },
                ttl=2.0,
            )

            pivots = data.get("pivots") or []
            if isinstance(pivots, list) and pivots:
                result: list[tuple[int, float]] = []
                for p in pivots:
                    if not isinstance(p, dict):
                        continue
                    shift = self._to_int(p.get("shift"))
                    price = self._to_float(p.get("price"))
                    if shift >= 0 and price > 0:
                        result.append((shift, price))
                return result

        except Exception as exc:
            logger.warning("Bridge ZigZag unavailable; using fallback. error=%s", exc)

        return await self._fallback_zigzag_pivots(symbol, timeframe, depth)

    async def _fallback_zigzag_pivots(
            self,
            symbol: str,
            timeframe: str,
            depth: int,
    ) -> list[tuple[int, float]]:
        candles = await self.bars(symbol, timeframe)
        if len(candles) < depth * 2 + 5:
            return []

        pivots: list[tuple[int, float]] = []

        # Convert newest-shift logic:
        # shift 0 is newest, Python candles are oldest -> newest.
        max_shift = min(180, len(candles) - depth - 1)

        for shift in range(depth, max_shift):
            idx = len(candles) - 1 - shift
            current = candles[idx]

            left = candles[max(0, idx - depth):idx]
            right = candles[idx + 1:min(len(candles), idx + depth + 1)]

            if not left or not right:
                continue

            is_high = current.high >= max(c.high for c in left + right)
            is_low = current.low <= min(c.low for c in left + right)

            if is_high:
                pivots.append((shift, current.high))
            elif is_low:
                pivots.append((shift, current.low))

        return pivots

    async def fractals(
            self,
            symbol: str,
            timeframe: str,
    ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        """
        Preferred bridge reply:
          {
            "status": "ok",
            "upper": [{"shift": 10, "price": 1.0950}],
            "lower": [{"shift": 21, "price": 1.0800}]
          }

        Fallback:
          Bill Williams-style 5-bar fractals.
        """
        try:
            data = await self.cached_request(
                f"fractals:{symbol}:{timeframe}",
                {
                    "action": "fractals",
                    "symbol": symbol,
                    "timeframe": timeframe,
                },
                ttl=2.0,
            )

            upper = self._parse_shift_price_list(data.get("upper") or data.get("upper_fractals") or [])
            lower = self._parse_shift_price_list(data.get("lower") or data.get("lower_fractals") or [])

            if upper or lower:
                return upper, lower

        except Exception as exc:
            logger.warning("Bridge fractals unavailable; using fallback. error=%s", exc)

        return await self._fallback_fractals(symbol, timeframe)

    def _parse_shift_price_list(self, values: Any) -> list[tuple[int, float]]:
        result: list[tuple[int, float]] = []

        if not isinstance(values, list):
            return result

        for item in values:
            if not isinstance(item, dict):
                continue

            shift = self._to_int(item.get("shift"))
            price = self._to_float(item.get("price"))

            if shift >= 0 and price > 0:
                result.append((shift, price))

        return result

    async def _fallback_fractals(
            self,
            symbol: str,
            timeframe: str,
    ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        candles = await self.bars(symbol, timeframe)

        upper: list[tuple[int, float]] = []
        lower: list[tuple[int, float]] = []

        if len(candles) < 7:
            return upper, lower

        # Need two candles before and after.
        for idx in range(2, len(candles) - 2):
            c = candles[idx]

            left_1 = candles[idx - 1]
            left_2 = candles[idx - 2]
            right_1 = candles[idx + 1]
            right_2 = candles[idx + 2]

            is_upper = (
                    c.high > left_1.high
                    and c.high > left_2.high
                    and c.high > right_1.high
                    and c.high > right_2.high
            )

            is_lower = (
                    c.low < left_1.low
                    and c.low < left_2.low
                    and c.low < right_1.low
                    and c.low < right_2.low
            )

            shift = len(candles) - 1 - idx

            if is_upper:
                upper.append((shift, c.high))

            if is_lower:
                lower.append((shift, c.low))

        return upper, lower

    # ============================================================
    # ORDER EXECUTION
    # ============================================================

    async def send_order(
            self,
            symbol: str,
            order_type: str,
            lots: float,
            price: float,
            sl: float,
            tp: float,
            comment: str,
            magic_number: int,
            slippage: int,
    ) -> str:
        data = await self.request(
            {
                "action": "send_order",
                "symbol": symbol,
                "type": order_type,
                "lots": lots,
                "lot": lots,
                "price": price,
                "sl": sl,
                "tp": tp,
                "comment": comment,
                "magic_number": magic_number,
                "slippage": slippage,
            }
        )

        ticket = data.get("ticket") or data.get("order_id") or data.get("id")

        if not ticket:
            raise MT4WebSocketAdapterError(f"Order response missing ticket: {data}")

        return str(ticket)

    async def close_ticket(self, ticket: str, slippage: int) -> bool:
        data = await self.request(
            {
                "action": "close_ticket",
                "ticket": ticket,
                "slippage": slippage,
            }
        )
        return data.get("status") in {"ok", "success"}

    async def delete_ticket(self, ticket: str) -> bool:
        data = await self.request(
            {
                "action": "delete_ticket",
                "ticket": ticket,
            }
        )
        return data.get("status") in {"ok", "success"}

    async def modify_ticket(
            self,
            ticket: str,
            price: float,
            sl: float,
            tp: float,
    ) -> bool:
        data = await self.request(
            {
                "action": "modify_ticket",
                "ticket": ticket,
                "price": price,
                "sl": sl,
                "tp": tp,
            }
        )
        return data.get("status") in {"ok", "success"}


# ============================================================
# QUICK TEST
# ============================================================

async def _smoke_test() -> None:
    logging.basicConfig(level=logging.INFO)

    adapter = MT4WebSocketAdapter(
        url="ws://127.0.0.1:8090/ws",
        default_symbol="EURUSD",
    )

    print("account:", await adapter.account_id())
    print("symbol:", await adapter.symbol())
    print("symbols:", await adapter.market_watch_symbols())

    symbol = await adapter.symbol()

    print("bid:", await adapter.bid(symbol))
    print("ask:", await adapter.ask(symbol))
    print("spread:", await adapter.spread_points(symbol))
    print("digits:", await adapter.digits(symbol))
    print("point:", await adapter.point(symbol))

    bars = await adapter.bars(symbol, "M5")
    print("bars:", len(bars), bars[-1] if bars else None)

    upper, lower = await adapter.fractals(symbol, "H1")
    print("fractals:", len(upper), len(lower))

    pivots = await adapter.zigzag_pivots(symbol, "H1", 12, 5, 3)
    print("zigzag:", len(pivots))


if __name__ == "__main__":
    asyncio.run(_smoke_test())