import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.actions.live_trade_actions import submit_manual_trade


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _Console:
    def __init__(self):
        self.rows = []

    def log(self, message, level):
        self.rows.append((message, level))


def test_submit_manual_trade_cancels_live_order_when_operator_rejects_review(monkeypatch):
    _app()
    preview_calls = []
    submit_calls = []
    audit_events = []
    notifications = []

    async def fake_preview_trade_submission(**kwargs):
        preview_calls.append(kwargs)
        return {
            "symbol": kwargs["symbol"],
            "requested_symbol": kwargs["symbol"],
            "reference_price": 105.0,
            "requested_amount": kwargs["amount"],
            "sizing_summary": "Preflight kept the requested size.",
            "sizing_notes": [],
            "market_data_guard": {
                "quote": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "20.0s"},
                "candles": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "3.0h"},
                "orderbook": {"supported": False, "fresh": None, "age_label": "unknown", "threshold_label": ""},
            },
            "eligibility_check": {"warnings": []},
            "resolved_venue": "spot",
        }

    async def fake_submit_trade_with_preflight(**kwargs):
        submit_calls.append(kwargs)
        return {"status": "submitted", "order_id": "should-not-submit"}

    controller = SimpleNamespace(
        is_live_mode=lambda: True,
        current_account_label=lambda: "Primary",
        broker=SimpleNamespace(exchange_name="coinbase"),
        preview_trade_submission=fake_preview_trade_submission,
        submit_trade_with_preflight=fake_submit_trade_with_preflight,
        queue_trade_audit=lambda action, **payload: audit_events.append((action, payload)),
    )
    terminal = SimpleNamespace(
        controller=controller,
        current_timeframe="1h",
        system_console=_Console(),
        _normalize_manual_trade_quantity_mode=lambda mode: str(mode or "units"),
        _show_async_message=lambda *args, **kwargs: None,
        _push_notification=lambda title, message, **kwargs: notifications.append((title, message, kwargs)),
    )

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)

    result = asyncio.run(
        submit_manual_trade(
            terminal,
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            quantity_mode="units",
        )
    )

    assert result is None
    assert len(preview_calls) == 1
    assert submit_calls == []
    assert audit_events[0][0] == "submit_canceled"
    assert notifications[0][0] == "Live order canceled"


def test_submit_manual_trade_bypasses_review_in_non_live_mode(monkeypatch):
    _app()
    preview_calls = []
    submit_calls = []

    async def fake_preview_trade_submission(**kwargs):
        preview_calls.append(kwargs)
        return {
            "symbol": kwargs["symbol"],
            "requested_symbol": kwargs["symbol"],
            "reference_price": 105.0,
            "requested_amount": kwargs["amount"],
            "requested_quantity_mode": kwargs.get("quantity_mode", "units"),
            "applied_requested_mode_amount": kwargs["amount"],
            "sizing_summary": "Preflight kept the requested size.",
            "sizing_notes": [],
            "market_data_guard": {
                "quote": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "20.0s"},
                "candles": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "3.0h"},
                "orderbook": {"supported": False, "fresh": None, "age_label": "unknown", "threshold_label": ""},
            },
            "eligibility_check": {"warnings": []},
            "resolved_venue": "spot",
        }

    async def fake_submit_trade_with_preflight(**kwargs):
        submit_calls.append(kwargs)
        return {
            "status": "submitted",
            "order_id": "manual-001",
            "requested_amount": kwargs["amount"],
            "applied_requested_mode_amount": kwargs["amount"],
            "requested_quantity_mode": "units",
            "size_adjusted": False,
            "sizing_summary": "Preflight kept the requested size.",
            "ai_sizing_reason": "",
        }

    controller = SimpleNamespace(
        is_live_mode=lambda: False,
        current_account_label=lambda: "Paper",
        broker=SimpleNamespace(exchange_name="paper"),
        preview_trade_submission=fake_preview_trade_submission,
        submit_trade_with_preflight=fake_submit_trade_with_preflight,
    )
    terminal = SimpleNamespace(
        controller=controller,
        current_timeframe="1h",
        system_console=_Console(),
        _normalize_manual_trade_quantity_mode=lambda mode: str(mode or "units"),
        _show_async_message=lambda *args, **kwargs: None,
        _push_notification=lambda *args, **kwargs: None,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("review dialog should not be shown outside live mode")

    monkeypatch.setattr(QMessageBox, "question", fail_if_called)

    result = asyncio.run(
        submit_manual_trade(
            terminal,
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            quantity_mode="units",
        )
    )

    assert len(preview_calls) == 1
    assert len(submit_calls) == 1
    assert result["order_id"] == "manual-001"


def test_submit_manual_trade_surfaces_rejection_reason(monkeypatch):
    _app()
    shown_messages = []

    async def fake_preview_trade_submission(**kwargs):
        return {
            "symbol": kwargs["symbol"],
            "requested_symbol": kwargs["symbol"],
            "reference_price": 4.29385,
            "requested_amount": kwargs["amount"],
            "requested_quantity_mode": kwargs.get("quantity_mode", "lots"),
            "applied_requested_mode_amount": kwargs["amount"],
            "sizing_summary": "Preflight kept the requested size.",
            "sizing_notes": [],
            "market_data_guard": {
                "quote": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "20.0s"},
                "candles": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "3.0h"},
                "orderbook": {"supported": True, "fresh": True, "age_label": "<1s", "threshold_label": "20.0s"},
            },
            "eligibility_check": {"warnings": []},
            "resolved_venue": "otc",
        }

    async def fake_submit_trade_with_preflight(**kwargs):
        return {
            "status": "rejected",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "type": kwargs["order_type"],
            "requested_amount": kwargs["amount"],
            "applied_requested_mode_amount": kwargs["amount"],
            "requested_quantity_mode": "lots",
            "size_adjusted": False,
            "sizing_summary": "Preflight kept the requested size.",
            "reason": "Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old).",
        }

    controller = SimpleNamespace(
        is_live_mode=lambda: False,
        current_account_label=lambda: "Paper",
        broker=SimpleNamespace(exchange_name="oanda"),
        preview_trade_submission=fake_preview_trade_submission,
        submit_trade_with_preflight=fake_submit_trade_with_preflight,
    )
    terminal = SimpleNamespace(
        controller=controller,
        current_timeframe="1h",
        system_console=_Console(),
        _normalize_manual_trade_quantity_mode=lambda mode: str(mode or "lots"),
        _show_async_message=lambda title, text, icon=None: shown_messages.append((title, text, icon)),
        _push_notification=lambda *args, **kwargs: None,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("review dialog should not be shown outside live mode")

    monkeypatch.setattr(QMessageBox, "question", fail_if_called)

    result = asyncio.run(
        submit_manual_trade(
            terminal,
            symbol="EUR/PLN",
            side="sell",
            amount=1.35,
            quantity_mode="lots",
        )
    )

    assert result["status"] == "rejected"
    assert terminal.system_console.rows[-1][1] == "ERROR"
    assert "Reason: Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old)." in terminal.system_console.rows[-1][0]
    assert "Reason: Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old)." in shown_messages[-1][1]
    assert shown_messages[-1][2] == QMessageBox.Icon.Critical
