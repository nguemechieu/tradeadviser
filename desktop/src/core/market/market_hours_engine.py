from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

try:
    import pandas_market_calendars as market_calendars
except Exception:  # pragma: no cover - optional dependency fallback
    market_calendars = None


UTC = timezone.utc
try:
    US_EASTERN = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - environment-specific fallback
    try:
        import pytz

        US_EASTERN = pytz.timezone("US/Eastern")
    except Exception:
        US_EASTERN = timezone(timedelta(hours=-5))
_CRYPTO_QUOTES = {"USDT", "USDC", "BUSD", "DAI", "BTC", "ETH", "BNB", "SOL"}
_FX_CODES = {
    "AUD",
    "CAD",
    "CHF",
    "CNH",
    "EUR",
    "GBP",
    "JPY",
    "MXN",
    "NOK",
    "NZD",
    "SEK",
    "SGD",
    "TRY",
    "USD",
    "ZAR",
}
_VENUE_TO_ASSET_TYPE = {
    "alpaca": "stocks",
    "binance": "crypto",
    "binanceus": "crypto",
    "bybit": "crypto",
    "coinbase": "crypto",
    "cme": "futures",
    "fxcm": "forex",
    "kraken": "crypto",
    "oanda": "forex",
    "schwab": "stocks",
    "tradovate": "futures",
}


