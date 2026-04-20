import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.app_controller import AppController
from strategy.strategy import Strategy
from strategy.strategy_registry import StrategyRegistry


class _Settings:
    def __init__(self):
        self.store = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value


class _Logger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def exception(self, *_args, **_kwargs):
        return None

    def debug(self, *_args, **_kwargs):
        return None


class _FakeRanker:
    def __init__(self):
        self.calls = []

    def rank(self, data, symbol, timeframe=None, strategy_names=None, top_n=None):
        self.calls.append((symbol, timeframe, tuple(strategy_names or []), len(data)))
        if symbol == "EUR/USD" and str(timeframe or "") == "4h":
            top_strategy = "MACD Trend"
            top_score = 12.0
            top_profit = 180.0
            top_sharpe = 1.9
            top_equity = 10180.0
        elif symbol == "EUR/USD":
            top_strategy = "EMA Cross"
            top_score = 9.0
            top_profit = 140.0
            top_sharpe = 1.6
            top_equity = 10140.0
        else:
            top_strategy = "MACD Trend"
            top_score = 9.0
            top_profit = 140.0
            top_sharpe = 1.6
            top_equity = 10140.0
        alt_strategy = "Trend Following"
        return pd.DataFrame(
            [
                {
                    "strategy_name": top_strategy,
                    "score": top_score,
                    "total_profit": top_profit,
                    "sharpe_ratio": top_sharpe,
                    "win_rate": 0.61,
                    "final_equity": top_equity,
                    "max_drawdown": 90.0,
                    "closed_trades": 18,
                },
                {
                    "strategy_name": alt_strategy,
                    "score": 5.0,
                    "total_profit": 80.0,
                    "sharpe_ratio": 1.1,
                    "win_rate": 0.55,
                    "final_equity": 10080.0,
                    "max_drawdown": 110.0,
                    "closed_trades": 14,
                },
            ]
        )


def _sample_frame(rows=160):
    return pd.DataFrame(
        {
            "timestamp": list(range(rows)),
            "open": [100.0 + i for i in range(rows)],
            "high": [101.0 + i for i in range(rows)],
            "low": [99.0 + i for i in range(rows)],
            "close": [100.5 + i for i in range(rows)],
            "volume": [1000.0 + i for i in range(rows)],
        }
    )


def _saved_assignment(symbol, strategy_name, timeframe="1h", assignment_mode="single", assignment_source="auto"):
    return [
        {
            "strategy_name": strategy_name,
            "score": 9.0,
            "weight": 1.0,
            "symbol": symbol,
            "timeframe": timeframe,
            "assignment_mode": assignment_mode,
            "assignment_source": assignment_source,
            "rank": 1,
            "total_profit": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "final_equity": 0.0,
            "max_drawdown": 0.0,
            "closed_trades": 0,
        }
    ]


def _make_controller():
    settings = _Settings()
    refresh_calls = []
    ranker = _FakeRanker()
    frame = _sample_frame()

    controller = AppController.__new__(AppController)
    controller.settings = settings
    controller.logger = _Logger()
    controller.multi_strategy_enabled = True
    controller.max_symbol_strategies = 2
    controller.symbol_strategy_assignments = {}
    controller.symbol_strategy_rankings = {}
    controller.symbol_strategy_locks = set()
    controller.strategy_auto_assignment_enabled = True
    controller.strategy_auto_assignment_ready = False
    controller.strategy_auto_assignment_in_progress = False
    controller.strategy_auto_assignment_progress = {}
    controller._strategy_auto_assignment_task = None
    controller._strategy_auto_assignment_deferred_task = None
    controller._symbol_universe_tiers = {}
    controller._symbol_universe_rotation_cursor = 0
    controller.time_frame = "1h"
    controller.strategy_assignment_scan_timeframes = ["1h"]
    controller.strategy_name = "Trend Following"
    controller.initial_capital = 10000
    controller.symbols = ["EUR/USD", "BTC/USDT"]
    controller.autotrade_watchlist = set()
    controller.balances = {}
    controller.market_trade_preference = "auto"
    controller.candle_buffers = {
        "EUR/USD": {"1h": frame.copy()},
        "BTC/USDT": {"1h": frame.copy()},
    }
    async def request_candle_data(symbol, timeframe="1h", limit=None):
        frame_for_timeframe = frame.copy()
        controller.candle_buffers.setdefault(str(symbol), {})[str(timeframe)] = frame_for_timeframe
        return frame_for_timeframe

    controller.request_candle_data = request_candle_data
    controller.trading_system = SimpleNamespace(
        strategy=SimpleNamespace(list=lambda: ["Trend Following", "EMA Cross", "MACD Trend"]),
        refresh_strategy_preferences=lambda: refresh_calls.append(True),
    )
    controller.terminal = None
    controller.connected = True
    controller._build_strategy_ranker = lambda strategy_registry: ranker
    controller._create_task = lambda coro, _name: asyncio.get_event_loop().create_task(coro)
    controller._refresh_calls = refresh_calls
    controller._ranker = ranker
    return controller


