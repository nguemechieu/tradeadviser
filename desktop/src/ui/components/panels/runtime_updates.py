import asyncio
import time

INITIAL_ACCOUNT_SYNC_TIMEOUT_SECONDS = 12.0
INITIAL_STAGE_TIMEOUT_SECONDS = 8.0


def _authoritative_server_runtime(terminal):
    controller = getattr(terminal, "controller", None)
    resolver = getattr(controller, "is_hybrid_server_authoritative", None)
    if callable(resolver):
        try:
            return bool(resolver())
        except Exception:
            return False
    return False


def _runtime_broker_name(terminal):
    broker = getattr(getattr(terminal, "controller", None), "broker", None)
    return str(getattr(broker, "exchange_name", "") or "").strip().lower()


def _positions_refresh_interval_seconds(terminal):
    broker_name = _runtime_broker_name(terminal)
    if broker_name == "coinbase":
        return 6.0
    if broker_name == "alpaca":
        return 5.0
    return 0.0


def _open_orders_refresh_interval_seconds(terminal):
    broker_name = _runtime_broker_name(terminal)
    if broker_name == "coinbase":
        return 5.0
    if broker_name == "alpaca":
        return 5.0
    return 0.0


def _assets_refresh_interval_seconds(terminal):
    broker_name = _runtime_broker_name(terminal)
    if broker_name in {"coinbase", "alpaca"}:
        return 8.0
    return 10.0


def _history_refresh_interval_seconds(terminal):
    broker_name = _runtime_broker_name(terminal)
    if broker_name in {"coinbase", "alpaca"}:
        return 12.0
    return 15.0


async def refresh_positions_async(terminal):
    if terminal._ui_shutting_down:
        return
    if _authoritative_server_runtime(terminal):
        positions_snapshot = getattr(terminal, "_latest_positions_snapshot", []) or []
        active_positions_snapshot = getattr(terminal, "_active_positions_snapshot", None)
        if callable(active_positions_snapshot):
            positions_snapshot = active_positions_snapshot()
        terminal._populate_positions_table(positions_snapshot)
        terminal._refresh_position_analysis_window()
        mark_dirty = getattr(terminal, "_mark_terminal_refresh_dirty", None)
        if callable(mark_dirty):
            mark_dirty("risk_heatmap")
        terminal._last_positions_refresh_at = time.monotonic()
        return
    broker = getattr(terminal.controller, "broker", None)
    positions = []
    if broker is not None and hasattr(broker, "fetch_positions"):
        try:
            positions = await broker.fetch_positions()
        except Exception as exc:
            terminal.logger.debug("Positions refresh failed: %s", exc)

    if not positions:
        positions = terminal._portfolio_positions_snapshot()

    terminal._latest_positions_snapshot = positions or []
    positions_snapshot = terminal._latest_positions_snapshot
    active_positions_snapshot = getattr(terminal, "_active_positions_snapshot", None)
    if callable(active_positions_snapshot):
        positions_snapshot = active_positions_snapshot()
    terminal._populate_positions_table(positions_snapshot)
    terminal._refresh_position_analysis_window()
    mark_dirty = getattr(terminal, "_mark_terminal_refresh_dirty", None)
    if callable(mark_dirty):
        mark_dirty("risk_heatmap")
    review_queue = getattr(getattr(terminal, "controller", None), "queue_pending_user_trade_position_reviews", None)
    if callable(review_queue):
        try:
            review_queue(positions_snapshot)
        except Exception as exc:
            terminal.logger.debug("Pending user trade review scheduling failed: %s", exc)
    terminal._last_positions_refresh_at = time.monotonic()


