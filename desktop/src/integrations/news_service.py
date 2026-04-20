import asyncio
import socket
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import aiohttp


class NewsService:
    DEFAULT_FEED_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    POSITIVE_KEYWORDS = {
        "surge",
        "growth",
        "beat",
        "bullish",
        "approval",
        "upside",
        "record",
        "breakout",
        "upgrade",
        "strong",
        "rally",
        "expands",
        "adoption",
        "profit",
        "gain",
    }
    NEGATIVE_KEYWORDS = {
        "drop",
        "fall",
        "lawsuit",
        "bearish",
        "downgrade",
        "weak",
        "recession",
        "selloff",
        "investigation",
        "risk",
        "warning",
        "loss",
        "miss",
        "cuts",
        "crash",
        "bankruptcy",
    }
    HIGH_IMPACT_KEYWORDS = {
        "fed",
        "fomc",
        "cpi",
        "inflation",
        "interest rate",
        "sec",
        "earnings",
        "etf",
        "guidance",
        "payrolls",
        "gdp",
        "tariff",
        "opec",
    }

    def __init__(self, logger=None, enabled=True, feed_url_template=None):
        self.logger = logger
        self.enabled = bool(enabled)
        self.feed_url_template = str(feed_url_template or self.DEFAULT_FEED_URL).strip() or self.DEFAULT_FEED_URL
        self._session = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            resolver = aiohttp.ThreadedResolver()
            connector = aiohttp.TCPConnector(
                resolver=resolver,
                family=socket.AF_INET,
                ttl_dns_cache=300,
            )
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self._session

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _query_for_symbol(self, symbol, broker_type=None):
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return ""

        if "/" in normalized:
            base, quote = normalized.split("/", 1)
        else:
            base, quote = normalized, ""

        aliases = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "XRP": "Ripple",
            "DOGE": "Dogecoin",
            "ADA": "Cardano",
            "BNB": "Binance Coin",
            "EUR": "Euro",
            "USD": "US Dollar",
            "GBP": "British Pound",
            "JPY": "Japanese Yen",
            "XAU": "Gold",
            "SPY": "S&P 500",
            "QQQ": "Nasdaq",
        }

        if str(broker_type or "").lower() == "forex" and quote:
            base_term = aliases.get(base, base)
            quote_term = aliases.get(quote, quote)
            return f'"{base} {quote}" OR "{base_term}" OR "{quote_term}"'

        search_terms = [base]
        if quote and quote not in {"USDT", "USD", "USDC", "BUSD"}:
            search_terms.append(quote)
        alias = aliases.get(base)
        if alias:
            search_terms.append(alias)
        return " OR ".join(dict.fromkeys(term for term in search_terms if term))

    def _score_headline(self, title, summary=""):
        text = f"{title} {summary}".lower()
        positive_hits = sum(1 for word in self.POSITIVE_KEYWORDS if word in text)
        negative_hits = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text)
        impact = 1.0 + (0.35 * sum(1 for word in self.HIGH_IMPACT_KEYWORDS if word in text))
        sentiment = float(positive_hits - negative_hits)
        if sentiment > 0:
            sentiment = min(sentiment / 3.0, 1.0)
        elif sentiment < 0:
            sentiment = max(sentiment / 3.0, -1.0)
        return sentiment, impact

    def _parse_timestamp(self, raw_value):
        if not raw_value:
            return datetime.now(timezone.utc)
        try:
            parsed = parsedate_to_datetime(str(raw_value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    async def fetch_symbol_news(self, symbol, broker_type=None, limit=8):
        if not self.enabled:
            return []

        query = self._query_for_symbol(symbol, broker_type=broker_type)
        if not query:
            return []

        session = await self._ensure_session()
        url = self.feed_url_template.format(query=quote_plus(query))
        try:
            async with session.get(url, headers={"User-Agent": "SopotekTradingAI/1.0"}) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"news feed request failed with status {response.status}")
        except Exception as exc:
            if self.logger is not None:
                self.logger.debug("News fetch failed for %s: %s", symbol, exc)
            return []

        try:
            root = ET.fromstring(text)
        except Exception as exc:
            if self.logger is not None:
                self.logger.debug("News XML parse failed for %s: %s", symbol, exc)
            return []

        events = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            description = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = ""
            source_node = item.find("source")
            if source_node is not None and source_node.text:
                source = source_node.text.strip()
            timestamp = self._parse_timestamp(item.findtext("pubDate"))
            sentiment_score, impact = self._score_headline(title, description)
            events.append(
                {
                    "symbol": str(symbol or "").upper().strip(),
                    "title": title,
                    "summary": description,
                    "url": link,
                    "source": source or "News Feed",
                    "timestamp": timestamp.isoformat(),
                    "sentiment_score": sentiment_score,
                    "impact": round(float(impact), 2),
                }
            )

        events.sort(key=lambda event: event.get("timestamp", ""), reverse=True)
        return events[: max(1, int(limit or 8))]

    def summarize_news_bias(self, events, max_age_hours=18):
        if not isinstance(events, list) or not events:
            return {
                "direction": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "reason": "No recent news events found.",
                "headline": "",
            }

        now = datetime.now(timezone.utc)
        freshest = []
        total_score = 0.0
        for event in events:
            try:
                timestamp = datetime.fromisoformat(str(event.get("timestamp", "")).replace("Z", "+00:00"))
            except Exception:
                timestamp = now
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            age_hours = max((now - timestamp).total_seconds() / 3600.0, 0.0)
            if age_hours > max_age_hours:
                continue
            decay = max(0.2, 1.0 - (age_hours / max_age_hours))
            score = float(event.get("sentiment_score", 0.0) or 0.0) * float(event.get("impact", 1.0) or 1.0) * decay
            if abs(score) > 0.01:
                freshest.append(event)
            total_score += score

        if not freshest:
            return {
                "direction": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "reason": "News exists, but nothing recent has enough impact yet.",
                "headline": "",
            }

        top = freshest[0]
        direction = "neutral"
        if total_score > 0.2:
            direction = "buy"
        elif total_score < -0.2:
            direction = "sell"

        confidence = min(abs(total_score) / max(len(freshest), 1), 1.0)
        headline = str(top.get("title", "") or "")
        if direction == "neutral":
            reason = f"Recent headlines are mixed. Latest: {headline}" if headline else "Recent headlines are mixed."
        elif direction == "buy":
            reason = f"Recent news bias is supportive. Latest: {headline}" if headline else "Recent news bias is supportive."
        else:
            reason = f"Recent news bias is negative. Latest: {headline}" if headline else "Recent news bias is negative."

        return {
            "direction": direction,
            "score": round(float(total_score), 4),
            "confidence": round(float(confidence), 4),
            "reason": reason,
            "headline": headline,
        }
