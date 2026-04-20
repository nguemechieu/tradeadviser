import asyncio

from quant.data_hub import QuantDataHub
from quant.data_models import DatasetRequest


class DummyController:
    def __init__(self):
        self.saved = []

    async def _safe_fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        base = 1700000000000
        return [
            [base + i * 3600000, 100 + i, 101 + i, 99 + i, 100.5 + i, 10 + i]
            for i in range(min(limit, 12))
        ]

    async def _persist_candles_to_db(self, symbol, timeframe, candles):
        self.saved.append((symbol, timeframe, len(candles)))
        return len(candles)

    def _active_exchange_code(self):
        return "paper"


def test_quant_data_hub_builds_dataset_from_controller():
    hub = QuantDataHub(controller=DummyController())

    snapshot = asyncio.run(
        hub.get_symbol_dataset(DatasetRequest(symbol="BTC/USDT", timeframe="1h", limit=10))
    )

    assert snapshot.symbol == "BTC/USDT"
    assert snapshot.timeframe == "1h"
    assert snapshot.source == "live_controller"
    assert snapshot.rows == 10
    assert not snapshot.empty
    assert snapshot.metadata["feature_version"] == "quant-v1"
