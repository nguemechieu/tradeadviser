import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.system_trading as sopotek_trading_module
import worker.symbol_worker as symbol_worker_module
from core.system_trading import SopotekTrading
from engines.risk_engine import RiskEngine
from worker.symbol_worker import SymbolWorker


class DummyBroker:
    hedging_supported = False

    async def fetch_ohlcv(self, _symbol, _timeframe="1h", _limit=100):
        return []

    async def fetch_balance(self):
        return {"total": {"USDT": 10000}}

    async def create_order(self, *_, **__):
        return {"status": "filled"}


class DummyOandaBroker(DummyBroker):
    exchange_name = "oanda"


class CleanupBroker(DummyBroker):
    def __init__(self, positions=None, orders=None):
        self.positions = list(positions or [])
        self.orders = list(orders or [])
        self.canceled = []

    async def fetch_positions(self, _symbols=None):
        return list(self.positions)

    async def fetch_open_orders(self, _symbol=None, _limit=None):
        return list(self.orders)

    async def cancel_order(self, order_id, symbol=None):
        self.canceled.append({"order_id": order_id, "symbol": symbol})
        return {"id": order_id, "status": "canceled", "symbol": symbol}


class ExplodingStrategy:
    def generate_signal(self, candles):
        raise AssertionError("fallback strategy path should not be used")


class ExplodingExecutionManager:
    async def execute(self, **kwargs):
        raise AssertionError("execution manager should not be called directly by SymbolWorker")


class FakeDataset:
    def __init__(self, frame):
        self.frame = frame
        self.empty = frame.empty

    def to_candles(self):
        return [
            [row.timestamp, row.open, row.high, row.low, row.close, row.volume]
            for row in self.frame.itertuples(index=False)
        ]


def _sample_frame():
    return pd.DataFrame(
        [
            {"timestamp": 1, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
            {"timestamp": 2, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 12.0},
        ]
    )


def test_symbol_worker_uses_centralized_signal_processor(monkeypatch):
    calls = []

    async def fast_sleep(_seconds):
        return None

    async def processor(symbol, timeframe=None, limit=None, publish_debug=True):
        calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "publish_debug": publish_debug,
            }
        )
        worker.running = False

    monkeypatch.setattr(symbol_worker_module.asyncio, "sleep", fast_sleep)

    worker = SymbolWorker(
        symbol="BTC/USDT",
        broker=DummyBroker(),
        strategy=ExplodingStrategy(),
        execution_manager=ExplodingExecutionManager(),
        timeframe="15m",
        limit=120,
        signal_processor=processor,
    )

    asyncio.run(worker.run())

    assert calls == [
        {
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "limit": 120,
            "publish_debug": True,
        }
    ]


def test_symbol_worker_fallback_uses_trading_system_process_signal(monkeypatch):
    calls = []

    async def fast_sleep(_seconds):
        worker.running = False
        return None

    async def fake_fetch_ohlcv(_symbol, _timeframe="1h", _limit=100):
        return [[1, 100.0, 101.0, 99.0, 100.5, 10.0]]

    async def fake_process_signal(symbol, signal, timeframe=None, regime_snapshot=None, portfolio_snapshot=None):
        calls.append(
            {
                "symbol": symbol,
                "signal": dict(signal),
                "timeframe": timeframe,
            }
        )
        worker.running = False
        return {"status": "filled"}

    class _Strategy:
        def generate_signal(self, _candles):
            return {"side": "buy", "amount": 0.5, "price": 1.1}

    controller = SimpleNamespace(
        trading_system=SimpleNamespace(process_signal=fake_process_signal),
        _safe_fetch_ohlcv=fake_fetch_ohlcv,
        publish_ai_signal=lambda *args, **kwargs: None,
        publish_strategy_debug=lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(symbol_worker_module.asyncio, "sleep", fast_sleep)

    worker = SymbolWorker(
        symbol="EUR/USD",
        broker=DummyBroker(),
        strategy=_Strategy(),
        execution_manager=ExplodingExecutionManager(),
        timeframe="5m",
        limit=120,
        controller=controller,
    )

    asyncio.run(worker.run())

    assert calls == [
        {
            "symbol": "EUR/USD",
            "signal": {"side": "buy", "amount": 0.5, "price": 1.1},
            "timeframe": "5m",
        }
    ]


def test_sopotek_trading_process_symbol_routes_through_central_pipeline():
    published_ai = []
    published_debug = []

    async def apply_news_bias(symbol, signal):
        updated = dict(signal)
        updated["reason"] = f"{signal['reason']} | news aligned"
        return updated

    controller = SimpleNamespace(
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
        publish_ai_signal=lambda symbol, signal, candles=None: published_ai.append((symbol, dict(signal), list(candles or []))),
        publish_strategy_debug=lambda symbol, signal, candles=None, features=None: published_debug.append(
            (symbol, dict(signal), list(candles or []), features)
        ),
        apply_news_bias_to_signal=apply_news_bias,
    )

    trading = SopotekTrading(controller=controller)
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(request=None, **kwargs):
        if request:
            captured.update(vars(request))
        captured.update(kwargs)
        assert captured["symbol"] == "BTC/USDT"
        assert captured["timeframe"] == "15m"
        assert captured["limit"] == 50
        return dataset

    captured = {}

    async def fake_process_signal(symbol, signal, dataset=None, timeframe=None, regime_snapshot=None, portfolio_snapshot=None):
        captured["symbol"] = symbol
        captured["signal"] = dict(signal)
        captured["dataset"] = dataset
        return {"status": "filled", "reason": "submitted"}

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset

    def fake_generate_signal(candles=None, dataset=None, strategy_name=None, symbol=None):
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.25,
            "confidence": 0.78,
            "reason": "breakout detected",
            "strategy_name": "Trend Following",
        }

    trading.signal_engine.generate_signal = fake_generate_signal
    trading.process_signal = fake_process_signal

    result = asyncio.run(trading.process_symbol("BTC/USDT", timeframe="15m", limit=50))

    assert result["status"] == "filled"
    assert captured["symbol"] == "BTC/USDT"
    assert captured["signal"]["reason"].endswith("news aligned")
    assert captured["dataset"] is dataset
    assert published_ai and published_ai[0][0] == "BTC/USDT"
    assert published_debug and published_debug[0][0] == "BTC/USDT"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "execution_manager"


