import time

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem, QPushButton


def _coerce_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _format_decimal(value, decimals=6, default="-"):
    numeric = _coerce_float(value)
    if numeric is None:
        return default
    return f"{numeric:.{int(decimals)}f}".rstrip("0").rstrip(".")


def _filter_query(terminal, attr_name):
    widget = getattr(terminal, attr_name, None)
    if widget is None:
        return ""
    try:
        return str(widget.text() or "").strip().lower()
    except Exception:
        return ""


def _row_matches_query(table, row, query):
    if not query:
        return True
    fragments = []
    for column in range(table.columnCount()):
        item = table.item(row, column)
        if item is None:
            continue
        text = str(item.text() or "").strip()
        if text:
            fragments.append(text.lower())
        tooltip = str(item.toolTip() or "").strip()
        if tooltip:
            fragments.append(tooltip.lower())
    haystack = " ".join(fragments)
    return query in haystack


def _table_signature(table, rows):
    return (id(table), tuple(rows))


def _record_get(record, *keys, default=None):
    if record is None:
        return default

    if isinstance(record, dict):
        for key in keys:
            if key is None:
                continue
            value = record.get(key)
            if value not in (None, ""):
                return value
        return default

    for key in keys:
        if key is None:
            continue
        attr_name = str(key).replace("-", "_")
        try:
            value = getattr(record, attr_name)
        except Exception:
            value = None
        if value not in (None, ""):
            return value

    return default


def _begin_table_update(table):
    if table is None:
        return None
    try:
        previous = bool(table.updatesEnabled())
    except Exception:
        previous = None
    try:
        table.setUpdatesEnabled(False)
    except Exception:
        pass
    return previous


def _finish_table_update(table, previous_updates_enabled, *, resize_threshold=60, resize_interval_seconds=20.0):
    if table is None:
        return
    try:
        if previous_updates_enabled is not None:
            table.setUpdatesEnabled(bool(previous_updates_enabled))
        else:
            table.setUpdatesEnabled(True)
    except Exception:
        pass

    header = getattr(table, "horizontalHeader", lambda: None)()
    if header is not None:
        try:
            header.setStretchLastSection(True)
        except Exception:
            pass

    row_count = int(getattr(table, "rowCount", lambda: 0)() or 0)
    now = time.monotonic()
    last_resize_at = float(getattr(table, "_sopotek_last_resize_at", 0.0) or 0.0)
    last_resize_rows = int(getattr(table, "_sopotek_last_resize_rows", -1) or -1)

    should_resize = (
        row_count <= resize_threshold
        or last_resize_at <= 0.0
        or (row_count != last_resize_rows and abs(row_count - last_resize_rows) >= resize_threshold)
        or (now - last_resize_at) >= float(resize_interval_seconds)
    )
    if should_resize:
        try:
            table.resizeColumnsToContents()
            table._sopotek_last_resize_at = now
            table._sopotek_last_resize_rows = row_count
        except Exception:
            pass


def _set_filter_summary(terminal, attr_name, *, visible, total, empty_label, noun):
    label = getattr(terminal, attr_name, None)
    if label is None:
        return
    if total <= 0:
        label.setText(empty_label)
        return
    if visible >= total:
        label.setText(f"Showing all {noun}")
        return
    label.setText(f"Showing {visible} of {total} {noun}")


