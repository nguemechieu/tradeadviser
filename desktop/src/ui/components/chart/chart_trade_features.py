from PySide6.QtWidgets import QLabel, QMenu


def install_chart_trade_features(ChartWidget):
    if getattr(ChartWidget, "_trade_features_installed", False):
        return

    orig_init = ChartWidget.__init__
    orig_set_trade_overlay = ChartWidget.set_trade_overlay
    orig_clear_trade_overlay = ChartWidget.clear_trade_overlay
    orig_handle_trade_line_moved = ChartWidget._handle_trade_line_moved
    orig_show_trade_context_menu = ChartWidget._show_trade_context_menu
    orig_update_price_lines = ChartWidget.update_price_lines

    def trade_plan_summary_text(self):
        state = dict(getattr(self, "_trade_overlay_state", {}) or {})
        side = str(state.get("side") or "buy").strip().lower() or "buy"
        entry = self._format_numeric_value(state.get("entry"))
        stop_loss = self._format_numeric_value(state.get("stop_loss"))
        take_profit = self._format_numeric_value(state.get("take_profit"))
        if entry is None:
            stats = getattr(self, "_last_candle_stats", {}) or {}
            entry = self._format_numeric_value(stats.get("last_price"))
        if entry is None or stop_loss is None or take_profit is None:
            return "Trade plan: set entry, stop, and target to see risk/reward."
        if side == "sell":
            risk = stop_loss - entry
            reward = entry - take_profit
        else:
            risk = entry - stop_loss
            reward = take_profit - entry
        if risk <= 0 or reward <= 0:
            return "Trade plan: levels are not aligned for the selected side."
        ratio = reward / risk if risk else 0.0
        return f"Trade plan: RR {ratio:.2f} | Risk {risk:.5f} | Reward {reward:.5f}"

    def update_trade_plan_label(self):
        label = getattr(self, "trade_plan_label", None)
        if label is None:
            return
        label.setText(self._trade_plan_summary_text())

    def trade_context_menu_definitions(self):
        return [
            ("Buy Market Ticket", "buy_market_ticket"),
            ("Sell Market Ticket", "sell_market_ticket"),
            None,
            ("Buy Limit Here", "buy_limit"),
            ("Sell Limit Here", "sell_limit"),
            None,
            ("Set Entry Here", "set_entry"),
            ("Set Stop Loss Here", "set_stop_loss"),
            ("Set Take Profit Here", "set_take_profit"),
            None,
            ("Clear Trade Levels", "clear_levels"),
        ]

    def wrapped_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        if getattr(self, "trade_plan_label", None) is None:
            self.trade_plan_label = QLabel()
            self.trade_plan_label.setStyleSheet("color: #9ed3ae; font-size: 11px; font-weight: 700;")
            self.trade_plan_label.setWordWrap(True)
            layout = self.info_bar.layout()
            insert_at = max(0, layout.count() - 1)
            layout.insertWidget(insert_at, self.trade_plan_label, 2)
        self._update_trade_plan_label()

    def wrapped_set_trade_overlay(self, entry=None, stop_loss=None, take_profit=None, side="buy"):
        result = orig_set_trade_overlay(self, entry=entry, stop_loss=stop_loss, take_profit=take_profit, side=side)
        self._update_trade_plan_label()
        return result

    def wrapped_clear_trade_overlay(self):
        result = orig_clear_trade_overlay(self)
        self._update_trade_plan_label()
        return result

    def wrapped_handle_trade_line_moved(self, line):
        result = orig_handle_trade_line_moved(self, line)
        self._update_trade_plan_label()
        return result

    def wrapped_update_price_lines(self, bid, ask, last=None):
        result = orig_update_price_lines(self, bid, ask, last=last)
        self._update_trade_plan_label()
        return result

    def wrapped_show_trade_context_menu(self, event):
        pos = event.scenePos()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return
        mouse_point = self.price_plot.getPlotItem().vb.mapSceneToView(pos)
        price = float(mouse_point.y())
        if not self._format_numeric_value(price):
            return orig_show_trade_context_menu(self, event)
        menu = QMenu(self)
        mapping = {}
        for item in self._trade_context_menu_definitions():
            if item is None:
                menu.addSeparator()
                continue
            label, action_name = item
            action = menu.addAction(label)
            mapping[action] = action_name
        chosen = menu.exec(event.screenPos().toPoint())
        action_name = mapping.get(chosen)
        if not action_name:
            return
        self.sigTradeContextAction.emit(
            {
                "action": action_name,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "price": price,
            }
        )
        try:
            event.accept()
        except Exception:
            pass

    ChartWidget._trade_plan_summary_text = trade_plan_summary_text
    ChartWidget._update_trade_plan_label = update_trade_plan_label
    ChartWidget._trade_context_menu_definitions = trade_context_menu_definitions
    ChartWidget.__init__ = wrapped_init
    ChartWidget.set_trade_overlay = wrapped_set_trade_overlay
    ChartWidget.clear_trade_overlay = wrapped_clear_trade_overlay
    ChartWidget._handle_trade_line_moved = wrapped_handle_trade_line_moved
    ChartWidget.update_price_lines = wrapped_update_price_lines
    ChartWidget._show_trade_context_menu = wrapped_show_trade_context_menu
    ChartWidget._trade_features_installed = True