def test_sopotek_trading_process_symbol_can_publish_signal_without_starting_ai_trading():
    published_ai = []
    published_debug = []

    controller = SimpleNamespace(
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
        publish_ai_signal=lambda symbol, signal, candles=None: published_ai.append((symbol, dict(signal), list(candles or []))),
        publish_strategy_debug=lambda symbol, signal, candles=None, features=None: published_debug.append(
            (symbol, dict(signal), list(candles or []), features)
        ),
    )

    trading = SopotekTrading(controller=controller)
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    async def forbidden_process_signal(*args, **kwargs):
        raise AssertionError("passive signal scans must not execute trades")

    async def forbidden_execute(**kwargs):
        raise AssertionError("execution manager must stay idle during passive scans")

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.process_signal = forbidden_process_signal
    trading.execution_manager.execute = forbidden_execute
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.25,
        "confidence": 0.78,
        "reason": "breakout detected",
        "strategy_name": "Trend Following",
    }

    result = asyncio.run(
        trading.process_symbol(
            "BTC/USDT",
            timeframe="15m",
            limit=50,
            allow_execution=False,
        )
    )

    assert result["status"] == "signal"
    assert result["symbol"] == "BTC/USDT"
    assert result["signal"]["side"] == "buy"
    assert result["display_signal"]["symbol"] == "BTC/USDT"
    assert published_ai and published_ai[0][0] == "BTC/USDT"
    assert published_debug and published_debug[0][0] == "BTC/USDT"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "signal_engine"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["status"] == "signal"


def test_sopotek_trading_process_symbol_uses_symbol_assigned_strategy_variants():
    controller = SimpleNamespace(
        broker=DummyBroker(),
        symbols=["EUR/USD"],
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
        assigned_strategies_for_symbol=lambda symbol: [
            {"strategy_name": "Trend Following", "weight": 0.40, "score": 4.0, "rank": 1},
            {"strategy_name": "EMA Cross | London Session Aggressive", "weight": 0.60, "score": 9.0, "rank": 2},
        ],
    )

    trading = SopotekTrading(controller=controller)
    dataset = FakeDataset(_sample_frame())

    async def fake_get_symbol_dataset(**kwargs):
        return dataset

    chosen = {}

    async def fake_process_signal(symbol, signal, dataset=None, timeframe=None, regime_snapshot=None, portfolio_snapshot=None):
        chosen["symbol"] = symbol
        chosen["signal"] = dict(signal)
        return {"status": "filled"}

    calls = []

    def fake_generate_signal(candles=None, dataset=None, strategy_name=None, symbol=None):
        calls.append(strategy_name)
        if strategy_name == "EMA Cross | London Session Aggressive":
            return {
                "symbol": "EUR/USD",
                "side": "buy",
                "amount": 0.5,
                "confidence": 0.72,
                "reason": "assigned strategy fired",
                "strategy_name": strategy_name,
            }
        return None

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.signal_engine.generate_signal = fake_generate_signal
    trading.process_signal = fake_process_signal

    result = asyncio.run(trading.process_symbol("EUR/USD", timeframe="1h", limit=50, publish_debug=False))

    assert result["status"] == "filled"
    assert calls == ["Trend Following", "EMA Cross | London Session Aggressive"]
    assert chosen["signal"]["strategy_name"] == "EMA Cross | London Session Aggressive"
    assert chosen["signal"]["strategy_assignment_weight"] == 0.60