def normalize_position_entry(terminal, raw):
    if raw is None:
        return None

    if isinstance(raw, dict):
        symbol = raw.get("symbol", "")
        side = raw.get("side", "")
        amount = raw.get("amount", raw.get("size", raw.get("quantity", raw.get("qty", 0))))
        entry = raw.get("entry_price", raw.get("avg_entry_price", raw.get("price", raw.get("avg_price", 0))))
        mark = raw.get("mark_price", raw.get("market_price"))
        pnl = raw.get("pnl", raw.get("unrealized_pnl", raw.get("unrealized_pl", raw.get("pl"))))
        realized_pnl = raw.get("realized_pnl", raw.get("realized_pl"))
        financing = raw.get("financing")
        margin_used = raw.get("margin_used", raw.get("marginUsed"))
        resettable_pl = raw.get("resettable_pl", raw.get("resettablePL"))
        units = raw.get("units")
        position_id = raw.get("position_id", raw.get("id", raw.get("trade_id")))
        position_key = raw.get("position_key", raw.get("key", position_id))
        position_side = raw.get("position_side", side)
    else:
        symbol = getattr(raw, "symbol", "")
        side = getattr(raw, "side", "")
        amount = getattr(raw, "amount", getattr(raw, "size", getattr(raw, "quantity", getattr(raw, "qty", 0))))
        entry = getattr(raw, "entry_price", getattr(raw, "avg_entry_price", getattr(raw, "avg_price", getattr(raw, "price", 0))))
        mark = getattr(raw, "mark_price", getattr(raw, "market_price", None))
        pnl = getattr(raw, "pnl", getattr(raw, "unrealized_pnl", getattr(raw, "unrealized_pl", None)))
        realized_pnl = getattr(raw, "realized_pnl", getattr(raw, "realized_pl", None))
        financing = getattr(raw, "financing", None)
        margin_used = getattr(raw, "margin_used", getattr(raw, "marginUsed", None))
        resettable_pl = getattr(raw, "resettable_pl", getattr(raw, "resettablePL", None))
        units = getattr(raw, "units", None)
        position_id = getattr(raw, "position_id", getattr(raw, "id", getattr(raw, "trade_id", None)))
        position_key = getattr(raw, "position_key", getattr(raw, "key", position_id))
        position_side = getattr(raw, "position_side", side)

    try:
        amount = float(amount or 0)
    except Exception:
        amount = 0.0
    try:
        entry = float(entry or 0)
    except Exception:
        entry = 0.0
    try:
        mark = float(mark) if mark not in (None, "") else None
    except Exception:
        mark = None
    try:
        pnl = float(pnl) if pnl not in (None, "") else None
    except Exception:
        pnl = None
    try:
        realized_pnl = float(realized_pnl) if realized_pnl not in (None, "") else None
    except Exception:
        realized_pnl = None
    try:
        financing = float(financing) if financing not in (None, "") else None
    except Exception:
        financing = None
    try:
        margin_used = float(margin_used) if margin_used not in (None, "") else None
    except Exception:
        margin_used = None
    try:
        resettable_pl = float(resettable_pl) if resettable_pl not in (None, "") else None
    except Exception:
        resettable_pl = None
    try:
        units = float(units) if units not in (None, "") else None
    except Exception:
        units = None

    normalized_symbol = str(symbol or "")
    if not normalized_symbol:
        return None

    normalized_side = str(side or "").lower()
    if not normalized_side:
        normalized_side = "long" if amount >= 0 else "short"
    abs_amount = abs(amount)

    if mark is None or mark <= 0:
        mark = terminal._lookup_symbol_mid_price(normalized_symbol)

    value = abs_amount * float(mark or entry or 0)
    if pnl is None and mark is not None and entry:
        direction = 1.0 if normalized_side != "short" else -1.0
        pnl = (float(mark) - entry) * abs_amount * direction

    return {
        "symbol": normalized_symbol,
        "side": normalized_side,
        "position_side": str(position_side or normalized_side).lower(),
        "position_id": str(position_id or "").strip(),
        "position_key": str(position_key or position_id or "").strip(),
        "amount": abs_amount,
        "units": float(units if units is not None else (abs_amount if normalized_side != "short" else -abs_amount)),
        "entry_price": entry,
        "mark_price": float(mark or 0),
        "value": value,
        "pnl": float(pnl or 0),
        "realized_pnl": float(realized_pnl or 0),
        "financing": float(financing or 0),
        "margin_used": float(margin_used or 0),
        "resettable_pl": float(resettable_pl or 0),
    }


