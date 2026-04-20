import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk.trader_behavior_guard import TraderBehaviorGuard


def test_behavior_guard_blocks_excess_hourly_order_flow():
    guard = TraderBehaviorGuard(max_orders_per_hour=2, max_orders_per_day=10)
    guard.record_order_attempt({"symbol": "BTC/USDT", "amount": 0.1, "source": "bot"}, allowed=True)
    guard.record_order_attempt({"symbol": "ETH/USDT", "amount": 0.1, "source": "bot"}, allowed=True)

    allowed, reason, snapshot = guard.evaluate_order({"symbol": "SOL/USDT", "amount": 0.1, "source": "bot"})

    assert allowed is False
    assert "too many orders in the last hour" in reason
    assert snapshot["state"] == "COOLDOWN"


def test_behavior_guard_blocks_large_size_jump():
    guard = TraderBehaviorGuard(max_size_jump_ratio=2.0)
    guard.record_order_attempt({"symbol": "BTC/USDT", "amount": 1.0, "source": "manual"}, allowed=True)

    allowed, reason, _snapshot = guard.evaluate_order({"symbol": "BTC/USDT", "amount": 2.5, "source": "manual"})

    assert allowed is False
    assert "size jump" in reason


def test_behavior_guard_applies_reentry_lock_after_loss():
    guard = TraderBehaviorGuard(
        max_consecutive_losses=3,
        same_symbol_reentry_cooldown_seconds=300,
    )
    guard.record_trade_update({"symbol": "BTC/USDT", "status": "filled", "pnl": -12.5, "filled_size": 0.5})

    allowed, reason, snapshot = guard.evaluate_order({"symbol": "BTC/USDT", "amount": 0.25, "source": "bot"})

    assert allowed is False
    assert "cooling down after a losing trade" in reason
    assert snapshot["active_symbol_cooldowns"] >= 1


def test_behavior_guard_blocks_after_daily_drawdown_limit():
    guard = TraderBehaviorGuard(daily_drawdown_limit_pct=0.05, cooldown_after_loss_seconds=120)
    guard.record_equity(1000.0)
    guard.record_equity(940.0)

    allowed, reason, snapshot = guard.evaluate_order({"symbol": "ETH/USDT", "amount": 0.25, "source": "bot"})

    assert allowed is False
    assert "daily drawdown reached" in reason
    assert snapshot["state"] == "COOLDOWN"


def test_behavior_guard_manual_lock_blocks_until_cleared():
    guard = TraderBehaviorGuard()
    guard.activate_manual_lock("Emergency kill switch active")

    allowed, reason, snapshot = guard.evaluate_order({"symbol": "BTC/USDT", "amount": 1.0, "source": "manual"})

    assert allowed is False
    assert "Emergency kill switch active" in reason
    assert snapshot["state"] == "LOCKED"

    guard.clear_manual_lock()
    allowed, _reason, snapshot = guard.evaluate_order({"symbol": "BTC/USDT", "amount": 1.0, "source": "manual"})
    assert allowed is True
    assert snapshot["state"] in {"NORMAL", "WATCH"}
