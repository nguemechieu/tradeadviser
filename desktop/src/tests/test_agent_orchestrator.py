import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.signal_agent import SignalAgent
from agents.signal_fanout import merge_signal_agent_results
from core.sopotek_trading import SopotekTrading
from engines.risk_engine import RiskEngine
from event_bus.event_bus import EventBus
from event_bus.event_types import EventType


class DummyBroker:
    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=100):
        return []

    async def fetch_balance(self):
        return {"total": {"USDT": 10000}}

    async def create_order(self, *args, **kwargs):
        return {"status": "filled"}


class FakeDataset:
    def __init__(self, frame):
        self.frame = frame
        self.empty = frame.empty

    def to_candles(self):
        rows = []
        for row in self.frame.itertuples(index=False):
            rows.append([row.timestamp, row.open, row.high, row.low, row.close, row.volume])
        return rows


def _sample_frame():
    return pd.DataFrame(
        [
            {"timestamp": 1, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
            {"timestamp": 2, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 12.0},
        ]
    )


def _controller():
    return SimpleNamespace(
        broker=DummyBroker(),
        symbols=["BTC/USDT"],
        time_frame="1h",
        limit=200,
        strategy_name="Trend Following",
        strategy_params={},
        max_portfolio_risk=0.10,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.10,
        max_gross_exposure_pct=2.0,
        balances={"total": {"USDT": 10000}},
        initial_capital=10000,
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
        publish_ai_signal=lambda *args, **kwargs: None,
        publish_strategy_debug=lambda *args, **kwargs: None,
    )


def test_agent_orchestrator_executes_trade_through_specialized_agents():
    controller = _controller()
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "reason": "submitted"}

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.5,
        "confidence": 0.84,
        "reason": "agent pipeline breakout",
        "strategy_name": "Trend Following",
    }

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["symbol"] == "BTC/USDT"
    assert captured["side"] == "buy"
    agent_names = [entry["agent"] for entry in trading.agent_memory_snapshot(limit=10)]
    assert "SignalAgent" in agent_names
    assert "RegimeAgent" in agent_names
    assert "PortfolioAgent" in agent_names
    assert "RiskAgent" in agent_names
    assert "ExecutionAgent" in agent_names
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "execution_manager"


def test_agent_orchestrator_stops_when_risk_agent_rejects_trade():
    controller = _controller()
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = SimpleNamespace(
        account_equity=10000,
        adjust_trade=lambda _price, _amount: (False, 0.0, "risk agent blocked the setup"),
    )
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        raise AssertionError("execution should not run after a risk rejection")

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.5,
        "confidence": 0.84,
        "reason": "agent pipeline breakout",
        "strategy_name": "Trend Following",
    }

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result is None
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "risk_engine"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["status"] == "rejected"
    latest = trading.agent_memory.latest("RiskAgent")
    assert latest is not None
    assert latest["stage"] == "rejected"


def test_agent_orchestrator_persists_agent_ledger_entries_when_repository_is_available():
    saved = []

    class Repo:
        def save_decision(self, **kwargs):
            saved.append(dict(kwargs))
            return SimpleNamespace(**kwargs)

    controller = _controller()
    controller.agent_decision_repository = Repo()
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        return {"status": "filled", "reason": "submitted"}

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.5,
        "confidence": 0.84,
        "reason": "agent pipeline breakout",
        "strategy_name": "Trend Following",
    }

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert len(saved) >= 5
    assert {row["agent_name"] for row in saved} >= {"SignalAgent", "RegimeAgent", "PortfolioAgent", "RiskAgent", "ExecutionAgent"}
    assert len({row["decision_id"] for row in saved if row.get("decision_id")}) == 1
    assert all(row.get("symbol") == "BTC/USDT" for row in saved)


def test_event_bus_dispatch_once_routes_typed_publish_to_async_handler():
    async def scenario():
        bus = EventBus()
        received = {}

        async def handler(event):
            received["type"] = event.type
            received["data"] = dict(event.data)

        bus.subscribe(EventType.MARKET_DATA, handler)
        await bus.publish(EventType.MARKET_DATA, {"symbol": "BTC/USDT", "timeframe": "15m"})
        await bus.dispatch_once()
        return received

    received = asyncio.run(scenario())

    assert received["type"] == EventType.MARKET_DATA
    assert received["data"] == {"symbol": "BTC/USDT", "timeframe": "15m"}


