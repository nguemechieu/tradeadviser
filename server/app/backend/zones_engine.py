from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Protocol

import websockets


logger = logging.getLogger("zones.engine")


# ============================================================
# CONFIG
# ============================================================

@dataclass(slots=True)
class ZonesConfig:
    bridge_websocket_url: str = "ws://127.0.0.1:8090/ws"

    post_all_market_watch_symbols: bool = False
    draw_zones_on_chart: bool = True

    timer_seconds: int = 60
    max_slippage: int = 5
    magic_number: int = 20260316

    bars_h1: int = 60
    bars_m5: int = 80
    bars_m1: int = 120

    max_market_watch_symbols: int = 0
    swing_lookback: int = 3
    scan_bars: int = 180
    zone_projection_bars: int = 80
    support_resistance_lookback: int = 80

    max_supply_zones: int = 3
    max_demand_zones: int = 3
    max_liquidity_zones: int = 2

    zone_padding_points: float = 60.0
    liquidity_tolerance_points: float = 45.0

    zigzag_depth: int = 12
    zigzag_deviation: int = 5
    zigzag_backstep: int = 3

    temp_zone_min_thickness_points: float = 45.0
    temp_zone_max_thickness_points: float = 180.0
    main_zone_min_thickness_points: float = 60.0
    main_zone_max_thickness_points: float = 260.0

    zone_merge_tolerance_points: float = 35.0
    minimum_m5_touches: int = 3

    enable_bridge_posting: bool = True
    bridge_retry_count: int = 2
    bridge_retry_delay_ms: int = 150

    execution_style: str = "advanced"
    advanced_confirmation_timeframe: str = "M5"
    advanced_retest_limit: int = 2
    retest_entry_mode: str = "close"

    enable_auto_execution: bool = False
    auto_execution_lots: float = 0.10
    require_ai_agreement_for_auto_execution: bool = False

    max_spread_points: float = 35.0
    max_risk_per_trade_pct: float = 1.00
    max_total_exposure_pct: float = 30.0
    max_open_trades_per_symbol: int = 2
    max_commands_per_poll: int = 10
    trade_cooldown_seconds: int = 10

    reject_if_stops_too_close: bool = True
    reject_if_trading_disabled: bool = True
    reject_duplicate_command_ids: bool = True
    include_only_magic_positions_in_payload: bool = False


# ============================================================
# RECORDS
# ============================================================

@dataclass(slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(slots=True)
class ZoneRecord:
    id: str = ""
    timeframe: str = ""
    anchor_timeframe: str = ""
    kind: str = ""
    family: str = ""
    status: str = ""
    strength_label: str = ""
    mode_bias: str = ""
    price_relation: str = ""
    structure_label: str = ""

    strength: int = 0
    zigzag_count: int = 0
    fractal_count: int = 0
    touch_count: int = 0
    retest_count: int = 0
    origin_shift: int = 0

    origin_time: datetime | None = None
    origin_price: float = 0.0
    body_start: float = 0.0
    lower: float = 0.0
    upper: float = 0.0


@dataclass(slots=True)
class SwingRecord:
    shift: int
    swing_time: datetime
    price: float
    is_high: bool
    from_zigzag: bool = False
    from_fractal: bool = False
    label: str = ""


@dataclass(slots=True)
class StructureEventRecord:
    event_name: str
    direction: str
    structure_label: str
    origin_shift: int
    event_time: datetime
    level: float


@dataclass(slots=True)
class ExecutionPlanRecord:
    allowed: bool = False
    prediction: str = "HOLD"
    style: str = "advanced"
    confirmation_timeframe: str = "M5"
    rrr_state: str = "none"
    bos_direction: str = "none"
    reason: str = "No eligible zone setup."
    active_zone_id: str = ""
    active_zone_kind: str = ""
    zone_state: str = ""
    retest_count: int = 0
    score: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass(slots=True)
class AiBridgeRecord:
    available: bool = False
    prediction: str = ""
    confidence: float = 0.0
    reason: str = ""
    zone_state: str = ""
    execution_hint: str = ""
    risk_hint: str = ""
    model_status: str = ""
    received_at: datetime | None = None
    raw: str = ""


# ============================================================
# BROKER / MARKET ADAPTER
# ============================================================

class MarketAdapter(Protocol):
    """
    Replace MT4 functions like MarketInfo(), iHigh(), iLow(), iClose(),
    OrderSend(), OrderClose(), etc.

    Your MT4 bridge, OANDA broker, Alpaca broker, CCXT broker, or simulated
    PaperBroker can implement this interface.
    """

    async def account_id(self) -> str: ...

    async def symbol(self) -> str: ...

    async def market_watch_symbols(self) -> list[str]: ...

    async def point(self, symbol: str) -> float: ...

    async def digits(self, symbol: str) -> int: ...

    async def bid(self, symbol: str) -> float: ...

    async def ask(self, symbol: str) -> float: ...

    async def spread_points(self, symbol: str) -> float: ...

    async def bars(self, symbol: str, timeframe: str) -> list[Candle]: ...

    async def zigzag_pivots(
            self,
            symbol: str,
            timeframe: str,
            depth: int,
            deviation: int,
            backstep: int,
    ) -> list[tuple[int, float]]: ...

    async def fractals(
            self,
            symbol: str,
            timeframe: str,
    ) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
        """
        Return:
            upper_fractals: [(shift, price), ...]
            lower_fractals: [(shift, price), ...]
        """
        ...

    async def trading_allowed(self, symbol: str) -> bool: ...

    async def free_margin(self) -> float: ...

    async def equity(self) -> float: ...

    async def margin(self) -> float: ...

    async def min_lot(self, symbol: str) -> float: ...

    async def max_lot(self, symbol: str) -> float: ...

    async def lot_step(self, symbol: str) -> float: ...

    async def stop_level_points(self, symbol: str) -> float: ...

    async def tick_value(self, symbol: str) -> float: ...

    async def tick_size(self, symbol: str) -> float: ...

    async def count_open_trades(self, symbol: str, magic_number: int) -> int: ...

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
    ) -> str: ...

    async def close_ticket(self, ticket: str, slippage: int) -> bool: ...

    async def delete_ticket(self, ticket: str) -> bool: ...

    async def modify_ticket(
            self,
            ticket: str,
            price: float,
            sl: float,
            tp: float,
    ) -> bool: ...


