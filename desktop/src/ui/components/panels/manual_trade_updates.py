import asyncio

import numpy as np
from PySide6.QtWidgets import QMessageBox


def manual_trade_default_payload(terminal, prefill=None):
    payload = dict(prefill or {})
    symbol_options = list(getattr(terminal.controller, "symbols", []) or [])
    default_symbol = (
        str(payload.get("symbol") or terminal._current_chart_symbol() or getattr(terminal, "symbol", "") or "").strip()
    )
    if default_symbol and default_symbol not in symbol_options:
        symbol_options.insert(0, default_symbol)
    default_order_type = str(payload.get("order_type") or "market").strip().lower()
    if default_order_type not in {"market", "limit", "stop_limit"}:
        default_order_type = "market"
    quantity_context = terminal._manual_trade_quantity_context(default_symbol)
    quantity_mode = terminal._normalize_manual_trade_quantity_mode(
        payload.get("quantity_mode") or quantity_context.get("default_mode")
    )
    default_amount = 0.01 if quantity_mode == "lots" and "amount" not in payload else 1.0
    return {
        "symbol_options": symbol_options,
        "symbol": default_symbol,
        "side": str(payload.get("side") or "buy").strip().lower() or "buy",
        "order_type": default_order_type,
        "amount": terminal._safe_float(payload.get("amount"), default_amount) or default_amount,
        "quantity_mode": quantity_mode,
        "price": terminal._safe_float(payload.get("price")),
        "stop_price": terminal._safe_float(payload.get("stop_price")),
        "stop_loss": terminal._safe_float(payload.get("stop_loss")),
        "take_profit": terminal._safe_float(payload.get("take_profit")),
        "source": str(payload.get("source") or "manual").strip().lower() or "manual",
        "timeframe": str(payload.get("timeframe") or terminal.current_timeframe or "").strip(),
    }


def default_entry_price_for_symbol(terminal, symbol, side="buy"):
    chart = terminal._chart_for_symbol(symbol)
    if chart is not None:
        last_df = getattr(chart, "_last_df", None)
        if last_df is not None and hasattr(last_df, "empty") and not last_df.empty:
            try:
                normalized_side = str(side or "buy").strip().lower()
                if normalized_side == "sell" and "bid" in last_df.columns:
                    return float(last_df["bid"].iloc[-1])
                if normalized_side == "buy" and "ask" in last_df.columns:
                    return float(last_df["ask"].iloc[-1])
                return float(last_df["close"].iloc[-1])
            except Exception:
                pass
        last_bid = terminal._safe_float(getattr(chart, "_last_bid", None))
        last_ask = terminal._safe_float(getattr(chart, "_last_ask", None))
        normalized_side = str(side or "buy").strip().lower()
        if normalized_side == "buy" and last_ask is not None:
            return last_ask
        if normalized_side == "sell" and last_bid is not None:
            return last_bid
        if last_bid is not None and last_ask is not None:
            return (last_bid + last_ask) / 2.0
    return None


def suggest_manual_trade_levels(terminal, symbol, side="buy", entry_price=None):
    entry = terminal._safe_float(entry_price)
    if entry is None or entry <= 0:
        entry = terminal._default_entry_price_for_symbol(symbol, side=side)
    if entry is None or entry <= 0:
        return (None, None, None)

    chart = terminal._chart_for_symbol(symbol)
    risk_distance = None
    if chart is not None:
        last_df = getattr(chart, "_last_df", None)
        if last_df is not None and hasattr(last_df, "empty") and not last_df.empty:
            try:
                lookback = min(len(last_df), 14)
                high = last_df["high"].astype(float).tail(lookback)
                low = last_df["low"].astype(float).tail(lookback)
                close = last_df["close"].astype(float).tail(lookback)
                prev_close = close.shift(1).fillna(close)
                tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
                atr_value = float(tr.mean())
                if np.isfinite(atr_value) and atr_value > 0:
                    risk_distance = atr_value * 1.5
            except Exception:
                risk_distance = None

    if risk_distance is None or risk_distance <= 0:
        risk_distance = max(abs(entry) * 0.002, 1e-6)

    reward_distance = risk_distance * 2.0
    normalized_side = str(side or "buy").strip().lower() or "buy"
    if normalized_side == "sell":
        stop_loss = entry + risk_distance
        take_profit = entry - reward_distance
    else:
        stop_loss = entry - risk_distance
        take_profit = entry + reward_distance

    entry = terminal._normalize_manual_trade_price(symbol, entry)
    stop_loss = terminal._normalize_manual_trade_price(symbol, stop_loss)
    take_profit = terminal._normalize_manual_trade_price(symbol, take_profit)
    return (entry, stop_loss, take_profit)