def test_process_symbol_uses_event_driven_runtime_when_no_custom_handler():
    controller = _controller()
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured["order"] = dict(kwargs)
        return {"status": "filled", "reason": "submitted"}

    async def fail_legacy_path(_context):
        raise AssertionError("legacy orchestrator path should not run")

    original_runtime = trading.event_driven_runtime.process_market_data

    async def tracked_runtime(context, timeout=None):
        captured["runtime_symbol"] = context["symbol"]
        return await original_runtime(context, timeout=timeout)

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.agent_orchestrator.run = fail_legacy_path
    trading.event_driven_runtime.process_market_data = tracked_runtime
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.5,
        "confidence": 0.84,
        "reason": "event runtime breakout",
        "strategy_name": "Trend Following",
    }

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["runtime_symbol"] == "BTC/USDT"
    assert captured["order"]["symbol"] == "BTC/USDT"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "execution_manager"


def test_event_runtime_aggregates_multiple_signal_agents_and_selects_best_candidate():
    controller = _controller()
    controller.max_signal_agents = 2
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.30, "score": 4.0, "rank": 1},
        {"strategy_name": "EMA Cross", "weight": 0.70, "score": 9.0, "rank": 2},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        return {"status": "filled", "reason": "submitted", "strategy_name": kwargs.get("strategy_name")}

    calls = []

    def fake_generate_signal(**kwargs):
        strategy_name = kwargs["strategy_name"]
        calls.append(strategy_name)
        if strategy_name == "Trend Following":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.90,
                "reason": "primary candidate",
                "strategy_name": strategy_name,
            }
        if strategy_name == "EMA Cross":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.40,
                "confidence": 0.65,
                "reason": "weighted candidate",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert calls == ["Trend Following", "EMA Cross"]
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["stage"] == "selected"
    assert latest["payload"]["strategy_name"] == "EMA Cross"
    assert latest["payload"]["candidate_count"] == 2
    assert any(entry["agent"] == "SignalAgent2" and entry["stage"] == "candidate" for entry in trading.agent_memory_snapshot(limit=20))


def test_signal_consensus_agent_filters_candidates_to_majority_side():
    controller = _controller()
    controller.max_signal_agents = 3
    controller.minimum_signal_votes = 2
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.90, "score": 10.0, "rank": 1},
        {"strategy_name": "EMA Cross", "weight": 0.60, "score": 7.0, "rank": 2},
        {"strategy_name": "Mean Reversion", "weight": 0.50, "score": 6.0, "rank": 3},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        return {"status": "filled", "reason": "submitted", "side": kwargs.get("side"), "strategy_name": kwargs.get("strategy_name")}

    def fake_generate_signal(**kwargs):
        strategy_name = kwargs["strategy_name"]
        if strategy_name == "Trend Following":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.95,
                "reason": "strong solo buy",
                "strategy_name": strategy_name,
            }
        if strategy_name == "EMA Cross":
            return {
                "symbol": "BTC/USDT",
                "side": "sell",
                "amount": 0.30,
                "confidence": 0.60,
                "reason": "sell vote one",
                "strategy_name": strategy_name,
            }
        if strategy_name == "Mean Reversion":
            return {
                "symbol": "BTC/USDT",
                "side": "sell",
                "amount": 0.35,
                "confidence": 0.62,
                "reason": "sell vote two",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    consensus = trading.agent_memory.latest("SignalConsensusAgent")
    assert consensus is not None
    assert consensus["stage"] == "majority"
    assert consensus["payload"]["side"] == "sell"
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["payload"]["strategy_name"] in {"EMA Cross", "Mean Reversion"}
    assert latest["payload"]["consensus_side"] == "sell"
    assert latest["payload"]["consensus_status"] == "majority"


def test_signal_consensus_scales_vote_threshold_to_available_candidates():
    controller = _controller()
    controller.max_signal_agents = 3
    controller.minimum_signal_votes = 2
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.90, "score": 10.0, "rank": 1},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "reason": "submitted", "side": kwargs.get("side")}

    def fake_generate_signal(**kwargs):
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.25,
            "confidence": 0.88,
            "reason": "single valid alpha",
            "strategy_name": kwargs["strategy_name"],
        }

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["symbol"] == "BTC/USDT"
    assert captured["side"] == "buy"
    assert captured["consensus_status"] == "unanimous"
    consensus = trading.agent_memory.latest("SignalConsensusAgent")
    assert consensus is not None
    assert consensus["stage"] == "unanimous"
    assert consensus["payload"]["vote_count"] == 1
    assert consensus["payload"]["minimum_votes"] == 1
    assert consensus["payload"]["configured_minimum_votes"] == 2
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["stage"] == "selected"


