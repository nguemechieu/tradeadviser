import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import socket

import aiohttp

from broker.base_broker import BaseBroker


class OandaBroker(BaseBroker):
    MAX_OHLCV_COUNT = 5000
    GRANULARITY_MAP = {
        "1m": "M1",
        "5m": "M5",
        "15m": "M15",
        "30m": "M30",
        "1h": "H1",
        "2h": "H2",
        "4h": "H4",
        "1d": "D",
        "1w": "W",
        "1mn":"Mn"
    }
    CANDLE_PRICE_COMPONENT_MAP = {
        "b": "B",
        "bid": "B",
        "a": "A",
        "ask": "A",
        "m": "M",
        "mid": "M",
        "midpoint": "M",
    }
    CANDLE_PRICE_BUCKET_MAP = {
        "B": "bid",
        "A": "ask",
        "M": "mid",
    }
    GRANULARITY_SECONDS_MAP = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D": 86400,
        "W": 604800,
    }

    def __init__(self, config):
        super().__init__()

        self.logger = logging.getLogger("OandaBroker")
        self.config = config
        self.exchange_name = "oanda"
        self.hedging_supported = True

        self.token = getattr(config, "api_key", None) or getattr(config, "token", None)
        self.account_id = getattr(config, "account_id", None)
        self.mode = (getattr(config, "mode", "paper") or "paper").lower()
        self.base_url = (
            "https://api-fxpractice.oanda.com"
            if self.mode in {"paper", "practice", "sandbox"}
            else "https://api-fxtrade.oanda.com"
        )
        self.stream_base_url = (
            "https://stream-fxpractice.oanda.com"
            if self.mode in {"paper", "practice", "sandbox"}
            else "https://stream-fxtrade.oanda.com"
        )
        options = dict(getattr(config, "options", None) or {})
        params = dict(getattr(config, "params", None) or {})
        self.candle_price_component = self._normalize_candle_price_component(
            options.get("candle_price_component", params.get("candle_price_component", "bid"))
        )

        self.session = None
        self._connected = False
        self._instrument_details = {}

        if not self.token:
            raise ValueError("Oanda API token is required")
        if not self.account_id:
            raise ValueError("Oanda account_id is required")

    def supported_market_venues(self):
        return ["auto", "otc"]

    # ===============================
    # INTERNALS
    # ===============================

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _ensure_connected(self):
        if not self._session_is_usable():
            await self.connect()

    def _session_is_usable(self):
        session = self.session
        if session is None:
            return False
        if bool(getattr(session, "closed", False)):
            return False
        return bool(self._connected)

    async def _dispose_session(self):
        session = self.session
        self.session = None
        self._connected = False
        if session is None:
            return
        try:
            await session.close()
        except Exception:
            self.logger.debug("Failed to close stale Oanda session cleanly.", exc_info=True)

    @staticmethod
    def _is_stale_transport_error(exc):
        reconnectable_types = tuple(
            error_type
            for error_type in (
                ConnectionResetError,
                BrokenPipeError,
                aiohttp.ServerDisconnectedError,
                getattr(aiohttp, "ClientConnectionResetError", None),
                getattr(aiohttp, "ClientOSError", None),
            )
            if error_type is not None
        )
        if reconnectable_types and isinstance(exc, reconnectable_types):
            return True

        message = str(exc or "").strip().lower()
        return any(
            token in message
            for token in (
                "cannot write to closing transport",
                "session is closed",
                "connector is closed",
                "server disconnected",
            )
        )

    async def _request(self, method, path, params=None, payload=None):
        url = f"{self.base_url}{path}"
        for attempt in range(2):
            await self._ensure_connected()
            try:
                async with self.session.request(
                    method,
                    url,
                    headers=self._headers,
                    params=params,
                    json=payload,
                ) as response:
                    try:
                        response.raise_for_status()
                    except aiohttp.ClientResponseError as exc:
                        detail = ""
                        payload_json = {}
                        try:
                            payload_text = await response.text()
                            detail = payload_text.strip()
                            if detail:
                                payload_json = json.loads(detail)
                        except Exception:
                            detail = ""
                            payload_json = {}

                        if isinstance(payload_json, dict):
                            detail_parts = []
                            error_message = payload_json.get("errorMessage") or payload_json.get("message")
                            reject_transaction = payload_json.get("orderRejectTransaction") or {}
                            reject_reason = ""
                            if isinstance(reject_transaction, dict):
                                reject_reason = (
                                    reject_transaction.get("rejectReason")
                                    or reject_transaction.get("reason")
                                    or ""
                                )
                            if error_message:
                                detail_parts.append(str(error_message).strip())
                            if reject_reason:
                                detail_parts.append(str(reject_reason).strip())
                            if detail_parts:
                                detail = " | ".join(part for part in detail_parts if part)

                        message = f"{exc.status} {exc.message}"
                        if detail:
                            message = f"{message}: {detail}"
                        raise RuntimeError(message) from exc
                    return await response.json()
            except Exception as exc:
                if attempt == 0 and self._is_stale_transport_error(exc):
                    self.logger.warning(
                        "Oanda session became stale during %s %s; rebuilding the HTTP session and retrying once.",
                        method,
                        path,
                    )
                    await self._dispose_session()
                    continue
                if isinstance(exc, aiohttp.ClientConnectorDNSError):
                    raise RuntimeError(
                        "Network DNS lookup failed while connecting to Oanda. "
                        "Check your internet connection, DNS settings, VPN, proxy, or firewall."
                    ) from exc
                if isinstance(exc, (aiohttp.ClientConnectorError, asyncio.TimeoutError)):
                    raise RuntimeError(
                        f"Network connection failed while connecting to Oanda: {exc}"
                    ) from exc
                raise

    def _normalize_symbol(self, symbol):
        if not symbol:
            return symbol
        return str(symbol).replace("/", "_").upper()

    @staticmethod
    def _display_symbol(symbol):
        if not symbol:
            return symbol
        return str(symbol).strip().upper().replace("_", "/").replace("-", "/")

    @classmethod
    def _instrument_display_name(cls, item):
        if isinstance(item, dict):
            candidate = (
                item.get("displayName")
                or item.get("display_name")
                or item.get("name")
                or item.get("instrument")
                or item.get("symbol")
            )
        else:
            candidate = item
        return cls._display_symbol(candidate)

    def _normalize_granularity(self, timeframe):
        key = str(timeframe or "1h").lower()
        return self.GRANULARITY_MAP.get(key, "H1")

    @classmethod
    def _normalize_candle_price_component(cls, value):
        normalized = str(value or "bid").strip().lower()
        return cls.CANDLE_PRICE_COMPONENT_MAP.get(normalized, "B")

    @classmethod
    def _candle_price_bucket(cls, component):
        normalized = cls._normalize_candle_price_component(component)
        return cls.CANDLE_PRICE_BUCKET_MAP.get(normalized, "bid")

    def set_candle_price_component(self, value):
        normalized = self._normalize_candle_price_component(value)
        self.candle_price_component = normalized

        config = getattr(self, "config", None)
        if config is not None:
            options = dict(getattr(config, "options", None) or {})
            options["candle_price_component"] = self._candle_price_bucket(normalized)
            try:
                config.options = options
            except Exception:
                pass

        return self._candle_price_bucket(normalized)

    @classmethod
    def _granularity_seconds(cls, granularity):
        return cls.GRANULARITY_SECONDS_MAP.get(str(granularity or "").upper())

    @staticmethod
    def _normalize_time_boundary(value, *, end_of_day=False):
        if value is None:
            return None

        if isinstance(value, datetime):
            timestamp = value
        else:
            text = str(value or "").strip()
            if not text:
                return None
            if "T" not in text and len(text) <= 10:
                text = (
                    f"{text}T23:59:59.999999+00:00"
                    if end_of_day
                    else f"{text}T00:00:00+00:00"
                )
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            timestamp = datetime.fromisoformat(text)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        return timestamp

    @staticmethod
    def _format_time_boundary(value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc)

    def _recent_history_boundaries(self, granularity, requested):
        step_seconds = self._granularity_seconds(granularity)
        if not step_seconds:
            return None, None
        try:
            requested_value = max(1, int(requested or 1))
        except Exception:
            requested_value = 1
        overscan = min(max(requested_value // 4, 8), 500)
        end_boundary = self._utc_now()
        start_boundary = end_boundary - timedelta(seconds=step_seconds * (requested_value + overscan))
        return start_boundary, end_boundary

    def _extract_price_entry(self, payload, symbol):
        prices = payload.get("prices", []) if isinstance(payload, dict) else []
        target = self._normalize_symbol(symbol)
        for price in prices:
            if price.get("instrument") == target:
                return price
        return prices[0] if prices else {}

    @classmethod
    def pricing_stream_payload_to_tick(cls, payload, *, requested_symbol=None):
        if not isinstance(payload, dict):
            return None

        payload_type = str(payload.get("type") or "").strip().upper()
        if payload_type and payload_type != "PRICE":
            return None

        instrument = str(payload.get("instrument") or cls._normalize_symbol(requested_symbol) or "").strip().upper()
        if not instrument:
            return None

        bids = list(payload.get("bids") or [])
        asks = list(payload.get("asks") or [])

        def _price(levels, fallback_key):
            if levels:
                try:
                    return float(levels[0].get("price"))
                except Exception:
                    pass
            try:
                fallback = payload.get(fallback_key)
                return float(fallback) if fallback is not None else None
            except Exception:
                return None

        bid = _price(bids, "closeoutBid")
        ask = _price(asks, "closeoutAsk")
        if bid is None and ask is None:
            return None

        midpoint = ((bid + ask) / 2.0) if bid is not None and ask is not None else (ask if ask is not None else bid)
        last = ask if ask is not None else bid
        symbol = cls._display_symbol(requested_symbol or instrument)

        tick = {
            "symbol": symbol,
            "instrument": instrument,
            "bid": bid,
            "ask": ask,
            "price": midpoint,
            "last": last,
            "tradeable": payload.get("tradeable"),
            "status": payload.get("status"),
            "timestamp": payload.get("time"),
            "raw": payload,
        }

        if bids:
            try:
                tick["bid_size"] = float(bids[0].get("liquidity", 0) or 0)
            except Exception:
                pass
        if asks:
            try:
                tick["ask_size"] = float(asks[0].get("liquidity", 0) or 0)
            except Exception:
                pass
        return tick

    async def _ensure_instrument_details(self):
        if self._instrument_details:
            return self._instrument_details

        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/instruments")
        instruments = payload.get("instruments", []) if isinstance(payload, dict) else []
        self._instrument_details = {
            item.get("name"): item
            for item in instruments
            if isinstance(item, dict) and item.get("name")
        }
        return self._instrument_details

    async def _get_instrument_meta(self, symbol):
        instrument = self._normalize_symbol(symbol)
        details = await self._ensure_instrument_details()
        return details.get(instrument, {})

    def _format_units(self, amount, precision):
        units = float(amount)
        precision = max(0, int(precision or 0))
        if precision == 0:
            return str(int(round(units)))
        formatted = f"{units:.{precision}f}".rstrip("0").rstrip(".")
        return formatted or "0"

    def _format_price(self, price, precision):
        precision = max(0, int(precision or 5))
        return f"{float(price):.{precision}f}"

    def _float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            if default is None:
                return None
            try:
                return float(default)
            except Exception:
                return None

    def _normalize_order_status(self, status):
        normalized = str(status or "").upper()
        mapping = {
            "PENDING": "open",
            "OPEN": "open",
            "FILLED": "filled",
            "CANCELLED": "canceled",
            "CANCEL_PENDING": "canceling",
            "TRIGGERED": "filled",
            "REJECTED": "rejected",
        }
        return mapping.get(normalized, normalized.lower() if normalized else "unknown")

    def _normalize_order_payload(
        self,
        payload,
        fallback_symbol=None,
        fallback_side=None,
        fallback_type=None,
        fallback_amount=None,
        fallback_price=None,
        fallback_stop_price=None,
    ):
        if not isinstance(payload, dict):
            return payload

        order = (
            payload.get("order")
            or payload.get("orderCreateTransaction")
            or payload.get("orderCancelTransaction")
            or payload.get("lastTransaction")
            or {}
        )
        fill = payload.get("orderFillTransaction") or {}

        instrument = order.get("instrument") or fill.get("instrument") or self._normalize_symbol(fallback_symbol)
        units_value = (
            order.get("units")
            or fill.get("units")
            or fill.get("tradeOpened", {}).get("units")
            or fallback_amount
            or 0
        )
        try:
            units_float = float(units_value)
        except Exception:
            units_float = float(fallback_amount or 0)

        side = fallback_side
        if side is None:
            side = "buy" if units_float >= 0 else "sell"

        order_type = str(order.get("type") or fallback_type or "").lower() or None
        if str(fallback_type or "").strip().lower() == "stop_limit":
            order_type = "stop_limit"
        status = self._normalize_order_status(
            order.get("state")
            or fill.get("reason")
            or payload.get("state")
            or ("FILLED" if fill else None)
        )

        price_value = (
            order.get("price")
            or order.get("priceBound")
            or fill.get("price")
            or fill.get("fullVWAP")
            or fallback_price
        )
        try:
            price_float = float(price_value) if price_value is not None else None
        except Exception:
            price_float = fallback_price

        filled_value = (
            fill.get("units")
            or fill.get("tradeOpened", {}).get("units")
            or (units_float if status == "filled" else 0)
        )
        try:
            filled_float = abs(float(filled_value))
        except Exception:
            filled_float = abs(units_float) if status == "filled" else 0.0

        return {
            "id": str(order.get("id") or fill.get("orderID") or payload.get("id") or ""),
            "symbol": self._display_symbol(instrument),
            "instrument": instrument,
            "side": str(side).lower(),
            "type": order_type,
            "status": status,
            "amount": abs(units_float),
            "filled": filled_float,
            "price": price_float,
            "stop_price": self._float(order.get("triggerPrice") or order.get("price"), fallback_stop_price),
            "raw": payload,
        }

    def _normalize_position_leg(self, instrument, leg_side, leg_payload, aggregate_position):
        if not isinstance(leg_payload, dict):
            return None
        units = abs(float(leg_payload.get("units", 0) or 0))
        if units <= 0:
            return None

        long_leg = aggregate_position.get("long", {}) or {}
        short_leg = aggregate_position.get("short", {}) or {}
        total_units = abs(float(long_leg.get("units", 0) or 0)) + abs(float(short_leg.get("units", 0) or 0))
        share = (units / total_units) if total_units > 0 else 1.0
        realized_pl = float(aggregate_position.get("pl", 0) or 0) * share
        unrealized_pl = float(aggregate_position.get("unrealizedPL", 0) or 0) * share
        resettable_pl = float(aggregate_position.get("resettablePL", 0) or 0) * share
        financing = float(aggregate_position.get("financing", 0) or 0) * share
        dividend_adjustment = float(aggregate_position.get("dividendAdjustment", 0) or 0) * share
        margin_used = float(aggregate_position.get("marginUsed", 0) or 0) * share
        value = float(aggregate_position.get("positionValue", 0) or 0) * share
        signed_units = units if leg_side == "long" else -units

        return {
            "symbol": self._display_symbol(instrument),
            "instrument": instrument,
            "position_id": f"{instrument}:{leg_side}",
            "position_key": f"{instrument}:{leg_side}",
            "position_side": leg_side,
            "amount": units,
            "side": leg_side,
            "entry_price": float(leg_payload.get("averagePrice", 0) or 0),
            "units": signed_units,
            "value": value,
            "pnl": unrealized_pl,
            "unrealized_pnl": unrealized_pl,
            "unrealized_pl": unrealized_pl,
            "realized_pnl": realized_pl,
            "realized_pl": realized_pl,
            "resettable_pl": resettable_pl,
            "financing": financing,
            "dividend_adjustment": dividend_adjustment,
            "margin_used": margin_used,
            "trade_ids": list(leg_payload.get("tradeIDs") or []),
            "raw": aggregate_position,
        }

    # ===============================
    # CONNECT
    # ===============================

    async def connect(self):
        if self._session_is_usable():
            return True

        await self._dispose_session()

        resolver = aiohttp.ThreadedResolver()
        connector = aiohttp.TCPConnector(
            resolver=resolver,
            family=socket.AF_INET,
            ttl_dns_cache=300,
        )
        timeout = aiohttp.ClientTimeout(total=45)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        self._connected = True
        return True

    async def close(self):
        await self._dispose_session()

    # ===============================
    # MARKET DATA
    # ===============================

    async def fetch_ticker(self, symbol):
        instrument = self._normalize_symbol(symbol)
        payload = await self._request(
            "GET",
            f"/v3/accounts/{self.account_id}/pricing",
            params={"instruments": instrument},
        )
        entry = self._extract_price_entry(payload, instrument)
        bids = entry.get("bids", [])
        asks = entry.get("asks", [])
        bid = float(bids[0]["price"]) if bids else None
        ask = float(asks[0]["price"]) if asks else None

        return {
            "symbol": self._display_symbol(symbol),
            "instrument": instrument,
            "bid": bid,
            "ask": ask,
            "last": ask or bid,
            "raw": entry,
        }

    async def stream_ticks(self, symbol):
        instrument = self._normalize_symbol(symbol)
        url = f"{self.stream_base_url}/v3/accounts/{self.account_id}/pricing/stream"
        params = {"instruments": instrument}

        reconnectable_errors = (
            asyncio.TimeoutError,
            aiohttp.ClientConnectionError,
            aiohttp.ClientPayloadError,
            aiohttp.ServerDisconnectedError,
        )

        while True:
            timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=None)
            session = aiohttp.ClientSession(timeout=timeout)
            try:
                async with session.request("GET", url, headers=self._headers, params=params) as response:
                    try:
                        response.raise_for_status()
                    except aiohttp.ClientResponseError as exc:
                        detail = ""
                        try:
                            detail = (await response.text()).strip()
                        except Exception:
                            detail = ""
                        message = f"{exc.status} {exc.message}"
                        if detail:
                            message = f"{message}: {detail}"
                        raise RuntimeError(message) from exc

                    async for raw_line in response.content:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            self.logger.debug("Skipping malformed Oanda pricing stream payload: %s", line)
                            continue
                        tick = self.pricing_stream_payload_to_tick(payload, requested_symbol=symbol)
                        if tick is not None:
                            yield tick
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientConnectorDNSError as exc:
                raise RuntimeError(
                    "Network DNS lookup failed while connecting to the Oanda pricing stream. "
                    "Check your internet connection, DNS settings, VPN, proxy, or firewall."
                ) from exc
            except reconnectable_errors as exc:
                self.logger.warning(
                    "Oanda pricing stream disconnected for %s; retrying shortly: %s",
                    instrument,
                    exc,
                )
                await asyncio.sleep(1.0)
            except Exception as exc:
                if self._is_stale_transport_error(exc):
                    self.logger.warning(
                        "Oanda pricing stream transport became stale for %s; retrying shortly.",
                        instrument,
                    )
                    await asyncio.sleep(1.0)
                    continue
                raise
            finally:
                await session.close()

    async def fetch_orderbook(self, symbol, limit=50):
        ticker = await self.fetch_ticker(symbol)
        bids = []
        asks = []

        raw = ticker.get("raw", {})
        for level in raw.get("bids", [])[:limit]:
            bids.append([float(level["price"]), float(level.get("liquidity", 0) or 0)])
        for level in raw.get("asks", [])[:limit]:
            asks.append([float(level["price"]), float(level.get("liquidity", 0) or 0)])

        return {
            "symbol": self._display_symbol(symbol),
            "instrument": self._normalize_symbol(symbol),
            "bids": bids,
            "asks": asks,
        }

    async def _fetch_ohlcv_with_component(self, instrument, granularity, requested, *, price_component, start_boundary=None, end_boundary=None):
        collected = []
        seen_times = set()
        cursor_to = None
        previous_oldest = None
        candle_price_bucket = self._candle_price_bucket(price_component)
        step_seconds = self._granularity_seconds(granularity)

        if start_boundary is not None and end_boundary is not None:
            if end_boundary < start_boundary:
                end_boundary = start_boundary

            current_from = start_boundary
            while current_from <= end_boundary and len(collected) < requested:
                remaining = max(1, requested - len(collected))
                batch_limit = min(remaining, self.MAX_OHLCV_COUNT)
                if step_seconds:
                    next_batch_from = current_from + timedelta(seconds=step_seconds * batch_limit)
                    if next_batch_from > end_boundary:
                        current_to = end_boundary
                    else:
                        current_to = current_from + timedelta(
                            seconds=step_seconds * max(batch_limit - 1, 0)
                        )
                else:
                    current_to = end_boundary

                params = {
                    "granularity": granularity,
                    "price": price_component,
                    "from": self._format_time_boundary(current_from),
                    "to": self._format_time_boundary(current_to),
                }
                payload = await self._request(
                    "GET",
                    f"/v3/instruments/{instrument}/candles",
                    params=params,
                )

                batch = []
                for candle in payload.get("candles", []):
                    price_payload = (
                        candle.get(candle_price_bucket)
                        or candle.get("mid")
                        or candle.get("bid")
                        or candle.get("ask")
                        or {}
                    )
                    if not candle.get("complete"):
                        continue
                    timestamp = candle.get("time")
                    if not timestamp:
                        continue
                    batch.append(
                        [
                            timestamp,
                            float(price_payload.get("o", 0) or 0),
                            float(price_payload.get("h", 0) or 0),
                            float(price_payload.get("l", 0) or 0),
                            float(price_payload.get("c", 0) or 0),
                            float(candle.get("volume", 0) or 0),
                        ]
                    )

                batch.sort(key=lambda row: row[0])
                for row in batch:
                    if row[0] in seen_times:
                        continue
                    seen_times.add(row[0])
                    collected.append(row)

                if current_to >= end_boundary:
                    break
                if step_seconds:
                    current_from = current_to + timedelta(seconds=step_seconds)
                else:
                    break

            return collected[-requested:]

        while len(collected) < requested:
            batch_size = min(requested - len(collected), self.MAX_OHLCV_COUNT)
            params = {
                "granularity": granularity,
                "count": batch_size,
                "price": price_component,
            }
            if cursor_to:
                params["to"] = cursor_to

            payload = await self._request(
                "GET",
                f"/v3/instruments/{instrument}/candles",
                params=params,
            )

            batch = []
            for candle in payload.get("candles", []):
                price_payload = (
                    candle.get(candle_price_bucket)
                    or candle.get("mid")
                    or candle.get("bid")
                    or candle.get("ask")
                    or {}
                )
                if not candle.get("complete"):
                    continue
                timestamp = candle.get("time")
                if not timestamp:
                    continue
                batch.append(
                    [
                        timestamp,
                        float(price_payload.get("o", 0) or 0),
                        float(price_payload.get("h", 0) or 0),
                        float(price_payload.get("l", 0) or 0),
                        float(price_payload.get("c", 0) or 0),
                        float(candle.get("volume", 0) or 0),
                    ]
                )

            if not batch:
                break

            batch.sort(key=lambda row: row[0])
            oldest_time = batch[0][0]

            new_rows = 0
            for row in batch:
                if row[0] in seen_times:
                    continue
                seen_times.add(row[0])
                collected.append(row)
                new_rows += 1

            collected.sort(key=lambda row: row[0])

            if len(collected) >= requested:
                break
            if len(batch) < batch_size:
                break
            if new_rows == 0 or oldest_time == previous_oldest:
                break

            previous_oldest = oldest_time
            cursor_to = oldest_time

        return collected[-requested:]

    async def fetch_ohlcv(self, symbol, timeframe="H1", limit=100, start_time=None, end_time=None):
        instrument = self._normalize_symbol(symbol)
        granularity = self._normalize_granularity(timeframe)
        requested = max(1, int(limit or 100))
        price_component = self._normalize_candle_price_component(
            getattr(self, "candle_price_component", "bid")
        )
        start_boundary = self._normalize_time_boundary(start_time, end_of_day=False)
        end_boundary = self._normalize_time_boundary(end_time, end_of_day=True)
        explicit_range_requested = start_boundary is not None or end_boundary is not None

        async def _load_history(component, range_start=None, range_end=None):
            return await self._fetch_ohlcv_with_component(
                instrument,
                granularity,
                requested,
                price_component=component,
                start_boundary=range_start,
                end_boundary=range_end,
            )

        async def _load_recent_window(component):
            if explicit_range_requested:
                return []
            recent_start, recent_end = self._recent_history_boundaries(granularity, requested)
            if recent_start is None or recent_end is None:
                return []
            return await _load_history(component, recent_start, recent_end)

        candles = await _load_history(price_component, start_boundary, end_boundary)
        if not candles:
            candles = await _load_recent_window(price_component)
        if candles or price_component == "M":
            return candles

        self.logger.warning(
            "Oanda returned no %s candles for %s (%s); retrying with midpoint candles.",
            self._candle_price_bucket(price_component),
            instrument,
            granularity,
        )
        candles = await _load_history("M", start_boundary, end_boundary)
        if candles:
            return candles
        return await _load_recent_window("M")

    async def fetch_trades(self, symbol=None, limit=None):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/trades")
        trades = payload.get("trades", [])
        target = self._normalize_symbol(symbol) if symbol else None
        filtered = [trade for trade in trades if target is None or trade.get("instrument") == target]
        return filtered[:limit] if limit else filtered

    async def fetch_symbol(self):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/instruments")
        instruments = payload.get("instruments", []) if isinstance(payload, dict) else []
        self._instrument_details = {
            item.get("name"): item
            for item in instruments
            if isinstance(item, dict) and item.get("name")
        }
        normalized = []
        for item in instruments:
            display_name = self._instrument_display_name(item)
            if display_name and display_name not in normalized:
                normalized.append(display_name)
        return normalized

    async def fetch_symbols(self):
        return await self.fetch_symbol()

    async def fetch_status(self):
        try:
            await self._request("GET", f"/v3/accounts/{self.account_id}/summary")
            return {"status": "ok", "broker": "oanda"}
        except Exception as exc:
            return {"status": "error", "broker": "oanda", "detail": str(exc)}

    # ===============================
    # ORDERS / ACCOUNT
    # ===============================

    async def fetch_balance(self):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/summary")
        account = payload.get("account", {})
        currency = account.get("currency", "USD")
        balance = float(account.get("balance", 0) or 0)
        margin_used = float(account.get("marginUsed", 0) or 0)
        return {
            "free": {currency: balance - margin_used},
            "used": {currency: margin_used},
            "total": {currency: balance},
            "equity": float(account.get("NAV", balance) or balance),
            "currency": currency,
            "raw": account,
        }

    async def fetch_positions(self, symbols=None):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/openPositions")
        payload2= await self._request("GET", f"/v3/accounts/{self.account_id}/positions")
        positions = payload.get("positions", [])
        positions+=payload2
        targets = {self._normalize_symbol(symbol) for symbol in (symbols or [])}
        normalized = []
        for position in positions:
            instrument = position.get("instrument")
            if targets and instrument not in targets:
                continue
            long_leg = position.get("long", {}) or {}
            short_leg = position.get("short", {}) or {}
            long_position = self._normalize_position_leg(instrument, "long", long_leg, position)
            short_position = self._normalize_position_leg(instrument, "short", short_leg, position)
            if long_position is not None:
                normalized.append(long_position)
            if short_position is not None:
                normalized.append(short_position)
        return normalized

    async def close_position(
        self,
        symbol,
        amount=None,
        params=None,
        order_type="market",
        position=None,
        position_side=None,
        position_id=None,
    ):
        instrument = self._normalize_symbol(symbol)
        snapshot_position = position if isinstance(position, dict) else None
        normalized_id = str(
            position_id
            or (snapshot_position or {}).get("position_id")
            or (snapshot_position or {}).get("id")
            or ""
        ).strip().lower()
        normalized_side = str(
            position_side
            or (snapshot_position or {}).get("position_side")
            or (snapshot_position or {}).get("side")
            or ""
        ).strip().lower()

        targets = await self.fetch_positions(symbols=[instrument])
        if normalized_id:
            targets = [
                item
                for item in targets
                if str(item.get("position_id") or item.get("id") or "").strip().lower() == normalized_id
            ]
        if normalized_side:
            targets = [
                item
                for item in targets
                if str(item.get("position_side") or item.get("side") or "").strip().lower() == normalized_side
            ]
        if len(targets) > 1:
            raise ValueError(
                f"Multiple hedge legs are open for {instrument}. Choose the long or short leg to close."
            )

        target_position = targets[0] if targets else snapshot_position
        if not targets and (normalized_id or normalized_side or snapshot_position is not None):
            raise RuntimeError(f"No live {instrument} position is available to close.")
        if not isinstance(target_position, dict):
            return None

        leg_side = str(
            normalized_side
            or target_position.get("position_side")
            or target_position.get("side")
            or ""
        ).strip().lower()
        if leg_side not in {"long", "short"}:
            raise ValueError(f"Unable to resolve which hedge leg to close for {instrument}.")

        meta = await self._get_instrument_meta(symbol)
        units_precision = int(meta.get("tradeUnitsPrecision", 0) or 0)
        live_amount = self._position_amount(target_position)
        if live_amount <= 0:
            raise RuntimeError(f"No live {instrument} position is available to close.")

        requested_amount = live_amount if amount is None else abs(float(amount))
        close_amount = min(requested_amount, live_amount)
        if close_amount <= 0:
            return None
        precision_step = 1.0 / (10 ** units_precision) if units_precision > 0 else 1.0
        close_all = amount is None or requested_amount >= (live_amount - (precision_step / 2.0))

        payload_key = "shortUnits" if leg_side == "short" else "longUnits"
        payload_value = "ALL" if close_all else self._format_units(close_amount, units_precision)
        payload = {payload_key: payload_value}
        payload.update(dict(params or {}))
        response = await self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/positions/{instrument}/close",
            payload=payload,
        )
        close_transaction = (
            response.get("longOrderCreateTransaction")
            or response.get("shortOrderCreateTransaction")
            or {}
        )
        close_side = "sell" if leg_side == "long" else "buy"
        normalized = self._normalize_order_payload(
            {"order": close_transaction},
            fallback_symbol=instrument,
            fallback_side=close_side,
            fallback_type=order_type,
            fallback_amount=close_amount,
        )
        normalized["amount"] = close_amount
        normalized["position_side"] = leg_side
        normalized["position_id"] = target_position.get("position_id") or f"{instrument}:{leg_side}"
        normalized["status"] = normalized.get("status") or "submitted"
        return normalized

    async def fetch_orders(self, symbol=None, limit=None):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/orders")
        orders = payload.get("orders", [])
        target = self._normalize_symbol(symbol) if symbol else None
        filtered = [
            self._normalize_order_payload({"order": order}, fallback_symbol=symbol)
            for order in orders
            if target is None or order.get("instrument") == target
        ]
        return filtered[:limit] if limit else filtered

    async def fetch_open_orders(self, symbol=None, limit=None):
        orders = await self.fetch_orders(symbol=symbol, limit=limit)
        return [order for order in orders if order.get("status") in {"open", "pending"}]

    async def fetch_closed_orders(self, symbol=None, limit=None):
        orders = await self.fetch_orders(symbol=symbol, limit=limit)
        return [order for order in orders if order.get("status") in {"filled", "canceled", "rejected"}]

    async def fetch_order(self, order_id, symbol=None):
        payload = await self._request("GET", f"/v3/accounts/{self.account_id}/orders/{order_id}")
        order = payload.get("order", payload)
        normalized = self._normalize_order_payload({"order": order}, fallback_symbol=symbol)
        if symbol is None:
            return normalized
        return normalized if normalized.get("instrument") == self._normalize_symbol(symbol) else None

    async def create_order(
        self,
        symbol,
        side,
        amount,
        type="market",
        price=None,
        stop_price=None,
        params=None,
        stop_loss=None,
        take_profit=None,
    ):
        instrument = self._normalize_symbol(symbol)
        normalized_type = str(type or "market").strip().lower() or "market"
        order_type = "STOP" if normalized_type == "stop_limit" else normalized_type.upper()
        meta = await self._get_instrument_meta(symbol)
        units = float(amount)
        if str(side).lower() == "sell":
            units = -abs(units)
        else:
            units = abs(units)

        units_precision = int(meta.get("tradeUnitsPrecision", 0) or 0)
        minimum_trade_size = float(meta.get("minimumTradeSize", 1) or 1)
        if abs(units) < minimum_trade_size:
            units = minimum_trade_size if units >= 0 else -minimum_trade_size

        order = {
            "instrument": instrument,
            "units": self._format_units(units, units_precision),
            "type": order_type,
            "positionFill": "DEFAULT",
        }

        extra = dict(params or {})
        if order_type == "MARKET":
            order["timeInForce"] = str(extra.pop("timeInForce", "FOK")).upper()
        else:
            order["timeInForce"] = str(extra.pop("timeInForce", "GTC")).upper()
            if price is None or float(price) <= 0:
                raise ValueError("Limit orders require a positive price")
            display_precision = int(meta.get("displayPrecision", 5) or 5)
            if normalized_type == "stop_limit":
                trigger_price = extra.pop("stop_price", stop_price)
                if trigger_price is None or float(trigger_price) <= 0:
                    raise ValueError("stop_limit orders require a positive stop_price trigger")
                order["price"] = self._format_price(trigger_price, display_precision)
                order["priceBound"] = self._format_price(price, display_precision)
            else:
                order["price"] = self._format_price(price, display_precision)

        stop_loss = extra.pop("stop_loss", stop_loss)
        take_profit = extra.pop("take_profit", take_profit)
        if stop_loss is not None:
            order["stopLossOnFill"] = {"price": self._format_price(stop_loss, int(meta.get("displayPrecision", 5) or 5))}
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": self._format_price(take_profit, int(meta.get("displayPrecision", 5) or 5))}
        order.update(extra)

        payload = await self._request(
            "POST",
            f"/v3/accounts/{self.account_id}/orders",
            payload={"order": order},
        )
        return self._normalize_order_payload(
            payload,
            fallback_symbol=symbol,
            fallback_side=side,
            fallback_type=normalized_type,
            fallback_amount=amount,
            fallback_price=price,
            fallback_stop_price=stop_price,
        )

    async def cancel_order(self, order_id, symbol=None):
        payload = await self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/orders/{order_id}/cancel",
        )
        normalized = self._normalize_order_payload(payload, fallback_symbol=symbol)
        normalized["id"] = str(order_id)
        normalized["status"] = "canceled"
        return normalized

    async def cancel_all_orders(self, symbol=None):
        orders = await self.fetch_open_orders(symbol=symbol)
        canceled = []
        for order in orders:
            order_id = order.get("id")
            if order_id:
                canceled.append(await self.cancel_order(order_id, symbol=symbol))
        return canceled
