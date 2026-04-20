import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QMessageBox,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
)


WORKSPACE_DOCKS = (
    "market_watch_dock",
    "tick_chart_dock",
    "session_tabs_dock",
    "positions_dock",
    "trade_log_dock",
    "orderbook_dock",
    "strategy_scorecard_dock",
    "strategy_debug_dock",
    "risk_heatmap_dock",
    "ai_signal_dock",
    "live_agent_timeline_dock",
    "system_console_dock",
    "system_status_dock",
)
# Detached subwindows have historically mixed workspace-facing names such as
# "logs" with raw window keys such as "system_logs". Normalize both forms so
# save/restore and workspace presets can manage the full tool-window set.
TOOL_WINDOW_ALIASES = {
    "agent_timeline": "agent_timeline",
    "api_reference": "api_reference",
    "application_settings": "application_settings",
    "backtesting_workspace": "backtesting_workspace",
    "closed_journal": "closed_trade_journal",
    "closed_trade_journal": "closed_trade_journal",
    "docs": "help_documentation",
    "documentation": "help_documentation",
    "education_trader_tv": "education_trader_tv",
    "help_documentation": "help_documentation",
    "logs": "logs",
    "manual_trade": "manual_trade_ticket",
    "manual_trade_ticket": "manual_trade_ticket",
    "market_chat": "market_chat",
    "market_chatgpt": "market_chat",
    "ml_monitor": "ml_monitor",
    "ml_research": "ml_research_lab",
    "ml_research_lab": "ml_research_lab",
    "notification": "notification_center",
    "notifications": "notification_center",
    "notification_center": "notification_center",
    "performance": "performance_analytics",
    "performance_analytics": "performance_analytics",
    "portfolio_exposure": "portfolio_exposure",
    "position_analysis": "position_analysis",
    "quant_pm": "quant_pm",
    "risk_settings": "application_settings",
    "settings": "application_settings",
    "stellar_asset_explorer": "stellar_asset_explorer",
    "strategy_assigner": "strategy_assignments",
    "strategy_assignments": "strategy_assignments",
    "strategy_optimization": "strategy_optimization",
    "symbol_universe": "symbol_universe",
    "system_health": "system_health",
    "system_logs": "logs",
    "trade_checklist": "trade_checklist",
    "trade_journal_review": "trade_journal_review",
    # TraderAgent now shares the same detached runtime window as the broader
    # agent monitor so saved layouts and aliases all converge on one live view.
    "trader_agent": "agent_timeline",
    "traderagent": "agent_timeline",
    "trader_agent_monitor": "agent_timeline",
    "trader_agent_timeline": "agent_timeline",
    "trade_review": "trade_review",
    "trade_recommendations": "trade_recommendations",
}
TOOL_WINDOWS = set(TOOL_WINDOW_ALIASES.values())
WORKSPACE_PRESETS = {
    "trading": {
        "docks": {"market_watch_dock", "positions_dock", "trade_log_dock", "orderbook_dock"},
        "tools": [],
    },
    "research": {
        "docks": {"market_watch_dock", "orderbook_dock", "ai_signal_dock"},
        "tools": ["trade_recommendations", "quant_pm", "agent_timeline"],
    },
    "risk": {
        "docks": {"positions_dock", "orderbook_dock", "risk_heatmap_dock"},
        "tools": ["portfolio_exposure", "position_analysis"],
    },
    "review": {
        "docks": {"positions_dock", "orderbook_dock", "trade_log_dock", "ai_signal_dock"},
        "tools": ["performance_analytics", "closed_trade_journal", "notification_center"],
    },
}

SHARED_DOCK_ALIAS_GROUPS = (
    frozenset({"positions_dock", "orderbook_dock", "open_orders_dock"}),
)

PANEL_ACTION_SPECS = (
    ("action_market_watch_panel", "Market Watch", "market_watch_dock"),
    ("action_tick_chart_panel", "Tick Chart", "tick_chart_dock"),
    ("action_session_tabs_panel", "Sessions", "session_tabs_dock"),
    ("action_positions_panel", "Positions", "positions_dock"),
    ("action_open_orders_panel", "Open Orders", "open_orders_dock"),
    ("action_trade_log_panel", "Trade Log", "trade_log_dock"),
    ("action_orderbook_panel", "Order Book", "orderbook_dock"),
    ("action_ai_signal_panel", "AI Signal Monitor", "ai_signal_dock"),
    ("action_live_agent_timeline_panel", "Agent Runtime Monitor", "live_agent_timeline_dock"),
    ("action_risk_heatmap_panel", "Risk Heatmap", "risk_heatmap_dock"),
    ("action_strategy_scorecard_panel", "Strategy Scorecard", "strategy_scorecard_dock"),
    ("action_strategy_debug_panel", "Strategy Debug", "strategy_debug_dock"),
    ("action_system_console_panel", "System Console", "system_console_dock"),
    ("action_system_status_panel", "System Status", "system_status_dock"),
)


