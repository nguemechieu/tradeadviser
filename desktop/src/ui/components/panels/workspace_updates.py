import time

import numpy as np
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from strategy.strategy import Strategy


def _strategy_scorecard_signature(rows):
    return tuple(
        (
            str(row.get("strategy") or ""),
            str(row.get("source") or ""),
            int(row.get("orders") or 0),
            int(row.get("realized") or 0),
            "-" if row.get("win_rate") is None else f"{float(row.get('win_rate')):.6f}",
            f"{float(row.get('net_pnl') or 0.0):.6f}",
            "-" if row.get("avg_trade") is None else f"{float(row.get('avg_trade')):.6f}",
            "-" if row.get("avg_conf") is None else f"{float(row.get('avg_conf')):.6f}",
            "-" if row.get("avg_spread") is None else f"{float(row.get('avg_spread')):.6f}",
            "-" if row.get("avg_slip") is None else f"{float(row.get('avg_slip')):.6f}",
            f"{float(row.get('fees') or 0.0):.6f}",
        )
        for row in rows
    )


def refresh_strategy_comparison_panel(terminal):
    table = getattr(terminal, "strategy_table", None)
    if table is None:
        return

    rows = strategy_scorecard_rows(terminal)
    signature = _strategy_scorecard_signature(rows)
    if signature == getattr(terminal, "_strategy_comparison_signature", None):
        return

    terminal._strategy_comparison_signature = signature
    try:
        previous_updates_enabled = bool(table.updatesEnabled())
    except Exception:
        previous_updates_enabled = True

    table.setUpdatesEnabled(False)
    try:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["strategy"],
                row["source"],
                row.get("orders", ""),
                row.get("realized", ""),
                terminal._format_percent_text(row.get("win_rate")),
                terminal._format_currency(row.get("net_pnl")),
                terminal._format_currency(row.get("avg_trade")),
                terminal._format_percent_text(row.get("avg_conf")),
                "-" if row.get("avg_spread") is None else f"{float(row.get('avg_spread')):.2f} bps",
                "-" if row.get("avg_slip") is None else f"{float(row.get('avg_slip')):.2f} bps",
                terminal._format_currency(row.get("fees")),
            ]
            for col, value in enumerate(values):
                table.setItem(row_index, col, QTableWidgetItem(str(value)))
    finally:
        table.setUpdatesEnabled(previous_updates_enabled)

    header = table.horizontalHeader()
    if header is not None:
        header.setStretchLastSection(True)

    now = time.monotonic()
    last_resize_at = float(getattr(table, "_sopotek_last_resize_at", 0.0) or 0.0)
    last_resize_rows = int(getattr(table, "_sopotek_last_resize_rows", -1) or -1)
    row_count = len(rows)
    should_resize = (
        row_count <= 12
        or last_resize_at <= 0.0
        or row_count != last_resize_rows
        or (now - last_resize_at) >= 20.0
    )
    if should_resize:
        table.resizeColumnsToContents()
        table._sopotek_last_resize_at = now
        table._sopotek_last_resize_rows = row_count