def manual_trade_format_context(terminal, symbol):
    broker = getattr(terminal.controller, "broker", None)
    context = {
        "amount_decimals": 8,
        "price_decimals": 6,
        "min_amount": 0.0,
        "amount_formatter": lambda value: value,
        "price_formatter": lambda value: value,
    }
    if broker is None or not symbol:
        return context

    exchange_name = str(getattr(broker, "exchange_name", "") or "").strip().lower()

    if exchange_name == "oanda":
        try:
            normalized_symbol = broker._normalize_symbol(symbol) if hasattr(broker, "_normalize_symbol") else symbol
            details = getattr(broker, "_instrument_details", {}) or {}
            meta = details.get(normalized_symbol, {}) if isinstance(details, dict) else {}
            amount_decimals = max(0, int(meta.get("tradeUnitsPrecision", 0) or 0))
            price_decimals = max(0, int(meta.get("displayPrecision", 5) or 5))
            min_amount = float(meta.get("minimumTradeSize", 1) or 1)
            context.update(
                {
                    "amount_decimals": amount_decimals,
                    "price_decimals": price_decimals,
                    "min_amount": min_amount,
                    "amount_formatter": lambda value, precision=amount_decimals: float(
                        broker._format_units(value, precision)
                    ),
                    "price_formatter": lambda value, precision=price_decimals: float(
                        broker._format_price(value, precision)
                    ),
                }
            )
            return context
        except Exception:
            return context

    exchange = getattr(broker, "exchange", None)
    market = None
    if exchange is not None:
        try:
            markets = getattr(exchange, "markets", None)
            if isinstance(markets, dict):
                market = markets.get(symbol)
        except Exception:
            market = None

    precision = market.get("precision", {}) if isinstance(market, dict) else {}
    limits = market.get("limits", {}) if isinstance(market, dict) else {}
    amount_precision = precision.get("amount")
    price_precision = precision.get("price")
    min_amount = (((limits.get("amount") or {}).get("min")) if isinstance(limits, dict) else None)

    try:
        if amount_precision is not None:
            context["amount_decimals"] = max(0, int(amount_precision))
    except Exception:
        pass
    try:
        if price_precision is not None:
            context["price_decimals"] = max(0, int(price_precision))
    except Exception:
        pass
    try:
        if min_amount not in (None, ""):
            context["min_amount"] = float(min_amount)
    except Exception:
        pass

    amount_converter = getattr(exchange, "amount_to_precision", None) if exchange is not None else None
    price_converter = getattr(exchange, "price_to_precision", None) if exchange is not None else None
    if callable(amount_converter):
        context["amount_formatter"] = lambda value, converter=amount_converter, target=symbol: float(
            converter(target, value)
        )
    if callable(price_converter):
        context["price_formatter"] = lambda value, converter=price_converter, target=symbol: float(
            converter(target, value)
        )
    return context


def normalize_manual_trade_quantity_mode(_terminal, value):
    mode = str(value or "units").strip().lower()
    if mode.endswith("s"):
        mode = mode[:-1]
    return "lots" if mode == "lot" else "units"


def manual_trade_quantity_context(terminal, symbol):
    controller = getattr(terminal, "controller", None)
    if controller is not None and hasattr(controller, "trade_quantity_context"):
        try:
            context = controller.trade_quantity_context(symbol)
            if isinstance(context, dict):
                return context
        except Exception:
            pass
    return {
        "symbol": str(symbol or "").strip().upper(),
        "supports_lots": False,
        "default_mode": "units",
        "lot_units": 100000.0,
    }


def normalize_manual_trade_amount(terminal, symbol, amount, quantity_mode="units"):
    try:
        numeric = float(amount)
    except Exception:
        return None
    mode = terminal._normalize_manual_trade_quantity_mode(quantity_mode)
    context = terminal._manual_trade_format_context(symbol)
    quantity_context = terminal._manual_trade_quantity_context(symbol)
    if mode == "lots":
        numeric *= float(quantity_context.get("lot_units", 100000.0) or 100000.0)
    formatter = context.get("amount_formatter")
    try:
        return float(formatter(numeric)) if callable(formatter) else numeric
    except Exception:
        return numeric


