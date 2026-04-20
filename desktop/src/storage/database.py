import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("storage.database")

DEFAULT_DATABASE_URL = f"sqlite:///{(DATA_DIR / 'sopotek_trading.db').as_posix()}"
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SOPOTEK_SQLITE_BUSY_TIMEOUT_MS", "30000"))
SQLITE_LOCK_RETRY_ATTEMPTS = max(int(os.getenv("SOPOTEK_SQLITE_LOCK_RETRY_ATTEMPTS", "4")), 1)
SQLITE_LOCK_RETRY_DELAY_SECONDS = max(float(os.getenv("SOPOTEK_SQLITE_LOCK_RETRY_DELAY_SECONDS", "0.25")), 0.0)
SQLITE_JOURNAL_MODE = str(os.getenv("SOPOTEK_SQLITE_JOURNAL_MODE", "wal") or "wal").strip().lower() or "wal"


def _normalize_common_database_url_typos(database_url):
    candidate = str(database_url or "").strip()
    if not candidate:
        return candidate

    parts = urlsplit(candidate)
    if not parts.scheme:
        return candidate

    normalized_query = []
    query_changed = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if str(key).lower() == "chartset":
            normalized_query.append(("charset", value))
            query_changed = True
        else:
            normalized_query.append((key, value))

    scheme = str(parts.scheme or "").strip().lower()
    normalized_scheme = parts.scheme
    if scheme in {"mysql", "mysql+pymsql"}:
        normalized_scheme = "mysql+pymysql"
    if not query_changed and normalized_scheme == parts.scheme:
        return candidate

    return urlunsplit(
        (
            normalized_scheme,
            parts.netloc,
            parts.path,
            urlencode(normalized_query, doseq=True),
            parts.fragment,
        )
    )


def normalize_database_url(database_url=None):
    raw_value = str(database_url or "").strip()
    if not raw_value:
        return DEFAULT_DATABASE_URL
    return _normalize_common_database_url_typos(raw_value)


def is_sqlite_url(database_url=None):
    return normalize_database_url(database_url or DATABASE_URL).startswith("sqlite")


def _sqlite_supports_wal(database_url):
    normalized = normalize_database_url(database_url)
    lowered = normalized.lower()
    return (
        SQLITE_JOURNAL_MODE == "wal"
        and lowered.startswith("sqlite")
        and ":memory:" not in lowered
        and "mode=memory" not in lowered
    )


def _build_connect_args(database_url):
    normalized = normalize_database_url(database_url)
    if is_sqlite_url(normalized):
        return {
            "check_same_thread": False,
            "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0,
        }
    return {}


def _apply_sqlite_pragmas(dbapi_connection, _connection_record, *, enable_wal=True):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA foreign_keys=ON")
        if not enable_wal:
            return

        wal_enabled = False
        try:
            result = cursor.execute("PRAGMA journal_mode=WAL")
            row = None
            if hasattr(result, "fetchone"):
                row = result.fetchone()
            elif hasattr(cursor, "fetchone"):
                row = cursor.fetchone()
            journal_mode = str((row[0] if row else "wal") or "").strip().lower()
            wal_enabled = journal_mode == "wal"
        except Exception:
            wal_enabled = False

        if wal_enabled:
            cursor.execute("PRAGMA synchronous=NORMAL")
        else:
            cursor.execute("PRAGMA journal_mode=DELETE")
    finally:
        cursor.close()


def _configure_sqlite_connection(active_engine, database_url):
    if not is_sqlite_url(database_url):
        return

    enable_wal = _sqlite_supports_wal(database_url)

    @event.listens_for(active_engine, "connect")
    def _on_sqlite_connect(dbapi_connection, connection_record):
        _apply_sqlite_pragmas(
            dbapi_connection,
            connection_record,
            enable_wal=enable_wal,
        )


def _is_sqlite_locked_error(error, database_url=None):
    if not is_sqlite_url(database_url):
        return False
    return "database is locked" in str(error).lower()


def _run_with_sqlite_lock_retry(operation, *, database_url=None):
    active_url = normalize_database_url(database_url or DATABASE_URL)
    delay_seconds = SQLITE_LOCK_RETRY_DELAY_SECONDS
    last_error = None

    for attempt in range(SQLITE_LOCK_RETRY_ATTEMPTS):
        try:
            return operation()
        except OperationalError as exc:
            last_error = exc
            if not _is_sqlite_locked_error(exc, active_url) or attempt >= SQLITE_LOCK_RETRY_ATTEMPTS - 1:
                raise
            if delay_seconds > 0:
                time.sleep(delay_seconds * (attempt + 1))

    if last_error is not None:
        raise last_error
    return operation()


