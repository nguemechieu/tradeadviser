import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.amp_broker import AMPFuturesBroker
from broker.broker_factory import BrokerFactory
from broker.ibkr_broker import IBKRBroker
from broker.tdameritrade_broker import TDAmeritradeBroker
from broker.tradovate_broker import TradovateBroker
from config.config import AppConfig, BrokerConfig, RiskConfig, SystemConfig
from engines.futures_engine import FuturesEngine
from engines.options_engine import OptionsEngine
from engines.risk_engine import RiskEngine
from execution.execution_manager import ExecutionManager
from execution.order_router import OrderRouter
from models.instrument import Instrument, InstrumentType, OptionRight
from models.position import Position


class FakeDerivativesBroker:
    def __init__(self, name, supported_types):
        self.exchange_name = name
        self.supported_types = set(supported_types)
        self.placed_orders = []

    def supports_instrument_type(self, instrument_type):
        return instrument_type in self.supported_types

    async def place_order(self, order):
        self.placed_orders.append(dict(order))
        return {
            "id": f"{self.exchange_name}-1",
            "broker": self.exchange_name,
            "symbol": order["symbol"],
            "side": order["side"],
            "amount": order["amount"],
            "type": order["type"],
            "status": "submitted",
        }


def test_options_engine_computes_call_greeks():
    engine = OptionsEngine(risk_free_rate=0.03, default_volatility=0.22)

    greeks = engine.compute_greeks(
        underlying_price=100.0,
        strike=100.0,
        expiry=datetime.now(timezone.utc) + timedelta(days=30),
        option_type="call",
        volatility=0.2,
        contract_size=100,
    )

    assert greeks["price"] > 0
    assert greeks["delta"] > 0
    assert greeks["gamma"] > 0
    assert greeks["vega"] > 0


def test_options_engine_builds_iron_condor_order():
    engine = OptionsEngine()
    expiry = datetime.now(timezone.utc) + timedelta(days=45)

    long_put = {"symbol": "SPY240621P00460000", "type": "option", "expiry": expiry.isoformat(), "strike": 460, "option_type": "put", "underlying": "SPY"}
    short_put = {"symbol": "SPY240621P00470000", "type": "option", "expiry": expiry.isoformat(), "strike": 470, "option_type": "put", "underlying": "SPY"}
    short_call = {"symbol": "SPY240621C00530000", "type": "option", "expiry": expiry.isoformat(), "strike": 530, "option_type": "call", "underlying": "SPY"}
    long_call = {"symbol": "SPY240621C00540000", "type": "option", "expiry": expiry.isoformat(), "strike": 540, "option_type": "call", "underlying": "SPY"}

    order = engine.build_iron_condor(long_put, short_put, short_call, long_call, quantity=2, limit_price=1.35)

    assert order.symbol == "SPY"
    assert order.order_type.value == "limit"
    assert len(order.legs) == 4
    assert order.params["complex_order_strategy"] == "IRON_CONDOR"


def test_futures_engine_computes_margin_leverage_and_rollover():
    engine = FuturesEngine(default_roll_days=7)
    metadata = {
        "symbol": "ESM6",
        "multiplier": 50,
        "initial_margin": 12000,
        "maintenance_margin": 11000,
        "expiry": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    }

    assert engine.margin_required(quantity=2, metadata=metadata) == 24000
    assert engine.maintenance_margin_required(quantity=2, metadata=metadata) == 22000
    assert engine.leverage(account_equity=50000, quantity=2, price=5200, multiplier=50) > 1
    assert engine.should_roll_contract(metadata) is True


def test_risk_engine_tracks_margin_and_option_greeks():
    option_position = Position(
        symbol="SPY240621C00530000",
        quantity=2,
        instrument=Instrument(
            symbol="SPY240621C00530000",
            type=InstrumentType.OPTION,
            expiry=datetime.now(timezone.utc) + timedelta(days=30),
            strike=530,
            option_type=OptionRight.CALL,
            contract_size=100,
            underlying="SPY",
        ),
        avg_price=4.2,
        mark_price=4.5,
        delta=90,
        gamma=14,
        theta=-8,
        vega=22,
        margin_used=1200,
    )

    engine = RiskEngine(account_equity=100000, max_gamma_exposure=500, max_theta_decay_pct=0.05)
    greek_exposure = engine.option_greek_exposure([option_position])
    margin_metrics = engine.margin_usage(account_info={"equity": 100000, "margin_used": 1200})
    approved, reason = engine.validate_derivatives_order(
        {
            "symbol": "SPY240621C00530000",
            "instrument": option_position.instrument.to_dict(),
            "amount": 1,
            "price": 4.5,
            "gamma": 10,
            "theta": -3,
        },
        positions=[option_position.to_dict()],
        account_info={"equity": 100000, "margin_used": 1200},
        contract_metadata={"initial_margin": 500, "multiplier": 100},
    )

    assert greek_exposure["gamma"] == 14
    assert margin_metrics["margin_usage"] == 0.012
    assert approved is True, reason


def test_order_router_selects_derivatives_broker_from_instrument_type():
    options_broker = FakeDerivativesBroker("schwab", {"option"})
    futures_broker = FakeDerivativesBroker("ibkr", {"future"})
    router = OrderRouter({"schwab": options_broker, "ibkr": futures_broker})

    execution = asyncio.run(
        router.route(
            {
                "symbol": "ESM6",
                "side": "buy",
                "amount": 1,
                "type": "market",
                "instrument": {"symbol": "ESM6", "type": "future"},
            }
        )
    )

    assert execution["broker"] == "ibkr"
    assert futures_broker.placed_orders[0]["instrument"]["type"] == "future"
    assert not options_broker.placed_orders


def test_execution_manager_disables_spot_inventory_checks_for_options():
    broker = FakeDerivativesBroker("schwab", {"option"})
    manager = ExecutionManager(broker=broker, event_bus=type("Bus", (), {"subscribe": lambda *_args, **_kwargs: None})(), router=None)

    assert manager._uses_inventory_balance_checks(
        {
            "symbol": "SPY240621C00530000",
            "instrument": {"symbol": "SPY240621C00530000", "type": "option"},
            "instrument_type": "option",
        },
        market={},
        balance={},
    ) is False


def test_broker_factory_supports_derivatives_exchanges():
    shared_risk = RiskConfig()
    shared_system = SystemConfig()

    schwab_config = AppConfig(
        broker=BrokerConfig(
            type="options",
            exchange="schwab",
            api_key="client-id",
            password="http://127.0.0.1:8182/callback",
        ),
        risk=shared_risk,
        system=shared_system,
    )
    ibkr_config = AppConfig(broker=BrokerConfig(type="futures", exchange="ibkr"), risk=shared_risk, system=shared_system)
    amp_config = AppConfig(broker=BrokerConfig(type="futures", exchange="amp"), risk=shared_risk, system=shared_system)
    tradovate_config = AppConfig(broker=BrokerConfig(type="futures", exchange="tradovate"), risk=shared_risk, system=shared_system)

    assert isinstance(BrokerFactory.create(schwab_config), TDAmeritradeBroker)
    assert isinstance(BrokerFactory.create(ibkr_config), IBKRBroker)
    assert isinstance(BrokerFactory.create(amp_config), AMPFuturesBroker)
    assert isinstance(BrokerFactory.create(tradovate_config), TradovateBroker)