def validate_manual_trade_amount(terminal, symbol, amount, quantity_mode="units"):
    try:
        numeric = float(amount)
    except Exception:
        return None, "Amount must be a valid number."
    mode = terminal._normalize_manual_trade_quantity_mode(quantity_mode)
    quantity_context = terminal._manual_trade_quantity_context(symbol)
    if mode == "lots" and not quantity_context.get("supports_lots"):
        return None, f"Lot sizing is not available for {symbol}. Switch the ticket to units."

    context = terminal._manual_trade_format_context(symbol)
    min_amount = float(context.get("min_amount") or 0.0)
    normalized = terminal._normalize_manual_trade_amount(symbol, numeric, quantity_mode=mode)
    if normalized is None or normalized <= 0:
        return None, "Amount must be greater than zero."
    if min_amount > 0:
        if mode == "lots":
            min_lots = min_amount / float(quantity_context.get("lot_units", 100000.0) or 100000.0)
            if abs(numeric) < min_lots:
                return None, f"Amount is below the broker minimum size of {min_lots:g} lots for {symbol}."
        elif abs(numeric) < min_amount:
            return None, f"Amount is below the broker minimum size of {min_amount} for {symbol}."
    if abs(normalized) <= 0:
        return None, "Amount rounds to zero at the broker precision for this symbol."
    return normalized, None


def normalize_manual_trade_price(terminal, symbol, value):
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    formatter = terminal._manual_trade_format_context(symbol).get("price_formatter")
    try:
        return float(formatter(numeric)) if callable(formatter) else numeric
    except Exception:
        return numeric


def submit_manual_trade_side(terminal, window, side):
    if window is None:
        return
    side_picker = getattr(window, "_manual_trade_side_picker", None)
    if side_picker is not None:
        side_picker.blockSignals(True)
        side_picker.setCurrentText(str(side or "buy"))
        side_picker.blockSignals(False)
        terminal._refresh_manual_trade_ticket(window)
    terminal._submit_manual_trade_from_ticket(window)


