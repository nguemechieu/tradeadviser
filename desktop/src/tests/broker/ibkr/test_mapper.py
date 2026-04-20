import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.ibkr.mapper import IBKRMapper
from broker.ibkr.models import IBKRContract


def test_ibkr_mapper_converts_account_position_quote_and_bars():
    mapper = IBKRMapper()

    account = mapper.account_from_accounts_payload(
        {"id": "DU12345", "accountAlias": "paper", "accountType": "INDIVIDUAL", "currency": "USD"}
    )
    balance = mapper.balance_from_summary(
        {"cashbalance": "12000.5", "netliq": "15400.8", "buyingpower": "30000.1", "availablefunds": "11000.0"},
        account_id="DU12345",
    )
    position = mapper.position_from_payload(
        {
            "symbol": "AAPL",
            "conid": 265598,
            "position": "10",
            "avgCost": "190.25",
            "mktPrice": "194.12",
            "mktValue": "1941.2",
            "unrealizedPnl": "38.7",
        },
        account_id="DU12345",
    )
    quote = mapper.quote_from_snapshot(
        {"55": "AAPL", "84": "194.1", "86": "194.3", "31": "194.2", "88": "193.0", "6008": "194.2"},
        contract=IBKRContract(symbol="AAPL", conid="265598"),
    )
    bars = mapper.historical_bars_from_payload(
        {
            "data": [
                {"t": 1712140800000, "o": 190.0, "h": 195.0, "l": 189.5, "c": 194.0, "v": 1000},
                {"t": 1712144400000, "o": 194.0, "h": 196.0, "l": 193.0, "c": 195.5, "v": 1200},
            ]
        },
        symbol="AAPL",
    )

    assert account.account_id == "DU12345"
    assert balance.equity == 15400.8
    assert mapper.canonical_position(position)["symbol"] == "AAPL"
    assert mapper.canonical_quote(quote)["ask"] == 194.3
    assert bars[-1][4] == 195.5


def test_ibkr_mapper_builds_normalized_order_payload_and_response():
    mapper = IBKRMapper()
    contract = IBKRContract(symbol="AAPL", conid="265598", sec_type="STK")

    request = mapper.order_request_from_order(
        {"symbol": "AAPL", "side": "buy", "amount": 5, "type": "limit", "price": 194.25, "client_order_id": "ibkr-1"},
        account_id="DU12345",
        contract=contract,
    )
    payload = mapper.webapi_order_payload(request)
    response = mapper.order_response_from_payload({"order_id": "123", "status": "Submitted"}, request=request)
    canonical = mapper.canonical_order_response(response)

    assert payload["conid"] == 265598
    assert payload["orderType"] == "LMT"
    assert canonical["id"] == "123"
    assert canonical["type"] == "limit"
    assert canonical["amount"] == 5
