from datetime import datetime, timezone


def build_runtime_metrics_snapshot(terminal):
    controller = getattr(terminal, "controller", None)
    balances = getattr(controller, "balances", {}) or {}

    balance_equity = None
    resolve_equity = getattr(controller, "_extract_balance_equity_value", None)
    if callable(resolve_equity):
        try:
            balance_equity = resolve_equity(balances)
        except Exception:
            balance_equity = None

    portfolio_equity = None
    portfolio = getattr(controller, "portfolio", None)
    get_equity = getattr(portfolio, "get_equity", None)
    if callable(get_equity):
        try:
            portfolio_equity = get_equity()
        except Exception:
            portfolio_equity = None

    positions_resolver = getattr(terminal, "_active_positions_snapshot", None)
    positions = list(positions_resolver() or []) if callable(positions_resolver) else []
    open_orders_resolver = getattr(terminal, "_active_open_orders_snapshot", None)
    open_orders = list(open_orders_resolver() or []) if callable(open_orders_resolver) else []

    generated_at = datetime.now(timezone.utc)
    return {
        "balances": balances,
        "free_balances": balances.get("free", 0) if isinstance(balances, dict) else 0,
        "used_balances": balances.get("used", 0) if isinstance(balances, dict) else 0,
        "balance_equity": balance_equity,
        "portfolio_equity": portfolio_equity,
        "equity_value": float(balance_equity) if balance_equity is not None else float(portfolio_equity or 0.0),
        "equity_source": "balances" if balance_equity is not None else "portfolio",
        "equity_timestamp": generated_at.timestamp(),
        "positions": positions,
        "open_orders": open_orders,
        "position_count": len(positions),
        "open_order_count": len(open_orders),
        "spread_pct": getattr(controller, "spread_pct", 0),
        "symbols_loaded": len(getattr(controller, "symbols", []) or []),
    }