def test_assign_strategy_to_symbol_marks_manual_lock_and_source():
    controller = _make_controller()

    assigned = controller.assign_strategy_to_symbol("btc_usdt", "Trend Following", timeframe="4h")

    assert assigned[0]["assignment_source"] == "manual"
    assert controller.symbol_strategy_assignment_locked("BTC/USDT") is True


def test_select_trade_symbols_keeps_full_coinbase_runtime_list_and_prioritizes_held_assets():
    controller = _make_controller()
    controller.balances = {"total": {"USD": 500.0, "AAVE": 2.0}}
    controller.broker = SimpleNamespace(exchange_name="coinbase")

    symbols = [
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
        "AAVE/EUR",
        "AAVE/BTC",
        "DOGE/USD",
        "XRP/USD",
        "ADA/USD",
        "AVAX/USD",
        "LINK/USD",
        "UNI/USD",
        "NEAR/USD",
        "FIL/USD",
        "AAVE/USD",
    ]

    selected = asyncio.run(controller._select_trade_symbols(symbols, "crypto", "coinbase"))
    filtered = controller._filter_symbols_for_trading(symbols, "crypto", "coinbase")

    assert len(selected) == len(filtered)
    assert selected[0] == "AAVE/USD"


def test_select_trade_symbols_prioritizes_solana_usdc_pairs_and_held_assets():
    controller = _make_controller()
    controller.balances = {"total": {"BONK": 150000.0, "USDC": 250.0}}
    controller.broker = SimpleNamespace(exchange_name="solana")

    symbols = [
        "RAY/SOL",
        "BONK/SOL",
        "JUP/USDC",
        "BONK/USDC",
    ]

    selected = asyncio.run(controller._select_trade_symbols(symbols, "crypto", "solana"))
    filtered = controller._filter_symbols_for_trading(symbols, "crypto", "solana")

    assert filtered == ["RAY/SOL", "BONK/SOL", "JUP/USDC", "BONK/USDC"]
    assert selected[:2] == ["BONK/USDC", "JUP/USDC"]


def test_strategy_auto_assignment_timeframes_are_narrowed_for_coinbase():
    controller = _make_controller()
    controller.strategy_assignment_scan_timeframes = None
    controller.broker = SimpleNamespace(exchange_name="coinbase")

    assert controller._strategy_auto_assignment_timeframes(timeframe="15m") == ["15m", "1h", "4h"]
    assert controller._strategy_auto_assignment_symbol_limit() == controller.COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT


def test_ranked_autotrade_scope_prefers_best_saved_rankings_across_catalog():
    controller = _make_controller()
    controller.autotrade_scope = "ranked"
    controller.broker = SimpleNamespace(exchange_name="coinbase")
    controller.symbols = ["BTC/USD", "ETH/USD"]
    controller.COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT = 2

    controller.save_ranked_strategies_for_symbol(
        "SOL/USD",
        [{"strategy_name": "EMA Cross", "score": 7.5, "sharpe_ratio": 1.2, "total_profit": 120.0, "win_rate": 0.58}],
        timeframe="1h",
        assignment_source="auto",
    )
    controller.save_ranked_strategies_for_symbol(
        "ADA/USD",
        [{"strategy_name": "MACD Trend", "score": 11.0, "sharpe_ratio": 1.8, "total_profit": 180.0, "win_rate": 0.63}],
        timeframe="4h",
        assignment_source="auto",
    )

    ranked = controller.get_active_autotrade_symbols(
        available_symbols=controller.symbols,
        catalog_symbols=["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD"],
        broker_type="crypto",
        exchange="coinbase",
    )

    assert ranked == ["ADA/USD", "SOL/USD"]


