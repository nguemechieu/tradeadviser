from broker.amp_broker import AMPFuturesBroker
from broker.base_broker import BaseBroker, BaseDerivativeBroker
from broker.ibkr_broker import IBKRBroker
from broker.schwab.broker import SchwabBroker
from broker.tdameritrade_broker import TDAmeritradeBroker
from broker.tradovate_broker import TradovateBroker

# Broker classification system
from broker.broker_classification import (
    AssetClass,
    MarketType,
    VenueType,
    BrokerProfile,
    BROKER_PROFILES,
    get_broker_profile,
    get_risk_engine_key,
    select_brokers,
    validate_broker_for_trade,
)
from broker.broker_selector import (
    BrokerSelector,
    BrokerValidator,
    route_broker_for_trade,
)

try:  # pragma: no cover - optional in minimal test environments
    from broker.coinbase_futures import CoinbaseFuturesBroker
except Exception:  # pragma: no cover - optional in stripped test environments
    CoinbaseFuturesBroker = None

try:  # pragma: no cover - optional dependency in stripped test environments
    from broker.binance_futures import BinanceFuturesBroker
except Exception:  # pragma: no cover - optional dependency in stripped test environments
    BinanceFuturesBroker = None

try:  # pragma: no cover - optional dependency in stripped test environments
    from broker.bybit import BybitBroker
except Exception:  # pragma: no cover - optional dependency in stripped test environments
    BybitBroker = None

try:  # pragma: no cover - optional dependency in stripped test environments
    from broker.solana_broker import SolanaBroker
except Exception:  # pragma: no cover - optional dependency in stripped test environments
    SolanaBroker = None

__all__ = [
    # Existing brokers
    "AMPFuturesBroker",
    "BaseBroker",
    "BaseDerivativeBroker",
    "IBKRBroker",
    "SchwabBroker",
    "TDAmeritradeBroker",
    "TradovateBroker",
    # Broker classification system
    "AssetClass",
    "MarketType",
    "VenueType",
    "BrokerProfile",
    "BROKER_PROFILES",
    "get_broker_profile",
    "get_risk_engine_key",
    "select_brokers",
    "validate_broker_for_trade",
    "BrokerSelector",
    "BrokerValidator",
    "route_broker_for_trade",
]

if CoinbaseFuturesBroker is not None:
    __all__.append("CoinbaseFuturesBroker")

if BinanceFuturesBroker is not None:
    __all__.append("BinanceFuturesBroker")

if BybitBroker is not None:
    __all__.append("BybitBroker")

if SolanaBroker is not None:
    __all__.append("SolanaBroker")