def test_sopotek_trading_scales_basic_risk_rejections_into_smaller_orders():
    controller = SimpleNamespace(
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
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None

    captured = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "amount": kwargs["amount"], "reason": "submitted"}

    trading.execution_manager.execute = fake_execute

    result = asyncio.run(
        trading.process_signal(
            "BTC/USDT",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 25.0,
                "price": 100.0,
                "confidence": 0.80,
                "reason": "oversized breakout signal",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
        )
    )

    assert result["status"] == "filled"
    assert captured["amount"] == 10.0
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "risk_engine"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["status"] == "approved"


def test_sopotek_trading_deduplicates_repeated_allocator_rejection_logs():
    controller = SimpleNamespace(
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
        rejection_log_cooldown_seconds=60.0,
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio = SimpleNamespace(equity=lambda: 10000.0, portfolio=None, market_prices={})
    trading.portfolio_risk_engine = None
    warnings = []
    trading.logger = SimpleNamespace(
        warning=lambda template, reason: warnings.append(template % reason),
        info=lambda *_args, **_kwargs: None,
    )

    async def allocate_trade(**_kwargs):
        return SimpleNamespace(
            approved=False,
            reason="Allocator reduced the ticket below the minimum useful allocation (0.75 < 500.00).",
            metrics={},
            adjusted_amount=0.0,
        )

    trading.portfolio_allocator = SimpleNamespace(
        sync_equity=lambda _equity: None,
        allocate_trade=allocate_trade,
    )

    signal = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 1.0,
        "price": 100.0,
        "confidence": 0.80,
        "reason": "undersized ticket",
        "strategy_name": "Trend Following",
    }

    first = asyncio.run(trading.process_signal("BTC/USDT", dict(signal), dataset=FakeDataset(_sample_frame())))
    second = asyncio.run(trading.process_signal("BTC/USDT", dict(signal), dataset=FakeDataset(_sample_frame())))

    assert first is None
    assert second is None
    assert warnings == ["Trade rejected by portfolio allocator: Allocator reduced the ticket below the minimum useful allocation (0.75 < 500.00)."]
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "portfolio_allocator"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["status"] == "rejected"


