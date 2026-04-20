from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTableWidget, QTextBrowser, QTextEdit

from ui.components.panels.system_panels import AI_MONITOR_HEADERS


DOCUMENTATION_HTML = """
            <h2>Documentation</h2>
            <h3>1. What This App Does</h3>
            <p>Sopotek is a trading workstation that combines broker access, live charting, AI-driven signal monitoring, orderbook and recent-trade views, depth and market-info tabs, execution controls, risk settings, historical backtesting, and strategy optimization.</p>

            <h3>2. Quick Start</h3>
            <p><b>Step 1:</b> Open the dashboard and choose a broker type, exchange, mode, strategy, and risk budget.</p>
            <p><b>Step 2:</b> Use paper mode first whenever you are testing a new broker, strategy, or market.</p>
            <p><b>Step 3:</b> Launch the terminal, open a symbol tab from the toolbar, and confirm candles, order book, recent trades, and chart tabs are loading.</p>
            <p><b>Step 4:</b> Review system status, balances, training states, and application settings before turning on AI trading.</p>
            <p><b>Step 5:</b> Use backtesting and optimization before trusting a strategy in live conditions.</p>

            <h3>3. Main Layout</h3>
            <p><b>Toolbar:</b> symbol picker, timeframe controls, AI trading toggle, and chart actions.</p>
            <p><b>Chart tabs:</b> one tab per symbol and timeframe, with internal views for candlesticks, depth chart, and market info.</p>
            <p><b>Orderbook:</b> bid/ask ladders plus a Coinbase-style recent-trades feed for the active chart symbol.</p>
            <p><b>AI Signal Monitor:</b> latest model decisions, confidence, regime, and volatility readout.</p>
            <p><b>Strategy Debug:</b> indicator values and strategy reasoning for generated signals.</p>
            <p><b>System Status:</b> connection state, websocket state, balances, and session health summary.</p>
            <p><b>Logs:</b> runtime messages, broker responses, and error diagnostics.</p>

            <h3>4. Charts</h3>
            <p>Use the symbol selector in the toolbar to open a new chart tab. If the symbol already exists, the app focuses the existing tab instead of duplicating it.</p>
            <p>Timeframe buttons reload candles for the active tab. Indicators can be added from the <b>Charts</b> menu. Bid and ask dashed price lines can be toggled from <b>Charts -&gt; Show Bid/Ask Lines</b>.</p>
            <p>The candlestick chart is intentionally the largest area and can be resized where splitters are available. Use the internal chart tabs to move between <b>Candlestick</b>, <b>Depth Chart</b>, and <b>Market Info</b>.</p>

            <h3>5. AI Trading</h3>
            <p>The AI trading button enables the automated worker loop. It does not guarantee that orders will be sent every cycle; signals still pass through broker checks, balance checks, market-status checks, and exchange minimum filters.</p>
            <p>If AI trading is on but no trades occur, check the logs, AI Signal Monitor, Strategy Debug, and account balances first.</p>

            <h3>6. Orders and Safety</h3>
            <p>The execution path checks available balances before sending orders, trims amounts when necessary, and skips symbols on cooldown after exchange rejections such as closed markets, insufficient balance, or minimum notional failures.</p>
            <p>For live sessions, always confirm that you have enough quote currency for buys and enough base currency for sells.</p>

            <h3>7. Backtesting</h3>
            <p>Open a chart that already has candles loaded, then use <b>Backtesting -&gt; Run Backtest</b>. This initializes the backtest with the active chart symbol, timeframe, and strategy context.</p>
            <p>In the backtesting workspace, click <b>Start Backtest</b> to run the historical simulation and <b>Generate Report</b> to export PDF and spreadsheet results.</p>
            <p>If backtesting says no data is available, reload the chart candles first.</p>

            <h3>8. Strategy Optimization</h3>
            <p>Use <b>Backtesting -&gt; Strategy Optimization</b> to run a parameter sweep over core strategy settings such as RSI, EMA fast, EMA slow, and ATR periods.</p>
            <p>The optimization table ranks results by performance metrics. Use <b>Apply Best Params</b> to push the top result into the active strategy object.</p>
            <p>Optimization depends on historical candle data being available for the active chart.</p>

            <h3>9. Settings and Risk Menus</h3>
            <p>Use the <b>Settings</b> menu for trading defaults, chart behavior, refresh intervals, backtesting capital, storage, and integrations.</p>
            <p>Use the <b>Risk</b> menu for risk settings, portfolio exposure, position analysis, and the rest of the risk-control workflow.</p>

            <h3>10. Tools Windows</h3>
            <p>The <b>Tools</b> menu opens detached utility windows so you can keep charts large while monitoring logs, AI signals, and performance analytics in parallel.</p>

            <h3>11. Supported Broker Concepts</h3>
            <p><b>Crypto:</b> CCXT-compatible exchanges and Stellar.</p>
            <p><b>Forex:</b> Oanda.</p>
            <p><b>Stocks:</b> Alpaca.</p>
            <p><b>Paper:</b> local simulated execution path.</p>

            <h3>12. Stellar Notes</h3>
            <p>For Stellar, use the public key in the dashboard API field and the secret seed in the secret field. Market data currently uses polling via Horizon rather than websocket streaming.</p>
            <p>Non-native assets may require issuer-aware configuration if the code is ambiguous.</p>

            <h3>13. Troubleshooting</h3>
            <p><b>No candles:</b> confirm the symbol exists on the broker and try changing timeframe.</p>
            <p><b>No orderbook:</b> open a chart tab first and wait for the orderbook refresh timer to update the active symbol.</p>
            <p><b>No recent trades:</b> some brokers do not expose public market prints for every symbol, so try another symbol or wait for the next refresh cycle.</p>
            <p><b>Depth chart or market info blank:</b> confirm the chart has candles and the order book has populated first.</p>
            <p><b>No AI signals:</b> verify that the strategy can compute features from the loaded candles and that AI trading is enabled when required.</p>
            <p><b>Orders rejected:</b> check exchange minimums, market status, insufficient balance, and broker-specific rules in the logs.</p>
            <p><b>Backtest/optimization blank:</b> make sure the active chart already has historical data loaded.</p>

            <h3>14. Recommended Workflow</h3>
            <p>Use this order: dashboard setup -> paper session -> verify charts and signals -> run backtest -> run optimization -> confirm application and risk settings -> move to live trading.</p>

            <h3>15. Where To Look Next</h3>
            <p>For broker-specific and integration-level details, open <b>Help -&gt; API Reference</b>.</p>
            """


