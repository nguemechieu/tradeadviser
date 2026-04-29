from __future__ import annotations

"""
InvestPro MarketHoursEngine

Session-aware market availability and liquidity checks.

Supports:
- crypto: 24/7
- forex: Sunday 22:00 UTC -> Friday 22:00 UTC
- stocks: NYSE regular session with optional pandas_market_calendars support
- futures: weekday sessions with daily maintenance break

Features:
- Asset type inference from broker, venue, metadata, and symbol.
- NYSE holiday fallback calendar when pandas_market_calendars is unavailable.
- US stock early-close fallback dates.
- Forex session detection: Sydney, Tokyo, London, New York, overlap.
- Futures daily maintenance break.
- Trade-window decision object with metadata.
- Compatibility aliases for older code.
"""

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional
from zoneinfo import ZoneInfo

try:
    import pandas_market_calendars as market_calendars
except Exception:  # pragma: no cover
    market_calendars = None


UTC = timezone.utc

try:
    US_EASTERN = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    try:
        import pytz

        US_EASTERN = pytz.timezone("US/Eastern")
    except Exception:
        US_EASTERN = timezone(timedelta(hours=-5))


_CRYPTO_QUOTES = {
    "USDT",
    "USDC",
    "BUSD",
    "DAI",
    "FDUSD",
    "TUSD",
    "USD",
    "BTC",
    "ETH",
    "BNB",
    "SOL",
}

_CRYPTO_BASES = {
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "DOGE",
    "ADA",
    "AVAX",
    "DOT",
    "LINK",
    "LTC",
    "BCH",
    "MATIC",
    "ARB",
    "OP",
    "ATOM",
    "NEAR",
    "APT",
    "SUI",
}

_FX_CODES = {
    "AUD",
    "CAD",
    "CHF",
    "CNH",
    "CNY",
    "EUR",
    "GBP",
    "HKD",
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
    "coinbaseadvanced": "crypto",
    "coinbase_advanced": "crypto",
    "cme": "futures",
    "fxcm": "forex",
    "interactivebrokers": "stocks",
    "ibkr": "stocks",
    "kraken": "crypto",
    "kucoin": "crypto",
    "oanda": "forex",
    "okx": "crypto",
    "schwab": "stocks",
    "tradovate": "futures",
}

