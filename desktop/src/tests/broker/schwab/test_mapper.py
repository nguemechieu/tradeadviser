import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.schwab.mapper import SchwabMapper


def test_schwab_mapper_converts_account_position_quote_and_order_payloads():
    mapper = SchwabMapper()

    account = mapper.canonical_account(
        mapper.account_from_number_entry(
            {
                "accountNumber": "123456789",
                "hashValue": "hash-123",
                "displayName": "Main Account",
                "type": "MARGIN",
            }
        )
    )
    position = mapper.canonical_position(
        mapper.position_from_payload(
            {
                "longQuantity": 2,
                "shortQuantity": 0,
                "averagePrice": 120.5,
                "marketValue": 252.0,
                "currentDayProfitLoss": 11.5,
                "instrument": {
                    "symbol": "AAPL",
                    "assetType": "EQUITY",
                },
            },
            account_id="123456789",
            account_hash="hash-123",
        )
    )
    quote = mapper.canonical_quote(
        mapper.quote_from_payload(
            "AAPL",
            {
                "bidPrice": 189.1,
                "askPrice": 189.3,
                "lastPrice": 189.2,
                "closePrice": 188.4,
                "quoteTime": "2026-04-03T15:30:00Z",
            },
        )
    )
    order = mapper.canonical_order_from_raw(
        {
            "orderId": "order-42",
            "orderType": "LIMIT",
            "status": "FILLED",
            "duration": "DAY",
            "price": 189.0,
            "orderLegCollection": [
                {
                    "instruction": "BUY",
                    "quantity": 3,
                    "instrument": {"symbol": "AAPL"},
                }
            ],
        },
        account_id="123456789",
    )

    assert account["broker"] == "schwab"
    assert account["account_id"] == "123456789"
    assert account["account_hash"] == "hash-123"

    assert position["broker"] == "schwab"
    assert position["symbol"] == "AAPL"
    assert position["quantity"] == 2.0
    assert position["notional"] == 252.0

    assert quote["broker"] == "schwab"
    assert quote["symbol"] == "AAPL"
    assert quote["last"] == 189.2

    assert order["broker"] == "schwab"
    assert order["id"] == "order-42"
    assert order["type"] == "limit"
    assert order["status"] == "filled"