def test_sopotek_trading_cancels_stale_orders_before_exit_like_signal():
    controller = SimpleNamespace(
        broker=CleanupBroker(
            positions=[{"symbol": "BTC/USDT", "contracts": 0.25, "side": "long"}],
            orders=[
                {"id": "open-1", "symbol": "BTC/USDT", "status": "open"},
                {"id": "open-2", "symbol": "BTC/USDT", "status": "new"},
            ],
        ),
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
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None

    executed = {}

    async def fake_execute(**kwargs):
        executed.update(kwargs)
        return {"status": "filled", "amount": kwargs["amount"], "reason": "submitted"}

    trading.execution_manager.execute = fake_execute

    result = asyncio.run(
        trading.process_signal(
            "BTC/USDT",
            {
                "symbol": "BTC/USDT",
                "side": "sell",
                "amount": 1.0,
                "price": 100.0,
                "confidence": 0.80,
                "reason": "exit long on reversal",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
        )
    )

    assert result["status"] == "filled"
    assert [row["order_id"] for row in controller.broker.canceled] == ["open-1", "open-2"]
    assert executed["side"] == "sell"


def test_sopotek_trading_does_not_cancel_orders_for_same_direction_signal():
    controller = SimpleNamespace(
        broker=CleanupBroker(
            positions=[{"symbol": "BTC/USDT", "contracts": 0.25, "side": "long"}],
            orders=[{"id": "open-1", "symbol": "BTC/USDT", "status": "open"}],
        ),
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
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None

    async def fake_execute(**kwargs):
        return {"status": "filled", "amount": kwargs["amount"], "reason": "submitted"}

    trading.execution_manager.execute = fake_execute

    asyncio.run(
        trading.process_signal(
            "BTC/USDT",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 1.0,
                "price": 100.0,
                "confidence": 0.80,
                "reason": "trend continuation",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
        )
    )

    assert controller.broker.canceled == []


def test_sopotek_trading_uses_open_only_orders_for_hedge_entries():
    controller = SimpleNamespace(
        broker=DummyBroker(),
        symbols=["EUR/USD"],
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
        hedging_enabled=True,
        hedging_is_active=lambda broker=None: True,
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None
    trading.broker.hedging_supported = True

    captured = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "amount": kwargs["amount"], "reason": "submitted"}

    trading.execution_manager.execute = fake_execute

    asyncio.run(
        trading.process_signal(
            "EUR/USD",
            {
                "symbol": "EUR/USD",
                "side": "sell",
                "amount": 1.0,
                "price": 1.10,
                "confidence": 0.80,
                "reason": "fresh hedge entry",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
        )
    )

    assert captured["params"]["positionFill"] == "OPEN_ONLY"


def test_sopotek_trading_blocks_trade_when_margin_closeout_guard_is_triggered():
    controller = SimpleNamespace(
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
        balances={"equity": 10000.0, "raw": {"marginCloseoutPercent": 0.72}},
        initial_capital=10000,
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
        margin_closeout_snapshot=lambda balances=None: {
            "enabled": True,
            "available": True,
            "ratio": 0.72,
            "threshold": 0.50,
            "blocked": True,
            "reason": "Margin closeout risk is 72.00%, above the configured limit of 50.00%. New trades are blocked.",
        },
    )

    trading = SopotekTrading(controller=controller)
    trading.risk_engine = RiskEngine(account_equity=10000, max_position_size_pct=0.10)
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None

    async def fake_execute(**kwargs):
        raise AssertionError("execution manager should not run when margin closeout guard blocks the trade")

    trading.execution_manager.execute = fake_execute

    result = asyncio.run(
        trading.process_signal(
            "BTC/USDT",
            {
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 1.0,
                "price": 100.0,
                "confidence": 0.80,
                "reason": "breakout signal",
                "strategy_name": "Trend Following",
            },
            dataset=FakeDataset(_sample_frame()),
        )
    )

    assert result is None
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["stage"] == "margin_closeout_guard"
    assert trading.pipeline_status_snapshot()["BTC/USDT"]["status"] == "rejected"


def test_sopotek_trading_start_tolerates_invalid_initial_capital_text(monkeypatch):
    controller = SimpleNamespace(
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
        balances={"total": {"USDT": 15000}},
        initial_capital="abc",
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
    )

    trading = SopotekTrading(controller=controller)
    async def _noop_start(*args, **kwargs):
        return None

    monkeypatch.setattr(trading.execution_manager, "start", _noop_start)
    monkeypatch.setattr(sopotek_trading_module.MultiSymbolOrchestrator, "start", _noop_start)
    trading.behavior_guard.record_equity = lambda _equity: None

    asyncio.run(trading.start())

    assert trading.risk_engine is not None
    assert abs(float(trading.risk_engine.account_equity) - 15000.0) < 1e-9


def test_sopotek_trading_run_processes_all_active_autotrade_symbols(monkeypatch):
    active_symbols = [f"SYM{i}/USD" for i in range(105)]
    controller = SimpleNamespace(
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
        get_active_autotrade_symbols=lambda: list(active_symbols),
    )
    trading = SopotekTrading(controller=controller)
    processed = []

    async def fake_process_symbol(symbol, timeframe=None, limit=None, publish_debug=True):
        processed.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "publish_debug": publish_debug,
            }
        )

    async def fast_sleep(_seconds):
        trading.running = False
        return None

    monkeypatch.setattr(sopotek_trading_module.asyncio, "sleep", fast_sleep)
    trading.process_symbol = fake_process_symbol
    trading.running = True

    asyncio.run(trading.run())

    assert [item["symbol"] for item in processed] == active_symbols
    assert all(item["limit"] == 200 for item in processed)
    assert all(item["publish_debug"] is True for item in processed)


def test_sopotek_trading_process_symbol_caps_runtime_history_limit_for_live_pipeline():
    controller = SimpleNamespace(
        broker=DummyBroker(),
        symbols=["USD/JPY"],
        time_frame="1h",
        limit=50000,
        strategy_name="Trend Following",
        strategy_params={},
        max_portfolio_risk=0.10,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.10,
        max_gross_exposure_pct=2.0,
        balances={"total": {"USD": 10000}},
        initial_capital=10000,
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
        publish_ai_signal=lambda *args, **kwargs: None,
        publish_strategy_debug=lambda *args, **kwargs: None,
    )

    trading = SopotekTrading(controller=controller)
    dataset = FakeDataset(_sample_frame())
    captured = {}

    async def fake_get_symbol_dataset(**kwargs):
        captured.update(kwargs)
        return dataset

    async def fake_process_signal(symbol, signal, dataset=None):
        return {"status": "filled", "symbol": symbol, "dataset": dataset}

    trading.data_hub.get_symbol_dataset = fake_get_symbol_dataset
    trading.signal_engine.generate_signal = lambda **kwargs: {
        "symbol": "USD/JPY",
        "side": "buy",
        "amount": 1.0,
        "confidence": 0.65,
        "reason": "runtime cap test",
        "strategy_name": "Trend Following",
    }
    trading.process_signal = fake_process_signal

    result = asyncio.run(trading.process_symbol("USD/JPY", timeframe="1h"))

    assert result["status"] == "filled"
    assert captured["symbol"] == "USD/JPY"
    assert captured["timeframe"] == "1h"
    assert captured["limit"] == SopotekTrading.MAX_RUNTIME_ANALYSIS_BARS


def test_sopotek_trading_uses_assigned_symbol_timeframe_when_available():
    controller = SimpleNamespace(
        broker=DummyBroker(),
        symbols=["EUR/USD"],
        historical_data={},
        time_frame="1h",
        strategy_name="Trend Following",
        strategy_params={},
        balances={"total": {"USD": 10000}},
        initial_capital=10000,
        handle_trade_execution=lambda trade: None,
        assigned_strategies_for_symbol=lambda symbol: [{"strategy_name": "EMA Cross", "timeframe": "4h", "weight": 1.0}],
    )

    trading = SopotekTrading(controller=controller)

    assert trading._assigned_timeframe_for_symbol("EUR/USD", fallback="1h") == "4h"
    assert trading._assigned_timeframe_for_symbol("GBP/USD", fallback="1h") == "4h"


def test_sopotek_trading_preflights_oanda_forex_bot_orders_as_lots():
    controller = SimpleNamespace(
        broker=DummyOandaBroker(),
        symbols=["EUR/USD"],
        time_frame="1h",
        limit=200,
        strategy_name="Trend Following",
        strategy_params={},
        max_portfolio_risk=0.10,
        max_risk_per_trade=0.02,
        max_position_size_pct=0.10,
        max_gross_exposure_pct=2.0,
        balances={"total": {"USD": 10000}},
        initial_capital=10000,
        market_data_repository=None,
        trade_repository=None,
        handle_trade_execution=lambda trade: None,
        trade_quantity_context=lambda symbol: {
            "symbol": symbol,
            "supports_lots": True,
            "default_mode": "lots",
            "lot_units": 100000.0,
        },
    )

    preflight_calls = {}

    async def fake_preflight_trade_submission(**kwargs):
        preflight_calls.update(kwargs)
        return {
            "requested_amount": 0.5,
            "requested_mode": "lots",
            "requested_amount_units": 50000.0,
            "deterministic_amount_units": 42000.0,
            "amount_units": 42000.0,
            "applied_requested_mode_amount": 0.42,
            "size_adjusted": True,
            "ai_adjusted": False,
            "sizing_summary": "Preflight reduced the order size.",
            "sizing_notes": ["Free margin reduced the order size for this symbol."],
            "ai_sizing_reason": "",
        }

    controller._preflight_trade_submission = fake_preflight_trade_submission
    trading = SopotekTrading(controller=controller)
    trading.risk_engine = None
    trading.portfolio_allocator = None
    trading.portfolio_risk_engine = None

    captured = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"status": "filled", "amount": kwargs["amount"], "reason": "submitted"}

    trading.execution_manager.execute = fake_execute

    result = asyncio.run(
        trading.execute_review(
            {
                "approved": True,
                "symbol": "EUR/USD",
                "side": "buy",
                "amount": 0.5,
                "price": 1.10,
                "strategy_name": "Trend Following",
                "type": "market",
                "execution_strategy": "market",
                "execution_params": {},
                "signal": {
                    "symbol": "EUR/USD",
                    "side": "buy",
                    "amount": 0.5,
                    "price": 1.10,
                    "confidence": 0.80,
                    "reason": "forex breakout",
                    "strategy_name": "Trend Following",
                },
            }
        )
    )

    assert result["status"] == "filled"
    assert preflight_calls["quantity_mode"] == "lots"
    assert captured["amount"] == 42000.0
    assert captured["requested_quantity_mode"] == "lots"
    assert captured["applied_requested_mode_amount"] == 0.42
