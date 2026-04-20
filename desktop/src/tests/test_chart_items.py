import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.chart.chart_items import CandlestickItem


def test_candlestick_item_renders_relative_to_local_time_origin():
    first_timestamp = 1710802800.0
    candles = [
        [first_timestamp, 68.5, 68.77, 68.5, 68.99],
        [first_timestamp + 3600.0, 68.77, 69.20, 68.70, 69.40],
        [first_timestamp + 7200.0, 69.20, 69.05, 68.95, 69.45],
    ]

    item = CandlestickItem(candles, body_width=2304.0)

    rect = item.boundingRect()

    assert item.pos().x() == first_timestamp
    assert rect.left() < 0.0
    assert rect.right() < 15000.0
    assert rect.width() < 15000.0
