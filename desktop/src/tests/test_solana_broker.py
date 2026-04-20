import asyncio
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.broker_factory import BrokerFactory
from broker.solana_broker import SolanaBroker
from config.config import AppConfig, BrokerConfig, RiskConfig, SystemConfig


def _make_wallet(seed_byte=7):
    seed = bytes([seed_byte]) * 32
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        "seed": seed,
        "wallet": SolanaBroker._base58_encode(public_key),
        "secret": SolanaBroker._base58_encode(seed),
    }


def test_broker_factory_routes_solana_exchange(monkeypatch):
    import broker.broker_factory as broker_factory_module

    monkeypatch.setattr(broker_factory_module, "SolanaBroker", lambda cfg: ("solana", cfg.exchange))

    config = AppConfig(
        broker=BrokerConfig(type="crypto", exchange="solana", mode="paper"),
        risk=RiskConfig(),
        system=SystemConfig(),
    )

    broker = BrokerFactory.create(config)

    assert broker == ("solana", "solana")


def test_solana_broker_fetches_ticker_and_ohlcv(monkeypatch):
    wallet = _make_wallet()
    broker = SolanaBroker(
        BrokerConfig(type="crypto", exchange="solana", api_key=wallet["wallet"], mode="paper")
    )

    market = {
        "symbol": "SOL/USDC",
        "base_mint": broker.WRAPPED_SOL_MINT,
        "quote_mint": broker.DEFAULT_USDC_MINT,
        "base_decimals": 9,
        "quote_decimals": 6,
        "pool_address": "pool-1",
    }
    pool_payload = {
        "data": {
            "id": "solana_pool-1",
            "attributes": {
                "address": "pool-1",
                "reserve_in_usd": "2500000",
                "base_token_price_quote_token": "142.5",
            },
            "relationships": {
                "base_token": {"data": {"id": "solana_sol"}},
                "quote_token": {"data": {"id": "solana_usdc"}},
            },
        },
        "included": [
            {
                "id": "solana_sol",
                "type": "token",
                "attributes": {"address": broker.WRAPPED_SOL_MINT, "symbol": "SOL", "decimals": 9},
            },
            {
                "id": "solana_usdc",
                "type": "token",
                "attributes": {"address": broker.DEFAULT_USDC_MINT, "symbol": "USDC", "decimals": 6},
            },
        ],
    }

    async def fake_resolve_market(symbol):
        assert symbol == "SOL/USDC"
        return market

    async def fake_pool_snapshot(_market):
        return pool_payload

    async def fake_request_gecko(path, params=None):
        assert "ohlcv" in path or "ohlc" in path
        return {
            "data": {
                "attributes": {
                    "ohlcv_list": [
                        [1710000000, 140.0, 145.0, 139.0, 144.0, 1000.0],
                        [1710003600, 144.0, 146.0, 143.0, 145.5, 1200.0],
                    ]
                }
            }
        }

    monkeypatch.setattr(broker, "_resolve_market", fake_resolve_market)
    monkeypatch.setattr(broker, "_pool_snapshot", fake_pool_snapshot)
    monkeypatch.setattr(broker, "_request_gecko", fake_request_gecko)

    ticker = asyncio.run(broker.fetch_ticker("SOL/USDC"))
    candles = asyncio.run(broker.fetch_ohlcv("SOL/USDC", timeframe="1h", limit=2))

    assert ticker["symbol"] == "SOL/USDC"
    assert ticker["last"] == 142.5
    assert ticker["bid"] < ticker["ask"]
    assert candles[-1][0] == 1710003600000
    assert candles[-1][4] == 145.5


def test_solana_broker_creates_paper_market_order(monkeypatch):
    wallet = _make_wallet()
    broker = SolanaBroker(
        BrokerConfig(type="crypto", exchange="solana", api_key=wallet["wallet"], mode="paper")
    )

    async def fake_fetch_ticker(symbol):
        assert symbol == "SOL/USDC"
        return {"symbol": symbol, "bid": 142.0, "ask": 143.0, "last": 142.5}

    monkeypatch.setattr(broker, "fetch_ticker", fake_fetch_ticker)

    created = asyncio.run(broker.create_order("SOL/USDC", "buy", 2.0, type="market"))

    assert created["status"] == "filled"
    assert created["filled"] == 2.0
    assert created["price"] == 143.0
    assert created["cost"] == 286.0
    assert asyncio.run(broker.fetch_order(created["id"]))["symbol"] == "SOL/USDC"


def test_solana_broker_signs_serialized_transactions():
    wallet = _make_wallet(seed_byte=11)
    broker = SolanaBroker(
        BrokerConfig(
            type="crypto",
            exchange="solana",
            api_key=wallet["wallet"],
            secret=wallet["secret"],
            mode="live",
            password="test-jup-key",
        )
    )

    signer_key = SolanaBroker._base58_decode(wallet["wallet"])
    message = bytes([0x80, 1, 0, 0, 1]) + signer_key + (b"\x00" * 32) + b"\x00\x00"
    unsigned = b"\x01" + (b"\x00" * 64) + message
    signed_b64 = broker._sign_serialized_transaction(base64.b64encode(unsigned).decode("ascii"))
    signed = base64.b64decode(signed_b64)

    assert signed[1:65] != (b"\x00" * 64)