def _expected_driver_modules(database_url):
    normalized = normalize_database_url(database_url).lower()
    if normalized.startswith("postgresql+psycopg://"):
        return {"psycopg"}
    if normalized.startswith("postgresql+psycopg2://"):
        return {"psycopg2"}
    if normalized.startswith("postgresql://") or normalized.startswith("postgres://"):
        return {"psycopg", "psycopg2"}
    if normalized.startswith("mysql+pymysql://") or normalized.startswith("mysql://"):
        return {"pymysql"}
    return set()


def _is_missing_database_driver(error, database_url):
    if not isinstance(error, ModuleNotFoundError):
        return False

    expected = _expected_driver_modules(database_url)
    if not expected:
        return False

    missing_name = str(getattr(error, "name", "") or "").strip()
    if missing_name and missing_name in expected:
        return True

    message = str(error or "")
    return any(f"No module named '{module}'" in message for module in expected)


def _instantiate_engine(database_url):
    normalized = normalize_database_url(database_url)
    return create_engine(
        normalized,
        echo=False,
        future=True,
        pool_pre_ping=not is_sqlite_url(normalized),
        connect_args=_build_connect_args(normalized),
    )


def _create_engine_with_fallback(database_url):
    normalized = normalize_database_url(database_url)
    resolved = normalized
    try:
        active_engine = _instantiate_engine(normalized)
    except ModuleNotFoundError as exc:
        if not _is_missing_database_driver(exc, normalized):
            raise
        resolved = DEFAULT_DATABASE_URL
        logger.warning(
            "Database driver for %s is unavailable (%s); falling back to local SQLite at %s",
            normalized,
            exc,
            resolved,
        )
        active_engine = _instantiate_engine(resolved)

    _configure_sqlite_connection(active_engine, resolved)
    return resolved, active_engine


def _create_engine(database_url):
    _, active_engine = _create_engine_with_fallback(database_url)
    return active_engine


def _create_session_factory(active_engine):
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=active_engine,
        expire_on_commit=False,
        future=True,
    )


DATABASE_URL, engine = _create_engine_with_fallback(os.getenv("SOPOTEK_DATABASE_URL", DEFAULT_DATABASE_URL))
SessionLocal = _create_session_factory(engine)

Base = declarative_base()
_MODELS_IMPORTED = False


def _table_columns(table_name):
    def _inspect_columns():
        inspector = inspect(engine)
        if not inspector.has_table(table_name):
            return set()
        return {column["name"] for column in inspector.get_columns(table_name)}

    return _run_with_sqlite_lock_retry(_inspect_columns)


def _ensure_sqlite_column(table_name, column_name, ddl):
    if not is_sqlite_url():
        return

    existing = _table_columns(table_name)
    if column_name in existing:
        return

    def _alter_table():
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

    _run_with_sqlite_lock_retry(_alter_table)