def test_coinbase_derivative_selection_keeps_contract_symbols_and_broadens_scan_timeframes():
    controller = _make_controller()
    controller.strategy_assignment_scan_timeframes = None
    controller.market_trade_preference = "derivative"
    controller.broker = SimpleNamespace(
        exchange_name="coinbase",
        market_preference="derivative",
        resolved_market_preference="derivative",
        exchange=SimpleNamespace(
            markets={
                "BTC/USD": {"symbol": "BTC/USD", "spot": True, "base": "BTC", "quote": "USD"},
                "BTC/USD:USD": {
                    "symbol": "BTC/USD:USD",
                    "contract": True,
                    "future": True,
                    "base": "BTC",
                    "quote": "USD",
                    "settle": "USD",
                },
                "ETH/USD:USD": {
                    "symbol": "ETH/USD:USD",
                    "contract": True,
                    "future": True,
                    "base": "ETH",
                    "quote": "USD",
                    "settle": "USD",
                },
            }
        ),
    )

    symbols = ["BTC/USD", "BTC/USD:USD", "ETH/USD:USD"]

    filtered = controller._filter_symbols_for_trading(symbols, "crypto", "coinbase")
    selected = asyncio.run(controller._select_trade_symbols(symbols, "crypto", "coinbase"))

    assert filtered == ["BTC/USD:USD", "ETH/USD:USD"]
    assert selected == ["BTC/USD:USD", "ETH/USD:USD"]
    assert controller._strategy_auto_assignment_timeframes(timeframe="15m") == [
        "15m",
        "1m",
        "5m",
        "30m",
        "1h",
        "4h",
        "1d",
    ]


def test_auto_rank_and_assign_strategies_assigns_unlocked_symbols_and_preserves_manual_locks():
    controller = _make_controller()
    manual_assignment = controller.assign_strategy_to_symbol("BTC/USDT", "Trend Following", timeframe="4h")
    controller._refresh_calls.clear()

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))

    eur_assigned = controller.assigned_strategies_for_symbol("EUR/USD")
    btc_assigned = controller.assigned_strategies_for_symbol("BTC/USDT")
    btc_ranked = controller.ranked_strategies_for_symbol("BTC/USDT")

    assert eur_assigned[0]["strategy_name"] == "EMA Cross"
    assert eur_assigned[0]["assignment_source"] == "auto"
    assert controller.symbol_strategy_assignment_locked("EUR/USD") is False

    assert btc_assigned == manual_assignment
    assert controller.symbol_strategy_assignment_locked("BTC/USDT") is True
    assert btc_ranked == []

    assert result["assigned_symbols"] == ["EUR/USD"]
    assert result["restored_symbols"] == ["BTC/USDT"]
    assert result["skipped_symbols"] == []
    assert controller._ranker.calls == [("EUR/USD", "1h", ("Trend Following", "EMA Cross", "MACD Trend"), 160)]
    assert controller._refresh_calls == [True]




def test_auto_rank_and_assign_strategies_selects_best_timeframe_for_symbol():
    controller = _make_controller()
    controller.symbols = ["EUR/USD"]
    controller.candle_buffers = {
        "EUR/USD": {
            "1h": _sample_frame(),
            "4h": _sample_frame(),
        }
    }
    controller.strategy_assignment_scan_timeframes = ["1h", "4h"]

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))
    assigned = controller.assigned_strategies_for_symbol("EUR/USD")
    ranked = controller.ranked_strategies_for_symbol("EUR/USD")

    assert result["assigned_symbols"] == ["EUR/USD"]
    assert assigned[0]["strategy_name"] == "MACD Trend"
    assert assigned[0]["timeframe"] == "4h"
    assert ranked[0]["strategy_name"] == "MACD Trend"
    assert ranked[0]["timeframe"] == "4h"
    assert result["scan_timeframes"] == ["1h", "4h"]


def test_auto_rank_and_assign_strategies_uses_dedicated_ranking_helper():
    controller = _make_controller()
    controller.symbols = ["EUR/USD"]
    ranking_calls = []

    async def fake_run_strategy_ranking(ranker, frame, symbol, timeframe, strategy_names):
        ranking_calls.append((symbol, timeframe, tuple(strategy_names or []), len(frame)))
        return ranker.rank(frame, symbol, timeframe, strategy_names)

    controller._run_strategy_ranking = fake_run_strategy_ranking

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))

    assert result["assigned_symbols"] == ["EUR/USD"]
    assert ranking_calls == [("EUR/USD", "1h", ("Trend Following", "EMA Cross", "MACD Trend"), 160)]