def sync_logs_window(terminal, editor):
    source_text = terminal.system_console.console.toPlainText()
    if editor.toPlainText() == source_text:
        return

    editor.setPlainText(source_text)
    editor.moveCursor(QTextCursor.MoveOperation.End)


def open_logs(terminal):
    window = terminal._get_or_create_tool_window(
        "system_logs",
        "System Logs",
        width=980,
        height=620,
    )

    editor = getattr(window, "_logs_editor", None)
    if editor is None:
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(terminal.system_console.console.styleSheet())
        window.setCentralWidget(editor)
        window._logs_editor = editor

        sync_timer = QTimer(window)
        sync_timer.timeout.connect(lambda: terminal._sync_logs_window(editor))
        sync_timer.start(700)
        window._sync_timer = sync_timer

    terminal._sync_logs_window(editor)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def open_ml_monitor(terminal):
    window = terminal._get_or_create_tool_window(
        "ml_monitor",
        "ML Signal Monitor",
        width=880,
        height=520,
    )

    table = getattr(window, "_monitor_table", None)
    if table is None:
        table = QTableWidget()
        terminal._configure_monitor_table(table)
        table.setColumnCount(len(AI_MONITOR_HEADERS))
        table.setHorizontalHeaderLabels(AI_MONITOR_HEADERS)
        window.setCentralWidget(table)
        window._monitor_table = table

        sync_timer = QTimer(window)
        sync_timer.timeout.connect(lambda: terminal._refresh_ai_monitor_table(table))
        sync_timer.start(900)
        window._sync_timer = sync_timer

    terminal._refresh_ai_monitor_table(table, force=True)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def open_text_window(terminal, key, title, html, width=760, height=520):
    window = terminal._get_or_create_tool_window(key, title, width=width, height=height)

    browser = getattr(window, "_browser", None)
    if browser is None:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser_style = None
        browser_style_getter = getattr(terminal, "_tool_window_text_browser_style", None)
        if callable(browser_style_getter):
            try:
                browser_style = browser_style_getter()
            except Exception:
                browser_style = None
        if not isinstance(browser_style, str) or not browser_style.strip():
            browser_style = "QTextBrowser { background-color: #0b1220; color: #e6edf7; padding: 16px; }"
        browser.setStyleSheet(browser_style)
        window.setCentralWidget(browser)
        window._browser = browser

    browser.setHtml(html)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def open_docs(terminal):
    return terminal._open_text_window(
        "help_documentation",
        "Documentation",
        DOCUMENTATION_HTML,
        width=940,
        height=760,
    )
