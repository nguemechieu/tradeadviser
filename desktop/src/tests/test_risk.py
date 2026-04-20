import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.risk_engine import RiskEngine


def test_position_size():
    risk = RiskEngine(account_equity=10000)

    size = risk.position_size(
        entry_price=100,
        stop_price=95,
    )

    assert size > 0


def test_trade_validation():
    risk = RiskEngine(account_equity=10000, max_position_size_pct=0.5)

    approved, msg = risk.validate_trade(
        price=100,
        quantity=1,
    )

    assert approved is True
    assert msg == "Approved"


def test_adjust_trade_scales_large_position_down_to_cap():
    risk = RiskEngine(account_equity=10000, max_position_size_pct=0.1)

    approved, adjusted_quantity, reason = risk.adjust_trade(
        price=100,
        quantity=25,
    )

    assert approved is True
    assert adjusted_quantity == 10
    assert "reduced" in reason.lower()


def test_position_size_is_capped_by_max_position_size():
    risk = RiskEngine(account_equity=10000, max_risk_per_trade=0.02, max_position_size_pct=0.05)

    size = risk.position_size(
        entry_price=100,
        stop_price=95,
    )

    assert size == 5


def test_position_size_converts_forex_quote_currency_to_account_currency():
    risk = RiskEngine(account_equity=10000, max_risk_per_trade=0.02, max_position_size_pct=1000.0)

    size = risk.position_size(
        entry_price=150.0,
        stop_price=149.5,
        quote_to_account_rate=(1.0 / 150.0),
        pip_size=0.01,
        symbol="USD/JPY",
    )

    assert size == pytest.approx(60000.0)


def test_adjust_trade_uses_stop_loss_risk_for_forex_pairs():
    risk = RiskEngine(account_equity=10000, max_risk_per_trade=0.02, max_position_size_pct=10.0)

    approved, adjusted_quantity, reason = risk.adjust_trade(
        price=1.10,
        quantity=100000.0,
        stop_price=1.095,
        quote_to_account_rate=1.0,
        pip_size=0.0001,
        symbol="EUR/USD",
    )

    assert approved is True
    assert adjusted_quantity == pytest.approx(40000.0)
    assert "max risk" in reason.lower()
    assert "pip" in reason.lower()


def test_position_size_uses_actual_tiny_account_equity():
    risk = RiskEngine(account_equity=0.25, max_risk_per_trade=1.0, max_position_size_pct=0.10)

    size = risk.position_size(
        entry_price=100.0,
        stop_price=99.0,
    )

    assert size == pytest.approx(0.00025)
