import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.services.diagnostics_service import export_diagnostics_bundle


def test_export_diagnostics_bundle_writes_summary_and_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    app_log = logs_dir / "app.log"
    app_log.write_text("runtime log line", encoding="utf-8")

    fake = SimpleNamespace(
        controller=SimpleNamespace(
            get_health_check_report=lambda: [{"name": "Connectivity", "status": "pass", "detail": "OK"}],
            get_health_check_summary=lambda: "1 pass / 0 warn",
            get_pipeline_status_summary=lambda: "1 active / 0 guarded / 0 idle",
            is_live_mode=lambda: False,
            current_account_label=lambda: "Demo",
            market_trade_preference="auto",
            risk_profile_name="Balanced",
            exchange_name="paper",
            _market_chat_log_file_paths=lambda: [app_log],
        ),
        current_timeframe="1h",
        symbol="BTC/USDT",
        _runtime_metrics_snapshot=lambda: {"equity_value": 1234.5, "open_order_count": 2},
        _notification_records=[{"title": "API disconnected", "message": "Broker unreachable"}],
        detached_tool_windows={"system_health": object()},
    )

    bundle_path = export_diagnostics_bundle(fake, tmp_path)

    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert "summary.json" in names
        assert "logs/app.log" in names
        summary = json.loads(archive.read("summary.json").decode("utf-8"))

    assert summary["session"]["account"] == "Demo"
    assert summary["session"]["exchange"] == "paper"
    assert summary["runtime_metrics"]["equity_value"] == 1234.5
    assert summary["health"]["summary"] == "1 pass / 0 warn"