def _runtime_timestamp_seconds(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1_000_000_000_000:
            return numeric / 1000.0
        return numeric

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric = float(text)
    except (TypeError, ValueError):
        numeric = None
    if numeric is not None:
        if numeric > 1_000_000_000_000:
            return numeric / 1000.0
        return numeric

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.timestamp()


def install_terminal_operator_features(Terminal):
    if getattr(Terminal, "_operator_features_installed", False):
        return

    orig_create_menu_bar = Terminal._create_menu_bar
    orig_update_symbols = Terminal._update_symbols
    orig_update_trade_log = Terminal._update_trade_log
    orig_update_connection_status = Terminal.update_connection_status
    orig_refresh_terminal = Terminal._refresh_terminal
    orig_restore_settings = Terminal._restore_settings
    orig_close_event = Terminal.closeEvent
    orig_submit_manual_trade_from_ticket = Terminal._submit_manual_trade_from_ticket
    orig_manual_trade_default_payload = Terminal._manual_trade_default_payload
    orig_show_async_message = Terminal._show_async_message
    orig_handle_chart_trade_context_action = Terminal._handle_chart_trade_context_action
    orig_on_chart_tab_changed = Terminal._on_chart_tab_changed

    def invoke_callable(value: object, *args: object, **kwargs: object) -> Any:
        if not callable(value):
            return None
        return cast(Callable[..., Any], value)(*args, **kwargs)

    def format_compact_number(value: object) -> str:
        try:
            number = float(value)
        except Exception:
            return "-"
        if abs(number) >= 1000:
            return f"{number:,.2f}"
        return f"{number:.2f}"

    def workspace_context_key(self):
        controller = getattr(self, "controller", None)
        exchange = "default"
        account = "default"
        if controller is not None:
            exchange_getter = getattr(controller, "_active_exchange_code", None)
            account_getter = getattr(controller, "current_account_label", None)
            try:
                exchange = str(invoke_callable(exchange_getter) if callable(exchange_getter) else getattr(controller, "exchange_name", "default") or "default")
            except Exception:
                exchange = str(getattr(controller, "exchange_name", "default") or "default")
            try:
                account = str(invoke_callable(account_getter) if callable(account_getter) else getattr(controller, "account_label", "default") or "default")
            except Exception:
                account = str(getattr(controller, "account_label", "default") or "default")
        value = f"{exchange}__{account}".lower().strip()
        for old, new in (("/", "_"), ("\\", "_"), (":", "_"), (" ", "_"), ("-", "_")):
            value = value.replace(old, new)
        value = "_".join(part for part in value.split("_") if part)
        return value or "default"

    def workspace_settings_prefix(self, slot="last"):
        slot_name = str(slot or "last").strip().lower() or "last"
        return f"workspace_layout/{self._workspace_context_key()}/{slot_name}"

    def favorite_symbols_storage_key(self):
        return f"trader_memory/{self._workspace_context_key()}/favorite_symbols"

    def manual_trade_template_storage_key(self):
        return f"trader_memory/{self._workspace_context_key()}/manual_trade_template"

    def ensure_notification_state(self):
        if not isinstance(getattr(self, "_notification_records", None), list):
            self._notification_records = []
        if not isinstance(getattr(self, "_notification_dedupe_cache", None), dict):
            self._notification_dedupe_cache = {}
        if not isinstance(getattr(self, "_runtime_notification_state", None), dict):
            self._runtime_notification_state = {}
        return self._notification_records

    def refresh_notification_action_text(self):
        action = getattr(self, "action_notifications", None)
        if action is None:
            return
        records = self._ensure_notification_state()
        count = len(list(records or []))
        action.setText("Notification Center" if count <= 0 else f"Notification Center ({count})")

    def push_notification(self, title, message, level="INFO", source="system", dedupe_seconds=20.0):
        self._ensure_notification_state()
        title_text = str(title or "").strip() or "Notification"
        message_text = str(message or "").strip()
        level_text = str(level or "INFO").strip().upper() or "INFO"
        source_text = str(source or "system").strip().lower() or "system"
        now = time.time()
        fingerprint = (title_text, message_text, level_text, source_text)
        cooldown = max(float(dedupe_seconds or 0.0), 0.0)
        last_seen = self._notification_dedupe_cache.get(fingerprint)
        if last_seen is not None and cooldown > 0 and (now - float(last_seen)) < cooldown:
            return None
        self._notification_dedupe_cache[fingerprint] = now
        created_at = datetime.now().astimezone()
        self._notification_records.append(
            {
                "id": int(now * 1000),
                "timestamp": now,
                "time_text": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "created_at": created_at.isoformat(),
                "title": title_text,
                "message": message_text,
                "level": level_text,
                "source": source_text,
            }
        )
        if len(self._notification_records) > 400:
            del self._notification_records[:-400]
        refresh_notification_action_text(self)
        window = (getattr(self, "detached_tool_windows", {}) or {}).get("notification_center")
        if self._is_qt_object_alive(window):
            refresh_notification_center_window(self, window)
        return self._notification_records[-1]

    def refresh_notification_center_window(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("notification_center")
        if not self._is_qt_object_alive(window):
            return
        table = getattr(window, "_notification_table", None)
        filter_input = getattr(window, "_notification_filter", None)
        summary = getattr(window, "_notification_summary", None)
        if table is None or filter_input is None or summary is None:
            return
        query = str(filter_input.text() or "").strip().lower()
        rows = []
        for record in reversed(list(self._ensure_notification_state() or [])):
            haystack = " ".join(str(record.get(key, "") or "") for key in ("title", "message", "level", "source", "time_text")).lower()
            if query and query not in haystack:
                continue
            rows.append(record)
        table.setRowCount(len(rows))
        colors = {
            "INFO": QColor("#74c0fc"),
            "WARN": QColor("#ffd166"),
            "WARNING": QColor("#ffd166"),
            "ERROR": QColor("#ff7b72"),
            "CRITICAL": QColor("#ff5d73"),
        }
        for row_index, record in enumerate(rows):
            values = [record.get("time_text", "-"), record.get("level", "INFO"), record.get("title", "Notification"), record.get("message", "")]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setToolTip(str(record.get("message", "") or ""))
                if column == 1:
                    item.setForeground(colors.get(str(record.get("level", "INFO")).upper(), QColor("#d8e6ff")))
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        summary.setText(f"{len(rows)} notifications shown for {self._workspace_context_key().replace('__', ' / ')}.")
        refresh_notification_action_text(self)

    def open_notification_center(self):
        window = self._get_or_create_tool_window("notification_center", "Notification Center", width=860, height=560)
        if getattr(window, "_notification_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            summary = QLabel("Notifications collect fills, rejects, disconnects, stale market-data warnings, and guard events.")
            summary.setWordWrap(True)
            summary.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; padding: 10px;")
            layout.addWidget(summary)
            controls = QHBoxLayout()
            filter_input = QLineEdit()
            filter_input.setPlaceholderText("Filter notifications")
            filter_input.textChanged.connect(lambda *_: self._refresh_notification_center_window(window))
            controls.addWidget(filter_input, 1)
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda: (setattr(self, "_notification_records", []), refresh_notification_action_text(self), self._refresh_notification_center_window(window)))
            controls.addWidget(clear_btn)
            layout.addLayout(controls)
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Time", "Level", "Event", "Details"])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().setVisible(False)
            layout.addWidget(table, 1)
            window.setCentralWidget(container)
            window._notification_container = container
            window._notification_summary = summary
            window._notification_filter = filter_input
            window._notification_table = table
        self._refresh_notification_center_window(window)
        window.show()
        window.raise_()
        window.activateWindow()
        if getattr(window, "_notification_filter", None) is not None:
            window._notification_filter.setFocus()
        return window

    def symbol_universe_snapshot(self):
        controller = getattr(self, "controller", None)
        snapshot = {}
        if controller is not None and hasattr(controller, "get_symbol_universe_snapshot"):
            try:
                snapshot = controller.get_symbol_universe_snapshot() or {}
            except Exception:
                snapshot = {}

        def normalize_symbol(symbol):
            text = str(symbol or "").strip()
            if not text:
                return ""
            normalizer = getattr(self, "_normalized_symbol", None)
            if callable(normalizer):
                try:
                    normalized = str(normalizer(text) or "").strip()
                    if normalized:
                        return normalized
                except Exception:
                    pass
            upper_text = text.upper()
            if (
                "PERP" in upper_text
                or re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", upper_text)
                or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", upper_text)
            ):
                return upper_text
            return upper_text.replace("-", "/").replace("_", "/")

        def normalize_symbols(values):
            normalized = []
            seen = set()
            for value in list(values or []):
                symbol = normalize_symbol(value)
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                normalized.append(symbol)
            return normalized

        if not isinstance(snapshot, dict) or not snapshot:
            symbols = []
            if controller is not None:
                try:
                    symbols = list(getattr(controller, "symbols", []) or [])
                except Exception:
                    symbols = []
            catalog = normalize_symbols(symbols)
            active = list(catalog[: min(len(catalog), 10)])
            snapshot = {
                "active": active,
                "watchlist": list(active),
                "catalog": catalog,
                "background_catalog": list(catalog),
                "last_batch": list(active[: min(len(active), 8)]),
                "rotation_cursor": 0,
                "policy": {},
            }

        normalized_snapshot = dict(snapshot)
        for key in ("active", "watchlist", "catalog", "background_catalog", "last_batch"):
            normalized_snapshot[key] = normalize_symbols(normalized_snapshot.get(key, []))
        normalized_snapshot["rotation_cursor"] = int(normalized_snapshot.get("rotation_cursor", 0) or 0)
        policy = normalized_snapshot.get("policy", {})
        normalized_snapshot["policy"] = dict(policy) if isinstance(policy, dict) else {}
        return normalized_snapshot

    def refresh_symbol_universe_window(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("symbol_universe")
        if not self._is_qt_object_alive(window):
            return
        tree = getattr(window, "_symbol_universe_tree", None)
        filter_input = getattr(window, "_symbol_universe_filter", None)
        summary = getattr(window, "_symbol_universe_summary", None)
        if tree is None or filter_input is None or summary is None:
            return

        controller = getattr(self, "controller", None)
        snapshot = self._symbol_universe_snapshot()
        query = str(filter_input.text() or "").strip().lower()
        policy = dict(snapshot.get("policy", {}) or {})
        active = list(snapshot.get("active", []) or [])
        watchlist = list(snapshot.get("watchlist", []) or [])
        catalog = list(snapshot.get("catalog", []) or [])
        background_catalog = list(snapshot.get("background_catalog", []) or [])
        last_batch = list(snapshot.get("last_batch", []) or [])
        display_limit = 60

        tier_specs = (
            ("Active", active, "Live symbols currently driving charts, execution, and frequent refreshes."),
            ("Watchlist", watchlist, "Priority symbols kept near the top of discovery and operator focus."),
            ("Discovery Batch", last_batch, "The most recent rotating discovery slice scanned in the background."),
            ("Background Catalog", background_catalog, "The broader rotation pool used without overloading the broker."),
            ("Catalog", catalog, "All broker-supported symbols available to search and stage into active use."),
        )

        tree.clear()
        visible_counts = {}
        for tier_name, symbols, description in tier_specs:
            filtered_symbols = [symbol for symbol in symbols if (not query) or (query in symbol.lower()) or (query in tier_name.lower())]
            visible_counts[tier_name] = len(filtered_symbols)
            if query and not filtered_symbols and query not in description.lower():
                continue
            top_level = QTreeWidgetItem([f"{tier_name} ({len(symbols)})", description, ""])
            top_level.setExpanded(tier_name in {"Active", "Watchlist", "Discovery Batch"})
            tree.addTopLevelItem(top_level)
            for symbol in filtered_symbols[:display_limit]:
                top_level.addChild(QTreeWidgetItem([symbol, tier_name, ""]))
            hidden_count = len(filtered_symbols) - min(len(filtered_symbols), display_limit)
            if hidden_count > 0:
                top_level.addChild(
                    QTreeWidgetItem(
                        [f"+ {hidden_count} more symbols", "Hidden to keep the window responsive.", "Refine the filter to narrow this tier."]
                    )
                )
            if not filtered_symbols:
                top_level.addChild(QTreeWidgetItem(["No matching symbols", tier_name, "Adjust the filter or refresh the snapshot."]))

        for column in range(3):
            tree.resizeColumnToContents(column)
        tree.header().setStretchLastSection(True)
        broker_name = "Broker"
        if controller is not None:
            exchange_getter = getattr(controller, "_active_exchange_code", None)
            try:
                if callable(exchange_getter):
                    broker_name = str(exchange_getter() or broker_name)
                else:
                    broker_name = str(getattr(controller, "exchange_name", broker_name) or broker_name)
            except Exception:
                broker_name = str(getattr(controller, "exchange_name", broker_name) or broker_name)
        batch_size = policy.get("discovery_batch_size", "-")
        live_cap = policy.get("live_symbol_limit", "-")
        watchlist_cap = policy.get("watchlist_limit", "-")
        filter_suffix = f" Filter: {query}." if query else ""
        summary.setText(
            f"{broker_name} universe | Active {len(active)}/{live_cap} | "
            f"Watchlist {len(watchlist)}/{watchlist_cap} | "
            f"Catalog {len(catalog)} | Background {len(background_catalog)} | "
            f"Current batch {len(last_batch)}/{batch_size}.{filter_suffix}"
        )

    def open_symbol_universe(self):
        window = self._get_or_create_tool_window("symbol_universe", "Symbol Universe", width=820, height=600)
        if getattr(window, "_symbol_universe_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            summary = QLabel(
                "See how each broker is split into active, watchlist, catalog, and rotating discovery tiers."
            )
            summary.setWordWrap(True)
            summary.setStyleSheet(
                "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; padding: 10px;"
            )
            layout.addWidget(summary)
            controls = QHBoxLayout()
            filter_input = QLineEdit()
            filter_input.setPlaceholderText("Filter symbols or tiers")
            filter_input.textChanged.connect(lambda *_: self._refresh_symbol_universe_window(window))
            controls.addWidget(filter_input, 1)
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(lambda: self._refresh_symbol_universe_window(window))
            controls.addWidget(refresh_btn)
            layout.addLayout(controls)
            tree = QTreeWidget()
            tree.setColumnCount(3)
            tree.setHeaderLabels(["Tier / Symbol", "Scope", "Notes"])
            layout.addWidget(tree, 1)
            window.setCentralWidget(container)
            window._symbol_universe_container = container
            window._symbol_universe_summary = summary
            window._symbol_universe_filter = filter_input
            window._symbol_universe_tree = tree
        self._refresh_symbol_universe_window(window)
        window.show()
        window.raise_()
        window.activateWindow()
        if getattr(window, "_symbol_universe_filter", None) is not None:
            window._symbol_universe_filter.setFocus()
        return window

    def refresh_agent_timeline_window(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return
        tree = getattr(window, "_agent_timeline_tree", None)
        filter_input = getattr(window, "_agent_timeline_filter", None)
        status_filter = getattr(window, "_agent_timeline_status_filter", None)
        timeframe_filter = getattr(window, "_agent_timeline_timeframe_filter", None)
        strategy_filter = getattr(window, "_agent_timeline_strategy_filter", None)
        pin_btn = getattr(window, "_agent_timeline_pin_btn", None)
        summary = getattr(window, "_agent_timeline_summary", None)
        if tree is None or filter_input is None or summary is None:
            return

        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "live_agent_runtime_feed"):
            rows = []
        else:
            rows = list(controller.live_agent_runtime_feed(limit=300) or [])
        row_source_label = "live agent events"
        if not rows:
            rows = list(self._agent_timeline_snapshot_rows(limit=180) or [])
            if rows:
                row_source_label = "restored decision steps"

        pinned_symbol = str(getattr(window, "_agent_timeline_pinned_symbol", "") or "").strip().upper().replace("-", "/").replace("_", "/")
        if pinned_symbol:
            rows = [
                dict(row)
                for row in rows
                if str((row or {}).get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/") == pinned_symbol
            ]
        self._populate_agent_timeline_filters(window, rows)

        selected_status = str(status_filter.currentText() or "").strip() if status_filter is not None else ""
        if selected_status and selected_status != "All Statuses":
            rows = [row for row in rows if self._agent_timeline_row_status_label(row) == selected_status]

        selected_timeframe = str(timeframe_filter.currentText() or "").strip() if timeframe_filter is not None else ""
        if selected_timeframe and selected_timeframe != "All Timeframes":
            rows = [row for row in rows if str((row or {}).get("timeframe") or "").strip() == selected_timeframe]

        selected_strategy = str(strategy_filter.currentText() or "").strip() if strategy_filter is not None else ""
        if selected_strategy and selected_strategy != "All Strategies":
            rows = [row for row in rows if str((row or {}).get("strategy_name") or "").strip() == selected_strategy]

        query = str(filter_input.text() or "").strip().lower()
        if query:
            filtered = []
            for row in rows:
                haystack = " ".join(
                    str(row.get(key) or "")
                    for key in (
                        "timestamp_label",
                        "kind",
                        "symbol",
                        "agent_name",
                        "event_type",
                        "stage",
                        "profile_id",
                        "action",
                        "strategy_name",
                        "timeframe",
                        "message",
                        "reason",
                    )
                ).lower()
                if query in haystack:
                    filtered.append(row)
            rows = filtered

        selected_symbol = self._selected_agent_timeline_symbol(window)
        tree.clear()
        kind_colors = {
            "memory": QColor("#74c0fc"),
            "bus": QColor("#ffd166"),
        }
        raw_anomaly_snapshot = self._agent_timeline_anomaly_snapshot(rows)
        anomaly_snapshot = self._visible_agent_timeline_anomaly_snapshot(window, raw_anomaly_snapshot)
        anomaly_map = {item["symbol"]: list(item["issues"]) for item in anomaly_snapshot.get("items", [])}
        grouped_rows = {}
        ordered_symbols = []
        for row in rows:
            symbol = str(row.get("symbol") or "Unscoped").strip() or "Unscoped"
            if symbol not in grouped_rows:
                grouped_rows[symbol] = []
                ordered_symbols.append(symbol)
            grouped_rows[symbol].append(dict(row))

        top_level_to_select = None
        for symbol in ordered_symbols:
            symbol_rows = grouped_rows.get(symbol, [])
            latest = symbol_rows[0] if symbol_rows else {}
            latest_message = str(latest.get("message") or latest.get("reason") or "").strip()
            latest_stage = str(latest.get("stage") or latest.get("action") or "").strip()
            group_item = QTreeWidgetItem(
                [
                    str(latest.get("timestamp_label") or "-"),
                    "Symbol",
                    symbol,
                    f"{len(symbol_rows)} events",
                    latest_stage,
                    str(latest.get("strategy_name") or "").strip(),
                    str(latest.get("timeframe") or "").strip(),
                    latest_message,
                ]
            )
            group_item.setData(0, Qt.ItemDataRole.UserRole, symbol)
            group_item.setData(0, Qt.ItemDataRole.UserRole + 1, json.dumps(latest, default=str))
            tree.addTopLevelItem(group_item)
            if symbol in anomaly_map:
                anomaly_text = "; ".join(anomaly_map[symbol])
                for column in range(8):
                    group_item.setForeground(column, QColor("#ff7b72"))
                    group_item.setToolTip(column, anomaly_text)
            if selected_symbol and symbol == selected_symbol:
                top_level_to_select = group_item

            for row in symbol_rows:
                actor = str(row.get("agent_name") or row.get("event_type") or "Agent").strip() or "Agent"
                message = str(row.get("message") or row.get("reason") or "").strip()
                stage_text = str(row.get("stage") or row.get("action") or "").strip()
                child = QTreeWidgetItem(
                    [
                        str(row.get("timestamp_label") or "-"),
                        str(row.get("kind") or "").strip().title() or "Runtime",
                        symbol,
                        actor,
                        stage_text,
                        str(row.get("strategy_name") or "").strip(),
                        str(row.get("timeframe") or "").strip(),
                        message,
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, symbol)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, json.dumps(row, default=str))
                child.setToolTip(7, message)
                child.setForeground(1, kind_colors.get(str(row.get("kind") or "").strip().lower(), QColor("#d8e6ff")))
                group_item.addChild(child)
            group_item.setExpanded(True)

        for column in range(7):
            tree.resizeColumnToContents(column)
        if top_level_to_select is not None:
            tree.setCurrentItem(top_level_to_select)
        elif tree.topLevelItemCount() > 0:
            tree.setCurrentItem(tree.topLevelItem(0))
        active_filters = []
        if pinned_symbol:
            active_filters.append(f"Pinned {pinned_symbol}")
        if selected_status and selected_status != "All Statuses":
            active_filters.append(selected_status)
        if selected_timeframe and selected_timeframe != "All Timeframes":
            active_filters.append(selected_timeframe)
        if selected_strategy and selected_strategy != "All Strategies":
            active_filters.append(selected_strategy)
        suffix = f" | Filters: {', '.join(active_filters)}" if active_filters else ""
        summary.setText(
            f"{sum(len(grouped_rows[symbol]) for symbol in ordered_symbols)} {row_source_label} across {len(ordered_symbols)} symbols.{suffix}"
        )
        if pin_btn is not None:
            pin_btn.setText(f"Unpin {pinned_symbol}" if pinned_symbol else "Pin Selected Symbol")
        window._agent_timeline_current_rows = [dict(row) for row in rows]
        window._agent_timeline_anomaly_snapshot_all = raw_anomaly_snapshot
        self._refresh_agent_timeline_health(window, rows)
        self._refresh_agent_timeline_anomalies(window, rows)
        self._refresh_agent_timeline_details(window)

    def agent_timeline_snapshot_rows(self, limit=120):
        controller = getattr(self, "controller", None)
        snapshot_resolver = getattr(controller, "decision_timeline_snapshot", None) if controller is not None else None
        if not callable(snapshot_resolver):
            return []

        def normalize_symbol(symbol):
            return str(symbol or "").strip().upper().replace("-", "/").replace("_", "/")

        candidates = []
        seen_candidates = set()

        def append_candidate(symbol):
            normalized = normalize_symbol(symbol)
            if not normalized or normalized in seen_candidates:
                return
            seen_candidates.add(normalized)
            candidates.append(normalized)

        symbol_resolver = getattr(controller, "get_active_autotrade_symbols", None) if controller is not None else None
        if callable(symbol_resolver):
            try:
                for symbol in list(symbol_resolver() or []):
                    append_candidate(symbol)
            except Exception:
                pass

        for symbol in list(getattr(controller, "symbols", []) or []):
            append_candidate(symbol)

        raw_assignments = getattr(controller, "symbol_strategy_assignments", None)
        if isinstance(raw_assignments, dict):
            for symbol in raw_assignments.keys():
                append_candidate(symbol)

        current_symbol_resolver = getattr(self, "_current_chart_symbol", None)
        if callable(current_symbol_resolver):
            try:
                current_symbol = normalize_symbol(current_symbol_resolver())
            except Exception:
                current_symbol = ""
            if current_symbol and (not candidates or current_symbol in seen_candidates):
                append_candidate(current_symbol)

        if not candidates:
            candidates = [""]

        rows = []
        seen_rows = set()
        max_symbols = max(1, min(8, int(limit or 120)))
        for candidate in candidates[:max_symbols]:
            try:
                snapshot = dict(snapshot_resolver(symbol=candidate or None, limit=12) or {})
            except TypeError:
                snapshot = dict(snapshot_resolver(candidate or None) or {})
            except Exception:
                snapshot = {}
            steps = list(snapshot.get("steps") or [])
            if not steps:
                continue

            snapshot_symbol = normalize_symbol(snapshot.get("symbol") or candidate)
            summary_text = str(snapshot.get("summary") or "").strip()
            for step in reversed(steps):
                payload = dict(step.get("payload") or {}) if isinstance(step.get("payload"), dict) else {}
                status = str(step.get("status") or "").strip().lower()
                approved = payload.get("approved")
                if approved is None:
                    if status == "approved":
                        approved = True
                    elif status == "rejected":
                        approved = False
                action = str(payload.get("action") or payload.get("decision") or "").strip().upper()
                fingerprint = (
                    snapshot_symbol,
                    str(step.get("decision_id") or payload.get("decision_id") or "").strip(),
                    str(step.get("agent_name") or "").strip(),
                    str(step.get("stage") or "").strip(),
                    str(step.get("timestamp_label") or "").strip(),
                )
                if fingerprint in seen_rows:
                    continue
                seen_rows.add(fingerprint)
                rows.append(
                    {
                        "kind": "snapshot",
                        "symbol": snapshot_symbol,
                        "agent_name": str(step.get("agent_name") or "").strip(),
                        "event_type": str(step.get("status") or "").strip(),
                        "stage": str(step.get("stage") or step.get("status") or "").strip(),
                        "strategy_name": str(step.get("strategy_name") or payload.get("strategy_name") or payload.get("selected_strategy") or "").strip(),
                        "timeframe": str(step.get("timeframe") or payload.get("timeframe") or "").strip(),
                        "decision_id": str(step.get("decision_id") or payload.get("decision_id") or "").strip(),
                        "timestamp": step.get("timestamp"),
                        "timestamp_label": str(step.get("timestamp_label") or "").strip(),
                        "message": str(step.get("reason") or payload.get("reason") or summary_text).strip(),
                        "reason": str(step.get("reason") or payload.get("reason") or "").strip(),
                        "side": str(step.get("side") or payload.get("side") or "").strip().lower(),
                        "approved": approved,
                        "profile_id": str(payload.get("profile_id") or "").strip(),
                        "action": action,
                        "confidence": payload.get("confidence", step.get("confidence")),
                        "model_probability": payload.get("model_probability"),
                        "quantity": payload.get("quantity"),
                        "price": payload.get("price"),
                        "applied_constraints": list(payload.get("applied_constraints") or []) if isinstance(payload.get("applied_constraints"), (list, tuple, set)) else [],
                        "votes": dict(payload.get("votes") or {}) if isinstance(payload.get("votes"), dict) else {},
                        "features": dict(payload.get("features") or {}) if isinstance(payload.get("features"), dict) else {},
                        "metadata": dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
                        "payload": payload,
                        "source": "snapshot",
                    }
                )
                if len(rows) >= max(1, int(limit or 120)):
                    break
            if len(rows) >= max(1, int(limit or 120)):
                break

        rows.sort(
            key=lambda row: (
                _runtime_timestamp_seconds(row.get("timestamp")) or 0.0,
                str(row.get("timestamp_label") or ""),
            ),
            reverse=True,
        )
        return [dict(row) for row in rows[: max(1, int(limit or 120))]]

    def selected_agent_timeline_symbol(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return ""
        tree = getattr(window, "_agent_timeline_tree", None)
        if tree is None:
            return ""
        item = tree.currentItem()
        if item is None:
            return ""
        current = item
        while current.parent() is not None:
            current = current.parent()
        symbol = str(current.data(0, Qt.ItemDataRole.UserRole) or item.data(0, Qt.ItemDataRole.UserRole) or "").strip()
        return symbol.upper().replace("-", "/").replace("_", "/")

    def selected_agent_timeline_row(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return {}
        tree = getattr(window, "_agent_timeline_tree", None)
        if tree is None:
            return {}
        item = tree.currentItem()
        if item is None:
            return {}
        raw = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not raw and item.parent() is not None:
            raw = item.parent().data(0, Qt.ItemDataRole.UserRole + 1)
        if not raw:
            return {}
        try:
            payload = json.loads(str(raw))
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def agent_timeline_row_status_label(self, row):
        event_type = str((row or {}).get("event_type") or "").strip().lower()
        approved = (row or {}).get("approved")
        stage = str((row or {}).get("stage") or "").strip()

        if event_type == "risk_alert" or approved is False:
            return "Rejected"
        if event_type == "risk_approved" or approved is True:
            return "Approved"
        if event_type == "order_filled":
            return "Filled"
        if event_type == "execution_plan":
            return "Execution"
        if stage:
            return stage.replace("_", " ").title()
        if event_type:
            return event_type.replace("_", " ").title()
        return "Live"

    def populate_agent_timeline_filters(self, window, rows):
        if not self._is_qt_object_alive(window):
            return

        status_combo = getattr(window, "_agent_timeline_status_filter", None)
        timeframe_combo = getattr(window, "_agent_timeline_timeframe_filter", None)
        strategy_combo = getattr(window, "_agent_timeline_strategy_filter", None)
        if any(combo is None for combo in (status_combo, timeframe_combo, strategy_combo)):
            return

        def refill(combo, default_label, values):
            current = str(combo.currentText() or "").strip()
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_label)
            for value in values:
                combo.addItem(value)
            if current and combo.findText(current) >= 0:
                combo.setCurrentText(current)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(blocked)

        refill(
            status_combo,
            "All Statuses",
            sorted(
                {
                    self._agent_timeline_row_status_label(row)
                    for row in rows
                    if self._agent_timeline_row_status_label(row)
                }
            ),
        )
        refill(
            timeframe_combo,
            "All Timeframes",
            sorted({str((row or {}).get("timeframe") or "").strip() for row in rows if str((row or {}).get("timeframe") or "").strip()}),
        )
        refill(
            strategy_combo,
            "All Strategies",
            sorted({str((row or {}).get("strategy_name") or "").strip() for row in rows if str((row or {}).get("strategy_name") or "").strip()}),
        )

    def toggle_agent_timeline_pin_symbol(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return ""

        selected_symbol = self._selected_agent_timeline_symbol(window)
        current_pinned = str(getattr(window, "_agent_timeline_pinned_symbol", "") or "").strip().upper().replace("-", "/").replace("_", "/")
        if current_pinned and current_pinned == selected_symbol:
            window._agent_timeline_pinned_symbol = ""
        elif selected_symbol:
            window._agent_timeline_pinned_symbol = selected_symbol
        else:
            self._show_async_message("Agent Runtime Monitor", "Select a symbol before pinning it in the monitor.", QMessageBox.Icon.Warning)
            return current_pinned

        self._refresh_agent_timeline_window(window)
        return str(getattr(window, "_agent_timeline_pinned_symbol", "") or "").strip()

    def agent_timeline_health_snapshot(self, rows, now_ts=None):
        events = [dict(row) for row in list(rows or [])]
        approved = 0
        rejected = 0
        execution = 0
        visible_symbols = []
        recent_symbols = []
        recent_count = 0
        now_value = float(now_ts if now_ts is not None else time.time())

        for row in events:
            status_label = self._agent_timeline_row_status_label(row)
            if status_label == "Approved":
                approved += 1
            elif status_label == "Rejected":
                rejected += 1
            elif status_label in {"Execution", "Filled"}:
                execution += 1

            symbol = str((row or {}).get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/")
            if symbol and symbol not in visible_symbols:
                visible_symbols.append(symbol)

            timestamp_value = (row or {}).get("timestamp")
            timestamp_float = _runtime_timestamp_seconds(timestamp_value)
            if timestamp_float is not None and (now_value - timestamp_float) <= 60.0:
                recent_count += 1
                if symbol and symbol not in recent_symbols:
                    recent_symbols.append(symbol)

        latest_symbols = visible_symbols[:3]
        return {
            "approved": approved,
            "rejected": rejected,
            "execution": execution,
            "visible_symbol_count": len(visible_symbols),
            "latest_symbols": latest_symbols,
            "recent_count": recent_count,
            "recent_symbols": recent_symbols[:4],
        }

    def agent_timeline_anomaly_snapshot(self, rows, now_ts=None):
        grouped = {}
        now_value = float(now_ts if now_ts is not None else time.time())

        for row in list(rows or []):
            symbol = str((row or {}).get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/")
            if not symbol:
                continue
            grouped.setdefault(symbol, []).append(dict(row))

        anomalies = []
        for symbol, symbol_rows in grouped.items():
            issues = []
            rejected_rows = [row for row in symbol_rows if self._agent_timeline_row_status_label(row) == "Rejected"]
            if len(rejected_rows) >= 2:
                issues.append(f"Repeated risk rejections ({len(rejected_rows)})")

            latest_timestamp = None
            for row in symbol_rows:
                timestamp_value = _runtime_timestamp_seconds((row or {}).get("timestamp"))
                if timestamp_value is None:
                    continue
                latest_timestamp = timestamp_value if latest_timestamp is None else max(latest_timestamp, timestamp_value)
            if latest_timestamp is not None and (now_value - latest_timestamp) > 300.0:
                issues.append("Stale decision flow")

            filled_ids = {
                str((row or {}).get("decision_id") or "").strip()
                for row in symbol_rows
                if str((row or {}).get("event_type") or "").strip().lower() == "order_filled"
            }
            execution_rows = [
                row for row in symbol_rows
                if str((row or {}).get("event_type") or "").strip().lower() == "execution_plan"
            ]
            if execution_rows:
                unmatched = []
                for row in execution_rows:
                    decision_id = str((row or {}).get("decision_id") or "").strip()
                    if decision_id:
                        if decision_id not in filled_ids:
                            unmatched.append(row)
                    elif not filled_ids:
                        unmatched.append(row)
                if unmatched:
                    issues.append("Execution plan without fill")

            if issues:
                anomalies.append({"symbol": symbol, "issues": issues})

        return {
            "count": len(anomalies),
            "symbols": [item["symbol"] for item in anomalies],
            "items": anomalies,
        }

    def agent_timeline_anomaly_fingerprint(self, item):
        if not isinstance(item, dict):
            return ""
        issues = [str(issue or "").strip() for issue in list(item.get("issues", []) or [])]
        issues = [issue for issue in issues if issue]
        return " | ".join(issues)

    def visible_agent_timeline_anomaly_snapshot(self, window, snapshot):
        if not isinstance(snapshot, dict):
            snapshot = {"count": 0, "symbols": [], "items": []}
        items = list(snapshot.get("items", []) or [])
        acknowledged = dict(getattr(window, "_agent_timeline_acknowledged", {}) or {}) if self._is_qt_object_alive(window) else {}
        visible_items = []
        for item in items:
            symbol = str((item or {}).get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/")
            if not symbol:
                continue
            normalized_item = {"symbol": symbol, "issues": list((item or {}).get("issues", []) or [])}
            fingerprint = self._agent_timeline_anomaly_fingerprint(normalized_item)
            if acknowledged.get(symbol) == fingerprint:
                continue
            visible_items.append(normalized_item)
        return {
            "count": len(visible_items),
            "symbols": [item["symbol"] for item in visible_items],
            "items": visible_items,
            "total_count": len(items),
        }

    def refresh_agent_timeline_health(self, window=None, rows=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return

        counts_label = getattr(window, "_agent_timeline_health_counts", None)
        symbols_label = getattr(window, "_agent_timeline_health_symbols", None)
        recent_label = getattr(window, "_agent_timeline_health_recent", None)
        if any(label is None for label in (counts_label, symbols_label, recent_label)):
            return

        snapshot = self._agent_timeline_health_snapshot(rows or [])
        counts_label.setText(
            "Agent Health\n"
            f"Approved: {snapshot['approved']}  |  Rejected: {snapshot['rejected']}  |  Execution: {snapshot['execution']}"
        )
        latest_symbols = ", ".join(snapshot["latest_symbols"]) if snapshot["latest_symbols"] else "No active symbols"
        symbols_label.setText(
            "Visible Symbols\n"
            f"Count: {snapshot['visible_symbol_count']}  |  Latest: {latest_symbols}"
        )
        recent_symbols = ", ".join(snapshot["recent_symbols"]) if snapshot["recent_symbols"] else "No symbols changed"
        recent_label.setText(
            "Last Minute\n"
            f"Changes: {snapshot['recent_count']}  |  {recent_symbols}"
        )

    def refresh_agent_timeline_anomalies(self, window=None, rows=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return

        anomaly_label = getattr(window, "_agent_timeline_anomaly_label", None)
        if anomaly_label is None:
            return

        raw_snapshot = getattr(window, "_agent_timeline_anomaly_snapshot_all", None)
        if not isinstance(raw_snapshot, dict):
            raw_snapshot = self._agent_timeline_anomaly_snapshot(rows or [])
        snapshot = self._visible_agent_timeline_anomaly_snapshot(window, raw_snapshot)
        window._agent_timeline_anomaly_snapshot_all = raw_snapshot
        window._agent_timeline_anomaly_snapshot = snapshot
        if snapshot["count"] <= 0:
            if int(raw_snapshot.get("count", 0) or 0) > 0:
                anomaly_label.setText("Agent Anomalies\nAll current anomalies are acknowledged.")
            else:
                anomaly_label.setText("Agent Anomalies\nNo anomalies detected in the current timeline view.")
            return

        previews = []
        for item in snapshot["items"][:3]:
            previews.append(f"{item['symbol']}: {', '.join(item['issues'])}")
        suffix = f" | +{snapshot['count'] - 3} more" if snapshot["count"] > 3 else ""
        anomaly_label.setText(
            "Agent Anomalies\n"
            f"{snapshot['count']} symbols flagged | {' | '.join(previews)}{suffix}"
        )

    def open_selected_agent_timeline_symbol_in_strategy_assigner(self, window=None):
        return self._replay_selected_agent_timeline_symbol(window)

    def refresh_selected_agent_timeline_symbol(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        symbol = self._selected_agent_timeline_symbol(window)
        if not symbol:
            self._show_async_message("Agent Runtime Monitor", "Select a symbol or event before refreshing it.", QMessageBox.Icon.Warning)
            return ""

        row = self._selected_agent_timeline_row(window)
        timeframe = str((row or {}).get("timeframe") or getattr(self, "current_timeframe", "1h") or "1h").strip() or "1h"
        open_chart = getattr(self, "_open_symbol_chart", None)
        refresh_chart = getattr(self, "_refresh_active_chart_data", None)
        refresh_orderbook = getattr(self, "_refresh_active_orderbook", None)

        invoke_callable(open_chart, symbol, timeframe)
        invoke_callable(refresh_chart)
        invoke_callable(refresh_orderbook)
        return symbol

    def acknowledge_selected_agent_timeline_anomaly(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return ""

        symbol = self._selected_agent_timeline_symbol(window)
        if not symbol:
            self._show_async_message("Agent Runtime Monitor", "Select an anomalous symbol before acknowledging it.", QMessageBox.Icon.Warning)
            return ""

        raw_snapshot = getattr(window, "_agent_timeline_anomaly_snapshot_all", None)
        if not isinstance(raw_snapshot, dict):
            raw_snapshot = self._agent_timeline_anomaly_snapshot(getattr(window, "_agent_timeline_current_rows", []) or [])
        matching_item = next((item for item in list(raw_snapshot.get("items", []) or []) if str(item.get("symbol") or "").strip().upper().replace("-", "/").replace("_", "/") == symbol), None)
        if not isinstance(matching_item, dict):
            self._show_async_message("Agent Runtime Monitor", f"{symbol} does not have an active anomaly in the current view.", QMessageBox.Icon.Information)
            return ""

        acknowledged = dict(getattr(window, "_agent_timeline_acknowledged", {}) or {})
        acknowledged[symbol] = self._agent_timeline_anomaly_fingerprint(matching_item)
        window._agent_timeline_acknowledged = acknowledged
        self._refresh_agent_timeline_window(window)
        return symbol

    def agent_timeline_assignment_text(self, symbol):
        normalized_symbol = str(symbol or "").strip().upper().replace("-", "/").replace("_", "/")
        if not normalized_symbol:
            return "Current Assignment\nSelect a symbol to inspect its active routing."

        controller = getattr(self, "controller", None)
        resolver = getattr(controller, "strategy_assignment_state_for_symbol", None) if controller is not None else None
        state = invoke_callable(resolver, normalized_symbol) if callable(resolver) else {}
        active_rows = list(state.get("active_rows", []) or [])
        mode = str(state.get("mode") or "default").strip().lower() or "default"
        locked = bool(state.get("locked", False))

        if active_rows:
            strategies = ", ".join(
                str(row.get("strategy_name") or "").strip()
                for row in active_rows
                if str(row.get("strategy_name") or "").strip()
            ) or str(getattr(controller, "strategy_name", "Trend Following") or "Trend Following").strip()
            timeframe = str(active_rows[0].get("timeframe") or getattr(controller, "time_frame", "1h") or "1h").strip()
        else:
            strategies = str(getattr(controller, "strategy_name", "Trend Following") or "Trend Following").strip()
            timeframe = str(getattr(controller, "time_frame", "1h") or "1h").strip()

        mode_label = {
            "single": "Single",
            "ranked": "Ranked Mix",
            "default": "Default",
        }.get(mode, mode.title() or "Default")
        return (
            f"Current Assignment\n"
            f"Symbol: {normalized_symbol}\n"
            f"Mode: {mode_label}\n"
            f"Strategy: {strategies}\n"
            f"Timeframe: {timeframe}\n"
            f"Locked: {'Yes' if locked else 'No'}"
        )

    def agent_timeline_recommendation_text(self, symbol):
        normalized_symbol = str(symbol or "").strip().upper().replace("-", "/").replace("_", "/")
        if not normalized_symbol:
            return "Latest Agent Recommendation\nSelect a symbol to inspect the latest decision."

        controller = getattr(self, "controller", None)
        resolver = getattr(controller, "latest_agent_decision_overview_for_symbol", None) if controller is not None else None
        overview = invoke_callable(resolver, normalized_symbol) if callable(resolver) else {}
        if not isinstance(overview, dict) or not overview:
            return (
                f"Latest Agent Recommendation\n"
                f"Symbol: {normalized_symbol}\n"
                f"No recent agent decision has been recorded yet."
            )

        strategy_name = str(overview.get("strategy_name") or "Unknown").strip()
        timeframe = str(overview.get("timeframe") or "-").strip()
        final_agent = str(overview.get("final_agent") or "-").strip()
        final_stage = str(overview.get("final_stage") or "-").strip()
        side = str(overview.get("side") or "").strip().upper() or "-"
        approved = overview.get("approved")
        approval_text = "Approved" if approved is True else "Rejected" if approved is False else "Pending"
        reason = str(overview.get("reason") or "").strip() or "No explanation recorded."
        return (
            f"Latest Agent Recommendation\n"
            f"Symbol: {normalized_symbol}\n"
            f"Strategy: {strategy_name}\n"
            f"Timeframe: {timeframe}\n"
            f"Side: {side}\n"
            f"Status: {approval_text} via {final_agent} / {final_stage}\n"
            f"Reason: {reason}"
        )

    def refresh_agent_timeline_details(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        if not self._is_qt_object_alive(window):
            return
        assigned_label = getattr(window, "_agent_timeline_assignment_label", None)
        recommendation_label = getattr(window, "_agent_timeline_recommendation_label", None)
        detail_browser = getattr(window, "_agent_timeline_detail_browser", None)
        if assigned_label is None or recommendation_label is None or detail_browser is None:
            return

        symbol = self._selected_agent_timeline_symbol(window)
        assigned_label.setText(self._agent_timeline_assignment_text(symbol))
        recommendation_label.setText(self._agent_timeline_recommendation_text(symbol))
        anomaly_snapshot = dict(getattr(window, "_agent_timeline_anomaly_snapshot", {}) or {})
        anomaly_map = {item["symbol"]: list(item["issues"]) for item in anomaly_snapshot.get("items", [])}

        row = self._selected_agent_timeline_row(window)
        if not row:
            detail_browser.setPlainText("Select a symbol or event to inspect the live agent payload.")
            return

        payload = row.get("payload")
        pretty_payload = json.dumps(payload, indent=2, sort_keys=True, default=str) if isinstance(payload, dict) else str(payload or "")
        votes = dict(row.get("votes") or {}) if isinstance(row.get("votes"), dict) else {}
        features = dict(row.get("features") or {}) if isinstance(row.get("features"), dict) else {}
        metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
        constraints = ", ".join(str(item or "").strip() for item in list(row.get("applied_constraints", []) or []) if str(item or "").strip())
        vote_lines = [f"  {key}: {value:.2f}" if isinstance(value, (int, float)) else f"  {key}: {value}" for key, value in votes.items()]
        feature_lines = [f"  {key}: {value:.6f}" if isinstance(value, (int, float)) else f"  {key}: {value}" for key, value in features.items()]
        metadata_text = json.dumps(metadata, indent=2, sort_keys=True, default=str) if metadata else "{}"
        detail_lines = [
            f"Symbol: {str(row.get('symbol') or symbol or '').strip()}",
            f"Kind: {str(row.get('kind') or '').strip()}",
            f"Agent/Event: {str(row.get('agent_name') or row.get('event_type') or '').strip()}",
            f"Stage: {str(row.get('stage') or row.get('action') or '').strip()}",
            f"Strategy: {str(row.get('strategy_name') or '').strip()}",
            f"Timeframe: {str(row.get('timeframe') or '').strip()}",
            f"Decision ID: {str(row.get('decision_id') or '').strip()}",
            f"Timestamp: {str(row.get('timestamp_label') or '').strip()}",
            f"Message: {str(row.get('message') or row.get('reason') or '').strip()}",
        ]
        trader_fields = []
        if str(row.get("profile_id") or "").strip():
            trader_fields.append(f"Profile: {str(row.get('profile_id') or '').strip()}")
        if str(row.get("action") or "").strip():
            trader_fields.append(f"Action: {str(row.get('action') or '').strip().upper()}")
        if row.get("confidence") not in (None, ""):
            trader_fields.append(f"Confidence: {format_compact_number(row.get('confidence'))}")
        if row.get("model_probability") not in (None, ""):
            trader_fields.append(f"Model Probability: {format_compact_number(row.get('model_probability'))}")
        if row.get("quantity") not in (None, ""):
            trader_fields.append(f"Quantity: {format_compact_number(row.get('quantity'))}")
        if row.get("price") not in (None, ""):
            trader_fields.append(f"Price: {format_compact_number(row.get('price'))}")
        if constraints:
            trader_fields.append(f"Constraints: {constraints}")
        if trader_fields:
            detail_lines.extend(trader_fields)
        if symbol and symbol in anomaly_map:
            detail_lines.append(f"Anomalies: {', '.join(anomaly_map[symbol])}")
        if vote_lines:
            detail_lines.extend(["", "Votes:", "\n".join(vote_lines)])
        if feature_lines:
            detail_lines.extend(["", "Features:", "\n".join(feature_lines)])
        if metadata:
            detail_lines.extend(["", "Metadata:", metadata_text])
        detail_lines.extend(
            [
                "",
                "Payload:",
                pretty_payload or "{}",
            ]
        )
        detail_browser.setPlainText("\n".join(detail_lines).strip())

    def replay_selected_agent_timeline_symbol(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("agent_timeline")
        symbol = self._selected_agent_timeline_symbol(window)
        if not symbol:
            self._show_async_message("Agent Runtime Monitor", "Select a symbol or event before replaying its latest chain.", QMessageBox.Icon.Warning)
            return None

        opener = getattr(self, "_open_strategy_assignment_window", None)
        refresher = getattr(self, "_refresh_strategy_assignment_window", None)
        if not callable(opener):
            return None
        strategy_window = invoke_callable(opener)
        if strategy_window is None:
            return None

        strategy_window._strategy_assignment_selected_symbol = symbol
        picker = getattr(strategy_window, "_strategy_assignment_symbol_picker", None)
        if picker is not None:
            blocked = picker.blockSignals(True)
            if picker.findText(symbol) < 0:
                picker.addItem(symbol)
            picker.setCurrentText(symbol)
            picker.blockSignals(blocked)
        invoke_callable(refresher, strategy_window, message=f"Replaying the latest agent chain for {symbol}.")
        return strategy_window

    def open_agent_timeline(self):
        window = self._get_or_create_tool_window("agent_timeline", "Agent Runtime Monitor", width=1120, height=620)
        if getattr(window, "_agent_timeline_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            summary = QLabel("Watch agent runtime health across symbols, from signal selection through risk and execution.")
            summary.setWordWrap(True)
            summary.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; padding: 10px;")
            layout.addWidget(summary)
            controls = QHBoxLayout()
            filter_input = QLineEdit()
            filter_input.setPlaceholderText("Filter by symbol, agent, event, strategy, timeframe, or message")
            filter_input.textChanged.connect(lambda *_: self._refresh_agent_timeline_window(window))
            controls.addWidget(filter_input, 1)
            status_filter = QComboBox()
            status_filter.addItem("All Statuses")
            status_filter.currentTextChanged.connect(lambda *_: self._refresh_agent_timeline_window(window))
            controls.addWidget(status_filter)
            timeframe_filter = QComboBox()
            timeframe_filter.addItem("All Timeframes")
            timeframe_filter.currentTextChanged.connect(lambda *_: self._refresh_agent_timeline_window(window))
            controls.addWidget(timeframe_filter)
            strategy_filter = QComboBox()
            strategy_filter.addItem("All Strategies")
            strategy_filter.currentTextChanged.connect(lambda *_: self._refresh_agent_timeline_window(window))
            controls.addWidget(strategy_filter)
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(lambda: self._refresh_agent_timeline_window(window))
            controls.addWidget(refresh_btn)
            clear_filters_btn = QPushButton("Clear Filters")
            clear_filters_btn.clicked.connect(
                lambda: (
                    filter_input.clear(),
                    status_filter.setCurrentIndex(0),
                    timeframe_filter.setCurrentIndex(0),
                    strategy_filter.setCurrentIndex(0),
                    setattr(window, "_agent_timeline_pinned_symbol", ""),
                    self._refresh_agent_timeline_window(window),
                )
            )
            controls.addWidget(clear_filters_btn)
            pin_btn = QPushButton("Pin Selected Symbol")
            pin_btn.clicked.connect(lambda: self._toggle_agent_timeline_pin_symbol(window))
            controls.addWidget(pin_btn)
            expand_btn = QPushButton("Expand All")
            expand_btn.clicked.connect(lambda: getattr(window, "_agent_timeline_tree", None).expandAll() if getattr(window, "_agent_timeline_tree", None) is not None else None)
            controls.addWidget(expand_btn)
            collapse_btn = QPushButton("Collapse All")
            collapse_btn.clicked.connect(lambda: getattr(window, "_agent_timeline_tree", None).collapseAll() if getattr(window, "_agent_timeline_tree", None) is not None else None)
            controls.addWidget(collapse_btn)
            replay_btn = QPushButton("Replay Latest Chain")
            replay_btn.clicked.connect(lambda: self._replay_selected_agent_timeline_symbol(window))
            controls.addWidget(replay_btn)
            layout.addLayout(controls)
            health_row = QHBoxLayout()
            health_counts = QLabel("Agent Health\nApproved: 0  |  Rejected: 0  |  Execution: 0")
            health_counts.setWordWrap(True)
            health_counts.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 10px; padding: 10px;")
            health_row.addWidget(health_counts, 1)
            health_symbols = QLabel("Visible Symbols\nCount: 0  |  Latest: No active symbols")
            health_symbols.setWordWrap(True)
            health_symbols.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 10px; padding: 10px;")
            health_row.addWidget(health_symbols, 1)
            health_recent = QLabel("Last Minute\nChanges: 0  |  No symbols changed")
            health_recent.setWordWrap(True)
            health_recent.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 10px; padding: 10px;")
            health_row.addWidget(health_recent, 1)
            layout.addLayout(health_row)
            anomaly_label = QLabel("Agent Anomalies\nNo anomalies detected in the current timeline view.")
            anomaly_label.setWordWrap(True)
            anomaly_label.setStyleSheet("color: #ffd166; background-color: #101a2d; border: 1px solid #5a4316; border-radius: 10px; padding: 10px;")
            layout.addWidget(anomaly_label)
            anomaly_controls = QHBoxLayout()
            open_assigner_btn = QPushButton("Open Strategy Assigner")
            open_assigner_btn.clicked.connect(lambda: self._open_selected_agent_timeline_symbol_in_strategy_assigner(window))
            anomaly_controls.addWidget(open_assigner_btn)
            refresh_symbol_btn = QPushButton("Refresh Symbol")
            refresh_symbol_btn.clicked.connect(lambda: self._refresh_selected_agent_timeline_symbol(window))
            anomaly_controls.addWidget(refresh_symbol_btn)
            acknowledge_btn = QPushButton("Acknowledge Anomaly")
            acknowledge_btn.clicked.connect(lambda: self._acknowledge_selected_agent_timeline_anomaly(window))
            anomaly_controls.addWidget(acknowledge_btn)
            anomaly_controls.addStretch(1)
            layout.addLayout(anomaly_controls)
            tree = QTreeWidget()
            tree.setColumnCount(8)
            tree.setHeaderLabels(["Time", "Kind", "Symbol", "Agent / Event", "Stage", "Strategy", "Timeframe", "Details"])
            tree.setRootIsDecorated(True)
            tree.setUniformRowHeights(True)
            tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            tree.itemSelectionChanged.connect(lambda: self._refresh_agent_timeline_details(window))
            tree.itemDoubleClicked.connect(lambda *_: self._replay_selected_agent_timeline_symbol(window))
            layout.addWidget(tree, 1)
            comparison_row = QHBoxLayout()
            assigned_label = QLabel("Current Assignment\nSelect a symbol to inspect its active routing.")
            assigned_label.setWordWrap(True)
            assigned_label.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 10px; padding: 10px;")
            comparison_row.addWidget(assigned_label, 1)
            recommendation_label = QLabel("Latest Agent Recommendation\nSelect a symbol to inspect the latest decision.")
            recommendation_label.setWordWrap(True)
            recommendation_label.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 10px; padding: 10px;")
            comparison_row.addWidget(recommendation_label, 1)
            layout.addLayout(comparison_row)
            detail_browser = QTextBrowser()
            detail_browser.setMinimumHeight(180)
            detail_browser.setStyleSheet("background-color: #0f1726; color: #d9e6f7; border: 1px solid #20324d; border-radius: 10px;")
            detail_browser.setPlainText("Select a symbol or event to inspect the live agent payload.")
            layout.addWidget(detail_browser)
            window.setCentralWidget(container)
            window._agent_timeline_container = container
            window._agent_timeline_summary = summary
            window._agent_timeline_filter = filter_input
            window._agent_timeline_status_filter = status_filter
            window._agent_timeline_timeframe_filter = timeframe_filter
            window._agent_timeline_strategy_filter = strategy_filter
            window._agent_timeline_health_counts = health_counts
            window._agent_timeline_health_symbols = health_symbols
            window._agent_timeline_health_recent = health_recent
            window._agent_timeline_anomaly_label = anomaly_label
            window._agent_timeline_anomaly_snapshot = {}
            window._agent_timeline_anomaly_snapshot_all = {}
            window._agent_timeline_acknowledged = {}
            window._agent_timeline_tree = tree
            window._agent_timeline_pinned_symbol = ""
            window._agent_timeline_clear_filters_btn = clear_filters_btn
            window._agent_timeline_pin_btn = pin_btn
            window._agent_timeline_open_assigner_btn = open_assigner_btn
            window._agent_timeline_refresh_symbol_btn = refresh_symbol_btn
            window._agent_timeline_acknowledge_btn = acknowledge_btn
            window._agent_timeline_assignment_label = assigned_label
            window._agent_timeline_recommendation_label = recommendation_label
            window._agent_timeline_detail_browser = detail_browser
            window._agent_timeline_expand_btn = expand_btn
            window._agent_timeline_collapse_btn = collapse_btn
            window._agent_timeline_replay_btn = replay_btn
        self._refresh_agent_timeline_window(window)
        window.show()
        window.raise_()
        window.activateWindow()
        if getattr(window, "_agent_timeline_filter", None) is not None:
            window._agent_timeline_filter.setFocus()
        return window

    def trader_agent_monitor_rows(self, limit=300):
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "live_agent_runtime_feed"):
            return []
        rows = list(controller.live_agent_runtime_feed(limit=limit) or [])
        decision_rows = []
        for row in rows:
            payload = dict((row or {}).get("payload") or {}) if isinstance((row or {}).get("payload"), dict) else {}
            event_type = str((row or {}).get("event_type") or "").strip().upper()
            agent_name = str((row or {}).get("agent_name") or "").strip().lower()
            if event_type != "DECISION_EVENT" and agent_name != "traderagent" and not str(payload.get("profile_id") or "").strip():
                continue
            decision_rows.append(dict(row))
        return decision_rows

    def selected_trader_agent_monitor_row(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("trader_agent_monitor")
        if not self._is_qt_object_alive(window):
            return {}
        tree = getattr(window, "_trader_agent_monitor_tree", None)
        if tree is None:
            return {}
        item = tree.currentItem()
        if item is None:
            return {}
        raw = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not raw and item.parent() is not None:
            raw = item.parent().data(0, Qt.ItemDataRole.UserRole + 1)
        if not raw:
            return {}
        try:
            payload = json.loads(str(raw))
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def populate_trader_agent_monitor_filters(self, window, rows):
        if not self._is_qt_object_alive(window):
            return
        profile_combo = getattr(window, "_trader_agent_monitor_profile_filter", None)
        action_combo = getattr(window, "_trader_agent_monitor_action_filter", None)
        strategy_combo = getattr(window, "_trader_agent_monitor_strategy_filter", None)
        if any(combo is None for combo in (profile_combo, action_combo, strategy_combo)):
            return

        def refill(combo, default_label, values):
            current = str(combo.currentText() or "").strip()
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItem(default_label)
            for value in values:
                combo.addItem(value)
            if current and combo.findText(current) >= 0:
                combo.setCurrentText(current)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(blocked)

        refill(
            profile_combo,
            "All Profiles",
            sorted({str((row or {}).get("profile_id") or "").strip() for row in rows if str((row or {}).get("profile_id") or "").strip()}),
        )
        refill(
            action_combo,
            "All Actions",
            sorted({str((row or {}).get("action") or "").strip().upper() for row in rows if str((row or {}).get("action") or "").strip()}),
        )
        refill(
            strategy_combo,
            "All Strategies",
            sorted({str((row or {}).get("strategy_name") or "").strip() for row in rows if str((row or {}).get("strategy_name") or "").strip()}),
        )

    def refresh_trader_agent_monitor_details(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("trader_agent_monitor")
        if not self._is_qt_object_alive(window):
            return
        detail_browser = getattr(window, "_trader_agent_monitor_detail_browser", None)
        if detail_browser is None:
            return

        row = self._selected_trader_agent_monitor_row(window)
        if not row:
            detail_browser.setPlainText("Select a TraderAgent decision to inspect its live reasoning and payload.")
            return

        constraints = ", ".join(str(item or "").strip() for item in list(row.get("applied_constraints", []) or []) if str(item or "").strip()) or "None"
        votes = dict(row.get("votes") or {}) if isinstance(row.get("votes"), dict) else {}
        features = dict(row.get("features") or {}) if isinstance(row.get("features"), dict) else {}
        metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
        payload = row.get("payload")
        pretty_payload = json.dumps(payload, indent=2, sort_keys=True, default=str) if isinstance(payload, dict) else str(payload or "")
        vote_lines = [f"  {key}: {value:.2f}" if isinstance(value, (int, float)) else f"  {key}: {value}" for key, value in votes.items()]
        feature_lines = [f"  {key}: {value:.6f}" if isinstance(value, (int, float)) else f"  {key}: {value}" for key, value in features.items()]
        metadata_text = json.dumps(metadata, indent=2, sort_keys=True, default=str) if metadata else "{}"
        detail_lines = [
            f"Profile: {str(row.get('profile_id') or '').strip() or '-'}",
            f"Symbol: {str(row.get('symbol') or '').strip() or '-'}",
            f"Action: {str(row.get('action') or '').strip().upper() or '-'}",
            f"Strategy: {str(row.get('strategy_name') or '').strip() or '-'}",
            f"Confidence: {format_compact_number(row.get('confidence'))}",
            f"Model Probability: {format_compact_number(row.get('model_probability'))}",
            f"Quantity: {format_compact_number(row.get('quantity'))}",
            f"Price: {format_compact_number(row.get('price'))}",
            f"Timestamp: {str(row.get('timestamp_label') or '').strip() or '-'}",
            f"Constraints: {constraints}",
            "",
            "Reasoning:",
            str(row.get("reason") or row.get("message") or "No reasoning recorded.").strip(),
            "",
            "Votes:",
            "\n".join(vote_lines) if vote_lines else "  None",
            "",
            "Features:",
            "\n".join(feature_lines) if feature_lines else "  None",
            "",
            "Metadata:",
            metadata_text,
            "",
            "Payload:",
            pretty_payload or "{}",
        ]
        detail_browser.setPlainText("\n".join(detail_lines).strip())

    def refresh_trader_agent_monitor_window(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("trader_agent_monitor")
        if not self._is_qt_object_alive(window):
            return
        tree = getattr(window, "_trader_agent_monitor_tree", None)
        filter_input = getattr(window, "_trader_agent_monitor_filter", None)
        profile_filter = getattr(window, "_trader_agent_monitor_profile_filter", None)
        action_filter = getattr(window, "_trader_agent_monitor_action_filter", None)
        strategy_filter = getattr(window, "_trader_agent_monitor_strategy_filter", None)
        summary = getattr(window, "_trader_agent_monitor_summary", None)
        score_label = getattr(window, "_trader_agent_monitor_score_label", None)
        profile_label = getattr(window, "_trader_agent_monitor_profile_label", None)
        if any(widget is None for widget in (tree, filter_input, profile_filter, action_filter, strategy_filter, summary, score_label, profile_label)):
            return

        rows = self._trader_agent_monitor_rows(limit=400)
        self._populate_trader_agent_monitor_filters(window, rows)

        selected_profile = str(profile_filter.currentText() or "").strip()
        if selected_profile and selected_profile != "All Profiles":
            rows = [row for row in rows if str((row or {}).get("profile_id") or "").strip() == selected_profile]

        selected_action_label = str(action_filter.currentText() or "").strip()
        if selected_action_label and selected_action_label != "All Actions":
            selected_action = selected_action_label.upper()
            rows = [row for row in rows if str((row or {}).get("action") or "").strip().upper() == selected_action]
        else:
            selected_action = ""

        selected_strategy = str(strategy_filter.currentText() or "").strip()
        if selected_strategy and selected_strategy != "All Strategies":
            rows = [row for row in rows if str((row or {}).get("strategy_name") or "").strip() == selected_strategy]

        query = str(filter_input.text() or "").strip().lower()
        if query:
            filtered = []
            for row in rows:
                haystack = " ".join(
                    str(row.get(key) or "")
                    for key in (
                        "timestamp_label",
                        "profile_id",
                        "symbol",
                        "action",
                        "strategy_name",
                        "reason",
                        "message",
                    )
                ).lower()
                if query in haystack:
                    filtered.append(row)
            rows = filtered

        tree.clear()
        grouped_rows = {}
        ordered_groups = []
        action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0, "SKIP": 0}
        visible_profiles = []
        visible_symbols = []
        confidence_values = []
        action_colors = {
            "BUY": QColor("#4ade80"),
            "SELL": QColor("#f97316"),
            "HOLD": QColor("#74c0fc"),
            "SKIP": QColor("#94a3b8"),
        }

        for row in rows:
            profile_id = str(row.get("profile_id") or "default").strip() or "default"
            symbol = str(row.get("symbol") or "Unknown").strip() or "Unknown"
            group_key = f"{profile_id}::{symbol}"
            if group_key not in grouped_rows:
                grouped_rows[group_key] = []
                ordered_groups.append(group_key)
            grouped_rows[group_key].append(dict(row))
            if profile_id not in visible_profiles:
                visible_profiles.append(profile_id)
            if symbol not in visible_symbols:
                visible_symbols.append(symbol)
            action = str(row.get("action") or "").strip().upper()
            if action in action_counts:
                action_counts[action] += 1
            try:
                confidence_values.append(float(row.get("confidence")))
            except Exception:
                pass

        top_level_to_select = None
        selected_row = self._selected_trader_agent_monitor_row(window)
        selected_fingerprint = json.dumps(selected_row, sort_keys=True, default=str) if selected_row else ""
        for group_key in ordered_groups:
            group_rows = grouped_rows.get(group_key, [])
            latest = group_rows[0] if group_rows else {}
            profile_id = str(latest.get("profile_id") or "default").strip() or "default"
            symbol = str(latest.get("symbol") or "Unknown").strip() or "Unknown"
            latest_action = str(latest.get("action") or "").strip().upper()
            latest_reason = str(latest.get("reason") or latest.get("message") or "").strip()
            confidence_text = format_compact_number(latest.get("confidence"))
            model_text = format_compact_number(latest.get("model_probability"))
            group_item = QTreeWidgetItem(
                [
                    str(latest.get("timestamp_label") or "-"),
                    profile_id,
                    symbol,
                    latest_action or f"{len(group_rows)} decisions",
                    str(latest.get("strategy_name") or "").strip(),
                    confidence_text,
                    model_text,
                    latest_reason,
                ]
            )
            group_item.setData(0, Qt.ItemDataRole.UserRole + 1, json.dumps(latest, default=str))
            tree.addTopLevelItem(group_item)
            for column in range(8):
                if latest_action in action_colors:
                    group_item.setForeground(column, action_colors[latest_action])

            for row in group_rows:
                action = str(row.get("action") or "").strip().upper()
                reason = str(row.get("reason") or row.get("message") or "").strip()
                child = QTreeWidgetItem(
                    [
                        str(row.get("timestamp_label") or "-"),
                        str(row.get("profile_id") or "").strip(),
                        str(row.get("symbol") or "").strip(),
                        action,
                        str(row.get("strategy_name") or "").strip(),
                        format_compact_number(row.get("confidence")),
                        format_compact_number(row.get("model_probability")),
                        reason,
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole + 1, json.dumps(row, default=str))
                child.setToolTip(7, reason)
                if action in action_colors:
                    for column in range(8):
                        child.setForeground(column, action_colors[action])
                group_item.addChild(child)
                if selected_fingerprint and json.dumps(row, sort_keys=True, default=str) == selected_fingerprint:
                    top_level_to_select = child
            group_item.setExpanded(True)

        for column in range(7):
            tree.resizeColumnToContents(column)
        if top_level_to_select is not None:
            tree.setCurrentItem(top_level_to_select)
        elif tree.topLevelItemCount() > 0:
            first_group = tree.topLevelItem(0)
            tree.setCurrentItem(first_group.child(0) or first_group)

        average_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        active_filters = []
        if selected_profile and selected_profile != "All Profiles":
            active_filters.append(selected_profile)
        if selected_action_label and selected_action_label != "All Actions":
            active_filters.append(selected_action)
        if selected_strategy and selected_strategy != "All Strategies":
            active_filters.append(selected_strategy)
        suffix = f" | Filters: {', '.join(active_filters)}" if active_filters else ""
        summary.setText(
            f"{len(rows)} TraderAgent decisions across {len(visible_symbols)} symbols and {len(visible_profiles)} profiles.{suffix}"
        )
        score_label.setText(
            "Action Mix\n"
            f"BUY: {action_counts['BUY']}  |  SELL: {action_counts['SELL']}  |  HOLD: {action_counts['HOLD']}  |  SKIP: {action_counts['SKIP']}"
        )
        profile_label.setText(
            "Profile Coverage\n"
            f"Profiles: {', '.join(visible_profiles[:4]) if visible_profiles else 'No active profiles'}\n"
            f"Avg confidence: {average_confidence:.2f}"
        )
        window._trader_agent_monitor_current_rows = [dict(row) for row in rows]
        self._refresh_trader_agent_monitor_details(window)

    def open_trader_agent_monitor(self):
        legacy_window = (getattr(self, "detached_tool_windows", {}) or {}).get("trader_agent_monitor")
        if self._is_qt_object_alive(legacy_window):
            try:
                legacy_window.hide()
            except Exception:
                pass
        return invoke_callable(getattr(self, "_open_agent_timeline", None))

    def record_trade_notification(self, trade):
        if not isinstance(trade, dict):
            return None
        symbol = str(trade.get("symbol") or "").strip() or "Unknown symbol"
        status = str(trade.get("status") or "").strip().lower()
        side = str(trade.get("side") or "").strip().upper() or "TRADE"
        size = trade.get("size", trade.get("amount", "-"))
        price = trade.get("price", trade.get("mark", "-"))
        reason_text = " ".join(str(trade.get(key) or "") for key in ("reason", "outcome", "status", "source")).lower()
        pnl = self._safe_float(trade.get("pnl"))
        details = f"{symbol} | {side} | size {size} | price {price}"
        if pnl is not None:
            details += f" | PnL {pnl:.2f}"
        if "stop" in reason_text:
            return self._push_notification("Stop hit", details, level="WARN", source="trade", dedupe_seconds=10.0)
        if any(token in status for token in ("reject", "fail", "error")) or trade.get("blocked_by_guard"):
            return self._push_notification("Order rejected", details, level="ERROR", source="trade", dedupe_seconds=10.0)
        if any(token in status for token in ("fill", "executed", "closed")):
            return self._push_notification("Order filled", details, level="INFO", source="trade", dedupe_seconds=10.0)
        return None

    def runtime_notification_transition(self, key, fingerprint, title, message, level="WARN", source="runtime"):
        state = getattr(self, "_runtime_notification_state", None)
        if not isinstance(state, dict):
            state = {}
            self._runtime_notification_state = state
        if fingerprint in (None, "", False):
            state.pop(key, None)
            return
        if state.get(key) != fingerprint:
            state[key] = fingerprint
            self._push_notification(title, message, level=level, source=source, dedupe_seconds=30.0)

    def refresh_runtime_notifications(self):
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        broker_snapshot = dict(getattr(self, "_latest_broker_status_snapshot", {}) or {})
        broker_summary = str(broker_snapshot.get("summary") or "").strip()
        broker_detail = str(broker_snapshot.get("detail") or "").strip()
        broker_text = f"{broker_summary} {broker_detail}".lower()
        fingerprint = None
        if broker_text and any(token in broker_text for token in ("disconnect", "offline", "fail", "error", "unauthorized", "denied")):
            fingerprint = f"{broker_summary}|{broker_detail}"
        self._runtime_notification_transition(
            "broker_api",
            fingerprint,
            "API disconnected",
            broker_detail or broker_summary or "The broker API is unavailable.",
            level="ERROR",
            source="broker",
        )
        notices = getattr(controller, "_market_data_shortfall_notices", {}) or {}
        stale_fingerprint = None
        stale_message = ""
        if isinstance(notices, dict) and notices:
            try:
                (symbol, timeframe), (received, requested) = next(iter(notices.items()))
                stale_fingerprint = f"{symbol}|{timeframe}|{received}|{requested}"
                stale_message = f"{symbol} {timeframe}: received {received} of {requested} requested candles."
            except Exception:
                stale_fingerprint = f"{len(notices)}-shortfalls"
                stale_message = "Recent candle history is incomplete for one or more symbols."
        else:
            market_status = ""
            if hasattr(controller, "get_market_stream_status"):
                try:
                    market_status = str(controller.get_market_stream_status() or "")
                except Exception:
                    market_status = ""
            if market_status.strip().lower() == "stopped":
                stale_fingerprint = "stream-stopped"
                stale_message = "Live market data is currently stopped."
        self._runtime_notification_transition(
            "stale_market_data",
            stale_fingerprint,
            "Stale market data",
            stale_message,
            level="WARN",
            source="market-data",
        )
        behavior = {}
        if hasattr(controller, "get_behavior_guard_status"):
            try:
                behavior = controller.get_behavior_guard_status() or {}
            except Exception:
                behavior = {}
        summary = str(behavior.get("summary") or "").strip()
        reason = str(behavior.get("reason") or "").strip()
        behavior_fingerprint = None
        if summary and summary.lower() not in {"not active", "inactive", "disabled", "off"}:
            behavior_fingerprint = f"{summary}|{reason}"
        self._runtime_notification_transition(
            "behavior_guard",
            behavior_fingerprint,
            "Behavior guard active",
            reason or summary or "The behavior guard is actively constraining trading behavior.",
            level="WARN",
            source="risk",
        )

    def visible_tool_window_keys(self):
        visible = set()
        for key, window in (getattr(self, "detached_tool_windows", {}) or {}).items():
            canonical_key = self._canonical_tool_window_key(key)
            if not canonical_key or not self._is_qt_object_alive(window):
                continue
            try:
                if window.isVisible():
                    visible.add(canonical_key)
            except Exception:
                continue
        return sorted(visible)

    def canonical_tool_window_key(self, key):
        normalized = str(key or "").strip().lower()
        return TOOL_WINDOW_ALIASES.get(normalized, "")

    def save_workspace_layout(self, slot="last"):
        settings = getattr(self, "settings", None)
        if settings is None:
            return False
        prefix = self._workspace_settings_prefix(slot)
        settings.setValue(f"{prefix}/geometry", self.saveGeometry())
        settings.setValue(f"{prefix}/windowState", self.saveState())
        visible_docks = []
        for attr_name in WORKSPACE_DOCKS:
            dock = getattr(self, attr_name, None)
            if self._is_qt_object_alive(dock) and dock.isVisible():
                visible_docks.append(attr_name)
        settings.setValue(f"{prefix}/visible_docks", json.dumps(sorted(visible_docks)))
        settings.setValue(f"{prefix}/open_tools", json.dumps(self._visible_tool_window_keys()))
        return True

    def restore_workspace_layout(self, slot="last"):
        settings = getattr(self, "settings", None)
        if settings is None:
            return False
        prefix = self._workspace_settings_prefix(slot)
        geometry = settings.value(f"{prefix}/geometry")
        state = settings.value(f"{prefix}/windowState")
        visible_docks_raw = settings.value(f"{prefix}/visible_docks", "")
        open_tools_raw = settings.value(f"{prefix}/open_tools", "")
        if all(value in (None, "") for value in (geometry, state, visible_docks_raw, open_tools_raw)):
            return False
        if geometry not in (None, ""):
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        if state not in (None, ""):
            try:
                self.restoreState(state)
            except Exception:
                pass
        try:
            visible_docks = set(json.loads(visible_docks_raw or "[]"))
        except Exception:
            visible_docks = set()
        if visible_docks:
            expanded_visible_docks = set(visible_docks)
            for alias_group in SHARED_DOCK_ALIAS_GROUPS:
                if expanded_visible_docks.intersection(alias_group):
                    expanded_visible_docks.update(alias_group)

            grouped_docks = {}
            for attr_name in WORKSPACE_DOCKS:
                dock = getattr(self, attr_name, None)
                if not self._is_qt_object_alive(dock):
                    continue
                grouped_docks.setdefault(id(dock), {"dock": dock, "aliases": set()})["aliases"].add(attr_name)

            for group in grouped_docks.values():
                dock = group["dock"]
                aliases = group["aliases"]
                dock.show() if expanded_visible_docks.intersection(aliases) else dock.hide()
        try:
            open_tools = {
                canonical
                for canonical in (
                    self._canonical_tool_window_key(key)
                    for key in json.loads(open_tools_raw or "[]")
                )
                if canonical
            }
        except Exception:
            open_tools = set()
        for key in open_tools:
            self._open_tool_window_by_key(key)
        for key, window in list((getattr(self, "detached_tool_windows", {}) or {}).items()):
            canonical_key = self._canonical_tool_window_key(key)
            if canonical_key and canonical_key not in open_tools and self._is_qt_object_alive(window):
                try:
                    window.hide()
                except Exception:
                    pass
        normalize_workspace = getattr(self, "_normalize_workspace_sidebar_docks", None)
        if callable(normalize_workspace):
            normalize_workspace()
        self._queue_terminal_layout_fit()
        self._refresh_symbol_picker_favorites()
        self._update_favorite_action_text()
        return True

    def save_current_workspace_layout(self):
        saved = self._save_workspace_layout("saved")
        if hasattr(self, "system_console"):
            self.system_console.log("Workspace layout saved for the current broker/account." if saved else "Workspace layout could not be saved.", "INFO" if saved else "WARN")
        return saved

    def restore_saved_workspace_layout(self):
        restored = self._restore_workspace_layout("saved")
        if hasattr(self, "system_console"):
            self.system_console.log("Saved workspace layout restored." if restored else "No saved workspace layout was found for this broker/account.", "INFO" if restored else "WARN")
        return restored

    def open_tool_window_by_key(self, key):
        requested_key = str(key or "").strip().lower()
        canonical_key = self._canonical_tool_window_key(requested_key)
        if not canonical_key:
            return None
        actions = {
            "performance_analytics": lambda: invoke_callable(getattr(self, "_open_performance", None)),
            "closed_trade_journal": lambda: invoke_callable(getattr(self, "_open_closed_journal_window", None)),
            "trade_journal_review": lambda: invoke_callable(getattr(self, "_open_trade_journal_review_window", None)),
            "portfolio_exposure": lambda: invoke_callable(getattr(self, "_show_portfolio_exposure", None)),
            "position_analysis": lambda: invoke_callable(getattr(self, "_open_position_analysis_window", None)),
            "trade_recommendations": lambda: invoke_callable(getattr(self, "_open_recommendations_window", None)),
            "quant_pm": lambda: invoke_callable(getattr(self, "_open_quant_pm_window", None)),
            "system_health": lambda: invoke_callable(getattr(self, "_open_system_health_window", None)),
            "trade_checklist": lambda: invoke_callable(getattr(self, "_open_trade_checklist_window", None)),
            "market_chat": lambda: invoke_callable(getattr(self, "_open_market_chat_window", None)),
            "ml_monitor": lambda: invoke_callable(getattr(self, "_open_ml_monitor", None)),
            "logs": lambda: invoke_callable(getattr(self, "_open_logs", None)),
            "notification_center": lambda: invoke_callable(getattr(self, "_open_notification_center", None)),
            "agent_timeline": lambda: invoke_callable(getattr(self, "_open_agent_timeline", None)),
            "trader_agent_monitor": lambda: invoke_callable(getattr(self, "_open_trader_agent_monitor", None)),
            "symbol_universe": lambda: invoke_callable(getattr(self, "_open_symbol_universe", None)),
            "manual_trade_ticket": lambda: invoke_callable(getattr(self, "_open_manual_trade", None)),
            "application_settings": lambda: invoke_callable(getattr(self, "_show_settings_window", None)),
            "strategy_optimization": lambda: invoke_callable(getattr(self, "_optimize_strategy", None)),
            "backtesting_workspace": lambda: invoke_callable(getattr(self, "_show_backtest_window", None)),
            "strategy_assignments": lambda: invoke_callable(getattr(self, "_open_strategy_assignment_window", None)),
            "stellar_asset_explorer": lambda: invoke_callable(getattr(self, "_open_stellar_asset_explorer_window", None)),
            "trade_review": lambda: invoke_callable(getattr(self, "_open_trade_review_window", None), {}),
            "education_trader_tv": lambda: invoke_callable(getattr(self, "_open_trader_tv_window", None)),
            "help_documentation": lambda: invoke_callable(getattr(self, "_open_docs", None)),
            "api_reference": lambda: invoke_callable(getattr(self, "_open_api_docs", None)),
            "ml_research_lab": lambda: invoke_callable(getattr(self, "_open_ml_research_window", None)),
        }
        alias_actions = {
            "risk_settings": lambda: invoke_callable(getattr(self, "_open_risk_settings", None)),
        }
        handler = alias_actions.get(requested_key) or actions.get(canonical_key)
        return invoke_callable(handler)

    def apply_workspace_preset(self, name):
        preset_name = str(name or "trading").strip().lower() or "trading"
        preset = WORKSPACE_PRESETS.get(preset_name, WORKSPACE_PRESETS["trading"])
        visible_docks = set(preset.get("docks", set()) or set())
        open_tools = list(preset.get("tools", []) or [])
        for attr_name in WORKSPACE_DOCKS:
            dock = getattr(self, attr_name, None)
            if not self._is_qt_object_alive(dock):
                continue
            dock.show() if attr_name in visible_docks else dock.hide()
        for key, window in list((getattr(self, "detached_tool_windows", {}) or {}).items()):
            canonical_key = self._canonical_tool_window_key(key)
            if canonical_key and canonical_key not in open_tools and self._is_qt_object_alive(window):
                try:
                    window.hide()
                except Exception:
                    pass
        for key in open_tools:
            self._open_tool_window_by_key(key)
        normalize_workspace = getattr(self, "_normalize_workspace_sidebar_docks", None)
        if callable(normalize_workspace):
            normalize_workspace()
        self._queue_terminal_layout_fit()
        self._save_workspace_layout("last")
        self._push_notification("Workspace preset applied", f"{preset_name.title()} workspace is now active.", level="INFO", source="workspace", dedupe_seconds=2.0)
        if hasattr(self, "system_console"):
            self.system_console.log(f"Applied {preset_name.title()} workspace preset.", "INFO")
        return preset_name

    def restore_trader_memory(self):
        settings = getattr(self, "settings", None)
        if settings is None:
            self.favorite_symbols = set()
            return
        raw = settings.value(self._favorite_symbols_storage_key(), "[]")
        try:
            parsed = json.loads(raw or "[]")
        except Exception:
            parsed = []
        self.favorite_symbols = {self._normalized_symbol(symbol) for symbol in parsed if str(symbol or "").strip()}
        self._refresh_symbol_picker_favorites()
        self._update_favorite_action_text()

    def persist_trader_memory(self):
        settings = getattr(self, "settings", None)
        if settings is None:
            return False
        settings.setValue(self._favorite_symbols_storage_key(), json.dumps(sorted(getattr(self, "favorite_symbols", set()) or set())))
        ticket = (getattr(self, "detached_tool_windows", {}) or {}).get("manual_trade_ticket")
        if self._is_qt_object_alive(ticket):
            self._save_manual_trade_template_from_window(ticket)
        return True

    def refresh_symbol_picker_favorites(self):
        picker = getattr(self, "symbol_picker", None)
        if picker is None:
            return
        items = [picker.itemText(index) for index in range(picker.count())]
        if not items:
            return
        favorites = set(getattr(self, "favorite_symbols", set()) or set())
        current = str(picker.currentText() or "").strip()
        ranked = sorted(items, key=lambda item: (0 if self._normalized_symbol(item) in favorites else 1, self._normalized_symbol(item)))
        if ranked == items:
            return
        blocked = picker.blockSignals(True)
        picker.clear()
        picker.addItems(ranked)
        if current:
            picker.setCurrentText(current)
        picker.blockSignals(blocked)

    def update_favorite_action_text(self):
        action = getattr(self, "action_favorite_symbol", None)
        if action is None:
            return
        symbol = ""
        current_chart = getattr(self, "_current_chart_symbol", None)
        if callable(current_chart):
            try:
                symbol = str(invoke_callable(current_chart) or "").strip()
            except Exception:
                symbol = ""
        if not symbol and getattr(self, "symbol_picker", None) is not None:
            symbol = str(self.symbol_picker.currentText() or "").strip()
        if not symbol:
            action.setText("Favorite Current Symbol")
            return
        normalized = self._normalized_symbol(symbol)
        favorites = set(getattr(self, "favorite_symbols", set()) or set())
        action.setText(f"Remove {normalized} From Favorites" if normalized in favorites else f"Favorite {normalized}")

    def toggle_current_symbol_favorite(self):
        symbol = ""
        current_chart = getattr(self, "_current_chart_symbol", None)
        if callable(current_chart):
            try:
                symbol = str(invoke_callable(current_chart) or "").strip()
            except Exception:
                symbol = ""
        if not symbol and getattr(self, "symbol_picker", None) is not None:
            symbol = str(self.symbol_picker.currentText() or "").strip()
        if not symbol:
            self._push_notification("Favorite symbol", "Open or select a symbol before saving it as a favorite.", level="WARN", source="favorites", dedupe_seconds=5.0)
            return False
        favorites = set(getattr(self, "favorite_symbols", set()) or set())
        normalized = self._normalized_symbol(symbol)
        added = normalized not in favorites
        favorites.add(normalized) if added else favorites.discard(normalized)
        self.favorite_symbols = favorites
        self._persist_trader_memory()
        self._refresh_symbol_picker_favorites()
        self._update_favorite_action_text()
        self._push_notification("Favorite symbols", f"{normalized} was {'added to' if added else 'removed from'} favorites.", level="INFO", source="favorites", dedupe_seconds=2.0)
        return added

    def load_manual_trade_template(self):
        settings = getattr(self, "settings", None)
        if settings is None:
            return {}
        raw = settings.value(self._manual_trade_template_storage_key(), "")
        try:
            payload = json.loads(raw or "{}")
        except Exception:
            payload = {}
        return dict(payload) if isinstance(payload, dict) else {}

    def save_manual_trade_template_from_window(self, window):
        if window is None:
            return {}
        payload = {
            "symbol": str(invoke_callable(getattr(getattr(window, "_manual_trade_symbol_picker", None), "currentText", None)) or "").strip(),
            "side": str(invoke_callable(getattr(getattr(window, "_manual_trade_side_picker", None), "currentText", None)) or "buy").strip().lower() or "buy",
            "order_type": str(invoke_callable(getattr(getattr(window, "_manual_trade_type_picker", None), "currentText", None)) or "market").strip().lower() or "market",
            "quantity_mode": self._normalize_manual_trade_quantity_mode(str(invoke_callable(getattr(getattr(window, "_manual_trade_quantity_picker", None), "currentText", None)) or "units")),
            "amount": float(invoke_callable(getattr(getattr(window, "_manual_trade_amount_input", None), "value", None)) or 0.0),
            "price": self._safe_float(invoke_callable(getattr(getattr(window, "_manual_trade_price_input", None), "text", None))),
            "stop_price": self._safe_float(invoke_callable(getattr(getattr(window, "_manual_trade_stop_price_input", None), "text", None))),
            "stop_loss": self._safe_float(invoke_callable(getattr(getattr(window, "_manual_trade_stop_loss_input", None), "text", None))),
            "take_profit": self._safe_float(invoke_callable(getattr(getattr(window, "_manual_trade_take_profit_input", None), "text", None))),
        }
        payload = {key: value for key, value in payload.items() if value not in (None, "", [])}
        settings = getattr(self, "settings", None)
        if settings is not None:
            settings.setValue(self._manual_trade_template_storage_key(), json.dumps(payload))
        return payload

    def command_palette_entries(self, query=None):
        query_text = str(query or "").strip().lower()
        entries = [
            {"title": "Manual Trade Ticket", "description": "Open the manual order ticket.", "keywords": "manual trade order ticket", "handler": lambda: self._open_manual_trade()},
            {"title": "Notification Center", "description": "Review fills, rejects, disconnects, and guard alerts.", "keywords": "notifications alerts fills rejects disconnect guard", "handler": self._open_notification_center},
            {"title": "Symbol Universe", "description": "Inspect active, watchlist, catalog, and discovery-batch tiers.", "keywords": "symbol universe tiers active watchlist catalog discovery batch broker", "handler": self._open_symbol_universe},
            {"title": "Live Agent Timeline", "description": "Watch the live decision flow across symbols and agents.", "keywords": "agent timeline live runtime signal risk execution", "handler": self._open_agent_timeline},
            {"title": "Trader Agent Monitor", "description": "Watch TraderAgent decisions, confidence, and reasoning in real time.", "keywords": "trader agent monitor decision profile confidence reasoning", "handler": self._open_trader_agent_monitor},
            {"title": "Performance Analytics", "description": "Open the performance analysis workspace.", "keywords": "performance analytics ledger equity pnl", "handler": self._open_performance},
            {"title": "Portfolio Exposure", "description": "Open the portfolio exposure view.", "keywords": "portfolio exposure risk", "handler": self._show_portfolio_exposure},
            {"title": "Position Analysis", "description": "Inspect open positions and account metrics.", "keywords": "position analysis risk", "handler": self._open_position_analysis_window},
            {"title": "Trade Checklist", "description": "Open the pre-trade and post-trade checklist.", "keywords": "checklist journal review", "handler": self._open_trade_checklist_window},
            {"title": "Journal Review", "description": "Open the trade journal review window.", "keywords": "journal review closed trades", "handler": self._open_trade_journal_review_window},
            {"title": "Recommendations", "description": "Open AI trade recommendations.", "keywords": "recommendations signals ai", "handler": self._open_recommendations_window},
            {"title": "Sopotek Pilot", "description": "Open the market chat workspace.", "keywords": "pilot market chat assistant", "handler": self._open_market_chat_window},
            {"title": "Quant PM", "description": "Open portfolio analytics and correlation tools.", "keywords": "quant pm correlation portfolio", "handler": self._open_quant_pm_window},
            {"title": "Strategy Assigner", "description": "Open the strategy assignment workspace.", "keywords": "strategy assigner ranking", "handler": self._open_strategy_assignment_window},
            {"title": "Strategy Optimization", "description": "Open the optimization workspace.", "keywords": "strategy optimization backtest", "handler": self._optimize_strategy},
            {"title": "Backtesting Workspace", "description": "Open the strategy tester.", "keywords": "backtest tester", "handler": self._show_backtest_window},
            {"title": "Export Diagnostics Bundle", "description": "Package logs, health checks, and runtime state for support.", "keywords": "diagnostics bundle support logs health export", "handler": self._export_diagnostics_bundle},
            {"title": "Trading Workspace", "description": "Focus the terminal on execution and monitoring.", "keywords": "workspace preset trading layout", "handler": lambda: self._apply_workspace_preset("trading")},
            {"title": "Research Workspace", "description": "Focus the terminal on analysis and strategy discovery.", "keywords": "workspace preset research layout", "handler": lambda: self._apply_workspace_preset("research")},
            {"title": "Risk Workspace", "description": "Focus the terminal on exposure and control panels.", "keywords": "workspace preset risk layout", "handler": lambda: self._apply_workspace_preset("risk")},
            {"title": "Review Workspace", "description": "Focus the terminal on journaling and performance review.", "keywords": "workspace preset review layout", "handler": lambda: self._apply_workspace_preset("review")},
            {"title": "Save Layout For Account", "description": "Save the current dock layout for this broker/account.", "keywords": "workspace layout save account", "handler": self._save_current_workspace_layout},
            {"title": "Restore Saved Layout", "description": "Restore the saved dock layout for this broker/account.", "keywords": "workspace layout restore account", "handler": self._restore_saved_workspace_layout},
            {"title": "Reset Dock Layout", "description": "Restore the main trading panels and default dock arrangement.", "keywords": "workspace reset dock layout panels", "handler": self._apply_default_dock_layout},
            {"title": "Show Market Watch", "description": "Bring back the Market Watch dock if it was hidden.", "keywords": "market watch watchlist symbols panel dock", "handler": lambda: self._show_workspace_dock(getattr(self, "market_watch_dock", None))},
            {"title": "Favorite Current Symbol", "description": "Pin the active symbol to the top of selectors.", "keywords": "favorite symbol watchlist", "handler": self._toggle_current_symbol_favorite},
            {"title": "Refresh Markets", "description": "Reload available symbols and market state.", "keywords": "refresh markets symbols", "handler": self._refresh_markets},
            {"title": "Refresh Chart", "description": "Reload the active chart candles.", "keywords": "refresh chart candles", "handler": self._refresh_active_chart_data},
            {"title": "Refresh Orderbook", "description": "Reload the active order book and recent trades.", "keywords": "refresh orderbook depth trades", "handler": self._refresh_active_orderbook},
            {"title": "Reload Balance", "description": "Refresh balances and equity.", "keywords": "reload balance equity", "handler": self._reload_balance},
        ]
        available_symbols = list(getattr(getattr(self, "controller", None), "symbols", []) or [])
        if query_text and available_symbols:
            ranked = []
            for symbol in available_symbols:
                normalized = self._normalized_symbol(symbol)
                haystack = normalized.lower()
                if query_text in haystack:
                    ranked.append((0 if haystack.startswith(query_text) else 1, normalized))
            for _priority, symbol in sorted(ranked)[:8]:
                entries.append({"title": f"Open Chart: {symbol}", "description": f"Open {symbol} on the active timeframe.", "keywords": f"chart symbol {symbol.lower()}", "handler": (lambda target=symbol: self._open_symbol_chart(target, getattr(self, "current_timeframe", "1h")))})
                entries.append({"title": f"Manual Trade: {symbol}", "description": f"Open a manual trade ticket for {symbol}.", "keywords": f"manual trade symbol {symbol.lower()}", "handler": (lambda target=symbol: self._open_manual_trade({"symbol": target, "source": "command_palette"}))})
        if not query_text:
            return entries
        tokens = [token for token in query_text.split() if token]
        return [entry for entry in entries if all(token in " ".join(str(entry.get(key, "") or "") for key in ("title", "description", "keywords")).lower() for token in tokens)]

    def refresh_command_palette_window(self, window=None, query=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("command_palette")
        if not self._is_qt_object_alive(window):
            return
        table = getattr(window, "_command_palette_table", None)
        search = getattr(window, "_command_palette_search", None)
        summary = getattr(window, "_command_palette_summary", None)
        if table is None or search is None or summary is None:
            return
        query_text = str(search.text() if query is None else query or "").strip()
        entries = self._command_palette_entries(query=query_text)
        window._command_palette_entries = entries
        table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            title_item = QTableWidgetItem(str(entry.get("title") or ""))
            description_item = QTableWidgetItem(str(entry.get("description") or ""))
            title_item.setToolTip(str(entry.get("description") or ""))
            description_item.setToolTip(str(entry.get("keywords") or ""))
            table.setItem(row_index, 0, title_item)
            table.setItem(row_index, 1, description_item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if entries:
            table.selectRow(0)
            summary.setText(f"{len(entries)} commands ready. Press Enter to run the highlighted command.")
        else:
            summary.setText("No commands match the current search.")

    def execute_command_palette_selection(self, window=None):
        window = window or (getattr(self, "detached_tool_windows", {}) or {}).get("command_palette")
        if not self._is_qt_object_alive(window):
            return None
        table = getattr(window, "_command_palette_table", None)
        entries = list(getattr(window, "_command_palette_entries", []) or [])
        if table is None or not entries:
            return None
        row = table.currentRow()
        row = 0 if row < 0 else row
        if row >= len(entries):
            return None
        entry = entries[row]
        handler = entry.get("handler")
        try:
            if callable(handler):
                window.hide()
                return invoke_callable(handler)
        except Exception as exc:
            self._show_async_message("Command Failed", str(exc), QMessageBox.Icon.Critical)
        return None

    def open_command_palette(self):
        window = self._get_or_create_tool_window("command_palette", "Command Palette", width=760, height=520)
        if getattr(window, "_command_palette_container", None) is None:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            summary = QLabel("Type a task, symbol, or workspace name to jump directly to it.")
            summary.setWordWrap(True)
            summary.setStyleSheet("color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; border-radius: 12px; padding: 10px;")
            layout.addWidget(summary)
            search = QLineEdit()
            search.setPlaceholderText("Try 'performance', 'risk', 'btc', or 'layout'")
            search.textChanged.connect(lambda *_: self._refresh_command_palette_window(window))
            search.returnPressed.connect(lambda: self._execute_command_palette_selection(window))
            layout.addWidget(search)
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Command", "Description"])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.cellDoubleClicked.connect(lambda *_: self._execute_command_palette_selection(window))
            layout.addWidget(table, 1)
            run_btn = QPushButton("Run Selected Command")
            run_btn.clicked.connect(lambda: self._execute_command_palette_selection(window))
            layout.addWidget(run_btn)
            window.setCentralWidget(container)
            window._command_palette_container = container
            window._command_palette_summary = summary
            window._command_palette_search = search
            window._command_palette_table = table
            window._command_palette_entries = []
        self._refresh_command_palette_window(window)
        window.show()
        window.raise_()
        window.activateWindow()
        if getattr(window, "_command_palette_search", None) is not None:
            window._command_palette_search.setFocus()
            window._command_palette_search.selectAll()
        return window

    def create_menu_bar(self):
        result = orig_create_menu_bar(self)
        if not bool(getattr(self, "__dict__", {}).get("_workspace_menu_actions_initialized", False)):
            self.action_workspace_trading = QAction("Trading Workspace", self)
            self.action_workspace_trading.triggered.connect(lambda: self._apply_workspace_preset("trading"))
            self.action_workspace_research = QAction("Research Workspace", self)
            self.action_workspace_research.triggered.connect(lambda: self._apply_workspace_preset("research"))
            self.action_workspace_risk = QAction("Risk Workspace", self)
            self.action_workspace_risk.triggered.connect(lambda: self._apply_workspace_preset("risk"))
            self.action_workspace_review = QAction("Review Workspace", self)
            self.action_workspace_review.triggered.connect(lambda: self._apply_workspace_preset("review"))
            self.action_save_workspace_layout = QAction("Save Layout For Account", self)
            self.action_save_workspace_layout.triggered.connect(self._save_current_workspace_layout)
            self.action_restore_workspace_layout = QAction("Restore Saved Layout", self)
            self.action_restore_workspace_layout.triggered.connect(self._restore_saved_workspace_layout)
            self.action_reset_dock_layout = QAction("Reset Dock Layout", self)
            self.action_reset_dock_layout.triggered.connect(self._apply_default_dock_layout)
            self.action_symbol_universe = QAction("Symbol Universe", self)
            self.action_symbol_universe.triggered.connect(self._open_symbol_universe)
            for action_name, label, dock_attr in PANEL_ACTION_SPECS:
                action = QAction(label, self)
                action.triggered.connect(
                    lambda _checked=False, attr_name=dock_attr: self._show_workspace_dock(getattr(self, attr_name, None))
                )
                setattr(self, action_name, action)
            self.action_notifications = QAction("Notification Center", self)
            self.action_notifications.setShortcut("Ctrl+Shift+N")
            self.action_notifications.triggered.connect(self._open_notification_center)
            self.action_agent_timeline = QAction("Agent Runtime Monitor", self)
            self.action_agent_timeline.setShortcut("Ctrl+Shift+L")
            self.action_agent_timeline.triggered.connect(self._open_agent_timeline)
            self.action_trader_agent_monitor = QAction("Trader Agent Monitor", self)
            self.action_trader_agent_monitor.triggered.connect(self._open_trader_agent_monitor)
            self.action_command_palette = QAction("Command Palette", self)
            self.action_command_palette.setShortcut("Ctrl+K")
            self.action_command_palette.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.action_command_palette.triggered.connect(self._open_command_palette)
            self.action_favorite_symbol = QAction("Favorite Current Symbol", self)
            self.action_favorite_symbol.triggered.connect(self._toggle_current_symbol_favorite)
            self._workspace_menu_actions_initialized = True

        help_action = self.help_menu.menuAction() if getattr(self, "help_menu", None) is not None else None
        self.workspace_menu = QMenu("Workspace", self)
        if help_action is not None:
            self.menuBar().insertMenu(help_action, self.workspace_menu)
        else:
            self.workspace_menu = self.menuBar().addMenu("Workspace")
        self.panels_menu = QMenu("Panels", self.workspace_menu)
        for action in (
            self.action_workspace_trading,
            self.action_workspace_research,
            self.action_workspace_risk,
            self.action_workspace_review,
        ):
            self.workspace_menu.addAction(action)
        self.workspace_menu.addSeparator()
        self.workspace_menu.addAction(self.action_symbol_universe)
        self.workspace_menu.addAction(self.action_save_workspace_layout)
        self.workspace_menu.addAction(self.action_restore_workspace_layout)
        self.workspace_menu.addAction(self.action_reset_dock_layout)
        self.workspace_menu.addSeparator()
        self.workspace_menu.addMenu(self.panels_menu)
        for action_name, _label, _dock_attr in PANEL_ACTION_SPECS:
            self.panels_menu.addAction(getattr(self, action_name))

        self.review_menu.addAction(self.action_notifications)
        self.tools_menu.addAction(self.action_notifications)
        self.review_menu.addAction(self.action_agent_timeline)
        self.research_menu.addAction(self.action_agent_timeline)
        self.tools_menu.addAction(self.action_agent_timeline)
        self.review_menu.addAction(self.action_trader_agent_monitor)
        self.research_menu.addAction(self.action_trader_agent_monitor)
        self.tools_menu.addAction(self.action_trader_agent_monitor)
        self.tools_menu.addAction(self.action_symbol_universe)
        self.tools_menu.addAction(self.action_command_palette)
        self.charts_menu.addSeparator()
        self.charts_menu.addAction(self.action_favorite_symbol)
        refresh_notification_action_text(self)
        update_favorite_action_text(self)
        return result

    def update_symbols(self, exchange, symbols):
        result = orig_update_symbols(self, exchange, symbols)
        self._refresh_symbol_picker_favorites()
        self._update_favorite_action_text()
        try:
            self._refresh_symbol_universe_window()
        except Exception:
            pass
        return result

    def update_trade_log(self, trade):
        result = orig_update_trade_log(self, trade)
        try:
            self._record_trade_notification(trade)
        except Exception:
            pass
        return result

    def update_connection_status(self, status):
        previous = str(getattr(self, "current_connection_status", "") or "").strip().lower()
        result = orig_update_connection_status(self, status)
        current = str(status or "").strip().lower()
        if current == "disconnected" and previous != "disconnected":
            self._push_notification("API disconnected", "The trading connection dropped and the terminal is no longer connected.", level="ERROR", source="broker", dedupe_seconds=5.0)
        elif current == "connected" and previous == "disconnected":
            self._push_notification("API reconnected", "The trading connection is back online.", level="INFO", source="broker", dedupe_seconds=5.0)
        return result

    def refresh_terminal(self):
        result = orig_refresh_terminal(self)
        try:
            self._refresh_runtime_notifications()
        except Exception:
            pass
        try:
            self._refresh_symbol_universe_window()
        except Exception:
            pass
        try:
            self._refresh_live_agent_timeline_panel()
        except Exception:
            pass
        return result

    def restore_settings(self):
        result = orig_restore_settings(self)
        self._restore_trader_memory()
        restored_workspace = self._restore_workspace_layout("last")
        if not restored_workspace:
            self._apply_default_dock_layout()
        normalize_workspace = getattr(self, "_normalize_workspace_sidebar_docks", None)
        if callable(normalize_workspace):
            normalize_workspace()
        self._update_favorite_action_text()
        return result

    def close_event(self, event):
        try:
            self._save_workspace_layout("last")
            self._persist_trader_memory()
        except Exception:
            pass
        return orig_close_event(self, event)

    def submit_manual_trade_from_ticket(self, window):
        try:
            self._save_manual_trade_template_from_window(window)
        except Exception:
            pass
        return orig_submit_manual_trade_from_ticket(self, window)

    def manual_trade_default_payload(self, prefill=None):
        merged = dict(self._load_manual_trade_template())
        merged.update(dict(prefill or {}))
        return orig_manual_trade_default_payload(self, merged)

    def show_async_message(self, title, text, icon=QMessageBox.Icon.Information):
        result = orig_show_async_message(self, title, text, icon=icon)
        level = "INFO"
        if icon == QMessageBox.Icon.Critical:
            level = "ERROR"
        elif icon == QMessageBox.Icon.Warning:
            level = "WARN"
        self._push_notification(title, text, level=level, source="dialog", dedupe_seconds=10.0)
        return result

    def handle_chart_trade_context_action(self, payload):
        if isinstance(payload, dict):
            action = str(payload.get("action") or "").strip().lower()
            symbol = str(payload.get("symbol") or self._current_chart_symbol() or "").strip()
            if action in {"buy_market_ticket", "sell_market_ticket"} and symbol:
                return self._open_manual_trade(
                    {
                        "symbol": symbol,
                        "side": "buy" if action == "buy_market_ticket" else "sell",
                        "order_type": "market",
                        "source": "chart_context_menu",
                        "timeframe": payload.get("timeframe"),
                    }
                )
        return orig_handle_chart_trade_context_action(self, payload)

    def on_chart_tab_changed(self, index):
        result = orig_on_chart_tab_changed(self, index)
        self._update_favorite_action_text()
        return result

    Terminal._workspace_context_key = workspace_context_key
    Terminal._workspace_settings_prefix = workspace_settings_prefix
    Terminal._favorite_symbols_storage_key = favorite_symbols_storage_key
    Terminal._manual_trade_template_storage_key = manual_trade_template_storage_key
    Terminal._ensure_notification_state = ensure_notification_state
    Terminal._refresh_notification_action_text = refresh_notification_action_text
    Terminal._push_notification = push_notification
    Terminal._refresh_notification_center_window = refresh_notification_center_window
    Terminal._open_notification_center = open_notification_center
    Terminal._symbol_universe_snapshot = symbol_universe_snapshot
    Terminal._refresh_symbol_universe_window = refresh_symbol_universe_window
    Terminal._open_symbol_universe = open_symbol_universe
    Terminal._agent_timeline_snapshot_rows = agent_timeline_snapshot_rows
    Terminal._refresh_agent_timeline_window = refresh_agent_timeline_window
    Terminal._selected_agent_timeline_symbol = selected_agent_timeline_symbol
    Terminal._selected_agent_timeline_row = selected_agent_timeline_row
    Terminal._agent_timeline_row_status_label = agent_timeline_row_status_label
    Terminal._populate_agent_timeline_filters = populate_agent_timeline_filters
    Terminal._toggle_agent_timeline_pin_symbol = toggle_agent_timeline_pin_symbol
    Terminal._agent_timeline_health_snapshot = agent_timeline_health_snapshot
    Terminal._refresh_agent_timeline_health = refresh_agent_timeline_health
    Terminal._agent_timeline_anomaly_snapshot = agent_timeline_anomaly_snapshot
    Terminal._agent_timeline_anomaly_fingerprint = agent_timeline_anomaly_fingerprint
    Terminal._visible_agent_timeline_anomaly_snapshot = visible_agent_timeline_anomaly_snapshot
    Terminal._refresh_agent_timeline_anomalies = refresh_agent_timeline_anomalies
    Terminal._open_selected_agent_timeline_symbol_in_strategy_assigner = open_selected_agent_timeline_symbol_in_strategy_assigner
    Terminal._refresh_selected_agent_timeline_symbol = refresh_selected_agent_timeline_symbol
    Terminal._acknowledge_selected_agent_timeline_anomaly = acknowledge_selected_agent_timeline_anomaly
    Terminal._agent_timeline_assignment_text = agent_timeline_assignment_text
    Terminal._agent_timeline_recommendation_text = agent_timeline_recommendation_text
    Terminal._refresh_agent_timeline_details = refresh_agent_timeline_details
    Terminal._replay_selected_agent_timeline_symbol = replay_selected_agent_timeline_symbol
    Terminal._open_agent_timeline = open_agent_timeline
    Terminal._trader_agent_monitor_rows = trader_agent_monitor_rows
    Terminal._selected_trader_agent_monitor_row = selected_trader_agent_monitor_row
    Terminal._populate_trader_agent_monitor_filters = populate_trader_agent_monitor_filters
    Terminal._refresh_trader_agent_monitor_details = refresh_trader_agent_monitor_details
    Terminal._refresh_trader_agent_monitor_window = refresh_trader_agent_monitor_window
    Terminal._open_trader_agent_monitor = open_trader_agent_monitor
    Terminal._record_trade_notification = record_trade_notification
    Terminal._runtime_notification_transition = runtime_notification_transition
    Terminal._refresh_runtime_notifications = refresh_runtime_notifications
    Terminal._canonical_tool_window_key = canonical_tool_window_key
    Terminal._visible_tool_window_keys = visible_tool_window_keys
    Terminal._save_workspace_layout = save_workspace_layout
    Terminal._restore_workspace_layout = restore_workspace_layout
    Terminal._save_current_workspace_layout = save_current_workspace_layout
    Terminal._restore_saved_workspace_layout = restore_saved_workspace_layout
    Terminal._open_tool_window_by_key = open_tool_window_by_key
    Terminal._apply_workspace_preset = apply_workspace_preset
    Terminal._restore_trader_memory = restore_trader_memory
    Terminal._persist_trader_memory = persist_trader_memory
    Terminal._refresh_symbol_picker_favorites = refresh_symbol_picker_favorites
    Terminal._update_favorite_action_text = update_favorite_action_text
    Terminal._toggle_current_symbol_favorite = toggle_current_symbol_favorite
    Terminal._load_manual_trade_template = load_manual_trade_template
    Terminal._save_manual_trade_template_from_window = save_manual_trade_template_from_window
    Terminal._command_palette_entries = command_palette_entries
    Terminal._refresh_command_palette_window = refresh_command_palette_window
    Terminal._execute_command_palette_selection = execute_command_palette_selection
    Terminal._open_command_palette = open_command_palette
    Terminal._create_menu_bar = create_menu_bar
    Terminal._update_symbols = update_symbols
    Terminal._update_trade_log = update_trade_log
    Terminal.update_connection_status = update_connection_status
    Terminal._refresh_terminal = refresh_terminal
    Terminal._restore_settings = restore_settings
    Terminal.closeEvent = close_event
    Terminal._submit_manual_trade_from_ticket = submit_manual_trade_from_ticket
    Terminal._manual_trade_default_payload = manual_trade_default_payload
    Terminal._show_async_message = show_async_message
    Terminal._handle_chart_trade_context_action = handle_chart_trade_context_action
    Terminal._on_chart_tab_changed = on_chart_tab_changed
    Terminal._operator_features_installed = True