_ASSET_ALIASES = {
    "crypto": "crypto",
    "cryptocurrency": "crypto",
    "coin": "crypto",
    "coins": "crypto",
    "forex": "forex",
    "fx": "forex",
    "currency": "forex",
    "currencies": "forex",
    "stock": "stocks",
    "stocks": "stocks",
    "equity": "stocks",
    "equities": "stocks",
    "share": "stocks",
    "shares": "stocks",
    "future": "futures",
    "futures": "futures",
    "derivative": "futures",
    "derivatives": "futures",
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


@lru_cache(maxsize=128)
def _nyse_fallback_holidays(year: int) -> frozenset[date]:
    """Approximate NYSE full-day holidays.

    pandas_market_calendars is preferred when installed. This fallback covers
    the main modern NYSE holidays.
    """
    holidays = {
        _observed_holiday(date(year, 1, 1)),              # New Year's Day
        _nth_weekday_of_month(year, 1, 0, 3),             # MLK Day
        _nth_weekday_of_month(year, 2, 0, 3),             # Presidents Day
        _easter_sunday(year) - timedelta(days=2),         # Good Friday
        _last_weekday_of_month(year, 5, 0),               # Memorial Day
        _observed_holiday(date(year, 6, 19)),             # Juneteenth
        _observed_holiday(date(year, 7, 4)),              # Independence Day
        _nth_weekday_of_month(year, 9, 0, 1),             # Labor Day
        _nth_weekday_of_month(year, 11, 3, 4),            # Thanksgiving
        _observed_holiday(date(year, 12, 25)),            # Christmas
    }
    return frozenset(holidays)


@lru_cache(maxsize=128)
def _nyse_fallback_early_close_time(year: int, session_date: date) -> time | None:
    """Approximate NYSE early close dates.

    Early-close rule of thumb:
    - Day after Thanksgiving
    - Christmas Eve when it falls on a weekday
    - July 3 when July 4 falls on a weekday after it / common observance cases

    pandas_market_calendars remains the authoritative path when installed.
    """
    thanksgiving = _nth_weekday_of_month(year, 11, 3, 4)
    day_after_thanksgiving = thanksgiving + timedelta(days=1)

    early_close_dates = {day_after_thanksgiving}

    christmas_eve = date(year, 12, 24)
    if christmas_eve.weekday() < 5:
        early_close_dates.add(christmas_eve)

    july_third = date(year, 7, 3)
    if july_third.weekday() < 5:
        early_close_dates.add(july_third)

    if session_date in early_close_dates:
        return time(13, 0)

    return None


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
    next_open: datetime | None = None
    next_close: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evaluated_at"] = self.evaluated_at.isoformat()
        payload["next_open"] = self.next_open.isoformat(
        ) if self.next_open else None
        payload["next_close"] = self.next_close.isoformat(
        ) if self.next_close else None
        return payload

    def to_dict(self) -> dict[str, Any]:
        return self.to_metadata()


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
        self._nyse = market_calendars.get_calendar(
            "NYSE") if market_calendars is not None else None
        self._nyse_schedule_cache: dict[date,
                                        tuple[datetime, datetime] | None] = {}

        if self._nyse is None:
            self.logger.info(
                "pandas_market_calendars unavailable; using NYSE fallback calendar."
            )

    # ------------------------------------------------------------------
    # Asset inference
    # ------------------------------------------------------------------

    def normalize_asset_type(self, asset_type: str | None) -> str:
        fallback = getattr(self, "default_asset_type", "crypto")
        normalized = str(asset_type or fallback or "crypto").strip().lower()
        return _ASSET_ALIASES.get(normalized, normalized or "crypto")

    def infer_asset_type(
        self,
        asset_type: str | None = None,
        *,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        metadata = metadata or {}

        venue = str(
            metadata.get("exchange")
            or metadata.get("venue")
            or metadata.get("broker")
            or metadata.get("broker_name")
            or ""
        ).strip().lower()

        candidates = (
            asset_type,
            metadata.get("asset_type"),
            metadata.get("market_type"),
            metadata.get("exchange_type"),
            metadata.get("broker_type"),
            _VENUE_TO_ASSET_TYPE.get(venue),
        )

        for candidate in candidates:
            if candidate is None or not str(candidate).strip():
                continue
            normalized = self.normalize_asset_type(str(candidate))
            if normalized in {"crypto", "forex", "stocks", "futures"}:
                return normalized

        raw_symbol = str(symbol or metadata.get(
            "symbol") or "").strip().upper()
        raw_symbol = raw_symbol.replace("-", "/")

        if ":" in raw_symbol:
            left, settlement = raw_symbol.split(":", 1)
            raw_symbol = left
            settlement = settlement.strip().upper()
            if settlement in _CRYPTO_QUOTES:
                return "crypto"

        if raw_symbol.endswith("PERP") or "PERP/" in raw_symbol:
            return "crypto"

        if "/" in raw_symbol:
            base, quote = raw_symbol.split("/", 1)
            base = base.strip().upper()
            quote = quote.strip().upper()

            if base in _FX_CODES and quote in _FX_CODES:
                return "forex"

            if quote in _CRYPTO_QUOTES or base in _CRYPTO_BASES:
                return "crypto"

        if "_" in raw_symbol:
            base, quote = raw_symbol.split("_", 1)
            base = base.strip().upper()
            quote = quote.strip().upper()

            if base in _FX_CODES and quote in _FX_CODES:
                return "forex"

            if quote in _CRYPTO_QUOTES or base in _CRYPTO_BASES:
                return "crypto"

        if raw_symbol.startswith(("/", "ES", "NQ", "YM", "RTY", "CL", "GC", "SI")):
            return "futures"

        if raw_symbol.isalpha() and 1 <= len(raw_symbol) <= 5:
            return "stocks"

        return self.default_asset_type

    # ------------------------------------------------------------------
    # Market open checks
    # ------------------------------------------------------------------

    def is_crypto_market_open(self, *, now: datetime | None = None) -> bool:
        _ = now
        return True

    def is_forex_market_open(self, *, now: datetime | None = None) -> bool:
        current = _coerce_datetime(now)
        weekday = current.weekday()
        current_time = current.time()

        # Saturday closed.
        if weekday == 5:
            return False

        # Sunday opens around 22:00 UTC.
        if weekday == 6:
            return current_time >= time(22, 0)

        # Friday closes around 22:00 UTC.
        if weekday == 4:
            return current_time < time(22, 0)

        return True

    def is_futures_market_open(self, *, now: datetime | None = None) -> bool:
        current = _coerce_datetime(now)
        weekday = current.weekday()
        current_time = current.time()

        # Simplified CME-style continuous session:
        # Sunday 23:00 UTC to Friday 22:00 UTC, with daily 22:00-23:00 UTC break.
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

    def is_market_open(
        self,
        asset_type: str | None,
        *,
        now: datetime | None = None,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        normalized = self.infer_asset_type(
            asset_type, symbol=symbol, metadata=metadata)
        current = _coerce_datetime(now)

        if normalized == "crypto":
            return self.is_crypto_market_open(now=current)

        if normalized == "forex":
            return self.is_forex_market_open(now=current)

        if normalized == "stocks":
            return self.is_stock_market_open(now=current)

        if normalized == "futures":
            return self.is_futures_market_open(now=current)

        self.logger.warning(
            "Unknown asset_type=%s; defaulting to closed market behavior.",
            normalized,
        )
        return False

    # ------------------------------------------------------------------
    # Session labels
    # ------------------------------------------------------------------

    def get_forex_session(self, *, now: datetime | None = None) -> str:
        current = _coerce_datetime(now)

        if not self.is_forex_market_open(now=current):
            return "inactive"

        current_time = current.time()

        sydney_active = current_time >= time(
            21, 0) or current_time < time(6, 0)
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

    def get_session(
        self,
        asset_type: str | None = None,
        *,
        now: datetime | None = None,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        current = _coerce_datetime(now)
        normalized = self.infer_asset_type(
            asset_type, symbol=symbol, metadata=metadata)
        market_open = self.is_market_open(
            normalized, now=current, symbol=symbol, metadata=metadata)

        if normalized == "forex":
            return self.get_forex_session(now=current)

        if normalized == "stocks":
            return "regular" if market_open else "closed"

        if normalized == "crypto":
            return "continuous"

        if normalized == "futures":
            return "extended" if market_open else "maintenance"

        return "unknown"

    def is_high_liquidity_session(
        self,
        *,
        now: datetime | None = None,
        asset_type: str | None = "forex",
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        normalized = self.infer_asset_type(
            asset_type, symbol=symbol, metadata=metadata)

        if normalized == "forex":
            return self.get_forex_session(now=now) in {"london", "new_york", "overlap"}

        if normalized == "stocks":
            current_utc = _coerce_datetime(now)
            current_et = current_utc.astimezone(US_EASTERN)
            current_time = current_et.time()
            return time(9, 45) <= current_time <= time(15, 45) and self.is_stock_market_open(now=current_utc)

        if normalized == "crypto":
            return True

        if normalized == "futures":
            return self.is_futures_market_open(now=now)

        return False

    # ------------------------------------------------------------------
    # Next open / close helpers
    # ------------------------------------------------------------------

    def next_stock_open_close(self, *, now: datetime | None = None) -> tuple[datetime | None, datetime | None]:
        current = _coerce_datetime(now)
        current_et = current.astimezone(US_EASTERN)

        for offset in range(0, 14):
            candidate_date = current_et.date() + timedelta(days=offset)
            session = self._get_nyse_session(candidate_date)

            if session is None:
                continue

            open_utc, close_utc = session

            if current < open_utc:
                return open_utc, close_utc

            if open_utc <= current < close_utc:
                return open_utc, close_utc

        return None, None

    def next_forex_open_close(self, *, now: datetime | None = None) -> tuple[datetime | None, datetime | None]:
        current = _coerce_datetime(now)

        # Current week's Friday close at 22:00 UTC.
        days_until_friday = (4 - current.weekday()) % 7
        friday_close_date = current.date() + timedelta(days=days_until_friday)
        close_utc = datetime.combine(
            friday_close_date, time(22, 0), tzinfo=UTC)

        if self.is_forex_market_open(now=current) and current < close_utc:
            return current, close_utc

        # Next Sunday 22:00 UTC.
        days_until_sunday = (6 - current.weekday()) % 7
        if days_until_sunday == 0 and current.time() >= time(22, 0):
            days_until_sunday = 7

        sunday_open_date = current.date() + timedelta(days=days_until_sunday)
        open_utc = datetime.combine(sunday_open_date, time(22, 0), tzinfo=UTC)
        next_friday_close = datetime.combine(
            open_utc.date() + timedelta(days=5), time(22, 0), tzinfo=UTC)

        return open_utc, next_friday_close

    def next_futures_open_close(self, *, now: datetime | None = None) -> tuple[datetime | None, datetime | None]:
        current = _coerce_datetime(now)

        if self.is_futures_market_open(now=current):
            daily_close = datetime.combine(
                current.date(), time(22, 0), tzinfo=UTC)
            if current < daily_close:
                return current, daily_close

            next_close = datetime.combine(
                current.date() + timedelta(days=1), time(22, 0), tzinfo=UTC)
            return current, next_close

        probe = current
        for _ in range(0, 14 * 24):
            probe += timedelta(hours=1)
            if self.is_futures_market_open(now=probe):
                daily_close = datetime.combine(
                    probe.date(), time(22, 0), tzinfo=UTC)
                return probe, daily_close

        return None, None

    def next_open_close(
        self,
        asset_type: str | None = None,
        *,
        now: datetime | None = None,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[datetime | None, datetime | None]:
        current = _coerce_datetime(now)
        normalized = self.infer_asset_type(
            asset_type, symbol=symbol, metadata=metadata)

        if normalized == "crypto":
            return current, None

        if normalized == "forex":
            return self.next_forex_open_close(now=current)

        if normalized == "stocks":
            return self.next_stock_open_close(now=current)

        if normalized == "futures":
            return self.next_futures_open_close(now=current)

        return None, None

    # ------------------------------------------------------------------
    # Trade window evaluation
    # ------------------------------------------------------------------

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
        normalized = self.infer_asset_type(
            asset_type, symbol=symbol, metadata=metadata)
        market_open = self.is_market_open(
            normalized, now=current, symbol=symbol, metadata=metadata)
        session = self.get_session(
            normalized, now=current, symbol=symbol, metadata=metadata)

        high_liquidity: bool | None = None
        if normalized in {"forex", "stocks", "crypto", "futures"}:
            high_liquidity = self.is_high_liquidity_session(
                now=current,
                asset_type=normalized,
                symbol=symbol,
                metadata=metadata,
            )

        next_open, next_close = self.next_open_close(
            normalized,
            now=current,
            symbol=symbol,
            metadata=metadata,
        )

        trade_allowed = market_open

        if trade_allowed and normalized == "forex" and require_high_liquidity and not bool(high_liquidity):
            trade_allowed = False

        if not market_open:
            reason = self._closed_reason(normalized)
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
            next_open=next_open,
            next_close=next_close,
            metadata={
                "require_high_liquidity": require_high_liquidity,
                "default_asset_type": self.default_asset_type,
                "source": "pandas_market_calendars" if self._nyse is not None else "fallback",
            },
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

    def _closed_reason(self, normalized: str) -> str:
        if normalized == "stocks":
            return "stock market is closed due to regular hours, weekend, or holiday."

        if normalized == "forex":
            return "forex market is closed outside the Sunday 22:00 UTC to Friday 22:00 UTC window."

        if normalized == "futures":
            return "futures market is in a maintenance or weekend closure window."

        return f"{normalized} market is closed."

    # ------------------------------------------------------------------
    # NYSE calendar
    # ------------------------------------------------------------------

    def _get_nyse_session(self, session_date: date) -> tuple[datetime, datetime] | None:
        if session_date in self._nyse_schedule_cache:
            return self._nyse_schedule_cache[session_date]

        if self._nyse is not None:
            schedule = self._nyse.schedule(
                start_date=session_date.isoformat(),
                end_date=session_date.isoformat(),
            )

            if schedule.empty:
                self._nyse_schedule_cache[session_date] = None
                return None

            row = schedule.iloc[0]
            market_open = row["market_open"].to_pydatetime().astimezone(UTC)
            market_close = row["market_close"].to_pydatetime().astimezone(UTC)
            self._nyse_schedule_cache[session_date] = (
                market_open, market_close)
            return self._nyse_schedule_cache[session_date]

        if session_date.weekday() >= 5:
            self._nyse_schedule_cache[session_date] = None
            return None

        if session_date in _nyse_fallback_holidays(session_date.year):
            self._nyse_schedule_cache[session_date] = None
            return None

        open_et = _eastern_datetime(session_date, time(9, 30))

        early_close_time = _nyse_fallback_early_close_time(
            session_date.year, session_date)
        close_et = _eastern_datetime(
            session_date, early_close_time or time(16, 0))

        self._nyse_schedule_cache[session_date] = (
            open_et.astimezone(UTC),
            close_et.astimezone(UTC),
        )

        return self._nyse_schedule_cache[session_date]

    # ------------------------------------------------------------------
    # Compatibility aliases
    # ------------------------------------------------------------------

    def can_trade(
        self,
        *,
        asset_type: str | None = None,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        require_high_liquidity: bool = False,
    ) -> bool:
        return self.evaluate_trade_window(
            asset_type=asset_type,
            symbol=symbol,
            metadata=metadata,
            now=now,
            require_high_liquidity=require_high_liquidity,
        ).trade_allowed

    def decision_metadata(
        self,
        *,
        asset_type: str | None = None,
        symbol: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        require_high_liquidity: bool = False,
    ) -> dict[str, Any]:
        return self.evaluate_trade_window(
            asset_type=asset_type,
            symbol=symbol,
            metadata=metadata,
            now=now,
            require_high_liquidity=require_high_liquidity,
        ).to_metadata()