def strategy_scorecard_rows(terminal):
    active_name = Strategy.normalize_strategy_name(
        getattr(terminal.controller, "strategy_name", None)
        or getattr(getattr(terminal.controller, "config", None), "strategy", "Trend Following")
    )
    grouped = {}

    for trade in terminal._performance_trade_records():
        source = str(trade.get("source") or "").strip().lower() or "runtime"
        strategy_name = str(trade.get("strategy_name") or "").strip()
        if source == "manual" and not strategy_name:
            strategy_name = "Manual"
        strategy_name = Strategy.normalize_strategy_name(strategy_name or active_name)

        row = grouped.setdefault(
            strategy_name,
            {
                "strategy": strategy_name,
                "sources": set(),
                "orders": 0,
                "realized": 0,
                "wins": 0,
                "net_pnl": 0.0,
                "confidence_total": 0.0,
                "confidence_count": 0,
                "slippage_total": 0.0,
                "slippage_count": 0,
                "spread_total": 0.0,
                "spread_count": 0,
                "fee_total": 0.0,
            },
        )
        row["sources"].add(source)
        row["orders"] += 1

        pnl = terminal._safe_float(trade.get("pnl"))
        if pnl is not None:
            row["realized"] += 1
            row["net_pnl"] += pnl
            if pnl > 0:
                row["wins"] += 1

        confidence = terminal._safe_float(trade.get("confidence"))
        if confidence is not None:
            row["confidence_total"] += confidence
            row["confidence_count"] += 1

        slippage_bps = terminal._safe_float(trade.get("slippage_bps"))
        if slippage_bps is not None:
            row["slippage_total"] += slippage_bps
            row["slippage_count"] += 1

        spread_bps = terminal._safe_float(trade.get("spread_bps"))
        if spread_bps is not None:
            row["spread_total"] += spread_bps
            row["spread_count"] += 1

        fee = terminal._safe_float(trade.get("fee"))
        if fee is not None:
            row["fee_total"] += fee

    if not grouped:
        grouped[active_name] = {
            "strategy": active_name,
            "sources": {"runtime"},
            "orders": 0,
            "realized": 0,
            "wins": 0,
            "net_pnl": 0.0,
            "confidence_total": 0.0,
            "confidence_count": 0,
            "slippage_total": 0.0,
            "slippage_count": 0,
            "spread_total": 0.0,
            "spread_count": 0,
            "fee_total": 0.0,
        }

    rows = []
    for data in grouped.values():
        realized = int(data["realized"])
        avg_trade = (data["net_pnl"] / realized) if realized else None
        win_rate = (data["wins"] / realized) if realized else None
        avg_conf = (data["confidence_total"] / data["confidence_count"]) if data["confidence_count"] else None
        avg_slip = (data["slippage_total"] / data["slippage_count"]) if data["slippage_count"] else None
        avg_spread = (data["spread_total"] / data["spread_count"]) if data["spread_count"] else None
        source_values = {str(item).title() for item in data["sources"] if item}
        if len(source_values) == 1:
            source_text = next(iter(source_values))
        elif len(source_values) > 1:
            source_text = "Mixed"
        else:
            source_text = "Runtime"

        rows.append(
            {
                "strategy": data["strategy"],
                "source": source_text,
                "orders": int(data["orders"]),
                "realized": realized,
                "win_rate": win_rate,
                "net_pnl": data["net_pnl"],
                "avg_trade": avg_trade,
                "avg_conf": avg_conf,
                "avg_spread": avg_spread,
                "avg_slip": avg_slip,
                "fees": data["fee_total"],
            }
        )

    rows.sort(
        key=lambda item: (
            terminal._safe_float(item.get("net_pnl"), 0.0) or 0.0,
            terminal._safe_float(item.get("win_rate"), 0.0) or 0.0,
            int(item.get("realized", 0) or 0),
            int(item.get("orders", 0) or 0),
        ),
        reverse=True,
    )
    return rows


def update_orderbook(terminal, symbol, bids, asks):
    if terminal._ui_shutting_down:
        return

    active_symbol = terminal._current_chart_symbol()

    if hasattr(terminal, "orderbook_panel") and active_symbol == symbol:
        terminal.orderbook_panel.update_orderbook(bids, asks)

    for chart in terminal._iter_chart_widgets():
        if chart.symbol == symbol:
            chart.update_orderbook_heatmap(bids, asks)


def update_recent_trades(terminal, symbol, trades):
    if terminal._ui_shutting_down:
        return

    active_symbol = terminal._current_chart_symbol()
    if hasattr(terminal, "orderbook_panel") and active_symbol == symbol:
        terminal.orderbook_panel.update_recent_trades(trades)