def test_strategy_names_for_auto_assignment_shortlists_full_catalog_for_solana():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="solana")

    strategy_names = controller._strategy_names_for_auto_assignment(
        "BONK/USDC",
        StrategyRegistry().list(),
    )

    assert len(strategy_names) == len(Strategy.CORE_STRATEGIES)
    assert strategy_names[:5] == [
        "Bollinger Squeeze",
        "Volume Spike Reversal",
        "ATR Compression Breakout",
        "Momentum Continuation",
        "Donchian Trend",
    ]
    assert all("|" not in name for name in strategy_names)


def test_strategy_names_for_auto_assignment_shortlists_full_catalog_for_forex():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="oanda")

    strategy_names = controller._strategy_names_for_auto_assignment(
        "EUR/USD",
        StrategyRegistry().list(),
    )

    assert len(strategy_names) == len(Strategy.CORE_STRATEGIES)
    assert strategy_names[:5] == [
        "Donchian Trend",
        "MACD Trend",
        "EMA Cross",
        "Trend Following",
        "ATR Compression Breakout",
    ]


def test_filter_symbols_for_trading_excludes_crypto_symbols_for_oanda():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="oanda")
    controller.config = SimpleNamespace(broker=SimpleNamespace(type="forex", exchange="oanda"))

    filtered = controller._filter_symbols_for_trading(
        ["EUR/USD", "GBP/USD", "XAU/USD", "NAS100/USD", "BTC/USDT", "ETH/USD", "SOL/USD"],
        "forex",
        "oanda",
    )

    assert filtered == ["EUR/USD", "GBP/USD", "XAU/USD", "NAS100/USD"]


def test_set_autotrade_watchlist_strips_crypto_symbols_for_oanda():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="oanda")
    controller.config = SimpleNamespace(broker=SimpleNamespace(type="forex", exchange="oanda"))
    controller._sync_session_scoped_state = lambda *args, **kwargs: None

    controller.set_autotrade_watchlist(["BTC/USDT", "EUR/USD", "XAU/USD", "ETH/USD"])

    assert controller.autotrade_watchlist == {"EUR/USD", "XAU/USD"}
    assert controller.settings.value("autotrade/watchlist") == "[\"EUR/USD\", \"XAU/USD\"]"


def test_apply_strategy_market_context_bias_prefers_solana_squeeze_families_on_close_scores():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="solana")

    biased = controller._apply_strategy_market_context_bias(
        [
            {"strategy_name": "Trend Following", "score": 10.0, "total_profit": 100.0, "sharpe_ratio": 1.2},
            {"strategy_name": "Bollinger Squeeze", "score": 9.7, "total_profit": 99.0, "sharpe_ratio": 1.15},
        ],
        "BONK/USDC",
    )

    assert biased[0]["strategy_name"] == "Bollinger Squeeze"
    assert biased[0]["market_profile"] == "solana"
    assert biased[0]["market_fit_bonus"] > biased[1]["market_fit_bonus"]


def test_auto_rank_and_assign_strategies_uses_contextual_shortlist_for_full_catalog_registry():
    controller = _make_controller()
    controller.symbols = ["BONK/USDC"]
    controller.broker = SimpleNamespace(exchange_name="solana")
    controller.candle_buffers = {"BONK/USDC": {"1h": _sample_frame()}}
    controller.trading_system = SimpleNamespace(
        strategy=StrategyRegistry(),
        refresh_strategy_preferences=lambda: controller._refresh_calls.append(True),
    )

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))

    assert result["assigned_symbols"] == ["BONK/USDC"]
    assert controller._ranker.calls[0][0] == "BONK/USDC"
    assert controller._ranker.calls[0][2][:5] == (
        "Bollinger Squeeze",
        "Volume Spike Reversal",
        "ATR Compression Breakout",
        "Momentum Continuation",
        "Donchian Trend",
    )
    assert len(controller._ranker.calls[0][2]) == len(Strategy.CORE_STRATEGIES)


def test_strategy_auto_assignment_status_reports_ready_after_scan():
    controller = _make_controller()

    asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))
    status = controller.strategy_auto_assignment_status()

    assert status["ready"] is True
    assert status["running"] is False
    assert status["assigned_symbols"] == 2
    assert status["completed"] == 2
    assert status["total"] == 2