def schedule_positions_refresh(terminal):
    if _authoritative_server_runtime(terminal):
        return
    task = getattr(terminal, "_positions_refresh_task", None)
    if task is not None and not task.done():
        return

    interval_seconds = _positions_refresh_interval_seconds(terminal)
    if interval_seconds > 0:
        last_refresh_at = float(getattr(terminal, "_last_positions_refresh_at", 0.0) or 0.0)
        if (time.monotonic() - last_refresh_at) < interval_seconds:
            return

    try:
        terminal._positions_refresh_task = asyncio.get_event_loop().create_task(terminal._refresh_positions_async())
    except Exception as exc:
        terminal.logger.debug("Unable to schedule positions refresh: %s", exc)


async def refresh_open_orders_async(terminal):
    if terminal._ui_shutting_down:
        return
    if _authoritative_server_runtime(terminal):
        terminal._populate_open_orders_table(getattr(terminal, "_latest_open_orders_snapshot", []) or [])
        terminal._last_open_orders_refresh_at = time.monotonic()
        return
    broker = getattr(terminal.controller, "broker", None)
    orders = []
    if broker is not None and hasattr(broker, "fetch_open_orders"):
        try:
            snapshot = getattr(broker, "fetch_open_orders_snapshot", None)
            if callable(snapshot):
                orders = await snapshot(symbols=getattr(terminal.controller, "symbols", []), limit=200)
            else:
                active_symbol = str(terminal._current_chart_symbol() or "").strip()
                request = {"limit": 200}
                if active_symbol:
                    request["symbol"] = active_symbol
                orders = await broker.fetch_open_orders(**request)
        except TypeError:
            active_symbol = str(terminal._current_chart_symbol() or "").strip()
            if active_symbol:
                orders = await broker.fetch_open_orders(active_symbol, 200)
            else:
                orders = await broker.fetch_open_orders()
        except Exception as exc:
            terminal.logger.debug("Open orders refresh failed: %s", exc)

    terminal._latest_open_orders_snapshot = orders or []
    orders_snapshot = terminal._latest_open_orders_snapshot
    active_open_orders_snapshot = getattr(terminal, "_active_open_orders_snapshot", None)
    if callable(active_open_orders_snapshot):
        orders_snapshot = active_open_orders_snapshot()
    terminal._populate_open_orders_table(orders_snapshot)
    terminal._last_open_orders_refresh_at = time.monotonic()


async def refresh_assets_async(terminal):
    if terminal._ui_shutting_down:
        return
    if _authoritative_server_runtime(terminal):
        terminal._populate_assets_table(getattr(terminal, "_latest_assets_snapshot", {}) or {})
        terminal._last_assets_refresh_at = time.monotonic()
        return
    controller = getattr(terminal, "controller", None)
    broker = getattr(controller, "broker", None)
    balances = dict(getattr(controller, "balances", {}) or {})
    if broker is not None and hasattr(broker, "fetch_balance"):
        try:
            fetch_balances = getattr(controller, "_fetch_balances", None)
            if callable(fetch_balances):
                balances = await fetch_balances(broker)
            else:
                payload = await broker.fetch_balance()
                balances = dict(payload or {}) if isinstance(payload, dict) else {"raw": payload}
            if controller is not None:
                controller.balances = dict(balances or {})
                if hasattr(controller, "balance"):
                    controller.balance = dict(balances or {})
        except Exception as exc:
            terminal.logger.debug("Assets refresh failed: %s", exc)

    terminal._latest_assets_snapshot = dict(balances or {})
    terminal._populate_assets_table(terminal._latest_assets_snapshot)
    terminal._last_assets_refresh_at = time.monotonic()