def test_split_signal_consensus_holds_and_skips_execution():
    controller = _controller()
    controller.max_signal_agents = 2
    controller.minimum_signal_votes = 2
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.60, "score": 8.0, "rank": 1},
        {"strategy_name": "EMA Cross", "weight": 0.40, "score": 7.0, "rank": 2},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        raise AssertionError("execution should not run when consensus is split")

    def fake_generate_signal(**kwargs):
        strategy_name = kwargs["strategy_name"]
        if strategy_name == "Trend Following":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.84,
                "reason": "buy vote",
                "strategy_name": strategy_name,
            }
        if strategy_name == "EMA Cross":
            return {
                "symbol": "BTC/USDT",
                "side": "sell",
                "amount": 0.25,
                "confidence": 0.82,
                "reason": "sell vote",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result is None
    consensus = trading.agent_memory.latest("SignalConsensusAgent")
    assert consensus is not None
    assert consensus["stage"] == "split"
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["stage"] == "hold"
    assert "disagreed" in str(latest["payload"]["reason"]).lower()
    snapshot = trading.pipeline_status_snapshot()["BTC/USDT"]
    assert snapshot["stage"] == "signal_engine"
    assert snapshot["status"] == "hold"


def test_merge_signal_agent_results_deduplicates_same_candidate_fingerprint():
    weaker = {
        "agent_name": "SignalAgent",
        "signal": {
            "strategy_name": "EMA Cross",
            "timeframe": "15m",
            "side": "buy",
            "confidence": 0.61,
            "strategy_assignment_weight": 0.50,
            "adaptive_score": 0.31,
        },
    }
    stronger = {
        "agent_name": "SignalAgent",
        "signal": {
            "strategy_name": "EMA Cross",
            "timeframe": "15m",
            "side": "buy",
            "confidence": 0.74,
            "strategy_assignment_weight": 0.50,
            "adaptive_score": 0.42,
        },
    }

    merged = merge_signal_agent_results(
        {"signal_candidates": [weaker]},
        [{"signal_candidates": [stronger], "assigned_strategies": []}],
    )

    assert len(merged["signal_candidates"]) == 1
    assert merged["signal_candidates"][0]["signal"]["confidence"] == 0.74


def test_signal_agents_run_in_parallel_during_market_processing():
    controller = _controller()
    controller.max_signal_agents = 2
    controller.minimum_signal_votes = 1
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.40, "score": 6.0, "rank": 1},
        {"strategy_name": "EMA Cross", "weight": 0.60, "score": 7.0, "rank": 2},
    ]
    concurrency = {"active": 0, "peak": 0}
    gate = asyncio.Event()

    async def apply_news_bias(symbol, signal):
        concurrency["active"] += 1
        concurrency["peak"] = max(concurrency["peak"], concurrency["active"])
        if concurrency["active"] >= 2:
            gate.set()
        await asyncio.wait_for(gate.wait(), timeout=0.25)
        concurrency["active"] -= 1
        return signal

    controller.apply_news_bias_to_signal = apply_news_bias
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        return {"status": "filled", "reason": "submitted"}

    def fake_generate_signal(**kwargs):
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.25,
            "confidence": 0.70 if kwargs["strategy_name"] == "Trend Following" else 0.75,
            "reason": kwargs["strategy_name"],
            "strategy_name": kwargs["strategy_name"],
        }

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(asyncio.wait_for(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50), timeout=0.5))

    assert result["status"] == "filled"
    assert concurrency["peak"] >= 2


def test_adaptive_trade_feedback_biases_candidate_selection_and_execution_metadata():
    profitable_history = [
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=18.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=12.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=9.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=6.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=-8.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=-5.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=-4.0),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=-3.0),
    ]

    controller = _controller()
    controller.max_signal_agents = 2
    controller.trade_repository = SimpleNamespace(get_trades=lambda limit=200: profitable_history[:limit])
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.45, "score": 9.0, "rank": 1, "timeframe": "15m"},
        {"strategy_name": "EMA Cross", "weight": 0.55, "score": 8.0, "rank": 2, "timeframe": "15m"},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "reason": "submitted", "strategy_name": kwargs.get("strategy_name")}

    def fake_generate_signal(**kwargs):
        strategy_name = kwargs["strategy_name"]
        if strategy_name == "Trend Following":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.90,
                "reason": "strong raw confidence",
                "strategy_name": strategy_name,
            }
        if strategy_name == "EMA Cross":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.72,
                "reason": "adaptive winner",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["strategy_name"] == "EMA Cross"
    assert captured["timeframe"] == "15m"
    assert captured["signal_source_agent"] == "SignalAgent2"
    assert captured["consensus_status"] == "unanimous"
    assert float(captured["adaptive_weight"]) > 1.0
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["payload"]["strategy_name"] == "EMA Cross"
    assert float(latest["payload"]["adaptive_weight"]) > 1.0
    assert int(latest["payload"]["adaptive_sample_size"]) == 4


