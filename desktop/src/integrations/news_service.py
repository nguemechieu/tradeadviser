from __future__ import annotations

"""
InvestPro News Service

Responsibilities:
- Fetch RSS news for symbols/assets.
- Build better symbol-aware search queries.
- Parse RSS safely.
- Deduplicate repeated headlines.
- Score sentiment from title/summary/source.
- Estimate event impact.
- Apply recency decay.
- Summarize news into buy/sell/neutral bias.
- Support lightweight in-memory caching.
- Stay fail-safe: if news fails, return neutral/no events instead of crashing.

Important:
This service is not financial advice. It is only one input into a larger
decision/risk pipeline.
"""

import asyncio
import html
import logging
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import quote_plus
import xml.etree

import aiohttp


@dataclass(slots=True)
class NewsEvent:
    symbol: str
    title: str
    summary: str
    url: str
    source: str
    timestamp: str
    sentiment_score: float
    impact: float
    age_hours: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "timestamp": self.timestamp,
            "sentiment_score": self.sentiment_score,
            "impact": self.impact,
            "age_hours": self.age_hours,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class NewsBias:
    direction: str
    score: float
    confidence: float
    reason: str
    headline: str = ""
    event_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    average_impact: float = 0.0
    latest_timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "score": self.score,
            "confidence": self.confidence,
            "reason": self.reason,
            "headline": self.headline,
            "event_count": self.event_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "average_impact": self.average_impact,
            "latest_timestamp": self.latest_timestamp,
            "metadata": self.metadata,
        }


