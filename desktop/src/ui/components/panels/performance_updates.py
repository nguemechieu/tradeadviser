import html

import numpy as np
from PySide6.QtWidgets import QTableWidgetItem


def performance_snapshot(terminal):
    equity_series = []
    for value in terminal._performance_series():
        numeric = terminal._safe_float(value)
        if numeric is not None:
            equity_series.append(numeric)

    equity_timestamps = []
    time_series_getter = getattr(terminal, "_performance_time_series", None)
    if callable(time_series_getter):
        for value in time_series_getter():
            numeric = terminal._safe_float(value)
            if numeric is not None:
                equity_timestamps.append(numeric)
    if len(equity_timestamps) != len(equity_series):
        equity_timestamps = []

    runtime_metrics = {}
    runtime_metrics_getter = getattr(terminal, "_runtime_metrics_snapshot", None)
    if callable(runtime_metrics_getter):
        try:
            runtime_metrics = runtime_metrics_getter() or {}
        except Exception:
            runtime_metrics = {}

    current_equity = terminal._safe_float(runtime_metrics.get("equity_value"))
    current_equity_timestamp = terminal._safe_float(runtime_metrics.get("equity_timestamp"))
    current_open_orders = runtime_metrics.get("open_order_count")
    if current_open_orders is None:
        current_open_orders = len(runtime_metrics.get("open_orders", []) or [])
    try:
        current_open_orders = int(current_open_orders or 0)
    except (TypeError, ValueError):
        current_open_orders = 0

    if current_equity is not None:
        if not equity_series or equity_series[-1] != current_equity:
            equity_series.append(current_equity)
            if equity_timestamps:
                if current_equity_timestamp is not None:
                    equity_timestamps.append(current_equity_timestamp)
                else:
                    equity_timestamps = []
            elif current_equity_timestamp is not None:
                equity_timestamps = [current_equity_timestamp]
        elif not equity_timestamps and current_equity_timestamp is not None and len(equity_series) == 1:
            equity_timestamps = [current_equity_timestamp]

    perf = getattr(terminal.controller, "performance_engine", None)
    report = {}
    if perf is not None and hasattr(perf, "report"):
        try:
            report = perf.report() or {}
        except Exception:
            report = {}

    initial_equity = equity_series[0] if equity_series else None
    latest_equity = equity_series[-1] if equity_series else None
    net_pnl = None
    if initial_equity is not None and latest_equity is not None:
        net_pnl = latest_equity - initial_equity

    drawdown_series = []
    current_drawdown = None
    max_drawdown = terminal._safe_float(report.get("max_drawdown"))
    if equity_series:
        equity_array = np.asarray(equity_series, dtype=float)
        running_peak = np.maximum.accumulate(equity_array)
        safe_peaks = np.where(running_peak == 0, 1.0, running_peak)
        drawdown_series = ((equity_array / safe_peaks) - 1.0).tolist()
        current_drawdown = abs(drawdown_series[-1]) if drawdown_series else 0.0
        if max_drawdown is None:
            max_drawdown = abs(min(drawdown_series))

    trades = terminal._performance_trade_records()
    trade_count = len(trades)
    pending_statuses = {"submitted", "open", "new", "pending", "partially_filled"}
    rejected_statuses = {"rejected", "failed", "error"}
    canceled_statuses = {"canceled", "cancelled"}
    historical_pending_orders = 0
    rejected_orders = 0
    canceled_orders = 0
    symbol_stats = {}
    realized_pnls = []
    fee_values = []
    spread_values = []
    slippage_values = []

    for trade in trades:
        status = str(trade.get("status") or "").strip().lower()
        symbol = str(trade.get("symbol") or "-").strip() or "-"
        pnl = terminal._safe_float(trade.get("pnl"))

        stats = symbol_stats.setdefault(
            symbol,
            {"symbol": symbol, "orders": 0, "realized": 0, "wins": 0, "pnl": 0.0},
        )
        stats["orders"] += 1

        if status in pending_statuses:
            historical_pending_orders += 1
        elif status in rejected_statuses:
            rejected_orders += 1
        elif status in canceled_statuses:
            canceled_orders += 1

        if pnl is not None:
            realized_pnls.append({"symbol": symbol, "pnl": pnl})
            stats["realized"] += 1
            stats["pnl"] += pnl
            if pnl > 0:
                stats["wins"] += 1

        fee = terminal._safe_float(trade.get("fee"))
        if fee is not None:
            fee_values.append(fee)

        spread_bps = terminal._safe_float(trade.get("spread_bps"))
        if spread_bps is not None:
            spread_values.append(spread_bps)

        slippage_bps = terminal._safe_float(trade.get("slippage_bps"))
        if slippage_bps is not None:
            slippage_values.append(slippage_bps)

    realized_trade_count = len(realized_pnls)
    pnl_values = [entry["pnl"] for entry in realized_pnls]
    gross_profit = sum(value for value in pnl_values if value > 0)
    gross_loss = sum(value for value in pnl_values if value < 0)
    win_count = sum(1 for value in pnl_values if value > 0)
    win_rate = (win_count / realized_trade_count) if realized_trade_count else None
    avg_trade = (sum(pnl_values) / realized_trade_count) if realized_trade_count else None
    best_trade = max(pnl_values) if pnl_values else None
    worst_trade = min(pnl_values) if pnl_values else None
    total_fees = sum(fee_values) if fee_values else 0.0
    avg_fee = (total_fees / len(fee_values)) if fee_values else None
    avg_spread_bps = (sum(spread_values) / len(spread_values)) if spread_values else None
    avg_slippage_bps = (sum(slippage_values) / len(slippage_values)) if slippage_values else None
    worst_slippage_bps = max(slippage_values) if slippage_values else None
    execution_drag = total_fees + sum(max(value, 0.0) for value in slippage_values)
    if gross_loss < 0:
        profit_factor = gross_profit / abs(gross_loss)
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = None

    symbol_rows = []
    for symbol, stats in symbol_stats.items():
        realized = int(stats["realized"])
        symbol_rows.append(
            {
                "symbol": symbol,
                "orders": int(stats["orders"]),
                "realized": realized,
                "win_rate": (stats["wins"] / realized) if realized else None,
                "net_pnl": stats["pnl"],
                "avg_pnl": (stats["pnl"] / realized) if realized else None,
            }
        )
    symbol_rows.sort(key=lambda item: (item["net_pnl"], item["realized"], item["orders"]), reverse=True)

    sharpe_ratio = terminal._safe_float(report.get("sharpe_ratio"))
    sortino_ratio = terminal._safe_float(report.get("sortino_ratio"))
    volatility = terminal._safe_float(report.get("volatility"))
    value_at_risk = terminal._safe_float(report.get("value_at_risk"))
    conditional_var = terminal._safe_float(report.get("conditional_var"))
    cumulative_return = terminal._safe_float(report.get("cumulative_return"))
    if cumulative_return is None and initial_equity not in (None, 0) and latest_equity is not None:
        cumulative_return = (latest_equity / initial_equity) - 1.0

    open_order_count = current_open_orders if runtime_metrics else historical_pending_orders

    if realized_trade_count == 0 and len(equity_series) < 2:
        health = "Not enough data"
    elif (sharpe_ratio is not None and sharpe_ratio >= 1.0) and (max_drawdown is not None and max_drawdown <= 0.08):
        health = "Strong risk-adjusted performance"
    elif (net_pnl is not None and net_pnl >= 0) and (max_drawdown is None or max_drawdown <= 0.15):
        health = "Constructive but still developing"
    else:
        health = "Needs closer risk review"

    best_symbol = symbol_rows[0] if symbol_rows else None
    summary_bits = []
    if net_pnl is not None:
        summary_bits.append(f"net PnL {terminal._format_currency(net_pnl)}")
    if cumulative_return is not None:
        summary_bits.append(f"return {terminal._format_percent_text(cumulative_return)}")
    if max_drawdown is not None:
        summary_bits.append(f"max drawdown {terminal._format_percent_text(max_drawdown)}")
    if win_rate is not None:
        summary_bits.append(f"win rate {terminal._format_percent_text(win_rate)}")
    headline = health
    if summary_bits:
        headline = f"{health}. Current read: " + ", ".join(summary_bits[:4]) + "."

    insights = []
    if latest_equity is not None and initial_equity is not None:
        insights.append(
            f"Equity moved from <b>{terminal._format_currency(initial_equity)}</b> to <b>{terminal._format_currency(latest_equity)}</b>, for a net change of <b>{terminal._format_currency(net_pnl)}</b>."
        )
    if realized_trade_count:
        trade_quality = f"{realized_trade_count} realized trades"
        if win_rate is not None:
            trade_quality += f", <b>{terminal._format_percent_text(win_rate)}</b> win rate"
        if profit_factor is not None:
            profit_factor_text = "infinite" if profit_factor == float("inf") else terminal._format_ratio_text(profit_factor)
            trade_quality += f", profit factor <b>{profit_factor_text}</b>"
        insights.append(trade_quality + ".")
    else:
        insights.append("No realized PnL history yet, so trade-quality metrics are still warming up.")

    if best_symbol is not None and best_symbol.get("realized", 0) > 0:
        insights.append(
            f"Best contributing symbol so far is <b>{html.escape(best_symbol['symbol'])}</b> with {best_symbol['realized']} realized trades and <b>{terminal._format_currency(best_symbol['net_pnl'])}</b> net PnL."
        )

    execution_notes = []
    if open_order_count:
        execution_notes.append(f"{open_order_count} open orders")
    if rejected_orders:
        execution_notes.append(f"{rejected_orders} rejected orders")
    if canceled_orders:
        execution_notes.append(f"{canceled_orders} canceled orders")
    if execution_notes:
        insights.append("Execution state: " + ", ".join(execution_notes) + ".")

    if spread_values or slippage_values or fee_values:
        parts = []
        if avg_spread_bps is not None:
            parts.append(f"avg spread <b>{avg_spread_bps:.2f} bps</b>")
        if avg_slippage_bps is not None:
            parts.append(f"avg slippage <b>{avg_slippage_bps:.2f} bps</b>")
        if total_fees:
            parts.append(f"fees <b>{terminal._format_currency(total_fees)}</b>")
        if parts:
            insights.append("Execution quality: " + ", ".join(parts) + ".")

    if max_drawdown is not None and max_drawdown >= 0.15:
        insights.append("Drawdown is elevated relative to the current sample; position sizing or strategy selectivity may need tightening.")
    elif max_drawdown is not None:
        insights.append("Drawdown remains contained relative to the current sample, which is a healthier sign than raw PnL alone.")

    metrics = {
        "Equity": {"text": terminal._format_currency(latest_equity), "tone": "neutral"},
        "Starting Equity": {"text": terminal._format_currency(initial_equity), "tone": "muted"},
        "Net PnL": {"text": terminal._format_currency(net_pnl), "tone": "positive" if (net_pnl or 0) > 0 else "negative" if (net_pnl or 0) < 0 else "neutral"},
        "Return": {"text": terminal._format_percent_text(cumulative_return), "tone": "positive" if (cumulative_return or 0) > 0 else "negative" if (cumulative_return or 0) < 0 else "neutral"},
        "Samples": {"text": str(len(equity_series)), "tone": "muted"},
        "Trades": {"text": str(trade_count), "tone": "muted"},
        "Realized Trades": {"text": str(realized_trade_count), "tone": "muted"},
        "Open Orders": {"text": str(open_order_count), "tone": "warning" if open_order_count else "muted"},
        "Pending Orders": {"text": str(open_order_count), "tone": "warning" if open_order_count else "muted"},
        "Win Rate": {"text": terminal._format_percent_text(win_rate), "tone": "positive" if (win_rate or 0) >= 0.5 and win_rate is not None else "neutral"},
        "Profit Factor": {"text": "infinite" if profit_factor == float("inf") else terminal._format_ratio_text(profit_factor), "tone": "positive" if profit_factor not in (None, float("inf")) and profit_factor >= 1.2 else "neutral"},
        "Fees": {"text": terminal._format_currency(total_fees), "tone": "warning" if total_fees > 0 else "muted"},
        "Avg Fee": {"text": terminal._format_currency(avg_fee), "tone": "muted"},
        "Avg Spread": {"text": "-" if avg_spread_bps is None else f"{avg_spread_bps:.2f} bps", "tone": "warning" if (avg_spread_bps or 0) >= 20 else "neutral"},
        "Avg Slippage": {"text": "-" if avg_slippage_bps is None else f"{avg_slippage_bps:.2f} bps", "tone": "warning" if (avg_slippage_bps or 0) > 0 else "neutral"},
        "Worst Slippage": {"text": "-" if worst_slippage_bps is None else f"{worst_slippage_bps:.2f} bps", "tone": "warning" if (worst_slippage_bps or 0) > 0 else "neutral"},
        "Execution Drag": {"text": terminal._format_currency(execution_drag), "tone": "warning" if execution_drag > 0 else "muted"},
        "Volatility": {"text": terminal._format_percent_text(volatility), "tone": "warning" if (volatility or 0) > 0.4 else "neutral"},
        "Sharpe Ratio": {"text": terminal._format_ratio_text(sharpe_ratio), "tone": "positive" if (sharpe_ratio or 0) >= 1.0 else "negative" if sharpe_ratio is not None and sharpe_ratio < 0 else "neutral"},
        "Sortino Ratio": {"text": terminal._format_ratio_text(sortino_ratio), "tone": "positive" if (sortino_ratio or 0) >= 1.0 else "negative" if sortino_ratio is not None and sortino_ratio < 0 else "neutral"},
        "Max Drawdown": {"text": terminal._format_percent_text(max_drawdown), "tone": "negative" if (max_drawdown or 0) >= 0.1 else "positive" if max_drawdown is not None else "neutral"},
        "Current Drawdown": {"text": terminal._format_percent_text(current_drawdown), "tone": "negative" if (current_drawdown or 0) >= 0.05 else "neutral"},
        "VaR (95%)": {"text": terminal._format_percent_text(value_at_risk), "tone": "warning" if value_at_risk is not None and value_at_risk < 0 else "neutral"},
        "CVaR (95%)": {"text": terminal._format_percent_text(conditional_var), "tone": "warning" if conditional_var is not None and conditional_var < 0 else "neutral"},
        "Best Trade": {"text": terminal._format_currency(best_trade), "tone": "positive" if best_trade is not None and best_trade > 0 else "neutral"},
        "Worst Trade": {"text": terminal._format_currency(worst_trade), "tone": "negative" if worst_trade is not None and worst_trade < 0 else "neutral"},
        "Avg Trade": {"text": terminal._format_currency(avg_trade), "tone": "positive" if avg_trade is not None and avg_trade > 0 else "negative" if avg_trade is not None and avg_trade < 0 else "neutral"},
    }

    return {
        "headline": headline,
        "insights": insights,
        "metrics": metrics,
        "equity_series": equity_series,
        "equity_timestamps": equity_timestamps,
        "drawdown_series": [abs(value) for value in drawdown_series],
        "drawdown_timestamps": list(equity_timestamps),
        "symbol_rows": symbol_rows[:8],
    }


