import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.news_service import NewsService


def test_news_service_builds_buy_bias_from_recent_positive_headlines():
    service = NewsService(enabled=True)
    now = datetime.now(timezone.utc)
    events = [
        {
            "title": "Bitcoin ETF approval drives strong rally",
            "summary": "Markets break out on bullish adoption news",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "sentiment_score": 0.9,
            "impact": 1.5,
        },
        {
            "title": "Institutions expand crypto allocation",
            "summary": "",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "sentiment_score": 0.6,
            "impact": 1.0,
        },
    ]

    bias = service.summarize_news_bias(events)

    assert bias["direction"] == "buy"
    assert bias["score"] > 0
    assert bias["confidence"] > 0


def test_news_service_returns_neutral_when_no_recent_events():
    service = NewsService(enabled=True)
    old_event_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    events = [
        {
            "title": "Old headline",
            "summary": "",
            "timestamp": old_event_time,
            "sentiment_score": -0.5,
            "impact": 1.0,
        }
    ]

    bias = service.summarize_news_bias(events, max_age_hours=12)

    assert bias["direction"] == "neutral"
    assert bias["score"] == 0.0