class NewsService:
    DEFAULT_FEED_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (compatible; InvestProNewsService/1.0; +https://investpro.local)"
    )

    POSITIVE_KEYWORDS = {
        "surge",
        "surges",
        "growth",
        "beat",
        "beats",
        "bullish",
        "approval",
        "approved",
        "upside",
        "record",
        "breakout",
        "upgrade",
        "upgraded",
        "strong",
        "rally",
        "rallies",
        "expands",
        "expansion",
        "adoption",
        "profit",
        "profits",
        "gain",
        "gains",
        "outperform",
        "optimism",
        "optimistic",
        "rebound",
        "recovery",
        "raises",
        "raised",
        "partnership",
        "launch",
        "launches",
        "inflows",
        "accumulation",
        "demand",
    }

    NEGATIVE_KEYWORDS = {
        "drop",
        "drops",
        "fall",
        "falls",
        "fell",
        "lawsuit",
        "bearish",
        "downgrade",
        "downgraded",
        "weak",
        "weakness",
        "recession",
        "selloff",
        "sell-off",
        "investigation",
        "risk",
        "risks",
        "warning",
        "loss",
        "losses",
        "miss",
        "misses",
        "cuts",
        "cut",
        "crash",
        "bankruptcy",
        "default",
        "fraud",
        "hack",
        "hacked",
        "exploit",
        "liquidation",
        "outflows",
        "ban",
        "banned",
        "probe",
        "slump",
        "plunge",
        "plunges",
        "fear",
        "volatility",
    }

    HIGH_IMPACT_KEYWORDS = {
        "fed",
        "fomc",
        "cpi",
        "inflation",
        "interest rate",
        "rate cut",
        "rate hike",
        "sec",
        "cftc",
        "earnings",
        "etf",
        "guidance",
        "payrolls",
        "nfp",
        "gdp",
        "tariff",
        "tariffs",
        "opec",
        "war",
        "sanctions",
        "recession",
        "bankruptcy",
        "default",
        "federal reserve",
        "treasury",
        "jobs report",
        "pce",
        "unemployment",
        "oil inventories",
        "halving",
        "hack",
        "exploit",
        "lawsuit",
        "approval",
    }

    NEGATION_TERMS = {
        "not",
        "no",
        "never",
        "without",
        "denies",
        "denied",
        "rejects",
        "rejected",
    }

    SYMBOL_ALIASES = {
        # Crypto
        "BTC": "Bitcoin",
        "XBT": "Bitcoin",
        "ETH": "Ethereum",
        "SOL": "Solana",
        "XRP": "Ripple XRP",
        "DOGE": "Dogecoin",
        "ADA": "Cardano",
        "BNB": "Binance Coin",
        "AVAX": "Avalanche crypto",
        "DOT": "Polkadot crypto",
        "LINK": "Chainlink crypto",
        "MATIC": "Polygon crypto",
        "LTC": "Litecoin",
        "BCH": "Bitcoin Cash",
        "USDT": "Tether",
        "USDC": "USD Coin",

        # Forex / macro
        "EUR": "Euro",
        "USD": "US Dollar",
        "GBP": "British Pound",
        "JPY": "Japanese Yen",
        "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar",
        "NZD": "New Zealand Dollar",
        "CHF": "Swiss Franc",
        "CNY": "Chinese Yuan",
        "XAU": "Gold",
        "XAG": "Silver",
        "WTI": "Crude Oil",
        "BRENT": "Brent crude",

        # ETFs / indexes
        "SPY": "S&P 500 ETF",
        "QQQ": "Nasdaq 100 ETF",
        "DIA": "Dow Jones ETF",
        "IWM": "Russell 2000 ETF",
        "VIX": "volatility index",

        # Common stocks
        "AAPL": "Apple stock",
        "MSFT": "Microsoft stock",
        "NVDA": "Nvidia stock",
        "TSLA": "Tesla stock",
        "AMZN": "Amazon stock",
        "GOOGL": "Alphabet stock",
        "GOOG": "Alphabet stock",
        "META": "Meta stock",
        "AMD": "AMD stock",
        "COIN": "Coinbase stock",
    }

    STABLE_QUOTES = {"USDT", "USD", "USDC", "BUSD", "DAI", "FDUSD", "TUSD"}

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        enabled: bool = True,
        feed_url_template: Optional[str] = None,
        *,
        request_timeout_seconds: float = 15.0,
        cache_ttl_seconds: float = 300.0,
        max_connections: int = 10,
        user_agent: Optional[str] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = bool(enabled)
        self.feed_url_template = str(
            feed_url_template or self.DEFAULT_FEED_URL).strip() or self.DEFAULT_FEED_URL
        self.request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self.max_connections = max(1, int(max_connections or 10))
        self.user_agent = str(user_agent or self.DEFAULT_USER_AGENT)

        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "NewsService":
        await self._ensure_session()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
            resolver = aiohttp.ThreadedResolver()
            connector = aiohttp.TCPConnector(
                resolver=resolver,
                family=socket.AF_INET,
                ttl_dns_cache=300,
                limit=self.max_connections,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": self.user_agent},
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # Symbol and query handling
    # ------------------------------------------------------------------

    def _clean_symbol_part(self, value: str) -> str:
        value = str(value or "").upper().strip()
        value = value.replace(":USD", "")
        value = value.replace(":USDT", "")
        value = value.replace("-PERP", "")
        value = value.replace("PERP", "") if value.endswith("PERP") else value
        value = re.sub(r"[^A-Z0-9.]", "", value)
        return value

    def _split_symbol(self, symbol: Any) -> tuple[str, str]:
        normalized = str(symbol or "").upper().strip()
        normalized = normalized.replace("-", "/")

        if ":" in normalized:
            left, settlement = normalized.split(":", 1)
            normalized = left
            settlement = self._clean_symbol_part(settlement)
        else:
            settlement = ""

        if "/" in normalized:
            base, quote = normalized.split("/", 1)
        else:
            base, quote = normalized, settlement

        base = self._clean_symbol_part(base)
        quote = self._clean_symbol_part(quote)

        if not quote and settlement:
            quote = settlement

        return base, quote

    def _alias(self, symbol_part: str) -> str:
        return self.SYMBOL_ALIASES.get(str(symbol_part or "").upper().strip(), str(symbol_part or "").upper().strip())

    def _query_for_symbol(self, symbol: Any, broker_type: Optional[str] = None) -> str:
        """Build a search query for crypto/forex/stocks/futures-like symbols."""
        base, quote = self._split_symbol(symbol)
        broker_type_normalized = str(broker_type or "").strip().lower()

        if not base:
            return ""

        base_alias = self._alias(base)
        quote_alias = self._alias(quote)

        # Forex pairs benefit from explicit pair + both currencies.
        if broker_type_normalized in {"forex", "fx", "oanda"} and quote:
            return f'"{base}{quote}" OR "{base} {quote}" OR "{base_alias}" OR "{quote_alias}" forex'

        # Perpetual/futures-style symbols.
        symbol_text = str(symbol or "").upper()
        if "PERP" in symbol_text or ":" in symbol_text:
            terms = [
                f'"{base} perpetual"',
                f'"{base_alias}"',
                f'"{base} futures"',
                f'"{base} crypto"',
            ]
            return " OR ".join(dict.fromkeys(term for term in terms if term))

        # Crypto pair.
        if quote in self.STABLE_QUOTES or broker_type_normalized in {"crypto", "ccxt", "binance", "coinbase", "kraken"}:
            terms = [
                f'"{base_alias}"',
                f'"{base} price"',
                f'"{base} crypto"',
            ]
            return " OR ".join(dict.fromkeys(term for term in terms if term))

        # Stock-like symbols.
        if broker_type_normalized in {"stock", "stocks", "equity", "alpaca"}:
            return f'"{base}" OR "{base_alias}" stock earnings'

        terms = [base, base_alias]
        if quote and quote not in self.STABLE_QUOTES:
            terms.extend([quote, quote_alias])

        return " OR ".join(dict.fromkeys(f'"{term}"' for term in terms if term))

    # ------------------------------------------------------------------
    # Text cleanup / parsing
    # ------------------------------------------------------------------

    def _strip_html(self, value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _normalize_title(self, title: str) -> str:
        title = self._strip_html(title)
        title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
        title = re.sub(r"\s+", " ", title)
        return title

    def _dedupe_key(self, title: str, url: str = "") -> str:
        text = self._normalize_title(title).lower()
        text = re.sub(r"[^a-z0-9 ]", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        if text:
            return text[:180]

        return str(url or "").strip().lower()

    def _parse_timestamp(self, raw_value: Any) -> datetime:
        if not raw_value:
            return datetime.now(timezone.utc)

        text = str(raw_value).strip()

        try:
            parsed = parsedate_to_datetime(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    def _find_text(self, item: xml.etree.ElementTree.Element, tag: str) -> str:
        value = item.findtext(tag)
        if value is not None:
            return str(value)
        return ""

    def _find_source(self, item: xml.etree.ElementTree.Element, title: str) -> str:
        source_node = item.find("source")
        if source_node is not None and source_node.text:
            return self._strip_html(source_node.text)

        # Google News often appends " - Source" to titles.
        if " - " in title:
            possible = title.rsplit(" - ", 1)[-1].strip()
            if 2 <= len(possible) <= 80:
                return possible

        return "News Feed"

    # ------------------------------------------------------------------
    # Sentiment scoring
    # ------------------------------------------------------------------

    def _contains_keyword(self, text: str, keyword: str) -> bool:
        keyword = keyword.lower().strip()
        if " " in keyword:
            return keyword in text
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None

    def _near_negation(self, text: str, keyword: str) -> bool:
        keyword = keyword.lower().strip()
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
        key_parts = keyword.split()
        first = key_parts[0] if key_parts else keyword

        for idx, word in enumerate(words):
            if word != first:
                continue

            window = words[max(0, idx - 3):idx]
            if any(term in self.NEGATION_TERMS for term in window):
                return True

        return False

    def _score_headline(self, title: str, summary: str = "", source: str = "") -> tuple[float, float, dict[str, Any]]:
        text = f"{title} {summary}".lower()

        positive_hits: list[str] = []
        negative_hits: list[str] = []
        high_impact_hits: list[str] = []

        for word in self.POSITIVE_KEYWORDS:
            if self._contains_keyword(text, word):
                if self._near_negation(text, word):
                    negative_hits.append(f"not_{word}")
                else:
                    positive_hits.append(word)

        for word in self.NEGATIVE_KEYWORDS:
            if self._contains_keyword(text, word):
                if self._near_negation(text, word):
                    positive_hits.append(f"not_{word}")
                else:
                    negative_hits.append(word)

        for word in self.HIGH_IMPACT_KEYWORDS:
            if self._contains_keyword(text, word):
                high_impact_hits.append(word)

        raw_sentiment = float(len(positive_hits) - len(negative_hits))

        if raw_sentiment > 0:
            sentiment = min(raw_sentiment / 4.0, 1.0)
        elif raw_sentiment < 0:
            sentiment = max(raw_sentiment / 4.0, -1.0)
        else:
            sentiment = 0.0

        impact = 1.0 + (0.30 * len(high_impact_hits))

        # Stronger source impact for known market-moving sources.
        source_lower = str(source or "").lower()
        if any(name in source_lower for name in {"reuters", "bloomberg", "cnbc", "wall street journal", "financial times"}):
            impact += 0.20

        impact = min(impact, 3.0)

        metadata = {
            "positive_hits": sorted(set(positive_hits)),
            "negative_hits": sorted(set(negative_hits)),
            "high_impact_hits": sorted(set(high_impact_hits)),
            "raw_sentiment": raw_sentiment,
        }

        return round(float(sentiment), 4), round(float(impact), 2), metadata

    # ------------------------------------------------------------------
    # Fetch / parse
    # ------------------------------------------------------------------

    def _cache_key(self, symbol: Any, broker_type: Optional[str], limit: int) -> str:
        return f"{str(symbol).upper().strip()}|{str(broker_type or '').lower().strip()}|{int(limit)}"

    def _get_cached(self, key: str) -> Optional[list[dict[str, Any]]]:
        if self.cache_ttl_seconds <= 0:
            return None

        cached = self._cache.get(key)
        if not cached:
            return None

        created_at, events = cached
        age = (datetime.now(timezone.utc) - created_at).total_seconds()

        if age > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None

        return list(events)

    def _set_cached(self, key: str, events: list[dict[str, Any]]) -> None:
        if self.cache_ttl_seconds <= 0:
            return

        self._cache[key] = (datetime.now(timezone.utc), list(events))

    async def fetch_symbol_news(
        self,
        symbol: Any,
        broker_type: Optional[str] = None,
        limit: int = 8,
        *,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch and score RSS news for a symbol."""
        if not self.enabled:
            return []

        limit = max(1, min(int(limit or 8), 50))
        cache_key = self._cache_key(symbol, broker_type, limit)

        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        query = self._query_for_symbol(symbol, broker_type=broker_type)
        if not query:
            return []

        session = await self._ensure_session()
        url = self.feed_url_template.format(query=quote_plus(query))

        try:
            async with self._lock:
                async with session.get(url) as response:
                    text = await response.text(errors="replace")

                    if response.status >= 400:
                        raise RuntimeError(
                            f"news feed request failed with status {response.status}")

        except Exception as exc:
            self.logger.debug("News fetch failed for %s: %s", symbol, exc)
            return []

        try:
            root = xml.etree.ElementTree.fromstring(text)
        except Exception as exc:
            self.logger.debug("News XML parse failed for %s: %s", symbol, exc)
            return []

        now = datetime.now(timezone.utc)
        events: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in root.findall(".//item"):
            raw_title = self._find_text(item, "title")
            title = self._normalize_title(raw_title)
            if not title:
                continue

            description = self._strip_html(
                self._find_text(item, "description"))
            link = self._strip_html(self._find_text(item, "link"))
            source = self._find_source(item, raw_title)

            dedupe_key = self._dedupe_key(title, link)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            timestamp = self._parse_timestamp(self._find_text(item, "pubDate"))
            age_hours = max((now - timestamp).total_seconds() / 3600.0, 0.0)

            sentiment_score, impact, scoring_metadata = self._score_headline(
                title,
                description,
                source,
            )

            event = NewsEvent(
                symbol=str(symbol or "").upper().strip(),
                title=title,
                summary=description,
                url=link,
                source=source or "News Feed",
                timestamp=timestamp.isoformat(),
                sentiment_score=sentiment_score,
                impact=impact,
                age_hours=round(float(age_hours), 4),
                metadata={
                    "query": query,
                    "scoring": scoring_metadata,
                },
            )

            events.append(event.to_dict())

        events.sort(key=lambda event: event.get("timestamp", ""), reverse=True)
        events = events[:limit]

        self._set_cached(cache_key, events)
        return events

    async def fetch_many_symbols_news(
        self,
        symbols: list[str],
        broker_type: Optional[str] = None,
        limit_per_symbol: int = 8,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch news for multiple symbols concurrently."""
        if not symbols:
            return {}

        async def _fetch_one(item: str) -> tuple[str, list[dict[str, Any]]]:
            return item, await self.fetch_symbol_news(item, broker_type=broker_type, limit=limit_per_symbol)

        results = await asyncio.gather(*[_fetch_one(symbol) for symbol in symbols], return_exceptions=True)

        output: dict[str, list[dict[str, Any]]] = {}

        for result in results:
            if isinstance(result, Exception):
                self.logger.debug("Batch news fetch item failed: %s", result)
                continue

            symbol, events = result
            output[str(symbol).upper().strip()] = events

        return output

    # ------------------------------------------------------------------
    # Bias summary
    # ------------------------------------------------------------------

    def summarize_news_bias(
        self,
        events: list[dict[str, Any]],
        max_age_hours: float = 18.0,
        *,
        buy_threshold: float = 0.20,
        sell_threshold: float = -0.20,
    ) -> dict[str, Any]:
        """Summarize scored news events into directional bias."""
        if not isinstance(events, list) or not events:
            return NewsBias(
                direction="neutral",
                score=0.0,
                confidence=0.0,
                reason="No recent news events found.",
            ).to_dict()

        now = datetime.now(timezone.utc)
        max_age_hours = max(1.0, float(max_age_hours or 18.0))

        usable_events: list[dict[str, Any]] = []
        total_score = 0.0
        impact_total = 0.0
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for event in events:
            try:
                timestamp = datetime.fromisoformat(
                    str(event.get("timestamp", "")).replace("Z", "+00:00"))
            except Exception:
                timestamp = now

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            age_hours = max((now - timestamp).total_seconds() / 3600.0, 0.0)

            if age_hours > max_age_hours:
                continue

            sentiment = self._safe_event_float(
                event.get("sentiment_score"), 0.0)
            impact = max(0.1, self._safe_event_float(event.get("impact"), 1.0))

            # Recency decay: fresh news matters more.
            decay = max(0.15, 1.0 - (age_hours / max_age_hours))

            # Score per event.
            event_score = sentiment * impact * decay

            if abs(event_score) > 0.01:
                usable_events.append(event)

            total_score += event_score
            impact_total += impact

            if sentiment > 0.05:
                positive_count += 1
            elif sentiment < -0.05:
                negative_count += 1
            else:
                neutral_count += 1

        if not usable_events:
            return NewsBias(
                direction="neutral",
                score=0.0,
                confidence=0.0,
                reason="News exists, but nothing recent has enough directional impact yet.",
                event_count=0,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
            ).to_dict()

        usable_events.sort(key=lambda event: str(
            event.get("timestamp", "")), reverse=True)

        top = usable_events[0]
        headline = str(top.get("title", "") or "")
        latest_timestamp = str(top.get("timestamp", "") or "")

        direction = "neutral"
        if total_score >= buy_threshold:
            direction = "buy"
        elif total_score <= sell_threshold:
            direction = "sell"

        # Confidence is based on score strength, event count, and agreement.
        event_count = len(usable_events)
        agreement_count = max(positive_count, negative_count, neutral_count)
        agreement_ratio = agreement_count / \
            max(positive_count + negative_count + neutral_count, 1)
        score_strength = min(abs(total_score) / max(event_count, 1), 1.0)
        confidence = min((0.65 * score_strength) +
                         (0.35 * agreement_ratio), 1.0)

        average_impact = impact_total / \
            max(positive_count + negative_count + neutral_count, 1)

        if direction == "neutral":
            reason = f"Recent headlines are mixed. Latest: {headline}" if headline else "Recent headlines are mixed."
        elif direction == "buy":
            reason = f"Recent news bias is supportive. Latest: {headline}" if headline else "Recent news bias is supportive."
        else:
            reason = f"Recent news bias is negative. Latest: {headline}" if headline else "Recent news bias is negative."

        return NewsBias(
            direction=direction,
            score=round(float(total_score), 4),
            confidence=round(float(confidence), 4),
            reason=reason,
            headline=headline,
            event_count=event_count,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            average_impact=round(float(average_impact), 4),
            latest_timestamp=latest_timestamp,
            metadata={
                "max_age_hours": max_age_hours,
                "buy_threshold": buy_threshold,
                "sell_threshold": sell_threshold,
            },
        ).to_dict()

    def _safe_event_float(self, value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)

        if number != number or number in {float("inf"), float("-inf")}:
            return float(default)

        return number

    async def fetch_and_summarize(
        self,
        symbol: Any,
        broker_type: Optional[str] = None,
        *,
        limit: int = 8,
        max_age_hours: float = 18.0,
    ) -> dict[str, Any]:
        """Convenience method: fetch news and return events + bias."""
        events = await self.fetch_symbol_news(symbol, broker_type=broker_type, limit=limit)
        bias = self.summarize_news_bias(events, max_age_hours=max_age_hours)

        return {
            "symbol": str(symbol or "").upper().strip(),
            "events": events,
            "bias": bias,
        }
