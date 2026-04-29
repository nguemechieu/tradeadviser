from __future__ import annotations

from shared.commands.trading_commands import PlaceOrderCommand
from shared.contracts.base import ApiResponseEnvelope, BrokerIdentifier
from shared.contracts.market import FeatureSnapshot, SymbolSnapshot
from shared.contracts.session import BrokerSessionSummary, SessionState
from shared.contracts.trading import ExecutionRequest, ExecutionResult
from shared.enums.common import BrokerKind, ExecutionStatus, OrderSide, OrderType, SessionStatus
from shared.events.base import ServerEventEnvelope


def test_server_event_envelope_round_trip() -> None:
    event = ServerEventEnvelope[dict](
        event_type="market.snapshot",
        sequence=42,
        payload={"symbol": "BTC/USD", "last_price": 84210.5},
    )

    encoded = event.model_dump_json()
    decoded = ServerEventEnvelope[dict].model_validate_json(encoded)

    assert decoded.sequence == 42
    assert decoded.payload["symbol"] == "BTC/USD"
    assert decoded.protocol_version == "1.0"


def test_api_response_and_command_models_serialize() -> None:
    broker = BrokerIdentifier(broker=BrokerKind.COINBASE, account_id="acct_1")
    request = ExecutionRequest(
        client_order_id="cli_1",
        broker=broker,
        identifier={"symbol": "BTC/USD", "broker": "coinbase"},
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        limit_price=84000.0,
    )
    command = PlaceOrderCommand(execution_request=request)
    response = ApiResponseEnvelope[ExecutionResult].success_envelope(
        data=ExecutionResult(
            order_id="ord_1",
            status=ExecutionStatus.ACCEPTED,
            client_order_id="cli_1",
            message="accepted",
        ),
        message="ok",
    )
    session = SessionState(
        session_id="sess_1",
        status=SessionStatus.ACTIVE,
        user=BrokerSessionSummary(
            user_id="user_1",
            account_id="acct_1",
            broker=BrokerKind.COINBASE,
        ),
    )
    symbol = SymbolSnapshot(
        identifier={"symbol": "BTC/USD", "broker": "coinbase"},
        last_price=84210.5,
    )
    feature = FeatureSnapshot(
        identifier={"symbol": "BTC/USD", "broker": "coinbase"},
        features={"rsi": 62.1, "ema_fast": 84200.0},
    )

    assert command.model_dump()["execution_request"]["client_order_id"] == "cli_1"
    assert response.model_dump()["data"]["status"] == "accepted"
    assert session.user.account_id == "acct_1"
    assert symbol.identifier.symbol == "BTC/USD"
    assert feature.features["rsi"] == 62.1