async def refresh_order_history_async(terminal):
    if terminal._ui_shutting_down:
        return
    if _authoritative_server_runtime(terminal):
        terminal._populate_order_history_table(getattr(terminal, "_latest_order_history_snapshot", []) or [])
        terminal._last_order_history_refresh_at = time.monotonic()
        return
    controller = getattr(terminal, "controller", None)
    broker = getattr(controller, "broker", None)
    rows = []

    fetcher = getattr(controller, "fetch_order_history", None)
    if callable(fetcher):
        try:
            rows = list(await fetcher(limit=200) or [])
        except Exception as exc:
            terminal.logger.debug("Order-history refresh via controller failed: %s", exc)

    if not rows and broker is not None:
        try:
            if hasattr(broker, "fetch_orders"):
                rows = list(await broker.fetch_orders(limit=200) or [])
        except TypeError:
            try:
                rows = list(await broker.fetch_orders() or [])
            except Exception as exc:
                terminal.logger.debug("Order-history refresh failed: %s", exc)
        except Exception as exc:
            terminal.logger.debug("Order-history refresh failed: %s", exc)

        if not rows:
            try:
                if hasattr(broker, "fetch_closed_orders"):
                    rows = list(await broker.fetch_closed_orders(limit=200) or [])
            except TypeError:
                try:
                    rows = list(await broker.fetch_closed_orders() or [])
                except Exception as exc:
                    terminal.logger.debug("Closed-order history refresh failed: %s", exc)
            except Exception as exc:
                terminal.logger.debug("Closed-order history refresh failed: %s", exc)

    terminal._latest_order_history_snapshot = list(rows or [])
    terminal._populate_order_history_table(terminal._latest_order_history_snapshot)
    terminal._last_order_history_refresh_at = time.monotonic()


async def refresh_trade_history_async(terminal):
    if terminal._ui_shutting_down:
        return
    if _authoritative_server_runtime(terminal):
        terminal._populate_trade_history_table(getattr(terminal, "_latest_trade_history_snapshot", []) or [])
        terminal._last_trade_history_refresh_at = time.monotonic()
        return
    controller = getattr(terminal, "controller", None)
    broker = getattr(controller, "broker", None)
    rows = []

    fetcher = getattr(controller, "fetch_trade_history", None)
    if callable(fetcher):
        try:
            rows = list(await fetcher(limit=200) or [])
        except Exception as exc:
            terminal.logger.debug("Trade-history refresh via controller failed: %s", exc)

    if not rows and broker is not None and hasattr(broker, "fetch_my_trades"):
        try:
            rows = list(await broker.fetch_my_trades(limit=200) or [])
        except TypeError:
            try:
                rows = list(await broker.fetch_my_trades() or [])
            except Exception as exc:
                terminal.logger.debug("Trade-history refresh from broker failed: %s", exc)
        except Exception as exc:
            terminal.logger.debug("Trade-history refresh from broker failed: %s", exc)

    if not rows:
        loader = getattr(controller, "_load_recent_trades", None)
        if callable(loader):
            try:
                rows = list(await loader(limit=200) or [])
            except Exception as exc:
                terminal.logger.debug("Trade-history refresh from repository failed: %s", exc)

    terminal._latest_trade_history_snapshot = list(rows or [])
    terminal._populate_trade_history_table(terminal._latest_trade_history_snapshot)
    terminal._last_trade_history_refresh_at = time.monotonic()


def schedule_open_orders_refresh(terminal):
    if _authoritative_server_runtime(terminal):
        return
    task = getattr(terminal, "_open_orders_refresh_task", None)
    if task is not None and not task.done():
        return

    interval_seconds = _open_orders_refresh_interval_seconds(terminal)
    if interval_seconds > 0:
        last_refresh_at = float(getattr(terminal, "_last_open_orders_refresh_at", 0.0) or 0.0)
        if (time.monotonic() - last_refresh_at) < interval_seconds:
            return

    try:
        terminal._open_orders_refresh_task = asyncio.get_event_loop().create_task(terminal._refresh_open_orders_async())
    except Exception as exc:
        terminal.logger.debug("Unable to schedule open-orders refresh: %s", exc)


