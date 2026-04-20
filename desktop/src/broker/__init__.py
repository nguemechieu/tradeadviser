from broker.amp_broker import AMPFuturesBroker
from broker.base_broker import BaseBroker, BaseDerivativeBroker
from broker.ibkr_broker import IBKRBroker
from broker.schwab.broker import SchwabBroker
from broker.tdameritrade_broker import TDAmeritradeBroker
from broker.tradovate_broker import TradovateBroker

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
    "AMPFuturesBroker",
    "BaseBroker",
    "BaseDerivativeBroker",
    "IBKRBroker",
    "SchwabBroker",
    "TDAmeritradeBroker",
    "TradovateBroker",
]

if CoinbaseFuturesBroker is not None:
    __all__.append("CoinbaseFuturesBroker")

if BinanceFuturesBroker is not None:
    __all__.append("BinanceFuturesBroker")

if BybitBroker is not None:
    __all__.append("BybitBroker")

if SolanaBroker is not None:
    __all__.append("SolanaBroker")