def refresh_manual_trade_ticket(terminal, window):
    symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
    side_picker = getattr(window, "_manual_trade_side_picker", None)
    type_picker = getattr(window, "_manual_trade_type_picker", None)
    quantity_picker = getattr(window, "_manual_trade_quantity_picker", None)
    amount_input = getattr(window, "_manual_trade_amount_input", None)
    price_input = getattr(window, "_manual_trade_price_input", None)
    stop_price_input = getattr(window, "_manual_trade_stop_price_input", None)
    stop_loss_input = getattr(window, "_manual_trade_stop_loss_input", None)
    take_profit_input = getattr(window, "_manual_trade_take_profit_input", None)
    status = getattr(window, "_manual_trade_status", None)
    price_label = getattr(window, "_manual_trade_price_label", None)
    stop_price_label = getattr(window, "_manual_trade_stop_price_label", None)
    submit_btn = getattr(window, "_manual_trade_submit_btn", None)
    buy_btn = getattr(window, "_manual_trade_buy_limit_btn", None)
    sell_btn = getattr(window, "_manual_trade_sell_limit_btn", None)
    if symbol_picker is None or side_picker is None or type_picker is None or amount_input is None:
        return

    symbol_text = str(symbol_picker.currentText() or "").strip()
    format_context = terminal._manual_trade_format_context(symbol_text)
    quantity_context = terminal._manual_trade_quantity_context(symbol_text)
    last_symbol = str(getattr(window, "_manual_trade_last_quantity_symbol", "") or "")
    if quantity_picker is not None and symbol_text != last_symbol:
        quantity_picker.blockSignals(True)
        quantity_picker.setCurrentText(str(quantity_context.get("default_mode", "units")).title())
        quantity_picker.blockSignals(False)
        window._manual_trade_last_quantity_symbol = symbol_text
    quantity_mode = terminal._normalize_manual_trade_quantity_mode(
        str(quantity_picker.currentText() or quantity_context.get("default_mode", "units"))
        if quantity_picker is not None
        else quantity_context.get("default_mode", "units")
    )
    if quantity_picker is not None and quantity_mode == "lots" and not quantity_context.get("supports_lots"):
        quantity_picker.blockSignals(True)
        quantity_picker.setCurrentText("Units")
        quantity_picker.blockSignals(False)
        quantity_mode = "units"
    broker_amount_decimals = max(0, int(format_context.get("amount_decimals", 8) or 8))
    lot_units = float(quantity_context.get("lot_units", 100000.0) or 100000.0)
    amount_decimals = max(5, broker_amount_decimals) if quantity_mode == "lots" else max(8, broker_amount_decimals)
    min_amount = max(0.0, float(format_context.get("min_amount", 0.0) or 0.0))
    price_decimals = max(0, int(format_context.get("price_decimals", 6) or 6))
    amount_input.setDecimals(amount_decimals)
    amount_input.setMinimum(0.0)
    amount_input.setSingleStep(0.01 if quantity_mode == "lots" else (10 ** (-amount_decimals) if amount_decimals > 0 else 1.0))

    order_type = str(type_picker.currentText() or "market").strip().lower()
    order_type_label = order_type.replace("_", " ").title() or "Market"
    has_symbol = bool(symbol_text)
    has_amount = amount_input.value() > 0
    price_required = order_type in {"limit", "stop_limit"}
    stop_price_required = order_type == "stop_limit"
    has_price = bool(str(price_input.text() or "").strip()) if price_input is not None else True
    has_stop_price = bool(str(stop_price_input.text() or "").strip()) if stop_price_input is not None else True

    if price_input is not None:
        price_input.setEnabled(price_required)
        price_input.setPlaceholderText(f"{'Limit' if stop_price_required else 'Price'} ({price_decimals} dp)")
        price_input.setToolTip(f"Broker price precision: {price_decimals} decimals")
    if price_label is not None:
        price_label.setEnabled(price_required)
        price_label.setText("Limit Price" if stop_price_required else "Entry Price")
    if stop_price_input is not None:
        stop_price_input.setEnabled(stop_price_required)
        stop_price_input.setPlaceholderText(f"Stop ({price_decimals} dp)")
        stop_price_input.setToolTip(f"Broker price precision: {price_decimals} decimals")
    if stop_price_label is not None:
        stop_price_label.setEnabled(stop_price_required)
    if stop_loss_input is not None:
        stop_loss_input.setPlaceholderText(f"SL ({price_decimals} dp)")
        stop_loss_input.setToolTip(f"Broker price precision: {price_decimals} decimals")
    if take_profit_input is not None:
        take_profit_input.setPlaceholderText(f"TP ({price_decimals} dp)")
        take_profit_input.setToolTip(f"Broker price precision: {price_decimals} decimals")
    quantity_tooltip = "Submit size in broker units."
    if quantity_mode == "lots":
        min_lots = (min_amount / lot_units) if min_amount > 0 else 0.0
        quantity_tooltip = (
            f"Forex lot sizing enabled. 1.00 lot = {lot_units:,.0f} units."
            + (f" Min lot size: {min_lots:g}" if min_lots > 0 else "")
        )
    elif quantity_context.get("supports_lots"):
        quantity_tooltip = f"Units mode. Switch to Lots to trade standard forex lots ({lot_units:,.0f} units each)."
    if quantity_picker is not None:
        quantity_picker.setToolTip(quantity_tooltip)
    amount_input.setToolTip(
        (
            f"Ticket amount decimals: {amount_decimals}"
            + (f" | Lot units: {lot_units:,.0f}" if quantity_mode == "lots" else f" | Broker amount precision: {broker_amount_decimals}")
            + (
                f" | Min amount: {(min_amount / lot_units):g} lots"
                if quantity_mode == "lots" and min_amount > 0
                else (f" | Min amount: {min_amount}" if min_amount > 0 else "")
            )
        )
    )
    if submit_btn is not None:
        submit_btn.setEnabled(
            has_symbol
            and has_amount
            and ((not price_required) or has_price)
            and ((not stop_price_required) or has_stop_price)
        )
    if buy_btn is not None:
        buy_btn.setText(f"Buy {order_type_label}")
    if sell_btn is not None:
        sell_btn.setText(f"Sell {order_type_label}")

    entry_hint = "Market execution will use the broker's live price."
    if price_required:
        entry_hint = f"Limit order will be placed at {str(price_input.text() or '-').strip() or '-'}."
    if stop_price_required:
        entry_hint = (
            f"Stop-limit will trigger at {str(stop_price_input.text() or '-').strip() or '-'} "
            f"and rest as a limit at {str(price_input.text() or '-').strip() or '-'}."
        )
    stop_price_text = str(stop_price_input.text() or "").strip() if stop_price_input is not None else ""
    stop_loss_text = str(stop_loss_input.text() or "").strip() if stop_loss_input is not None else ""
    take_profit_text = str(take_profit_input.text() or "").strip() if take_profit_input is not None else ""
    side_text = str(side_picker.currentText() or "").strip().upper() or "-"
    amount_text = f"{amount_input.value():.{amount_decimals}f}".rstrip("0").rstrip(".")
    normalized_units = terminal._normalize_manual_trade_amount(
        symbol_text,
        amount_input.value(),
        quantity_mode=quantity_mode,
    )
    size_text = f"{amount_text or '0'} {quantity_mode.upper()}"
    if quantity_mode == "lots" and normalized_units is not None:
        units_text = (
            f"{float(normalized_units):,.0f}"
            if abs(float(normalized_units)) >= 1
            else f"{float(normalized_units):.6f}".rstrip("0").rstrip(".")
        )
        size_text = f"{size_text} (~{units_text} units)"
    if status is not None:
        source = str(getattr(window, "_manual_trade_source", "manual") or "manual").replace("_", " ").title()
        status.setText(
            f"{source} ticket | {symbol_text} | {side_text} | {order_type.upper()} | "
            f"{entry_hint} Stop: {stop_price_text or '-'} | SL: {stop_loss_text or '-'} | TP: {take_profit_text or '-'} | "
            f"Size: {size_text} | Px dp {price_decimals}"
        )
    terminal._sync_manual_trade_ticket_to_chart(window)


