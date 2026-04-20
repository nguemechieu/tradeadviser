import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

DB_PATH = Path(__file__).resolve().parent / "test_equity_storage.sqlite3"
os.environ["SOPOTEK_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from storage import database as storage_db
from storage.equity_repository import EquitySnapshotRepository


class _SettingsRecorder:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


def setup_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    storage_db.configure_database(f"sqlite:///{DB_PATH.as_posix()}")
    storage_db.init_database()


def teardown_function(_func):
    storage_db.engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_equity_snapshot_repository_round_trips_account_history():
    repo = EquitySnapshotRepository()

    repo.save_snapshot(
        equity=1000.0,
        exchange="paper",
        account_label="Demo",
        balance=1000.0,
        free_margin=750.0,
        used_margin=250.0,
        timestamp="2026-03-17T09:30:00+00:00",
    )
    repo.save_snapshot(
        equity=1015.5,
        exchange="paper",
        account_label="Demo",
        balance=1015.5,
        free_margin=800.0,
        used_margin=215.5,
        timestamp="2026-03-17T10:00:00+00:00",
    )

    rows = repo.get_snapshots(limit=10, exchange="paper", account_label="Demo")

    assert len(rows) == 2
    assert rows[0].equity == 1015.5
    assert rows[1].equity == 1000.0
    assert rows[0].account_label == "Demo"


def test_restore_performance_state_prefers_repository_equity_history():
    repo = EquitySnapshotRepository()
    repo.save_snapshot(equity=1500.0, exchange="paper", account_label="Demo", timestamp="2026-03-17T09:30:00+00:00")
    repo.save_snapshot(equity=1512.5, exchange="paper", account_label="Demo", timestamp="2026-03-17T10:15:00+00:00")

    captured = {}
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.performance.ledger.restore")
    controller.equity_repository = repo
    controller.trade_repository = SimpleNamespace(get_trades=lambda limit=500: [])
    controller.performance_engine = SimpleNamespace(
        load_equity_history=lambda history: captured.setdefault("history", list(history)),
        load_trades=lambda trades: captured.setdefault("trades", list(trades)),
    )
    controller._load_persisted_performance_history = lambda: [{"equity": 1.0, "timestamp": 1.0}]
    controller._performance_trade_payload_from_record = lambda item: item
    controller._active_exchange_code = lambda: "paper"
    controller.current_account_label = lambda: "Demo"

    controller._restore_performance_state()

    assert captured["history"][0]["equity"] == 1500.0
    assert captured["history"][1]["equity"] == 1512.5
    assert captured["history"][0]["timestamp"] < captured["history"][1]["timestamp"]
    assert captured["trades"] == []


def test_restore_performance_state_filters_trades_by_active_exchange():
    captured = {}
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.performance.ledger.exchange_scope")
    controller.equity_repository = None
    controller.trade_repository = SimpleNamespace(
        get_trades=lambda limit=500, exchange=None: (
            [SimpleNamespace(order_id="paper-1", exchange="paper", symbol="BTC/USDT")]
            if exchange == "paper"
            else [
                SimpleNamespace(order_id="paper-1", exchange="paper", symbol="BTC/USDT"),
                SimpleNamespace(order_id="coinbase-1", exchange="coinbase", symbol="BTC/USDT"),
            ]
        )
    )
    controller.performance_engine = SimpleNamespace(
        load_equity_history=lambda history: captured.setdefault("history", list(history)),
        load_trades=lambda trades: captured.setdefault("trades", list(trades)),
    )
    controller._load_persisted_performance_history = lambda: []
    controller._active_exchange_code = lambda: "paper"
    controller.current_account_label = lambda: "Demo"

    controller._restore_performance_state()

    assert captured["history"] == []
    assert len(captured["trades"]) == 1
    assert captured["trades"][0]["exchange"] == "paper"
    assert captured["trades"][0]["order_id"] == "paper-1"


def test_update_performance_equity_persists_snapshot_to_repository():
    repo = EquitySnapshotRepository()
    recorded = []
    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.performance.ledger.persist")
    controller.settings = _SettingsRecorder()
    controller.performance_engine = SimpleNamespace(
        equity_curve=[],
        equity_timestamps=[],
        update_equity=lambda value: recorded.append(float(value)),
    )
    controller.equity_repository = repo
    controller._active_exchange_code = lambda: "paper"
    controller.current_account_label = lambda: "Demo"

    equity = controller._update_performance_equity(
        {
            "equity": 1250.25,
            "free": {"USD": 1000.0},
            "used": {"USD": 250.25},
        }
    )
    rows = repo.get_snapshots(limit=5, exchange="paper", account_label="Demo")

    assert equity == 1250.25
    assert recorded == [1250.25]
    assert len(rows) == 1
    assert rows[0].equity == 1250.25
    assert rows[0].free_margin == 1000.0
    assert rows[0].used_margin == 250.25