def _positions_table_signature(table, normalized_positions):
    return (
        id(table),
        tuple(
            (
                pos["symbol"],
                pos["side"],
                pos.get("position_id") or pos.get("position_key") or "",
                f"{pos['amount']:.6f}",
                f"{pos['entry_price']:.6f}",
                f"{pos['mark_price']:.6f}",
                f"{pos['value']:.2f}",
                f"{pos['pnl']:.2f}",
            )
            for pos in normalized_positions
        ),
    )


def populate_positions_table(terminal, positions):
    table = getattr(terminal, "positions_table", None)
    if table is None:
        return
    close_all_btn = getattr(terminal, "positions_close_all_button", None)
    if table.columnCount() < 9:
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            ["Symbol", "Side", "Amount", "Entry", "Mark", "Value", "P/L", "View", "Close"]
        )

    normalized_positions = []
    for pos in positions or []:
        normalized = terminal._normalize_position_entry(pos)
        if normalized is not None and normalized["amount"] > 0:
            normalized_positions.append(normalized)

    normalized_positions.sort(
        key=lambda item: (
            item["symbol"],
            item["side"],
            item.get("position_id") or item.get("position_key") or "",
        )
    )
    signature = _positions_table_signature(table, normalized_positions)
    if close_all_btn is not None:
        close_all_btn.setEnabled(bool(getattr(terminal.controller, "broker", None)) and bool(normalized_positions))
    if signature == getattr(terminal, "_positions_table_signature", None):
        return

    terminal._positions_table_signature = signature
    previous_updates_enabled = _begin_table_update(table)
    table.setRowCount(len(normalized_positions))

    for row, pos in enumerate(normalized_positions):
        values = [
            pos["symbol"],
            pos["side"].upper(),
            f"{pos['amount']:.6f}".rstrip("0").rstrip("."),
            f"{pos['entry_price']:.6f}".rstrip("0").rstrip("."),
            f"{pos['mark_price']:.6f}".rstrip("0").rstrip("."),
            f"{pos['value']:.2f}",
            f"{pos['pnl']:.2f}",
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 6:
                item.setForeground(QColor("#32d296" if pos["pnl"] >= 0 else "#ef5350"))
            table.setItem(row, col, item)
        
        # Add View button
        view_btn = QPushButton("View Position")
        view_btn.setStyleSheet(terminal._action_button_style())
        view_btn.setToolTip("View position details.")
        view_btn.clicked.connect(lambda _checked=False, payload=dict(pos): terminal._show_position_details(payload))
        table.setCellWidget(row, 7, view_btn)
        
        # Add Close button
        table.setCellWidget(row, 8, terminal._build_position_close_button(pos, compact=True))

    apply_positions_filter(terminal)
    _finish_table_update(table, previous_updates_enabled)


def normalize_open_order_entry(terminal, order):
    if order is None:
        return None

    symbol = str(_record_get(order, "symbol", "instrument", "market") or "").strip()
    if not symbol:
        return None

    side = str(_record_get(order, "side") or "").strip().lower()
    order_type = str(_record_get(order, "type", "order_type") or "").strip().lower()
    status = str(_record_get(order, "status", "state") or "").strip().lower()

    amount = abs(float(_coerce_float(_record_get(order, "amount", "qty", "quantity", "size"), default=0.0) or 0.0))
    filled = abs(float(_coerce_float(_record_get(order, "filled", "filled_qty", "filled_quantity", "executedQty"), default=0.0) or 0.0))
    remaining = max(amount - filled, 0.0)

    price = _coerce_float(_record_get(order, "price", "average", "avg_price"), default=None)
    if price is not None and price <= 0:
        price = None

    mark = terminal._lookup_symbol_mid_price(symbol)
    if mark is not None and mark <= 0:
        mark = None

    pnl = _coerce_float(_record_get(order, "pnl", "unrealized_pnl", "unrealizedPnl"), default=None)

    if pnl is None and price is not None and mark is not None and remaining > 0:
        direction = -1.0 if side == "sell" else 1.0
        pnl = (float(mark) - float(price)) * remaining * direction

    return {
        "symbol": symbol,
        "side": side or "-",
        "type": order_type or "-",
        "price": price,
        "mark": mark,
        "amount": amount,
        "filled": filled,
        "remaining": remaining,
        "status": status or "-",
        "pnl": pnl,
        "order_id": str(_record_get(order, "id", "order_id", "clientOrderId", "client_order_id") or ""),
    }


def _open_orders_table_signature(table, normalized_orders):
    return (
        id(table),
        tuple(
            (
                order["symbol"],
                order["side"],
                order["type"],
                "-" if order["price"] is None else f"{order['price']:.6f}",
                "-" if order["mark"] is None else f"{order['mark']:.6f}",
                f"{order['amount']:.6f}",
                f"{order['filled']:.6f}",
                f"{order['remaining']:.6f}",
                order["status"],
                "-" if order["pnl"] is None else f"{float(order['pnl']):.2f}",
                order["order_id"],
            )
            for order in normalized_orders
        ),
    )


def populate_open_orders_table(terminal, orders):
    table = getattr(terminal, "open_orders_table", None)
    if table is None:
        return
    if table.columnCount() < 11:
        table.setColumnCount(11)

    normalized_orders = []
    for order in orders or []:
        normalized = terminal._normalize_open_order_entry(order)
        if normalized is not None:
            normalized_orders.append(normalized)

    normalized_orders.sort(key=lambda item: (item["symbol"], item["status"], item["order_id"]))
    signature = _open_orders_table_signature(table, normalized_orders)
    if signature == getattr(terminal, "_open_orders_table_signature", None):
        return

    terminal._open_orders_table_signature = signature
    previous_updates_enabled = _begin_table_update(table)
    table.setRowCount(len(normalized_orders))

    for row, order in enumerate(normalized_orders):
        price_text = "-" if order["price"] is None else f"{order['price']:.6f}".rstrip("0").rstrip(".")
        mark_text = "-" if order["mark"] is None else f"{order['mark']:.6f}".rstrip("0").rstrip(".")
        pnl_value = order["pnl"]
        pnl_text = "-" if pnl_value is None else f"{float(pnl_value):.2f}"

        values = [
            order["symbol"],
            order["side"].upper(),
            order["type"].upper(),
            price_text,
            mark_text,
            f"{order['amount']:.6f}".rstrip("0").rstrip("."),
            f"{order['filled']:.6f}".rstrip("0").rstrip("."),
            f"{order['remaining']:.6f}".rstrip("0").rstrip("."),
            order["status"].replace("_", " ").upper(),
            pnl_text,
            order["order_id"],
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 8:
                status_value = order["status"]
                if "partial" in status_value:
                    item.setForeground(QColor("#f0a35e"))
                elif status_value in {"open", "pending", "submitted", "accepted", "new"}:
                    item.setForeground(QColor("#65a3ff"))
            elif col == 9 and pnl_value is not None:
                    item.setForeground(QColor("#32d296" if float(pnl_value) >= 0 else "#ef5350"))
            table.setItem(row, col, item)

    apply_open_orders_filter(terminal)
    _finish_table_update(table, previous_updates_enabled)


def _asset_balance_rows(balances):
    if not isinstance(balances, dict):
        return []

    free = dict(balances.get("free") or {}) if isinstance(balances.get("free"), dict) else {}
    used = dict(balances.get("used") or {}) if isinstance(balances.get("used"), dict) else {}
    total = dict(balances.get("total") or {}) if isinstance(balances.get("total"), dict) else {}
    asset_codes = {str(code).strip().upper() for code in [*free.keys(), *used.keys(), *total.keys()] if str(code).strip()}

    rows = []
    for code in sorted(asset_codes):
        row = {
            "asset": code,
            "free": float(free.get(code, 0.0) or 0.0),
            "used": float(used.get(code, 0.0) or 0.0),
            "total": float(total.get(code, 0.0) or 0.0),
        }
        if any(abs(float(row[key] or 0.0)) > 1e-12 for key in ("free", "used", "total")):
            rows.append(row)

    if rows:
        rows.sort(key=lambda item: abs(float(item.get("total", 0.0) or 0.0)), reverse=True)
        return rows

    raw = dict(balances.get("raw") or {}) if isinstance(balances.get("raw"), dict) else {}
    currency = str(
        raw.get("currency")
        or balances.get("currency")
        or raw.get("accountCurrency")
        or raw.get("homeCurrency")
        or "ACCOUNT"
    ).strip().upper() or "ACCOUNT"
    free_value = _coerce_float(
        balances.get("cash")
        if not isinstance(balances.get("cash"), dict)
        else None,
        default=_coerce_float(raw.get("cash"), default=0.0),
    )
    used_value = _coerce_float(
        balances.get("margin_used")
        if not isinstance(balances.get("margin_used"), dict)
        else None,
        default=_coerce_float(raw.get("marginUsed"), default=0.0),
    )
    total_value = _coerce_float(
        balances.get("equity")
        if not isinstance(balances.get("equity"), dict)
        else None,
        default=_coerce_float(raw.get("NAV"), default=_coerce_float(raw.get("equity"), default=None)),
    )
    if free_value is None and used_value is None and total_value is None:
        return []
    return [
        {
            "asset": currency,
            "free": float(free_value or 0.0),
            "used": float(used_value or 0.0),
            "total": float(total_value if total_value is not None else (float(free_value or 0.0) + float(used_value or 0.0))),
        }
    ]


def _assets_table_signature(table, rows):
    return _table_signature(
        table,
        tuple(
            (
                row["asset"],
                f"{float(row['free']):.8f}",
                f"{float(row['used']):.8f}",
                f"{float(row['total']):.8f}",
            )
            for row in rows
        ),
    )


def populate_assets_table(terminal, balances):
    table = getattr(terminal, "assets_table", None)
    if table is None:
        return
    if table.columnCount() < 4:
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Asset", "Free", "Used", "Total"])

    rows = _asset_balance_rows(balances)
    signature = _assets_table_signature(table, rows)
    if signature == getattr(terminal, "_assets_table_signature", None):
        return

    terminal._assets_table_signature = signature
    previous_updates_enabled = _begin_table_update(table)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        values = [
            row["asset"],
            _format_decimal(row["free"], decimals=8, default="0"),
            _format_decimal(row["used"], decimals=8, default="0"),
            _format_decimal(row["total"], decimals=8, default="0"),
        ]
        for col_index, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col_index == 3:
                total_value = float(row.get("total", 0.0) or 0.0)
                item.setForeground(QColor("#32d296" if total_value >= 0 else "#ef5350"))
            table.setItem(row_index, col_index, item)

    apply_assets_filter(terminal)
    _finish_table_update(table, previous_updates_enabled)


def normalize_order_history_entry(order):
    if order is None:
        return None

    symbol = str(_record_get(order, "symbol", "instrument", "market") or "").strip()
    order_id = str(_record_get(order, "id", "order_id", "clientOrderId", "client_order_id") or "").strip()
    if not symbol and not order_id:
        return None

    amount = abs(float(_coerce_float(_record_get(order, "amount", "qty", "quantity", "size"), default=0.0) or 0.0))
    filled = abs(float(_coerce_float(_record_get(order, "filled", "filled_qty", "filled_quantity", "executedQty"), default=0.0) or 0.0))
    remaining = _record_get(order, "remaining")
    remaining_value = _coerce_float(remaining, default=max(0.0, amount - filled))
    price = _coerce_float(_record_get(order, "price", "average", "avg_price"), default=None)

    return {
        "timestamp": str(_record_get(order, "timestamp", "datetime", "time", "created_at") or "").strip(),
        "symbol": symbol,
        "side": str(_record_get(order, "side") or "").strip().lower(),
        "type": str(_record_get(order, "type", "order_type") or "").strip().lower(),
        "price": price,
        "filled": float(filled),
        "remaining": float(remaining_value or 0.0),
        "status": str(_record_get(order, "status", "state") or "").strip().lower(),
        "order_id": order_id,
    }


def _order_history_table_signature(table, rows):
    return _table_signature(
        table,
        tuple(
            (
                row["timestamp"],
                row["symbol"],
                row["side"],
                row["type"],
                "-" if row["price"] is None else f"{float(row['price']):.8f}",
                f"{float(row['filled']):.8f}",
                f"{float(row['remaining']):.8f}",
                row["status"],
                row["order_id"],
            )
            for row in rows
        ),
    )


def populate_order_history_table(terminal, orders):
    table = getattr(terminal, "order_history_table", None)
    if table is None:
        return
    if table.columnCount() < 9:
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(
            ["Timestamp", "Symbol", "Side", "Type", "Price", "Filled", "Remaining", "Status", "Order ID"]
        )

    rows = []
    for order in orders or []:
        normalized = normalize_order_history_entry(order)
        if normalized is not None:
            rows.append(normalized)

    rows.sort(key=lambda item: (item["timestamp"], item["symbol"], item["order_id"]), reverse=True)
    signature = _order_history_table_signature(table, rows)
    if signature == getattr(terminal, "_order_history_table_signature", None):
        return

    terminal._order_history_table_signature = signature
    previous_updates_enabled = _begin_table_update(table)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        values = [
            row["timestamp"],
            row["symbol"],
            row["side"].upper(),
            row["type"].upper(),
            _format_decimal(row["price"], decimals=8),
            _format_decimal(row["filled"], decimals=8, default="0"),
            _format_decimal(row["remaining"], decimals=8, default="0"),
            row["status"].replace("_", " ").upper(),
            row["order_id"],
        ]
        for col_index, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col_index == 7:
                status_value = row["status"]
                if status_value in {"filled", "closed"}:
                    item.setForeground(QColor("#32d296"))
                elif status_value in {"canceled", "cancelled", "rejected", "failed", "expired"}:
                    item.setForeground(QColor("#ef5350"))
                elif status_value in {"open", "pending", "submitted", "accepted", "new"}:
                    item.setForeground(QColor("#65a3ff"))
            table.setItem(row_index, col_index, item)

    apply_order_history_filter(terminal)
    _finish_table_update(table, previous_updates_enabled)


def normalize_trade_log_entry(terminal, trade):
    if trade is None:
        return None

    normalized = {
        "trade_db_id": _record_get(trade, "trade_db_id", "id", default=""),
        "timestamp": _record_get(trade, "timestamp", "datetime", "time", "created_at", default=""),
        "symbol": _record_get(trade, "symbol", "instrument", "market", default=""),
        "source": terminal._format_trade_source_label(_record_get(trade, "source", default="bot")),
        "side": _record_get(trade, "side", default=""),
        "price": _record_get(trade, "price", "average", default=""),
        "size": _record_get(trade, "size", "amount", "qty", "quantity", default=""),
        "order_type": _record_get(trade, "order_type", "type", default=""),
        "status": _record_get(trade, "status", "state", default=""),
        "order_id": _record_get(trade, "order_id", "order", "id", default=""),
        "pnl": _record_get(trade, "pnl", "realized_pnl", "realizedPL", "pl", default=""),
        "stop_loss": _record_get(trade, "stop_loss", "sl", default=""),
        "take_profit": _record_get(trade, "take_profit", "tp", default=""),
        "reason": _record_get(trade, "reason", "message", default=""),
        "strategy_name": _record_get(trade, "strategy_name", default=""),
        "confidence": _record_get(trade, "confidence", default=""),
        "expected_price": _record_get(trade, "expected_price", default=""),
        "spread_bps": _record_get(trade, "spread_bps", default=""),
        "slippage_bps": _record_get(trade, "slippage_bps", default=""),
        "fee": _record_get(trade, "fee", "commission", "cost", default=""),
        "setup": _record_get(trade, "setup", default=""),
        "outcome": _record_get(trade, "outcome", default=""),
        "lessons": _record_get(trade, "lessons", default=""),
        "blocked_by_guard": bool(_record_get(trade, "blocked_by_guard", default=False)),
    }
    return normalized


def format_trade_log_value(_terminal, value):
    if value is None:
        return ""
    return str(value)


def format_trade_source_label(_terminal, value):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    mapping = {
        "chatgpt": "Sopotek Pilot",
        "manual": "Manual",
        "bot": "Bot",
        "chart_double_click": "Chart Double Click",
        "chart_context_menu": "Chart Context Menu",
    }
    return mapping.get(normalized, str(value).replace("_", " ").title())


def trade_log_row_for_entry(terminal, entry):
    order_id = str(entry.get("order_id") or "").strip()
    if not order_id:
        return None

    for row in range(terminal.trade_log.rowCount()):
        item = terminal.trade_log.item(row, 8)
        if item is not None and item.text().strip() == order_id:
            return row
    return None


def update_trade_log(terminal, trade):
    entry = terminal._normalize_trade_log_entry(trade)
    if entry is None:
        return
    if terminal.trade_log.columnCount() < 10:
        terminal.trade_log.setColumnCount(10)

    row = terminal._trade_log_row_for_entry(entry)
    if row is None:
        row = terminal.trade_log.rowCount()

    if row == terminal.trade_log.rowCount() and row >= terminal.MAX_LOG_ROWS:
        terminal.trade_log.removeRow(0)
        row = terminal.trade_log.rowCount()

    if row == terminal.trade_log.rowCount():
        terminal.trade_log.insertRow(row)

    column_values = [
        entry["timestamp"],
        entry["symbol"],
        entry["source"],
        entry["side"],
        entry["price"],
        entry["size"],
        entry["order_type"],
        entry["status"],
        entry["order_id"],
        entry["pnl"],
    ]
    for column, value in enumerate(column_values):
        terminal.trade_log.setItem(row, column, QTableWidgetItem(terminal._format_trade_log_value(value)))

    tooltip_parts = []
    if entry.get("stop_loss") not in ("", None):
        tooltip_parts.append(f"SL: {entry.get('stop_loss')}")
    if entry.get("take_profit") not in ("", None):
        tooltip_parts.append(f"TP: {entry.get('take_profit')}")
    if entry.get("reason") not in ("", None):
        prefix = "Guard" if entry.get("blocked_by_guard") else "Reason"
        tooltip_parts.append(f"{prefix}: {entry.get('reason')}")
    if entry.get("strategy_name") not in ("", None):
        tooltip_parts.append(f"Strategy: {entry.get('strategy_name')}")
    if entry.get("confidence") not in ("", None, 0):
        tooltip_parts.append(f"Confidence: {entry.get('confidence')}")
    if entry.get("spread_bps") not in ("", None):
        tooltip_parts.append(f"Spread: {entry.get('spread_bps')} bps")
    if entry.get("slippage_bps") not in ("", None):
        tooltip_parts.append(f"Slippage: {entry.get('slippage_bps')} bps")
    if entry.get("fee") not in ("", None):
        tooltip_parts.append(f"Fee: {entry.get('fee')}")
    if tooltip_parts:
        tooltip = " | ".join(tooltip_parts)
        for column in range(terminal.trade_log.columnCount()):
            item = terminal.trade_log.item(row, column)
            if item is not None:
                item.setToolTip(tooltip)

    apply_trade_log_filter(terminal)
    terminal.trade_log.horizontalHeader().setStretchLastSection(True)
    terminal._refresh_performance_views()


def _trade_history_table_signature(table, rows):
    return _table_signature(
        table,
        tuple(
            (
                str(row.get("timestamp") or ""),
                str(row.get("symbol") or ""),
                str(row.get("source") or ""),
                str(row.get("side") or ""),
                str(row.get("price") or ""),
                str(row.get("size") or row.get("amount") or ""),
                str(row.get("order_type") or row.get("type") or ""),
                str(row.get("status") or ""),
                str(row.get("order_id") or row.get("id") or ""),
                str(row.get("pnl") or ""),
            )
            for row in rows
        ),
    )


def populate_trade_history_table(terminal, trades):
    table = getattr(terminal, "trade_history_table", None)
    if table is None:
        return
    if table.columnCount() < 10:
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["Timestamp", "Symbol", "Source", "Side", "Price", "Size", "Order Type", "Status", "Order ID", "PnL"]
        )

    rows = []
    for trade in trades or []:
        normalized = terminal._normalize_trade_log_entry(trade)
        if normalized is not None:
            rows.append(normalized)

    signature = _trade_history_table_signature(table, rows)
    if signature == getattr(terminal, "_trade_history_table_signature", None):
        return

    terminal._trade_history_table_signature = signature
    previous_updates_enabled = _begin_table_update(table)
    table.setRowCount(len(rows))
    for row_index, entry in enumerate(rows):
        values = [
            entry["timestamp"],
            entry["symbol"],
            entry["source"],
            entry["side"],
            entry["price"],
            entry["size"],
            entry["order_type"],
            entry["status"],
            entry["order_id"],
            entry["pnl"],
        ]
        for col_index, value in enumerate(values):
            item = QTableWidgetItem(terminal._format_trade_log_value(value))
            if col_index == 9:
                pnl_value = _coerce_float(entry.get("pnl"))
                if pnl_value is not None:
                    item.setForeground(QColor("#32d296" if pnl_value >= 0 else "#ef5350"))
            table.setItem(row_index, col_index, item)

        tooltip_parts = []
        if entry.get("reason") not in ("", None):
            prefix = "Guard" if entry.get("blocked_by_guard") else "Reason"
            tooltip_parts.append(f"{prefix}: {entry.get('reason')}")
        if entry.get("strategy_name") not in ("", None):
            tooltip_parts.append(f"Strategy: {entry.get('strategy_name')}")
        if entry.get("confidence") not in ("", None, 0):
            tooltip_parts.append(f"Confidence: {entry.get('confidence')}")
        if tooltip_parts:
            tooltip = " | ".join(tooltip_parts)
            for col_index in range(table.columnCount()):
                item = table.item(row_index, col_index)
                if item is not None:
                    item.setToolTip(tooltip)

    apply_trade_history_filter(terminal)
    _finish_table_update(table, previous_updates_enabled)


def apply_positions_filter(terminal):
    table = getattr(terminal, "positions_table", None)
    if table is None:
        return
    query = _filter_query(terminal, "positions_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "positions_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all positions",
        noun="positions",
    )


def apply_open_orders_filter(terminal):
    table = getattr(terminal, "open_orders_table", None)
    if table is None:
        return
    query = _filter_query(terminal, "open_orders_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "open_orders_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all open orders",
        noun="open orders",
    )


def apply_assets_filter(terminal):
    table = getattr(terminal, "assets_table", None)
    if table is None:
        return
    query = _filter_query(terminal, "assets_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "assets_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all assets",
        noun="assets",
    )


def apply_order_history_filter(terminal):
    table = getattr(terminal, "order_history_table", None)
    if table is None:
        return
    query = _filter_query(terminal, "order_history_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "order_history_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all historical orders",
        noun="historical orders",
    )


def apply_trade_log_filter(terminal):
    table = getattr(terminal, "trade_log", None)
    if table is None:
        return
    query = _filter_query(terminal, "trade_log_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "trade_log_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all trade log rows",
        noun="trade log rows",
    )


def apply_trade_history_filter(terminal):
    table = getattr(terminal, "trade_history_table", None)
    if table is None:
        return
    query = _filter_query(terminal, "trade_history_filter_input")
    visible_rows = 0
    total_rows = table.rowCount()
    for row in range(total_rows):
        matches = _row_matches_query(table, row, query)
        table.setRowHidden(row, not matches)
        if matches:
            visible_rows += 1
    _set_filter_summary(
        terminal,
        "trade_history_filter_summary",
        visible=visible_rows,
        total=total_rows,
        empty_label="Showing all trade history rows",
        noun="trade history rows",
    )
