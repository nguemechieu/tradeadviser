from manager.broker_manager import BrokerManager


def test_broker_manager_routes_slash_forex_pairs_to_forex_broker():
    manager = BrokerManager()
    crypto_broker = object()
    forex_broker = object()

    manager.register_crypto(crypto_broker)
    manager.register_forex(forex_broker)

    assert manager.get_broker("EUR/USD") is forex_broker
    assert manager.get_broker("XAU/USD") is forex_broker
    assert manager.get_broker("NAS100/USD") is forex_broker
    assert manager.get_broker("EUR_USD") is forex_broker


def test_broker_manager_keeps_crypto_pairs_on_crypto_broker():
    manager = BrokerManager()
    crypto_broker = object()
    forex_broker = object()

    manager.register_crypto(crypto_broker)
    manager.register_forex(forex_broker)

    assert manager.get_broker("BTC/USDT") is crypto_broker
    assert manager.get_broker("ETH/USD") is crypto_broker


def test_broker_manager_keeps_coinbase_futures_contract_ids_on_crypto_broker():
    manager = BrokerManager()
    crypto_broker = object()
    forex_broker = object()

    manager.register_crypto(crypto_broker)
    manager.register_forex(forex_broker)

    assert manager.get_broker("SLP-20DEC30-CDE") is crypto_broker
    assert manager.get_broker("BTC-USD-20241227") is crypto_broker