def schedule_assets_refresh(terminal):
    if _authoritative_server_runtime(terminal):
        return
    task = getattr(terminal, "_assets_refresh_task", None)
    if task is not None and not task.done():
        return

    interval_seconds = _assets_refresh_interval_seconds(terminal)
    if interval_seconds > 0:
        last_refresh_at = float(getattr(terminal, "_last_assets_refresh_at", 0.0) or 0.0)
        if (time.monotonic() - last_refresh_at) < interval_seconds:
            return

    try:
        terminal._assets_refresh_task = asyncio.get_event_loop().create_task(terminal._refresh_assets_async())
    except Exception as exc:
        terminal.logger.debug("Unable to schedule assets refresh: %s", exc)


def schedule_order_history_refresh(terminal):
    if _authoritative_server_runtime(terminal):
        return
    task = getattr(terminal, "_order_history_refresh_task", None)
    if task is not None and not task.done():
        return

    interval_seconds = _history_refresh_interval_seconds(terminal)
    if interval_seconds > 0:
        last_refresh_at = float(getattr(terminal, "_last_order_history_refresh_at", 0.0) or 0.0)
        if (time.monotonic() - last_refresh_at) < interval_seconds:
            return

    try:
        terminal._order_history_refresh_task = asyncio.get_event_loop().create_task(terminal._refresh_order_history_async())
    except Exception as exc:
        terminal.logger.debug("Unable to schedule order-history refresh: %s", exc)


def schedule_trade_history_refresh(terminal):
    if _authoritative_server_runtime(terminal):
        return
    task = getattr(terminal, "_trade_history_refresh_task", None)
    if task is not None and not task.done():
        return

    interval_seconds = _history_refresh_interval_seconds(terminal)
    if interval_seconds > 0:
        last_refresh_at = float(getattr(terminal, "_last_trade_history_refresh_at", 0.0) or 0.0)
        if (time.monotonic() - last_refresh_at) < interval_seconds:
            return

    try:
        terminal._trade_history_refresh_task = asyncio.get_event_loop().create_task(terminal._refresh_trade_history_async())
    except Exception as exc:
        terminal.logger.debug("Unable to schedule trade-history refresh: %s", exc)


async def load_persisted_runtime_data(terminal):
    """
    Load and replay trade history progressively.
    
    Strategy:
    - Load all trades from database
    - Replay in batches with event loop yields
    - Prevents UI freeze during journal population
    - Shows trades progressively as they load
    """
    loader = getattr(terminal.controller, "_load_recent_trades", None)
    if loader is None:
        return

    try:
        trades = await loader(limit=min(int(terminal.MAX_LOG_ROWS or 200), 200))
    except Exception:
        terminal.logger.exception("Failed to load persisted trade history")
        return

    batch_size = max(1, int(getattr(terminal, "STARTUP_TRADE_REPLAY_BATCH_SIZE", 25) or 25))
    total = len(trades or [])

    for index, trade in enumerate(trades, start=1):
        if getattr(terminal, "_ui_shutting_down", False):
            break
        terminal._update_trade_log(trade)
        # Yield control after each trade to allow UI updates
        if index < total:
            await asyncio.sleep(0)
        # Also yield after batch for efficiency
        if (index % batch_size) == 0:
            await asyncio.sleep(0)


