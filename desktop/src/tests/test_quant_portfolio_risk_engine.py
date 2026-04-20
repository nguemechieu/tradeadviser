import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from quant.portfolio_risk_engine import PortfolioRiskEngine


class FakeDataset:
    def __init__(self, symbol, frame):
        self.symbol = symbol
        self.frame = frame
        self.empty = frame is None or frame.empty


class FakeDataHub:
    def __init__(self, frames):
        self.frames = frames

    async def get_symbol_dataset(self, request=None, **kwargs):
        symbol = str(getattr(request, "symbol", None) or kwargs.get("symbol") or "").upper()
        frame = self.frames.get(symbol, pd.DataFrame())
        return FakeDataset(symbol, frame)


def _frame_from_closes(closes):
    rows = []
    for index, close in enumerate(closes):
        value = float(close)
        rows.append(
            {
                "timestamp": index,
                "open": value,
                "high": value * 1.01,
                "low": value * 0.99,
                "close": value,
                "volume": 1000.0 + index,
            }
        )
    return pd.DataFrame(rows)


def test_portfolio_risk_engine_approves_reasonable_trade():
    engine = PortfolioRiskEngine(account_equity=10000, max_symbol_exposure_pct=0.30)
    frame = _frame_from_closes([100, 101, 101.5, 102, 102.2, 102.8, 103.1, 103.4, 103.7, 104.0])
    data_hub = FakeDataHub({"BTC/USDT": frame})

    approval = asyncio.run(
        engine.approve_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=2,
            price=100,
            portfolio=SimpleNamespace(positions={}),
            market_prices={},
            data_hub=data_hub,
            dataset=FakeDataset("BTC/USDT", frame),
        )
    )

    assert approval.approved is True
    assert approval.adjusted_amount > 0
    assert "Approved" in approval.reason


def test_portfolio_risk_engine_rejects_high_correlation_concentration():
    engine = PortfolioRiskEngine(account_equity=10000, max_symbol_exposure_pct=0.30, max_correlation=0.80)
    eth_frame = _frame_from_closes([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    btc_frame = _frame_from_closes([200, 202, 204, 206, 208, 210, 212, 214, 216, 218])
    data_hub = FakeDataHub({"ETH/USDT": eth_frame, "BTC/USDT": btc_frame})
    portfolio = SimpleNamespace(
        positions={
            "ETH/USDT": SimpleNamespace(quantity=30, avg_price=100),
        }
    )

    approval = asyncio.run(
        engine.approve_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=5,
            price=100,
            portfolio=portfolio,
            market_prices={"ETH/USDT": 100, "BTC/USDT": 100},
            data_hub=data_hub,
            dataset=FakeDataset("BTC/USDT", btc_frame),
        )
    )

    assert approval.approved is False
    assert "correlated" in approval.reason.lower()


def test_portfolio_risk_engine_scales_trade_down_when_requested_size_is_too_large():
    engine = PortfolioRiskEngine(account_equity=10000, max_symbol_exposure_pct=0.30, max_position_size_pct=0.10)
    frame = _frame_from_closes([100, 110, 90, 115, 92, 118, 95, 120, 96, 121, 98])
    data_hub = FakeDataHub({"SOL/USDT": frame})

    approval = asyncio.run(
        engine.approve_trade(
            symbol="SOL/USDT",
            side="buy",
            amount=50,
            price=100,
            portfolio=SimpleNamespace(positions={}),
            market_prices={"SOL/USDT": 100},
            data_hub=data_hub,
            dataset=FakeDataset("SOL/USDT", frame),
        )
    )

    assert approval.approved is True
    assert approval.adjusted_amount < 50
    assert "reduced" in approval.reason.lower()


def test_portfolio_risk_engine_uses_actual_tiny_equity_for_trade_caps():
    engine = PortfolioRiskEngine(
        account_equity=0.25,
        max_portfolio_risk=1.0,
        max_risk_per_trade=1.0,
        max_position_size_pct=0.10,
        max_symbol_exposure_pct=1.0,
    )
    frame = _frame_from_closes([100, 100.1, 100.2, 100.25, 100.3, 100.35, 100.4, 100.45, 100.5, 100.55])
    data_hub = FakeDataHub({"BTC/USDT": frame})

    approval = asyncio.run(
        engine.approve_trade(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            price=100.0,
            portfolio=SimpleNamespace(positions={}),
            market_prices={"BTC/USDT": 100.0},
            data_hub=data_hub,
            dataset=FakeDataset("BTC/USDT", frame),
        )
    )

    assert approval.approved is True
    assert approval.adjusted_amount == pytest.approx(0.00025)