def _coerce_datetime(value: datetime | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.now(UTC)


def _eastern_datetime(session_date: date, session_time: time) -> datetime:
    naive = datetime.combine(session_date, session_time)
    localize = getattr(US_EASTERN, "localize", None)
    if callable(localize):
        return localize(naive)
    return naive.replace(tzinfo=US_EASTERN)


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(weeks=max(0, occurrence - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _observed_holiday(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=64)
def _nyse_fallback_holidays(year: int) -> frozenset[date]:
    holidays = {
        _observed_holiday(date(year, 1, 1)),
        _nth_weekday_of_month(year, 1, 0, 3),
        _nth_weekday_of_month(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday_of_month(year, 5, 0),
        _observed_holiday(date(year, 6, 19)),
        _observed_holiday(date(year, 7, 4)),
        _nth_weekday_of_month(year, 9, 0, 1),
        _nth_weekday_of_month(year, 11, 3, 4),
        _observed_holiday(date(year, 12, 25)),
        }
    return frozenset(holidays)


@dataclass(slots=True)
class MarketWindowDecision:
    asset_type: str
    symbol: str | None
    market_open: bool
    trade_allowed: bool
    session: str | None
    high_liquidity: bool | None
    reason: str
    evaluated_at: datetime

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evaluated_at"] = self.evaluated_at.isoformat()
        return payload


class MarketHoursEngine:
    """Session-aware market availability and liquidity checks."""

    def __init__(
            self,
            *,
            default_asset_type: str = "crypto",
            logger: logging.Logger | None = None,
    ) -> None:
        self.default_asset_type = self.normalize_asset_type(default_asset_type)
        self.logger = logger or logging.getLogger("MarketHoursEngine")
        self._nyse = market_calendars.get_calendar("NYSE") if market_calendars is not None else None
        self._nyse_schedule_cache: dict[date, tuple[datetime, datetime] | None] = {}
        if self._nyse is None:
            self.logger.info("pandas_market_calendars unavailable; using NYSE holiday fallback calendar.")

    def normalize_asset_type(self, asset_type: str | None) -> str:
        fallback = getattr(self, "default_asset_type", "crypto")
        normalized = str(asset_type or fallback or "crypto").strip().lower()
        return {
            "equity": "stocks",
            "equities": "stocks",
            "fx": "forex",
            "stock": "stocks",
        }.get(normalized, normalized or "crypto")

    def infer_asset_type(
            self,
            asset_type: str | None = None,
            *,
            symbol: str | None = None,
            metadata: Mapping[str, Any] | None = None,
    ) -> str:
        metadata = metadata or {}
        for candidate in (
                asset_type,
                metadata.get("asset_type"),
                metadata.get("market_type"),
                metadata.get("exchange_type"),
                metadata.get("broker_type"),
                _VENUE_TO_ASSET_TYPE.get(str(metadata.get("exchange") or metadata.get("venue") or "").strip().lower()),
        ):
            if candidate is None or not str(candidate).strip():
                continue
            normalized = self.normalize_asset_type(candidate)
            if normalized in {"crypto", "forex", "stocks", "futures"}:
                return normalized

        raw_symbol = str(symbol or metadata.get("symbol") or "").strip().upper()
        if "/" in raw_symbol:
            base, quote = raw_symbol.split("/", 1)
            if base in _FX_CODES and quote in _FX_CODES:
                return "forex"
            if quote in _CRYPTO_QUOTES or base in {"BTC", "ETH", "SOL", "XRP", "DOGE"}:
                return "crypto"
        if "_" in raw_symbol:
            base, quote = raw_symbol.split("_", 1)
            if base in _FX_CODES and quote in _FX_CODES:
                return "forex"
        if raw_symbol.isalpha() and 1 <= len(raw_symbol) <= 5:
            return "stocks"
        return self.default_asset_type

    def is_crypto_market_open(self, *, now: datetime | None = None) -> bool:
        _ = now
        return True

    def is_forex_market_open(self, *, now: datetime | None = None) -> bool:
        current = _coerce_datetime(now)
        weekday = current.weekday()
        current_time = current.time()
        if weekday == 5:
            return False
        if weekday == 6:
            return current_time >= time(22, 0)
        if weekday == 4:
            return current_time < time(22, 0)
        return True

    def is_futures_market_open(self, *, now: datetime | None = None) -> bool:
        current = _coerce_datetime(now)
        weekday = current.weekday()
        current_time = current.time()
        if weekday == 5:
            return False
        if weekday == 6:
            return current_time >= time(23, 0)
        if weekday == 4 and current_time >= time(22, 0):
            return False
        return not (time(22, 0) <= current_time < time(23, 0))

    def is_stock_market_open(self, *, now: datetime | None = None) -> bool:
        current_utc = _coerce_datetime(now)
        current_et = current_utc.astimezone(US_EASTERN)
        if current_et.weekday() >= 5:
            return False

        session_window = self._get_nyse_session(current_et.date())
        if session_window is None:
            return False
        open_utc, close_utc = session_window
        return open_utc <= current_utc < close_utc

    def get_forex_session(self, *, now: datetime | None = None) -> str:
        current = _coerce_datetime(now)
        if not self.is_forex_market_open(now=current):
            return "inactive"

        current_time = current.time()
        sydney_active = current_time >= time(21, 0) or current_time < time(6, 0)
        tokyo_active = time(0, 0) <= current_time < time(9, 0)
        london_active = time(7, 0) <= current_time < time(16, 0)
        new_york_active = time(12, 0) <= current_time < time(21, 0)

        if london_active and new_york_active:
            return "overlap"
        if london_active:
            return "london"
        if new_york_active:
            return "new_york"
        if tokyo_active:
            return "tokyo"
        if sydney_active:
            return "sydney"
        return "inactive"

    def is_high_liquidity_session(self, *, now: datetime | None = None) -> bool:
        return self.get_forex_session(now=now) in {"london", "new_york", "overlap"}

    def is_market_open(
            self,
            asset_type: str,
            *,
            now: datetime | None = None,
            symbol: str | None = None,
            metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        normalized = self.infer_asset_type(asset_type, symbol=symbol, metadata=metadata)
        current = _coerce_datetime(now)
        if normalized == "crypto":
            return self.is_crypto_market_open(now=current)
        if normalized == "forex":
            return self.is_forex_market_open(now=current)
        if normalized == "stocks":
            return self.is_stock_market_open(now=current)
        if normalized == "futures":
            return self.is_futures_market_open(now=current)
        self.logger.warning("Unknown asset_type=%s; defaulting to closed market behavior.", normalized)
        return False

    def evaluate_trade_window(
            self,
            *,
            asset_type: str | None = None,
            symbol: str | None = None,
            metadata: Mapping[str, Any] | None = None,
            now: datetime | None = None,
            require_high_liquidity: bool = False,
    ) -> MarketWindowDecision:
        current = _coerce_datetime(now)
        normalized = self.infer_asset_type(asset_type, symbol=symbol, metadata=metadata)
        market_open = self.is_market_open(normalized, now=current, symbol=symbol, metadata=metadata)
        session: str | None = None
        high_liquidity: bool | None = None

        if normalized == "forex":
            session = self.get_forex_session(now=current)
            high_liquidity = self.is_high_liquidity_session(now=current)
        elif normalized == "stocks":
            session = "regular" if market_open else "closed"
        elif normalized == "crypto":
            session = "continuous"
        elif normalized == "futures":
            session = "extended" if market_open else "maintenance"

        trade_allowed = market_open
        if trade_allowed and normalized == "forex" and require_high_liquidity and not bool(high_liquidity):
            trade_allowed = False

        if not market_open:
            if normalized == "stocks":
                reason = "stock market is closed due to regular hours, weekend, or holiday."
            elif normalized == "forex":
                reason = "forex market is closed outside the Sunday 22:00 UTC to Friday 22:00 UTC window."
            elif normalized == "futures":
                reason = "futures market is in a maintenance or weekend closure window."
            else:
                reason = f"{normalized} market is closed."
        elif normalized == "forex" and require_high_liquidity and not bool(high_liquidity):
            reason = f"forex session {session} is open but below the configured liquidity threshold."
        else:
            reason = f"{normalized} market is open."
            if session:
                reason = f"{reason[:-1]} during the {session} session."

        decision = MarketWindowDecision(
            asset_type=normalized,
            symbol=str(symbol or "").strip() or None,
            market_open=market_open,
            trade_allowed=trade_allowed,
            session=session,
            high_liquidity=high_liquidity,
            reason=reason,
            evaluated_at=current,
        )
        self.logger.info(
            "Market hours decision asset_type=%s symbol=%s open=%s allowed=%s session=%s high_liquidity=%s reason=%s",
            decision.asset_type,
            decision.symbol or "-",
            decision.market_open,
            decision.trade_allowed,
            decision.session or "-",
            decision.high_liquidity,
            decision.reason,
            )
        return decision

    def _get_nyse_session(self, session_date: date) -> tuple[datetime, datetime] | None:
        if session_date in self._nyse_schedule_cache:
            return self._nyse_schedule_cache[session_date]

        if self._nyse is not None:
            schedule = self._nyse.schedule(start_date=session_date.isoformat(), end_date=session_date.isoformat())
            if schedule.empty:
                self._nyse_schedule_cache[session_date] = None
                return None
            row = schedule.iloc[0]
            market_open = row["market_open"].to_pydatetime().astimezone(UTC)
            market_close = row["market_close"].to_pydatetime().astimezone(UTC)
            self._nyse_schedule_cache[session_date] = (market_open, market_close)
            return self._nyse_schedule_cache[session_date]

        if session_date in _nyse_fallback_holidays(session_date.year):
            self._nyse_schedule_cache[session_date] = None
            return None

        open_et = _eastern_datetime(session_date, time(9, 30))
        close_et = _eastern_datetime(session_date, time(16, 0))
        self._nyse_schedule_cache[session_date] = (open_et.astimezone(UTC), close_et.astimezone(UTC))
        return self._nyse_schedule_cache[session_date]