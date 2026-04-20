from types import SimpleNamespace

import pytest

from broker.ccxt_broker import CCXTBroker


def test_ccxt_broker_requires_exchange_name():
    with pytest.raises(ValueError):
        CCXTBroker(SimpleNamespace(exchange=None))


def test_ccxt_broker_stores_exchange_name_from_config():
    broker = CCXTBroker(SimpleNamespace(exchange="binance", api_key=None, secret=None, mode="live"))
    assert broker.exchange_name == "binance"