def populate_performance_symbol_table(terminal, table, symbol_rows):
    if table is None:
        return
    table.setRowCount(0)
    for row_data in symbol_rows:
        row = table.rowCount()
        table.insertRow(row)
        values = [
            row_data.get("symbol", "-"),
            str(int(row_data.get("orders", 0) or 0)),
            str(int(row_data.get("realized", 0) or 0)),
            terminal._format_percent_text(row_data.get("win_rate")),
            terminal._format_currency(row_data.get("net_pnl")),
            terminal._format_currency(row_data.get("avg_pnl")),
        ]
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))
    table.horizontalHeader().setStretchLastSection(True)


def populate_performance_view(terminal, widgets, snapshot):
    if not widgets:
        return

    summary = widgets.get("summary")
    if summary is not None:
        summary.setText(snapshot.get("headline", "Performance snapshot unavailable."))

    metric_labels = widgets.get("metric_labels", {})
    for name, label in metric_labels.items():
        meta = snapshot.get("metrics", {}).get(name, {"text": "-", "tone": "neutral"})
        label.setText(meta.get("text", "-"))
        label.setStyleSheet(terminal._performance_metric_style(meta.get("tone", "neutral")))

    curve = widgets.get("equity_curve")
    if curve is not None:
        equity_series = snapshot.get("equity_series", [])
        equity_timestamps = snapshot.get("equity_timestamps", [])
        if equity_timestamps and len(equity_timestamps) == len(equity_series):
            curve.setData(equity_timestamps, equity_series)
        else:
            curve.setData(equity_series)

    drawdown_curve = widgets.get("drawdown_curve")
    if drawdown_curve is not None:
        drawdown_series = snapshot.get("drawdown_series", [])
        drawdown_timestamps = snapshot.get("drawdown_timestamps", [])
        if drawdown_timestamps and len(drawdown_timestamps) == len(drawdown_series):
            drawdown_curve.setData(drawdown_timestamps, drawdown_series)
        else:
            drawdown_curve.setData(drawdown_series)

    insights = widgets.get("insights")
    if insights is not None:
        lines = "".join(f"<li>{line}</li>" for line in snapshot.get("insights", []))
        insights.setHtml(f"<ul style='margin-top:4px;'>{lines}</ul>")

    populate_performance_symbol_table(terminal, widgets.get("symbol_table"), snapshot.get("symbol_rows", []))


def refresh_performance_views(terminal):
    snapshot = terminal._performance_snapshot()
    panel_widgets = getattr(terminal, "_performance_panel_widgets", None)
    if panel_widgets:
        terminal._populate_performance_view(panel_widgets, snapshot)

    window = getattr(terminal, "detached_tool_windows", {}).get("performance_analytics")
    if terminal._is_qt_object_alive(window):
        terminal._populate_performance_view(getattr(window, "_performance_widgets", None), snapshot)
