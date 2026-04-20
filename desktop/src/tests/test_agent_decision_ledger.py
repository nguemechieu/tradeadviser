import logging
import os
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "test_agent_decision_ledger.sqlite3"
os.environ["SOPOTEK_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from storage import database as storage_db
from storage.agent_decision_repository import AgentDecisionRepository


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


def test_agent_decision_repository_round_trips_latest_symbol_chain():
    repo = AgentDecisionRepository()
    repo.save_decision(
        agent_name="SignalAgent",
        stage="selected",
        symbol="EUR/USD",
        decision_id="decision-1",
        exchange="paper",
        account_label="Demo",
        strategy_name="EMA Cross",
        timeframe="4h",
        side="buy",
        confidence=0.82,
        reason="signal ready",
        payload={"strategy_name": "EMA Cross", "timeframe": "4h"},
        timestamp="2026-03-17T09:30:00+00:00",
    )
    repo.save_decision(
        agent_name="RiskAgent",
        stage="approved",
        symbol="EUR/USD",
        decision_id="decision-1",
        exchange="paper",
        account_label="Demo",
        strategy_name="EMA Cross",
        timeframe="4h",
        side="buy",
        approved=True,
        reason="approved",
        payload={"approved": True, "strategy_name": "EMA Cross", "timeframe": "4h"},
        timestamp="2026-03-17T09:30:02+00:00",
    )
    repo.save_decision(
        agent_name="SignalAgent",
        stage="selected",
        symbol="EUR/USD",
        decision_id="decision-0",
        exchange="paper",
        account_label="Demo",
        strategy_name="Trend Following",
        timeframe="1h",
        side="sell",
        reason="older chain",
        payload={"strategy_name": "Trend Following", "timeframe": "1h"},
        timestamp="2026-03-17T08:00:00+00:00",
    )

    chain = repo.latest_chain_for_symbol("EUR/USD", limit=10, exchange="paper", account_label="Demo")

    assert len(chain) == 2
    assert chain[0].decision_id == "decision-1"
    assert chain[0].agent_name == "SignalAgent"
    assert chain[1].agent_name == "RiskAgent"


def test_app_controller_reads_agent_decision_chain_and_summary_from_repository():
    repo = AgentDecisionRepository()
    repo.save_decision(
        agent_name="SignalAgent",
        stage="selected",
        symbol="BTC/USDT",
        decision_id="decision-7",
        exchange="paper",
        account_label="Demo",
        strategy_name="MACD Trend",
        timeframe="4h",
        side="buy",
        confidence=0.91,
        reason="signal ready",
        payload={"strategy_name": "MACD Trend", "timeframe": "4h", "side": "buy", "confidence": 0.91},
        timestamp="2026-03-17T10:00:00+00:00",
    )
    repo.save_decision(
        agent_name="RiskAgent",
        stage="approved",
        symbol="BTC/USDT",
        decision_id="decision-7",
        exchange="paper",
        account_label="Demo",
        strategy_name="MACD Trend",
        timeframe="4h",
        side="buy",
        approved=True,
        reason="within limits",
        payload={"approved": True, "strategy_name": "MACD Trend", "timeframe": "4h", "side": "buy"},
        timestamp="2026-03-17T10:00:02+00:00",
    )
    repo.save_decision(
        agent_name="ExecutionAgent",
        stage="filled",
        symbol="BTC/USDT",
        decision_id="decision-7",
        exchange="paper",
        account_label="Demo",
        strategy_name="MACD Trend",
        timeframe="4h",
        side="buy",
        approved=True,
        reason="submitted",
        payload={"approved": True, "strategy_name": "MACD Trend", "timeframe": "4h", "side": "buy"},
        timestamp="2026-03-17T10:00:04+00:00",
    )

    controller = AppController.__new__(AppController)
    controller.logger = logging.getLogger("test.agent.ledger")
    controller.agent_decision_repository = repo
    controller.trading_system = None
    controller._active_exchange_code = lambda: "paper"
    controller.current_account_label = lambda: "Demo"
    controller._normalize_strategy_symbol_key = lambda symbol: str(symbol or "").strip().upper().replace("-", "/").replace("_", "/")

    chain = controller.latest_agent_decision_chain_for_symbol("BTC/USDT", limit=10)
    overview = controller.latest_agent_decision_overview_for_symbol("BTC/USDT")

    assert len(chain) == 3
    assert chain[0]["agent_name"] == "SignalAgent"
    assert chain[-1]["agent_name"] == "ExecutionAgent"
    assert overview["strategy_name"] == "MACD Trend"
    assert overview["timeframe"] == "4h"
    assert overview["approved"] == 1
    assert overview["steps"] == 3