def test_auto_rank_and_assign_strategies_restores_saved_assignments_without_rescanning():
    controller = _make_controller()
    controller.symbol_strategy_assignments = {
        "EUR/USD": _saved_assignment("EUR/USD", "EMA Cross"),
        "BTC/USDT": _saved_assignment("BTC/USDT", "MACD Trend", assignment_mode="ranked"),
    }
    controller._refresh_calls.clear()
    controller._ranker.calls.clear()

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))
    status = controller.strategy_auto_assignment_status()

    assert result["assigned_symbols"] == []
    assert result["restored_symbols"] == ["EUR/USD", "BTC/USDT"]
    assert result["skipped_symbols"] == []
    assert controller._ranker.calls == []
    assert controller._refresh_calls == [True]
    assert status["ready"] is True
    assert status["message"] == "Loaded saved strategy assignments for 2 symbols."


def test_schedule_strategy_auto_assignment_only_scans_symbols_missing_saved_state():
    controller = _make_controller()
    controller.symbol_strategy_assignments = {
        "EUR/USD": _saved_assignment("EUR/USD", "EMA Cross"),
    }
    scheduled = {}

    async def fake_auto_rank_and_assign_strategies(symbols=None, timeframe=None, force=False):
        scheduled["symbols"] = list(symbols or [])
        scheduled["timeframe"] = timeframe
        scheduled["force"] = force
        return {"assigned_symbols": list(symbols or [])}

    controller.auto_rank_and_assign_strategies = fake_auto_rank_and_assign_strategies

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        task = controller.schedule_strategy_auto_assignment(symbols=controller.symbols, timeframe="1h", force=False)
        loop.run_until_complete(task)
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert scheduled["symbols"] == ["BTC/USDT"]
    assert scheduled["timeframe"] == "1h"
    assert scheduled["force"] is False


def test_coinbase_startup_fast_mode_defers_strategy_auto_assignment():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="coinbase")
    controller.market_trade_preference = "spot"
    controller.strategy_assignment_scan_timeframes = None
    controller.COINBASE_FAST_START_AUTO_ASSIGN_DELAY_SECONDS = 0.01
    controller.COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT = 4
    controller.COINBASE_WATCHLIST_SYMBOL_LIMIT = 4
    controller.COINBASE_DISCOVERY_BATCH_SIZE = 2
    controller.COINBASE_DISCOVERY_PRIORITY_COUNT = 2
    controller.symbols = ["BTC/USD", "ETH/USD"]
    controller.autotrade_watchlist = {"SOL/USD", "ADA/USD"}
    controller._refresh_symbol_universe_tiers(
        catalog_symbols=["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD", "AVAX/USD", "LINK/USD"],
        broker_type="crypto",
        exchange="coinbase",
    )
    scheduled = {}

    def fake_schedule_strategy_auto_assignment(symbols=None, timeframe=None, force=False):
        scheduled["symbols"] = None if symbols is None else list(symbols or [])
        scheduled["timeframe"] = timeframe
        scheduled["force"] = force
        future = asyncio.get_event_loop().create_future()
        future.set_result({"scheduled": True})
        return future

    controller.schedule_strategy_auto_assignment = fake_schedule_strategy_auto_assignment

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        task = controller._schedule_startup_strategy_auto_assignment(
            symbols=controller.symbols,
            timeframe="1h",
            exchange="coinbase",
        )
        assert scheduled == {}
        loop.run_until_complete(task)
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert scheduled["symbols"] is None
    assert scheduled["timeframe"] == "1h"
    assert scheduled["force"] is False
    assert "Coinbase fast mode" in controller.strategy_auto_assignment_progress["message"]


def test_non_coinbase_startup_auto_assignment_runs_immediately():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="binanceus")
    controller.COINBASE_FAST_START_AUTO_ASSIGN_DELAY_SECONDS = 0.01
    scheduled = {}

    def fake_schedule_strategy_auto_assignment(symbols=None, timeframe=None, force=False):
        scheduled["symbols"] = None if symbols is None else list(symbols or [])
        scheduled["timeframe"] = timeframe
        scheduled["force"] = force
        return "scheduled-now"

    controller.schedule_strategy_auto_assignment = fake_schedule_strategy_auto_assignment

    result = controller._schedule_startup_strategy_auto_assignment(
        symbols=controller.symbols,
        timeframe="1h",
        exchange="binanceus",
    )

    assert result == "scheduled-now"
    assert scheduled["symbols"] is None
    assert scheduled["timeframe"] == "1h"
    assert scheduled["force"] is False