# ============================================================
# ENGINE
# ============================================================

class ZonesEngine:
    def __init__(self, adapter: MarketAdapter, config: ZonesConfig | None = None) -> None:
        self.adapter = adapter
        self.config = config or ZonesConfig()

        self.last_trade_time: float = 0.0
        self.last_command_ids: list[str] = []
        self.last_bridge_success: datetime | None = None
        self.last_bridge_error: str = ""
        self.bridge_failure_count: int = 0

        self.chart_zones: list[ZoneRecord] = []
        self.chart_swings: list[SwingRecord] = []
        self.chart_events: list[StructureEventRecord] = []

        self.execution_plan = ExecutionPlanRecord()
        self.ai_bridge = AiBridgeRecord()

        self.structure_bias = "neutral"
        self.structure_labels_csv = ""

    # ========================================================
    # BASIC HELPERS
    # ========================================================

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def timeframe_seconds(timeframe: str) -> int:
        mapping = {
            "M1": 60,
            "1M": 60,
            "M5": 300,
            "5M": 300,
            "M15": 900,
            "15M": 900,
            "M30": 1800,
            "30M": 1800,
            "H1": 3600,
            "1H": 3600,
            "H4": 14400,
            "4H": 14400,
            "D1": 86400,
            "1D": 86400,
        }
        return mapping.get(timeframe.upper(), 300)

    @staticmethod
    def normalize_timeframe(value: str) -> str:
        value = value.strip().upper()
        mapping = {
            "1M": "M1",
            "5M": "M5",
            "15M": "M15",
            "30M": "M30",
            "1H": "H1",
            "4H": "H4",
            "1D": "D1",
        }
        return mapping.get(value, value)

    @staticmethod
    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    @staticmethod
    def bool_text(value: bool) -> str:
        return "true" if value else "false"

    async def normalize_price(self, symbol: str, price: float) -> float:
        digits = await self.adapter.digits(symbol)
        return round(price, digits)

    async def normalize_lots(self, symbol: str, lots: float) -> float:
        min_lot = await self.adapter.min_lot(symbol)
        max_lot = await self.adapter.max_lot(symbol)
        lot_step = await self.adapter.lot_step(symbol)

        if lot_step <= 0:
            lot_step = 0.01

        lots = max(min_lot, min(max_lot, lots))
        lots = math.floor(lots / lot_step) * lot_step

        if lots < min_lot:
            lots = min_lot

        return round(lots, 2)

    async def price_distance_points(self, symbol: str, first: float, second: float) -> float:
        point = await self.adapter.point(symbol)
        if point <= 0:
            return 0.0
        return abs(first - second) / point

    async def zone_min_thickness_price(self, symbol: str, family: str) -> float:
        point = await self.adapter.point(symbol)
        if family == "main":
            return self.config.main_zone_min_thickness_points * point
        return self.config.temp_zone_min_thickness_points * point

    async def zone_max_thickness_price(self, symbol: str, family: str) -> float:
        point = await self.adapter.point(symbol)
        if family == "main":
            return self.config.main_zone_max_thickness_points * point
        return self.config.temp_zone_max_thickness_points * point

    # ========================================================
    # WEBSOCKET BRIDGE
    # ========================================================

    async def ws_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.config.enable_bridge_posting:
            return None

        raw = json.dumps(payload)

        for attempt in range(self.config.bridge_retry_count + 1):
            try:
                async with websockets.connect(self.config.bridge_websocket_url) as ws:
                    await ws.send(raw)
                    reply = await ws.recv()

                self.last_bridge_success = self.utc_now()
                self.last_bridge_error = ""
                return json.loads(reply)

            except Exception as exc:
                self.last_bridge_error = f"bridge:{type(exc).__name__}:{exc}"
                logger.warning(
                    "ZONES bridge request failed attempt=%s error=%s",
                    attempt + 1,
                    exc,
                    )

                if attempt < self.config.bridge_retry_count:
                    await asyncio.sleep(self.config.bridge_retry_delay_ms / 1000)

        self.bridge_failure_count += 1
        return None

    async def send_command_ack(self, command_id: str, status: str, message: str) -> bool:
        account_id = await self.adapter.account_id()
        reply = await self.ws_request(
            {
                "action": "command_ack",
                "account_id": account_id,
                "id": command_id,
                "status": status,
                "message": message,
            }
        )
        return bool(reply and reply.get("status") == "ok")

    # ========================================================
    # COMMAND PARSING
    # ========================================================

    @staticmethod
    def parse_command(command_text: str) -> dict[str, str]:
        """
        Converts:
            id=123|type=market_buy|symbol=EURUSD|lot=0.10|sl=1.0800|tp=1.0900

        Into:
            {"id": "123", "type": "market_buy", …}
        """
        result: dict[str, str] = {}
        for part in command_text.split("|"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        return result

    def seen_command_id(self, command_id: str) -> bool:
        return bool(command_id and command_id in self.last_command_ids)

    def remember_command_id(self, command_id: str) -> None:
        if not command_id:
            return

        self.last_command_ids.append(command_id)

        if len(self.last_command_ids) > 128:
            self.last_command_ids.pop(0)

    # ========================================================
    # EXECUTION SAFETY
    # ========================================================

    def in_trade_cooldown(self) -> bool:
        if self.last_trade_time <= 0:
            return False
        return (time.time() - self.last_trade_time) < self.config.trade_cooldown_seconds

    async def current_exposure_pct(self) -> float:
        equity = await self.adapter.equity()
        if equity <= 0:
            return 0.0
        margin = await self.adapter.margin()
        return (margin / equity) * 100.0

    async def symbol_has_fresh_quotes(self, symbol: str) -> bool:
        bid = await self.adapter.bid(symbol)
        ask = await self.adapter.ask(symbol)
        return 0 < bid <= ask and ask > 0

    async def stops_valid(
            self,
            symbol: str,
            order_type: str,
            price: float,
            sl: float,
            tp: float,
    ) -> tuple[bool, str]:
        if not self.config.reject_if_stops_too_close:
            return True, ""

        point = await self.adapter.point(symbol)
        stop_level = await self.adapter.stop_level_points(symbol)
        min_distance = stop_level * point

        is_buy = order_type in {"market_buy", "buy_limit", "buy_stop"}

        if sl > 0:
            if is_buy and (price - sl) < min_distance:
                return False, "SL too close"
            if not is_buy and (sl - price) < min_distance:
                return False, "SL too close"

        if tp > 0:
            if is_buy and (tp - price) < min_distance:
                return False, "TP too close"
            if not is_buy and (price - tp) < min_distance:
                return False, "TP too close"

        return True, ""

    async def pending_price_valid(
            self,
            symbol: str,
            order_type: str,
            price: float,
    ) -> tuple[bool, str]:
        bid = await self.adapter.bid(symbol)
        ask = await self.adapter.ask(symbol)

        if order_type == "buy_limit" and price >= ask:
            return False, "Buy limit must be below ask"

        if order_type == "sell_limit" and price <= bid:
            return False, "Sell limit must be above bid"

        if order_type == "buy_stop" and price <= ask:
            return False, "Buy stop must be above ask"

        if order_type == "sell_stop" and price >= bid:
            return False, "Sell stop must be below bid"

        return True, ""

    async def risk_within_limit(
            self,
            symbol: str,
            lots: float,
            price: float,
            sl: float,
    ) -> bool:
        equity = await self.adapter.equity()

        if sl <= 0 or equity <= 0:
            return True

        tick_value = await self.adapter.tick_value(symbol)
        tick_size = await self.adapter.tick_size(symbol)
        point = await self.adapter.point(symbol)

        if tick_value <= 0 or tick_size <= 0 or point <= 0:
            return True

        distance = abs(price - sl)
        points_distance = distance / point
        value_per_point_per_lot = tick_value * (point / tick_size)
        risk_money = points_distance * value_per_point_per_lot * lots
        risk_pct = (risk_money / equity) * 100.0

        return risk_pct <= self.config.max_risk_per_trade_pct

    async def pre_trade_check(
            self,
            command_id: str,
            symbol: str,
            order_type: str,
            lots: float,
            price: float,
            sl: float,
            tp: float,
    ) -> tuple[bool, str, float, float, float, float]:
        if self.config.reject_duplicate_command_ids and self.seen_command_id(command_id):
            return False, "Duplicate command id", lots, price, sl, tp

        if not symbol:
            return False, "Empty symbol", lots, price, sl, tp

        if self.config.reject_if_trading_disabled:
            if not await self.adapter.trading_allowed(symbol):
                return False, "Trading not allowed", lots, price, sl, tp

        if not await self.symbol_has_fresh_quotes(symbol):
            return False, "No fresh quotes", lots, price, sl, tp

        spread = await self.adapter.spread_points(symbol)
        if spread > self.config.max_spread_points:
            return False, "Spread too high", lots, price, sl, tp

        is_market = order_type in {"market_buy", "market_sell"}
        is_pending = order_type in {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}

        if self.in_trade_cooldown() and is_market:
            return False, "Trade cooldown active", lots, price, sl, tp

        open_trades = await self.adapter.count_open_trades(symbol, self.config.magic_number)
        if open_trades >= self.config.max_open_trades_per_symbol and is_market:
            return False, "Max open trades per symbol reached", lots, price, sl, tp

        if await self.current_exposure_pct() >= self.config.max_total_exposure_pct:
            return False, "Total exposure limit reached", lots, price, sl, tp

        lots = await self.normalize_lots(symbol, lots)
        if lots <= 0:
            return False, "Invalid lot size", lots, price, sl, tp

        price = await self.normalize_price(symbol, price)
        if sl > 0:
            sl = await self.normalize_price(symbol, sl)
        if tp > 0:
            tp = await self.normalize_price(symbol, tp)

        if is_pending:
            if price <= 0:
                return False, "Pending order price is required", lots, price, sl, tp

            ok, reason = await self.pending_price_valid(symbol, order_type, price)
            if not ok:
                return False, reason, lots, price, sl, tp

        ok, reason = await self.stops_valid(symbol, order_type, price, sl, tp)
        if not ok:
            return False, reason, lots, price, sl, tp

        if not await self.risk_within_limit(symbol, lots, price, sl):
            return False, "Risk per trade exceeds configured limit", lots, price, sl, tp

        return True, "", lots, price, sl, tp

    # ========================================================
    # COMMAND EXECUTION
    # ========================================================

    async def execute_command(self, command_text: str) -> bool:
        cmd = self.parse_command(command_text)

        command_id = cmd.get("id", "")
        command_type = cmd.get("type", "")
        symbol = cmd.get("symbol", "") or await self.adapter.symbol()

        if not command_type:
            await self.send_command_ack(command_id, "error", "Missing command type")
            return False

        if command_type == "alert":
            message = cmd.get("message", "")
            logger.warning("ZONES alert: %s", message)
            await self.send_command_ack(command_id, "ok", "Alert executed")
            self.remember_command_id(command_id)
            return True

        if command_type in {"market_buy", "market_sell"}:
            lots = float(cmd.get("lot", "0") or 0)
            sl = float(cmd.get("sl", "0") or 0)
            tp = float(cmd.get("tp", "0") or 0)
            comment = cmd.get("comment", "")

            price = await self.adapter.ask(symbol) if command_type == "market_buy" else await self.adapter.bid(symbol)

            ok, reason, lots, price, sl, tp = await self.pre_trade_check(
                command_id,
                symbol,
                command_type,
                lots,
                price,
                sl,
                tp,
            )

            if not ok:
                await self.send_command_ack(command_id, "rejected", reason)
                return False

            ticket = await self.adapter.send_order(
                symbol=symbol,
                order_type=command_type,
                lots=lots,
                price=price,
                sl=sl,
                tp=tp,
                comment=comment,
                magic_number=self.config.magic_number,
                slippage=self.config.max_slippage,
            )

            self.last_trade_time = time.time()
            self.remember_command_id(command_id)

            await self.send_command_ack(command_id, "ok", f"ticket={ticket}|symbol={symbol}")
            return True

        if command_type in {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}:
            lots = float(cmd.get("lot", "0") or 0)
            price = float(cmd.get("price", "0") or 0)
            sl = float(cmd.get("sl", "0") or 0)
            tp = float(cmd.get("tp", "0") or 0)
            comment = cmd.get("comment", "")

            ok, reason, lots, price, sl, tp = await self.pre_trade_check(
                command_id,
                symbol,
                command_type,
                lots,
                price,
                sl,
                tp,
            )

            if not ok:
                await self.send_command_ack(command_id, "rejected", reason)
                return False

            ticket = await self.adapter.send_order(
                symbol=symbol,
                order_type=command_type,
                lots=lots,
                price=price,
                sl=sl,
                tp=tp,
                comment=comment,
                magic_number=self.config.magic_number,
                slippage=self.config.max_slippage,
            )

            self.remember_command_id(command_id)
            await self.send_command_ack(command_id, "ok", f"ticket={ticket}|symbol={symbol}")
            return True

        if command_type == "close_ticket":
            ticket = cmd.get("ticket", "")
            ok = await self.adapter.close_ticket(ticket, self.config.max_slippage)

            if not ok:
                await self.send_command_ack(command_id, "error", f"Close failed ticket={ticket}")
                return False

            self.remember_command_id(command_id)
            await self.send_command_ack(command_id, "ok", f"Closed ticket={ticket}")
            return True

        if command_type == "delete_ticket":
            ticket = cmd.get("ticket", "")
            ok = await self.adapter.delete_ticket(ticket)

            if not ok:
                await self.send_command_ack(command_id, "error", f"Delete failed ticket={ticket}")
                return False

            self.remember_command_id(command_id)
            await self.send_command_ack(command_id, "ok", f"Deleted pending ticket={ticket}")
            return True

        if command_type == "modify_ticket":
            ticket = cmd.get("ticket", "")
            price = float(cmd.get("price", "0") or 0)
            sl = float(cmd.get("sl", "0") or 0)
            tp = float(cmd.get("tp", "0") or 0)

            ok = await self.adapter.modify_ticket(ticket, price, sl, tp)

            if not ok:
                await self.send_command_ack(command_id, "error", f"Modify failed ticket={ticket}")
                return False

            self.remember_command_id(command_id)
            await self.send_command_ack(command_id, "ok", f"Modified ticket={ticket}")
            return True

        await self.send_command_ack(command_id, "error", f"Unsupported command type: {command_type}")
        return False

    async def poll_command_queue_for_symbol(self, symbol: str) -> None:
        account_id = await self.adapter.account_id()

        processed = 0
        while processed < self.config.max_commands_per_poll:
            reply = await self.ws_request(
                {
                    "action": "fetch_command",
                    "account_id": account_id,
                    "symbol": symbol,
                }
            )

            if not reply or reply.get("status") != "ok":
                return

            command = reply.get("command") or ""
            if not command:
                return

            await self.execute_command(command)
            processed += 1

    async def poll_commands(self) -> None:
        if not self.config.post_all_market_watch_symbols:
            await self.poll_command_queue_for_symbol(await self.adapter.symbol())
            return

        symbols = await self.adapter.market_watch_symbols()

        if self.config.max_market_watch_symbols > 0:
            symbols = symbols[: self.config.max_market_watch_symbols]

        for symbol in symbols:
            await self.poll_command_queue_for_symbol(symbol)

    # ========================================================
    # CANDLE HELPERS
    # ========================================================

    async def get_bars(self, symbol: str, timeframe: str) -> list[Candle]:
        return await self.adapter.bars(symbol, timeframe)

    @staticmethod
    def candle_at(bars: list[Candle], shift: int) -> Candle | None:
        """
        MQL4 shift 0 = newest candle.
        Python list here assumes oldest -> newest.
        """
        if shift < 0 or shift >= len(bars):
            return None
        return bars[-1 - shift]

    @staticmethod
    def highest_shift(bars: list[Candle], count: int, start_shift: int = 2) -> int:
        best_shift = start_shift
        best_high = -float("inf")

        for shift in range(start_shift, start_shift + count):
            candle = ZonesEngine.candle_at(bars, shift)
            if candle and candle.high > best_high:
                best_high = candle.high
                best_shift = shift

        return best_shift

    @staticmethod
    def lowest_shift(bars: list[Candle], count: int, start_shift: int = 2) -> int:
        best_shift = start_shift
        best_low = float("inf")

        for shift in range(start_shift, start_shift + count):
            candle = ZonesEngine.candle_at(bars, shift)
            if candle and candle.low < best_low:
                best_low = candle.low
                best_shift = shift

        return best_shift

    # ========================================================
    # ZONE ANALYSIS
    # ========================================================

    async def is_high_swing(self, symbol: str, timeframe: str, shift: int, pivot_price: float) -> bool:
        bars = await self.get_bars(symbol, timeframe)
        candle = self.candle_at(bars, shift)
        if candle is None:
            return False

        return abs(pivot_price - candle.high) <= abs(pivot_price - candle.low)

    async def add_or_merge_zone_candidate(
            self,
            symbol: str,
            zones: list[ZoneRecord],
            kind: str,
            origin_shift: int,
            origin_time: datetime,
            origin_price: float,
            body_start: float,
            from_zigzag: bool,
            from_fractal: bool,
    ) -> None:
        for zone in zones:
            if zone.kind != kind:
                continue

            distance = await self.price_distance_points(symbol, zone.body_start, body_start)
            if distance > self.config.zone_merge_tolerance_points:
                continue

            if from_zigzag:
                zone.zigzag_count += 1
            if from_fractal:
                zone.fractal_count += 1

            total_hits = max(1, zone.zigzag_count + zone.fractal_count)
            zone.body_start = ((zone.body_start * (total_hits - 1)) + body_start) / total_hits
            zone.origin_price = ((zone.origin_price * (total_hits - 1)) + origin_price) / total_hits

            if origin_shift > zone.origin_shift:
                zone.origin_shift = origin_shift
                zone.origin_time = origin_time

            return

        zones.append(
            ZoneRecord(
                id=f"{kind}_{int(origin_time.timestamp())}",
                timeframe="5M",
                anchor_timeframe="1H",
                kind=kind,
                family="temp",
                status="fresh",
                strength_label="",
                mode_bias="neutral",
                price_relation="unknown",
                structure_label="",
                strength=0,
                zigzag_count=1 if from_zigzag else 0,
                fractal_count=1 if from_fractal else 0,
                touch_count=0,
                retest_count=0,
                origin_shift=origin_shift,
                origin_time=origin_time,
                origin_price=origin_price,
                body_start=body_start,
                lower=body_start,
                upper=body_start,
            )
        )

    async def collect_zone_candidates(self, symbol: str) -> list[ZoneRecord]:
        zones: list[ZoneRecord] = []

        h1_bars = await self.get_bars(symbol, "H1")

        pivots = await self.adapter.zigzag_pivots(
            symbol,
            "H1",
            self.config.zigzag_depth,
            self.config.zigzag_deviation,
            self.config.zigzag_backstep,
        )

        for shift, pivot in pivots:
            if shift < 2 or shift > min(self.config.scan_bars, len(h1_bars) - 1):
                continue

            candle = self.candle_at(h1_bars, shift)
            if candle is None:
                continue

            is_high = await self.is_high_swing(symbol, "H1", shift, pivot)
            body_start = min(candle.open, candle.close) if is_high else max(candle.open, candle.close)

            await self.add_or_merge_zone_candidate(
                symbol=symbol,
                zones=zones,
                kind="supply" if is_high else "demand",
                origin_shift=shift,
                origin_time=candle.timestamp,
                origin_price=pivot,
                body_start=body_start,
                from_zigzag=True,
                from_fractal=False,
            )

        upper_fractals, lower_fractals = await self.adapter.fractals(symbol, "H1")

        for shift, price in upper_fractals:
            candle = self.candle_at(h1_bars, shift)
            if candle is None:
                continue

            await self.add_or_merge_zone_candidate(
                symbol,
                zones,
                "supply",
                shift,
                candle.timestamp,
                price,
                min(candle.open, candle.close),
                False,
                True,
            )

        for shift, price in lower_fractals:
            candle = self.candle_at(h1_bars, shift)
            if candle is None:
                continue

            await self.add_or_merge_zone_candidate(
                symbol,
                zones,
                "demand",
                shift,
                candle.timestamp,
                price,
                max(candle.open, candle.close),
                False,
                True,
            )

        return zones

    async def candle_touches_zone(
            self,
            symbol: str,
            timeframe: str,
            shift: int,
            zone: ZoneRecord,
    ) -> bool:
        bars = await self.get_bars(symbol, timeframe)
        candle = self.candle_at(bars, shift)
        if candle is None:
            return False

        return candle.low <= zone.upper and candle.high >= zone.lower

    async def candle_shows_respect(
            self,
            symbol: str,
            timeframe: str,
            shift: int,
            zone: ZoneRecord,
    ) -> bool:
        if not await self.candle_touches_zone(symbol, timeframe, shift, zone):
            return False

        bars = await self.get_bars(symbol, timeframe)
        candle = self.candle_at(bars, shift)

        if candle is None:
            return False

        if zone.kind == "demand":
            return candle.close >= zone.upper and candle.close >= candle.open

        return candle.close <= zone.lower and candle.close <= candle.open

    async def candle_shows_reject(
            self,
            symbol: str,
            timeframe: str,
            shift: int,
            zone: ZoneRecord,
    ) -> bool:
        if not await self.candle_touches_zone(symbol, timeframe, shift, zone):
            return False

        bars = await self.get_bars(symbol, timeframe)
        candle = self.candle_at(bars, shift)

        if candle is None:
            return False

        point = await self.adapter.point(symbol)
        probe = self.config.zone_padding_points * point * 0.12

        if zone.kind == "demand":
            return candle.low <= zone.lower + probe and candle.close > candle.open and candle.close >= zone.upper

        return candle.high >= zone.upper - probe and candle.close < candle.open and candle.close <= zone.lower

    async def count_recent_retests(
            self,
            symbol: str,
            timeframe: str,
            zone: ZoneRecord,
            max_bars: int,
    ) -> int:
        bars = await self.get_bars(symbol, timeframe)

        sequences = 0
        previous_touch = False

        for shift in range(min(max_bars, len(bars) - 1), 0, -1):
            current_touch = await self.candle_touches_zone(symbol, timeframe, shift, zone)
            if current_touch and not previous_touch:
                sequences += 1
            previous_touch = current_touch

        return sequences

    async def refine_zone_on_m5(self, symbol: str, zone: ZoneRecord) -> None:
        m5_bars = await self.get_bars(symbol, "M5")

        min_thickness = await self.zone_min_thickness_price(symbol, zone.family)
        max_thickness = await self.zone_max_thickness_price(symbol, zone.family)

        start_shift = min(self.config.bars_m5, len(m5_bars) - 1)

        extreme = zone.body_start
        zone.touch_count = 0

        for shift in range(start_shift, 0, -1):
            candle = self.candle_at(m5_bars, shift)
            if candle is None:
                continue

            body_edge = max(candle.open, candle.close) if zone.kind == "demand" else min(candle.open, candle.close)

            distance = await self.price_distance_points(symbol, body_edge, zone.body_start)
            if distance > self.config.zone_merge_tolerance_points:
                continue

            zone.touch_count += 1

            if zone.kind == "demand":
                extreme = min(extreme, candle.low)
            else:
                extreme = max(extreme, candle.high)

        thickness = zone.body_start - extreme if zone.kind == "demand" else extreme - zone.body_start

        if zone.touch_count < self.config.minimum_m5_touches:
            thickness = min_thickness

        thickness = self.clamp(max(thickness, min_thickness), min_thickness, max_thickness)

        if zone.kind == "demand":
            zone.upper = zone.body_start
            zone.lower = zone.body_start - thickness
        else:
            zone.lower = zone.body_start
            zone.upper = zone.body_start + thickness

        zone.lower = await self.normalize_price(symbol, zone.lower)
        zone.upper = await self.normalize_price(symbol, zone.upper)
        zone.retest_count = await self.count_recent_retests(symbol, "M5", zone, 40)

    async def finalize_zones(
            self,
            symbol: str,
            zones: list[ZoneRecord],
            structure_bias: str,
    ) -> list[ZoneRecord]:
        bid = await self.adapter.bid(symbol)
        ask = await self.adapter.ask(symbol)

        m5_bars = await self.get_bars(symbol, "M5")
        last_m5 = self.candle_at(m5_bars, 1)

        point = await self.adapter.point(symbol)
        invalidation_padding = point * 4.0

        for zone in zones:
            if zone.zigzag_count <= 0:
                zone.status = "deleted"
                continue

            zone.family = "main" if zone.fractal_count >= 1 else "temp"

            if zone.family == "main":
                if zone.fractal_count >= 2 and zone.zigzag_count >= 2:
                    zone.strength = 3
                elif zone.fractal_count >= 1 and zone.zigzag_count >= 2:
                    zone.strength = 2
                else:
                    zone.strength = 1

                zone.strength_label = f"S{zone.strength}"
            else:
                zone.strength = 0
                zone.strength_label = "TEMP"

            await self.refine_zone_on_m5(symbol, zone)

            last_close = last_m5.close if last_m5 else 0.0

            if zone.kind == "demand":
                if bid > zone.upper:
                    zone.price_relation = "above"
                elif bid < zone.lower:
                    zone.price_relation = "below"
                else:
                    zone.price_relation = "inside"

                if last_close < zone.lower - invalidation_padding:
                    zone.status = "deleted" if zone.family == "temp" else "invalidated"
                elif await self.candle_shows_reject(symbol, "M5", 1, zone):
                    zone.status = "rejected"
                elif await self.candle_shows_respect(symbol, "M5", 1, zone):
                    zone.status = "respected"
                else:
                    zone.status = "active"

                zone.mode_bias = (
                    "buying"
                    if zone.price_relation == "above"
                       and zone.status not in {"deleted", "invalidated"}
                       and structure_bias != "bearish"
                    else "neutral"
                )

            else:
                if ask < zone.lower:
                    zone.price_relation = "below"
                elif ask > zone.upper:
                    zone.price_relation = "above"
                else:
                    zone.price_relation = "inside"

                if last_close > zone.upper + invalidation_padding:
                    zone.status = "deleted" if zone.family == "temp" else "invalidated"
                elif await self.candle_shows_reject(symbol, "M5", 1, zone):
                    zone.status = "rejected"
                elif await self.candle_shows_respect(symbol, "M5", 1, zone):
                    zone.status = "respected"
                else:
                    zone.status = "active"

                zone.mode_bias = (
                    "selling"
                    if zone.price_relation == "below"
                       and zone.status not in {"deleted", "invalidated"}
                       and structure_bias != "bullish"
                    else "neutral"
                )

            zone.structure_label = structure_bias

        current_price = (bid + ask) / 2.0

        zones.sort(
            key=lambda z: (
                z.strength,
                -abs(current_price - z.body_start),
            ),
            reverse=True,
        )

        filtered: list[ZoneRecord] = []
        demand_count = 0
        supply_count = 0

        for zone in zones:
            if zone.kind == "demand":
                if demand_count >= self.config.max_demand_zones:
                    continue
                demand_count += 1
            else:
                if supply_count >= self.config.max_supply_zones:
                    continue
                supply_count += 1

            filtered.append(zone)

        return filtered

    # ========================================================
    # STRUCTURE ANALYSIS
    # ========================================================

    async def collect_h1_structure(
            self,
            symbol: str,
    ) -> tuple[list[SwingRecord], list[StructureEventRecord], str, str]:
        swings: list[SwingRecord] = []
        events: list[StructureEventRecord] = []
        structure_bias = "neutral"
        labels: list[str] = []

        h1_bars = await self.get_bars(symbol, "H1")
        pivots = await self.adapter.zigzag_pivots(
            symbol,
            "H1",
            self.config.zigzag_depth,
            self.config.zigzag_deviation,
            self.config.zigzag_backstep,
        )

        for shift, pivot in pivots:
            if shift < 2 or shift > min(self.config.scan_bars, len(h1_bars) - 1):
                continue

            candle = self.candle_at(h1_bars, shift)
            if candle is None:
                continue

            is_high = await self.is_high_swing(symbol, "H1", shift, pivot)

            swings.append(
                SwingRecord(
                    shift=shift,
                    swing_time=candle.timestamp,
                    price=pivot,
                    is_high=is_high,
                    from_zigzag=True,
                    from_fractal=False,
                )
            )

        previous_high = 0.0
        previous_low = 0.0
        has_previous_high = False
        has_previous_low = False
        latest_high_label = ""
        latest_low_label = ""

        for swing in swings:
            if swing.is_high:
                if not has_previous_high:
                    swing.label = "HH"
                else:
                    distance = await self.price_distance_points(symbol, swing.price, previous_high)
                    if distance <= self.config.zone_merge_tolerance_points:
                        swing.label = "EQHH"
                    elif swing.price > previous_high:
                        swing.label = "HH"
                    else:
                        swing.label = "LH"

                previous_high = swing.price
                has_previous_high = True
                latest_high_label = swing.label

            else:
                if not has_previous_low:
                    swing.label = "LL"
                else:
                    distance = await self.price_distance_points(symbol, swing.price, previous_low)
                    if distance <= self.config.zone_merge_tolerance_points:
                        swing.label = "EQLL"
                    elif swing.price > previous_low:
                        swing.label = "HL"
                    else:
                        swing.label = "LL"

                previous_low = swing.price
                has_previous_low = True
                latest_low_label = swing.label

            if swing.label:
                labels.append(swing.label)

        if latest_high_label in {"HH", "EQHH"} and latest_low_label in {"HL", "EQLL"}:
            structure_bias = "bullish"
        elif latest_high_label == "LH" and latest_low_label == "LL":
            structure_bias = "bearish"

        last_closed_h1 = self.candle_at(h1_bars, 1)

        if last_closed_h1:
            last_high_level = next((s.price for s in reversed(swings) if s.is_high), 0.0)
            last_low_level = next((s.price for s in reversed(swings) if not s.is_high), 0.0)

            point = await self.adapter.point(symbol)
            bos_padding = point * 2.0

            if last_high_level > 0 and last_closed_h1.close > last_high_level + bos_padding:
                events.append(
                    StructureEventRecord(
                        event_name="BOS",
                        direction="bullish",
                        structure_label=latest_high_label,
                        origin_shift=1,
                        event_time=last_closed_h1.timestamp,
                        level=last_high_level,
                    )
                )
                labels.append("BOS")

                if structure_bias == "bearish":
                    events.append(
                        StructureEventRecord(
                            event_name="CHOC",
                            direction="bullish",
                            structure_label=latest_high_label,
                            origin_shift=1,
                            event_time=last_closed_h1.timestamp,
                            level=last_high_level,
                        )
                    )
                    labels.append("CHOC")

            if last_low_level > 0 and last_closed_h1.close < last_low_level - bos_padding:
                events.append(
                    StructureEventRecord(
                        event_name="BOS",
                        direction="bearish",
                        structure_label=latest_low_label,
                        origin_shift=1,
                        event_time=last_closed_h1.timestamp,
                        level=last_low_level,
                    )
                )
                labels.append("BOS")

                if structure_bias == "bullish":
                    events.append(
                        StructureEventRecord(
                            event_name="CHOC",
                            direction="bearish",
                            structure_label=latest_low_label,
                            origin_shift=1,
                            event_time=last_closed_h1.timestamp,
                            level=last_low_level,
                        )
                    )
                    labels.append("CHOC")

        return swings, events, structure_bias, ",".join(labels)

    # ========================================================
    # EXECUTION PLAN
    # ========================================================

    async def detect_lower_timeframe_bos(
            self,
            symbol: str,
            timeframe: str,
            bullish: bool,
    ) -> tuple[bool, float]:
        bars = await self.get_bars(symbol, timeframe)

        if len(bars) < 20:
            return False, 0.0

        last_closed = self.candle_at(bars, 1)

        if last_closed is None:
            return False, 0.0

        if bullish:
            shift = self.highest_shift(bars, 12, 2)
            candle = self.candle_at(bars, shift)
            level = candle.high if candle else 0.0
            return last_closed.close > level, level

        shift = self.lowest_shift(bars, 12, 2)
        candle = self.candle_at(bars, shift)
        level = candle.low if candle else 0.0
        return last_closed.close < level, level

    async def score_zone_for_execution(
            self,
            symbol: str,
            zone: ZoneRecord,
            respect: bool,
            reject: bool,
            bos_aligned: bool,
            near_zone: bool,
            bias_aligned: bool,
    ) -> float:
        score = float(zone.strength)

        if zone.family == "temp":
            score += 0.6

        if zone.touch_count >= self.config.minimum_m5_touches:
            score += 0.4

        if near_zone:
            score += 0.6

        if respect:
            score += 0.6

        if reject:
            score += 0.6

        if bos_aligned:
            score += 0.8

        if bias_aligned:
            score += 0.4

        if zone.retest_count > 0:
            score += min(zone.retest_count, 3) * 0.15

        if await self.adapter.spread_points(symbol) > self.config.max_spread_points:
            score -= 1.0

        return max(score, 0.0)

    async def evaluate_execution_plan(
            self,
            symbol: str,
            zones: list[ZoneRecord],
            structure_bias: str,
    ) -> ExecutionPlanRecord:
        plan = ExecutionPlanRecord(
            style=self.config.execution_style,
            confirmation_timeframe=self.config.advanced_confirmation_timeframe,
        )

        confirmation_tf = self.normalize_timeframe(self.config.advanced_confirmation_timeframe)

        bullish_bos, _ = await self.detect_lower_timeframe_bos(symbol, confirmation_tf, True)
        bearish_bos, _ = await self.detect_lower_timeframe_bos(symbol, confirmation_tf, False)

        point = await self.adapter.point(symbol)

        for zone in zones:
            if zone.status in {"deleted", "invalidated"}:
                continue

            bullish_setup = zone.kind == "demand"
            expected_bias = "buying" if bullish_setup else "selling"
            bias_aligned = zone.mode_bias == expected_bias

            live_price = await self.adapter.ask(symbol) if bullish_setup else await self.adapter.bid(symbol)
            near_padding = self.config.zone_padding_points * point * 0.35
            near_zone = zone.lower - near_padding <= live_price <= zone.upper + near_padding

            respect = await self.candle_shows_respect(symbol, confirmation_tf, 1, zone)
            reject = await self.candle_shows_reject(symbol, confirmation_tf, 1, zone)
            bos_aligned = bullish_bos if bullish_setup else bearish_bos
            retests = await self.count_recent_retests(symbol, confirmation_tf, zone, 40)

            rrr_state = "none"
            if retests > 0 and near_zone:
                rrr_state = "retest"
            if respect:
                rrr_state = "respect"
            if reject:
                rrr_state = "reject"

            if self.config.execution_style.lower() == "instant":
                allowed = near_zone and bias_aligned
            else:
                allowed = near_zone and bias_aligned and (rrr_state != "none" or bos_aligned)

                if 0 < self.config.advanced_retest_limit < retests:
                    allowed = False

                if self.config.retest_entry_mode.lower() == "close" and not respect and not reject:
                    allowed = False

            score = await self.score_zone_for_execution(
                symbol,
                zone,
                respect,
                reject,
                bos_aligned,
                near_zone,
                bias_aligned,
            )

            if score < plan.score:
                continue

            stop_padding = max(point * 8.0, self.config.zone_padding_points * point * 0.12)

            if bullish_setup:
                stop_loss = await self.normalize_price(symbol, zone.lower - stop_padding)
                take_profit = await self.normalize_price(symbol, live_price + ((live_price - stop_loss) * 2.0))
            else:
                stop_loss = await self.normalize_price(symbol, zone.upper + stop_padding)
                take_profit = await self.normalize_price(symbol, live_price - ((stop_loss - live_price) * 2.0))

            plan = ExecutionPlanRecord(
                allowed=allowed,
                prediction="BUY" if bullish_setup else "SELL",
                style=self.config.execution_style,
                confirmation_timeframe=confirmation_tf,
                rrr_state=rrr_state,
                bos_direction=("bullish" if bullish_setup else "bearish") if bos_aligned else "none",
                reason=(
                           "Execution conditions satisfied."
                           if allowed
                           else "Execution conditions are not fully aligned."
                       )
                       + f" Zone={zone.id} bias={zone.mode_bias} status={zone.status}",
                active_zone_id=zone.id,
                active_zone_kind=zone.kind,
                zone_state=zone.status,
                retest_count=retests,
                score=score,
                entry_price=await self.normalize_price(symbol, live_price),
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        if plan.score <= 0 and structure_bias != "neutral":
            plan.reason = f"Structure is {structure_bias} but no active zone is close enough for execution."

        return plan

    # ========================================================
    # SNAPSHOT PAYLOAD
    # ========================================================

    @staticmethod
    def candle_to_payload(candle: Candle) -> dict[str, Any]:
        return {
            "timestamp": candle.timestamp.isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }

    async def timeframe_series_payload(
            self,
            symbol: str,
            timeframe: str,
            bars_count: int,
    ) -> list[dict[str, Any]]:
        bars = await self.get_bars(symbol, timeframe)
        selected = bars[-bars_count:]
        return [self.candle_to_payload(c) for c in selected]

    async def build_snapshot_payload(
            self,
            symbol: str,
            zones: list[ZoneRecord],
            swings: list[SwingRecord],
            events: list[StructureEventRecord],
            structure_bias: str,
            labels_csv: str,
            plan: ExecutionPlanRecord,
    ) -> dict[str, Any]:
        account_id = await self.adapter.account_id()

        return {
            "action": "snapshot",
            "account_id": account_id,
            "symbol": symbol,
            "timestamp": self.utc_now().isoformat(),
            "bid": await self.adapter.bid(symbol),
            "ask": await self.adapter.ask(symbol),
            "spread_points": await self.adapter.spread_points(symbol),
            "structure_bias": structure_bias,
            "structure_labels": labels_csv,
            "zones": [asdict(z) for z in zones],
            "swings": [asdict(s) for s in swings],
            "events": [asdict(e) for e in events],
            "execution_plan": asdict(plan),
            "series": {
                "H1": await self.timeframe_series_payload(symbol, "H1", self.config.bars_h1),
                "M5": await self.timeframe_series_payload(symbol, "M5", self.config.bars_m5),
                "M1": await self.timeframe_series_payload(symbol, "M1", self.config.bars_m1),
            },
        }

    async def post_snapshot_for_symbol(self, symbol: str) -> None:
        zones, swings, events, bias, labels, plan = await self.analyze_symbol_state(symbol)

        payload = await self.build_snapshot_payload(
            symbol=symbol,
            zones=zones,
            swings=swings,
            events=events,
            structure_bias=bias,
            labels_csv=labels,
            plan=plan,
        )

        reply = await self.ws_request(payload)

        if reply and reply.get("status") == "ok":
            ai = reply.get("ai") or {}
            self.ai_bridge = AiBridgeRecord(
                available=bool(ai),
                prediction=ai.get("prediction", ""),
                confidence=float(ai.get("confidence", 0.0) or 0.0),
                reason=ai.get("reason", ""),
                zone_state=ai.get("zone_state", ""),
                execution_hint=ai.get("execution_hint", ""),
                risk_hint=ai.get("risk_hint", ""),
                model_status=ai.get("model_status", ""),
                received_at=self.utc_now(),
                raw=json.dumps(ai),
            )

    async def post_snapshots(self) -> None:
        symbols = await self.adapter.market_watch_symbols()

        if self.config.max_market_watch_symbols > 0:
            symbols = symbols[: self.config.max_market_watch_symbols]

        for symbol in symbols:
            await self.post_snapshot_for_symbol(symbol)

    # ========================================================
    # MAIN CYCLE
    # ========================================================

    async def symbol_has_required_history(self, symbol: str) -> bool:
        h1 = await self.get_bars(symbol, "H1")
        m5 = await self.get_bars(symbol, "M5")
        m1 = await self.get_bars(symbol, "M1")

        return (
                len(h1) >= self.config.bars_h1
                and len(m5) >= self.config.bars_m5
                and len(m1) >= self.config.bars_m1
        )

    async def analyze_symbol_state(
            self,
            symbol: str,
    ) -> tuple[
        list[ZoneRecord],
        list[SwingRecord],
        list[StructureEventRecord],
        str,
        str,
        ExecutionPlanRecord,
    ]:
        if not await self.symbol_has_required_history(symbol):
            return [], [], [], "neutral", "", ExecutionPlanRecord()

        swings, events, bias, labels = await self.collect_h1_structure(symbol)
        zones = await self.collect_zone_candidates(symbol)
        zones = await self.finalize_zones(symbol, zones, bias)
        plan = await self.evaluate_execution_plan(symbol, zones, bias)

        return zones, swings, events, bias, labels, plan

    async def refresh_chart_state(self) -> None:
        symbol = await self.adapter.symbol()

        zones, swings, events, bias, labels, plan = await self.analyze_symbol_state(symbol)

        self.chart_zones = zones
        self.chart_swings = swings
        self.chart_events = events
        self.structure_bias = bias
        self.structure_labels_csv = labels
        self.execution_plan = plan

    async def execute_auto_trade_if_needed(self) -> None:
        if not self.config.enable_auto_execution:
            return

        plan = self.execution_plan

        if not plan.allowed:
            return

        if plan.prediction not in {"BUY", "SELL"}:
            return

        if self.config.require_ai_agreement_for_auto_execution:
            if not self.ai_bridge.available:
                return
            if self.ai_bridge.prediction != plan.prediction:
                return

        symbol = await self.adapter.symbol()
        order_type = "market_buy" if plan.prediction == "BUY" else "market_sell"
        price = await self.adapter.ask(symbol) if plan.prediction == "BUY" else await self.adapter.bid(symbol)

        lots = await self.normalize_lots(symbol, self.config.auto_execution_lots)
        sl = await self.normalize_price(symbol, plan.stop_loss)
        tp = await self.normalize_price(symbol, plan.take_profit)

        ok, reason, lots, price, sl, tp = await self.pre_trade_check(
            command_id="auto",
            symbol=symbol,
            order_type=order_type,
            lots=lots,
            price=price,
            sl=sl,
            tp=tp,
        )

        if not ok:
            logger.warning("ZONES auto execution blocked: %s", reason)
            return

        ticket = await self.adapter.send_order(
            symbol=symbol,
            order_type=order_type,
            lots=lots,
            price=price,
            sl=sl,
            tp=tp,
            comment=f"ZONES_AUTO_{plan.active_zone_id}",
            magic_number=self.config.magic_number,
            slippage=self.config.max_slippage,
        )

        self.last_trade_time = time.time()

        logger.warning(
            "ZONES auto execution opened ticket=%s prediction=%s zone=%s",
            ticket,
            plan.prediction,
            plan.active_zone_id,
        )

    async def run_bridge_cycle(self, include_all_symbols: bool = True) -> None:
        await self.refresh_chart_state()
        await self.execute_auto_trade_if_needed()

        if self.config.enable_bridge_posting:
            if include_all_symbols:
                await self.post_snapshots()
            else:
                await self.post_snapshot_for_symbol(await self.adapter.symbol())

            await self.poll_commands()

    async def start(self) -> None:
        if self.config.enable_bridge_posting:
            health = await self.ws_request({"action": "health"})
            if health:
                logger.info("ZONES bridge ready: %s", health)
            else:
                logger.warning("ZONES bridge unavailable at startup. Continuing local analysis.")

        await self.run_bridge_cycle(include_all_symbols=False)

        while True:
            await asyncio.sleep(self.config.timer_seconds)
            await self.run_bridge_cycle(include_all_symbols=True)