def populate_manual_trade_ticket(terminal, window, prefill=None):
    defaults = terminal._manual_trade_default_payload(prefill)
    if defaults["price"] in (None, ""):
        defaults["price"] = terminal._default_entry_price_for_symbol(defaults["symbol"], side=defaults["side"])
    symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
    side_picker = getattr(window, "_manual_trade_side_picker", None)
    type_picker = getattr(window, "_manual_trade_type_picker", None)
    quantity_picker = getattr(window, "_manual_trade_quantity_picker", None)
    amount_input = getattr(window, "_manual_trade_amount_input", None)
    price_input = getattr(window, "_manual_trade_price_input", None)
    stop_price_input = getattr(window, "_manual_trade_stop_price_input", None)
    stop_loss_input = getattr(window, "_manual_trade_stop_loss_input", None)
    take_profit_input = getattr(window, "_manual_trade_take_profit_input", None)
    hint = getattr(window, "_manual_trade_hint", None)

    if symbol_picker is not None:
        symbol_picker.blockSignals(True)
        symbol_picker.clear()
        symbol_picker.addItems(defaults["symbol_options"])
        if defaults["symbol"]:
            if symbol_picker.findText(defaults["symbol"]) == -1:
                symbol_picker.addItem(defaults["symbol"])
            symbol_picker.setCurrentText(defaults["symbol"])
        symbol_picker.blockSignals(False)
    if side_picker is not None:
        side_picker.blockSignals(True)
        side_picker.setCurrentText(defaults["side"])
        side_picker.blockSignals(False)
    if type_picker is not None:
        type_picker.blockSignals(True)
        type_picker.setCurrentText(defaults["order_type"])
        type_picker.blockSignals(False)
    if quantity_picker is not None:
        quantity_picker.blockSignals(True)
        quantity_picker.setCurrentText(str(defaults["quantity_mode"]).title())
        quantity_picker.blockSignals(False)
        window._manual_trade_last_quantity_symbol = defaults["symbol"]
    if amount_input is not None:
        amount_input.blockSignals(True)
        amount_input.setValue(max(float(defaults["amount"] or 0.0), 0.0))
        amount_input.blockSignals(False)
    for attr_name, value in (
        ("_manual_trade_price_input", defaults["price"]),
        ("_manual_trade_stop_price_input", defaults["stop_price"]),
        ("_manual_trade_stop_loss_input", defaults["stop_loss"]),
        ("_manual_trade_take_profit_input", defaults["take_profit"]),
    ):
        field = getattr(window, attr_name, None)
        if field is None:
            continue
        field.blockSignals(True)
        field.setText("" if value is None else str(value))
        field.blockSignals(False)

    window._manual_trade_source = defaults["source"]
    if hint is not None:
        if defaults["source"] in {"chart_double_click", "chart_context_menu"} and defaults["price"] is not None:
            hint.setText(
                f"Chart captured {defaults['symbol']} at {defaults['price']:.6f}. "
                "Stop loss and take profit are optional. Add them only if you want protection levels on this ticket."
            )
        else:
            hint.setText(
                "Set symbol, side, and size. Limit and stop-limit orders need prices. "
                "Stop loss and take profit are optional."
            )
    terminal._refresh_manual_trade_ticket(window)


