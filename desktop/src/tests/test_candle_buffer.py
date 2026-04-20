import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data.candle_buffer import CandleBuffer


def test_candle_buffer_parses_millisecond_timestamps():
    buffer = CandleBuffer()
    buffer.update(
        "XLM/USDT",
        {
            "timestamp": 1710000000000,
            "open": 0.10,
            "high": 0.12,
            "low": 0.09,
            "close": 0.11,
            "volume": 1000,
        },
    )

    df = buffer.get("XLM/USDT")

    assert str(df["timestamp"].dtype).startswith("datetime64")
    assert float(df.iloc[0]["close"]) == 0.11


def test_candle_buffer_parses_iso_timestamps():
    buffer = CandleBuffer()
    buffer.update(
        "XLM/USDT",
        {
            "timestamp": "2026-03-10T06:47:52.242790+00:00",
            "open": 0.10,
            "high": 0.12,
            "low": 0.09,
            "close": 0.11,
            "volume": 1000,
        },
    )

    df = buffer.get("XLM/USDT")

    assert str(df["timestamp"].dtype).startswith("datetime64")
    assert float(df.iloc[0]["close"]) == 0.11
