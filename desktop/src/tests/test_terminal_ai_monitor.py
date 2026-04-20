import os
import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QTableWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.terminal import Terminal


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_refresh_ai_monitor_table_populates_rows_from_signal_records():
    _app()
    table = QTableWidget()
    fake = SimpleNamespace(
        MAX_LOG_ROWS=200,
        _ai_signal_records={
            "EUR/USD": {
                "symbol": "EUR/USD",
                "signal": "BUY",
                "confidence": 0.73,
                "regime": "TREND_UP",
                "volatility": 0.0123,
                "timestamp": "2026-03-13T10:00:00+00:00",
            }
        },
        _is_qt_object_alive=lambda obj: obj is not None,
        _monitor_table_is_busy=lambda _table: False,
    )
    fake._ai_monitor_rows = lambda: Terminal._ai_monitor_rows(fake)

    Terminal._refresh_ai_monitor_table(fake, table, force=True)

    assert table.rowCount() == 1
    assert table.columnCount() == 6
    assert table.item(0, 0).text() == "EUR/USD"
    assert table.item(0, 1).text() == "BUY"
    assert table.item(0, 2).text() == "0.73"


def test_update_ai_signal_skips_hidden_dock_table_and_refreshes_visible_monitor_window():
    _app()
    ai_table = QTableWidget()
    ai_dock = QDockWidget()
    ai_dock.setWidget(ai_table)
    ai_dock.hide()

    detached_window = QMainWindow()
    detached_table = QTableWidget()
    detached_window._monitor_table = detached_table
    detached_window.setCentralWidget(detached_table)
    detached_window.show()
    QApplication.processEvents()

    refreshed = []
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        _ai_signal_records={},
        _last_ai_table_refresh_at=0.0,
        AI_TABLE_REFRESH_MIN_SECONDS=0.0,
        ai_table=ai_table,
        ai_signal_dock=ai_dock,
        detached_tool_windows={"ml_monitor": detached_window},
        _record_recommendation=lambda **_kwargs: None,
        _is_qt_object_alive=lambda obj: obj is not None,
    )

    def _refresh(table, force=False):
        refreshed.append((table, force))

    fake._refresh_ai_monitor_table = _refresh
    fake._log_ai_signal_update = lambda record: None

    Terminal._update_ai_signal(
        fake,
        {
            "symbol": "EUR/USD",
            "signal": "BUY",
            "confidence": 0.81,
            "regime": "TREND_UP",
            "volatility": 0.014,
            "reason": "Momentum aligned",
            "timestamp": "2026-03-13T10:00:00+00:00",
        },
    )

    assert "EUR/USD" in fake._ai_signal_records
    refreshed_tables = [table for table, _force in refreshed]
    assert ai_table not in refreshed_tables
    assert detached_table in refreshed_tables


def test_update_ai_signal_logs_to_system_console_and_dedupes_repeats():
    logs = []
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        _ai_signal_records={},
        _ai_signal_log_state={},
        _last_ai_table_refresh_at=0.0,
        AI_TABLE_REFRESH_MIN_SECONDS=999.0,
        AI_SIGNAL_LOG_MIN_SECONDS=60.0,
        ai_table=None,
        ai_signal_dock=None,
        detached_tool_windows={},
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        _record_recommendation=lambda **_kwargs: None,
        _is_qt_object_alive=lambda obj: obj is not None,
    )
    fake._log_ai_signal_update = lambda record: Terminal._log_ai_signal_update(fake, record)

    payload = {
        "symbol": "EUR/USD",
        "signal": "BUY",
        "confidence": 0.81,
        "regime": "TREND_UP",
        "reason": "Momentum aligned across trend filters.",
        "market_hours": {
            "asset_type": "forex",
            "session": "overlap",
            "market_open": True,
            "trade_allowed": True,
            "high_liquidity": True,
        },
        "timestamp": "2026-03-13T10:00:00+00:00",
    }

    Terminal._update_ai_signal(fake, payload)
    Terminal._update_ai_signal(fake, dict(payload))

    assert len(logs) == 1
    assert logs[0][1] == "INFO"
    assert "Signal monitor EUR/USD: BUY" in logs[0][0]
    assert "market forex | session overlap | open | trade allowed | liq high" in logs[0][0]
    assert "Momentum aligned across trend filters." in logs[0][0]


def test_session_scoped_slot_routes_payloads_to_matching_terminal_session():
    calls = []
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        bound_session_id="coinbase-paper-002",
        controller=SimpleNamespace(active_session_id="binance-paper-001"),
    )
    fake._session_is_current = lambda: Terminal._session_is_current(fake)
    fake._extract_session_id_from_payload = lambda value: Terminal._extract_session_id_from_payload(fake, value)
    fake._payload_session_matches_terminal = (
        lambda *args, **kwargs: Terminal._payload_session_matches_terminal(fake, *args, **kwargs)
    )

    wrapped = Terminal._session_scoped_slot(fake, lambda payload: calls.append(payload))

    wrapped({"session_id": "coinbase-paper-002", "symbol": "BTC/USDT"})
    wrapped({"session_id": "binance-paper-001", "symbol": "ETH/USDT"})

    assert calls == [{"session_id": "coinbase-paper-002", "symbol": "BTC/USDT"}]