async def load_initial_terminal_data(terminal):
    """
    Progressive data loading for desktop terminal.
    
    Performance Optimization Strategy:
    - Load critical data first (assets/balances)
    - Update UI after each stage
    - Allow event loop to process between stages
    - Non-critical data (order/trade history) loads in background
    - User sees responsive UI immediately instead of frozen loading screen
    """
    def _set_loading(title, detail=None, *, visible=True):
        updater = getattr(terminal, "_set_workspace_loading_state", None)
        if callable(updater):
            updater(title, detail, visible=visible)

    async def _run_stage(title, detail, operation, *, continue_on_error=True):
        if getattr(terminal, "_ui_shutting_down", False):
            return None
        _set_loading(title, detail)
        await asyncio.sleep(0)
        try:
            return await asyncio.wait_for(
                operation(),
                timeout=float(getattr(terminal, "INITIAL_STAGE_TIMEOUT_SECONDS", INITIAL_STAGE_TIMEOUT_SECONDS)),
            )
        except asyncio.TimeoutError as exc:
            logger = getattr(terminal, "logger", None)
            if logger is not None:
                logger.warning("Initial runtime stage timed out: %s", title)
            if continue_on_error:
                return None
            raise RuntimeError(f"{title} timed out.") from exc
        except Exception as exc:
            logger = getattr(terminal, "logger", None)
            if logger is not None:
                logger.debug("Initial runtime stage failed: %s", exc, exc_info=True)
            if continue_on_error:
                return None
            raise
        finally:
            await asyncio.sleep(0)

    try:
        if _authoritative_server_runtime(terminal):
            # Server handles all data, just refresh UI
            _set_loading("Loading from server...", "Fetching latest account state.")
            refresher = getattr(terminal, "_refresh_terminal", None)
            if callable(refresher):
                refresher()
        else:
            # Progressive loading: critical data first, background data after
            
            # Stage 1: Load balances (critical - needed for display)
            assets_op = getattr(terminal, "_refresh_assets_async", None)
            if callable(assets_op):
                await _run_stage(
                    "Loading trading workspace...",
                    "Syncing account balances and assets.",
                    assets_op,
                )
                await asyncio.sleep(0)
                refresher = getattr(terminal, "_refresh_terminal", None)
                if callable(refresher):
                    refresher()
            
            # Stage 2: Load positions and open orders (important for trading)
            positions_op = getattr(terminal, "_refresh_positions_async", None)
            orders_op = getattr(terminal, "_refresh_open_orders_async", None)
            
            if callable(positions_op):
                await _run_stage(
                    "Loading positions...",
                    "Fetching your current positions.",
                    positions_op,
                    continue_on_error=True,
                )
                await asyncio.sleep(0)
                
            if callable(orders_op):
                await _run_stage(
                    "Loading open orders...",
                    "Retrieving active orders.",
                    orders_op,
                    continue_on_error=True,
                )
                await asyncio.sleep(0)
                
            # Update UI after critical data loads
            refresher = getattr(terminal, "_refresh_terminal", None)
            if callable(refresher):
                refresher()
            
            # Stage 3: Load historical data (less critical - can be in background)
            order_history_op = getattr(terminal, "_refresh_order_history_async", None)
            if callable(order_history_op):
                await _run_stage(
                    "Loading order history...",
                    "Retrieving recent orders.",
                    order_history_op,
                    continue_on_error=True,
                )
                await asyncio.sleep(0)
            
            trade_history_op = getattr(terminal, "_refresh_trade_history_async", None)
            if callable(trade_history_op):
                await _run_stage(
                    "Loading trade history...",
                    "Retrieving recent trades.",
                    trade_history_op,
                    continue_on_error=True,
                )
                await asyncio.sleep(0)
            
            # Update UI after all data loads
            refresher = getattr(terminal, "_refresh_terminal", None)
            if callable(refresher):
                refresher()
            
            # Stage 4: Load persisted runtime data (trade journal)
            await _run_stage(
                "Restoring trade activity...",
                "Replaying recent executions into the terminal journal.",
                lambda: load_persisted_runtime_data(terminal),
                continue_on_error=True,
            )
            
            # Stage 5: Load chart bootstrap (non-critical, can take time)
            chart_loader = getattr(terminal, "_load_active_chart_bootstrap_async", None)
            if callable(chart_loader):
                await _run_stage(
                    "Loading market data...",
                    "Fetching the active chart so the workspace opens with live context.",
                    chart_loader,
                    continue_on_error=True,
                )
            
            # Final refresh
            if callable(refresher):
                refresher()
    finally:
        _set_loading(None, None, visible=False)