def handle_strategy_debug(terminal, debug):
    if terminal._ui_shutting_down:
        return

    if debug is None:
        return

    terminal._record_recommendation(
        symbol=debug.get("symbol", ""),
        signal=debug.get("signal", ""),
        confidence=debug.get("ml_probability", 0.0),
        reason=debug.get("reason", ""),
        strategy="Strategy Engine",
        timestamp=debug.get("timestamp", ""),
    )

    if terminal.debug_table.rowCount() >= int(terminal.MAX_LOG_ROWS or 200):
        terminal.debug_table.removeRow(0)
    row = terminal.debug_table.rowCount()
    terminal.debug_table.insertRow(row)

    terminal.debug_table.setItem(row, 0, QTableWidgetItem(str(debug["index"])))
    terminal.debug_table.setItem(row, 1, QTableWidgetItem(debug["signal"]))
    terminal.debug_table.setItem(row, 2, QTableWidgetItem(str(debug["rsi"])))
    terminal.debug_table.setItem(row, 3, QTableWidgetItem(str(debug["ema_fast"])))
    terminal.debug_table.setItem(row, 4, QTableWidgetItem(str(debug["ema_slow"])))
    terminal.debug_table.setItem(row, 5, QTableWidgetItem(str(debug["ml_probability"])))
    terminal.debug_table.setItem(row, 6, QTableWidgetItem(debug["reason"]))

    for chart in terminal._iter_chart_widgets():
        if chart.symbol == debug["symbol"]:
            chart.add_strategy_signal(
                debug["index"],
                debug.get("price", debug["ema_fast"]),
                debug["signal"],
            )


def set_risk_heatmap_status(terminal, message, tone="muted"):
    label = getattr(terminal, "risk_heatmap_status_label", None)
    if label is None:
        return
    color_map = {
        "muted": "#8fa7c6",
        "warning": "#ffb84d",
        "positive": "#32d296",
        "negative": "#ff6b6b",
    }
    color = color_map.get(tone, "#8fa7c6")
    label.setStyleSheet(f"color: {color}; font-weight: 600; padding: 6px 2px 0 2px;")
    label.setText(str(message or ""))


def risk_heatmap_positions_snapshot(terminal):
    normalized_positions = []
    for raw in list(getattr(terminal, "_latest_positions_snapshot", []) or []):
        normalized = terminal._normalize_position_entry(raw)
        if normalized is not None and float(normalized.get("amount", 0.0) or 0.0) > 0:
            normalized_positions.append(normalized)
    if normalized_positions:
        return normalized_positions
    return list(terminal._portfolio_positions_snapshot() or [])


def update_risk_heatmap(terminal):
    if terminal.risk_map is None:
        return

    positions = risk_heatmap_positions_snapshot(terminal)
    if not positions:
        signature = (id(terminal.risk_map), "empty")
        if signature == getattr(terminal, "_risk_heatmap_signature", None):
            return
        terminal.risk_map.setImage(np.zeros((1, 1), dtype=float), autoLevels=False, levels=(0.0, 1.0))
        terminal._set_risk_heatmap_status("No open positions, so there is no live portfolio risk to map.", "muted")
        terminal._risk_heatmap_signature = signature
        return

    risks = []

    for pos in positions:
        normalized = terminal._normalize_position_entry(pos)
        if normalized is None:
            continue
        risk = pos.get("risk") if isinstance(pos, dict) else getattr(pos, "risk", None)
        if risk is None:
            risk = normalized.get("margin_used")
        if risk in (None, "", 0, 0.0):
            risk = normalized.get("value")
        if risk is None:
            size = float(normalized.get("amount", 0.0) or 0.0)
            entry = float(normalized.get("entry_price", 0.0) or 0.0)
            risk = abs(size * entry)

        try:
            risk_value = abs(float(risk))
        except Exception:
            continue

        if risk_value > 0:
            risks.append(risk_value)

    if not risks:
        signature = (id(terminal.risk_map), "unusable")
        if signature == getattr(terminal, "_risk_heatmap_signature", None):
            return
        terminal.risk_map.setImage(np.zeros((1, 1), dtype=float), autoLevels=False, levels=(0.0, 1.0))
        terminal._set_risk_heatmap_status("Positions exist, but no usable risk values were found for them.", "warning")
        terminal._risk_heatmap_signature = signature
        return

    data = np.array(risks, dtype=float).reshape(1, len(risks))
    max_value = float(np.max(data))

    if max_value <= 0:
        normalized = np.zeros_like(data)
    else:
        normalized = data / max_value

    signature = (id(terminal.risk_map), tuple(float(value) for value in risks))
    if signature == getattr(terminal, "_risk_heatmap_signature", None):
        return
    terminal.risk_map.setImage(normalized, autoLevels=False, levels=(0.0, 1.0))
    terminal._set_risk_heatmap_status(
        f"Live risk snapshot across {len(risks)} position(s). Highest relative exposure: {max_value:,.2f}.",
        "positive",
    )
    terminal._risk_heatmap_signature = signature
