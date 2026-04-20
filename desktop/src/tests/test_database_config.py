import os
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import database as storage_db


def test_normalize_database_url_repairs_mysql_scheme_and_charset_typo():
    normalized = storage_db.normalize_database_url(
        " mysql://sopotek:sopotek_local@localhost:3306/sopotek_trading?chartset=utf8mb4 "
    )

    assert normalized == (
        "mysql+pymysql://sopotek:sopotek_local@localhost:3306/"
        "sopotek_trading?charset=utf8mb4"
    )


def test_normalize_database_url_repairs_pymsql_driver_typo():
    normalized = storage_db.normalize_database_url(
        "mysql+pymsql://sopotek:sopotek_local@localhost:3306/sopotek_trading?charset=utf8mb4"
    )

    assert normalized == (
        "mysql+pymysql://sopotek:sopotek_local@localhost:3306/"
        "sopotek_trading?charset=utf8mb4"
    )


def test_sqlite_engine_configures_busy_timeout_and_wal(tmp_path):
    database_path = tmp_path / "sqlite-pragmas.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = storage_db._create_engine(database_url)

    try:
        with engine.connect() as connection:
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            journal_mode = str(connection.execute(text("PRAGMA journal_mode")).scalar_one()).lower()

        assert busy_timeout == storage_db.SQLITE_BUSY_TIMEOUT_MS
        assert journal_mode == "wal"
    finally:
        engine.dispose()


def test_apply_sqlite_pragmas_falls_back_when_wal_is_unavailable():
    executed = []

    class _FakeCursor:
        def execute(self, statement):
            executed.append(statement)
            if statement == "PRAGMA journal_mode=WAL":
                raise OperationalError(statement, {}, Exception("disk I/O error"))

        def fetchone(self):
            return ("wal",)

        def close(self):
            return None

    class _FakeConnection:
        def cursor(self):
            return _FakeCursor()

    storage_db._apply_sqlite_pragmas(_FakeConnection(), None)

    assert f"PRAGMA busy_timeout={storage_db.SQLITE_BUSY_TIMEOUT_MS}" in executed
    assert "PRAGMA journal_mode=WAL" in executed
    assert "PRAGMA journal_mode=DELETE" in executed


def test_run_with_sqlite_lock_retry_retries_transient_lock(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(storage_db.time, "sleep", lambda _seconds: None)

    def flaky_operation():
        calls["count"] += 1
        if calls["count"] == 1:
            raise OperationalError("PRAGMA main.table_info('trades')", {}, Exception("database is locked"))
        return "ok"

    result = storage_db._run_with_sqlite_lock_retry(
        flaky_operation,
        database_url="sqlite:///memory-test.sqlite3",
    )

    assert result == "ok"
    assert calls["count"] == 2


def test_configure_database_normalizes_remote_url_before_storing(monkeypatch):
    created_urls = []
    previous_engine = storage_db.engine
    previous_session_local = storage_db.SessionLocal
    previous_url = storage_db.DATABASE_URL
    previous_env = os.environ.get("SOPOTEK_DATABASE_URL")

    fake_previous_engine = SimpleNamespace(dispose=lambda: None)
    fake_next_engine = SimpleNamespace(dispose=lambda: None)

    monkeypatch.setattr(storage_db, "engine", fake_previous_engine)
    monkeypatch.setattr(
        storage_db,
        "_create_engine_with_fallback",
        lambda database_url: (created_urls.append(database_url) or database_url, fake_next_engine),
    )
    monkeypatch.setattr(storage_db, "_create_session_factory", lambda active_engine: ("session-factory", active_engine))

    try:
        configured = storage_db.configure_database(
            "mysql://user:secret@localhost:3306/sopotek_trading?chartset=utf8mb4"
        )

        assert configured == "mysql+pymysql://user:secret@localhost:3306/sopotek_trading?charset=utf8mb4"
        assert created_urls == [configured]
        assert storage_db.DATABASE_URL == configured
        assert os.environ["SOPOTEK_DATABASE_URL"] == configured
    finally:
        storage_db.engine = previous_engine
        storage_db.SessionLocal = previous_session_local
        storage_db.DATABASE_URL = previous_url
        if previous_env is None:
            os.environ.pop("SOPOTEK_DATABASE_URL", None)
        else:
            os.environ["SOPOTEK_DATABASE_URL"] = previous_env


def test_configure_database_falls_back_to_sqlite_when_driver_is_missing(monkeypatch):
    created_urls = []
    previous_engine = storage_db.engine
    previous_session_local = storage_db.SessionLocal
    previous_url = storage_db.DATABASE_URL
    previous_env = os.environ.get("SOPOTEK_DATABASE_URL")
    original_create_engine = storage_db.create_engine

    fake_previous_engine = SimpleNamespace(dispose=lambda: None)

    def _fake_create_engine(database_url, *args, **kwargs):
        normalized = storage_db.normalize_database_url(database_url)
        created_urls.append(normalized)
        if normalized.startswith("postgresql+psycopg://"):
            error = ModuleNotFoundError("No module named 'psycopg'")
            error.name = "psycopg"
            raise error
        return original_create_engine(normalized, *args, **kwargs)

    monkeypatch.setattr(storage_db, "engine", fake_previous_engine)
    monkeypatch.setattr(storage_db, "create_engine", _fake_create_engine)

    try:
        configured = storage_db.configure_database(
            "postgresql+psycopg://user:secret@localhost:5432/sopotek_trading"
        )

        assert configured == storage_db.DEFAULT_DATABASE_URL
        assert created_urls[0] == "postgresql+psycopg://user:secret@localhost:5432/sopotek_trading"
        assert created_urls[1] == storage_db.DEFAULT_DATABASE_URL
        assert storage_db.DATABASE_URL == storage_db.DEFAULT_DATABASE_URL
        assert os.environ["SOPOTEK_DATABASE_URL"] == "postgresql+psycopg://user:secret@localhost:5432/sopotek_trading"
    finally:
        storage_db.engine = previous_engine
        storage_db.SessionLocal = previous_session_local
        storage_db.DATABASE_URL = previous_url
        storage_db.create_engine = original_create_engine
        if previous_env is None:
            os.environ.pop("SOPOTEK_DATABASE_URL", None)
        else:
            os.environ["SOPOTEK_DATABASE_URL"] = previous_env


def test_storage_metadata_compiles_for_mysql():
    from storage import agent_decision_repository  # noqa: F401
    from storage import equity_repository  # noqa: F401
    from storage import market_data_repository  # noqa: F401
    from storage import paper_trade_learning_repository  # noqa: F401
    from storage import trade_audit_repository  # noqa: F401
    from storage import trade_repository  # noqa: F401
    from sopotek.storage import repository as quant_repository  # noqa: F401

    expected_tables = {
        "agent_decisions",
        "candles",
        "equity_snapshots",
        "paper_trade_events",
        "paper_trade_records",
        "quant_feature_vectors",
        "quant_model_scores",
        "quant_performance_metrics",
        "quant_trade_feedback",
        "quant_trade_journal_entries",
        "quant_trade_journal_summaries",
        "trade_audits",
        "trades",
    }

    compiled_tables = set()
    for table in storage_db.Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert ddl.lstrip().startswith("CREATE TABLE")
        compiled_tables.add(table.name)

    assert expected_tables.issubset(compiled_tables)