def _migrate_sqlite_schema():
    # Existing local DBs may come from the earlier lightweight schema.
    _ensure_sqlite_column("candles", "exchange", "exchange VARCHAR")
    _ensure_sqlite_column("candles", "timeframe", "timeframe VARCHAR")
    _ensure_sqlite_column("candles", "timestamp_ms", "timestamp_ms BIGINT")

    _ensure_sqlite_column("trades", "exchange", "exchange VARCHAR")
    _ensure_sqlite_column("trades", "order_id", "order_id VARCHAR")
    _ensure_sqlite_column("trades", "order_type", "order_type VARCHAR")
    _ensure_sqlite_column("trades", "status", "status VARCHAR")
    _ensure_sqlite_column("trades", "source", "source VARCHAR")
    _ensure_sqlite_column("trades", "pnl", "pnl FLOAT")
    _ensure_sqlite_column("trades", "strategy_name", "strategy_name VARCHAR")
    _ensure_sqlite_column("trades", "reason", "reason VARCHAR")
    _ensure_sqlite_column("trades", "confidence", "confidence FLOAT")
    _ensure_sqlite_column("trades", "expected_price", "expected_price FLOAT")
    _ensure_sqlite_column("trades", "spread_bps", "spread_bps FLOAT")
    _ensure_sqlite_column("trades", "slippage_bps", "slippage_bps FLOAT")
    _ensure_sqlite_column("trades", "fee", "fee FLOAT")
    _ensure_sqlite_column("trades", "stop_loss", "stop_loss FLOAT")
    _ensure_sqlite_column("trades", "take_profit", "take_profit FLOAT")
    _ensure_sqlite_column("trades", "setup", "setup TEXT")
    _ensure_sqlite_column("trades", "outcome", "outcome TEXT")
    _ensure_sqlite_column("trades", "lessons", "lessons TEXT")
    _ensure_sqlite_column("trades", "timeframe", "timeframe VARCHAR")
    _ensure_sqlite_column("trades", "signal_source_agent", "signal_source_agent VARCHAR")
    _ensure_sqlite_column("trades", "consensus_status", "consensus_status VARCHAR")
    _ensure_sqlite_column("trades", "adaptive_weight", "adaptive_weight FLOAT")
    _ensure_sqlite_column("trades", "adaptive_score", "adaptive_score FLOAT")

    _ensure_sqlite_column("equity_snapshots", "exchange", "exchange VARCHAR")
    _ensure_sqlite_column("equity_snapshots", "account_label", "account_label VARCHAR")
    _ensure_sqlite_column("equity_snapshots", "equity", "equity FLOAT")
    _ensure_sqlite_column("equity_snapshots", "balance", "balance FLOAT")
    _ensure_sqlite_column("equity_snapshots", "free_margin", "free_margin FLOAT")
    _ensure_sqlite_column("equity_snapshots", "used_margin", "used_margin FLOAT")
    _ensure_sqlite_column("equity_snapshots", "payload_json", "payload_json TEXT")
    _ensure_sqlite_column("equity_snapshots", "timestamp", "timestamp DATETIME")

    _ensure_sqlite_column("agent_decisions", "decision_id", "decision_id VARCHAR")
    _ensure_sqlite_column("agent_decisions", "exchange", "exchange VARCHAR")
    _ensure_sqlite_column("agent_decisions", "account_label", "account_label VARCHAR")
    _ensure_sqlite_column("agent_decisions", "symbol", "symbol VARCHAR")
    _ensure_sqlite_column("agent_decisions", "agent_name", "agent_name VARCHAR")
    _ensure_sqlite_column("agent_decisions", "stage", "stage VARCHAR")
    _ensure_sqlite_column("agent_decisions", "strategy_name", "strategy_name VARCHAR")
    _ensure_sqlite_column("agent_decisions", "timeframe", "timeframe VARCHAR")
    _ensure_sqlite_column("agent_decisions", "side", "side VARCHAR")
    _ensure_sqlite_column("agent_decisions", "confidence", "confidence FLOAT")
    _ensure_sqlite_column("agent_decisions", "approved", "approved INTEGER")
    _ensure_sqlite_column("agent_decisions", "reason", "reason VARCHAR")
    _ensure_sqlite_column("agent_decisions", "payload_json", "payload_json TEXT")
    _ensure_sqlite_column("agent_decisions", "timestamp", "timestamp DATETIME")


def init_database():
    global _MODELS_IMPORTED

    # Import models before create_all so SQLAlchemy sees the mapped tables.
    if not _MODELS_IMPORTED:
        from storage import agent_decision_repository  # noqa: F401
        from storage import equity_repository  # noqa: F401
        from storage import market_data_repository  # noqa: F401
        from storage import paper_trade_learning_repository  # noqa: F401
        if "storage.repository" not in sys.modules:
            from storage import repository as sopotek_quant_repository  # noqa: F401
        from storage import trade_audit_repository  # noqa: F401
        from storage import trade_repository  # noqa: F401

        _MODELS_IMPORTED = True

    _run_with_sqlite_lock_retry(lambda: Base.metadata.create_all(bind=engine))
    _migrate_sqlite_schema()


def get_database_url():
    return str(DATABASE_URL or DEFAULT_DATABASE_URL)


def configure_database(database_url=None):
    global DATABASE_URL, engine, SessionLocal

    normalized = normalize_database_url(database_url)
    current = normalize_database_url(DATABASE_URL)
    if normalized == current:
        return get_database_url()

    previous_engine = engine
    resolved_url, engine = _create_engine_with_fallback(normalized)
    SessionLocal = _create_session_factory(engine)
    DATABASE_URL = resolved_url
    os.environ["SOPOTEK_DATABASE_URL"] = normalized

    try:
        previous_engine.dispose()
    except Exception:
        pass

    return get_database_url()