def test_adaptive_trade_feedback_uses_active_exchange_only():
    paper_history = [
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=14.0, exchange="paper"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=11.0, exchange="paper"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=8.0, exchange="paper"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="Trend Following", timeframe="15m", pnl=6.0, exchange="paper"),
    ]
    coinbase_history = [
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=18.0, exchange="coinbase"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=16.0, exchange="coinbase"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=12.0, exchange="coinbase"),
        SimpleNamespace(symbol="BTC/USDT", strategy_name="EMA Cross", timeframe="15m", pnl=9.0, exchange="coinbase"),
    ]
    mixed_history = paper_history + coinbase_history

    controller = _controller()
    controller.max_signal_agents = 2
    controller._active_exchange_code = lambda: "paper"
    controller.trade_repository = SimpleNamespace(
        get_trades=lambda limit=200, exchange=None: (
            paper_history[:limit]
            if exchange == "paper"
            else mixed_history[:limit]
        )
    )
    controller.assigned_strategies_for_symbol = lambda symbol: [
        {"strategy_name": "Trend Following", "weight": 0.45, "score": 9.0, "rank": 1, "timeframe": "15m"},
        {"strategy_name": "EMA Cross", "weight": 0.55, "score": 8.0, "rank": 2, "timeframe": "15m"},
    ]
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "reason": "submitted", "strategy_name": kwargs.get("strategy_name")}

    def fake_generate_signal(**kwargs):
        strategy_name = kwargs["strategy_name"]
        if strategy_name == "Trend Following":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.80,
                "reason": "paper venue winner",
                "strategy_name": strategy_name,
            }
        if strategy_name == "EMA Cross":
            return {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.70,
                "reason": "other venue winner",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.execution_manager.execute = fake_execute
    trading.signal_engine.generate_signal = fake_generate_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["strategy_name"] == "Trend Following"
    latest = trading.agent_memory.latest("SignalAggregationAgent")
    assert latest is not None
    assert latest["payload"]["strategy_name"] == "Trend Following"
    assert latest["payload"]["adaptive_sample_size"] == 4


def test_signal_agent_process_supports_async_selectors():
    async def selector(symbol, candles, dataset):
        await asyncio.sleep(0)
        return (
            {
                "symbol": symbol,
                "side": "buy",
                "amount": 0.25,
                "confidence": 0.81,
                "reason": "async selector",
                "strategy_name": "Trend Following",
            },
            [{"strategy_name": "Trend Following", "timeframe": "1h"}],
        )

    agent = SignalAgent(selector=selector)

    async def scenario():
        return await agent.process({"symbol": "BTC/USDT", "candles": [], "dataset": None, "decision_id": "d-1"})

    result = asyncio.run(scenario())

    assert result["signal"]["side"] == "buy"
    assert result["signal"]["strategy_name"] == "Trend Following"
    assert result["assigned_strategies"] == [{"strategy_name": "Trend Following", "timeframe": "1h"}]


def test_signal_agent_process_treats_missing_signal_as_hold():
    async def selector(symbol, candles, dataset):
        await asyncio.sleep(0)
        return (
            None,
            [{"strategy_name": "Trend Following", "timeframe": "1h"}],
        )

    agent = SignalAgent(selector=selector)

    async def scenario():
        return await agent.process({"symbol": "AUD/HKD", "candles": [], "dataset": None, "decision_id": "d-2"})

    result = asyncio.run(scenario())

    assert result["signal"] is None
    assert result["signal_hold_reason"] == "No entry signal on the latest scan."
    assert result["assigned_strategies"] == [{"strategy_name": "Trend Following", "timeframe": "1h"}]
    assert result.get("halt_pipeline") is None


def test_sopotek_trading_stop_can_wait_for_signal_executor_shutdown():
    trading = SopotekTrading(controller=_controller())
    waits = []
    trading.orchestrator = None
    trading.event_driven_runtime = None
    trading.execution_manager = None
    trading._shutdown_signal_selection_executor = lambda wait=False: waits.append(wait)

    asyncio.run(trading.stop(wait_for_background_workers=True))

    assert waits == [True]