def test_solana_broker_accepts_okx_trade_api_credentials():
    broker = SolanaBroker(
        BrokerConfig(
            type="crypto",
            exchange="solana",
            api_key="okx-dev-key",
            secret="okx-dev-secret",
            password="okx-passphrase",
            account_id="project-123",
            mode="paper",
        )
    )

    assert broker.wallet_address == ""
    assert broker.secret == ""
    assert broker.okx_api_key == "okx-dev-key"
    assert broker.okx_secret_key == "okx-dev-secret"
    assert broker.okx_passphrase == "okx-passphrase"
    assert broker.okx_project_id == "project-123"
    assert broker.market_data_provider == "okx"


def test_solana_broker_fetches_symbols_and_ticker_via_okx(monkeypatch):
    broker = SolanaBroker(
        BrokerConfig(
            type="crypto",
            exchange="solana",
            api_key="okx-dev-key",
            secret="okx-dev-secret",
            password="okx-passphrase",
            mode="paper",
        )
    )
    requests = []

    async def fake_request_okx(path, *, params=None):
        requests.append((path, dict(params or {})))
        if path == broker.OKX_TOKENS_PATH:
            return {
                "code": "0",
                "data": [
                    {
                        "tokenSymbol": "SOL",
                        "tokenContractAddress": broker.NATIVE_SOL_MINT,
                        "decimals": "9",
                        "tokenName": "Solana",
                    },
                    {
                        "tokenSymbol": "USDC",
                        "tokenContractAddress": broker.DEFAULT_USDC_MINT,
                        "decimals": "6",
                        "tokenName": "USD Coin",
                    },
                    {
                        "tokenSymbol": "JUP",
                        "tokenContractAddress": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
                        "decimals": "6",
                        "tokenName": "Jupiter",
                    },
                ],
            }
        if path == broker.OKX_QUOTES_PATH:
            assert params["chainIndex"] == broker.OKX_CHAIN_INDEX
            assert params["fromTokenAddress"] == broker.NATIVE_SOL_MINT
            assert params["toTokenAddress"] == broker.DEFAULT_USDC_MINT
            assert int(params["amount"]) == 10**9
            return {
                "code": "0",
                "data": [
                    {
                        "fromTokenAmount": str(10**9),
                        "toTokenAmount": "142500000",
                    }
                ],
            }
        raise AssertionError(f"Unexpected OKX path: {path}")

    monkeypatch.setattr(broker, "_request_okx", fake_request_okx)

    symbols = asyncio.run(broker.fetch_symbols())
    ticker = asyncio.run(broker.fetch_ticker("SOL/USDC"))

    assert "SOL/USDC" in symbols
    assert ticker["symbol"] == "SOL/USDC"
    assert ticker["last"] == 142.5
    assert any(path == broker.OKX_TOKENS_PATH for path, _ in requests)
    assert any(path == broker.OKX_QUOTES_PATH for path, _ in requests)


def test_solana_broker_creates_live_okx_market_sell(monkeypatch):
    wallet = _make_wallet(seed_byte=13)
    broker = SolanaBroker(
        BrokerConfig(
            type="crypto",
            exchange="solana",
            api_key="okx-dev-key",
            secret="okx-dev-secret",
            password="okx-passphrase",
            mode="live",
            options={
                "wallet_address": wallet["wallet"],
                "private_key": wallet["secret"],
            },
        )
    )
    unsigned = b"\x01" + (b"\x00" * 64) + (
        bytes([0x80, 1, 0, 0, 1])
        + SolanaBroker._base58_decode(wallet["wallet"])
        + (b"\x00" * 32)
        + b"\x00\x00"
    )
    market = {
        "symbol": "SOL/USDC",
        "base_mint": broker.NATIVE_SOL_MINT,
        "quote_mint": broker.DEFAULT_USDC_MINT,
        "base_decimals": 9,
        "quote_decimals": 6,
        "provider": "okx",
    }

    async def fake_resolve_market(symbol):
        assert symbol == "SOL/USDC"
        return market

    async def fake_quote_okx(from_mint, to_mint, amount_units):
        assert from_mint == broker.NATIVE_SOL_MINT
        assert to_mint == broker.DEFAULT_USDC_MINT
        assert amount_units == 2 * 10**9
        return {
            "fromTokenAmount": str(2 * 10**9),
            "toTokenAmount": "285000000",
        }

    async def fake_request_okx(path, *, params=None):
        assert path == broker.OKX_SWAP_PATH
        assert params["userWalletAddress"] == wallet["wallet"]
        assert params["fromTokenAddress"] == broker.NATIVE_SOL_MINT
        assert params["toTokenAddress"] == broker.DEFAULT_USDC_MINT
        return {
            "code": "0",
            "data": [
                {
                    "tx": {
                        "data": SolanaBroker._base58_encode(unsigned),
                    }
                }
            ],
        }

    async def fake_send_signed_transaction(signed_transaction, *, encoding="base64"):
        assert encoding == "base58"
        assert signed_transaction
        return "solana-okx-txid"

    async def fake_wait_for_signature(signature):
        assert signature == "solana-okx-txid"
        return {"confirmationStatus": "confirmed"}

    monkeypatch.setattr(broker, "_resolve_market", fake_resolve_market)
    monkeypatch.setattr(broker, "_quote_okx", fake_quote_okx)
    monkeypatch.setattr(broker, "_request_okx", fake_request_okx)
    monkeypatch.setattr(broker, "_send_signed_transaction", fake_send_signed_transaction)
    monkeypatch.setattr(broker, "_wait_for_signature", fake_wait_for_signature)

    order = asyncio.run(broker.create_order("SOL/USDC", "sell", 2.0, type="market"))

    assert order["id"] == "solana-okx-txid"
    assert order["filled"] == 2.0
    assert order["cost"] == 285.0
    assert order["average"] == 142.5
