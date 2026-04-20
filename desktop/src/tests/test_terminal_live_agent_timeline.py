import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QTextBrowser

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_refresh_live_agent_timeline_panel_renders_current_symbol_decision_chain():
    _app()
    summary = QLabel()
    browser = QTextBrowser()

    fake = SimpleNamespace(
        controller=SimpleNamespace(
            symbols=["EUR/USD", "USD/JPY"],
            decision_timeline_snapshot=lambda symbol=None, limit=12: {
                "symbol": symbol or "EUR/USD",
                "summary": "EUR/USD: BUY approved via RiskAgent / execution_ready.",
                "steps": [
                    {
                        "timestamp_label": "2026-04-06 14:01:00 UTC",
                        "agent_name": "SignalAgent",
                        "stage": "signal",
                        "status": "signal",
                        "strategy_name": "EMA Cross",
                        "timeframe": "1h",
                        "side": "BUY",
                        "reason": "Momentum breakout aligned with trend.",
                        "payload": {"confidence": 0.82},
                    },
                    {
                        "timestamp_label": "2026-04-06 14:01:02 UTC",
                        "agent_name": "RiskAgent",
                        "stage": "execution_ready",
                        "status": "approved",
                        "strategy_name": "EMA Cross",
                        "timeframe": "1h",
                        "side": "BUY",
                        "reason": "Risk approved within exposure limits.",
                        "payload": {"approved": True},
                    },
                ],
            },
            live_agent_runtime_feed=lambda limit=60, symbol=None: [
                {"symbol": symbol or "EUR/USD", "message": "Risk approved", "timestamp_label": "2026-04-06 14:01:02 UTC"}
            ],
        ),
        live_agent_timeline_dock=None,
        live_agent_timeline_summary=summary,
        live_agent_timeline_browser=browser,
        _live_agent_timeline_cache=None,
    )
    fake._is_qt_object_alive = lambda obj: obj is not None
    fake._normalized_symbol = lambda symbol: Terminal._normalized_symbol(fake, symbol)
    fake._current_chart_symbol = lambda: "EUR/USD"
    fake._live_agent_timeline_target_symbol = lambda: Terminal._live_agent_timeline_target_symbol(fake)
    fake._agent_runtime_status_label = lambda row: Terminal._agent_runtime_status_label(fake, row)
    fake._agent_runtime_health_snapshot = lambda rows, now_ts=None: Terminal._agent_runtime_health_snapshot(fake, rows, now_ts)

    Terminal._refresh_live_agent_timeline_panel(fake, force=True)

    assert "EUR/USD" in summary.text()
    assert "Health:" in summary.text()
    assert "Decision steps: 2" in summary.text()
    assert "Agent Health Check" in browser.toPlainText()
    assert "SignalAgent" in browser.toPlainText()
    assert "Risk approved within exposure limits." in browser.toPlainText()


def test_refresh_live_agent_timeline_panel_ignores_stale_chart_symbol_and_uses_session_feed_symbol():
    _app()
    summary = QLabel()
    browser = QTextBrowser()

    def _snapshot(symbol=None, limit=12):
        resolved = symbol or "EUR/USD"
        return {
            "symbol": resolved,
            "summary": f"{resolved}: HOLD pending via TraderAgent / review.",
            "steps": [
                {
                    "timestamp_label": "2026-04-06 14:05:00 UTC",
                    "agent_name": "TraderAgent",
                    "stage": "review",
                    "status": "pending",
                    "strategy_name": "Donchian Trend",
                    "timeframe": "4h",
                    "side": "",
                    "reason": "Waiting for confirmation.",
                    "payload": {},
                }
            ],
        }

    fake = SimpleNamespace(
        controller=SimpleNamespace(
            symbols=["EUR/USD"],
            decision_timeline_snapshot=_snapshot,
            live_agent_runtime_feed=lambda limit=60, symbol=None: [
                {
                    "symbol": "EUR/USD",
                    "agent_name": "TraderAgent",
                    "message": "Waiting for confirmation.",
                    "timestamp_label": "2026-04-06 14:05:00 UTC",
                }
            ],
        ),
        live_agent_timeline_dock=None,
        live_agent_timeline_summary=summary,
        live_agent_timeline_browser=browser,
        _live_agent_timeline_cache=None,
    )
    fake._is_qt_object_alive = lambda obj: obj is not None
    fake._normalized_symbol = lambda symbol: Terminal._normalized_symbol(fake, symbol)
    fake._current_chart_symbol = lambda: "GBP/HKD"
    fake._live_agent_timeline_target_symbol = lambda: Terminal._live_agent_timeline_target_symbol(fake)
    fake._agent_runtime_status_label = lambda row: Terminal._agent_runtime_status_label(fake, row)
    fake._agent_runtime_health_snapshot = lambda rows, now_ts=None: Terminal._agent_runtime_health_snapshot(fake, rows, now_ts)

    Terminal._refresh_live_agent_timeline_panel(fake, force=True)

    assert "Focus symbol: EUR/USD" in summary.text()
    assert "GBP/HKD" not in summary.text()
    assert "Health:" in summary.text()
    assert "TraderAgent" in browser.toPlainText()


def test_agent_runtime_health_snapshot_accepts_iso_timestamps():
    _app()
    now_dt = datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    fake = SimpleNamespace()
    fake._agent_runtime_status_label = lambda row: Terminal._agent_runtime_status_label(fake, row)

    snapshot = Terminal._agent_runtime_health_snapshot(
        fake,
        [
            {
                "symbol": "EUR/USD",
                "event_type": "signal",
                "timestamp": (now_dt - timedelta(seconds=15)).isoformat(),
                "message": "Signal selected.",
            },
            {
                "symbol": "EUR/USD",
                "event_type": "risk_approved",
                "decision_id": "dec-1",
                "timestamp": (now_dt - timedelta(seconds=5)).isoformat(),
                "message": "Risk approved.",
            },
        ],
        now_ts=now_ts,
    )

    assert snapshot["health"] == "HEALTHY"
    assert snapshot["recent_event_count"] == 2
    assert snapshot["active_symbol_count"] == 1
    assert snapshot["last_event_age"] is not None and snapshot["last_event_age"] < 10.0