def submit_manual_trade_from_ticket(terminal, window):
    if window is None:
        return
    symbol_picker = getattr(window, "_manual_trade_symbol_picker", None)
    side_picker = getattr(window, "_manual_trade_side_picker", None)
    type_picker = getattr(window, "_manual_trade_type_picker", None)
    quantity_picker = getattr(window, "_manual_trade_quantity_picker", None)
    amount_input = getattr(window, "_manual_trade_amount_input", None)
    price_input = getattr(window, "_manual_trade_price_input", None)
    stop_price_input = getattr(window, "_manual_trade_stop_price_input", None)
    stop_loss_input = getattr(window, "_manual_trade_stop_loss_input", None)
    take_profit_input = getattr(window, "_manual_trade_take_profit_input", None)

    symbol = str(symbol_picker.currentText() or "").strip() if symbol_picker is not None else ""
    side = str(side_picker.currentText() or "").strip().lower() if side_picker is not None else "buy"
    order_type = str(type_picker.currentText() or "").strip().lower() if type_picker is not None else "market"
    quantity_mode = terminal._normalize_manual_trade_quantity_mode(
        str(quantity_picker.currentText() or "units") if quantity_picker is not None else "units"
    )
    requested_amount = float(amount_input.value() or 0.0) if amount_input is not None else 0.0
    price_text = str(price_input.text() or "").strip() if price_input is not None else ""
    stop_price_text = str(stop_price_input.text() or "").strip() if stop_price_input is not None else ""
    stop_loss_text = str(stop_loss_input.text() or "").strip() if stop_loss_input is not None else ""
    take_profit_text = str(take_profit_input.text() or "").strip() if take_profit_input is not None else ""

    if not symbol:
        QMessageBox.warning(terminal, "Manual Order", "A symbol is required.")
        return
    amount, amount_error = terminal._validate_manual_trade_amount(
        symbol,
        requested_amount,
        quantity_mode=quantity_mode,
    )
    if amount_error:
        QMessageBox.warning(terminal, "Manual Order", amount_error)
        return

    price = terminal._normalize_manual_trade_price(symbol, price_text) if price_text else None
    if order_type in {"limit", "stop_limit"} and (price is None or price <= 0):
        QMessageBox.warning(terminal, "Manual Order", "Limit orders require a positive entry price.")
        return
    stop_price = terminal._normalize_manual_trade_price(symbol, stop_price_text) if stop_price_text else None
    if order_type == "stop_limit" and (stop_price is None or stop_price <= 0):
        QMessageBox.warning(terminal, "Manual Order", "Stop-limit orders require a positive stop trigger price.")
        return
    stop_loss = terminal._normalize_manual_trade_price(symbol, stop_loss_text) if stop_loss_text else None
    take_profit = terminal._normalize_manual_trade_price(symbol, take_profit_text) if take_profit_text else None

    for attr_name, value in (
        ("_manual_trade_price_input", price),
        ("_manual_trade_stop_price_input", stop_price),
        ("_manual_trade_stop_loss_input", stop_loss),
        ("_manual_trade_take_profit_input", take_profit),
    ):
        field = getattr(window, attr_name, None)
        if field is None:
            continue
        field.blockSignals(True)
        field.setText("" if value in (None, "") else str(value))
        field.blockSignals(False)
    if amount_input is not None:
        amount_input.blockSignals(True)
        amount_input.setValue(requested_amount)
        amount_input.blockSignals(False)
    terminal._refresh_manual_trade_ticket(window)

    asyncio.get_event_loop().create_task(
        terminal._submit_manual_trade(
            symbol=symbol,
            side=side,
            amount=amount,
            requested_amount=requested_amount,
            quantity_mode=quantity_mode,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
    )