def test_run_passive_signal_scan_requests_signals_without_enabling_autotrading():
    calls = []

    async def fake_process_symbol(symbol, timeframe=None, limit=None, publish_debug=True, allow_execution=True):
        calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "publish_debug": publish_debug,
                "allow_execution": allow_execution,
            }
        )
        return {"status": "signal", "symbol": symbol}

    fake_trading_system = SimpleNamespace(
        process_symbol=fake_process_symbol,
        _assigned_timeframe_for_symbol=lambda symbol, fallback="1h": "4h" if symbol == "BTC/USDT" else fallback,
    )
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        autotrading_enabled=False,
        bound_session_id="paper-solana-001",
        controller=SimpleNamespace(
            active_session_id="paper-solana-001",
            limit=180,
            time_frame="1h",
            symbols=["BTC/USDT"],
            trading_system=fake_trading_system,
            get_active_autotrade_symbols=lambda: ["BTC/USDT"],
        ),
        autotrade_scope_value="selected",
        current_timeframe="15m",
        symbol="BTC/USDT",
        logger=SimpleNamespace(debug=lambda *args, **kwargs: None),
    )
    fake._session_is_current = lambda: Terminal._session_is_current(fake)
    fake._normalized_symbol = lambda symbol: Terminal._normalized_symbol(fake, symbol)
    fake._current_chart_symbol = lambda: "BTC/USDT"
    fake._passive_signal_scan_symbols = lambda: Terminal._passive_signal_scan_symbols(fake)

    asyncio.run(Terminal._run_passive_signal_scan(fake))

    assert calls == [
        {
            "symbol": "BTC/USDT",
            "timeframe": "4h",
            "limit": 180,
            "publish_debug": True,
            "allow_execution": False,
        }
    ]


def test_passive_signal_scan_all_scope_uses_session_symbols_and_ignores_stale_chart_symbol():
    calls = []

    async def fake_process_symbol(symbol, timeframe=None, limit=None, publish_debug=True, allow_execution=True):
        calls.append(symbol)
        return {"status": "signal", "symbol": symbol}

    active_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        autotrading_enabled=False,
        PASSIVE_SIGNAL_SCAN_MAX_SYMBOLS=3,
        bound_session_id="coinbase-paper-001",
        controller=SimpleNamespace(
            active_session_id="coinbase-paper-001",
            limit=120,
            time_frame="1h",
            symbols=list(active_symbols),
            trading_system=SimpleNamespace(
                process_symbol=fake_process_symbol,
                _assigned_timeframe_for_symbol=lambda symbol, fallback="1h": fallback,
            ),
            get_active_autotrade_symbols=lambda: list(active_symbols),
            is_symbol_enabled_for_autotrade=lambda symbol: symbol in set(active_symbols),
        ),
        autotrade_scope_value="all",
        current_timeframe="15m",
        symbol="GBP/HKD",
        logger=SimpleNamespace(debug=lambda *args, **kwargs: None),
    )
    fake._session_is_current = lambda: Terminal._session_is_current(fake)
    fake._normalized_symbol = lambda symbol: Terminal._normalized_symbol(fake, symbol)
    fake._current_chart_symbol = lambda: "GBP/HKD"
    fake._passive_signal_scan_symbols = lambda: Terminal._passive_signal_scan_symbols(fake)

    asyncio.run(Terminal._run_passive_signal_scan(fake))

    assert calls == active_symbols


def test_enable_live_autotrading_async_uses_warmed_readiness_report():
    started = []
    emitted = []
    logs = []
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        autotrading_enabled=False,
        current_timeframe="15m",
        symbol="EUR/USD",
        logger=SimpleNamespace(debug=lambda *args, **kwargs: None),
        controller=SimpleNamespace(
            trading_system=SimpleNamespace(start=lambda: asyncio.sleep(0, result=started.append("start"))),
            evaluate_live_readiness_report_async=lambda symbol=None, timeframe=None: asyncio.sleep(
                0,
                result={"ready": True, "summary": "Ready for live trading.", "symbol": symbol, "timeframe": timeframe},
            ),
        ),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        autotrade_toggle=SimpleNamespace(emit=lambda value: emitted.append(value)),
    )
    fake._current_chart_symbol = lambda: "EUR/USD"
    fake._autotrade_scope_label = lambda: "Selected Symbol"
    fake._update_autotrade_button = lambda: None

    asyncio.run(Terminal._enable_live_autotrading_async(fake, ["EUR/USD"]))

    assert fake.autotrading_enabled is True
    assert emitted == [True]
    assert logs[-1][0] == "AI auto trading enabled for 1 symbol(s) using scope: Selected Symbol."


def test_enable_live_autotrading_async_does_not_block_on_readiness_report():
    started = []
    emitted = []
    logs = []
    fake = SimpleNamespace(
        _ui_shutting_down=False,
        autotrading_enabled=False,
        current_timeframe="15m",
        symbol="EUR/USD",
        logger=SimpleNamespace(debug=lambda *args, **kwargs: None),
        controller=SimpleNamespace(
            trading_system=SimpleNamespace(start=lambda: asyncio.sleep(0, result=started.append("start"))),
            evaluate_live_readiness_report_async=lambda symbol=None, timeframe=None: asyncio.sleep(
                0,
                result={"ready": False, "summary": "Blocked by 2 readiness issues."},
            ),
        ),
        system_console=SimpleNamespace(log=lambda message, level="INFO": logs.append((message, level))),
        autotrade_toggle=SimpleNamespace(emit=lambda value: emitted.append(value)),
    )
    fake._current_chart_symbol = lambda: "EUR/USD"
    fake._autotrade_scope_label = lambda: "Selected Symbol"
    fake._update_autotrade_button = lambda: None

    asyncio.run(Terminal._enable_live_autotrading_async(fake, ["EUR/USD"]))

    assert fake.autotrading_enabled is True
    assert emitted == [True]
    assert logs[-1][0] == "AI auto trading enabled for 1 symbol(s) using scope: Selected Symbol."
