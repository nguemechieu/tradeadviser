from __future__ import annotations

from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import shutil
import zipfile


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _resolve(value, default=None):
    if callable(value):
        try:
            return value()
        except Exception:
            return default
    return value if value is not None else default


def _dedupe_paths(paths):
    unique = []
    seen = set()
    for raw in paths:
        if raw in (None, ""):
            continue
        try:
            path = Path(raw).resolve()
        except Exception:
            path = Path(str(raw))
        key = str(path).lower()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        unique.append(path)
    return unique


def collect_diagnostic_log_paths(terminal):
    controller = getattr(terminal, "controller", None)
    candidates = []
    resolver = getattr(controller, "_market_chat_log_file_paths", None)
    if callable(resolver):
        try:
            candidates.extend(list(resolver() or []))
        except Exception:
            pass
    for root in (Path("logs"), Path(".")):
        for name in ("app.log", "errors.log", "native_crash.log", "system.log"):
            candidates.append(root / name)
    return _dedupe_paths(candidates)


def build_diagnostics_snapshot(terminal):
    controller = getattr(terminal, "controller", None)
    runtime_metrics = {}
    runtime_getter = getattr(terminal, "_runtime_metrics_snapshot", None)
    if callable(runtime_getter):
        try:
            runtime_metrics = dict(runtime_getter() or {})
        except Exception:
            runtime_metrics = {}

    health_report = []
    health_getter = getattr(controller, "get_health_check_report", None)
    if callable(health_getter):
        try:
            health_report = list(health_getter() or [])
        except Exception:
            health_report = []

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app": {
            "name": "Sopotek Quant System",
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "session": {
            "live_mode": bool(_resolve(getattr(controller, "is_live_mode", None), False)),
            "exchange": str(getattr(controller, "exchange_name", "") or getattr(getattr(controller, "broker", None), "exchange_name", "") or "").strip(),
            "account": str(_resolve(getattr(controller, "current_account_label", None), "Not set") or "Not set"),
            "timeframe": str(getattr(terminal, "current_timeframe", "") or getattr(controller, "time_frame", "") or ""),
            "symbol": str(getattr(terminal, "symbol", "") or ""),
            "market_preference": str(getattr(controller, "market_trade_preference", "auto") or "auto"),
            "risk_profile": str(getattr(controller, "risk_profile_name", "Balanced") or "Balanced"),
        },
        "health": {
            "summary": str(_resolve(getattr(controller, "get_health_check_summary", None), "Not run") or "Not run"),
            "report": health_report,
            "pipeline": str(_resolve(getattr(controller, "get_pipeline_status_summary", None), "Idle") or "Idle"),
        },
        "runtime_metrics": runtime_metrics,
        "notifications": list(getattr(terminal, "_notification_records", []) or [])[-50:],
        "open_tool_windows": sorted(list((getattr(terminal, "detached_tool_windows", {}) or {}).keys())),
        "log_files": [str(path) for path in collect_diagnostic_log_paths(terminal)],
    }
    return _json_safe(snapshot)


def export_diagnostics_bundle(terminal, output_dir):
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bundle_name = f"sopotek-diagnostics-{stamp}"
    bundle_dir = destination / bundle_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    snapshot = build_diagnostics_snapshot(terminal)
    (bundle_dir / "summary.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    log_dir = bundle_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for path in collect_diagnostic_log_paths(terminal):
        try:
            shutil.copy2(path, log_dir / path.name)
        except Exception:
            continue

    zip_path = destination / f"{bundle_name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in bundle_dir.rglob("*"):
            archive.write(item, item.relative_to(bundle_dir))
    return zip_path
