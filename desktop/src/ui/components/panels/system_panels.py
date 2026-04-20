from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QGridLayout, QLabel, QTableWidget, QTextBrowser, QVBoxLayout, QWidget

from ui.console.system_console import SystemConsole


AI_MONITOR_HEADERS = [
    "Symbol",
    "Signal",
    "Confidence",
    "Regime",
    "Volatility",
    "Time",
]


def create_system_console_panel(terminal):
    terminal.system_console = SystemConsole()
    terminal.system_console.screenshot_requested.connect(terminal.take_screen_shot)

    dock = QDockWidget("System Console", terminal)
    dock.setObjectName("system_console_dock")
    terminal.system_console_dock = dock
    dock.setWidget(terminal.system_console)

    terminal.addDockWidget(Qt.BottomDockWidgetArea, dock)
    dock.hide()
    return dock


def create_system_status_panel(terminal):
    dock = QDockWidget("System Status", terminal)
    dock.setObjectName("system_status_dock")
    dock.setMinimumWidth(250)
    dock.setMaximumWidth(320)
    terminal.system_status_dock = dock

    container = QWidget()
    layout = QGridLayout()
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(8)

    terminal.status_labels = {}

    fields = [
        "Exchange",
        "Mode",
        "Account",
        "License",
        "Risk Profile",
        "Trade Venue",
        "Data Provider",
        "Swap Provider",
        "News Mode",
        "Symbols Loaded",
        "Equity",
        "Balance",
        "Free Margin",
        "Used Margin",
        "Spread %",
        "Open Positions",
        "Open Orders",
        "Broker API",
        "Websocket",
        "AITrading",
        "AI Scope",
        "Watchlist",
        "Behavior Guard",
        "Guard Reason",
        "Health Check",
        "Readiness",
        "Quote Health",
        "Candle Health",
        "Orderbook Health",
        "Pipeline",
        "Timeframe",
    ]

    for row, field in enumerate(fields):
        title = QLabel(field)
        title.setStyleSheet("color: #8fa3bf; font-weight: 700;")
        value = QLabel("-")
        value.setWordWrap(True)
        value.setStyleSheet("color: #e6edf7; font-weight: 600;")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(title, row, 0)
        layout.addWidget(value, row, 1)

        terminal.status_labels[field] = value

    container.setLayout(layout)

    dock.setWidget(container)

    terminal.addDockWidget(Qt.LeftDockWidgetArea, dock)
    dock.hide()
    return dock


def create_ai_signal_panel(terminal):
    dock = QDockWidget("AI Signal Monitor", terminal)
    dock.setObjectName("ai_signal_dock")
    terminal.ai_signal_dock = dock

    terminal.ai_table = QTableWidget()
    terminal._configure_monitor_table(terminal.ai_table)
    terminal.ai_table.setColumnCount(len(AI_MONITOR_HEADERS))
    terminal.ai_table.setHorizontalHeaderLabels(AI_MONITOR_HEADERS)

    dock.setWidget(terminal.ai_table)

    def _refresh_on_visibility(visible):
        if not visible:
            return
        refresh = getattr(terminal, "_refresh_ai_monitor_table", None)
        table = getattr(terminal, "ai_table", None)
        if callable(refresh) and table is not None:
            refresh(table, force=True)

    dock.visibilityChanged.connect(_refresh_on_visibility)

    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    return dock


def create_live_agent_timeline_panel(terminal):
    dock = QDockWidget("Agent Runtime Monitor", terminal)
    dock.setObjectName("live_agent_timeline_dock")
    terminal.live_agent_timeline_dock = dock

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    summary = QLabel("Waiting for agent runtime activity in the current session.")
    summary.setWordWrap(True)
    summary.setStyleSheet(
        "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
        "border-radius: 12px; padding: 10px; font-size: 12px; font-weight: 600;"
    )
    layout.addWidget(summary)

    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setStyleSheet(
        "QTextBrowser { background-color: #0f1726; color: #d9e6f7; border: 1px solid #20324d; "
        "border-radius: 12px; padding: 10px; }"
    )
    layout.addWidget(browser, 1)

    terminal.live_agent_timeline_summary = summary
    terminal.live_agent_timeline_browser = browser
    dock.setWidget(container)

    def _refresh_on_visibility(visible):
        if not visible:
            return
        refresh = getattr(terminal, "_refresh_live_agent_timeline_panel", None)
        if callable(refresh):
            refresh(force=True)

    dock.visibilityChanged.connect(_refresh_on_visibility)

    terminal.addDockWidget(Qt.RightDockWidgetArea, dock)
    dock.hide()
    return dock
