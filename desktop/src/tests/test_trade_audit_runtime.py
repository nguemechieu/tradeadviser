import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController


def test_queue_trade_audit_accepts_sizing_metadata_without_crashing():
    recorded = []

    class _Repository:
        def record_event(self, **kwargs):
            recorded.append(kwargs)
            return kwargs

    controller = AppController.__new__(AppController)
    controller.trade_audit_repository = _Repository()
    controller.broker = SimpleNamespace(exchange_name="oanda")
    controller.current_account_label = lambda: "acct-1"
    controller._market_venue_for_symbol = lambda symbol: "forex" if symbol else None

    async def _run():
        task = controller.queue_trade_audit(
            "submit_success",
            status="submitted",
            symbol="EUR/USD",
            side="buy",
            requested_amount=2.5,
            requested_quantity_mode="lots",
            sizing_summary="AI reduced order size to fit risk.",
            ai_sizing_reason="risk cap",
        )
        assert task is not None
        await task

    asyncio.run(_run())

    assert recorded
    assert recorded[0]["symbol"] == "EUR/USD"
    assert recorded[0]["payload"]["requested_amount"] == 2.5
    assert recorded[0]["payload"]["requested_quantity_mode"] == "lots"
    assert recorded[0]["payload"]["sizing_summary"] == "AI reduced order size to fit risk."
    assert recorded[0]["payload"]["ai_sizing_reason"] == "risk cap"
