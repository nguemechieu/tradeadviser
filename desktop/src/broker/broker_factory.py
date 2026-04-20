from __future__ import annotations

import importlib

from config.config_validator import ConfigValidator


BROKER_REGISTRY = {
    "crypto": "broker.ccxt_broker:CCXTBroker",
    "forex": "broker.oanda_broker:OandaBroker",
    "stocks": "broker.alpaca_broker:AlpacaBroker",
    "options": "broker.schwab.broker:SchwabBroker",
    "futures": "broker.ibkr_broker:IBKRBroker",
    "derivatives": "broker.ibkr_broker:IBKRBroker",
    "paper": "broker.paper_broker:PaperBroker",
}

EXCHANGE_REGISTRY = {
    "alpaca": "broker.alpaca_broker:AlpacaBroker",
    "amp": "broker.amp_broker:AMPFuturesBroker",
    "ampfutures": "broker.amp_broker:AMPFuturesBroker",
    "coinbase_futures": "broker.coinbase_futures.client:CoinbaseFuturesBroker",
    "coinbasefutures": "broker.coinbase_futures.client:CoinbaseFuturesBroker",
    "coinbase-advanced-futures": "broker.coinbase_futures.client:CoinbaseFuturesBroker",
    "binance_futures": "broker.binance_futures.client:BinanceFuturesBroker",
    "binancefutures": "broker.binance_futures.client:BinanceFuturesBroker",
    "bybit_futures": "broker.bybit.client:BybitBroker",
    "bybitfutures": "broker.bybit.client:BybitBroker",
    "ib": "broker.ibkr_broker:IBKRBroker",
    "ibkr": "broker.ibkr_broker:IBKRBroker",
    "interactivebrokers": "broker.ibkr_broker:IBKRBroker",
    "interactive_brokers": "broker.ibkr_broker:IBKRBroker",
    "oanda": "broker.oanda_broker:OandaBroker",
    "paper": "broker.paper_broker:PaperBroker",
    "schwab": "broker.schwab.broker:SchwabBroker",
    "solana": "broker.solana_broker:SolanaBroker",
    "stellar": "broker.stellar_broker:StellarBroker",
    "tdameritrade": "broker.tdameritrade_broker:TDAmeritradeBroker",
    "tradovate": "broker.tradovate_broker:TradovateBroker",
}

US_REGION_CODES = {"us", "usa", "united_states", "united states"}

# Exposed broker symbols allow tests to monkeypatch dedicated broker routes
# without eagerly importing every optional broker implementation.
CCXTBroker = None
OandaBroker = None
AlpacaBroker = None
SchwabBroker = None
IBKRBroker = None
PaperBroker = None
AMPFuturesBroker = None
SolanaBroker = None
StellarBroker = None
TDAmeritradeBroker = None
TradovateBroker = None
CoinbaseFuturesBroker = None
BinanceFuturesBroker = None
BybitBroker = None


def _load_broker_class(target: str):
    module_name, class_name = target.split(":", 1)
    existing = globals().get(class_name)
    if existing is not None:
        return existing
    module = importlib.import_module(module_name)
    broker_class = getattr(module, class_name)
    globals()[class_name] = broker_class
    return broker_class


def _normalized_customer_region(broker_cfg):
    if broker_cfg is None:
        return ""

    raw = getattr(broker_cfg, "customer_region", None)
    if raw is None:
        options = getattr(broker_cfg, "options", None) or {}
        raw = options.get("customer_region")

    return str(raw or "").strip().lower()


def _validate_exchange_jurisdiction(broker_cfg):
    if broker_cfg is None:
        return

    broker_type = str(getattr(broker_cfg, "type", "") or "").strip().lower()
    exchange = str(getattr(broker_cfg, "exchange", "") or "").strip().lower()
    region = _normalized_customer_region(broker_cfg)

    if broker_type != "crypto" or exchange not in {"binance", "binanceus"}:
        return

    is_us_customer = region in US_REGION_CODES
    if exchange == "binance" and is_us_customer:
        raise ValueError("Binance.com is not available for US customers. Use Binance US instead.")
    if exchange == "binanceus" and region and not is_us_customer:
        raise ValueError("Binance US is only available for US customers. Use Binance instead.")


class BrokerFactory:
    @staticmethod
    def create(config):
        ConfigValidator.validate(config)

        broker_cfg = config.broker
        _validate_exchange_jurisdiction(broker_cfg)

        normalized_exchange = str(getattr(broker_cfg, "exchange", "") or "").strip().lower()
        normalized_type = str(getattr(broker_cfg, "type", "") or "").strip().lower()

        if normalized_exchange == "coinbase" and normalized_type in {"future", "futures", "derivative", "derivatives"}:
            target = "broker.coinbase_futures.client:CoinbaseFuturesBroker"
        elif normalized_exchange == "binance" and normalized_type in {"future", "futures", "derivative", "derivatives"}:
            target = "broker.binance_futures.client:BinanceFuturesBroker"
        elif normalized_exchange == "bybit" and normalized_type in {"future", "futures", "derivative", "derivatives"}:
            target = "broker.bybit.client:BybitBroker"
        else:
            target = EXCHANGE_REGISTRY.get(normalized_exchange) or BROKER_REGISTRY.get(normalized_type)
        if target is None:
            raise ValueError(
                f"Unsupported broker configuration: type={broker_cfg.type} exchange={broker_cfg.exchange}"
            )

        broker_class = _load_broker_class(target)
        return broker_class(broker_cfg)