def test_coinbase_symbol_universe_rotates_background_batch_without_expanding_live_symbols():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="coinbase")
    controller.market_trade_preference = "spot"
    controller.symbols = ["BTC/USD", "ETH/USD"]
    controller.autotrade_watchlist = {"SOL/USD", "ADA/USD"}
    controller.COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT = 4
    controller.COINBASE_WATCHLIST_SYMBOL_LIMIT = 4
    controller.COINBASE_DISCOVERY_BATCH_SIZE = 2
    controller.COINBASE_DISCOVERY_PRIORITY_COUNT = 2

    catalog = ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD", "AVAX/USD", "LINK/USD", "UNI/USD"]
    controller._refresh_symbol_universe_tiers(catalog_symbols=catalog, broker_type="crypto", exchange="coinbase")

    first = controller._rotating_discovery_batch(limit=4, advance=True, broker_type="crypto", exchange="coinbase")
    second = controller._rotating_discovery_batch(limit=4, advance=True, broker_type="crypto", exchange="coinbase")
    tiers = controller.get_symbol_universe_snapshot()

    assert controller.symbols == ["BTC/USD", "ETH/USD"]
    assert tiers["catalog"] == catalog
    assert tiers["watchlist"][:4] == ["BTC/USD", "ETH/USD", "ADA/USD", "SOL/USD"]
    assert first == ["BTC/USD", "ETH/USD", "AVAX/USD", "LINK/USD"]
    assert second == ["BTC/USD", "ETH/USD", "UNI/USD", "AVAX/USD"]


def test_spot_only_broker_symbol_universe_rotates_background_batch():
    controller = _make_controller()
    controller.broker = SimpleNamespace(exchange_name="binanceus")
    controller.market_trade_preference = "spot"
    controller.symbols = ["BTC/USDT", "ETH/USDT"]
    controller.autotrade_watchlist = {"SOL/USDT"}
    controller.SPOT_ONLY_SYMBOL_WATCHLIST_LIMIT = 4
    controller.SPOT_ONLY_DISCOVERY_BATCH_SIZE = 4

    catalog = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT"]
    controller._refresh_symbol_universe_tiers(catalog_symbols=catalog, broker_type="crypto", exchange="binanceus")

    batch = controller._rotating_discovery_batch(limit=4, advance=True, broker_type="crypto", exchange="binanceus")
    tiers = controller.get_symbol_universe_snapshot()

    assert tiers["catalog"] == catalog
    assert tiers["watchlist"][:4] == ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    assert batch == ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT"]


def test_coinbase_market_preference_change_keeps_live_symbol_cap():
    controller = _make_controller()
    controller.connected = True
    controller.symbols = ["BTC/USD"]
    controller.config = SimpleNamespace(
        broker=SimpleNamespace(
            type="crypto",
            exchange="coinbase",
            options={},
        )
    )
    controller.broker = SimpleNamespace(
        exchange_name="coinbase",
        extra_options={},
        market_preference="spot",
        apply_market_preference=lambda _pref: [
            "BTC/USD",
            "ETH/USD",
            "SOL/USD",
            "ADA/USD",
            "AVAX/USD",
            "LINK/USD",
            "UNI/USD",
            "NEAR/USD",
            "DOGE/USD",
            "XRP/USD",
            "LTC/USD",
        ],
        supported_market_venues=lambda: ["auto", "spot", "derivative"],
    )
    emitted = []
    scheduled = {}
    controller.symbols_signal = SimpleNamespace(emit=lambda exchange, symbols: emitted.append((exchange, list(symbols))))

    def fake_schedule_strategy_auto_assignment(symbols=None, timeframe=None, force=False):
        scheduled["symbols"] = symbols
        scheduled["timeframe"] = timeframe
        scheduled["force"] = force
        return None

    controller.schedule_strategy_auto_assignment = fake_schedule_strategy_auto_assignment

    controller.set_market_trade_preference("spot")

    assert len(controller.symbols) == 11
    assert emitted[-1][0] == "coinbase"
    assert emitted[-1][1] == controller.symbols
    assert len(controller.get_symbol_universe_snapshot()["catalog"]) == 11
    assert scheduled["symbols"] is None
    assert scheduled["timeframe"] == controller.time_frame
    assert scheduled["force"] is False


def test_auto_rank_and_assign_strategies_preserves_locked_default_symbols_on_restart():
    controller = _make_controller()
    controller.symbols = ["EUR/USD"]
    controller._mark_symbol_strategy_assignment_locked("EUR/USD", True)
    controller._refresh_calls.clear()
    controller._ranker.calls.clear()

    result = asyncio.run(controller.auto_rank_and_assign_strategies(timeframe="1h"))

    assert result["restored_symbols"] == ["EUR/USD"]
    assert controller._ranker.calls == []
    assert controller._refresh_calls == [True]
