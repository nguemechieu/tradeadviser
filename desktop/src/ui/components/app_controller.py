"""
App Controller is a Module - Main UI Controller for Sopotek Quant Trading System

This module contains the AppController class, which serves as the primary PyQt6-based
UI controller for the TradeAdviser Quant trading platform. It manages:
- User authentication and session management
- Broker connections and paper trading
- Market data streaming and web sockets
- Strategy execution and back testing
- Portfolio and risk management
- Trade execution and monitoring
- Integration services (Telegram, Email, SMS, News, Voice)
- Desktop-to-server communications
- Performance tracking and reporting

The AppController coordinates between the UI layers, trading core logic, and external
services, providing signals for real-time updates to the UI.
"""
import copy
import asyncio
import pathlib
from datetime import datetime, timedelta, timezone

import inspect
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
import traceback
import aiohttp
import pandas as pd
import shiboken6  # type: ignore[import-untyped]
from PySide6.QtCore import QEvent, QSettings, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
)
from dataclasses import asdict, is_dataclass

from concurrent.futures import ThreadPoolExecutor
from core.scheduler.event_scheduler import EventScheduler
from core.scheduler.scheduler import Scheduler
from backtesting.experiment_tracker import ExperimentTracker
from broker.broker_factory import BrokerFactory
from broker.market_venues import SPOT_ONLY_EXCHANGES, normalize_market_venue, supported_market_venues_for_profile
from broker.paper_broker import PaperBroker
from broker.rate_limiter import RateLimiter
from core.account_identity import resolve_account_label
from core.server_client import TradeAdviserClient
from core.trading_core import TradingCore
from events.event_bus import EventBus
from events.event_bus.event_types import EventType

from execution.hybrid_execution_request import HybridExecutionRequest
from integrations.news_service import NewsService
from integrations.telegram_service import TelegramService
from integrations.trade_notifications import (
    EmailTradeNotificationService,
    TwilioSmsTradeNotificationService,
    is_trade_close_event,
    trade_close_cache_key,
)
from integrations.voice_service import VoiceService
from engines.performance_engine import PerformanceEngine
from manager.broker_manager import BrokerManager
from portfolio.position_manager import PositionManager
from market_data.candle_buffer import CandleBuffer
from market_data.orderbook_buffer import OrderBookBuffer
from market_data.ticker_buffer import TickerBuffer
from market_data.ticker_stream import TickerStream
from websocket.alpaca_web_socket import AlpacaWebSocket
from websocket.binanceus_web_socket import BinanceUsWebSocket
from websocket.coinbase_web_socket import CoinbaseWebSocket
from websocket.oanda_web_socket import OandaWebSocket
from websocket.paper_web_socket import PaperWebSocket
from storage.agent_decision_repository import AgentDecisionRepository
from storage.database import configure_database, get_database_url, init_database, is_sqlite_url, normalize_database_url
from storage.equity_repository import EquitySnapshotRepository
from storage.market_data_repository import MarketDataRepository
from storage.trade_audit_repository import TradeAuditRepository
from storage.trade_repository import TradeRepository, derive_trade_outcome
from strategy.strategy import Strategy
from ui.components.services.trade_safety import age_seconds, format_age_label, timeframe_seconds
from ui.components.utils.performance_utils import safe_timer_start
from session.session_manager import SessionManager

# Hybrid server connection imports (for future server-connected mode)

# Use shared contracts from backend
try:
    from shared.contracts import (
        SessionContext,
        ApiResponseEnvelope,
        BrokerIdentifier,
        SymbolIdentifier,
        UserContext,
        CorrelationIds,
    )
    from sopotek.shared.enums import (
        SessionStatus,
        ExecutionStatus,
        BrokerKind,
        OrderSide,
        OrderType,
    )
    from sopotek.shared.commands import (
        CancelOrderCommand,
        ClosePositionCommand,
        ConnectBrokerCommand,
        PlaceOrderCommand,
        RequestMarketDataSubscriptionCommand,
        TriggerKillSwitchCommand,
    )
    from sopotek.shared.events import (
        ServerEventEnvelope,
    )
except ImportError:
    # Fallback for local development if sopotek package not available
    from shared.contracts import (
        SessionContext,
        ApiResponseEnvelope,
        BrokerIdentifier,
        SymbolIdentifier,
        UserContext,
        CorrelationIds,
    )
    from shared.enums import (
        SessionStatus,
        ExecutionStatus,
        BrokerKind,
        OrderSide,
        OrderType,
    )
    from shared.commands import (
        CancelOrderCommand,
        ClosePositionCommand,
        ConnectBrokerCommand,
        PlaceOrderCommand,
        RequestMarketDataSubscriptionCommand,
        TriggerKillSwitchCommand,
    )
    from shared.events import (
        ServerEventEnvelope,
    )

# Import real hybrid client classes
try:
    from shared.hybrid_client import (
        HybridApiClient,
        HybridWsClient,
        HybridSessionController,
        HybridSession,
    )
except ImportError:
    # Fallback placeholder classes for development without hybrid_client.py
    class HybridSession:
        """Placeholder for hybrid session data."""
        def __init__(self):
            self.session_id = ""
            self.access_token = ""
            self.user_id = ""
            self.email = ""
            self.status = "disconnected"

    class HybridApiClient:
        """Placeholder for hybrid API client."""
        def __init__(self, base_url):
            self.base_url = base_url

    class HybridWsClient:
        """Placeholder for hybrid WebSocket client."""
        def __init__(self, ws_url):
            self.ws_url = ws_url

    class HybridSessionController:
        """Placeholder for hybrid session controller."""
        def __init__(self, api_client=None, ws_client=None):
            self.api_client = api_client
            self.ws_client = ws_client
            self.event_callback = None

# Define event types if not imported
try:
    from sopotek.shared.events.base import EventType, ServerEventType
except ImportError:
    class EventType:  # type: ignore
        MARKET_TICK = "market.tick"
        ACCOUNT_EVENT = "ACCOUNT_EVENT"
        ALERT_EVENT = "ALERT_EVENT"
        CANDLE = "CANDLE"
        MARKET_DATA = "MARKET_DATA"
        ORDER = "ORDER"
        POSITION = "POSITION"
    
    class ServerEventType:  # type: ignore
        AGENT_HEALTH_UPDATED = "AGENT HEALTH UPDATED"

# Aliases for Hybrid* naming convention (for backward compatibility)
HybridBrokerIdentifier = BrokerIdentifier
HybridCancelOrderCommand = CancelOrderCommand
HybridClosePositionCommand = ClosePositionCommand
HybridConnectBrokerCommand = ConnectBrokerCommand
HybridCorrelationIds = CorrelationIds
# HybridExecutionRequest not available in contracts module - removed
HybridPlaceOrderCommand = PlaceOrderCommand
HybridRequestMarketDataSubscriptionCommand = RequestMarketDataSubscriptionCommand
HybridSessionContext = SessionContext
HybridSymbolIdentifier = SymbolIdentifier
HybridTriggerKillSwitchCommand = TriggerKillSwitchCommand
HybridUserContext = UserContext
HybridBrokerKind = BrokerKind
HybridOrderSide = OrderSide
HybridOrderType = OrderType
HybridSessionStatus = SessionStatus
HybridServerEventEnvelope = ServerEventEnvelope
HybridServerEventType = ServerEventType

try:
    import winsound
except Exception:  # pragma: no cover - non-Windows fallback
    winsound = None
from ui.components.i18n import (
    DEFAULT_LANGUAGE,
    apply_runtime_translations,
    normalize_language_code,
    translate,
    translate_rich_text,
    translate_text)
from ui.components.terminal import Terminal

from ui.components.services.platform_sync_service import PlatformSyncService
from ui.components.services.screenshot_service import capture_widget_to_output, sanitize_screenshot_fragment
from ui.components.dashboard import Dashboard
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

def _bounded_window_extent(requested, available, *, margin=24, minimum=640):
    """
    Calculate bounded window dimensions ensuring reasonable constraints.

    Args:
        requested: Requested window size (pixels)
        available: Available space (pixels)
        margin: Margin to reserve (default 24 pixels)
        minimum: Minimum allowed size (default 640 pixels)
    Returns:
        Tuple of (bounded_size, bounded_minimum) ensuring size fits within constraints
    """
    try:
        requested_value = int(requested)
    except Exception:
        requested_value = int(minimum)

    try:
        available_value = int(available)
    except Exception:
        available_value = requested_value

    usable = max(320, available_value - max(0, int(margin)))
    bounded_minimum = min(max(320, int(minimum)), usable)
    bounded_size = max(bounded_minimum, min(requested_value, usable))
    return bounded_size, bounded_minimum


def _normalize_forex_candle_price_component(value):
    """
    Normalize forex candle price component preference to standard format.
    Accepts 'bid', 'ask', or 'mid' (with various aliases).
    Defaults to 'bid' if invalid.
    """
    normalized = str(value or "bid").strip().lower()
    if normalized in {"b", "bid", "bids"}:
        return "bid"
    if normalized in {"a", "ask", "asks"}:
        return "ask"
    if normalized in {"m", "mid", "middle", "midpoint"}:
        return "mid"
    return "bid"


def _remote_database_url_from_env():
    """
    Extract remote database URL from SOPOTEK_DATABASE_URL environment variable.
    Returns empty string if not configured or if URL is a SQLite database.
    """
    raw_url = str(os.getenv("SOPOTEK_DATABASE_URL", "") or "").strip()
    if not raw_url:
        return ""
    normalized = normalize_database_url(raw_url)
    if not normalized or is_sqlite_url(normalized):
        return ""
    return normalized


def _storage_mode_from_env():
    """
    Extract storage mode from SOPOTEK_DATABASE_MODE environment variable.
    Valid values are 'local' or 'remote'. Returns empty string if not set.
    """
    value = str(os.getenv("SOPOTEK_DATABASE_MODE", "") or "").strip().lower()
    if value in {"local", "remote"}:
        return value
    return ""


def _normalize_history_boundary(value, *, end_of_day=False):
    """
    Normalize history boundary to UTC-aware timestamp.

    Handles string dates (YYYY-MM-DD or ISO format) and datetime objects.
    For date-only strings, sets time to end-of-day (23:59:59) or start-of-day (00:00:00)
    based on end_of_day parameter.

    Args:
        value: Date/datetime value to normalize
        end_of_day: If True, set to end of day; if False, set to start of day

    Returns:
        UTC-aware pandas Timestamp or None if invalid
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        timestamp = pd.Timestamp(value)
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if "T" not in text and len(text) <= 10:
            text = (
                f"{text}T23:59:59.999999+00:00"
                if end_of_day
                else f"{text}T00:00:00+00:00"
            )
        timestamp = pd.Timestamp(text)

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def _normalize_live_agent_timestamp(timestamp):
    if isinstance(timestamp, datetime):
        normalized = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        return normalized.timestamp(), normalized.strftime("%Y-%m-%d %H:%M:%S UTC")
    text = str(timestamp or "").strip()
    if not text:
        return None, ""
    try:
        normalized = datetime.fromisoformat(text.replace("Z", "+00:00"))
        normalized = normalized.replace(tzinfo=timezone.utc) if normalized.tzinfo is None else normalized.astimezone(timezone.utc)
        return normalized.timestamp(), normalized.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return None, text


class AppController(QMainWindow):
    """
    Main application controller for the Sopotek Quant trading platform.

    Inherits from QMainWindow to provide the primary application window.
    Manages all core functionality including:
    - Broker connections and trading operations
    - Market data streaming and storage
    - Strategy execution and monitoring
    - Portfolio and risk management
    - Integration services
    - Workspace access state

    Class Attributes:
        MAX_HISTORY_LIMIT: Maximum data points for local storage (50000)
        MAX_BACKTEST_HISTORY_LIMIT: Maximum history for backtest analysis (1M)
        FOREX_STANDARD_LOT_UNITS: Standard forex lot size in units (100000)
        ORDER_SIZE_BUFFER: Buffer to apply when calculating order sizes (0.98)

    Signals:
        symbols_signal: Emitted when symbol list changes
        candle_signal: Emitted when new candle data arrives
        equity_signal: Emitted when portfolio equity updates
        trade_signal: Emitted when trade is executed
        ticker_signal: Emitted when ticker data updates
        connection_signal: Emitted when broker connection status changes
        orderbook_signal: Emitted when orderbook updates
        news_signal: Emitted when news items arrive
        strategy_debug_signal: Emitted for strategy debugging data
        agent_runtime_signal: Emitted for agent runtime updates
        workspace access state updates
    """

    # === Configuration Constants ===
    MAX_HISTORY_LIMIT = 50000
    MAX_BACKTEST_HISTORY_LIMIT = 1000000
    FOREX_STANDARD_LOT_UNITS = 100000.0
    ORDER_SIZE_BUFFER = 0.98
    OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICES = [
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
    ]

    # === PyQt6 Signals for UI Updates ===
    symbols_signal = Signal(str, list)
    candle_signal = Signal(str, object)
    equity_signal = Signal(float)

    trade_signal = Signal(dict)
    ticker_signal = Signal(str, float, float)
    connection_signal = Signal(str)
    orderbook_signal = Signal(str, list, list)
    recent_trades_signal = Signal(str, list)
    news_signal = Signal(str, list)
    ai_signal_monitor = Signal(dict)

    strategy_debug_signal = Signal(dict)
    agent_runtime_signal = Signal(dict)
    autotrade_toggle = Signal(bool)
    logout_requested = Signal(str)
    training_status_signal = Signal(str, str)
    language_changed = Signal(str)

    # === Crypto Asset Configuration ===
    ALLOWED_CRYPTO_QUOTES = {"USDT", "USD", "USDC", "BUSD", "BTC", "ETH"}
    BANNED_BASE_TOKENS = {"USD4", "FAKE", "TEST"}
    BANNED_BASE_SUFFIXES = {"UP", "DOWN", "BULL", "BEAR", "3L", "3S", "5L", "5S"}
    PREFERRED_BASES = [
        "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
        "DOT", "LINK", "LTC", "ATOM", "AAVE", "NEAR", "UNI", "MKR",
    ]
    QUOTE_PRIORITY = {"USDT": 0, "USD": 1, "USDC": 2, "BUSD": 3, "BTC": 4, "ETH": 5}
    COINBASE_QUOTE_PRIORITY = {"USD": 0, "USDC": 1, "EUR": 2, "GBP": 3, "USDT": 4, "BUSD": 5, "BTC": 6, "ETH": 7}

    # === Exchange-Specific Symbol Limits ===
    COINBASE_SYMBOL_LIMIT = 10
    COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT = 6
    COINBASE_TICKER_POLL_LIMIT = 8
    COINBASE_TICKER_POLL_SECONDS = 2.0
    COINBASE_FAST_START_AUTO_ASSIGN_DELAY_SECONDS = 12.0
    COINBASE_WATCHLIST_SYMBOL_LIMIT = 24
    COINBASE_DISCOVERY_BATCH_SIZE = 4
    COINBASE_DISCOVERY_PRIORITY_COUNT = 2
    DEFAULT_SYMBOL_WATCHLIST_LIMIT = 36
    DEFAULT_DISCOVERY_BATCH_SIZE = 10
    DEFAULT_DISCOVERY_PRIORITY_COUNT = 3
    SPOT_ONLY_SYMBOL_WATCHLIST_LIMIT = 20
    SPOT_ONLY_DISCOVERY_BATCH_SIZE = 8
    SOLANA_SYMBOL_WATCHLIST_LIMIT = 18
    SOLANA_DISCOVERY_BATCH_SIZE = 6
    STELLAR_SYMBOL_WATCHLIST_LIMIT = 18
    STELLAR_DISCOVERY_BATCH_SIZE = 6
    FOREX_SYMBOL_WATCHLIST_LIMIT = 20
    FOREX_DISCOVERY_BATCH_SIZE = 8
    STOCKS_SYMBOL_WATCHLIST_LIMIT = 24
    STOCKS_DISCOVERY_BATCH_SIZE = 8
    PAPER_SYMBOL_WATCHLIST_LIMIT = 24
    PAPER_DISCOVERY_BATCH_SIZE = 10

    # === Data Freshness Thresholds ===
    QUOTE_STALE_SECONDS = 20.0
    ORDERBOOK_STALE_SECONDS = 20.0
    CANDLE_STALE_MIN_SECONDS = 60.0
    CANDLE_STALE_MULTIPLIER = 3.0

    # === Forex and Commodity Assets ===
    FOREX_SYMBOL_QUOTES = {
        "AED", "AUD", "CAD", "CHF", "CNH", "CZK", "DKK", "EUR", "GBP", "HKD",
        "HUF", "JPY", "MXN", "NOK", "NZD", "PLN", "SEK", "SGD", "THB", "TRY",
        "USD", "ZAR",
    }
    OANDA_CFD_BASES = {
        "XAU", "XAG", "XPT", "XPD", "XCU",
        "BCO", "WTICO", "NATGAS", "SOYBN", "WHEAT", "CORN", "SUGAR",
    }

    # === Feature Gating ===
    TRADEADVISER_FEATURE_ALIASES = {
        "live_trading": "trading",
        "trading": "trading",
        "auto_trading": "auto_trading",
        "ml_signals": "ml_signals",
        "multi_exchange": "multi_exchange",
        "agent_network": "agent_network",
    }
    TRADEADVISER_RESTRICTED_FEATURES = {"trading", "auto_trading", "ml_signals", "multi_exchange", "agent_network"}

    def __init__(self, *args, **kwargs):
        """
        Initialize the AppController (main application window).

        Sets up:
        - PyQt6 main window and event handling
        - Logging infrastructure
        - Server connectivity
        - Broker and trading system managers
        - Configuration from settings and environment
        - Market data buffers and streams
        - Integration services (Telegram, Email, SMS, News, Voice)
        - UI components and layouts

        Raises exception if critical initialization fails (caught and logged).
        """
        super().__init__(*args, **kwargs)
        self.controller = self
        self.event_bus = EventBus()


        # === Async and Threading ===
        self._login_lock = asyncio.Lock()

        # === Background Tasks ===
        self._ticker_task = None
        self._market_stream_recovery_task = None
        self._ws_task = None
        self._ws_bus_task = None
        self.ws_bus = None
        self.ws_manager = None

        # === Application Settings and Localization ===
        self.settings = QSettings("TradeAdviser", "TradingPlatform")
        self.language_code = normalize_language_code(
            self.settings.value("ui/language", DEFAULT_LANGUAGE)
        )



        # === Logging Setup ===
        self.logger = logging.getLogger("AppController")
        self.logger.setLevel(logging.INFO)
        self._app_event_filter_target = None
        self._event_filter_disabled = False

        # Install event filter for global event monitoring
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_event_filter_target = app

        # Setup logging to file and console
        os.makedirs("logs", exist_ok=True)
        if not self.logger.handlers:
            self.logger.addHandler(logging.StreamHandler(sys.stdout))
            self.logger.addHandler(logging.FileHandler("logs/app.log"))

        # === Server Configuration ===
        self.license_status = {
            "summary": "Open workspace access",
            "description": "Licensing has been removed from the desktop workflow.",
            "features": [],
            "allowed_features": [],
        }
        self.platform_sync_service = PlatformSyncService()
        self.server = TradeAdviserClient(base_url="")
        self.hybrid_api_client = None
        self.hybrid_ws_client = None
        self.hybrid_session_controller = None
        self.hybrid_session_state = None
        self.hybrid_server_connected = False
        self.hybrid_server_last_error = ""
        self.hybrid_server_last_sequence = 0
        self.hybrid_server_base_url = ""
        self.hybrid_server_ws_url = ""
        self.hybrid_authoritative_runtime = {}
        self._reset_hybrid_authoritative_runtime()
        self.allowed_features = set(self.TRADEADVISER_RESTRICTED_FEATURES)
        self.server_feature_gate_enabled = False
        self.server_performance_snapshot = {}
        self.server_strategy_feedback = {}

        # === Broker and Trading Management ===
        self.broker_manager = BrokerManager()
        self.session_manager = SessionManager(parent_controller=self, logger=self.logger)
        self.active_session_id = None
        self.rate_limiter = RateLimiter()

        # === Core Services ===
        self.broker = None
        self.trading_system = None
        self.terminal = None
        self.session_terminals = {}
        self.telegram_service = None
        self.behavior_guard = None
        self.portfolio_allocator = None
        self.institutional_risk_engine = None

        # === Quant System State ===
        self.quant_allocation_snapshot = {}
        self.quant_risk_snapshot = {}
        self.health_check_report = []
        self.health_check_summary = "Not run"
        self._latest_live_readiness_report = {}
        self._live_agent_decision_events = {}
        self._live_agent_runtime_feed = []
        self.feedback_experiment_tracker = ExperimentTracker()
        self._strategy_feedback_cache = {}

        # === Risk Management Configuration ===
        self.risk_profile_name = str(self.settings.value("risk/profile_name", "Balanced") or "Balanced").strip() or "Balanced"
        self.max_portfolio_risk = self.settings.value("risk/max_portfolio_risk", 0.10) or 0.10
        self.max_risk_per_trade = self.settings.value("risk/max_risk_per_trade", 0.02) or 0.02
        self.max_position_size_pct = self.settings.value("risk/max_position_size_pct", 0.10) or 0.10
        self.max_gross_exposure_pct = self.settings.value("risk/max_gross_exposure_pct", 2.0) or 2.0
        self.min_confidence = 0.65
        self.min_vote_margin = 0.10
        self.max_risk_score = 0.7
        self.allow_ranging = True
        self.max_portfolio_exposure = 0.85

        # === Hedging and Margin Management ===
        self.hedging_enabled = str(
            self.settings.value("trading/hedging_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.margin_closeout_guard_enabled = str(
            self.settings.value("risk/margin_closeout_guard_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.max_margin_closeout_pct = max(0.01,
                                           min(1.0, float(self.settings.value("risk/max_margin_closeout_pct") or 0.50) ))

        # === Trading Parameters ===
        self.confidence = 0
        self.volatility = 0
        self.order_type = "limit"
        self.time_frame = "1h"
        self.strategy_name = Strategy.normalize_strategy_name(
            self.settings.value("strategy/name", "Trend Following")
        )
        # === Integration Services Configuration ===
        self.telegram_enabled = str(self.settings.value("integrations/telegram_enabled", "false")).lower() in {"1", "true", "yes", "on"}
        self.telegram_bot_token = str(self.settings.value("integrations/telegram_bot_token", "") or "").strip()
        self.telegram_chat_id = str(self.settings.value("integrations/telegram_chat_id", "") or "").strip()

        # === Trade Close Notifications ===
        self.trade_close_notifications_enabled = str(
            self.settings.value("integrations/trade_close_notifications_enabled", "false")
        ).lower() in {"1", "true", "yes", "on"}
        self.trade_close_notify_telegram = str(
            self.settings.value("integrations/trade_close_notify_telegram", "false")
        ).lower() in {"1", "true", "yes", "on"}
        self.trade_close_notify_email = str(
            self.settings.value("integrations/trade_close_notify_email", "false")
        ).lower() in {"1", "true", "yes", "on"}
        self.trade_close_notify_sms = str(
            self.settings.value("integrations/trade_close_notify_sms", "false")
        ).lower() in {"1", "true", "yes", "on"}

        # === Email Configuration ===
        self.trade_close_email_host = str(self.settings.value("integrations/trade_close_email_host", "") or "").strip()
        self.trade_close_email_port = int(self.settings.value("integrations/trade_close_email_port", 587) or 587)
        self.trade_close_email_username = str(self.settings.value("integrations/trade_close_email_username", "") or "").strip()
        self.trade_close_email_password = str(self.settings.value("integrations/trade_close_email_password", "") or "")
        self.trade_close_email_from = str(self.settings.value("integrations/trade_close_email_from", "") or "").strip()
        self.trade_close_email_to = str(self.settings.value("integrations/trade_close_email_to", "") or "").strip()
        self.trade_close_email_starttls = str(
            self.settings.value("integrations/trade_close_email_starttls", "true")
        ).lower() in {"1", "true", "yes", "on"}

        # === SMS Configuration ===
        self.trade_close_sms_account_sid = str(self.settings.value("integrations/trade_close_sms_account_sid", "") or "").strip()
        self.trade_close_sms_auth_token = str(self.settings.value("integrations/trade_close_sms_auth_token", "") or "")
        self.trade_close_sms_from_number = str(self.settings.value("integrations/trade_close_sms_from_number", "") or "").strip()
        self.trade_close_sms_to_number = str(self.settings.value("integrations/trade_close_sms_to_number", "") or "").strip()

        # === Voice and AI Services ===
        self.openai_api_key = str(self.settings.value("integrations/openai_api_key", "") or "").strip()
        self.openai_model = str(self.settings.value("integrations/openai_model", "gpt-5-mini") or "gpt-5-mini").strip()
        self.voice_provider = str(self.settings.value("integrations/voice_provider", "windows") or "windows").strip().lower()
        if self.voice_provider not in {"windows", "google"}:
            self.voice_provider = "windows"
        self.voice_output_provider = str(
            self.settings.value("integrations/voice_output_provider", "windows") or "windows"
        ).strip().lower()
        if self.voice_output_provider not in {"windows", "openai"}:
            self.voice_output_provider = "windows"
        legacy_voice_name = str(self.settings.value("integrations/voice_name", "") or "").strip()
        self.voice_windows_name = str(
            self.settings.value("integrations/voice_windows_name", legacy_voice_name) or legacy_voice_name
        ).strip()
        self.voice_openai_name = str(
            self.settings.value("integrations/voice_openai_name", "alloy") or "alloy"
        ).strip().lower() or "alloy"
        if self.voice_openai_name not in self.OPENAI_TTS_VOICES:
            self.voice_openai_name = "alloy"
        self.voice_name = self._current_market_chat_voice_name()

        # === News and Market Data Integration ===
        self.news_enabled = str(self.settings.value("integrations/news_enabled", "true")).lower() in {"1", "true", "yes", "on"}
        self.news_autotrade_enabled = str(self.settings.value("integrations/news_autotrade_enabled", "false")).lower() in {"1", "true", "yes", "on"}
        self.news_draw_on_chart = str(self.settings.value("integrations/news_draw_on_chart", "true")).lower() in {"1", "true", "yes", "on"}
        self.news_feed_url = str(self.settings.value("integrations/news_feed_url", NewsService.DEFAULT_FEED_URL) or NewsService.DEFAULT_FEED_URL).strip()

        # === Market and Trading Preferences ===
        self.market_trade_preference = normalize_market_venue(self.settings.value("trading/market_type", "auto"))
        self.forex_candle_price_component = _normalize_forex_candle_price_component(
            self.settings.value("market_data/forex_candle_price_component", "bid")
        )
        # === Database Configuration ===
        self.database_mode, self.database_url = self._resolve_initial_storage_preferences(self.settings)
        self.database_connection_url = ""

        # === Autotrade Configuration ===
        self.autotrade_scope = self._normalize_autotrade_scope(self.settings.value("autotrade/scope", "all"))
        self._market_data_shortfall_notices = {}
        self._market_data_warning_timestamps = {}
        raw_watchlist = self.settings.value("autotrade/watchlist", "[]")
        try:
            parsed_watchlist = json.loads(raw_watchlist or "[]")
        except Exception:
            parsed_watchlist = []
        self.autotrade_watchlist = {
            str(symbol).upper().strip()
            for symbol in parsed_watchlist
            if str(symbol).strip()
        }

        # === Strategy Configuration ===
        self.strategy_params = {
            "rsi_period": int(self.settings.value("strategy/rsi_period", 14)),
            "ema_fast": int(self.settings.value("strategy/ema_fast", 20)),
            "ema_slow": int(self.settings.value("strategy/ema_slow", 50)),
            "atr_period": int(self.settings.value("strategy/atr_period", 14)),
            "oversold_threshold": float(self.settings.value("strategy/oversold_threshold", 35.0)),
            "overbought_threshold": float(self.settings.value("strategy/overbought_threshold", 65.0)),
            "breakout_lookback": int(self.settings.value("strategy/breakout_lookback", 20)),
            "min_confidence": float(self.settings.value("strategy/min_confidence", 0.55)),
            "signal_amount": float(self.settings.value("strategy/signal_amount", 1.0)),
        }
        self.equity_repository = None
        self.agent_decision_repository = None

        # === Multi-Strategy Support ===
        self.multi_strategy_enabled = str(
            self.settings.value("strategy/multi_strategy_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.max_symbol_strategies = max(
            1,
            min(10, int(self.settings.value("strategy/max_symbol_strategies", 3) or 3)),
        )
        self.symbol_strategy_assignments = self._load_strategy_symbol_payload("strategy/symbol_assignments")
        self.symbol_strategy_rankings = self._load_strategy_symbol_payload("strategy/symbol_rankings")
        self.symbol_strategy_locks = self._load_strategy_symbol_lock_payload(
            "strategy/symbol_assignment_locks",
            fallback_symbols=list(self.symbol_strategy_assignments.keys()),
        )

        # === Strategy Auto-Assignment ===
        self.strategy_auto_assignment_enabled = str(
            self.settings.value("strategy/auto_assignment_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.strategy_auto_assignment_ready = not self.strategy_auto_assignment_enabled
        self.strategy_auto_assignment_in_progress = False
        self.strategy_auto_assignment_progress = {
            "completed": 0,
            "total": 0,
            "current_symbol": "",
            "timeframe": self.time_frame,
            "updated_at": "",
            "message": "Waiting to scan symbols.",
            "failed_symbols": [],
        }
        self._strategy_auto_assignment_task = None
        self._strategy_auto_assignment_deferred_task = None
        self._strategy_ranking_executor = None
        self._terminal_runtime_restore_task = None

        # === User Trade Risk Management ===
        self.user_trade_autocorrect_enabled = str(
            self.settings.value("risk/user_trade_autocorrect_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.user_trade_min_reward_risk = max(
            1.0,
            float(self.settings.value("risk/user_trade_min_reward_risk", 1.5) or 1.5),
        )
        self.user_trade_bias_confidence_threshold = max(
            0.5,
            min(0.95, float(self.settings.value("risk/user_trade_bias_confidence_threshold", 0.72) or 0.72)),
        )
        self.user_trade_risk_monitor_enabled = str(
            self.settings.value("risk/user_trade_risk_monitor_enabled", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.user_trade_risk_monitor_grace_seconds = max(
            15.0,
            float(self.settings.value("risk/user_trade_risk_monitor_grace_seconds", 60.0) or 60.0),
        )
        self.user_trade_risk_monitor_adverse_move_fraction = max(
            0.1,
            min(
                1.0,
                float(self.settings.value("risk/user_trade_risk_monitor_adverse_move_fraction", 0.35) or 0.35),
            ),
        )
        self._pending_user_trade_reviews = {}
        self._pending_user_trade_review_task = None
        self._monitored_user_trade_positions = {}

        # === Portfolio and Account State ===
        self.portfolio = None
        self.ai_signal = None
        self.balances = {}
        self.balance = {}
        self._position_manager = PositionManager()  # Track positions with SL/TP

        # === Market Data Infrastructure ===
        self.ticker_stream = TickerStream()
        self._performance_recorded_orders = set()
        self.news_service = NewsService(
            logger=self.logger,
            enabled=self.news_enabled,
            feed_url_template=self.news_feed_url,
        )
        self.voice_service = VoiceService(
            logger=self.logger,
            voice_name=self.voice_name,
            recognition_provider=self.voice_provider,
        )
        self._trade_close_entry_cache = {}
        self.email_trade_notification_service = None
        self.sms_trade_notification_service = None
        self._configure_trade_close_notification_services()
        self._news_cache = {}
        self._news_inflight = {}

        # === Data Buffers and History ===
        self.limit = self.MAX_HISTORY_LIMIT
        self.runtime_history_limit = int(getattr(TradingCore, "MAX_RUNTIME_ANALYSIS_BARS", 500) or 500)
        self.initial_capital = 10000

        self.candle_buffer = CandleBuffer(max_length=self.limit)
        self.candle_buffers = {}
        self.orderbook_buffer = OrderBookBuffer()
        self.ticker_buffer = TickerBuffer(max_length=self.limit)
        self._orderbook_tasks = {}
        self._orderbook_last_request_at = {}
        self._recent_trades_cache = {}
        self._recent_trades_tasks = {}
        self._recent_trades_last_request_at = {}
        self._symbol_universe_tiers = {}
        self._symbol_universe_rotation_cursor = 0

        # === Trading State ===
        self.symbols = ["BTC/USDT", "ETH/USDT", "XLM/USDT"]
        self.symbol_catalog = list(self.symbols)

        self.connected = False
        self.config = None
        self._session_closing = False

        # === Schedulers ===
        self.scheduler = None
        self.event_scheduler = None

        # === Cache Maintenance ===
        self._cache_trim_timer = QTimer()
        self._cache_trim_timer.timeout.connect(self._trim_application_caches)
        self._cache_trim_timer.setInterval(300000)  # 5 minutes
        self._cache_trim_timer.setSingleShot(False)

        # === Final Initialization ===
        try:
            self._setup_paths()
            self._setup_data()
            self._setup_ui(self.controller)
            self.setWindowTitle(self.tr("app.window_title"))
            safe_timer_start(self._cache_trim_timer, 300000)  # Start cache trimming after successful initialization
        except Exception as exc:
            traceback.print_exc()
            startup_message = self._friendly_startup_error(exc)
            if startup_message:
                if getattr(self, "logger", None) is not None:
                    self.logger.error(startup_message)
                try:
                    sys.stderr.write(f"{startup_message}\n")
                except Exception:
                    traceback.print_exc()


    # === Translation and Localization Methods ===

    def tr(self, key, **kwargs):
        """Translate UI text using i18n system."""
        return translate(self.language_code, key, **kwargs)

    def translate_runtime_text(self, text, rich=False):
        """Translate runtime text (e.g., market data, status messages)."""
        translator = translate_rich_text if rich else translate_text
        return translator(self.language_code, text)

    # === Workspace Access Methods ===

    def refresh_license_status(self):
        """Return the current workspace access snapshot."""
        self.license_status = self.get_license_status()
        return dict(self.license_status)

    def get_license_status(self):
        """Return the current workspace access status - supports full license, 30-day trial, and fallback."""
        merged = self._server_license_status_snapshot()
        # Check for active trial or full license (30-day trial = full access)
        trial_days_remaining = self._get_trial_days_remaining()
        if trial_days_remaining is not None and trial_days_remaining > 0:
            # Trial is active - grant full access
            merged["tier"] = "trial"
            merged["plan_name"] = f"30-Day Trial ({trial_days_remaining} days remaining)"
            merged["is_premium"] = True
            merged["features"] = sorted(set(self.TRADEADVISER_RESTRICTED_FEATURES))
            merged["allowed_features"] = merged["features"]
        elif trial_days_remaining == 0:
            # Trial expired
            merged["tier"] = "expired"
            merged["plan_name"] = "Trial Expired"
            merged["is_premium"] = False
        # Full license always has all features
        if merged.get("tier") != "expired":
            self.allowed_features = set(merged.get("features") or merged.get("allowed_features") or self.TRADEADVISER_RESTRICTED_FEATURES)
        self.license_status = dict(merged)
        return dict(self.license_status)

    def license_allows(self, feature):
        return bool(self.is_feature_enabled(feature))

    def is_feature_enabled(self, feature):
        normalized_feature = self._normalized_tradeadviser_feature_name(feature)
        if normalized_feature not in self.TRADEADVISER_RESTRICTED_FEATURES:
            return True
        return normalized_feature in set(getattr(self, "allowed_features", set()) or set())

    def feature_message(self, feature):
        normalized_feature = self._normalized_tradeadviser_feature_name(feature)
        if self.license_allows(feature):
            return f"{normalized_feature.replace('_', ' ').title()} is available."
        else:
            return f"{normalized_feature.replace('_', ' ').title()} requires an active license or trial."

    def _get_trial_days_remaining(self) -> int | None:
        """Get the number of days remaining in the trial period. None if no trial, 0 if expired."""
        try:
            # Check desktop license file if exists
            license_file = pathlib.Path(self.config_dir or ".") / ".license_trial"
            if license_file.exists():
                data = json.loads(license_file.read_text())
                start_date = datetime.fromisoformat(data.get("start_date", ""))
                trial_duration = int(data.get("duration_days", 30))
                end_date = start_date + timedelta(days=trial_duration)
                days_remaining = (end_date - datetime.now()).days
                if days_remaining > 0:
                    return days_remaining
                else:
                    return 0
        except Exception:
            pass
        # Check server license status
        status = getattr(self, "license_status", {})
        if status.get("tier") == "trial":
            return status.get("days_remaining", 30)
        return None

    def _normalized_tradeadviser_feature_name(self, feature):
        """Normalize feature name to TradeAdviser server standard."""
        normalized = str(feature or "").strip().lower()
        return self.TRADEADVISER_FEATURE_ALIASES.get(normalized, normalized)

    # === Server Configuration Methods ===

    def _server_sync_profile(self):
        """Load server sync profile from platform sync service."""
        try:
            profile = dict(self.platform_sync_service.load_profile() or {})
        except Exception:
            profile = {}
        return profile

    def _is_server_profile_configured(self, profile=None):
        """Check if server profile has required configuration (base_url, email, password)."""
        active_profile = dict(profile or self._server_sync_profile() or {})
        return bool(
            str(active_profile.get("base_url") or "").strip()
            and str(active_profile.get("email") or "").strip()
            and str(active_profile.get("password") or "").strip()
        )

    def _is_server_feature_gate_active(self):
        """Check if TradeAdviser server integration is configured."""
        return self._is_server_profile_configured()

    def _configure_server_client(self, profile=None):
        """Initialize and configure TradeAdviser server client."""
        active_profile = dict(profile or self._server_sync_profile() or {})
        server = getattr(self, "server", None)
        if server is None:
            server = TradeAdviserClient(base_url=str(active_profile.get("base_url") or "").strip())
            self.server = server
        server.configure(
            base_url=str(active_profile.get("base_url") or "").strip(),
            email=str(active_profile.get("email") or "").strip(),
            password=str(active_profile.get("password") or "").strip(),
        )
        return server, active_profile

    def _server_license_status_snapshot(self, base_status=None):
        allowed_features = sorted(set(getattr(self, "allowed_features", set()) or set()))
        status = {
            "base_status": base_status,
            "tier": "workspace",
            "state": "active",
            "status": "active",
            "plan_name": "Workspace Access",
            "badge": "OPEN",
            "summary": "Open workspace access",
            "description": (
                f"TradeAdviser Server integration is configured via {str((self._server_sync_profile() or {}).get('base_url') or '').strip()}."
                if self._is_server_feature_gate_active()
                else "Desktop features are available without license checks."
            ).strip(),
            "days_remaining": None,
            "expires_at": None,
            "is_premium": True,
            "features": allowed_features,
            "allowed_features": allowed_features,
            "source": "workspace",
            "server_url": str((self._server_sync_profile() or {}).get("base_url") or "").strip(),
        }
        return status

    async def initialize_license(self, force_login=False):
        server, profile = self._configure_server_client()
        self.server_feature_gate_enabled = self._is_server_profile_configured(profile)
        self.allowed_features = set(self.TRADEADVISER_RESTRICTED_FEATURES)
        if not self.server_feature_gate_enabled:
            self.server_performance_snapshot = {}
            self.server_strategy_feedback = {}
            return self.refresh_license_status()

        try:
            if force_login or not server.is_authenticated():
                await server.login()
            return self.refresh_license_status()
        except Exception as exc:
            self.allowed_features = set(self.TRADEADVISER_RESTRICTED_FEATURES)
            self.server_performance_snapshot = {}
            self.server_strategy_feedback = {}
            self.logger.warning("TradeAdviser workspace initialization failed: %s", exc)
            return self.refresh_license_status()

    def _server_feedback_multiplier(self, strategy_name):
        normalized = Strategy.normalize_strategy_name(strategy_name)
        feedback_map = dict(getattr(self, "server_strategy_feedback", {}) or {})
        try:
            return max(0.75, min(1.25, float(feedback_map.get(normalized, 1.0) or 1.0)))
        except Exception:
            return 1.0

    async def refresh_server_performance_feedback(self):
        if not self._is_server_feature_gate_active():
            return {}
        if not self.is_feature_enabled("trading"):
            return {}

        server = getattr(self, "server", None)
        if server is None:
            return {}

        try:
            performance = await server.get_performance()
        except Exception as exc:
            self.logger.debug("Unable to fetch TradeAdviser performance feedback: %s", exc)
            return {}

        strategy_feedback = {}
        for strategy_name, stats in dict(performance.get("strategy_stats") or {}).items():
            normalized_strategy = Strategy.normalize_strategy_name(strategy_name)
            try:
                win_rate = float(stats.get("win_rate", 0.0) or 0.0)
            except Exception:
                win_rate = 0.0
            try:
                avg_pnl = float(stats.get("avg_pnl", 0.0) or 0.0)
            except Exception:
                avg_pnl = 0.0

            multiplier = 1.0
            if win_rate < 0.40 or avg_pnl < 0.0:
                multiplier = 0.90
            elif win_rate >= 0.55 and avg_pnl >= 0.0:
                multiplier = 1.05
            strategy_feedback[normalized_strategy] = multiplier

        self.server_performance_snapshot = dict(performance or {})
        self.server_strategy_feedback = dict(strategy_feedback)

        trading_system = getattr(self, "trading_system", None)
        refresher = getattr(trading_system, "refresh_strategy_preferences", None) if trading_system is not None else None
        if callable(refresher):
            try:
                refresher()
            except Exception:
                self.logger.debug("Unable to refresh strategy preferences from TradeAdviser feedback", exc_info=True)
        return dict(performance or {})

    def _server_trade_payload(self, trade):
        if not isinstance(trade, dict):
            return None
        symbol = self._normalize_strategy_symbol_key(trade.get("symbol"))
        if not symbol:
            return None
        side = str(trade.get("side") or "").strip().lower()
        if side not in {"buy", "sell"}:
            return None

        amount = trade.get("size", trade.get("amount"))
        try:
            amount_value = float(amount)
        except Exception:
            return None
        if amount_value <= 0:
            return None

        pnl = trade.get("pnl")
        try:
            pnl_value = float(pnl if pnl not in (None, "") else 0.0)
        except Exception:
            pnl_value = 0.0

        strategy_name = str(
            trade.get("strategy_name")
            or trade.get("strategy")
            or "Execution"
        ).strip() or "Execution"

        timestamp = trade.get("timestamp")
        if isinstance(timestamp, datetime):
            timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
        else:
            timestamp_text = str(timestamp or datetime.now(timezone.utc).isoformat()).strip()

        return {
            "symbol": symbol,
            "side": side,
            "amount": amount_value,
            "pnl": pnl_value,
            "strategy": strategy_name,
            "timestamp": timestamp_text,
        }

    def _server_signal_payload_from_runtime_event(self, event_type, data):
        if str(event_type or "").strip() != str(EventType.SIGNAL):
            return None
        payload = dict(data or {})
        signal_payload = dict(payload.get("signal") or {}) if isinstance(payload.get("signal"), dict) else {}
        symbol = self._normalize_strategy_symbol_key(payload.get("symbol") or signal_payload.get("symbol"))
        if not symbol:
            return None
        strategy_name = str(
            signal_payload.get("strategy_name")
            or payload.get("selected_strategy")
            or payload.get("strategy_name")
            or "Signal Engine"
        ).strip() or "Signal Engine"
        timeframe = str(
            payload.get("timeframe")
            or signal_payload.get("timeframe")
            or getattr(self, "time_frame", "1h")
            or "1h"
        ).strip() or "1h"
        confidence = payload.get("confidence", signal_payload.get("confidence"))
        try:
            confidence_value = max(0.0, min(1.0, float(confidence if confidence not in (None, "") else 0.0)))
        except Exception:
            confidence_value = 0.0

        return {
            "symbol": symbol,
            "strategy": strategy_name,
            "confidence": confidence_value,
            "timeframe": timeframe,
            "timestamp": str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat()).strip(),
        }

    async def _sync_trade_to_server(self, trade):
        if not self._is_server_feature_gate_active() or not self.is_feature_enabled("trading"):
            return None
        payload = self._server_trade_payload(trade)
        if payload is None:
            return None
        try:
            result = await self.server.send_trade(payload)
            await self.refresh_server_performance_feedback()
            return result
        except Exception as exc:
            self.logger.debug("Unable to sync trade to TradeAdviser Server: %s", exc)
            return None

    async def _sync_signal_to_server(self, event_type, data):
        if not self._is_server_feature_gate_active() or not self.is_feature_enabled("ml_signals"):
            return None
        payload = self._server_signal_payload_from_runtime_event(event_type, data)
        if payload is None:
            return None
        try:
            return await self.server.send_signal(payload)
        except Exception as exc:
            self.logger.debug("Unable to sync signal to TradeAdviser Server: %s", exc)
            return None

    def _friendly_initialization_error(self, exc):
        message = str(exc or "").strip()
        lowered = message.lower()

        if "could not contact dns servers" in lowered or "dns lookup failed" in lowered:
            return (
                "Broker connection failed because DNS resolution is not working on this machine right now. "
                "Check your internet connection, DNS settings, VPN, proxy, or firewall, then try again."
            )

        if "cannot connect to host" in lowered:
            return (
                "Broker connection failed before login completed. "
                "Check your internet connection, VPN, proxy, or firewall, then try again.\n\n"
                f"Details: {message}"
            )

        if "binance.com is not available for us customers" in lowered:
            return "Binance.com is not available for US customers in Sopotek. Choose Binance US or switch the customer region to Outside US."

        if "binance us is only available for us customers" in lowered:
            return "Binance US is only available for US customers in Sopotek. Choose Binance for non-US customers or switch the customer region to US."

        if "restricted location" in lowered and "testnet.binance.vision" in lowered:
            return (
                "Binance US sandbox routing is unavailable from this location. "
                "For Binance US, use LIVE mode for a real exchange session, or use PAPER mode so Sopotek runs a local "
                "paper broker with Binance US market data instead of the Binance global testnet."
            )

        if "api-key format invalid" in lowered or "\"code\":-2014" in lowered or "code': -2014" in lowered:
            return (
                "The broker rejected the API key format. For Binance US, use a Binance US API key and secret pair, "
                "not Binance.com credentials. Also make sure the key and secret were pasted without spaces or line breaks."
            )

        if "coinbase" in lowered and "passphrase" in lowered:
            return (
                "Coinbase Advanced Trade in Sopotek uses the API key name and private key."
            )

        if "coinbase" in lowered and any(
                token in lowered
                for token in ("unauthorized", "authentication", "invalid signature", "forbidden", "401")
        ):
            return (
                "Coinbase authentication failed. In Sopotek's Coinbase mode, use Coinbase Advanced Trade credentials: "
                "put the API key name like organizations/.../apiKeys/... in the first field and the privateKey PEM in "
                "the second field. If you pasted the private key from JSON, keep the full BEGIN/END block or the "
                "escaped \\n form."
            )

        if "schwab" in lowered and "redirect_uri" in lowered:
            return (
                "Schwab authentication failed because the callback URL did not match the app setup. "
                "Check the redirect URI in the Schwab Developer Portal and in the Sopotek dashboard, then try again.\n\n"
                f"Details: {message}"
            )

        if "oauth callback state did not match" in lowered:
            return (
                "The broker sign-in response could not be verified safely. "
                "Restart the Schwab sign-in flow and make sure the final redirect URL comes from the same browser session."
            )

        return message or "Unknown initialization error"

    def _friendly_startup_error(self, exc):
        message = str(exc or "").strip()
        lowered = message.lower()
        if not lowered:
            return ""

        if "access denied for user" in lowered and "mysql" in lowered:
            masked_database_url = self._masked_database_url(
                getattr(self, "database_url", "") or _remote_database_url_from_env()
            )
            uses_local_compose_mysql = "@mysql:" in masked_database_url
            recovery_hint = ""
            if uses_local_compose_mysql:
                recovery_hint = (
                    " If this is the local Docker stack, the persisted `mysql_data` volume was likely initialized "
                    "with older `MYSQL_USER`, `MYSQL_PASSWORD`, or `MYSQL_ROOT_PASSWORD` values. Reuse the original "
                    "credentials or recreate the local MySQL volume with `docker compose down -v` before starting "
                    "the stack again."
                )

            details_suffix = f"\n\nConfigured database: {masked_database_url}" if masked_database_url else ""
            return (
                "Startup could not connect to the configured MySQL database because the server rejected the username "
                f"or password.{recovery_hint}\n\nDetails: {message}{details_suffix}"
            )

        return ""

    def _should_route_crypto_paper_to_local_paper_broker(self, config):
        broker_cfg = getattr(config, "broker", None)
        if broker_cfg is None:
            return False
        broker_type = str(getattr(broker_cfg, "type", "") or "").strip().lower()
        exchange = str(getattr(broker_cfg, "exchange", "") or "").strip().lower()
        mode = str(getattr(broker_cfg, "mode", "") or "").strip().lower()
        return broker_type == "crypto" and exchange not in {"", "paper"} and mode == "paper"

    def _configure_local_crypto_paper_session(self, config):
        broker_cfg = getattr(config, "broker", None)
        if broker_cfg is None:
            return []

        exchange = str(getattr(broker_cfg, "exchange", "") or "").strip().lower()
        params = dict(getattr(broker_cfg, "params", None) or {})
        configured = params.get("paper_data_exchanges") or params.get("market_data_exchanges")
        if isinstance(configured, str):
            configured_exchanges = [item.strip().lower() for item in configured.split(",") if item.strip()]
        elif isinstance(configured, (list, tuple, set)):
            configured_exchanges = [str(item).strip().lower() for item in configured if str(item).strip()]
        else:
            configured_exchanges = []

        ordered_exchanges = []
        for candidate in [exchange, *configured_exchanges, *PaperBroker.DEFAULT_MARKET_DATA_EXCHANGES]:
            normalized = str(candidate or "").strip().lower()
            if normalized and normalized not in ordered_exchanges:
                ordered_exchanges.append(normalized)

        params["paper_data_exchange"] = exchange
        params["paper_data_exchanges"] = ordered_exchanges
        broker_cfg.params = params
        self.paper_data_exchange = exchange
        self.paper_data_exchanges = list(ordered_exchanges)
        return ordered_exchanges

    def _build_broker_for_login(self, config):
        if self._should_route_crypto_paper_to_local_paper_broker(config):
            exchanges = self._configure_local_crypto_paper_session(config)
            exchange = str(getattr(getattr(config, "broker", None), "exchange", "") or "").strip().lower()
            self.logger.info(
                "Routing crypto paper session through PaperBroker exchange=%s market_data_exchanges=%s",
                exchange,
                exchanges,
            )
            return PaperBroker(self)
        return BrokerFactory.create(config)

    def _broker_is_connected(self, broker):
        if broker is None:
            return False
        for attr in ("_connected", "connected", "is_connected"):
            value = getattr(broker, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            if isinstance(value, bool):
                return value
        return False

    def set_language(self, language_code):
        """Change application language and refresh all language-dependent UI elements."""
        previous_language = self.language_code
        normalized = normalize_language_code(language_code)
        if normalized == self.language_code:
            return

        self.language_code = normalized
        self.settings.setValue("ui/language", normalized)
        self.setWindowTitle(self.tr("app.window_title"))
        self.language_changed.emit(normalized)
        self._refresh_open_language_widgets(previous_language)

    def _refresh_open_language_widgets(self, previous_language=None):
        app = QApplication.instance()
        if app is None:
            return
        for widget in app.topLevelWidgets():
            try:
                if hasattr(widget, "apply_language") and callable(widget.apply_language):
                    widget.apply_language()
                apply_runtime_translations(
                    widget,
                    self.language_code,
                    previous_language=previous_language,
                )
            except Exception:
                continue

    def eventFilter(self, watched, event):
        """
        Global event filter for language and UI updates.

        Monitors Show events to apply language translations to newly visible widgets.
        Safely checks object validity using shiboken6 before accessing.
        """
        try:
            if getattr(self, "_event_filter_disabled", False):
                return False
            if watched is None or event is None:
                return False
            if not shiboken6.isValid(watched) or not shiboken6.isValid(event):
                return False
            if event.type() == QEvent.Type.Show and self.language_code != DEFAULT_LANGUAGE:
                try:
                    is_window = getattr(watched, "isWindow", None)
                    if (
                            callable(is_window)
                            and is_window()
                            and not bool(getattr(watched, "_ui_shutting_down", False))
                    ):
                        apply_runtime_translations(watched, self.language_code)
                except BaseException as exc:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    pass
            return super().eventFilter(watched, event)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.debug("AppController eventFilter failed", exc_info=True)
            return False

    def _remove_app_event_filter(self):
        """Remove global event filter from application instance."""
        app = getattr(self, "_app_event_filter_target", None)
        self._app_event_filter_target = None
        self._event_filter_disabled = True
        if app is None:
            return
        try:
            app.removeEventFilter(self)
        except Exception:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.debug("AppController event filter removal failed", exc_info=True)

    def closeEvent(self, event):
        """Handle application window close event."""
        self._remove_app_event_filter()
        super().closeEvent(event)

    def _setup_paths(self):
        """Initialize required filesystem directories."""
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)

    @staticmethod
    def _resolve_initial_storage_preferences(settings):
        """
        Resolve database storage mode and connection URL.

        Reads from environment variables first, then settings.
        Supports 'local' (SQLite) or 'remote' (PostgreSQL/MySQL) modes.

        Returns:
            Tuple of (mode, database_url)
        """
        remote_env_url = _remote_database_url_from_env()
        env_mode = _storage_mode_from_env()
        has_mode = bool(getattr(settings, "contains", lambda _key: False)("storage/database_mode"))
        has_url = bool(getattr(settings, "contains", lambda _key: False)("storage/database_url"))

        default_mode = env_mode or ("remote" if remote_env_url and not has_mode else "local")
        mode = str(settings.value("storage/database_mode", default_mode) or default_mode).strip().lower()
        if env_mode:
            mode = env_mode
        if mode not in {"local", "remote"}:
            mode = default_mode

        default_url = remote_env_url if mode == "remote" and (env_mode or not has_url) else ""
        database_url = str(settings.value("storage/database_url", default_url) or default_url).strip()
        if mode == "remote" and remote_env_url:
            database_url = remote_env_url
        return mode, database_url

    def _setup_data(self):
        """
        Initialize data structures and services:
        - Configure database connectivity
        - Initialize performance tracking
        - Restore persisted performance state
        """
        require_remote_storage = (
                str(getattr(self, "database_mode", "local") or "local").strip().lower() == "remote"
                and bool(_storage_mode_from_env() or _remote_database_url_from_env())
        )
        self.configure_storage_database(
            database_mode=getattr(self, "database_mode", "local"),
            database_url=getattr(self, "database_url", ""),
            persist=False,
            raise_on_error=require_remote_storage,
        )
        self.historical_data = pd.DataFrame(
            columns=["symbol", "timestamp", "open", "high", "low", "close", "volume"]
        )
        self.performance_engine = PerformanceEngine()
        self._restore_performance_state()

    def _performance_trade_payload_from_record(self, trade):
        """
        Convert trade database record to performance tracking payload.

        Extracts all relevant trade information from database record for performance analysis.

        Args:
            trade: Trade record from database

        Returns:
            dict: Normalized trade payload including exchange, symbol, side, price, size,
                  order type, status, PnL, strategy name, fees, and slippage
        """
        return {
            "exchange": getattr(trade, "exchange", ""),
            "symbol": getattr(trade, "symbol", ""),
            "side": getattr(trade, "side", ""),
            "source": getattr(trade, "source", ""),
            "price": getattr(trade, "price", ""),
            "size": getattr(trade, "quantity", ""),
            "order_type": getattr(trade, "order_type", ""),
            "status": getattr(trade, "status", ""),
            "order_id": getattr(trade, "order_id", ""),
            "timestamp": getattr(trade, "timestamp", ""),
            "pnl": getattr(trade, "pnl", ""),
            "strategy_name": getattr(trade, "strategy_name", ""),
            "reason": getattr(trade, "reason", ""),
            "confidence": getattr(trade, "confidence", ""),
            "expected_price": getattr(trade, "expected_price", ""),
            "spread_bps": getattr(trade, "spread_bps", ""),
            "slippage_bps": getattr(trade, "slippage_bps", ""),
            "fee": getattr(trade, "fee", ""),
        }

    def _performance_scope(self):
        """Get current performance scope (exchange and account).

        Returns:
            Tuple of (exchange_code, account_label) for filtering performance data
        """
        exchange = self._active_exchange_code() if hasattr(self, "_active_exchange_code") else None
        normalized_exchange = str(exchange or "").strip().lower() or None
        account_label = self.current_account_label() if hasattr(self, "current_account_label") else None
        account_text = str(account_label or "").strip()
        if account_text.lower() == "not set":
            account_text = ""
        return normalized_exchange, (account_text or None)

    def _performance_history_settings_key(self):
        """Generate settings key for storing performance history.

        Includes exchange and account in key to support multi-exchange/account tracking.
        """
        exchange, account_label = self._performance_scope()
        if not exchange:
            return "performance/equity_history"
        account_segment = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(account_label or "default")).strip("._") or "default"
        return f"performance/equity_history/{exchange}/{account_segment}"

    def _trade_row_exchange_value(self, trade):
        """Extract exchange value from trade record.

        Handles both dict and object trade representations.
        """
        if isinstance(trade, dict):
            exchange = trade.get("exchange")
        else:
            exchange = getattr(trade, "exchange", None)
        return str(exchange or "").strip().lower() or None

    def _repository_trade_rows_for_active_exchange(self, limit=200):
        """Retrieve trade records from repository filtered by active exchange.

        Args:
            limit: Maximum number of trades to retrieve

        Returns:
            List of trade records for current active exchange
        """
        repository = getattr(self, "trade_repository", None)
        if repository is None or not hasattr(repository, "get_trades"):
            return []

        exchange, _account_label = self._performance_scope()
        if not exchange:
            return []

        try:
            return list(repository.get_trades(limit=limit, exchange=exchange) or [])
        except TypeError:
            try:
                rows = list(repository.get_trades(limit=limit) or [])
            except Exception:
                self.logger.debug("Trade DB load failed for exchange-scoped performance history", exc_info=True)
                return []
            row_exchanges = [self._trade_row_exchange_value(row) for row in rows]
            if any(row_exchanges):
                rows = [
                    row
                    for row, row_exchange in zip(rows, row_exchanges)
                    if row_exchange == exchange
                ]
            return rows
        except Exception:
            self.logger.debug("Trade DB load failed for exchange-scoped performance history", exc_info=True)
            return []

    def _load_persisted_performance_history(self):
        settings = getattr(self, "settings", None)
        if settings is None:
            return []

        settings_key = self._performance_history_settings_key()
        if not settings_key:
            return []

        settings_keys = [settings_key]
        legacy_key = "performance/equity_history"
        if legacy_key not in settings_keys:
            settings_keys.append(legacy_key)

        for key in settings_keys:
            raw_value = settings.value(key, "[]")
            try:
                payload = json.loads(raw_value or "[]")
            except Exception:
                payload = raw_value if isinstance(raw_value, list) else []

            history = []
            for item in list(payload or [])[-2000:]:
                timestamp = None
                value = item
                if isinstance(item, dict):
                    timestamp = item.get("timestamp")
                    value = item.get("equity", item.get("value"))

                try:
                    numeric = float(value)
                except Exception:
                    continue
                if not pd.notna(numeric):
                    continue

                if timestamp in (None, ""):
                    history.append(numeric)
                else:
                    history.append({"equity": numeric, "timestamp": timestamp})
            if history:
                return history
        return []

    def _persist_performance_history(self):
        perf = getattr(self, "performance_engine", None)
        settings = getattr(self, "settings", None)
        if perf is None or settings is None:
            return
        settings_key = self._performance_history_settings_key()
        if not settings_key:
            return

        equity_values = list(getattr(perf, "equity_curve", []) or [])[-2000:]
        equity_timestamps = list(getattr(perf, "equity_timestamps", []) or [])[-len(equity_values):]

        history = []
        for index, value in enumerate(equity_values):
            try:
                numeric = float(value)
            except Exception:
                continue
            if not pd.notna(numeric):
                continue

            timestamp = equity_timestamps[index] if index < len(equity_timestamps) else None
            if timestamp in (None, ""):
                history.append(numeric)
            else:
                try:
                    history.append({"equity": numeric, "timestamp": float(timestamp)})
                except Exception:
                    history.append({"equity": numeric, "timestamp": timestamp})
        settings.setValue(settings_key, json.dumps(history))

    def _load_persisted_equity_history_from_repository(self, limit=2000):
        repository = getattr(self, "equity_repository", None)
        if repository is None or not hasattr(repository, "get_snapshots"):
            return []

        exchange = self._active_exchange_code() if hasattr(self, "_active_exchange_code") else None
        if not str(exchange or "").strip():
            return []
        account_label = self.current_account_label() if hasattr(self, "current_account_label") else None
        if str(account_label or "").strip().lower() == "not set":
            account_label = None

        try:
            snapshots = repository.get_snapshots(limit=limit, exchange=exchange, account_label=account_label)
        except TypeError:
            snapshots = repository.get_snapshots(limit=limit)
        except Exception:
            self.logger.debug("Unable to restore equity snapshot ledger", exc_info=True)
            return []

        history = []
        for item in reversed(list(snapshots or [])):
            equity = getattr(item, "equity", None)
            if equity in (None, ""):
                continue
            timestamp = getattr(item, "timestamp", None)
            if isinstance(timestamp, datetime):
                timestamp = timestamp.replace(tzinfo=timezone.utc).timestamp() if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc).timestamp()
            history.append({"equity": float(equity), "timestamp": timestamp})
        return history

    def _persist_equity_snapshot(self, equity, balances=None):
        repository = getattr(self, "equity_repository", None)
        if repository is None or not hasattr(repository, "save_snapshot"):
            return None

        balance_payload = balances if isinstance(balances, dict) else getattr(self, "balances", {}) or {}
        exchange = self._active_exchange_code() if hasattr(self, "_active_exchange_code") else None
        account_label = self.current_account_label() if hasattr(self, "current_account_label") else None
        if str(account_label or "").strip().lower() == "not set":
            account_label = None

        balance_value = self._balance_metric_value(
            balance_payload,
            "balance",
            "cash",
            "equity",
            "nav",
            "net_liquidation",
            "account_value",
        )
        free_margin = self._safe_balance_metric(balance_payload.get("free")) if isinstance(balance_payload, dict) else None
        used_margin = self._safe_balance_metric(balance_payload.get("used")) if isinstance(balance_payload, dict) else None

        try:
            return repository.save_snapshot(
                equity=float(equity),
                exchange=exchange,
                account_label=account_label,
                balance=balance_value,
                free_margin=free_margin,
                used_margin=used_margin,
                payload=balance_payload,
            )
        except Exception:
            self.logger.debug("Unable to persist equity snapshot ledger", exc_info=True)
            return None

    def _restore_performance_state(self):
        perf = getattr(self, "performance_engine", None)
        if perf is None:
            return

        equity_history = self._load_persisted_equity_history_from_repository(limit=2000)
        if not equity_history:
            equity_history = self._load_persisted_performance_history()

        if hasattr(perf, "load_equity_history"):
            perf.load_equity_history(equity_history)

        stored = list(reversed(self._repository_trade_rows_for_active_exchange(limit=500)))

        trades = [self._performance_trade_payload_from_record(item) for item in stored]
        if hasattr(perf, "load_trades"):
            perf.load_trades(trades)
        else:
            perf.trades = list(trades)

    def _agent_decision_record_to_payload(self, item):
        payload = {}
        raw_payload = getattr(item, "payload_json", None)
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except Exception:
                payload = {"raw": str(raw_payload)}

        timestamp = getattr(item, "timestamp", None)
        timestamp_value = None
        timestamp_label = ""
        if isinstance(timestamp, datetime):
            normalized = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
            timestamp_value = normalized.timestamp()
            timestamp_label = normalized.strftime("%Y-%m-%d %H:%M:%S UTC")
        elif timestamp not in (None, ""):
            timestamp_label = str(timestamp)

        return {
            "id": getattr(item, "id", None),
            "decision_id": str(getattr(item, "decision_id", "") or "").strip(),
            "exchange": getattr(item, "exchange", None),
            "account_label": getattr(item, "account_label", None),
            "symbol": str(getattr(item, "symbol", "") or "").strip().upper(),
            "agent_name": str(getattr(item, "agent_name", "") or "").strip(),
            "stage": str(getattr(item, "stage", "") or "").strip(),
            "strategy_name": str(getattr(item, "strategy_name", "") or payload.get("strategy_name") or "").strip(),
            "timeframe": str(getattr(item, "timeframe", "") or payload.get("timeframe") or "").strip(),
            "side": str(getattr(item, "side", "") or payload.get("side") or "").strip().lower(),
            "confidence": getattr(item, "confidence", None),
            "approved": getattr(item, "approved", None),
            "reason": str(getattr(item, "reason", "") or payload.get("reason") or "").strip(),
            "timestamp": timestamp_value,
            "timestamp_label": timestamp_label,
            "payload": payload,
        }

    def _live_agent_memory_event_to_payload(self, event):
        if not isinstance(event, dict):
            return {}
        symbol = self._normalize_strategy_symbol_key(event.get("symbol"))
        if not symbol:
            return {}
        payload = dict(event.get("payload") or {})
        timestamp_value, timestamp_label = _normalize_live_agent_timestamp(event.get("timestamp"))
        return {
            "decision_id": str(event.get("decision_id") or "").strip(),
            "symbol": symbol,
            "agent_name": str(event.get("agent") or "").strip(),
            "stage": str(event.get("stage") or "").strip(),
            "strategy_name": str(payload.get("strategy_name") or "").strip(),
            "timeframe": str(payload.get("timeframe") or "").strip(),
            "side": str(payload.get("side") or "").strip().lower(),
            "confidence": payload.get("confidence"),
            "approved": payload.get("approved"),
            "reason": str(payload.get("reason") or "").strip(),
            "timestamp": timestamp_value,
            "timestamp_label": timestamp_label,
            "payload": payload,
            "source": "live",
        }

    def _append_live_agent_decision_event(self, payload):
        if not isinstance(payload, dict):
            return []
        symbol = self._normalize_strategy_symbol_key(payload.get("symbol"))
        if not symbol:
            return []
        events_by_symbol = getattr(self, "_live_agent_decision_events", None)
        if not isinstance(events_by_symbol, dict):
            events_by_symbol = {}
            self._live_agent_decision_events = events_by_symbol
        events = events_by_symbol.setdefault(symbol, [])
        events.append(dict(payload, symbol=symbol))
        if len(events) > 250:
            del events[:-250]
        return list(events)

    def _append_live_agent_runtime_feed(self, payload):
        if not isinstance(payload, dict):
            return {}

        row = dict(payload)
        symbol = self._normalize_strategy_symbol_key(row.get("symbol"))
        if symbol:
            row["symbol"] = symbol

        row["kind"] = str(row.get("kind") or "runtime").strip().lower() or "runtime"
        row["message"] = str(row.get("message") or row.get("reason") or "").strip()
        row["stage"] = str(row.get("stage") or "").strip()
        row["agent_name"] = str(row.get("agent_name") or "").strip()
        row["event_type"] = str(row.get("event_type") or "").strip()
        row["strategy_name"] = str(row.get("strategy_name") or "").strip()
        row["timeframe"] = str(row.get("timeframe") or "").strip()
        row["decision_id"] = str(row.get("decision_id") or "").strip()

        timestamp_value, timestamp_label = _normalize_live_agent_timestamp(
            row.get("timestamp") if row.get("timestamp") not in (None, "") else datetime.now(timezone.utc)
        )
        row["timestamp"] = timestamp_value
        row["timestamp_label"] = str(row.get("timestamp_label") or timestamp_label or "").strip()
        if not row["timestamp_label"] and timestamp_value is not None:
            row["timestamp_label"] = datetime.fromtimestamp(timestamp_value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        feed = getattr(self, "_live_agent_runtime_feed", None)
        if not isinstance(feed, list):
            feed = []
            self._live_agent_runtime_feed = feed
        feed.append(row)
        if len(feed) > 500:
            del feed[:-500]
        return dict(row)

    def _latest_live_agent_decision_chain_for_symbol(self, symbol, limit=12):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if not normalized_symbol:
            return []
        rows = list((getattr(self, "_live_agent_decision_events", {}) or {}).get(normalized_symbol, []) or [])
        if not rows:
            return []
        latest_decision_id = str(rows[-1].get("decision_id") or "").strip()
        if latest_decision_id:
            rows = [row for row in rows if str(row.get("decision_id") or "").strip() == latest_decision_id]
        return [dict(row) for row in rows[-max(1, int(limit or 12)):]]

    def live_agent_runtime_feed(self, limit=200, symbol=None, kinds=None):
        rows = list(getattr(self, "_live_agent_runtime_feed", []) or [])

        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if normalized_symbol:
            rows = [
                dict(row)
                for row in rows
                if self._normalize_strategy_symbol_key((row or {}).get("symbol")) == normalized_symbol
            ]
        else:
            rows = [dict(row) for row in rows]

        if kinds:
            allowed_kinds = {
                str(kind or "").strip().lower()
                for kind in (kinds if isinstance(kinds, (list, tuple, set)) else [kinds])
                if str(kind or "").strip()
            }
            if allowed_kinds:
                rows = [row for row in rows if str(row.get("kind") or "").strip().lower() in allowed_kinds]

        try:
            limit_value = max(1, int(limit or 200))
        except Exception:
            limit_value = 200
        return list(reversed(rows[-limit_value:]))

    def _emit_agent_runtime_signal(self, payload):
        normalized_payload = self._append_live_agent_runtime_feed(payload)
        signal = getattr(self, "agent_runtime_signal", None)
        if signal is not None:
            try:
                signal.emit(dict(normalized_payload or payload or {}))
            except Exception:
                self.logger.debug("Unable to emit agent runtime signal", exc_info=True)

    def _handle_live_agent_memory_event(self, event):
        payload = self._live_agent_memory_event_to_payload(event)
        if not payload:
            return {}
        self._append_live_agent_decision_event(payload)
        runtime_payload = dict(payload)
        runtime_payload["kind"] = "memory"
        runtime_payload["message"] = (
            f"{payload.get('agent_name') or 'Agent'} {payload.get('stage') or 'updated'}"
            f" for {payload.get('symbol') or 'symbol'}"
        )
        if payload.get("reason"):
            runtime_payload["message"] = f"{runtime_payload['message']} | {payload.get('reason')}"
        self._emit_agent_runtime_signal(runtime_payload)
        return payload

    @staticmethod
    def _coerce_runtime_event_payload(data):
        if isinstance(data, dict):
            return dict(data)
        if is_dataclass(data):
            try:
                return asdict(data)
            except Exception:
                return {}
        if hasattr(data, "__dict__"):
            try:
                return {
                    str(key): value
                    for key, value in vars(data).items()
                    if not str(key).startswith("_")
                }
            except Exception:
                return {}
        try:
            return dict(data or {})
        except Exception:
            return {}

    def _agent_runtime_bus_message(self, event_type, data):
        payload = dict(data or {})
        signal_payload = dict(payload.get("signal") or {}) if isinstance(payload.get("signal"), dict) else {}
        review_payload = dict(payload.get("trade_review") or {}) if isinstance(payload.get("trade_review"), dict) else {}
        symbol = self._normalize_strategy_symbol_key(payload.get("symbol"))
        strategy_name = str(signal_payload.get("strategy_name") or review_payload.get("strategy_name") or payload.get("strategy_name") or "").strip()
        timeframe = str(payload.get("timeframe") or review_payload.get("timeframe") or payload.get("timeframe") or "").strip()
        side = str(signal_payload.get("side") or review_payload.get("side") or payload.get("side") or "").strip().upper()
        reason = str(review_payload.get("reason") or signal_payload.get("reason") or payload.get("reason") or "").strip()
        if event_type == EventType.SIGNAL:
            detail = f"{side or 'HOLD'} via {strategy_name or 'strategy'}"
            if timeframe:
                detail = f"{detail} ({timeframe})"
            return f"Signal selected for {symbol}: {detail}."
        if event_type == EventType.REASONING_DECISION:
            decision = str(payload.get("decision") or "NEUTRAL").strip().upper() or "NEUTRAL"
            confidence = payload.get("confidence")

            try:
                confidence_text = f" at {float(confidence):.2f} confidence"
            except Exception:
                confidence_text = ""
            return f"Reasoning engine marked {symbol} as {decision}{confidence_text}."
        if event_type == EventType.DECISION_EVENT:
            action = str(payload.get("action") or "HOLD").strip().upper() or "HOLD"
            profile_id = str(payload.get("profile_id") or "").strip()
            selected_strategy = str(payload.get("selected_strategy") or strategy_name or "").strip() or "strategy blend"
            confidence = payload.get("confidence")

            try:
                confidence_text = f" at {float(confidence):.2f} confidence"
            except Exception:
                confidence_text = ""
            profile_text = f" for profile {profile_id}" if profile_id else ""
            return f"TraderAgent chose {action} on {symbol} via {selected_strategy}{profile_text}{confidence_text}."
        if event_type == EventType.RISK_APPROVED:
            return f"Risk approved {side or 'trade'} for {symbol}."
        if event_type == EventType.EXECUTION_PLAN:
            execution_strategy = str(payload.get("execution_strategy") or "").strip() or "default routing"
            return f"Execution plan ready for {symbol}: {execution_strategy}."
        if event_type == EventType.ORDER_FILLED:
            status = str((payload.get("execution_result") or {}).get("status") or payload.get("status") or "filled").strip().lower()
            return f"Execution {status} for {symbol}."
        if event_type == EventType.RISK_ALERT:
            return reason or f"Risk blocked the trade for {symbol}."
        return reason or f"{event_type} for {symbol}."

    async def _handle_trading_agent_bus_event(self, event):
        data = self._coerce_runtime_event_payload(getattr(event, "data", {}) or {})
        symbol = self._normalize_strategy_symbol_key(data.get("symbol"))
        if not symbol:
            return
        event_type = str(getattr(event, "type", "") or "").strip()
        signal_payload = dict(data.get("signal") or {}) if isinstance(data.get("signal"), dict) else {}
        review_payload = dict(data.get("trade_review") or {}) if isinstance(data.get("trade_review"), dict) else {}
        metadata = dict(data.get("metadata") or {}) if isinstance(data.get("metadata"), dict) else {}
        applied_constraints = data.get("applied_constraints")
        if isinstance(applied_constraints, (list, tuple, set)):
            applied_constraints = [str(item).strip() for item in applied_constraints if str(item).strip()]
        elif str(applied_constraints or "").strip():
            applied_constraints = [str(applied_constraints).strip()]
        else:
            applied_constraints = []
        votes = dict(data.get("votes") or {}) if isinstance(data.get("votes"), dict) else {}
        features = dict(data.get("features") or {}) if isinstance(data.get("features"), dict) else {}
        selected_strategy = str(
            data.get("selected_strategy")
            or signal_payload.get("strategy_name")
            or review_payload.get("strategy_name")
            or data.get("strategy_name")
            or ""
        ).strip()
        action = str(data.get("action") or "").strip().upper()
        side = str(signal_payload.get("side") or review_payload.get("side") or data.get("side") or "").strip().lower()
        if not side and action in {"BUY", "SELL"}:
            side = action.lower()
        payload = {
            "kind": "bus",
            "event_type": event_type,
            "agent_name": str(getattr(event, "source", "") or data.get("agent_name") or "").strip(),
            "symbol": symbol,
            "decision_id": str(data.get("decision_id") or review_payload.get("decision_id") or "").strip(),
            "profile_id": str(data.get("profile_id") or metadata.get("profile_id") or "").strip(),
            "strategy_name": selected_strategy,
            "timeframe": str(data.get("timeframe") or review_payload.get("timeframe") or metadata.get("timeframe") or "").strip(),
            "stage": str(data.get("stage") or (action.lower() if action else "")).strip(),
            "action": action,
            "side": side,
            "price": data.get("price"),
            "quantity": data.get("quantity"),
            "confidence": data.get("confidence"),
            "model_probability": data.get("model_probability"),
            "applied_constraints": applied_constraints,
            "votes": votes,
            "features": features,
            "metadata": metadata,
            "reason": str(data.get("reasoning") or review_payload.get("reason") or signal_payload.get("reason") or data.get("reason") or "").strip(),
            "timestamp": data.get("timestamp") or getattr(event, "timestamp", None),
            "message": self._agent_runtime_bus_message(event_type, data),
            "payload": data,
        }
        self._append_live_agent_decision_event(payload)
        self._emit_agent_runtime_signal(payload)
        if event_type == EventType.SIGNAL:
            await self._create_task(self._sync_signal_to_server(event_type, data), "tradeadviser_signal_sync")

    def _bind_trading_runtime_streams(self):
        trading_system = getattr(self, "trading_system", None)
        if trading_system is None:
            return
        memory = getattr(trading_system, "agent_memory", None)
        if memory is not None and hasattr(memory, "add_sink"):
            memory.add_sink(self._handle_live_agent_memory_event)
        event_bus = getattr(trading_system, "event_bus", None)
        if event_bus is not None and hasattr(event_bus, "subscribe"):
            for event_type in (
                    EventType.SIGNAL,
                    EventType.REASONING_DECISION,
                    EventType.DECISION_EVENT,
                    EventType.RISK_APPROVED,
                    EventType.RISK_ALERT,
                    EventType.EXECUTION_PLAN,
                    EventType.ORDER_FILLED,
            ):
                event_bus.subscribe(event_type, self._handle_trading_agent_bus_event)

    def latest_agent_decision_chain_for_symbol(self, symbol, limit=300):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if not normalized_symbol:
            return []

        live_rows = self._latest_live_agent_decision_chain_for_symbol(normalized_symbol, limit=limit)
        if live_rows:
            return live_rows

        repository = getattr(self, "agent_decision_repository", None)
        exchange = self._active_exchange_code() if hasattr(self, "_active_exchange_code") else None
        account_label = self.current_account_label() if hasattr(self, "current_account_label") else None
        if str(account_label or "").strip().lower() == "not set":
            account_label = None

        if repository is not None and hasattr(repository, "latest_chain_for_symbol"):
            try:
                rows = repository.latest_chain_for_symbol(
                    normalized_symbol,
                    limit=limit,
                    exchange=exchange,
                    account_label=account_label,
                )
                payloads = [self._agent_decision_record_to_payload(item) for item in list(rows or [])]
                if payloads:
                    return payloads
            except Exception:
                self.logger.debug("Unable to restore agent decision chain from repository", exc_info=True)

        trading_system = getattr(self, "trading_system", None)
        if trading_system is None or not hasattr(trading_system, "agent_memory_snapshot"):
            return []

        try:
            events = list(trading_system.agent_memory_snapshot(limit=200) or [])
        except Exception:
            return []
        filtered = [
            dict(item)
            for item in events
            if str((item or {}).get("symbol") or "").strip().upper() == normalized_symbol
        ]
        if not filtered:
            return []
        latest_decision_id = str(filtered[-1].get("decision_id") or "").strip()
        if latest_decision_id:
            filtered = [item for item in filtered if str(item.get("decision_id") or "").strip() == latest_decision_id]
        filtered = filtered[-max(1, int(limit)):]
        return [
            {
                "decision_id": str(item.get("decision_id") or "").strip(),
                "symbol": str(item.get("symbol") or "").strip().upper(),
                "agent_name": str(item.get("agent") or "").strip(),
                "stage": str(item.get("stage") or "").strip(),
                "strategy_name": str((item.get("payload") or {}).get("strategy_name") or "").strip(),
                "timeframe": str((item.get("payload") or {}).get("timeframe") or "").strip(),
                "side": str((item.get("payload") or {}).get("side") or "").strip().lower(),
                "confidence": (item.get("payload") or {}).get("confidence"),
                "approved": (item.get("payload") or {}).get("approved"),
                "reason": str((item.get("payload") or {}).get("reason") or "").strip(),
                "timestamp": item.get("timestamp"),
                "timestamp_label": str(item.get("timestamp") or "").strip(),
                "payload": dict(item.get("payload") or {}),
            }
            for item in filtered
        ]

    def latest_agent_decision_overview_for_symbol(self, symbol):
        chain = list(self.latest_agent_decision_chain_for_symbol(symbol, limit=20) or [])
        if not chain:
            return {}

        signal_row = next((row for row in chain if row.get("agent_name") == "SignalAgent"), {})
        reasoning_row = next((row for row in reversed(chain) if row.get("agent_name") == "ReasoningEngine"), {})
        risk_row = next((row for row in reversed(chain) if row.get("agent_name") == "RiskAgent"), {})
        execution_row = next((row for row in reversed(chain) if row.get("agent_name") == "ExecutionAgent"), {})
        latest = dict(chain[-1])
        strategy_name = str(signal_row.get("strategy_name") or reasoning_row.get("strategy_name") or risk_row.get("strategy_name") or execution_row.get("strategy_name") or "").strip()
        timeframe = str(signal_row.get("timeframe") or reasoning_row.get("timeframe") or risk_row.get("timeframe") or execution_row.get("timeframe") or "").strip()
        approved = execution_row.get("approved")
        if approved is None:
            approved = risk_row.get("approved")
        return {
            "decision_id": latest.get("decision_id"),
            "symbol": latest.get("symbol"),
            "strategy_name": strategy_name,
            "timeframe": timeframe,
            "side": str(signal_row.get("side") or execution_row.get("side") or "").strip().lower(),
            "approved": approved,
            "final_stage": latest.get("stage"),
            "final_agent": latest.get("agent_name"),
            "reason": str(latest.get("reason") or reasoning_row.get("reason") or risk_row.get("reason") or signal_row.get("reason") or "").strip(),
            "reasoning_decision": (reasoning_row.get("payload") or {}).get("decision"),
            "reasoning_confidence": (reasoning_row.get("payload") or {}).get("confidence"),
            "reasoning_provider": (reasoning_row.get("payload") or {}).get("provider"),
            "steps": len(chain),
            "timestamp_label": latest.get("timestamp_label"),
        }

    def decision_timeline_snapshot(self, symbol=None, limit=10):
        normalized_symbol = self._primary_runtime_symbol(symbol)
        if not normalized_symbol:
            latest_feed = list(getattr(self, "_live_agent_runtime_feed", []) or [])
            for row in reversed(latest_feed):
                normalized_symbol = self._normalize_strategy_symbol_key((row or {}).get("symbol"))
                if normalized_symbol:
                    break
        if not normalized_symbol:
            return {"symbol": "", "steps": [], "summary": "No runtime decision events have been recorded yet."}

        overview = dict(self.latest_agent_decision_overview_for_symbol(normalized_symbol) or {})
        chain = list(self.latest_agent_decision_chain_for_symbol(normalized_symbol, limit=max(3, int(limit or 10))) or [])
        if not chain:
            runtime_rows = list(self.live_agent_runtime_feed(limit=max(3, int(limit or 10)), symbol=normalized_symbol) or [])
            chain = [
                {
                    "decision_id": str(row.get("decision_id") or "").strip(),
                    "symbol": str(row.get("symbol") or normalized_symbol).strip().upper(),
                    "agent_name": str(row.get("agent_name") or row.get("event_type") or "").strip(),
                    "stage": str(row.get("stage") or "").strip(),
                    "strategy_name": str(row.get("strategy_name") or "").strip(),
                    "timeframe": str(row.get("timeframe") or "").strip(),
                    "side": "",
                    "approved": None,
                    "reason": str(row.get("message") or row.get("reason") or "").strip(),
                    "timestamp": row.get("timestamp"),
                    "timestamp_label": str(row.get("timestamp_label") or "").strip(),
                    "payload": dict(row.get("payload") or {}),
                }
                for row in runtime_rows
            ]

        steps = []
        for row in list(chain or [])[-max(1, int(limit or 10)):]:
            payload = dict(row.get("payload") or {}) if isinstance(row.get("payload"), dict) else {}
            approved = row.get("approved")
            status = "pending"
            if approved is True:
                status = "approved"
            elif approved is False:
                status = "rejected"
            elif str(payload.get("decision") or "").strip():
                status = str(payload.get("decision") or "").strip().lower()
            elif str(row.get("stage") or "").strip():
                status = str(row.get("stage") or "").strip().lower()
            steps.append(
                {
                    "timestamp": row.get("timestamp"),
                    "timestamp_label": str(row.get("timestamp_label") or "").strip(),
                    "agent_name": str(row.get("agent_name") or "").strip(),
                    "stage": str(row.get("stage") or "").strip(),
                    "status": status,
                    "strategy_name": str(row.get("strategy_name") or "").strip(),
                    "timeframe": str(row.get("timeframe") or "").strip(),
                    "side": str(row.get("side") or "").strip().upper(),
                    "reason": str(row.get("reason") or "").strip(),
                    "payload": payload,
                }
            )

        summary = "No decision chain available."
        if overview:
            final_agent = str(overview.get("final_agent") or "-").strip()
            final_stage = str(overview.get("final_stage") or "-").strip()
            side = str(overview.get("side") or "-").strip().upper()
            approval_text = "approved" if overview.get("approved") is True else "rejected" if overview.get("approved") is False else "pending"
            summary = f"{normalized_symbol}: {side} {approval_text} via {final_agent} / {final_stage}."
        elif steps:
            latest = steps[-1]
            summary = f"{normalized_symbol}: latest step {latest['agent_name'] or latest['status']} / {latest['stage'] or latest['status']}."

        return {
            "symbol": normalized_symbol,
            "summary": summary,
            "steps": steps,
            "overview": overview,
        }

    def _rebind_storage_dependencies(self):
        trading_system = getattr(self, "trading_system", None)
        if trading_system is None:
            return

        data_hub = getattr(trading_system, "data_hub", None)
        if data_hub is not None:
            data_hub.market_data_repository = self.market_data_repository

        execution_manager = getattr(trading_system, "execution_manager", None)
        if execution_manager is not None:
            execution_manager.trade_repository = self.trade_repository

        binder = getattr(trading_system, "bind_agent_decision_repository", None)
        if callable(binder):
            try:
                binder(getattr(self, "agent_decision_repository", None))
            except Exception:
                self.logger.debug("Unable to rebind agent decision repository", exc_info=True)

    @staticmethod
    def _masked_database_url(database_url):
        text = str(database_url or "").strip()
        if not text:
            return ""
        return re.sub(r":([^:@/]+)@", ":***@", text, count=1)

    def current_database_label(self):
        mode = str(getattr(self, "database_mode", "local") or "local").strip().lower()
        if mode == "remote":
            masked = self._masked_database_url(getattr(self, "database_url", "") or "")
            return masked or "Remote URL not set"
        return "Local SQLite"

    def configure_storage_database(self, database_mode=None, database_url=None, persist=True, raise_on_error=True):
        mode = str(database_mode or getattr(self, "database_mode", "local") or "local").strip().lower()
        if mode not in {"local", "remote"}:
            mode = "local"
        raw_url = str(database_url if database_url is not None else getattr(self, "database_url", "") or "").strip()

        if mode == "remote" and not raw_url:
            raise ValueError("Remote database URL is required when remote storage is selected.")

        target_url = raw_url if mode == "remote" else None
        auto_fallback_to_local = False
        try:
            configured_url = configure_database(target_url)
            init_database()
        except Exception:
            if not raise_on_error:
                self.logger.exception("Storage database configuration failed; falling back to local SQLite")
                mode = "local"
                raw_url = ""
                configured_url = configure_database(None)
                init_database()
            else:
                raise
        if mode == "remote" and is_sqlite_url(configured_url):
            self.logger.warning(
                "Remote storage requested for %s but the runtime is using local SQLite at %s.",
                raw_url or "the configured database URL",
                configured_url,
                )
            auto_fallback_to_local = True
            mode = "local"
            raw_url = ""

        self.database_mode = mode
        self.database_url = configured_url if mode == "remote" else ""
        self.database_connection_url = configured_url or get_database_url()
        self.market_data_repository = MarketDataRepository()
        self.trade_repository = TradeRepository()
        self.trade_audit_repository = TradeAuditRepository()
        self.equity_repository = EquitySnapshotRepository()
        self.agent_decision_repository = AgentDecisionRepository()
        self._rebind_storage_dependencies()

        should_persist_storage_settings = (bool(persist) and not auto_fallback_to_local) or (
                mode == "remote" and bool(raw_url) and self.database_url != raw_url
        )
        if should_persist_storage_settings:
            self.settings.setValue("storage/database_mode", self.database_mode)
            self.settings.setValue("storage/database_url", self.database_url)

        return self.database_connection_url

    def _setup_ui(self, controller):
        self.setWindowTitle("TradeAdviser")
        self.resize(1600, 900)
        self.setMinimumSize(960, 640)
        self._fit_window_to_available_screen(requested_width=1600, requested_height=900)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.dashboard = Dashboard(controller)
        self.stack.addWidget(self.dashboard)

        self.dashboard.login_requested.connect(self._on_login_requested)

    def _fit_window_to_available_screen(self, requested_width=None, requested_height=None):
        screen = self.screen()
        if screen is None:
            app = QApplication.instance()
            screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return

        available = screen.availableGeometry()
        width, minimum_width = _bounded_window_extent(
            requested_width if requested_width is not None else self.width() or 1600,
            available.width(),
            minimum=960,
        )
        height, minimum_height = _bounded_window_extent(
            requested_height if requested_height is not None else self.height() or 900,
            available.height(),
            minimum=640,
        )
        self.setMinimumSize(minimum_width, minimum_height)
        self.resize(width, height)

    def _on_login_requested(self, config):
        self._create_task(self.handle_login(config), "handle_login")

    def _on_logout_requested(self):
        self._create_task(self.logout(), "logout")

    def platform_sync_profile(self):
        return self.platform_sync_service.load_profile()

    def save_platform_sync_profile(self, profile):
        return self.platform_sync_service.save_profile(profile)

    def request_hybrid_market_watch_subscription(self, symbols=None, timeframe=None):
        if not self.is_hybrid_server_authoritative():
            return None
        return self._create_task(
            self._request_hybrid_market_data_subscription(symbols=symbols, timeframe=timeframe),
            "hybrid_market_subscription",
        )

    def request_platform_workspace_pull(self, profile=None):
        return self._create_task(
            self.pull_platform_workspace(profile=profile, interactive=True),
            "platform_workspace_pull",
        )

    def request_platform_workspace_push(self, workspace_payload, profile=None, *, interactive=False):
        return self._create_task(
            self.push_platform_workspace(
                workspace_payload,
                profile=profile,
                interactive=interactive,
            ),
            "platform_workspace_push",
        )

    async def pull_platform_workspace(self, profile=None, *, interactive=True):
        dashboard = getattr(self, "dashboard", None)
        if dashboard is not None and hasattr(dashboard, "set_platform_sync_status"):
            dashboard.set_platform_sync_status("Loading workspace from Sopotek server...", tone="busy")
        try:
            result = await self.platform_sync_service.fetch_workspace_settings(profile)
            refreshed_profile = dict(result.get("profile") or {})
            workspace = dict(result.get("workspace") or {})
            if dashboard is not None:
                if hasattr(dashboard, "apply_platform_sync_profile"):
                    dashboard.apply_platform_sync_profile(refreshed_profile)
                if hasattr(dashboard, "apply_workspace_settings"):
                    dashboard.apply_workspace_settings(workspace)
                if hasattr(dashboard, "set_platform_sync_status"):
                    dashboard.set_platform_sync_status(
                        str(
                            refreshed_profile.get("last_sync_message")
                            or "Loaded workspace from Sopotek server."
                        ),
                        tone="success",
                    )
            return result
        except Exception as exc:
            self.logger.warning("Platform workspace pull failed: %s", exc)
            if dashboard is not None and hasattr(dashboard, "set_platform_sync_status"):
                dashboard.set_platform_sync_status(str(exc), tone="error")
            if interactive and dashboard is not None:
                QMessageBox.warning(dashboard, "Server Sync Failed", str(exc))
            return None

    async def push_platform_workspace(self, workspace_payload, profile=None, *, interactive=False):
        dashboard = getattr(self, "dashboard", None)
        if dashboard is not None and hasattr(dashboard, "set_platform_sync_status"):
            dashboard.set_platform_sync_status("Syncing desktop workspace to Sopotek server...", tone="busy")
        try:
            result = await self.platform_sync_service.push_workspace_settings(workspace_payload, profile)
            refreshed_profile = dict(result.get("profile") or {})
            if dashboard is not None:
                if hasattr(dashboard, "apply_platform_sync_profile"):
                    dashboard.apply_platform_sync_profile(refreshed_profile)
                if hasattr(dashboard, "set_platform_sync_status"):
                    dashboard.set_platform_sync_status(
                        str(
                            refreshed_profile.get("last_sync_message")
                            or "Synced desktop workspace to Sopotek server."
                        ),
                        tone="success",
                    )
            return result
        except Exception as exc:
            self.logger.warning("Platform workspace push failed: %s", exc)
            if dashboard is not None and hasattr(dashboard, "set_platform_sync_status"):
                dashboard.set_platform_sync_status(str(exc), tone="error")
            if interactive and dashboard is not None:
                QMessageBox.warning(dashboard, "Server Sync Failed", str(exc))
            return None

    def _hybrid_desktop_enabled(self):
        value = os.getenv(
            "SOPOTEK_ENABLE_HYBRID_DESKTOP",
            self.settings.value("hybrid/desktop_enabled", "true"),
        )
        return str(value or "true").strip().lower() in {"1", "true", "yes", "on"}

    def _reset_hybrid_authoritative_runtime(self):
        self.hybrid_authoritative_runtime = {
            "symbols": [],
            "subscriptions": {},
            "market_watch": {},
            "assets": {},
            "positions": [],
            "open_orders": [],
            "order_history": [],
            "trade_history": [],
            "broker_status": {},
            "market_data_health": {},
            "live_readiness": {},
            "pipeline_snapshot": {},
            "pipeline_summary": "",
            "health_check_report": [],
            "health_summary": "",
            "behavior_guard_status": {},
        }

    def is_hybrid_server_authoritative(self):
        return bool(
            getattr(self, "hybrid_server_connected", False)
            and getattr(self, "hybrid_session_state", None) is not None
        )

    def _hybrid_runtime_snapshot(self):
        runtime = getattr(self, "hybrid_authoritative_runtime", None)
        if isinstance(runtime, dict):
            return runtime
        self._reset_hybrid_authoritative_runtime()
        return self.hybrid_authoritative_runtime

    def _hybrid_server_profile(self):
        return dict(self._server_sync_profile() or {})

    def _hybrid_server_is_ready(self, profile=None):
        return bool(self._hybrid_desktop_enabled() and self._is_server_profile_configured(profile))

    @staticmethod
    def _hybrid_ws_url_from_base(base_url):
        normalized_base = str(base_url or "").strip().rstrip("/")
        if not normalized_base:
            return ""
        parsed = urlsplit(normalized_base)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunsplit((scheme, parsed.netloc, "/ws/events", "", ""))

    def _hybrid_exchange_kind(self, exchange=None):
        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        normalized_exchange = str(
            exchange
            or getattr(broker_cfg, "exchange", None)
            or ""
        ).strip().lower()
        mapping = {
            "paper": HybridBrokerKind.PAPER,
            "coinbase": HybridBrokerKind.COINBASE,
            "binance": HybridBrokerKind.BINANCE,
            "binanceus": HybridBrokerKind.BINANCE,
            "oanda": HybridBrokerKind.OANDA,
            "alpaca": HybridBrokerKind.ALPACA,
            "ibkr": HybridBrokerKind.IBKR,
            "schwab": HybridBrokerKind.SCHWAB,
        }
        return mapping.get(normalized_exchange)

    def _hybrid_command_session_id(self):
        return str(
            getattr(self, "active_session_id", None)
            or getattr(getattr(self, "hybrid_session_state", None), "session_id", None)
            or ""
        ).strip()

    def _hybrid_account_id(self):
        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        configured_account = str(getattr(broker_cfg, "account_id", None) or "").strip()
        if configured_account:
            return configured_account
        session_state = getattr(self, "hybrid_session_state", None)
        if session_state is not None:
            return str(getattr(getattr(session_state, "user", None), "account_id", "") or "").strip()
        return ""

    def _hybrid_trading_available(self, exchange=None):
        return bool(
            getattr(self, "hybrid_session_controller", None) is not None
            and getattr(self, "hybrid_session_state", None) is not None
            and self._hybrid_exchange_kind(exchange) is not None
        )

    def _set_hybrid_status(self, message, *, tone="info"):
        dashboard = getattr(self, "dashboard", None)
        if dashboard is not None and hasattr(dashboard, "set_platform_sync_status"):
            dashboard.set_platform_sync_status(str(message or "").strip(), tone=tone)

    async def _teardown_hybrid_session(self, *, clear_status=False):
        controller = getattr(self, "hybrid_session_controller", None)
        self.hybrid_api_client = None
        self.hybrid_ws_client = None
        self.hybrid_session_controller = None
        self.hybrid_session_state = None
        self.hybrid_server_connected = False
        self.hybrid_server_last_sequence = 0
        self.hybrid_server_base_url = ""
        self.hybrid_server_ws_url = ""
        self._reset_hybrid_authoritative_runtime()
        if controller is not None:
            try:
                await controller.close()
            except Exception:
                self.logger.debug("Hybrid session controller shutdown failed", exc_info=True)
        if clear_status:
            self._set_hybrid_status(
                "Server authority disconnected. Desktop is running without a linked Sopotek server session.",
                tone="idle",
            )

    async def _ensure_hybrid_clients(self, profile=None):
        active_profile = dict(profile or self._hybrid_server_profile() or {})
        if not self._hybrid_server_is_ready(active_profile):
            await self._teardown_hybrid_session(clear_status=False)
            return None, active_profile

        base_url = str(active_profile.get("base_url") or "").strip().rstrip("/")
        ws_url = self._hybrid_ws_url_from_base(base_url)
        controller = getattr(self, "hybrid_session_controller", None)
        should_recreate = (
                controller is None
                or str(getattr(self, "hybrid_server_base_url", "") or "") != base_url
                or str(getattr(self, "hybrid_server_ws_url", "") or "") != ws_url
        )
        if should_recreate:
            await self._teardown_hybrid_session(clear_status=False)
            api_client = HybridApiClient(base_url)
            ws_client = HybridWsClient(ws_url)
            controller = HybridSessionController(api_client=api_client, ws_client=ws_client)
            controller.event_callback = self._handle_hybrid_server_event
            self.hybrid_api_client = api_client
            self.hybrid_ws_client = ws_client
            self.hybrid_session_controller = controller
            self.hybrid_server_base_url = base_url
            self.hybrid_server_ws_url = ws_url
        return controller, active_profile

    async def _connect_hybrid_operator_session(self, profile=None, *, interactive=False):
        controller, active_profile = await self._ensure_hybrid_clients(profile)
        if controller is None:
            return None

        if self.hybrid_session_state is not None:
            return self.hybrid_session_state

        username = str(active_profile.get("email") or "").strip()
        password = str(active_profile.get("password") or "").strip()
        try:
            session_state = await controller.connect({"email": username, "password": password})
        except Exception as exc:
            self.hybrid_server_last_error = str(exc)
            self.hybrid_server_connected = False
            self.logger.warning("Hybrid server login failed, falling back to desktop-local flow: %s", exc)
            self._set_hybrid_status(
                f"Server authority unavailable. Continuing in desktop-local mode: {exc}",
                tone="error",
            )
            if interactive:
                dashboard = getattr(self, "dashboard", None)
                if dashboard is not None:
                    QMessageBox.warning(
                        dashboard,
                        "Hybrid Server Login Failed",
                        f"Desktop will continue locally.\n\n{exc}",
                    )
            return None

        self.hybrid_session_state = session_state
        self.hybrid_server_connected = True
        self.hybrid_server_last_error = ""
        self.hybrid_server_last_sequence = 0
        self.settings.setValue("hybrid/last_session_id", session_state.session_id)
        self._set_hybrid_status(
            f"Server authority connected for {username or session_state.user.user_id}. Live updates will stream into the desktop console.",
            tone="success",
        )
        return session_state

    def _hybrid_terminal_targets(self):
        terminals = []
        primary_terminal = getattr(self, "terminal", None)
        if primary_terminal is not None:
            terminals.append(primary_terminal)
        for terminal in list(self._session_terminal_registry().values()):
            if terminal is not None and terminal not in terminals:
                terminals.append(terminal)
        return terminals

    def _apply_hybrid_runtime_to_terminals(self, payload, *, market_only=False):
        for terminal in self._hybrid_terminal_targets():
            if terminal is None:
                continue
            if market_only:
                applier = getattr(terminal, "apply_server_market_watch_snapshot", None)
            else:
                applier = getattr(terminal, "apply_server_runtime_snapshot", None)
            if callable(applier):
                try:
                    applier(payload)
                except Exception:
                    self.logger.debug("Hybrid runtime application to terminal failed", exc_info=True)

    async def _start_positions_orders_polling(self):
        """Start background polling for positions and orders data."""
        api_client = getattr(self, "hybrid_api_client", None)
        if api_client is None:
            return

        # Poll every 2 seconds for positions and orders
        try:
            while True:
                if not getattr(self, "hybrid_server_connected", False):
                    await asyncio.sleep(5)
                    continue

                try:
                    # Fetch positions and orders in parallel
                    positions, orders = await asyncio.gather(
                        api_client.fetch_positions(),
                        api_client.fetch_orders(),
                        return_exceptions=True
                    )

                    # Filter out exceptions
                    positions = positions if isinstance(positions, list) else []
                    orders = orders if isinstance(orders, list) else []

                    # Apply updates to terminals
                    if positions:
                        self._apply_hybrid_runtime_to_terminals({"positions": positions})
                    if orders:
                        self._apply_hybrid_runtime_to_terminals({"open_orders": orders})
                except Exception as e:
                    self.logger.debug(f"Polling error: {e}")

                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.debug(f"Polling task failed: {e}")

    async def _request_hybrid_market_data_subscription(self, symbols=None, timeframe=None):
        controller = getattr(self, "hybrid_session_controller", None)
        session_id = self._hybrid_command_session_id()
        if controller is None or not session_id:
            return None

        normalized_symbols = []
        for symbol in list(symbols or getattr(self, "symbols", []) or []):
            normalized = self._normalize_market_data_symbol(symbol)
            if normalized and normalized not in normalized_symbols:
                normalized_symbols.append(normalized)
        if not normalized_symbols:
            return None

        response = await controller.api_client.request_market_data_subscription(
            HybridRequestMarketDataSubscriptionCommand(
                session_id=session_id,
                symbols=normalized_symbols,
                timeframe=str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h",
                include_quotes=True,
                include_candles=True,
            )
        )
        if not response.success:
            raise RuntimeError(response.error.message if response.error else "Market data subscription request failed.")
        runtime = self._hybrid_runtime_snapshot()
        runtime["subscriptions"] = dict(response.data or {})
        runtime["symbols"] = list(normalized_symbols)
        return response.data

    async def _register_hybrid_broker_session(self, session):
        if not self._hybrid_trading_available():
            return None

        controller = getattr(self, "hybrid_session_controller", None)
        session_state = getattr(self, "hybrid_session_state", None)
        broker_kind = self._hybrid_exchange_kind()
        if controller is None or session_state is None or broker_kind is None:
            return None

        user_context = HybridUserContext(
            user_id=str(session_state.user.user_id or "").strip() or "desktop-operator",
            username=str(session_state.user.user_id or "").strip() or "desktop-operator",
            roles=list(getattr(session_state.user, "permissions", []) or []),
        )
        session_context = HybridSessionContext(
            session_id=str(getattr(session, "session_id", "") or "").strip(),
            user=user_context,
            broker=HybridBrokerIdentifier(
                broker=broker_kind,
                account_id=self._hybrid_account_id() or str(getattr(session_state.user, "account_id", "") or "").strip() or "desktop",
            ),
            status=HybridSessionStatus.ACTIVE,
            permissions=list(getattr(session_state.user, "permissions", []) or []),
            correlation=HybridCorrelationIds(),
        )
        response = await controller.api_client.connect_broker(
            HybridConnectBrokerCommand(session_context=session_context)
        )
        if not response.success:
            message = response.error.message if response.error else "Broker registration failed."
            raise RuntimeError(message)
        return response.data

    @staticmethod
    def _hybrid_order_side(side):
        normalized = str(side or "").strip().lower()
        return HybridOrderSide.SELL if normalized == "sell" else HybridOrderSide.BUY

    @staticmethod
    def _hybrid_order_type(order_type):
        normalized = str(order_type or "market").strip().lower()
        mapping = {
            "market": HybridOrderType.MARKET,
            "limit": HybridOrderType.LIMIT,
            "stop": HybridOrderType.STOP,
            "stop_limit": HybridOrderType.STOP_LIMIT,
            "stop-limit": HybridOrderType.STOP_LIMIT,
        }
        return mapping.get(normalized, HybridOrderType.MARKET)

    def _record_hybrid_market_watch_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            return None
        identifier = snapshot.get("identifier") if isinstance(snapshot.get("identifier"), dict) else {}
        symbol = self._normalize_market_data_symbol(snapshot.get("symbol") or identifier.get("symbol"))
        if not symbol:
            return None
        runtime = self._hybrid_runtime_snapshot()
        market_watch = runtime.setdefault("market_watch", {})
        normalized_snapshot = dict(snapshot)
        normalized_snapshot["symbol"] = symbol
        market_watch[symbol] = normalized_snapshot
        self._cache_ticker_snapshot(
            symbol,
            {
                "symbol": symbol,
                "bid": float(self._safe_balance_metric(snapshot.get("bid")) or self._safe_balance_metric(snapshot.get("last_price")) or 0.0),
                "ask": float(self._safe_balance_metric(snapshot.get("ask")) or self._safe_balance_metric(snapshot.get("last_price")) or self._safe_balance_metric(snapshot.get("bid")) or 0.0),
                "last": float(self._safe_balance_metric(snapshot.get("last_price")) or self._safe_balance_metric(snapshot.get("ask")) or 0.0),
                "raw": normalized_snapshot,
            },
        )
        return normalized_snapshot

    def _apply_hybrid_state_rehydration(self, payload):
        runtime = self._hybrid_runtime_snapshot()
        runtime["symbols"] = list(payload.get("symbols") or runtime.get("symbols") or [])
        runtime["subscriptions"] = dict(payload.get("subscriptions") or runtime.get("subscriptions") or {})
        runtime["assets"] = dict(payload.get("assets") or {})
        runtime["positions"] = list(payload.get("positions") or [])
        runtime["open_orders"] = list(payload.get("open_orders") or [])
        runtime["order_history"] = list(payload.get("order_history") or [])
        runtime["trade_history"] = list(payload.get("trade_history") or [])
        runtime["broker_status"] = dict(payload.get("broker_status") or {})
        runtime["market_data_health"] = dict(payload.get("market_data_health") or {})
        runtime["live_readiness"] = dict(payload.get("live_readiness") or {})
        runtime["pipeline_snapshot"] = dict(payload.get("pipeline") or {})
        runtime["pipeline_summary"] = str(
            runtime["pipeline_snapshot"].get("summary")
            or payload.get("pipeline_summary")
            or runtime.get("pipeline_summary")
            or ""
        ).strip()
        runtime["health_check_report"] = list(payload.get("health_check_report") or [])
        runtime["health_summary"] = str(payload.get("health_summary") or runtime.get("health_summary") or "").strip()
        runtime["behavior_guard_status"] = dict(payload.get("behavior_guard_status") or {})
        runtime["market_watch"] = {}
        for snapshot in list(payload.get("market_watch") or []):
            self._record_hybrid_market_watch_snapshot(snapshot)
        symbols = list(runtime.get("symbols") or [])
        if not symbols:
            symbols = list(runtime.get("market_watch", {}).keys())
        if symbols:
            self.symbols = list(symbols)
            self.symbols_signal.emit(self._active_exchange_code(), list(symbols))
        self._apply_hybrid_runtime_to_terminals(payload)

    async def _handle_hybrid_server_event(self, event):
        envelope = event if isinstance(event, HybridServerEventEnvelope) else HybridServerEventEnvelope.model_validate(event)
        payload = dict(envelope.payload or {}) if isinstance(envelope.payload, dict) else {"payload": envelope.payload}
        normalized_event_type = str(envelope.event_type or "").strip()
        self.hybrid_server_connected = True
        runtime = self._hybrid_runtime_snapshot()
        self.hybrid_server_last_sequence = max(
            int(getattr(self, "hybrid_server_last_sequence", 0) or 0),
            int(getattr(envelope, "sequence", 0) or 0),
        )

        if normalized_event_type == HybridServerEventType.SESSION_VALIDATED.value:
            self._set_hybrid_status("Server authority session validated. Streaming is active.", tone="success")
            try:
                await self._request_hybrid_market_data_subscription(
                    symbols=getattr(self, "symbols", []) or [],
                    timeframe=getattr(self, "time_frame", "1h"),
                )
            except Exception:
                self.logger.debug("Hybrid market subscription refresh failed after validation", exc_info=True)
            # Start polling positions and orders to ensure data is displayed
            try:
                await self._start_positions_orders_polling()
            except Exception:
                self.logger.debug("Failed to start positions/orders polling", exc_info=True)
            return

        if normalized_event_type == HybridServerEventType.STATE_REHYDRATED.value:
            self._apply_hybrid_state_rehydration(payload)
            self._set_hybrid_status("Server authority state rehydrated after connect/reconnect.", tone="success")
            return

        if normalized_event_type == HybridServerEventType.MARKET_SUBSCRIPTION_UPDATED.value:
            runtime["subscriptions"] = dict(payload or {})
            return

        if normalized_event_type == HybridServerEventType.MARKET_SNAPSHOT.value:
            snapshot = self._record_hybrid_market_watch_snapshot(payload)
            if snapshot is not None:
                symbol = str(snapshot.get("symbol") or "").strip()
                bid = float(
                    self._safe_balance_metric(snapshot.get("bid"))
                    or self._safe_balance_metric(snapshot.get("last_price"))
                    or 0.0
                )
                ask = float(
                    self._safe_balance_metric(snapshot.get("ask"))
                    or self._safe_balance_metric(snapshot.get("last_price"))
                    or bid
                )
                self.ticker_signal.emit(symbol, bid, ask)
                self._apply_hybrid_runtime_to_terminals({"market_watch": [snapshot], "symbols": list(runtime.get("market_watch", {}).keys())}, market_only=True)
            return

        if normalized_event_type == HybridServerEventType.MARKET_WATCH_SNAPSHOT.value:
            snapshots = []
            for snapshot in list(payload.get("symbols") or payload.get("market_watch") or []):
                normalized_snapshot = self._record_hybrid_market_watch_snapshot(snapshot)
                if normalized_snapshot is not None:
                    snapshots.append(normalized_snapshot)
            if snapshots:
                symbols = [str(item.get("symbol") or "").strip() for item in snapshots if str(item.get("symbol") or "").strip()]
                runtime["symbols"] = list(dict.fromkeys(symbols or runtime.get("symbols") or []))
                if runtime["symbols"]:
                    self.symbols = list(runtime["symbols"])
                    self.symbols_signal.emit(self._active_exchange_code(), list(runtime["symbols"]))
                self._apply_hybrid_runtime_to_terminals({"market_watch": snapshots, "symbols": list(runtime.get("symbols") or [])}, market_only=True)
            return

        if normalized_event_type == HybridServerEventType.CANDLE_UPDATE.value:
            identifier = payload.get("identifier") if isinstance(payload.get("identifier"), dict) else {}
            symbol = self._normalize_market_data_symbol(payload.get("symbol") or identifier.get("symbol"))
            if symbol:
                end_at = payload.get("end_at") or payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
                frame = pd.DataFrame(
                    [
                        {
                            "timestamp": end_at,
                            "open": float(payload.get("open") or 0.0),
                            "high": float(payload.get("high") or 0.0),
                            "low": float(payload.get("low") or 0.0),
                            "close": float(payload.get("close") or 0.0),
                            "volume": float(payload.get("volume") or 0.0),
                        }
                    ]
                )
                self.candle_signal.emit(symbol, frame)
            return

        if normalized_event_type == HybridServerEventType.BROKER_STATUS_UPDATED.value:
            runtime["broker_status"] = dict(payload or {})
            self._apply_hybrid_runtime_to_terminals({"broker_status": dict(payload or {})})
            return

        if normalized_event_type == HybridServerEventType.ASSETS_SNAPSHOT.value:
            runtime["assets"] = dict(payload.get("balances") or payload.get("assets") or payload or {})
            self._apply_hybrid_runtime_to_terminals({"assets": dict(runtime["assets"])})
            return

        if normalized_event_type == HybridServerEventType.POSITIONS_SNAPSHOT.value:
            positions_payload = payload if isinstance(payload, list) else (payload.get("positions") or payload.get("items") or [])
            runtime["positions"] = list(positions_payload or [])
            self._apply_hybrid_runtime_to_terminals({"positions": list(runtime["positions"])})
            return

        if normalized_event_type == HybridServerEventType.OPEN_ORDERS_SNAPSHOT.value:
            orders_payload = payload if isinstance(payload, list) else (payload.get("orders") or payload.get("items") or [])
            runtime["open_orders"] = list(orders_payload or [])
            self._apply_hybrid_runtime_to_terminals({"open_orders": list(runtime["open_orders"])})
            return

        if normalized_event_type == HybridServerEventType.ORDER_HISTORY_SNAPSHOT.value:
            order_history_payload = payload if isinstance(payload, list) else (payload.get("orders") or payload.get("items") or [])
            runtime["order_history"] = list(order_history_payload or [])
            self._apply_hybrid_runtime_to_terminals({"order_history": list(runtime["order_history"])})
            return

        if normalized_event_type == HybridServerEventType.TRADE_HISTORY_SNAPSHOT.value:
            trade_history_payload = payload if isinstance(payload, list) else (payload.get("trades") or payload.get("items") or [])
            runtime["trade_history"] = list(trade_history_payload or [])
            self._apply_hybrid_runtime_to_terminals({"trade_history": list(runtime["trade_history"])})
            return

        payload.setdefault("session_id", self._hybrid_command_session_id() or payload.get("session_id"))
        payload["event_type"] = normalized_event_type

        if normalized_event_type in {
            HybridServerEventType.ORDER_UPDATED.value,
            HybridServerEventType.FILL_RECEIVED.value,
            HybridServerEventType.POSITION_UPDATED.value,
            HybridServerEventType.PNL_UPDATED.value,
        }:
            if normalized_event_type in {HybridServerEventType.ORDER_UPDATED.value, HybridServerEventType.FILL_RECEIVED.value}:
                existing_orders = [dict(item) for item in list(runtime.get("open_orders") or []) if isinstance(item, dict)]
                order_id = str(payload.get("order_id") or payload.get("id") or payload.get("client_order_id") or "").strip()
                if order_id:
                    existing_orders = [
                        item
                        for item in existing_orders
                        if str(item.get("order_id") or item.get("id") or item.get("client_order_id") or "").strip() != order_id
                    ]
                existing_orders.insert(0, dict(payload))
                runtime["open_orders"] = existing_orders[:200]
                existing_history = [dict(item) for item in list(runtime.get("order_history") or []) if isinstance(item, dict)]
                existing_history.insert(0, dict(payload))
                runtime["order_history"] = existing_history[:200]
            if normalized_event_type in {HybridServerEventType.POSITION_UPDATED.value, HybridServerEventType.PNL_UPDATED.value}:
                existing_positions = [dict(item) for item in list(runtime.get("positions") or []) if isinstance(item, dict)]
                position_key = str(payload.get("position_id") or payload.get("id") or payload.get("symbol") or "").strip()
                if position_key:
                    existing_positions = [
                        item
                        for item in existing_positions
                        if str(item.get("position_id") or item.get("id") or item.get("symbol") or "").strip() != position_key
                    ]
                existing_positions.insert(0, dict(payload))
                runtime["positions"] = existing_positions[:200]
            trade_history = [dict(item) for item in list(runtime.get("trade_history") or []) if isinstance(item, dict)]
            trade_history.insert(0, dict(payload))
            runtime["trade_history"] = trade_history[:200]
            self._apply_hybrid_runtime_to_terminals(
                {
                    "positions": list(runtime.get("positions") or []),
                    "open_orders": list(runtime.get("open_orders") or []),
                    "order_history": list(runtime.get("order_history") or []),
                    "trade_history": list(runtime.get("trade_history") or []),
                }
            )
            self.trade_signal.emit(payload)
            return

        if normalized_event_type in {
            HybridServerEventType.SIGNAL_GENERATED.value,
            HybridServerEventType.DECISION_UPDATED.value,
            HybridServerEventType.REASONING_REVIEW.value,
            HybridServerEventType.PORTFOLIO_UPDATED.value,
            HybridServerEventType.AGENT_HEALTH_UPDATED.value,
            HybridServerEventType.REPORT_READY.value,
        }:
            if normalized_event_type == HybridServerEventType.AGENT_HEALTH_UPDATED.value:
                runtime["pipeline_snapshot"] = dict(payload or {})
                runtime["pipeline_summary"] = str(
                    payload.get("summary")
                    or payload.get("status")
                    or runtime.get("pipeline_summary")
                    or "Server runtime updated"
                ).strip()
            self.ai_signal_monitor.emit(payload)
            self._apply_hybrid_runtime_to_terminals(
                {
                    "pipeline": dict(runtime.get("pipeline_snapshot") or {}),
                    "pipeline_summary": runtime.get("pipeline_summary") or "",
                }
            )
            return

        if normalized_event_type in {
            HybridServerEventType.RISK_ALERT.value,
            HybridServerEventType.SYSTEM_ALERT.value,
        }:
            runtime["behavior_guard_status"] = {
                "summary": str(payload.get("message") or payload.get("summary") or normalized_event_type).strip(),
                "reason": str(payload.get("message") or payload.get("reason") or "").strip(),
            }
            terminal = getattr(self, "terminal", None)
            system_console = getattr(terminal, "system_console", None) if terminal is not None else None
            message = str(payload.get("message") or payload.get("notes") or normalized_event_type).strip()
            if system_console is not None:
                system_console.log(f"Server: {message}", "WARN")
            self.ai_signal_monitor.emit(payload)
            self._apply_hybrid_runtime_to_terminals({"behavior_guard_status": dict(runtime.get("behavior_guard_status") or {})})

    async def _submit_trade_via_hybrid_server(
            self,
            *,
            symbol,
            side,
            amount_units,
            order_type,
            price=None,
            stop_price=None,
            source="manual",
            strategy_name="Manual",
            reason="Manual order",
            timeframe=None,
    ):
        controller = getattr(self, "hybrid_session_controller", None)
        broker_kind = self._hybrid_exchange_kind()
        if controller is None or broker_kind is None:
            raise RuntimeError("Hybrid server execution is not available for this broker.")

        client_order_id = f"desktop_{uuid4().hex[:20]}"
        execution_request = HybridExecutionRequest(
            client_order_id=client_order_id,
            broker=HybridBrokerIdentifier(
                broker=broker_kind,
                account_id=self._hybrid_account_id() or self._hybrid_command_session_id() or "desktop",
            ),
            identifier=HybridSymbolIdentifier(
                symbol=str(symbol or "").strip().upper(),
                broker=broker_kind,
                timeframe=str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h",
            ),
            side=self._hybrid_order_side(side),
            order_type=self._hybrid_order_type(order_type),
            quantity=float(amount_units or 0.0),
            limit_price=float(price) if price is not None else None,
            stop_price=float(stop_price) if stop_price is not None else None,
            correlation_id=HybridCorrelationIds().correlation_id,
        )
        response = await controller.api_client.place_order(
            execution_request
        )
        if not response.success or response.data is None:
            raise RuntimeError(response.error.message if response.error else "Hybrid order placement failed.")

        result = response.data
        result_payload = result.model_dump() if hasattr(result, "model_dump") else dict(result or {})
        order_id = str(result_payload.get("order_id") or "").strip()
        client_order_id = str(result_payload.get("client_order_id") or client_order_id).strip() or client_order_id
        order = {
            "id": order_id,
            "order_id": order_id,
            "client_order_id": client_order_id,
            "status": str(
                result_payload.get("status")
                or "accepted"
            ).strip().lower(),
            "symbol": str(symbol or "").strip().upper(),
            "side": str(side or "").strip().lower(),
            "amount": float(amount_units or 0.0),
            "amount_units": float(amount_units or 0.0),
            "filled": float(result_payload.get("filled_quantity") or 0.0),
            "price": float(
                result_payload.get("average_fill_price")
                or price
                or 0.0
            ),
            "type": str(order_type or "market").strip().lower() or "market",
            "source": source,
            "strategy_name": strategy_name,
            "reason": reason,
            "session_id": self._hybrid_command_session_id(),
            "hybrid_server": True,
            "broker_order_id": str(result_payload.get("broker_order_id") or "").strip() or None,
        }
        self.trade_signal.emit(dict(order))
        return order

    async def _cancel_order_via_hybrid_server(self, order_id):
        controller = getattr(self, "hybrid_session_controller", None)
        if controller is None:
            raise RuntimeError("Hybrid server session is not active.")
        response = await controller.api_client.cancel_order(
            HybridCancelOrderCommand(order_id=str(order_id or "").strip(), session_id=self._hybrid_command_session_id())
        )
        if not response.success:
            raise RuntimeError(response.error.message if response.error else "Cancel order request failed.")
        return dict(response.data or {})

    async def _close_position_via_hybrid_server(self, position_id):
        controller = getattr(self, "hybrid_session_controller", None)
        if controller is None:
            raise RuntimeError("Hybrid server session is not active.")
        response = await controller.api_client.close_position(
            HybridClosePositionCommand(
                position_id=str(position_id or "").strip(),
                session_id=self._hybrid_command_session_id(),
            )
        )
        if not response.success:
            raise RuntimeError(response.error.message if response.error else "Close position request failed.")
        return dict(response.data or {})

    async def _trigger_hybrid_kill_switch(self, reason):
        controller = getattr(self, "hybrid_session_controller", None)
        if controller is None:
            return None
        response = await controller.api_client.trigger_kill_switch(
            HybridTriggerKillSwitchCommand(
                session_id=self._hybrid_command_session_id(),
                reason=str(reason or "Emergency kill switch active").strip() or "Emergency kill switch active",
            )
        )
        if not response.success:
            raise RuntimeError(response.error.message if response.error else "Kill switch request failed.")
        return dict(response.data or {})

    def prompt_oauth_redirect_url(self, provider_name, authorization_url, redirect_uri):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{provider_name} Sign-In")
        dialog.setModal(True)
        dialog.resize(760, 360)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        title = QLabel(
            f"Finish the {provider_name} sign-in flow in your browser, then paste the redirected URL or the authorization code below."
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        redirect_label = QLabel(f"Expected redirect URI: {redirect_uri}")
        redirect_label.setWordWrap(True)
        layout.addWidget(redirect_label)

        auth_url_browser = QTextBrowser()
        auth_url_browser.setOpenExternalLinks(True)
        auth_url_browser.setPlainText(str(authorization_url or "").strip())
        auth_url_browser.setMinimumHeight(120)
        layout.addWidget(auth_url_browser)

        input_label = QLabel("Redirect URL or authorization code")
        layout.addWidget(input_label)

        input_box = QLineEdit()
        input_box.setPlaceholderText("Paste the full redirected URL or just the code parameter")
        layout.addWidget(input_box)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        cancel_button = QPushButton("Cancel")
        submit_button = QPushButton("Continue")
        submit_button.setDefault(True)
        button_row.addWidget(cancel_button)
        button_row.addWidget(submit_button)
        layout.addLayout(button_row)

        cancel_button.clicked.connect(dialog.reject)
        submit_button.clicked.connect(dialog.accept)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return input_box.text().strip() or None

    def _create_task(self, coro, name):
        # Handle case where a Task is passed instead of a coroutine
        if isinstance(coro, asyncio.Task):
            task = coro
        else:
            task = asyncio.create_task(coro)

        def _done(t):
            try:
                exc = t.exception()
                if exc:
                    self.logger.error("Task %s failed: %s", name, exc)
            except asyncio.CancelledError:
                pass

        task.add_done_callback(_done)
        return task

    def _emit_symbols_signal_deferred(self, exchange, symbols):
        exchange_name = str(exchange or "unknown")
        normalized_symbols = list(symbols or [])

        def _emit():
            try:
                self.symbols_signal.emit(exchange_name, normalized_symbols)
            except Exception:
                self.logger.debug("Deferred symbols signal emit failed", exc_info=True)

        defer_emit = False
        if QApplication.instance() is not None:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            defer_emit = running_loop is not None and str(type(running_loop).__module__ or "").startswith("qasync")

        if not defer_emit:
            _emit()
            return
        QTimer.singleShot(0, _emit)

    def _run_on_gui_thread(self, func):
        """Run a function on the GUI thread using QTimer.singleShot.
        
        This ensures that Qt operations that require the GUI thread are executed
        safely even when called from async/background contexts.
        
        Args:
            func: Callable to execute on the GUI thread
        """
        if callable(func):
            QTimer.singleShot(0, func)

    def _handle_session_registry_changed(self):
        manager = getattr(self, "session_manager", None)
        if manager is not None:
            self.active_session_id = manager.active_session_id
        dashboard = getattr(self, "dashboard", None)
        if dashboard is not None and hasattr(dashboard, "refresh_active_sessions"):
            try:
                dashboard.refresh_active_sessions()
            except Exception:
                self.logger.debug("Dashboard session refresh failed", exc_info=True)
        terminals = []
        active_terminal = getattr(self, "terminal", None)
        if active_terminal is not None:
            terminals.append(active_terminal)
        for terminal in list(getattr(self, "session_terminals", {}).values()):
            if terminal is not None and terminal not in terminals:
                terminals.append(terminal)
        for terminal in terminals:
            refresh_picker = getattr(terminal, "_refresh_session_selector", None)
            if callable(refresh_picker):
                try:
                    refresh_picker()
                except Exception:
                    self.logger.debug("Terminal session selector refresh failed", exc_info=True)
            refresh_tabs = getattr(terminal, "_refresh_session_tabs", None)
            if callable(refresh_tabs):
                try:
                    refresh_tabs()
                except Exception:
                    self.logger.debug("Terminal session tabs refresh failed", exc_info=True)

    def _session_terminal_registry(self):
        registry = getattr(self, "session_terminals", None)
        if not isinstance(registry, dict):
            registry = {}
            self.session_terminals = registry
        return registry

    def _remember_session_terminal(self, session_id, terminal):
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id or terminal is None:
            return
        registry = self._session_terminal_registry()
        registry[normalized_session_id] = terminal
        self.terminal = terminal

        destroyed_signal = getattr(terminal, "destroyed", None)
        if destroyed_signal is not None and not bool(getattr(terminal, "_session_destroy_hook_installed", False)):
            destroyed_signal.connect(
                lambda *_args, sid=normalized_session_id, target=terminal: self._forget_session_terminal(
                    sid,
                    target,
                )
            )
            terminal._session_destroy_hook_installed = True

    def _forget_session_terminal(self, session_id, terminal=None):
        normalized_session_id = str(session_id or "").strip()
        registry = self._session_terminal_registry()
        cached = registry.get(normalized_session_id)
        if cached is None:
            return
        if terminal is not None and cached is not terminal:
            return
        registry.pop(normalized_session_id, None)
        if getattr(self, "terminal", None) is cached:
            self.terminal = None
            active_session_id = str(getattr(self, "active_session_id", None) or "").strip()
            replacement = registry.get(active_session_id) if active_session_id else None
            if replacement is None and registry:
                replacement = next(iter(registry.values()))
            if replacement is not None:
                self.terminal = replacement

    def _focus_session_terminal(self, session_id):
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        terminal = self._session_terminal_registry().get(normalized_session_id)
        if terminal is None:
            return None
        self.terminal = terminal
        show_normal = getattr(terminal, "showNormal", None)
        if callable(show_normal):
            show_normal()
        show_window = getattr(terminal, "show", None)
        if callable(show_window):
            show_window()
        raise_window = getattr(terminal, "raise_", None)
        if callable(raise_window):
            raise_window()
        activate_window = getattr(terminal, "activateWindow", None)
        if callable(activate_window):
            activate_window()
        return terminal

    def _session_label(self, session_id):
        manager = getattr(self, "session_manager", None)
        session = manager.get_session(session_id) if manager is not None and hasattr(manager, "get_session") else None
        if session is None:
            return ""
        return str(getattr(session, "label", "") or "").strip()

    def _clone_session_scoped_payload(self, value):
        try:
            return copy.deepcopy(value)
        except Exception:
            return value

    def _session_for_state_sync(self, session_id=None):
        manager = getattr(self, "session_manager", None)
        if manager is None or not hasattr(manager, "get_session"):
            return None
        normalized_session_id = str(session_id or getattr(self, "active_session_id", None) or "").strip()
        if not normalized_session_id:
            return None
        return manager.get_session(normalized_session_id)

    def _sync_session_scoped_state(self, session=None):
        target_session = session or self._session_for_state_sync()
        if target_session is None:
            return

        target_session.autotrade_scope = str(getattr(self, "autotrade_scope", "all") or "all").strip().lower() or "all"
        target_session.autotrade_watchlist = {
            self._normalize_market_data_symbol(symbol)
            for symbol in set(getattr(self, "autotrade_watchlist", set()) or set())
            if str(symbol or "").strip()
        }
        target_session.symbol_strategy_assignments = self._clone_session_scoped_payload(
            getattr(self, "symbol_strategy_assignments", {}) or {}
        )
        target_session.symbol_strategy_rankings = self._clone_session_scoped_payload(
            getattr(self, "symbol_strategy_rankings", {}) or {}
        )
        target_session.symbol_strategy_locks = set(getattr(self, "symbol_strategy_locks", set()) or set())
        target_session.candle_buffers = getattr(self, "candle_buffers", {})
        target_session.orderbook_buffer = getattr(self, "orderbook_buffer", None)
        target_session.ticker_buffer = getattr(self, "ticker_buffer", None)
        target_session.recent_trades_cache = dict(getattr(self, "_recent_trades_cache", {}) or {})
        target_session.recent_trades_last_request_at = dict(getattr(self, "_recent_trades_last_request_at", {}) or {})
        target_session.live_agent_runtime_feed = list(getattr(self, "_live_agent_runtime_feed", []) or [])
        target_session.live_agent_decision_events = self._clone_session_scoped_payload(
            getattr(self, "_live_agent_decision_events", {}) or {}
        )

        proxy = getattr(target_session, "session_controller", None)
        if proxy is not None:
            proxy.autotrade_scope = target_session.autotrade_scope
            proxy.autotrade_watchlist = set(target_session.autotrade_watchlist)
            proxy.symbol_strategy_assignments = self._clone_session_scoped_payload(target_session.symbol_strategy_assignments)
            proxy.symbol_strategy_rankings = self._clone_session_scoped_payload(target_session.symbol_strategy_rankings)
            proxy.symbol_strategy_locks = set(target_session.symbol_strategy_locks)
            proxy.candle_buffers = target_session.candle_buffers
            proxy.orderbook_buffer = target_session.orderbook_buffer
            proxy.ticker_buffer = target_session.ticker_buffer
            proxy._recent_trades_cache = target_session.recent_trades_cache
            proxy._recent_trades_last_request_at = target_session.recent_trades_last_request_at
            proxy._live_agent_runtime_feed = target_session.live_agent_runtime_feed
            proxy._live_agent_decision_events = target_session.live_agent_decision_events

    def _restore_session_scoped_state(self, session):
        if session is None:
            return

        self.autotrade_scope = str(getattr(session, "autotrade_scope", getattr(self, "autotrade_scope", "all")) or "all").strip().lower() or "all"
        self.autotrade_watchlist = set(getattr(session, "autotrade_watchlist", set()) or set())
        self.symbol_strategy_assignments = self._clone_session_scoped_payload(
            getattr(session, "symbol_strategy_assignments", {}) or {}
        )
        self.symbol_strategy_rankings = self._clone_session_scoped_payload(
            getattr(session, "symbol_strategy_rankings", {}) or {}
        )
        self.symbol_strategy_locks = set(getattr(session, "symbol_strategy_locks", set()) or set())

        candle_buffers = getattr(session, "candle_buffers", None)
        if not isinstance(candle_buffers, dict):
            candle_buffers = {}
            session.candle_buffers = candle_buffers
        self.candle_buffers = candle_buffers

        orderbook_buffer = getattr(session, "orderbook_buffer", None)
        if orderbook_buffer is None:
            orderbook_buffer = OrderBookBuffer()
            session.orderbook_buffer = orderbook_buffer
        self.orderbook_buffer = orderbook_buffer

        ticker_buffer = getattr(session, "ticker_buffer", None)
        if ticker_buffer is None:
            ticker_buffer = TickerBuffer(max_length=int(getattr(self, "limit", 1000) or 1000))
            session.ticker_buffer = ticker_buffer
        self.ticker_buffer = ticker_buffer

        self._recent_trades_cache = dict(getattr(session, "recent_trades_cache", {}) or {})
        self._recent_trades_last_request_at = dict(getattr(session, "recent_trades_last_request_at", {}) or {})
        self._recent_trades_tasks = {}

        runtime_feed = getattr(session, "live_agent_runtime_feed", None)
        if not isinstance(runtime_feed, list):
            runtime_feed = []
            session.live_agent_runtime_feed = runtime_feed
        self._live_agent_runtime_feed = runtime_feed

        decision_events = getattr(session, "live_agent_decision_events", None)
        if not isinstance(decision_events, dict):
            decision_events = {}
            session.live_agent_decision_events = decision_events
        self._live_agent_decision_events = decision_events

    def list_trading_sessions(self):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return []
        return manager.list_session_snapshots()

    def active_trading_session_snapshot(self):
        manager = getattr(self, "session_manager", None)
        session = manager.get_active_session() if manager is not None else None
        return session.snapshot().to_dict() if session is not None else None

    def aggregate_session_portfolio(self):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return {}
        return manager.aggregate_portfolio()

    async def route_order_to_best_session(self, symbol, side):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return None
        return await manager.route_order_to_best_session(symbol, side)

    async def activate_trading_session(self, session_id):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            raise RuntimeError("Session manager is not available.")
        session = await manager.activate_session(session_id)
        await self._bind_active_session_state(session)
        await self.initialize_trading(session_id=session.session_id, force_new=False)
        return session

    def request_session_activation(self, session_id):
        if not session_id:
            return None
        return self._create_task(self.activate_trading_session(session_id), f"activate_session:{session_id}")

    async def stop_trading_session(self, session_id):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return None
        session = await manager.stop_session(session_id)
        if session is None:
            return None
        if getattr(self, "active_session_id", None) == session_id:
            await self._bind_active_session_state(session, restart_stream=False)
        return session
    def start_trading_pipeline(self):

        if not self.config or not self.broker:
            self.logger.warning("Cannot start scheduler: config or broker missing")
            return

        # 🔥 dynamic interval from latency
        self.interval = self.dynamic_based_on_latency(
            self.broker.latency_tracker,
            base_interval=2
        )
        self.event_scheduler = EventScheduler(
            event_bus=self.event_bus,
            symbols=self.symbols,
            interval=self.interval,
            batch_size=5,
        )
        self.scheduler=Scheduler()

        # 🔥 start it
        asyncio.create_task(self.event_scheduler.start())
        asyncio.create_task(self.scheduler.start())


    async def start_trading_session(self, session_id):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return None
        session = await manager.start_session(session_id)
        if getattr(self, "active_session_id", None) == session_id:
            await self._bind_active_session_state(session, restart_stream=False)
        return session

    def request_session_stop(self, session_id):
        if not session_id:
            return None
        return self._create_task(self.stop_trading_session(session_id), f"stop_session:{session_id}")

    def request_session_start(self, session_id):
        if not session_id:
            return None
        return self._create_task(self.start_trading_session(session_id), f"start_session:{session_id}")

    async def destroy_trading_session(self, session_id):
        manager = getattr(self, "session_manager", None)
        if manager is None:
            return False
        session_terminal = self._session_terminal_registry().get(str(session_id or "").strip())
        if session_terminal is not None:
            close_terminal = getattr(session_terminal, "close", None)
            if callable(close_terminal):
                try:
                    close_terminal()
                except Exception:
                    self.logger.debug("Session terminal close failed", exc_info=True)
            self._forget_session_terminal(session_id, session_terminal)
        was_active = str(session_id or "") == str(getattr(self, "active_session_id", None) or "")
        destroyed = await manager.destroy_session(session_id)
        if not destroyed:
            return False
        next_active = manager.get_active_session()
        if next_active is not None:
            await self._bind_active_session_state(next_active)
        elif was_active:
            await self._stop_active_market_stream_tasks()
            self.broker = None
            self.trading_system = None
            self.config = None
            self.symbols = []
            self.symbol_catalog = []
            self.balances = {}
            self.balance = {}
            self.connected = False
            try:
                self.connection_signal.emit("disconnected")
            except Exception:
                pass
        self._handle_session_registry_changed()
        return True

    def request_session_destroy(self, session_id):
        if not session_id:
            return None
        return self._create_task(self.destroy_trading_session(session_id), f"destroy_session:{session_id}")

    async def _stop_active_market_stream_tasks(self):
        ticker_task = getattr(self, "_ticker_task", None)
        if ticker_task is not None and not ticker_task.done():
            ticker_task.cancel()
            try:
                await ticker_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.debug("Ticker task shutdown failed", exc_info=True)
        self._ticker_task = None

        recovery_task = getattr(self, "_market_stream_recovery_task", None)
        if recovery_task is not None and not recovery_task.done():
            recovery_task.cancel()
            try:
                await recovery_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.debug("Market stream recovery shutdown failed", exc_info=True)
        self._market_stream_recovery_task = None

        ws_task = getattr(self, "_ws_task", None)
        if ws_task is not None and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.debug("Websocket task shutdown failed", exc_info=True)
        self._ws_task = None

        ws_bus_task = getattr(self, "_ws_bus_task", None)
        if ws_bus_task is not None and not ws_bus_task.done():
            ws_bus_task.cancel()
            try:
                await ws_bus_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.debug("Websocket bus shutdown failed", exc_info=True)
        self._ws_bus_task = None
        self.ws_bus = None
        self.ws_manager = None
    def dynamic_based_on_latency(self,latency_tracker, base_interval=1.0):

        stats = latency_tracker.stats()

        avg = stats["avg"]
        p95 = stats["p95"]
        error_rate = stats["error_rate"]

        # =========================
        # BASE ADJUSTMENT
        # =========================
        interval = base_interval

        # Slow API → increase interval
        if avg > 0.5:
            interval *= 1.5

        if p95 > 1.0:
            interval *= 2.0

        # High errors → throttle hard
        if error_rate > 0.1:
            interval *= 2.5

        # Fast API → speed up
        if avg < 0.2 and error_rate < 0.02:
            interval *= 0.8

        # clamp
        return max(0.5, min(5.0, interval))

    async def _bind_active_session_state(self, session, restart_stream=True):
        if session is None:
            return

        previous_session = self._session_for_state_sync()
        if previous_session is not None and getattr(previous_session, "session_id", None) != getattr(session, "session_id", None):
            self._sync_session_scoped_state(previous_session)

        self.active_session_id = getattr(session, "session_id", None)
        manager = getattr(self, "session_manager", None)
        if manager is not None:
            manager.active_session_id = self.active_session_id

        self.config = getattr(session, "config", None)

        self.broker = getattr(session, "broker", None)
        self.trading_system = getattr(session, "trading_system", None)
        exchange_name = getattr(session, "exchange", None) or self._active_exchange_code() or "broker"
        broker_type = getattr(getattr(self.config, "broker", None), "type", None) if getattr(self, "config", None) is not None else None
        session_symbols = list(getattr(session, "symbols", []) or [])
        session_catalog = list(getattr(session, "symbol_catalog", []) or session_symbols)
        self.symbols = self._filter_symbols_for_trading(session_symbols, broker_type, exchange=exchange_name)
        self.symbol_catalog = self._filter_symbols_for_trading(session_catalog, broker_type, exchange=exchange_name) or list(self.symbols)

        try:
            session.symbols = list(self.symbols)
            session.symbol_catalog = list(self.symbol_catalog)
            self.interval = self.dynamic_based_on_latency(self.broker.latency_tracker,     base_interval=1)
            self.start_trading_pipeline()
        except Exception:
            traceback.print_exc()

        try:
            session.symbols = list(self.symbols)
            session.symbol_catalog = list(self.symbol_catalog)
        except Exception:
            traceback.print_exc()
        self.balances = dict(getattr(session, "balances", {}) or {})
        self.balance = dict(self.balances)
        self.portfolio = getattr(session, "portfolio", None)
        proxy = getattr(session, "session_controller", None)
        self.behavior_guard = getattr(proxy, "behavior_guard", None) if proxy is not None else None
        self.event_bus = getattr(proxy, "event_bus", None) if proxy is not None else None
        self.agent_event_runtime = getattr(proxy, "agent_event_runtime", None) if proxy is not None else None
        self.signal_agents = getattr(proxy, "signal_agents", []) if proxy is not None else []
        self.signal_consensus_agent = getattr(proxy, "signal_consensus_agent", None) if proxy is not None else None
        self.signal_aggregation_agent = getattr(proxy, "signal_aggregation_agent", None) if proxy is not None else None
        self.reasoning_engine = getattr(proxy, "reasoning_engine", None) if proxy is not None else None
        self.agent_memory = getattr(proxy, "agent_memory", None) if proxy is not None else None
        self.connected = bool(getattr(session, "connected", False))
        self.connection_signal.emit("connected" if self.connected else "disconnected")
        self._restore_session_scoped_state(session)
        filtered_watchlist = set(
            self._filter_symbols_for_trading(
                list(getattr(self, "autotrade_watchlist", set()) or set()),
                broker_type,
                exchange=exchange_name,
            )
        )
        self.autotrade_watchlist = filtered_watchlist
        try:
            session.autotrade_watchlist = set(filtered_watchlist)
        except Exception:
            pass

        self._refresh_symbol_universe_tiers(
            catalog_symbols=self.symbol_catalog,
            broker_type=broker_type,
            exchange=exchange_name,
        )
        if self.symbols:
            self._emit_symbols_signal_deferred(str(exchange_name), list(self.symbols))

        self._handle_session_registry_changed()

        if restart_stream and self.connected:
            await self._stop_active_market_stream_tasks()
            await self._restart_telegram_service()
            await self._start_market_stream()
            await self._warmup_visible_candles()
            self._create_task(self.run_startup_health_check(), "startup_health_check")

    async def handle_login(self, config):
        async with self._login_lock:
            session = None
            try:
                if config is None:
                    raise RuntimeError("Invalid configuration received")
                if config.broker is None:
                    raise RuntimeError("Broker configuration missing")

                # Show loading on GUI thread
                self._run_on_gui_thread(lambda: self.dashboard.show_loading())
                await asyncio.sleep(0)
                
                self.config = config
                await self.initialize_license(force_login=False)
                self.strategy_name = Strategy.normalize_strategy_name(getattr(config, "strategy", self.strategy_name))
                self.settings.setValue("strategy/name", self.strategy_name)
                broker_options = dict(getattr(config.broker, "options", None) or {})
                self.set_market_trade_preference(broker_options.get("market_type", self.market_trade_preference))
                self.set_forex_candle_price_component(
                    broker_options.get("candle_price_component", self.forex_candle_price_component)
                )
                broker_options["market_type"] = getattr(self, "market_trade_preference", "auto")
                broker_options["candle_price_component"] = getattr(
                    self,
                    "forex_candle_price_component",
                    "bid",
                )
                try:
                    config.broker.options = broker_options
                except Exception:
                    pass

                hybrid_profile = self._hybrid_server_profile()
                if self._hybrid_server_is_ready(hybrid_profile):
                    await self._connect_hybrid_operator_session(profile=hybrid_profile, interactive=False)
                else:
                    await self._teardown_hybrid_session(clear_status=False)

                broker_type = config.broker.type
                exchange = config.broker.exchange or "unknown"
                if not broker_type:
                    raise RuntimeError("Broker type missing")
                self.logger.info("Initializing session for broker %s", exchange)
                session = await self.session_manager.create_session(config)
                await self._bind_active_session_state(session)
                if self._hybrid_trading_available(exchange):
                    try:
                        await self._register_hybrid_broker_session(session)
                        await self._request_hybrid_market_data_subscription(
                            symbols=getattr(self, "symbols", []) or [],
                            timeframe=getattr(self, "time_frame", "1h"),
                        )
                    except Exception as exc:
                        self.logger.warning("Hybrid broker registration failed; continuing locally: %s", exc)
                        self._set_hybrid_status(
                            f"Server session is connected, but broker authority registration fell back locally: {exc}",
                            tone="error",
                        )
                self._restore_performance_state()
                self._update_performance_equity(self.balances)
                self._performance_recorded_orders.clear()

                await self.initialize_trading(session_id=session.session_id, force_new=True)
                self._emit_symbols_signal_deferred(exchange, self.symbols)
                await self._create_task(
                    self._schedule_startup_strategy_auto_assignment(
                        exchange=exchange,
                    ),
                    name="startup_strategy_auto_assignment"
                )

            except Exception as e:
                if session is not None:
                    try:
                        await self.session_manager.destroy_session(session.session_id)
                    except Exception:
                        self.logger.debug("Failed to roll back incomplete session %s", getattr(session, "session_id", None), exc_info=True)
                self.connected = False
                self.connection_signal.emit("disconnected")
                self.logger.exception("Initialization failed")
                
                # Show error dialog on GUI thread
                error_msg = self._friendly_initialization_error(e)
                self._run_on_gui_thread(
                    lambda: QMessageBox.critical(
                        self,
                        "Initialization Failed",
                        error_msg,
                    )
                )
            finally:
                # Hide loading on GUI thread
                self._run_on_gui_thread(lambda: self.dashboard.hide_loading())
                self._run_on_gui_thread(lambda: self._handle_session_registry_changed())

    async def _fetch_symbols(self, broker):
        symbols = None

        if hasattr(broker, "fetch_symbol"):
            symbols = await broker.fetch_symbol()
        elif hasattr(broker, "fetch_symbols"):
            symbols = await broker.fetch_symbols()

        if isinstance(symbols, dict):
            instruments = symbols.get("instruments", [])
            normalized = []
            for item in instruments:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("displayName")
                    if name:
                        normalized.append(name)
            symbols = normalized

        if not symbols:
            return self._configured_symbol_hints_for_broker(broker)

        return [s for s in symbols if s]

    def _configured_symbol_hints_for_broker(self, broker=None):
        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        normalized = []
        sources = (
            getattr(broker, "params", None) if broker is not None else None,
            getattr(broker, "options", None) if broker is not None else None,
            getattr(broker_cfg, "params", None) if broker_cfg is not None else None,
            getattr(broker_cfg, "options", None) if broker_cfg is not None else None,
        )
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in ("symbols", "default_symbols", "watchlist_symbols"):
                for symbol in self._normalize_symbol_sequence(source.get(key)):
                    if symbol not in normalized:
                        normalized.append(symbol)
        return normalized

    def _active_market_trade_preference_value(self):
        broker = getattr(self, "broker", None)
        if broker is not None:
            for attr in ("resolved_market_preference", "market_preference"):
                candidate = normalize_market_venue(getattr(broker, attr, None), default="auto")
                if candidate != "auto":
                    return candidate
        return normalize_market_venue(getattr(self, "market_trade_preference", None), default="auto")

    def _broker_market_for_symbol(self, symbol):
        if not isinstance(symbol, str) or not symbol.strip():
            return None

        markets = getattr(getattr(getattr(self, "broker", None), "exchange", None), "markets", None)
        if not isinstance(markets, dict) or not markets:
            return None

        normalized_symbol = self._normalize_market_data_symbol(symbol)
        direct_market = markets.get(symbol)
        if isinstance(direct_market, dict):
            return direct_market

        for market_symbol, market in markets.items():
            if not isinstance(market, dict):
                continue
            declared_symbol = str(market.get("symbol") or market_symbol or "").strip()
            normalized_market_symbol = self._normalize_market_data_symbol(declared_symbol)
            if normalized_market_symbol == normalized_symbol:
                return market

        return None

    def _symbol_market_is_derivative(self, symbol, market=None):
        market = market if isinstance(market, dict) else self._broker_market_for_symbol(symbol)
        if isinstance(market, dict):
            if bool(market.get("option")):
                return False
            return any(bool(market.get(key)) for key in ("contract", "swap", "future"))

        normalized_symbol = str(symbol or "").upper().strip()
        return ":" in normalized_symbol or normalized_symbol.endswith(("-PERP", "/PERP")) or "PERPETUAL" in normalized_symbol

    def _market_symbol_base_quote(self, symbol, market=None):
        market = market if isinstance(market, dict) else self._broker_market_for_symbol(symbol)
        if isinstance(market, dict):
            base = str(market.get("base") or "").upper().strip()
            quote = str(market.get("quote") or market.get("settle") or "").upper().strip()
            if base and quote:
                return base, quote

        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if "/" not in normalized_symbol:
            return normalized_symbol, ""

        base, quote = normalized_symbol.split("/", 1)
        return base.strip(), quote.split(":", 1)[0].strip()

    def _market_matches_trade_preference(self, symbol, market=None, preference=None):
        normalized_preference = normalize_market_venue(
            self._active_market_trade_preference_value() if preference is None else preference,
            default="auto",
        )
        if normalized_preference == "auto":
            return True

        market = market if isinstance(market, dict) else self._broker_market_for_symbol(symbol)
        if normalized_preference == "derivative":
            return self._symbol_market_is_derivative(symbol, market=market)
        if normalized_preference == "option":
            return bool((market or {}).get("option"))
        if normalized_preference == "otc":
            return bool((market or {}).get("otc"))
        if normalized_preference == "spot":
            if bool((market or {}).get("option")) or bool((market or {}).get("otc")):
                return False
            return not self._symbol_market_is_derivative(symbol, market=market)
        return True

    def _resolve_preferred_market_symbol(self, symbol, preference=None):
        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if not normalized_symbol:
            return ""

        exact_market = self._broker_market_for_symbol(normalized_symbol)
        exact_symbol = str((exact_market or {}).get("symbol") or normalized_symbol).strip().upper() or normalized_symbol
        normalized_preference = normalize_market_venue(
            self._active_market_trade_preference_value() if preference is None else preference,
            default="auto",
        )
        if self._market_matches_trade_preference(exact_symbol, market=exact_market, preference=normalized_preference):
            return exact_symbol

        markets = getattr(getattr(getattr(self, "broker", None), "exchange", None), "markets", None)
        if not isinstance(markets, dict) or not markets:
            return exact_symbol

        base, quote = self._market_symbol_base_quote(normalized_symbol, market=exact_market)
        if not base or not quote:
            return exact_symbol

        candidates = []
        for market_symbol, market in markets.items():
            if not isinstance(market, dict):
                continue

            declared_symbol = str(market.get("symbol") or market_symbol or "").strip().upper()
            if not declared_symbol:
                continue

            candidate_base, candidate_quote = self._market_symbol_base_quote(declared_symbol, market=market)
            if candidate_base != base or candidate_quote != quote:
                continue
            if not self._market_matches_trade_preference(declared_symbol, market=market, preference=normalized_preference):
                continue

            score = 0
            if declared_symbol == normalized_symbol:
                score += 1000
            if bool(market.get("active", True)):
                score += 100
            if normalized_preference == "derivative":
                settle_currency = str(market.get("settle") or "").upper().strip()
                if settle_currency == quote:
                    score += 20
                if bool(market.get("future")):
                    score += 10
                if bool(market.get("swap")):
                    score += 5
            elif normalized_preference == "spot" and bool(market.get("spot")):
                score += 10

            candidates.append((score, declared_symbol))

        if candidates:
            candidates.sort(key=lambda item: (-item[0], item[1]))
            return candidates[0][1]

        return exact_symbol

    def _filter_symbols_for_trading(self, symbols, broker_type, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        normalized_type = self._active_broker_type(broker_type=broker_type, exchange=exchange_code)
        active_preference = self._active_market_trade_preference_value()
        plausible_symbols = [
            self._normalize_market_data_symbol(symbol)
            for symbol in list(symbols or [])
            if self._is_plausible_market_symbol(symbol, broker_type=broker_type, exchange=exchange_code)
        ]

        if exchange_code in {"stellar", "solana"}:
            filtered = []
            for symbol in plausible_symbols:
                if not isinstance(symbol, str) or "/" not in symbol:
                    continue

                base, quote = symbol.upper().split("/", 1)
                if not re.fullmatch(r"[A-Z]{2,12}", base):
                    continue
                if not re.fullmatch(r"[A-Z]{2,12}", quote):
                    continue
                filtered.append(f"{base}/{quote}")

            return list(dict.fromkeys(filtered))

        if normalized_type == "forex" or exchange_code == "oanda":
            filtered = [
                symbol
                for symbol in plausible_symbols
                if self._is_supported_oanda_symbol(symbol)
            ]
            return list(dict.fromkeys(filtered))

        if normalized_type != "crypto":
            return list(dict.fromkeys(plausible_symbols))

        if exchange_code == "coinbase" and active_preference == "derivative":
            filtered = []
            for symbol in plausible_symbols:
                if not isinstance(symbol, str) or not symbol.strip():
                    continue

                market = self._broker_market_for_symbol(symbol)
                if not self._symbol_market_is_derivative(symbol, market=market):
                    continue

                normalized_symbol = str((market or {}).get("symbol") or symbol).strip().upper()
                if normalized_symbol:
                    filtered.append(normalized_symbol)

            return list(dict.fromkeys(filtered))

        filtered = []
        for symbol in plausible_symbols:
            if not isinstance(symbol, str) or "/" not in symbol:
                continue

            base, quote = symbol.upper().split("/", 1)

            if quote not in self.ALLOWED_CRYPTO_QUOTES:
                continue

            if not re.fullmatch(r"[A-Z]{2,12}", base):
                continue
            if base in self.BANNED_BASE_TOKENS or quote in self.BANNED_BASE_TOKENS:
                continue
            if any(base.endswith(sfx) for sfx in self.BANNED_BASE_SUFFIXES):
                continue

            filtered.append(f"{base}/{quote}")

        return list(dict.fromkeys(filtered))

    def _is_supported_oanda_symbol(self, symbol):
        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if not normalized_symbol or "/" not in normalized_symbol:
            return False

        base, quote_segment = normalized_symbol.split("/", 1)
        quote, settle = (quote_segment.split(":", 1) + [""])[:2]
        base = str(base or "").upper().strip()
        quote = str(quote or "").upper().strip()
        settle = str(settle or "").upper().strip()

        if quote not in self.FOREX_SYMBOL_QUOTES:
            return False
        if settle and settle not in self.FOREX_SYMBOL_QUOTES:
            return False

        if base in self.FOREX_SYMBOL_QUOTES:
            return True
        if base in self.OANDA_CFD_BASES:
            return True
        if any(character.isdigit() for character in base):
            return bool(re.fullmatch(r"[A-Z0-9]{2,20}", base))
        return False

    def _is_spot_only_exchange_profile(self, broker_type=None, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        if exchange_code == "coinbase":
            return self._active_market_trade_preference_value() != "derivative"
        if exchange_code in SPOT_ONLY_EXCHANGES or exchange_code in {"stellar", "solana"}:
            return True
        return str(broker_type or "").strip().lower() == "stocks"

    def _positive_balance_asset_codes(self, balances=None):
        if not isinstance(balances, dict):
            return set()

        skip_keys = {
            "free",
            "used",
            "total",
            "info",
            "raw",
            "equity",
            "cash",
            "balance",
            "account_value",
            "total_account_value",
            "net_liquidation",
            "position_value",
            "positions_value",
            "asset_balances",
        }
        asset_codes = set()
        buckets = [
            balances.get("asset_balances"),
            balances.get("total"),
            balances.get("free"),
            balances.get("used"),
        ]
        candidate_buckets = [bucket for bucket in buckets if isinstance(bucket, dict)]
        if not candidate_buckets:
            candidate_buckets = [balances]

        for bucket in candidate_buckets:
            for asset_code, raw_value in bucket.items():
                normalized_code = str(asset_code or "").upper().strip()
                if not normalized_code or normalized_code in skip_keys:
                    continue
                try:
                    numeric_value = float(raw_value or 0.0)
                except Exception:
                    continue
                if numeric_value > 0:
                    asset_codes.add(normalized_code)
        return asset_codes

    @staticmethod
    def _normalize_symbol_sequence(symbols):
        normalized = []
        for symbol in list(symbols or []):
            value = AppController._normalize_market_data_symbol(symbol)
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @classmethod
    def _normalize_autotrade_scope(cls, scope):
        normalized = str(scope or "all").strip().lower().replace("_", " ").replace("-", " ")
        aliases = {
            "selected symbol": "selected",
            "watch list": "watchlist",
            "best ranked": "ranked",
            "top ranked": "ranked",
        }
        normalized = aliases.get(normalized, normalized)
        normalized = normalized.replace(" ", "")
        if normalized not in {"all", "selected", "watchlist", "ranked"}:
            return "all"
        return normalized

    @classmethod
    def _autotrade_scope_display_name(cls, scope):
        labels = {
            "all": "All Symbols",
            "selected": "Selected Symbol",
            "watchlist": "Watchlist",
            "ranked": "Best Ranked",
        }
        return labels.get(cls._normalize_autotrade_scope(scope), "All Symbols")

    def _active_broker_type(self, broker_type=None, exchange=None):
        normalized_type = str(broker_type or "").strip().lower()
        if normalized_type:
            return normalized_type

        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        if broker_cfg is not None and getattr(broker_cfg, "type", None):
            return str(broker_cfg.type).strip().lower()

        exchange_code = self._active_exchange_code(exchange=exchange)
        if exchange_code in {"coinbase", "binance", "binanceus", "kraken", "kucoin", "bybit", "stellar", "solana"}:
            return "crypto"
        if exchange_code == "oanda":
            return "forex"
        if exchange_code == "alpaca":
            return "stocks"
        if exchange_code == "paper":
            return "paper"
        return ""

    def _symbol_universe_policy(self, broker_type=None, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        normalized_type = self._active_broker_type(broker_type=broker_type, exchange=exchange)

        if exchange_code == "coinbase":
            return {
                "watchlist_limit": int(self.COINBASE_WATCHLIST_SYMBOL_LIMIT or 24),
                "discovery_batch_size": int(self.COINBASE_DISCOVERY_BATCH_SIZE or 4),
                "discovery_priority_count": int(self.COINBASE_DISCOVERY_PRIORITY_COUNT or 2),
                "auto_assignment_limit": int(self.COINBASE_AUTO_ASSIGN_SYMBOL_LIMIT or 6),
            }
        if exchange_code == "solana":
            return {
                "watchlist_limit": int(self.SOLANA_SYMBOL_WATCHLIST_LIMIT or 18),
                "discovery_batch_size": int(self.SOLANA_DISCOVERY_BATCH_SIZE or 6),
                "discovery_priority_count": 2,
                "auto_assignment_limit": int(self.SOLANA_DISCOVERY_BATCH_SIZE or 6),
            }
        if exchange_code == "stellar":
            return {
                "watchlist_limit": int(self.STELLAR_SYMBOL_WATCHLIST_LIMIT or 18),
                "discovery_batch_size": int(self.STELLAR_DISCOVERY_BATCH_SIZE or 6),
                "discovery_priority_count": 2,
                "auto_assignment_limit": int(self.STELLAR_DISCOVERY_BATCH_SIZE or 6),
            }
        if exchange_code in SPOT_ONLY_EXCHANGES:
            return {
                "watchlist_limit": int(self.SPOT_ONLY_SYMBOL_WATCHLIST_LIMIT or 20),
                "discovery_batch_size": int(self.SPOT_ONLY_DISCOVERY_BATCH_SIZE or 8),
                "discovery_priority_count": 3,
                "auto_assignment_limit": int(self.SPOT_ONLY_DISCOVERY_BATCH_SIZE or 8),
            }
        if normalized_type == "forex":
            return {
                "watchlist_limit": int(self.FOREX_SYMBOL_WATCHLIST_LIMIT or 20),
                "discovery_batch_size": int(self.FOREX_DISCOVERY_BATCH_SIZE or 8),
                "discovery_priority_count": 3,
                "auto_assignment_limit": int(self.FOREX_DISCOVERY_BATCH_SIZE or 8),
            }
        if normalized_type == "stocks":
            return {
                "watchlist_limit": int(self.STOCKS_SYMBOL_WATCHLIST_LIMIT or 24),
                "discovery_batch_size": int(self.STOCKS_DISCOVERY_BATCH_SIZE or 8),
                "discovery_priority_count": 3,
                "auto_assignment_limit": int(self.STOCKS_DISCOVERY_BATCH_SIZE or 8),
            }
        if normalized_type == "paper":
            return {
                "watchlist_limit": int(self.PAPER_SYMBOL_WATCHLIST_LIMIT or 24),
                "discovery_batch_size": int(self.PAPER_DISCOVERY_BATCH_SIZE or 10),
                "discovery_priority_count": 3,
                "auto_assignment_limit": int(self.PAPER_DISCOVERY_BATCH_SIZE or 10),
            }
        return {
            "watchlist_limit": int(self.DEFAULT_SYMBOL_WATCHLIST_LIMIT or 36),
            "discovery_batch_size": int(self.DEFAULT_DISCOVERY_BATCH_SIZE or 10),
            "discovery_priority_count": int(self.DEFAULT_DISCOVERY_PRIORITY_COUNT or 3),
            "auto_assignment_limit": int(self.DEFAULT_DISCOVERY_BATCH_SIZE or 10),
        }

    def _limit_runtime_symbols(self, symbols, broker_type, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        normalized_symbols = self._normalize_symbol_sequence(symbols)
        if exchange_code in {"stellar", "solana"}:
            return normalized_symbols
        if broker_type != "crypto":
            return normalized_symbols
        if exchange_code == "coinbase":
            candidate_symbols = self._filter_symbols_for_trading(normalized_symbols, broker_type, exchange_code)
            prioritized = self._prioritize_symbols_for_trading(
                candidate_symbols,
                top_n=len(candidate_symbols),
                quote_priority=self.COINBASE_QUOTE_PRIORITY,
                account_assets=self._positive_balance_asset_codes(getattr(self, "balances", None)),
            )
            return prioritized if prioritized else candidate_symbols
        prioritized = self._prioritize_symbols_for_trading(normalized_symbols, top_n=len(normalized_symbols))
        return prioritized if prioritized else normalized_symbols

    def _refresh_symbol_universe_tiers(self, catalog_symbols=None, broker_type=None, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        normalized_type = self._active_broker_type(broker_type=broker_type, exchange=exchange)
        policy = self._symbol_universe_policy(broker_type=normalized_type, exchange=exchange_code)
        active_symbols = self._filter_symbols_for_trading(
            self._normalize_symbol_sequence(getattr(self, "symbols", []) or []),
            normalized_type,
            exchange=exchange_code,
        )

        normalized_catalog = self._filter_symbols_for_trading(
            self._normalize_symbol_sequence(catalog_symbols),
            normalized_type,
            exchange=exchange_code,
        )
        if not normalized_catalog:
            existing_catalog = (getattr(self, "_symbol_universe_tiers", {}) or {}).get("catalog", [])
            normalized_catalog = self._filter_symbols_for_trading(
                self._normalize_symbol_sequence(existing_catalog),
                normalized_type,
                exchange=exchange_code,
            )
        if not normalized_catalog:
            broker_symbols = getattr(getattr(self, "broker", None), "symbols", None)
            normalized_catalog = self._filter_symbols_for_trading(
                self._normalize_symbol_sequence(broker_symbols or active_symbols),
                normalized_type,
                exchange=exchange_code,
            )

        explicit_watchlist = sorted(
            [
                symbol
                for symbol in self._normalize_symbol_sequence(getattr(self, "autotrade_watchlist", set()) or set())
                if symbol in normalized_catalog
            ]
        )
        account_assets = self._positive_balance_asset_codes(getattr(self, "balances", None))
        if normalized_type == "crypto":
            prioritized_catalog = self._prioritize_symbols_for_trading(
                normalized_catalog,
                top_n=max(int(policy["watchlist_limit"] or 0), len(active_symbols), int(policy["discovery_batch_size"] or 0), 1),
                quote_priority=self.COINBASE_QUOTE_PRIORITY if exchange_code == "coinbase" else self.QUOTE_PRIORITY,
                account_assets=account_assets,
            )
        else:
            prioritized_catalog = list(normalized_catalog)

        watchlist_pool = []
        for source in (active_symbols, explicit_watchlist, prioritized_catalog, normalized_catalog):
            for symbol in source:
                if symbol in normalized_catalog and symbol not in watchlist_pool:
                    watchlist_pool.append(symbol)
        watchlist_limit = max(int(policy["watchlist_limit"] or 0), len(active_symbols), 1)
        watchlist_symbols = watchlist_pool[:watchlist_limit]
        background_catalog = [symbol for symbol in normalized_catalog if symbol not in watchlist_symbols]

        if background_catalog:
            cursor = int(getattr(self, "_symbol_universe_rotation_cursor", 0) or 0) % len(background_catalog)
        else:
            cursor = 0
        self._symbol_universe_rotation_cursor = cursor
        self._symbol_universe_tiers = {
            "exchange": exchange_code or "",
            "broker_type": normalized_type,
            "active": list(active_symbols),
            "watchlist": list(watchlist_symbols),
            "catalog": list(normalized_catalog),
            "background_catalog": list(background_catalog),
            "rotation_cursor": cursor,
            "policy": dict(policy),
            "last_batch": list(getattr(self, "_symbol_universe_tiers", {}).get("last_batch", []) or []),
        }
        return dict(self._symbol_universe_tiers)

    def get_symbol_universe_snapshot(self):
        tiers = dict(getattr(self, "_symbol_universe_tiers", {}) or {})
        for key in ("active", "watchlist", "catalog", "background_catalog", "last_batch"):
            tiers[key] = list(tiers.get(key, []) or [])
        tiers["rotation_cursor"] = int(tiers.get("rotation_cursor", 0) or 0)
        return tiers

    def _rotating_discovery_batch(self, limit=None, advance=False, broker_type=None, exchange=None):
        tiers = self._refresh_symbol_universe_tiers(broker_type=broker_type, exchange=exchange)
        watchlist_symbols = list(tiers.get("watchlist", []) or [])
        background_catalog = list(tiers.get("background_catalog", []) or [])
        policy = dict(tiers.get("policy", {}) or self._symbol_universe_policy(broker_type=broker_type, exchange=exchange))
        if limit is None:
            limit = int(policy.get("discovery_batch_size", self.DEFAULT_DISCOVERY_BATCH_SIZE) or self.DEFAULT_DISCOVERY_BATCH_SIZE)
        batch_limit = max(int(limit or 0), 1)
        priority_count = min(
            max(int(policy.get("discovery_priority_count", self.DEFAULT_DISCOVERY_PRIORITY_COUNT) or 0), 0),
            batch_limit,
            len(watchlist_symbols),
        )
        batch = list(watchlist_symbols[:priority_count])
        remaining = batch_limit - len(batch)
        cursor = int(getattr(self, "_symbol_universe_rotation_cursor", 0) or 0)
        rotating_symbols = []
        if background_catalog and remaining > 0:
            cursor = cursor % len(background_catalog)
            for offset in range(remaining):
                rotating_symbols.append(background_catalog[(cursor + offset) % len(background_catalog)])
            if advance:
                cursor = (cursor + len(rotating_symbols)) % len(background_catalog)
        batch.extend(rotating_symbols)
        if len(batch) < batch_limit:
            for symbol in watchlist_symbols[priority_count:]:
                if symbol not in batch:
                    batch.append(symbol)
                if len(batch) >= batch_limit:
                    break
        batch = self._normalize_symbol_sequence(batch)
        if advance:
            self._symbol_universe_rotation_cursor = cursor if background_catalog else 0
            tiers = dict(getattr(self, "_symbol_universe_tiers", {}) or {})
            tiers["rotation_cursor"] = int(self._symbol_universe_rotation_cursor or 0)
            tiers["last_batch"] = list(batch)
            self._symbol_universe_tiers = tiers
        return batch

    async def _select_trade_symbols(self, symbols, broker_type, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        if str(exchange or "").lower() == "solana":
            preferred_quotes = ("USDC", "SOL")
            account_assets = self._positive_balance_asset_codes(getattr(self, "balances", None))
            unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols if symbol))

            def solana_sort_key(symbol):
                if "/" not in symbol:
                    return 99, 1, symbol
                base, quote = symbol.split("/", 1)
                quote_rank = preferred_quotes.index(quote) if quote in preferred_quotes else len(preferred_quotes)
                account_rank = 0 if base in account_assets or quote in account_assets else 1
                return (quote_rank, account_rank, base, quote)

            ordered_symbols = sorted(unique_symbols, key=solana_sort_key)
            return ordered_symbols[:20]

        if str(exchange or "").lower() == "stellar":
            prioritized = []
            preferred_quotes = ("USDC", "USDT", "XLM", "EURC")
            account_assets = {
                str(code).upper()
                for code in (getattr(getattr(self, "broker", None), "_account_asset_codes", []) or [])
            }
            unique_symbols = list(dict.fromkeys(str(symbol).upper() for symbol in symbols if symbol))

            def stellar_sort_key(symbol):
                if "/" not in symbol:
                    return (99, 1, 1, symbol)
                base, quote = symbol.split("/", 1)
                quote_rank = preferred_quotes.index(quote) if quote in preferred_quotes else len(preferred_quotes)
                account_rank = 0 if base in account_assets or quote in account_assets else 1
                length_rank = 0 if len(base) <= 5 else 1
                return (quote_rank, account_rank, length_rank, base, quote)

            ordered_symbols = sorted(unique_symbols, key=stellar_sort_key)
            for quote in preferred_quotes:
                for symbol in ordered_symbols:
                    if "/" not in symbol:
                        continue
                    base, current_quote = symbol.split("/", 1)
                    if current_quote != quote:
                        continue
                    normalized = f"{base}/{current_quote}"
                    if normalized not in prioritized:
                        prioritized.append(normalized)
            for symbol in ordered_symbols:
                normalized = str(symbol).upper()
                if normalized not in prioritized:
                    prioritized.append(normalized)

            validated = []
            max_xlm_pairs = 4
            xlm_pairs = 0
            for symbol in prioritized[:40]:
                book = await self._safe_fetch_orderbook(symbol, limit=1)
                bids = (book or {}).get("bids") or []
                asks = (book or {}).get("asks") or []
                if not bids and not asks:
                    continue
                if symbol.endswith("/XLM"):
                    if xlm_pairs >= max_xlm_pairs:
                        continue
                    xlm_pairs += 1
                validated.append(symbol)
                if len(validated) >= 12:
                    break

            return validated if validated else prioritized[:12]

        return self._limit_runtime_symbols(symbols, broker_type, exchange=exchange_code)

    def _prioritize_symbols_for_trading(self, symbols, top_n=30, quote_priority=None, account_assets=None):
        account_asset_codes = {
            str(code or "").upper().strip()
            for code in (account_assets or [])
            if str(code or "").strip()
        }
        normalized_quote_priority = {
            str(quote or "").upper().strip(): int(rank)
            for quote, rank in (quote_priority or self.QUOTE_PRIORITY).items()
            if str(quote or "").strip()
        }

        def sort_key(symbol):
            if not isinstance(symbol, str) or not symbol.strip():
                return (99, 99, 99, "")

            market = self._broker_market_for_symbol(symbol)
            base, quote = self._market_symbol_base_quote(symbol, market=market)
            if not base or not quote:
                return (99, 99, 99, str(symbol).upper())

            is_derivative = self._symbol_market_is_derivative(symbol, market=market)
            account_rank = 0 if base in account_asset_codes or (is_derivative and quote in account_asset_codes) else 1
            preferred_rank = self.PREFERRED_BASES.index(base) if base in self.PREFERRED_BASES else len(self.PREFERRED_BASES)
            quote_rank = normalized_quote_priority.get(quote, 99)
            return (account_rank, quote_rank, preferred_rank, f"{base}/{quote}")

        ordered = sorted(dict.fromkeys(symbols), key=sort_key)
        return ordered[:top_n]

    async def _rank_symbols_by_risk_return(self, symbols, max_candidates=120, top_n=30):
        candidates = symbols[:max_candidates]
        semaphore = asyncio.Semaphore(8)
        scored = []

        async def score_symbol(symbol):
            async with semaphore:
                try:
                    candles = await self._safe_fetch_ohlcv(symbol, timeframe="1h", limit=120)
                    if not candles or len(candles) < 40:
                        return

                    closes = []
                    for row in candles:
                        if isinstance(row, (list, tuple)) and len(row) >= 5:
                            closes.append(float(row[4]))

                    if len(closes) < 30:
                        return

                    rets = []
                    for i in range(1, len(closes)):
                        prev = closes[i - 1]
                        cur = closes[i]
                        if prev > 0:
                            rets.append((cur - prev) / prev)

                    if len(rets) < 20:
                        return

                    mean_ret = sum(rets) / len(rets)
                    var = sum((r - mean_ret) ** 2 for r in rets) / max(len(rets) - 1, 1)
                    vol = var ** 0.5
                    if vol <= 1e-9:
                        return

                    total_return = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0.0
                    sharpe_like = mean_ret / vol
                    score = (0.7 * sharpe_like) + (0.3 * total_return)

                    scored.append((symbol, score))

                except Exception:
                    return

        await asyncio.gather(*(score_symbol(sym) for sym in candidates))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:top_n]]

    async def _fetch_balances(self, broker):
        balances = await broker.fetch_balance()
        if balances is None:
            return {}
        if isinstance(balances, dict):
            return balances
        return {"raw": balances}

    async def update_balance(self):
        if not self.broker:
            return

        self.balances = await self._fetch_balances(self.broker)
        self.balance = self.balances
        self._refresh_symbol_universe_tiers()
        equity = self._update_performance_equity(self.balances)
        self._update_behavior_guard_equity(self.balances)
        if equity is not None:
            self.equity_signal.emit(equity)

    async def initialize_trading(self, session_id=None, force_new=False):
        try:
            resolved_session_id = str(session_id or getattr(self, "active_session_id", None) or "").strip()
            if resolved_session_id and not force_new:
                existing_terminal = self._focus_session_terminal(resolved_session_id)
                if existing_terminal is not None:
                    bind_session = getattr(existing_terminal, "bind_session", None)
                    if callable(bind_session):
                        bind_session(resolved_session_id, label=self._session_label(resolved_session_id))
                    self._handle_session_registry_changed()
                    return
            elif not resolved_session_id and self.terminal:
                show_normal = getattr(self.terminal, "showNormal", None)
                if callable(show_normal):
                    show_normal()
                show_window = getattr(self.terminal, "show", None)
                if callable(show_window):
                    show_window()
                raise_window = getattr(self.terminal, "raise_", None)
                if callable(raise_window):
                    raise_window()
                activate_window = getattr(self.terminal, "activateWindow", None)
                if callable(activate_window):
                    activate_window()
                self._handle_session_registry_changed()
                return

            restore_task = getattr(self, "_terminal_runtime_restore_task", None)
            if restore_task is not None and not restore_task.done():
                restore_task.cancel()
            self._terminal_runtime_restore_task = None

            terminal = Terminal(self)
            if resolved_session_id:
                bind_session = getattr(terminal, "bind_session", None)
                if callable(bind_session):
                    bind_session(resolved_session_id, label=self._session_label(resolved_session_id))
                self._remember_session_terminal(resolved_session_id, terminal)
            else:
                self.terminal = terminal
            show_window = getattr(terminal, "show", None)
            if callable(show_window):
                show_window()
            raise_window = getattr(terminal, "raise_", None)
            if callable(raise_window):
                raise_window()
            activate_window = getattr(terminal, "activateWindow", None)
            if callable(activate_window):
                activate_window()
            await asyncio.sleep(0)
            self._fit_window_to_available_screen()
            QTimer.singleShot(0, self._fit_window_to_available_screen)
            terminal.logout_requested.connect(self._on_logout_requested)
            wait_until_ready = getattr(terminal, "wait_until_ready", None)
            if callable(wait_until_ready):
                await wait_until_ready(timeout=20.0)
            elif hasattr(terminal, "load_persisted_runtime_data"):
                self._terminal_runtime_restore_task = self._create_task(
                    self._restore_terminal_runtime_data(terminal),
                    "terminal_runtime_restore",
                )
            equity = self._extract_balance_equity_value(getattr(self, "balances", {}))
            if equity is not None:
                self.equity_signal.emit(equity)
            self._create_task(self.run_startup_health_check(), "startup_health_check")

        except Exception as e:
            self.logger.exception("Terminal initialization failed")
            QMessageBox.critical(self, "Initialization Failed", str(e))

    async def _restore_terminal_runtime_data(self, terminal):
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(0)
            if terminal is None:
                return
            if getattr(terminal, "_ui_shutting_down", False):
                return
            if hasattr(terminal, "load_initial_runtime_data"):
                await terminal.load_initial_runtime_data()
            elif hasattr(terminal, "load_persisted_runtime_data"):
                await terminal.load_persisted_runtime_data()
        finally:
            if getattr(self, "_terminal_runtime_restore_task", None) is current_task:
                self._terminal_runtime_restore_task = None

    def update_integration_settings(
            self,
            telegram_enabled=None,
            telegram_bot_token=None,
            telegram_chat_id=None,
            trade_close_notifications_enabled=None,
            trade_close_notify_telegram=None,
            trade_close_notify_email=None,
            trade_close_notify_sms=None,
            trade_close_email_host=None,
            trade_close_email_port=None,
            trade_close_email_username=None,
            trade_close_email_password=None,
            trade_close_email_from=None,
            trade_close_email_to=None,
            trade_close_email_starttls=None,
            trade_close_sms_account_sid=None,
            trade_close_sms_auth_token=None,
            trade_close_sms_from_number=None,
            trade_close_sms_to_number=None,
            openai_api_key=None,
            openai_model=None,
            news_enabled=None,
            news_autotrade_enabled=None,
            news_draw_on_chart=None,
            news_feed_url=None,
    ):
        if telegram_enabled is not None:
            self.telegram_enabled = bool(telegram_enabled)
        if telegram_bot_token is not None:
            self.telegram_bot_token = str(telegram_bot_token or "").strip()
        if telegram_chat_id is not None:
            self.telegram_chat_id = str(telegram_chat_id or "").strip()
        if trade_close_notifications_enabled is not None:
            self.trade_close_notifications_enabled = bool(trade_close_notifications_enabled)
        if trade_close_notify_telegram is not None:
            self.trade_close_notify_telegram = bool(trade_close_notify_telegram)
        if trade_close_notify_email is not None:
            self.trade_close_notify_email = bool(trade_close_notify_email)
        if trade_close_notify_sms is not None:
            self.trade_close_notify_sms = bool(trade_close_notify_sms)
        if trade_close_email_host is not None:
            self.trade_close_email_host = str(trade_close_email_host or "").strip()
        if trade_close_email_port is not None:
            try:
                self.trade_close_email_port = max(1, int(trade_close_email_port))
            except Exception:
                self.trade_close_email_port = 587
        if trade_close_email_username is not None:
            self.trade_close_email_username = str(trade_close_email_username or "").strip()
        if trade_close_email_password is not None:
            self.trade_close_email_password = str(trade_close_email_password or "")
        if trade_close_email_from is not None:
            self.trade_close_email_from = str(trade_close_email_from or "").strip()
        if trade_close_email_to is not None:
            self.trade_close_email_to = str(trade_close_email_to or "").strip()
        if trade_close_email_starttls is not None:
            self.trade_close_email_starttls = bool(trade_close_email_starttls)
        if trade_close_sms_account_sid is not None:
            self.trade_close_sms_account_sid = str(trade_close_sms_account_sid or "").strip()
        if trade_close_sms_auth_token is not None:
            self.trade_close_sms_auth_token = str(trade_close_sms_auth_token or "")
        if trade_close_sms_from_number is not None:
            self.trade_close_sms_from_number = str(trade_close_sms_from_number or "").strip()
        if trade_close_sms_to_number is not None:
            self.trade_close_sms_to_number = str(trade_close_sms_to_number or "").strip()
        if openai_api_key is not None:
            self.openai_api_key = str(openai_api_key or "").strip()
        if openai_model is not None:
            self.openai_model = str(openai_model or "gpt-5-mini").strip() or "gpt-5-mini"
        if news_enabled is not None:
            self.news_enabled = bool(news_enabled)
        if news_autotrade_enabled is not None:
            self.news_autotrade_enabled = bool(news_autotrade_enabled)
        if news_draw_on_chart is not None:
            self.news_draw_on_chart = bool(news_draw_on_chart)
        if news_feed_url is not None:
            self.news_feed_url = str(news_feed_url or NewsService.DEFAULT_FEED_URL).strip() or NewsService.DEFAULT_FEED_URL

        self.settings.setValue("integrations/telegram_enabled", self.telegram_enabled)
        self.settings.setValue("integrations/telegram_bot_token", self.telegram_bot_token)
        self.settings.setValue("integrations/telegram_chat_id", self.telegram_chat_id)
        self.settings.setValue("integrations/trade_close_notifications_enabled", self.trade_close_notifications_enabled)
        self.settings.setValue("integrations/trade_close_notify_telegram", self.trade_close_notify_telegram)
        self.settings.setValue("integrations/trade_close_notify_email", self.trade_close_notify_email)
        self.settings.setValue("integrations/trade_close_notify_sms", self.trade_close_notify_sms)
        self.settings.setValue("integrations/trade_close_email_host", self.trade_close_email_host)
        self.settings.setValue("integrations/trade_close_email_port", self.trade_close_email_port)
        self.settings.setValue("integrations/trade_close_email_username", self.trade_close_email_username)
        self.settings.setValue("integrations/trade_close_email_password", self.trade_close_email_password)
        self.settings.setValue("integrations/trade_close_email_from", self.trade_close_email_from)
        self.settings.setValue("integrations/trade_close_email_to", self.trade_close_email_to)
        self.settings.setValue("integrations/trade_close_email_starttls", self.trade_close_email_starttls)
        self.settings.setValue("integrations/trade_close_sms_account_sid", self.trade_close_sms_account_sid)
        self.settings.setValue("integrations/trade_close_sms_auth_token", self.trade_close_sms_auth_token)
        self.settings.setValue("integrations/trade_close_sms_from_number", self.trade_close_sms_from_number)
        self.settings.setValue("integrations/trade_close_sms_to_number", self.trade_close_sms_to_number)
        self.settings.setValue("integrations/openai_api_key", self.openai_api_key)
        self.settings.setValue("integrations/openai_model", self.openai_model)
        self.settings.setValue("integrations/voice_name", getattr(self, "voice_name", ""))
        self.settings.setValue("integrations/voice_windows_name", getattr(self, "voice_windows_name", ""))
        self.settings.setValue("integrations/voice_openai_name", getattr(self, "voice_openai_name", "alloy"))
        self.settings.setValue("integrations/voice_provider", getattr(self, "voice_provider", "windows"))
        self.settings.setValue("integrations/voice_output_provider", getattr(self, "voice_output_provider", "windows"))
        self.settings.setValue("integrations/news_enabled", self.news_enabled)
        self.settings.setValue("integrations/news_autotrade_enabled", self.news_autotrade_enabled)
        self.settings.setValue("integrations/news_draw_on_chart", self.news_draw_on_chart)
        self.settings.setValue("integrations/news_feed_url", self.news_feed_url)
        self.news_service.enabled = self.news_enabled
        self.news_service.feed_url_template = self.news_feed_url
        self._configure_trade_close_notification_services(close_existing=True)

        asyncio.get_event_loop().create_task(self._restart_telegram_service())

    def supported_market_venues(self):
        broker = getattr(self, "broker", None)
        if broker is not None and hasattr(broker, "supported_market_venues"):
            try:
                venues = [
                    str(item).strip().lower()
                    for item in (broker.supported_market_venues() or [])
                    if str(item).strip()
                ]
            except Exception:
                venues = []
            if venues:
                return list(dict.fromkeys(venues))

        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        broker_type = getattr(broker_cfg, "type", None)
        exchange = getattr(broker_cfg, "exchange", None)
        return supported_market_venues_for_profile(broker_type, exchange)

    def set_market_trade_preference(self, preference):
        normalized = normalize_market_venue(preference)
        supported = self.supported_market_venues()
        if normalized not in supported:
            normalized = "auto" if "auto" in supported else (supported[0] if supported else "auto")
        self.market_trade_preference = normalized
        self.settings.setValue("trading/market_type", normalized)

        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        if broker_cfg is not None:
            options = dict(getattr(broker_cfg, "options", None) or {})
            options["market_type"] = normalized
            try:
                broker_cfg.options = options
            except Exception:
                pass

        broker = getattr(self, "broker", None)
        if broker is not None and hasattr(broker, "extra_options"):
            broker.extra_options["market_type"] = normalized
            if hasattr(broker, "market_preference"):
                broker.market_preference = normalized
            if hasattr(broker, "apply_market_preference"):
                try:
                    updated_symbols = broker.apply_market_preference(normalized)
                except Exception:
                    updated_symbols = None
                if updated_symbols:
                    exchange_name = getattr(broker, "exchange_name", getattr(broker_cfg, "exchange", "broker")) or "broker"
                    broker_type = getattr(broker_cfg, "type", None)
                    self.symbols = self._normalize_symbol_sequence(updated_symbols)
                    self._refresh_symbol_universe_tiers(
                        catalog_symbols=updated_symbols,
                        broker_type=broker_type,
                        exchange=exchange_name,
                    )
                    self._emit_symbols_signal_deferred(str(exchange_name), list(self.symbols))
                    if getattr(self, "connected", False):
                        self.schedule_strategy_auto_assignment(symbols=None, timeframe=self.time_frame, force=False)

    def set_forex_candle_price_component(self, component):
        normalized = _normalize_forex_candle_price_component(component)
        self.forex_candle_price_component = normalized
        self.settings.setValue("market_data/forex_candle_price_component", normalized)

        broker_cfg = getattr(getattr(self, "config", None), "broker", None)
        if broker_cfg is not None:
            options = dict(getattr(broker_cfg, "options", None) or {})
            options["candle_price_component"] = normalized
            try:
                broker_cfg.options = options
            except Exception:
                pass

        broker = getattr(self, "broker", None)
        if str(getattr(broker, "exchange_name", "") or "").strip().lower() == "oanda":
            if hasattr(broker, "set_candle_price_component"):
                try:
                    broker.set_candle_price_component(normalized)
                except Exception:
                    pass
            else:
                setattr(broker, "candle_price_component", normalized)

        return normalized

    async def request_news(self, symbol, force=False, max_age_seconds=300):
        normalized = str(symbol or "").upper().strip()
        if not normalized or not self.news_enabled:
            return []

        cached = self._news_cache.get(normalized)
        if not force and isinstance(cached, dict):
            cached_at = float(cached.get("fetched_at", 0.0) or 0.0)
            if (time.monotonic() - cached_at) <= max_age_seconds:
                events = list(cached.get("events", []) or [])
                self.news_signal.emit(normalized, events)
                return events

        existing_task = self._news_inflight.get(normalized)
        if existing_task is not None and not existing_task.done():
            try:
                return await existing_task
            except Exception:

                return []

        async def runner():
            broker_type = getattr(getattr(self, "config", None), "broker", None)
            broker_type = getattr(broker_type, "type", None)
            events = await self.news_service.fetch_symbol_news(normalized, broker_type=broker_type, limit=8)
            self._news_cache[normalized] = {
                "fetched_at": time.monotonic(),
                "events": list(events or []),
            }
            self.news_signal.emit(normalized, list(events or []))
            return list(events or [])

        task = asyncio.create_task( runner())
        self._news_inflight[normalized] = task
        try:
            return await task
        finally:
            current = self._news_inflight.get(normalized)
            if current is task:
                self._news_inflight.pop(normalized, None)

    def get_news_bias(self, symbol):
        normalized = str(symbol or "").upper().strip()
        cached = self._news_cache.get(normalized, {})
        events = list(cached.get("events", []) or [])
        return self.news_service.summarize_news_bias(events)

    async def apply_news_bias_to_signal(self, symbol, signal):
        if not isinstance(signal, dict):
            return None
        if not self.news_enabled or not self.news_autotrade_enabled:
            return signal

        events = await self.request_news(symbol)
        bias = self.news_service.summarize_news_bias(events)
        direction = str(bias.get("direction", "neutral") or "neutral").lower()
        score = float(bias.get("score", 0.0) or 0.0)

        updated = dict(signal)
        base_reason = str(updated.get("reason", "") or "").strip()
        news_reason = str(bias.get("reason", "") or "").strip()
        if news_reason:
            updated["reason"] = f"{base_reason} | News: {news_reason}" if base_reason else f"News: {news_reason}"
        updated["news_bias"] = direction
        updated["news_score"] = score

        side = str(updated.get("side", "") or "").lower()
        if direction in {"buy", "sell"} and direction != side and abs(score) >= 0.35:
            self.logger.info("Skipping %s %s due to conflicting news bias (%s %.3f)", symbol, side, direction, score)
            return None

        if direction == side and abs(score) >= 0.2:
            updated["confidence"] = min(float(updated.get("confidence", 0.0) or 0.0) + 0.08, 0.99)

        return updated

    async def _restart_telegram_service(self):
        if self.telegram_service is not None:
            try:
                await self.telegram_service.stop()
            except Exception as exc:
                self.logger.debug("Telegram restart stop failed: %s", exc)

        self.telegram_service = TelegramService(
            controller=self,
            logger=self.logger,
            bot_token=self.telegram_bot_token,
            chat_id=self.telegram_chat_id,
            enabled=self.telegram_enabled,
        )
        if self.telegram_enabled and self.telegram_bot_token:
            await self.telegram_service.start()

    async def _stop_telegram_service(self):
        if self.telegram_service is None:
            return
        try:
            await self.telegram_service.stop()
        finally:
            self.telegram_service = None

    def _configure_trade_close_notification_services(self, close_existing=False):
        previous_sms_service = getattr(self, "sms_trade_notification_service", None) if close_existing else None
        self.email_trade_notification_service = EmailTradeNotificationService(
            host=getattr(self, "trade_close_email_host", ""),
            port=getattr(self, "trade_close_email_port", 587),
            username=getattr(self, "trade_close_email_username", ""),
            password=getattr(self, "trade_close_email_password", ""),
            from_addr=getattr(self, "trade_close_email_from", ""),
            to_addrs=getattr(self, "trade_close_email_to", ""),
            use_starttls=getattr(self, "trade_close_email_starttls", True),
        )
        self.sms_trade_notification_service = TwilioSmsTradeNotificationService(
            account_sid=getattr(self, "trade_close_sms_account_sid", ""),
            auth_token=getattr(self, "trade_close_sms_auth_token", ""),
            from_number=getattr(self, "trade_close_sms_from_number", ""),
            to_number=getattr(self, "trade_close_sms_to_number", ""),
        )
        close_previous = getattr(previous_sms_service, "close", None)
        if close_existing and previous_sms_service is not None:
            try:
                asyncio.get_event_loop().create_task(close_previous())
            except Exception:
                self.logger.debug("Trade close SMS service cleanup failed", exc_info=True)

    def _remember_trade_close_entry(self, trade):
        if not isinstance(trade, dict) or is_trade_close_event(trade):
            return
        status = str(trade.get("status") or "").strip().lower().replace("-", "_")
        if status not in {"filled", "partially_filled", "partial_fill"}:
            return
        key = trade_close_cache_key(trade)
        if not key:
            return
        entry_price = self._safe_balance_metric(
            trade.get("entry_price")
            or trade.get("avg_entry_price")
            or trade.get("price")
        )
        if entry_price is None or entry_price <= 0:
            return
        size = self._safe_balance_metric(
            trade.get("filled_size")
            or trade.get("size")
            or trade.get("amount")
        )
        previous = getattr(self, "_trade_close_entry_cache", {}).get(key)
        if previous and size is not None and size > 0 and previous.get("size"):
            previous_size = abs(float(previous.get("size") or 0.0))
            total_size = previous_size + abs(float(size))
            if total_size > 0:
                entry_price = (
                                      (float(previous.get("entry_price") or 0.0) * previous_size)
                                      + (float(entry_price) * abs(float(size)))
                              ) / total_size
                size = total_size
        elif size is None:
            size = previous.get("size") if previous else 0.0
        self._trade_close_entry_cache[key] = {
            "entry_price": float(entry_price),
            "size": float(abs(float(size or 0.0))),
        }

    def _enrich_trade_close_notification_trade(self, trade):
        payload = dict(trade or {})
        if not payload.get("strategy_name"):
            payload["strategy_name"] = str(getattr(self, "strategy_name", "") or "").strip()
        if (
                payload.get("exit_price") in (None, "")
                and payload.get("close_price") in (None, "")
                and payload.get("price") not in (None, "")
        ):
            payload["exit_price"] = payload.get("price")
        if payload.get("entry_price") in (None, ""):
            cached = getattr(self, "_trade_close_entry_cache", {}).get(trade_close_cache_key(payload))
            if isinstance(cached, dict) and cached.get("entry_price") not in (None, ""):
                payload["entry_price"] = cached.get("entry_price")
        return payload

    def _dispatch_trade_close_notifications(self, trade):
        if not is_trade_close_event(trade):
            self._remember_trade_close_entry(trade)
            return
        key = trade_close_cache_key(trade)
        payload = self._enrich_trade_close_notification_trade(trade)
        if key:
            getattr(self, "_trade_close_entry_cache", {}).pop(key, None)
        if not getattr(self, "trade_close_notifications_enabled", False):
            return
        telegram_service = getattr(self, "telegram_service", None)
        if getattr(self, "trade_close_notify_telegram", False) and telegram_service is not None:
            self._create_task(telegram_service.notify_trade_close(payload), "telegram_trade_close_notify")
        email_service = getattr(self, "email_trade_notification_service", None)
        if getattr(self, "trade_close_notify_email", False) and email_service is not None:
            self._create_task(email_service.send_trade_close(payload), "email_trade_close_notify")
        sms_service = getattr(self, "sms_trade_notification_service", None)
        if getattr(self, "trade_close_notify_sms", False) and sms_service is not None:
            self._create_task(sms_service.send_trade_close(payload), "sms_trade_close_notify")

    def telegram_status_snapshot(self):
        service = getattr(self, "telegram_service", None)
        running = bool(getattr(service, "_running", False)) if service is not None else False
        configured = bool(str(getattr(self, "telegram_bot_token", "") or "").strip())
        chat_id = str(getattr(self, "telegram_chat_id", "") or "").strip()
        masked_chat = "Not set"
        if chat_id:
            masked_chat = chat_id if len(chat_id) <= 6 else f"{chat_id[:3]}...{chat_id[-3:]}"
        return {
            "enabled": bool(getattr(self, "telegram_enabled", False)),
            "configured": configured,
            "running": running,
            "chat_id": masked_chat,
            "can_send": bool(service.can_send()) if service is not None else bool(configured and chat_id),
        }

    def telegram_management_text(self):
        snapshot = self.telegram_status_snapshot()
        return (
            "Telegram Integration\n"
            f"Enabled: {'YES' if snapshot['enabled'] else 'NO'}\n"
            f"Configured: {'YES' if snapshot['configured'] else 'NO'}\n"
            f"Running: {'YES' if snapshot['running'] else 'NO'}\n"
            f"Chat ID: {snapshot['chat_id']}\n"
            f"Can Send Messages: {'YES' if snapshot['can_send'] else 'NO'}"
        )

    async def _set_telegram_enabled_state(self, enabled):
        self.telegram_enabled = bool(enabled)
        self.settings.setValue("integrations/telegram_enabled", self.telegram_enabled)
        if self.telegram_enabled:
            await self._restart_telegram_service()
        else:
            await self._stop_telegram_service()

    async def send_test_telegram_message(self, text=None):
        service = getattr(self, "telegram_service", None)
        if service is None or not service.can_send():
            return False
        message = text or (
            "<b>Sopotek Telegram Test</b>\n"
            "Sopotek Pilot sent this test message successfully."
        )
        return bool(await service.send_message(message))

    def trade_quantity_context(self, symbol):
        normalized_symbol = str(symbol or "").strip().upper()
        broker = getattr(self, "broker", None)
        exchange_name = str(getattr(broker, "exchange_name", "") or "").strip().lower()
        compact = self._normalize_market_data_symbol(normalized_symbol)
        parts = compact.split("/", 1) if "/" in compact else []
        supports_lots = False
        if exchange_name == "oanda" and len(parts) == 2:
            base, quote = parts
            supports_lots = (
                    len(base) == 3
                    and len(quote) == 3
                    and base.isalpha()
                    and quote.isalpha()
                    and base in self.FOREX_SYMBOL_QUOTES
                    and quote in self.FOREX_SYMBOL_QUOTES
            )
        return {
            "symbol": normalized_symbol,
            "supports_lots": supports_lots,
            "default_mode": "lots" if supports_lots else "units",
            "lot_units": self.FOREX_STANDARD_LOT_UNITS,
        }

    def normalize_trade_quantity(self, symbol, amount, quantity_mode=None):
        try:
            numeric_amount = abs(float(amount))
        except Exception as exc:
            raise ValueError("Trade amount must be numeric.") from exc
        if numeric_amount <= 0:
            raise ValueError("Trade amount must be positive.")

        context = self.trade_quantity_context(symbol)
        requested_mode = str(quantity_mode or context.get("default_mode") or "units").strip().lower()
        if requested_mode.endswith("s"):
            requested_mode = requested_mode[:-1]
        if requested_mode not in {"unit", "lot"}:
            raise ValueError("Trade quantity mode must be 'units' or 'lots'.")
        if requested_mode == "lot" and not context.get("supports_lots"):
            raise ValueError(f"Lot sizing is only available for supported forex symbols. Use units for {symbol}.")

        normalized_units = (
            numeric_amount * float(context.get("lot_units", self.FOREX_STANDARD_LOT_UNITS))
            if requested_mode == "lot"
            else numeric_amount
        )
        result = dict(context)
        result.update(
            {
                "requested_amount": numeric_amount,
                "requested_mode": "lots" if requested_mode == "lot" else "units",
                "amount_units": float(normalized_units),
            }
        )
        return result

    def _trade_symbol_parts(self, symbol):
        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if "/" not in normalized_symbol:
            return None, None
        base_currency, quote_currency = normalized_symbol.split("/", 1)
        return base_currency or None, quote_currency.split(":", 1)[0] or None

    def _balance_account_currency(self, balances):
        if not isinstance(balances, dict):
            return None

        for key in ("currency", "account_currency"):
            value = str(balances.get(key) or "").strip().upper()
            if value.isalpha() and len(value) >= 3:
                return value

        for bucket_name in ("total", "free", "used"):
            bucket = balances.get(bucket_name)
            if not isinstance(bucket, dict) or not bucket:
                continue
            currencies = [str(item or "").strip().upper() for item in bucket.keys()]
            currencies = [item for item in currencies if item.isalpha() and len(item) >= 3]
            if len(currencies) == 1:
                return currencies[0]
        return None

    async def _conversion_reference_price(self, symbol):
        fetch_ticker = getattr(self, "_safe_fetch_ticker", None)
        if not callable(fetch_ticker):
            return None
        try:
            ticker = await fetch_ticker(symbol)
        except Exception:
            return None
        if not isinstance(ticker, dict):
            return None
        prepared = self._prepare_ticker_snapshot(symbol, ticker) if hasattr(self, "_prepare_ticker_snapshot") else ticker
        for key in ("ask", "price", "last", "close", "mid", "bid"):
            numeric = self._safe_balance_metric(prepared.get(key))
            if numeric is not None and numeric > 0:
                return float(numeric)
        return None

    async def _resolve_trade_risk_context(
            self,
            symbol,
            reference_price,
            balances,
            broker=None,
            allow_cross_conversion=True,
    ):
        base_currency, quote_currency = self._trade_symbol_parts(symbol)
        account_currency = self._balance_account_currency(balances)
        context = {
            "symbol": str(symbol or "").strip().upper(),
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "account_currency": account_currency,
            "is_forex": False,
            "pip_size": None,
            "quote_to_account_rate": 1.0,
        }
        if not base_currency or not quote_currency:
            return context

        is_forex = (
                len(base_currency) == 3
                and len(quote_currency) == 3
                and base_currency.isalpha()
                and quote_currency.isalpha()
                and base_currency in self.FOREX_SYMBOL_QUOTES
                and quote_currency in self.FOREX_SYMBOL_QUOTES
        )
        context["is_forex"] = is_forex
        if not is_forex:
            return context

        pip_size = None
        meta_loader = getattr(broker or getattr(self, "broker", None), "_get_instrument_meta", None)
        if callable(meta_loader):
            try:
                meta = await meta_loader(symbol)
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                try:
                    pip_size = 10 ** int(meta.get("pipLocation"))
                except Exception:
                    pip_size = None
        if pip_size is None or pip_size <= 0:
            pip_size = 0.01 if quote_currency == "JPY" else 0.0001
        context["pip_size"] = float(pip_size)

        try:
            reference_value = float(reference_price)
        except Exception:
            reference_value = None

        quote_to_account_rate = 1.0
        if account_currency and account_currency == quote_currency:
            quote_to_account_rate = 1.0
        elif account_currency and account_currency == base_currency and reference_value and reference_value > 0:
            quote_to_account_rate = 1.0 / float(reference_value)
        elif (
                account_currency
                and allow_cross_conversion
                and account_currency not in {base_currency, quote_currency}
        ):
            direct_price = await self._conversion_reference_price(f"{quote_currency}/{account_currency}")
            if direct_price is not None and direct_price > 0:
                quote_to_account_rate = float(direct_price)
            else:
                reverse_price = await self._conversion_reference_price(f"{account_currency}/{quote_currency}")
                if reverse_price is not None and reverse_price > 0:
                    quote_to_account_rate = 1.0 / float(reverse_price)
        if quote_to_account_rate > 0:
            context["quote_to_account_rate"] = float(quote_to_account_rate)
        return context

    def _display_trade_amount(self, amount_units, quantity):
        try:
            normalized_units = abs(float(amount_units))
        except Exception:
            normalized_units = 0.0
        requested_mode = str((quantity or {}).get("requested_mode") or "units").strip().lower() or "units"
        if requested_mode == "lots":
            try:
                lot_units = float(
                    (quantity or {}).get("lot_units", self.FOREX_STANDARD_LOT_UNITS) or self.FOREX_STANDARD_LOT_UNITS
                )
            except Exception:
                lot_units = self.FOREX_STANDARD_LOT_UNITS
            if lot_units > 0:
                return round(normalized_units / lot_units, 6)
        return round(normalized_units, 8)

    def _balance_bucket_currency_value(self, balances, bucket_name, currency):
        if not isinstance(balances, dict):
            return None
        bucket = balances.get(bucket_name)
        if not isinstance(bucket, dict):
            return None
        normalized_currency = str(currency or "").strip().upper()
        if normalized_currency in bucket:
            return self._safe_balance_metric(bucket.get(normalized_currency))
        if len(bucket) == 1:
            try:
                return self._safe_balance_metric(next(iter(bucket.values())))
            except Exception:
                return None
        return None

    async def _resolve_trade_reference_price(self, symbol, side, order_type="market", price=None, stop_price=None):
        candidates = []
        for candidate in (price, stop_price):
            try:
                numeric_candidate = float(candidate)
            except Exception:
                numeric_candidate = None
            if numeric_candidate is not None and numeric_candidate > 0:
                candidates.append(numeric_candidate)
        if candidates:
            return max(candidates), None

        ticker = None
        fetch_ticker = getattr(self, "_safe_fetch_ticker", None)
        if callable(fetch_ticker):
            try:
                ticker = await fetch_ticker(symbol)
            except Exception:
                ticker = None

        if isinstance(ticker, dict):
            ticker = self._prepare_ticker_snapshot(symbol, ticker)
            exchange_name = str(self._active_exchange_code() or "").strip().lower()
            market_venue = str(self._market_venue_for_symbol(symbol) or "").strip().lower()
            if exchange_name == "oanda" or market_venue == "otc":
                price_keys = (
                    ("price", "last", "close", "mid", "ask", "bid")
                    if str(side or "").lower() == "buy"
                    else ("price", "last", "close", "mid", "bid", "ask")
                )
            else:
                price_keys = (
                    ("ask", "price", "last", "close", "mid", "bid")
                    if str(side or "").lower() == "buy"
                    else ("bid", "price", "last", "close", "mid", "ask")
                )
            for key in price_keys:
                numeric = self._safe_balance_metric(ticker.get(key))
                if numeric is not None and numeric > 0:
                    return float(numeric), ticker
        return None, ticker

    async def _instrument_margin_rate(self, symbol, broker=None):
        broker = broker or getattr(self, "broker", None)
        if broker is None:
            return None
        meta_loader = getattr(broker, "_get_instrument_meta", None)
        if not callable(meta_loader):
            return None
        try:
            meta = await meta_loader(symbol)
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            return None
        for key in ("marginRate", "margin_rate"):
            numeric = self._safe_balance_metric(meta.get(key))
            if numeric is not None and numeric > 0:
                return float(numeric)
        return None

    def _market_venue_for_symbol(self, symbol, market=None):
        market = market if isinstance(market, dict) else self._broker_market_for_symbol(symbol)
        if isinstance(market, dict):
            if bool(market.get("option")):
                return "option"
            if bool(market.get("otc")):
                return "otc"
            if self._symbol_market_is_derivative(symbol, market=market):
                return "derivative"
        return "spot"

    def _prepare_ticker_snapshot(self, symbol, ticker):
        if not isinstance(ticker, dict):
            return ticker
        snapshot = dict(ticker)
        normalized_symbol = self._normalize_market_data_symbol(snapshot.get("symbol") or symbol) or str(symbol or "").strip().upper()
        raw_payload = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
        broker_timestamp = (
                snapshot.get("_received_at")
                or snapshot.get("timestamp")
                or snapshot.get("time")
                or snapshot.get("datetime")
                or raw_payload.get("time")
                or raw_payload.get("timestamp")
                or raw_payload.get("datetime")
        )
        received_at = broker_timestamp or datetime.now(timezone.utc).isoformat()
        snapshot["symbol"] = normalized_symbol
        snapshot.setdefault("timestamp", received_at)
        snapshot["_received_at"] = received_at
        return snapshot

    def _cache_ticker_snapshot(self, symbol, ticker):
        snapshot = self._prepare_ticker_snapshot(symbol, ticker)
        if not isinstance(snapshot, dict):
            return snapshot

        normalized_symbol = self._normalize_market_data_symbol(snapshot.get("symbol") or symbol) or str(symbol or "").strip().upper()
        ticker_buffer = getattr(self, "ticker_buffer", None)
        if ticker_buffer is not None and hasattr(ticker_buffer, "update"):
            try:
                ticker_buffer.update(normalized_symbol, snapshot)
            except Exception:
                pass

        ticker_stream = getattr(self, "ticker_stream", None)
        if ticker_stream is not None and hasattr(ticker_stream, "update"):
            try:
                ticker_stream.update(normalized_symbol, snapshot)
            except Exception:
                pass
        return snapshot

    def _latest_cached_candle_timestamp(self, symbol, timeframe=None):
        normalized_symbol = self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        symbol_candidates = [normalized_symbol]
        resolved_symbol = self._resolve_preferred_market_symbol(normalized_symbol)
        if resolved_symbol and resolved_symbol not in symbol_candidates:
            symbol_candidates.append(resolved_symbol)

        caches = getattr(self, "candle_buffers", {})
        for candidate in symbol_candidates:
            symbol_cache = caches.get(candidate, {}) if isinstance(caches, dict) else {}
            frame = symbol_cache.get(timeframe_value) if isinstance(symbol_cache, dict) else None
            if frame is None or getattr(frame, "empty", True):
                continue
            try:
                timestamp_value = frame["timestamp"].iloc[-1]
            except Exception:
                timestamp_value = None
            if timestamp_value is not None:
                return timestamp_value

        candle_buffer = getattr(self, "candle_buffer", None)
        if candle_buffer is not None and hasattr(candle_buffer, "latest"):
            for candidate in symbol_candidates:
                try:
                    latest = candle_buffer.latest(candidate)
                except Exception:
                    latest = None
                if isinstance(latest, dict):
                    timestamp_value = latest.get("timestamp")
                    if timestamp_value is not None:
                        return timestamp_value
        return None

    async def _refresh_trade_guard_candle_data(self, symbol, timeframe):
        request_candle_data = getattr(self, "request_candle_data", None)
        if not callable(request_candle_data):
            return None

        history_limit_resolver = getattr(self, "_resolve_history_limit", None)
        warmup_limit = 180
        if callable(history_limit_resolver):
            try:
                warmup_limit = min(180, max(100, int(history_limit_resolver(180))))
            except Exception:
                warmup_limit = 180

        try:
            await request_candle_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=warmup_limit,
                history_scope="runtime",
            )
        except Exception as exc:
            self.logger.debug("Trade guard candle refresh failed for %s %s: %s", symbol, timeframe, exc)

        return self._latest_cached_candle_timestamp(symbol, timeframe=timeframe)

    async def _refresh_trade_guard_orderbook(self, symbol):
        fetch_orderbook = getattr(self, "_safe_fetch_orderbook", None)
        if not callable(fetch_orderbook):
            return None

        try:
            orderbook = await fetch_orderbook(symbol, limit=20)
        except Exception as exc:
            self.logger.debug("Trade guard orderbook refresh failed for %s: %s", symbol, exc)
            return None

        if not isinstance(orderbook, dict):
            return None

        bids = list(orderbook.get("bids") or [])
        asks = list(orderbook.get("asks") or [])
        if not bids and not asks:
            return None

        orderbook_buffer = getattr(self, "orderbook_buffer", None)
        if orderbook_buffer is not None and hasattr(orderbook_buffer, "update"):
            try:
                orderbook_buffer.update(symbol, bids, asks)
            except Exception:
                self.logger.debug("Trade guard orderbook cache update failed for %s", symbol, exc_info=True)

        return orderbook_buffer.get(symbol) if orderbook_buffer is not None and hasattr(orderbook_buffer, "get") else None

    async def _assess_trade_market_data_guard(self, symbol, *, timeframe=None, ticker=None):
        normalized_symbol = self._resolve_preferred_market_symbol(symbol) or self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        quote_threshold = max(1.0, float(getattr(self, "QUOTE_STALE_SECONDS", 20.0) or 20.0))
        candle_threshold_seconds = max(
            float(getattr(self, "CANDLE_STALE_MIN_SECONDS", 60.0) or 60.0),
            float(timeframe_seconds(timeframe_value, default=60))
            * float(getattr(self, "CANDLE_STALE_MULTIPLIER", 3.0) or 3.0),
            )
        orderbook_threshold = max(1.0, float(getattr(self, "ORDERBOOK_STALE_SECONDS", 20.0) or 20.0))

        ticker_payload = ticker or self._cached_ticker_snapshot(normalized_symbol)
        if not isinstance(ticker_payload, dict):
            fetch_ticker = getattr(self, "_safe_fetch_ticker", None)
            if callable(fetch_ticker):
                try:
                    ticker_payload = await fetch_ticker(normalized_symbol)
                except Exception:
                    ticker_payload = None
        ticker_snapshot = self._prepare_ticker_snapshot(normalized_symbol, ticker_payload)
        quote_age_seconds = age_seconds(
            (ticker_snapshot or {}).get("_received_at") or (ticker_snapshot or {}).get("timestamp")
        )
        quote_fresh = quote_age_seconds is not None and quote_age_seconds <= quote_threshold
        if not quote_fresh:
            fetch_ticker = getattr(self, "_safe_fetch_ticker", None)
            if callable(fetch_ticker):
                try:
                    refreshed_payload = await fetch_ticker(normalized_symbol)
                except Exception:
                    refreshed_payload = None
                refreshed_snapshot = self._prepare_ticker_snapshot(normalized_symbol, refreshed_payload)
                refreshed_age_seconds = age_seconds(
                    (refreshed_snapshot or {}).get("_received_at") or (refreshed_snapshot or {}).get("timestamp")
                )
                refreshed_fresh = refreshed_age_seconds is not None and refreshed_age_seconds <= quote_threshold
                if refreshed_fresh or (
                        refreshed_age_seconds is not None
                        and (quote_age_seconds is None or refreshed_age_seconds < quote_age_seconds)
                ):
                    ticker_snapshot = refreshed_snapshot
                    quote_age_seconds = refreshed_age_seconds
                    quote_fresh = refreshed_fresh

        candle_timestamp = self._latest_cached_candle_timestamp(normalized_symbol, timeframe=timeframe_value)
        candle_age_seconds = age_seconds(candle_timestamp)
        candle_fresh = candle_age_seconds is not None and candle_age_seconds <= candle_threshold_seconds
        if not candle_fresh:
            refreshed_candle_timestamp = await self._refresh_trade_guard_candle_data(normalized_symbol, timeframe_value)
            refreshed_candle_age_seconds = age_seconds(refreshed_candle_timestamp)
            refreshed_candle_fresh = (
                    refreshed_candle_age_seconds is not None
                    and refreshed_candle_age_seconds <= candle_threshold_seconds
            )
            if refreshed_candle_fresh or (
                    refreshed_candle_age_seconds is not None
                    and (candle_age_seconds is None or refreshed_candle_age_seconds < candle_age_seconds)
            ):
                candle_timestamp = refreshed_candle_timestamp
                candle_age_seconds = refreshed_candle_age_seconds
                candle_fresh = refreshed_candle_fresh

        orderbook_supported = bool(self.get_broker_capabilities().get("orderbook"))
        book_snapshot = getattr(self, "orderbook_buffer", None)
        if book_snapshot is not None and hasattr(book_snapshot, "get"):
            try:
                book_snapshot = book_snapshot.get(normalized_symbol)
            except Exception:
                book_snapshot = None
        else:
            book_snapshot = None
        orderbook_age_seconds = age_seconds((book_snapshot or {}).get("updated_at"))
        orderbook_fresh = orderbook_age_seconds is not None and orderbook_age_seconds <= orderbook_threshold
        if orderbook_supported and not orderbook_fresh:
            refreshed_book_snapshot = await self._refresh_trade_guard_orderbook(normalized_symbol)
            refreshed_orderbook_age_seconds = age_seconds((refreshed_book_snapshot or {}).get("updated_at"))
            refreshed_orderbook_fresh = (
                    refreshed_orderbook_age_seconds is not None
                    and refreshed_orderbook_age_seconds <= orderbook_threshold
            )
            if refreshed_orderbook_fresh or (
                    refreshed_orderbook_age_seconds is not None
                    and (orderbook_age_seconds is None or refreshed_orderbook_age_seconds < orderbook_age_seconds)
            ):
                book_snapshot = refreshed_book_snapshot
                orderbook_age_seconds = refreshed_orderbook_age_seconds
                orderbook_fresh = refreshed_orderbook_fresh

        blocked_reasons = []
        if not quote_fresh:
            blocked_reasons.append(
                f"Live trade blocked: quote data for {normalized_symbol} is stale ({format_age_label(quote_age_seconds)} old)."
            )
        if not candle_fresh:
            blocked_reasons.append(
                f"Live trade blocked: candle data for {normalized_symbol} {timeframe_value} is stale ({format_age_label(candle_age_seconds)} old)."
            )
        if orderbook_supported and not orderbook_fresh:
            blocked_reasons.append(
                f"Live trade blocked: orderbook data for {normalized_symbol} is stale ({format_age_label(orderbook_age_seconds)} old)."
            )

        return {
            "blocked": bool(blocked_reasons),
            "reasons": blocked_reasons,
            "quote": {
                "supported": True,
                "fresh": quote_fresh,
                "age_seconds": quote_age_seconds,
                "age_label": format_age_label(quote_age_seconds),
                "threshold_seconds": quote_threshold,
                "threshold_label": format_age_label(quote_threshold),
            },
            "candles": {
                "supported": True,
                "fresh": candle_fresh,
                "age_seconds": candle_age_seconds,
                "age_label": format_age_label(candle_age_seconds),
                "threshold_seconds": candle_threshold_seconds,
                "threshold_label": format_age_label(candle_threshold_seconds),
                "timeframe": timeframe_value,
            },
            "orderbook": {
                "supported": orderbook_supported,
                "fresh": orderbook_fresh if orderbook_supported else None,
                "age_seconds": orderbook_age_seconds,
                "age_label": format_age_label(orderbook_age_seconds),
                "threshold_seconds": orderbook_threshold if orderbook_supported else None,
                "threshold_label": format_age_label(orderbook_threshold) if orderbook_supported else "",
            },
        }

    def _evaluate_trade_eligibility(self, symbol):
        broker = getattr(self, "broker", None)
        market = self._broker_market_for_symbol(symbol)
        resolved_venue = self._market_venue_for_symbol(symbol, market=market)
        active_preference = self._active_market_trade_preference_value()
        supported_venues = self.supported_market_venues()
        capabilities = self.get_broker_capabilities()
        issues = []
        warnings = []

        if broker is None:
            issues.append("Connect a broker before submitting a trade.")
        if not capabilities.get("trading"):
            issues.append("The connected broker does not expose order submission.")
        if active_preference != "auto" and active_preference not in supported_venues:
            issues.append(f"The active market venue '{active_preference}' is not supported by this broker profile.")
        if active_preference != "auto" and resolved_venue != active_preference:
            issues.append(
                f"{symbol} resolves to the {resolved_venue} venue while the active session is set to {active_preference}."
            )
        if self.is_live_mode() and not self._broker_is_connected(broker):
            issues.append("The live broker session is not connected.")
        if self.is_live_mode() and self.current_account_label() == "Not set":
            warnings.append("The broker did not expose a live account identity. Verify you are on the intended live account.")

        return {
            "ok": not issues,
            "issues": issues,
            "warnings": warnings,
            "resolved_venue": resolved_venue,
            "supported_market_venues": supported_venues,
            "active_market_preference": active_preference,
        }

    async def _record_trade_audit(
            self,
            action,
            *,
            status=None,
            symbol=None,
            requested_symbol=None,
            side=None,
            order_type=None,
            source=None,
            order_id=None,
            message=None,
            payload=None,
            venue=None,
            **extra_payload,
    ):
        repository = getattr(self, "trade_audit_repository", None)
        if repository is None:
            return None
        exchange_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").strip().lower() or None
        account_label = str(self.current_account_label() or "").strip() or None
        resolved_symbol = str(symbol or "").strip().upper() or None
        requested_symbol_value = str(requested_symbol or resolved_symbol or "").strip().upper() or None
        resolved_venue = str(venue or self._market_venue_for_symbol(resolved_symbol or requested_symbol_value)).strip().lower() or None
        payload_data = payload
        if extra_payload:
            payload_data = dict(payload) if isinstance(payload, dict) else {"payload": payload} if payload is not None else {}
            payload_data.update(extra_payload)
        try:
            return await asyncio.to_thread(
                repository.record_event,
                action=action,
                status=status,
                exchange=exchange_name,
                account_label=account_label,
                symbol=resolved_symbol,
                requested_symbol=requested_symbol_value,
                side=side,
                order_type=order_type,
                venue=resolved_venue,
                source=source,
                order_id=order_id,
                message=message,
                payload=payload_data,
            )
        except Exception:
            self.logger.debug("Trade audit persistence failed for %s", action, exc_info=True)
            return None

    def queue_trade_audit(self, action, **payload):
        try:
            loop = asyncio.get_event_loop()
        except Exception:
            return None
        return loop.create_task(self._record_trade_audit(action, **payload))

    def _extract_json_object(self, text):
        payload_text = str(text or "").strip()
        if not payload_text:
            return None
        try:
            parsed = json.loads(payload_text)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        match = re.search(r"\{.*}", payload_text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def _recommend_trade_size_with_openai(
            self,
            *,
            symbol,
            side,
            quantity,
            requested_units,
            deterministic_units,
            reference_price,
            balances,
            closeout_guard,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
    ):
        api_key = str(getattr(self, "openai_api_key", "") or "").strip()
        if not api_key:
            return None
        if reference_price is None or reference_price <= 0:
            return None

        equity = self._extract_balance_equity_value(balances if isinstance(balances, dict) else {})
        free_margin = self._balance_metric_value(
            balances,
            "free_margin",
            "available_margin",
            "margin_available",
            "cash",
            "free",
        )
        margin_used = self._balance_metric_value(balances, "margin_used", "used_margin", "used")
        request_context = {
            "symbol": str(symbol or "").strip().upper(),
            "side": str(side or "").strip().lower(),
            "order_type": str(order_type or "market").strip().lower(),
            "requested_amount": float((quantity or {}).get("requested_amount", 0.0) or 0.0),
            "requested_quantity_mode": str((quantity or {}).get("requested_mode") or "units").strip().lower() or "units",
            "requested_units": float(requested_units),
            "hard_cap_units": float(deterministic_units),
            "reference_price": float(reference_price),
            "price": price,
            "stop_price": stop_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "equity": equity,
            "free_margin_or_cash": free_margin,
            "margin_used": margin_used,
            "margin_closeout_ratio": closeout_guard.get("ratio") if isinstance(closeout_guard, dict) else None,
            "max_position_size_pct": float(getattr(self, "max_position_size_pct", 0.10) or 0.10),
            "max_risk_per_trade": float(getattr(self, "max_risk_per_trade", 0.02) or 0.02),
        }
        payload = {
            "model": self.openai_model or "gpt-5-mini",
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a trade sizing assistant inside Sopotek Quant System. "
                        "Recommend a conservative order size for the exact symbol and account state provided. "
                        "Never exceed the hard_cap_units value. Never increase above the user's requested size. "
                        "If the trade should be skipped, return recommended_units as 0. "
                        "Return only compact JSON with keys recommended_units and reason."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(request_context, default=str),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400:
                        self.logger.debug("OpenAI trade sizing request failed: %s", data)
                        return None
        except Exception:
            self.logger.debug("OpenAI trade sizing request failed", exc_info=True)
            return None

        response_text = data.get("output_text")
        if not isinstance(response_text, str) or not response_text.strip():
            parts = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    content_text = content.get("text")
                    if isinstance(content_text, str) and content_text.strip():
                        parts.append(content_text.strip())
            response_text = "\n".join(parts)

        recommendation = self._extract_json_object(response_text)
        if not isinstance(recommendation, dict):
            return None

        try:
            recommended_units = float(recommendation.get("recommended_units"))
        except Exception:
            return None
        recommended_units = max(0.0, min(float(requested_units), float(deterministic_units), recommended_units))
        return {
            "recommended_units": recommended_units,
            "reason": str(recommendation.get("reason") or "").strip(),
        }

    @staticmethod
    def _should_ignore_ai_size_rejection(reason):
        lowered = str(reason or "").strip().lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                "invalid risk params",
                "cannot size trade safely",
                "stop_loss",
                "take_profit",
                "stop loss",
                "take profit",
            )
        )

    @staticmethod
    def _is_balance_or_equity_trade_rejection(reason):
        lowered = str(reason or "").strip().lower()
        if not lowered:
            return False
        return any(
            token in lowered
            for token in (
                "insufficient margin",
                "insufficient_margin",
                "insufficient funds",
                "insufficient_funds",
                "insufficient balance",
                "insufficient_balance",
                "margin available",
                "margin_available",
                "not enough margin",
                "not_enough_margin",
                "not enough funds",
                "not_enough_funds",
                "not enough balance",
                "not_enough_balance",
                "no available balance",
                "no_available_balance",
                "no free margin",
                "no_free_margin",
                "insufficient buying power",
                "insufficient_buying_power",
                "not enough buying power",
                "not_enough_buying_power",
            )
        )

    def _trade_account_unit_price(self, reference_price, risk_context=None):
        price_value = self._safe_balance_metric(reference_price)
        if price_value is None or price_value <= 0:
            return None

        account_price = float(price_value)
        if isinstance(risk_context, dict) and bool(risk_context.get("is_forex")):
            quote_to_account_rate = self._safe_balance_metric(
                risk_context.get("quote_to_account_rate", 1.0)
            )
            if quote_to_account_rate is not None and quote_to_account_rate > 0:
                account_price *= float(quote_to_account_rate)
        return account_price if account_price > 0 else None

    async def _retry_user_trade_after_balance_rejection(
            self,
            *,
            order,
            preflight,
            symbol,
            side,
            amount,
            quantity_mode=None,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
            source="manual",
            strategy_name="Manual",
            reason="Manual order",
            timeframe=None,
    ):
        if not isinstance(order, dict):
            return order, preflight
        if not self._is_user_directed_trade_source(source):
            return order, preflight

        status = str(order.get("status") or "").strip().lower()
        reject_reason = str(
            order.get("reason")
            or (
                ((order.get("raw") or {}) if isinstance(order.get("raw"), dict) else {}).get("error")
            )
            or ""
        ).strip()
        if status != "rejected" or not self._is_balance_or_equity_trade_rejection(reject_reason):
            return order, preflight

        previous_units = self._safe_balance_metric(order.get("amount"))
        if previous_units is None:
            previous_units = self._safe_balance_metric((preflight or {}).get("amount_units"))
        previous_units = max(0.0, float(previous_units or 0.0))
        if previous_units <= 0:
            order["retried_after_rejection"] = False
            order["initial_rejection_reason"] = reject_reason
            return order, preflight

        refreshed_preflight = await self._preflight_trade_submission(
            symbol=symbol,
            side=side,
            amount=amount,
            quantity_mode=quantity_mode,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            source=source,
            timeframe=timeframe,
        )
        retry_units = max(0.0, float(refreshed_preflight.get("amount_units") or 0.0))
        if retry_units <= 0 or retry_units >= previous_units - 1e-9:
            order["retried_after_rejection"] = False
            order["initial_rejection_reason"] = reject_reason
            order["retry_sizing_summary"] = (
                "Broker rejected the first size and the latest balance/equity snapshot did not yield a smaller safe amount."
            )
            return order, preflight

        order_symbol = str(refreshed_preflight.get("symbol") or symbol).strip().upper() or str(symbol or "").strip().upper()
        trading_system = getattr(self, "trading_system", None)
        execution_manager = getattr(trading_system, "execution_manager", None)
        broker = getattr(self, "broker", None)

        retry_summary = (
            "Broker rejected the first size, so Sopotek recalculated from the latest balance/equity snapshot and retried smaller."
        )
        if hasattr(self, "_record_trade_audit"):
            await self._record_trade_audit(
                "submit_retry",
                status="retrying",
                symbol=order_symbol,
                requested_symbol=str(refreshed_preflight.get("requested_symbol") or symbol).strip().upper(),
                side=side,
                order_type=order_type,
                source=source,
                venue=refreshed_preflight.get("resolved_venue"),
                message=retry_summary,
                payload={
                    "initial_rejection_reason": reject_reason,
                    "previous_order": dict(order),
                    "preflight": dict(refreshed_preflight),
                },
            )

        if execution_manager is not None:
            retried_order = await execution_manager.execute(
                symbol=order_symbol,
                side=side,
                amount=retry_units,
                type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                source=source,
                strategy_name=strategy_name,
                reason=reason,
                confidence=1.0,
            )
        elif broker is not None:
            retried_order = await broker.create_order(
                symbol=order_symbol,
                side=side,
                amount=retry_units,
                type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if isinstance(retried_order, dict):
                retried_order.setdefault("source", source)
                retried_order.setdefault("strategy_name", strategy_name)
                retried_order.setdefault("reason", reason)
        else:
            retried_order = None

        if not isinstance(retried_order, dict):
            order["retried_after_rejection"] = False
            order["initial_rejection_reason"] = reject_reason
            order["retry_sizing_summary"] = retry_summary
            return order, preflight

        retried_order["retried_after_rejection"] = True
        retried_order["initial_rejection_reason"] = reject_reason
        retried_order["retry_sizing_summary"] = retry_summary
        return retried_order, refreshed_preflight

    async def _preflight_trade_submission(
            self,
            *,
            symbol,
            side,
            amount,
            quantity_mode=None,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
            source=None,
            timeframe=None,
    ):
        broker = getattr(self, "broker", None)
        if broker is None:
            raise RuntimeError("Connect a broker before placing an order.")

        resolved_symbol = self._resolve_preferred_market_symbol(symbol) or self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        quantity = self.normalize_trade_quantity(resolved_symbol, amount, quantity_mode=quantity_mode)
        requested_units = float(quantity["amount_units"])
        exchange_name = str(getattr(broker, "exchange_name", "") or "").strip().lower()
        eligibility = self._evaluate_trade_eligibility(resolved_symbol)
        if not eligibility.get("ok"):
            raise RuntimeError(" ".join(str(item).strip() for item in eligibility.get("issues", []) if str(item).strip()))

        live_balances = {}
        if hasattr(broker, "fetch_balance"):
            try:
                live_balances = await self._fetch_balances(broker) or {}
            except Exception:
                self.logger.debug("Order preflight balance fetch failed for %s", symbol, exc_info=True)
                live_balances = {}
        balances = live_balances if isinstance(live_balances, dict) and live_balances else dict(getattr(self, "balances", {}) or {})
        if isinstance(live_balances, dict) and live_balances:
            self.balances = live_balances
            self.balance = live_balances

        closeout_guard = self.margin_closeout_snapshot(balances)
        if closeout_guard.get("blocked"):
            raise RuntimeError(str(closeout_guard.get("reason") or "Margin closeout guard blocked the trade."))

        reference_price, _ticker = await self._resolve_trade_reference_price(
            resolved_symbol,
            side,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
        )
        market_data_guard = await self._assess_trade_market_data_guard(
            resolved_symbol,
            timeframe=timeframe_value,
            ticker=_ticker,
        )
        if self.is_live_mode() and market_data_guard.get("blocked"):
            raise RuntimeError(" ".join(str(item).strip() for item in market_data_guard.get("reasons", []) if str(item).strip()))
        base_currency, quote_currency = self._trade_symbol_parts(resolved_symbol)
        free_margin = self._balance_metric_value(
            balances,
            "free_margin",
            "available_margin",
            "margin_available",
        )
        if exchange_name == "alpaca":
            available_cash = self._balance_metric_value(
                balances,
                "buying_power",
                "available_funds",
                "cash",
                "free",
            )
        else:
            available_cash = self._balance_metric_value(
                balances,
                "cash",
                "buying_power",
                "available_funds",
                "free",
            )
        equity = self._extract_balance_equity_value(balances if isinstance(balances, dict) else {})
        trading_system = getattr(self, "trading_system", None)
        risk_engine = getattr(trading_system, "risk_engine", None)
        risk_context = await self._resolve_trade_risk_context(
            resolved_symbol,
            reference_price,
            balances,
            broker=broker,
            allow_cross_conversion=risk_engine is not None,
        )
        account_unit_price = self._trade_account_unit_price(reference_price, risk_context)
        account_currency = str(risk_context.get("account_currency") or "").strip().upper() or None

        hard_caps = []
        sizing_notes = []
        side_value = str(side or "").strip().lower() or "buy"

        if equity is not None and equity <= 0:
            raise RuntimeError("Account equity is zero. New trades are blocked.")

        if exchange_name != "oanda" and base_currency and quote_currency:
            free_quote_balance = self._balance_bucket_currency_value(balances, "free", quote_currency)
            free_base_balance = self._balance_bucket_currency_value(balances, "free", base_currency)
            if side_value == "buy" and free_quote_balance is not None and reference_price and reference_price > 0:
                if free_quote_balance <= 0:
                    raise RuntimeError(f"No available {quote_currency} balance to buy {resolved_symbol}.")
                quote_cap = max(0.0, float(free_quote_balance) * self.ORDER_SIZE_BUFFER / float(reference_price))
                hard_caps.append(quote_cap)
                if quote_cap + 1e-12 < requested_units:
                    sizing_notes.append(f"Available {quote_currency} balance reduced the order size.")
            if side_value == "sell" and free_base_balance is not None:
                if free_base_balance <= 0:
                    raise RuntimeError(f"No available {base_currency} balance to sell {resolved_symbol}.")
                base_cap = max(0.0, float(free_base_balance) * self.ORDER_SIZE_BUFFER)
                hard_caps.append(base_cap)
                if base_cap + 1e-12 < requested_units:
                    sizing_notes.append(f"Available {base_currency} balance reduced the order size.")
        elif side_value == "buy" and available_cash is not None and reference_price and reference_price > 0 and exchange_name != "oanda":
            if available_cash <= 0:
                raise RuntimeError(f"No available cash balance to buy {symbol}.")
            cash_cap = max(0.0, float(available_cash) * self.ORDER_SIZE_BUFFER / float(reference_price))
            hard_caps.append(cash_cap)
            if cash_cap + 1e-12 < requested_units:
                sizing_notes.append("Available cash balance reduced the order size.")

        margin_rate = await self._instrument_margin_rate(resolved_symbol, broker=broker)
        margin_cap_applied = False
        if (
                account_unit_price is not None
                and free_margin is not None
                and margin_rate is not None
                and margin_rate > 0
        ):
            if free_margin <= 0:
                raise RuntimeError("No free margin is available for a new leveraged trade.")
            margin_cap = max(
                0.0,
                float(free_margin) * self.ORDER_SIZE_BUFFER / (float(account_unit_price) * float(margin_rate)),
                )
            hard_caps.append(margin_cap)
            margin_cap_applied = True
            if margin_cap + 1e-12 < requested_units:
                sizing_notes.append("Free margin reduced the order size for this symbol.")

        if (
                exchange_name == "oanda"
                and not margin_cap_applied
                and free_margin is None
                and available_cash is not None
                and account_unit_price is not None
                and account_currency
                and account_currency == quote_currency
        ):
            if available_cash <= 0:
                raise RuntimeError("No available account balance is available for a new trade.")
            balance_cap = max(
                0.0,
                float(available_cash) * self.ORDER_SIZE_BUFFER / float(account_unit_price),
                )
            hard_caps.append(balance_cap)
            if balance_cap + 1e-12 < requested_units:
                sizing_notes.append("Available account balance reduced the order size.")

        if risk_engine is not None and equity is not None and hasattr(risk_engine, "sync_equity"):
            try:
                risk_engine.sync_equity(equity)
            except Exception:
                self.logger.debug("Risk engine equity sync failed during order preflight", exc_info=True)
        if risk_engine is not None and reference_price and reference_price > 0 and hasattr(risk_engine, "adjust_trade"):
            try:
                allowed, adjusted_units, risk_reason = risk_engine.adjust_trade(
                    float(reference_price),
                    requested_units,
                    symbol=resolved_symbol,
                    stop_price=stop_loss,
                    quote_to_account_rate=risk_context.get("quote_to_account_rate", 1.0),
                    pip_size=risk_context.get("pip_size"),
                )
            except Exception:
                self.logger.debug("Risk engine preflight check failed for %s", symbol, exc_info=True)
                allowed, adjusted_units, risk_reason = True, requested_units, ""
            if not allowed:
                raise RuntimeError(str(risk_reason or "Risk engine rejected the trade."))
            adjusted_units = max(0.0, float(adjusted_units))
            hard_caps.append(adjusted_units)
            if adjusted_units + 1e-12 < requested_units:
                sizing_notes.append(str(risk_reason or "Risk settings reduced the order size.").strip())
        elif (
                equity is not None
                and account_unit_price is not None
                and not self._is_user_directed_trade_source(source)
        ):
            max_position_size_pct = max(0.001, float(getattr(self, "max_position_size_pct", 0.10) or 0.10))
            risk_cap = max(0.0, float(equity) * max_position_size_pct / float(account_unit_price))
            hard_caps.append(risk_cap)
            if risk_cap + 1e-12 < requested_units:
                sizing_notes.append(f"Risk settings capped the order to {max_position_size_pct:.1%} of equity.")

        deterministic_units = requested_units
        positive_caps = [float(cap) for cap in hard_caps if cap is not None and float(cap) > 0]
        if positive_caps:
            deterministic_units = min([requested_units, *positive_caps])
        if deterministic_units <= 0:
            raise RuntimeError("No safe order size is available with the current balance, margin, and risk settings.")

        normalized_source = str(source or "").strip().lower()
        ai_recommendation = None
        if normalized_source != "manual":
            ai_recommendation = await self._recommend_trade_size_with_openai(
                symbol=resolved_symbol,
                side=side_value,
                quantity=quantity,
                requested_units=requested_units,
                deterministic_units=deterministic_units,
                reference_price=reference_price,
                balances=balances,
                closeout_guard=closeout_guard,
                order_type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        final_units = deterministic_units
        ai_adjusted = False
        if isinstance(ai_recommendation, dict):
            ai_units = max(0.0, float(ai_recommendation.get("recommended_units", deterministic_units) or 0.0))
            if ai_units <= 0:
                ai_reason = str(ai_recommendation.get("reason") or "").strip()
                if self._should_ignore_ai_size_rejection(ai_reason):
                    ai_units = final_units
                else:
                    raise RuntimeError(ai_reason or "OpenAI sizing recommended skipping this trade.")
            if ai_units + 1e-12 < final_units:
                final_units = ai_units
                ai_adjusted = True
                ai_reason = str(ai_recommendation.get("reason") or "").strip()
                if ai_reason:
                    sizing_notes.append(ai_reason)

        if closeout_guard.get("warning") and not closeout_guard.get("blocked"):
            warning_reason = str(closeout_guard.get("reason") or "").strip()
            if warning_reason:
                sizing_notes.append(warning_reason)

        size_adjusted = abs(final_units - requested_units) > 1e-9
        applied_display_amount = self._display_trade_amount(final_units, quantity)
        summary_parts = []
        if abs(deterministic_units - requested_units) > 1e-9:
            summary_parts.append(
                f"Preflight reduced the order to {applied_display_amount} {quantity['requested_mode']} using balance, margin, or risk limits."
            )
        if ai_adjusted:
            summary_parts.append("OpenAI sizing guidance was applied.")
        if not summary_parts:
            summary_parts.append("Preflight kept the requested size.")

        prepared = dict(quantity)
        prepared.update(
            {
                "symbol": resolved_symbol,
                "requested_symbol": self._normalize_market_data_symbol(symbol) or resolved_symbol,
                "requested_amount_units": requested_units,
                "amount_units": float(final_units),
                "deterministic_amount_units": float(deterministic_units),
                "reference_price": float(reference_price) if reference_price is not None else None,
                "balances": balances,
                "trade_timeframe": timeframe_value,
                "closeout_guard": closeout_guard,
                "market_data_guard": market_data_guard,
                "eligibility_check": eligibility,
                "resolved_venue": eligibility.get("resolved_venue"),
                "supported_market_venues": eligibility.get("supported_market_venues"),
                "size_adjusted": size_adjusted,
                "ai_adjusted": ai_adjusted,
                "applied_requested_mode_amount": applied_display_amount,
                "sizing_summary": " ".join(part for part in summary_parts if part).strip(),
                "sizing_notes": [note for note in sizing_notes if note],
                "ai_sizing_reason": (
                    ""
                    if self._should_ignore_ai_size_rejection((ai_recommendation or {}).get("reason"))
                    else str((ai_recommendation or {}).get("reason") or "").strip()
                ),
            }
        )
        return prepared

    async def preview_trade_submission(
            self,
            *,
            symbol,
            side,
            amount,
            quantity_mode=None,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
            source="manual",
            timeframe=None,
    ):
        return await self._preflight_trade_submission(
            symbol=symbol,
            side=side,
            amount=amount,
            quantity_mode=quantity_mode,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            source=source,
            timeframe=timeframe,
        )

    async def submit_trade_with_preflight(
            self,
            *,
            symbol,
            side,
            amount,
            quantity_mode=None,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
            source="manual",
            strategy_name="Manual",
            reason="Manual order",
            preflight=None,
            timeframe=None,
    ):
        broker = getattr(self, "broker", None)
        if broker is None:
            raise RuntimeError("Connect a broker before placing an order.")

        if not isinstance(preflight, dict):
            preflight = await self._preflight_trade_submission(
                symbol=symbol,
                side=side,
                amount=amount,
                quantity_mode=quantity_mode,
                order_type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                source=source,
                timeframe=timeframe,
            )
        order_symbol = str(preflight.get("symbol") or symbol).strip().upper() or str(symbol or "").strip().upper()
        amount_units = float(preflight["amount_units"])
        requested_symbol = str(preflight.get("requested_symbol") or symbol).strip().upper()

        await self._record_trade_audit(
            "submit_attempt",
            status="pending",
            symbol=order_symbol,
            requested_symbol=requested_symbol,
            side=side,
            order_type=order_type,
            source=source,
            venue=preflight.get("resolved_venue"),
            message="Trade preflight approved and order submission started.",
            payload={"preflight": dict(preflight)},
        )

        trading_system = getattr(self, "trading_system", None)
        execution_manager = getattr(trading_system, "execution_manager", None)
        order = None
        if self._hybrid_trading_available():
            try:
                order = await self._submit_trade_via_hybrid_server(
                    symbol=order_symbol,
                    side=side,
                    amount_units=amount_units,
                    order_type=order_type,
                    price=price,
                    stop_price=stop_price,
                    source=source,
                    strategy_name=strategy_name,
                    reason=reason,
                    timeframe=preflight.get("trade_timeframe") or timeframe,
                )
            except Exception as exc:
                self.hybrid_server_last_error = str(exc)
                self.logger.warning("Hybrid order routing failed; falling back to local execution: %s", exc)
                self._set_hybrid_status(
                    f"Server order routing failed, so the desktop is falling back to local execution: {exc}",
                    tone="error",
                )
        try:
            if order is None and execution_manager is not None:
                order = await execution_manager.execute(
                    symbol=order_symbol,
                    side=side,
                    amount=amount_units,
                    type=order_type,
                    price=price,
                    stop_price=stop_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    source=source,
                    strategy_name=strategy_name,
                    reason=reason,
                    confidence=1.0,
                )
            elif order is None:
                order = await broker.create_order(
                    symbol=order_symbol,
                    side=side,
                    amount=amount_units,
                    type=order_type,
                    price=price,
                    stop_price=stop_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                if isinstance(order, dict):
                    order.setdefault("source", source)
                    order.setdefault("strategy_name", strategy_name)
                    order.setdefault("reason", reason)
        except Exception as exc:
            await self._record_trade_audit(
                "submit_error",
                status="error",
                symbol=order_symbol,
                requested_symbol=requested_symbol,
                side=side,
                order_type=order_type,
                source=source,
                venue=preflight.get("resolved_venue"),
                message=str(exc),
                payload={"preflight": dict(preflight)},
            )
            raise

        order, preflight = await self._retry_user_trade_after_balance_rejection(
            order=order,
            preflight=preflight,
            symbol=symbol,
            side=side,
            amount=amount,
            quantity_mode=quantity_mode,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            source=source,
            strategy_name=strategy_name,
            reason=reason,
            timeframe=preflight.get("trade_timeframe") or timeframe,
        )

        if not order:
            skip_reason = None
            if execution_manager is not None and hasattr(execution_manager, "last_skip_reason"):
                try:
                    skip_reason = execution_manager.last_skip_reason(order_symbol)
                except Exception:
                    skip_reason = None
            await self._record_trade_audit(
                "submit_skipped",
                status="skipped",
                symbol=order_symbol,
                requested_symbol=requested_symbol,
                side=side,
                order_type=order_type,
                source=source,
                venue=preflight.get("resolved_venue"),
                message=skip_reason or "The order was skipped by broker or safety checks.",
                payload={"preflight": dict(preflight)},
            )
            raise RuntimeError(skip_reason or "The order was skipped by broker or safety checks.")

        if isinstance(order, dict):
            order.setdefault("symbol", order_symbol)
            order["requested_symbol"] = requested_symbol
            actual_amount_units = self._safe_balance_metric(order.get("amount"))
            if actual_amount_units is None:
                actual_amount_units = amount_units
            order["requested_amount"] = float(preflight["requested_amount"])
            order["requested_quantity_mode"] = preflight["requested_mode"]
            order["amount_units"] = float(actual_amount_units)
            order["applied_requested_mode_amount"] = self._display_trade_amount(actual_amount_units, preflight)
            order["size_adjusted"] = abs(float(actual_amount_units) - float(preflight["requested_amount_units"])) > 1e-9
            order["ai_adjusted"] = bool(preflight.get("ai_adjusted"))
            order["reference_price"] = preflight.get("reference_price")
            order["sizing_summary"] = preflight.get("sizing_summary")
            order["sizing_notes"] = list(preflight.get("sizing_notes", []) or [])
            order["ai_sizing_reason"] = preflight.get("ai_sizing_reason")
            order["closeout_guard"] = dict(preflight.get("closeout_guard") or {})
            order["trade_timeframe"] = preflight.get("trade_timeframe")
            order["market_data_guard"] = dict(preflight.get("market_data_guard") or {})
            order["eligibility_check"] = dict(preflight.get("eligibility_check") or {})
            order["resolved_venue"] = preflight.get("resolved_venue")
            retry_summary = str(order.get("retry_sizing_summary") or "").strip()
            if retry_summary:
                base_summary = str(order.get("sizing_summary") or "").strip()
                order["sizing_summary"] = (
                    f"{retry_summary} {base_summary}".strip()
                    if base_summary
                    else retry_summary
                )
                initial_rejection_reason = str(order.get("initial_rejection_reason") or "").strip()
                if initial_rejection_reason:
                    existing_notes = list(order.get("sizing_notes", []) or [])
                    order["sizing_notes"] = [initial_rejection_reason, *existing_notes]

        await self._record_trade_audit(
            "submit_success",
            status=str((order or {}).get("status") or "submitted"),
            symbol=order_symbol,
            requested_symbol=requested_symbol,
            side=side,
            order_type=order_type,
            source=source,
            order_id=(order or {}).get("id") if isinstance(order, dict) else None,
            venue=preflight.get("resolved_venue"),
            message="Order submission completed.",
            payload={"preflight": dict(preflight), "order": dict(order) if isinstance(order, dict) else order},
        )
        if isinstance(order, dict):
            order = await self._handle_user_trade_review(
                order,
                symbol=order_symbol,
                side=side,
                order_type=order_type,
                price=price,
                stop_price=stop_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                source=source,
                timeframe=preflight.get("trade_timeframe") or timeframe,
            )
        return order

    def _normalize_strategy_symbol_key(self, symbol):
        return self._normalize_market_data_symbol(symbol)

    def _load_strategy_symbol_payload(self, key):
        raw_value = self.settings.value(key, "{}")
        try:
            payload = json.loads(raw_value or "{}")
        except Exception:
            payload = {}
        normalized = {}
        if not isinstance(payload, dict):
            return normalized
        for symbol, rows in payload.items():
            normalized_symbol = self._normalize_strategy_symbol_key(symbol)
            source_rows = list(rows or [])
            cleaned_rows = []
            for row in source_rows:
                if not isinstance(row, dict):
                    continue
                strategy_name = Strategy.normalize_strategy_name(row.get("strategy_name"))
                if not strategy_name:
                    continue
                assignment_mode = str(
                    row.get("assignment_mode") or ("ranked" if len(source_rows) > 1 else "single")
                ).strip().lower()
                assignment_source = str(row.get("assignment_source") or "manual").strip().lower()
                cleaned_rows.append(
                    {
                        "strategy_name": strategy_name,
                        "score": float(row.get("score", 0.0) or 0.0),
                        "weight": float(row.get("weight", 0.0) or 0.0),
                        "symbol": normalized_symbol,
                        "timeframe": str(row.get("timeframe") or "").strip(),
                        "assignment_mode": assignment_mode if assignment_mode in {"single", "ranked"} else "single",
                        "assignment_source": assignment_source if assignment_source in {"manual", "auto"} else "manual",
                        "rank": int(row.get("rank", len(cleaned_rows) + 1) or (len(cleaned_rows) + 1)),
                        "total_profit": float(row.get("total_profit", 0.0) or 0.0),
                        "sharpe_ratio": float(row.get("sharpe_ratio", 0.0) or 0.0),
                        "win_rate": float(row.get("win_rate", 0.0) or 0.0),
                        "final_equity": float(row.get("final_equity", 0.0) or 0.0),
                        "max_drawdown": float(row.get("max_drawdown", 0.0) or 0.0),
                        "closed_trades": int(row.get("closed_trades", 0) or 0),
                    }
                )
            if cleaned_rows:
                normalized[normalized_symbol] = cleaned_rows
        return normalized

    def _persist_strategy_symbol_state(self):
        lock_set = getattr(self, "symbol_strategy_locks", None)
        if not isinstance(lock_set, set):
            lock_set = set(lock_set or [])
            self.symbol_strategy_locks = lock_set
        self.settings.setValue("strategy/multi_strategy_enabled", bool(self.multi_strategy_enabled))
        self.settings.setValue("strategy/max_symbol_strategies", int(self.max_symbol_strategies))
        self.settings.setValue("strategy/symbol_assignments", json.dumps(self.symbol_strategy_assignments))
        self.settings.setValue("strategy/symbol_rankings", json.dumps(self.symbol_strategy_rankings))
        self.settings.setValue("strategy/symbol_assignment_locks", json.dumps(sorted(lock_set)))
        self.settings.setValue("strategy/auto_assignment_enabled", bool(getattr(self, "strategy_auto_assignment_enabled", True)))
        self._sync_session_scoped_state()

    def _load_strategy_symbol_lock_payload(self, key, fallback_symbols=None):
        raw_value = self.settings.value(key, None)
        payload = None
        if raw_value not in (None, ""):
            try:
                payload = json.loads(raw_value)
            except Exception:
                payload = None

        if payload is None:
            source = list(fallback_symbols or [])
        elif isinstance(payload, dict):
            source = [symbol for symbol, locked in payload.items() if locked]
        elif isinstance(payload, (list, tuple, set)):
            source = list(payload)
        else:
            source = []

        normalized = []
        for symbol in source:
            normalized_symbol = self._normalize_strategy_symbol_key(symbol)
            if normalized_symbol and normalized_symbol not in normalized:
                normalized.append(normalized_symbol)
        return set(normalized)

    def _mark_symbol_strategy_assignment_locked(self, symbol, locked=True):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        lock_set = getattr(self, "symbol_strategy_locks", None)
        if not isinstance(lock_set, set):
            lock_set = set(lock_set or [])
            self.symbol_strategy_locks = lock_set
        if not normalized_symbol:
            return False
        if locked:
            lock_set.add(normalized_symbol)
        else:
            lock_set.discard(normalized_symbol)
        return normalized_symbol in lock_set

    def symbol_strategy_assignment_locked(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        lock_set = getattr(self, "symbol_strategy_locks", set()) or set()
        return normalized_symbol in lock_set

    def _strategy_auto_assignment_symbols(self, symbols=None, advance_rotation=False):
        broker_type = self._active_broker_type()
        exchange_code = self._active_exchange_code()
        symbol_sources = []
        if symbols is not None:
            symbol_sources.append(list(symbols or []))
        else:
            saved_sources = [
                list(getattr(self, "symbol_strategy_assignments", {}).keys()),
                list(getattr(self, "symbol_strategy_rankings", {}).keys()),
                list(getattr(self, "symbol_strategy_locks", set()) or set()),
            ]
            symbol_sources.extend(saved_sources)
            symbol_sources.append(
                self._rotating_discovery_batch(
                    limit=self._strategy_auto_assignment_symbol_limit(),
                    advance=advance_rotation,
                )
            )
            symbol_sources.extend(
                [
                    list(getattr(self, "symbols", []) or []),
                    list((getattr(self, "_symbol_universe_tiers", {}) or {}).get("watchlist", []) or []),
                ]
            )

        symbol_candidates = []
        for source in symbol_sources:
            for symbol in list(source or []):
                normalized_symbol = self._normalize_strategy_symbol_key(symbol)
                if (
                        normalized_symbol
                        and self._is_plausible_market_symbol(normalized_symbol, broker_type=broker_type, exchange=exchange_code)
                        and normalized_symbol not in symbol_candidates
                ):
                    symbol_candidates.append(normalized_symbol)
        return symbol_candidates

    def _symbol_has_saved_strategy_state(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if not normalized_symbol:
            return False
        if self.symbol_strategy_assignment_locked(normalized_symbol):
            return True
        assigned_rows = list((getattr(self, "symbol_strategy_assignments", {}) or {}).get(normalized_symbol, []) or [])
        return bool(assigned_rows)

    def _partition_strategy_auto_assignment_symbols(self, symbols=None, symbol_candidates=None):
        if symbol_candidates is None:
            symbol_candidates = self._strategy_auto_assignment_symbols(symbols=symbols)
        restored_symbols = []
        missing_symbols = []
        for symbol in symbol_candidates:
            if self._symbol_has_saved_strategy_state(symbol):
                restored_symbols.append(symbol)
            else:
                missing_symbols.append(symbol)
        return symbol_candidates, missing_symbols, restored_symbols

    def _restore_saved_strategy_assignments(self, restored_symbols, timeframe=None, message=None):
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        restored_symbols = list(restored_symbols or [])
        restored_count = len(restored_symbols)
        summary_message = message or (
            f"Loaded saved strategy assignments for {restored_count} symbol{'s' if restored_count != 1 else ''}."
            if restored_count
            else "No saved strategy assignments were available."
        )

        self.strategy_auto_assignment_in_progress = False
        self.strategy_auto_assignment_ready = True
        self._update_strategy_auto_assignment_progress(
            completed=restored_count,
            total=restored_count,
            current_symbol="",
            timeframe=timeframe_value,
            message=summary_message,
            failed_symbols=[],
        )

        trading_system = getattr(self, "trading_system", None)
        if trading_system is not None and hasattr(trading_system, "refresh_strategy_preferences"):
            try:
                trading_system.refresh_strategy_preferences()
            except Exception:
                pass

        return {
            "assigned_symbols": [],
            "restored_symbols": list(restored_symbols),
            "skipped_symbols": [],
            "failed_symbols": [],
            "timeframe": timeframe_value,
        }

    def strategy_auto_assignment_status(self):
        progress = dict(getattr(self, "strategy_auto_assignment_progress", {}) or {})
        progress["failed_symbols"] = list(progress.get("failed_symbols", []) or [])
        progress["enabled"] = bool(getattr(self, "strategy_auto_assignment_enabled", True))
        progress["running"] = bool(getattr(self, "strategy_auto_assignment_in_progress", False))
        progress["ready"] = (not progress["enabled"]) or bool(getattr(self, "strategy_auto_assignment_ready", False))
        progress["locked_symbols"] = sorted(list(getattr(self, "symbol_strategy_locks", set()) or set()))
        progress["assigned_symbols"] = len(getattr(self, "symbol_strategy_assignments", {}) or {})
        return progress

    def _update_strategy_auto_assignment_progress(self, **changes):
        snapshot = dict(getattr(self, "strategy_auto_assignment_progress", {}) or {})
        snapshot.update(changes)
        snapshot["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "failed_symbols" not in snapshot:
            snapshot["failed_symbols"] = []
        else:
            snapshot["failed_symbols"] = list(snapshot.get("failed_symbols", []) or [])
        self.strategy_auto_assignment_progress = snapshot
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return snapshot
        window = getattr(terminal, "detached_tool_windows", {}).get("strategy_assignments")
        if window is not None and hasattr(terminal, "_refresh_strategy_assignment_window"):
            try:
                terminal._refresh_strategy_assignment_window(window=window, message=snapshot.get("message"))
            except Exception as error:
                self.logger.debug("Failed to refresh strategy assignment window with progress update", exc_info=True)
        return snapshot

    def _strategy_registry_for_auto_assignment(self):
        trading_system = getattr(self, "trading_system", None)
        registry = getattr(trading_system, "strategy", None)
        if registry is not None and hasattr(registry, "list"):
            return registry
        from strategy.strategy_registry import StrategyRegistry

        return StrategyRegistry()

    def _strategy_market_profile(self, symbol, broker_type=None, exchange=None):
        normalized_symbol = str(symbol or "").strip().upper()
        exchange_code = self._active_exchange_code(exchange=exchange)
        normalized_type = self._active_broker_type(broker_type=broker_type, exchange=exchange_code)
        active_preference = self._active_market_trade_preference_value()

        if exchange_code == "solana":
            return "solana"
        if exchange_code == "stellar":
            return "stellar"
        if normalized_type == "forex":
            return "forex"
        if normalized_type == "stocks":
            return "stocks"
        if normalized_type != "crypto":
            return "general"

        market = self._broker_market_for_symbol(normalized_symbol)
        is_derivative = (
                active_preference == "derivative"
                or ":" in normalized_symbol
                or self._symbol_market_is_derivative(normalized_symbol, market=market)
        )
        if is_derivative:
            return "crypto_derivative"

        quote = ""
        if "/" in normalized_symbol:
            _, quote = normalized_symbol.split("/", 1)
        quote = quote.split(":", 1)[0].strip().upper()
        if quote and quote not in {"USD", "USDC", "USDT", "BUSD", "FDUSD", "DAI"}:
            return "crypto_cross"
        return "crypto_spot"

    @staticmethod
    def _strategy_preference_order_for_profile(profile):
        mappings = {
            "solana": [
                "Bollinger Squeeze",
                "Volume Spike Reversal",
                "ATR Compression Breakout",
                "Momentum Continuation",
                "Donchian Trend",
                "Volatility Breakout",
                "RSI Failure Swing",
                "Range Fade",
                "Mean Reversion",
                "MACD Trend",
                "EMA Cross",
                "Trend Following",
                "Pullback Trend",
                "Breakout",
                "AI Hybrid",
                "ML Model",
            ],
            "stellar": [
                "Bollinger Squeeze",
                "RSI Failure Swing",
                "Volume Spike Reversal",
                "Mean Reversion",
                "Donchian Trend",
                "Momentum Continuation",
                "ATR Compression Breakout",
                "Volatility Breakout",
                "EMA Cross",
                "Trend Following",
                "MACD Trend",
                "Pullback Trend",
                "Range Fade",
                "Breakout",
                "AI Hybrid",
                "ML Model",
            ],
            "crypto_derivative": [
                "ATR Compression Breakout",
                "Donchian Trend",
                "Volatility Breakout",
                "MACD Trend",
                "Bollinger Squeeze",
                "Momentum Continuation",
                "Trend Following",
                "EMA Cross",
                "Pullback Trend",
                "Breakout",
                "Volume Spike Reversal",
                "RSI Failure Swing",
                "Mean Reversion",
                "Range Fade",
                "AI Hybrid",
                "ML Model",
            ],
            "crypto_cross": [
                "Volume Spike Reversal",
                "Bollinger Squeeze",
                "Momentum Continuation",
                "ATR Compression Breakout",
                "Volatility Breakout",
                "Range Fade",
                "Mean Reversion",
                "Donchian Trend",
                "RSI Failure Swing",
                "MACD Trend",
                "EMA Cross",
                "Trend Following",
                "Pullback Trend",
                "Breakout",
                "AI Hybrid",
                "ML Model",
            ],
            "crypto_spot": [
                "Bollinger Squeeze",
                "ATR Compression Breakout",
                "Momentum Continuation",
                "Volatility Breakout",
                "Donchian Trend",
                "Volume Spike Reversal",
                "MACD Trend",
                "EMA Cross",
                "Trend Following",
                "Pullback Trend",
                "RSI Failure Swing",
                "Mean Reversion",
                "Range Fade",
                "Breakout",
                "AI Hybrid",
                "ML Model",
            ],
            "forex": [
                "Donchian Trend",
                "MACD Trend",
                "EMA Cross",
                "Trend Following",
                "ATR Compression Breakout",
                "RSI Failure Swing",
                "Pullback Trend",
                "Mean Reversion",
                "Breakout",
                "Volatility Breakout",
                "Range Fade",
                "Momentum Continuation",
                "Bollinger Squeeze",
                "Volume Spike Reversal",
                "AI Hybrid",
                "ML Model",
            ],
            "stocks": [
                "Pullback Trend",
                "Donchian Trend",
                "EMA Cross",
                "Trend Following",
                "RSI Failure Swing",
                "MACD Trend",
                "Bollinger Squeeze",
                "Mean Reversion",
                "ATR Compression Breakout",
                "Volatility Breakout",
                "Breakout",
                "Momentum Continuation",
                "Volume Spike Reversal",
                "Range Fade",
                "AI Hybrid",
                "ML Model",
            ],
        }
        default = [
            "Trend Following",
            "EMA Cross",
            "MACD Trend",
            "Breakout",
            "Donchian Trend",
            "Pullback Trend",
            "Momentum Continuation",
            "Volatility Breakout",
            "Bollinger Squeeze",
            "ATR Compression Breakout",
            "RSI Failure Swing",
            "Volume Spike Reversal",
            "Mean Reversion",
            "Range Fade",
            "AI Hybrid",
            "ML Model",
        ]
        return list(mappings.get(str(profile or "").strip().lower(), default))

    def _strategy_names_for_auto_assignment(self, symbol, strategy_names, broker_type=None, exchange=None):
        normalized = []
        seen = set()
        for name in list(strategy_names or []):
            strategy_name = Strategy.normalize_strategy_name(name)
            if not strategy_name or strategy_name in seen:
                continue
            seen.add(strategy_name)
            normalized.append(strategy_name)
        if not normalized:
            return []

        profile = self._strategy_market_profile(symbol, broker_type=broker_type, exchange=exchange)
        preferred_order = self._strategy_preference_order_for_profile(profile)
        core_available = [name for name in Strategy.CORE_STRATEGIES if name in seen]
        shortlist_threshold = max(len(Strategy.CORE_STRATEGIES) + 4, len(core_available) * 2)
        shortlist_full_catalog = bool(core_available) and len(normalized) > shortlist_threshold
        candidate_pool = list(core_available) if shortlist_full_catalog else list(normalized)
        if not shortlist_full_catalog:
            return candidate_pool

        ordered = [name for name in preferred_order if name in candidate_pool]
        ordered.extend(name for name in candidate_pool if name not in ordered)
        return ordered

    def _apply_strategy_market_context_bias(self, rankings, symbol, broker_type=None, exchange=None):
        profile = self._strategy_market_profile(symbol, broker_type=broker_type, exchange=exchange)
        preferred_order = self._strategy_preference_order_for_profile(profile)
        preference_index = {name: index for index, name in enumerate(preferred_order)}

        biased = []
        for row in list(rankings or []):
            if not isinstance(row, dict):
                continue
            candidate = dict(row)
            strategy_name = Strategy.normalize_strategy_name(candidate.get("strategy_name"))
            if not strategy_name:
                continue
            base_name = Strategy.resolve_signal_strategy_name(strategy_name)
            raw_score = float(candidate.get("score", 0.0) or 0.0)
            index = preference_index.get(base_name)
            bonus = max(0.0, 0.9 - (0.08 * index)) if index is not None else 0.0
            candidate["strategy_name"] = strategy_name
            candidate["raw_score"] = raw_score
            candidate["market_profile"] = profile
            candidate["market_fit_bonus"] = float(bonus)
            candidate["score"] = float(raw_score + bonus)
            biased.append(candidate)

        biased.sort(
            key=lambda item: (
                -float(item.get("score", 0.0) or 0.0),
                -float(item.get("market_fit_bonus", 0.0) or 0.0),
                -float(item.get("total_profit", 0.0) or 0.0),
                -float(item.get("sharpe_ratio", 0.0) or 0.0),
                str(item.get("strategy_name") or ""),
            ),
        )
        return biased

    def _build_strategy_ranker(self, strategy_registry=None):
        from backtesting.strategy_ranker import StrategyRanker

        return StrategyRanker(
            strategy_registry=strategy_registry,
            initial_balance=getattr(self, "initial_capital", 1000)
        )

    def _get_strategy_ranking_executor(self):
        """
        Return a dedicated single-worker executor for strategy ranking.

        A single worker avoids heavy backtests competing against UI/event-loop tasks.
        """

        executor = getattr(self, "_strategy_ranking_executor", None)

        if executor is None:
         executor = ThreadPoolExecutor(
            max_workers=100,
            thread_name_prefix="strategy-ranker",
        )
        self._strategy_ranking_executor = executor

        return executor

    async def _run_strategy_ranking(
            self,
            ranker,
            data,
            symbol,
            timeframe=None,
            strategy_names=None,
            top_n=None,
            include_failed=True,
            export_csv_path=None,
            metadata=None,
    ):
        """
        Run strategy ranking safely in a background executor.

        Important:
        Do NOT pass extra positional arguments to run_in_executor after ranking_call.
        Anything after ranking_call becomes an argument to ranking_call itself.
        """

        loop = asyncio.get_running_loop()

        def ranking_call():
         return ranker.rank(
            data=data,
            symbol=symbol,
            timeframe=timeframe,
            strategy_names=strategy_names,
            top_n=top_n,
            include_failed=include_failed,
            export_csv_path=export_csv_path,
            metadata=metadata,
        )
        executor = self._get_strategy_ranking_executor()
        return await loop.run_in_executor(
            executor,
            ranking_call,
        )

    def _shutdown_strategy_ranking_executor(self, wait=False):
        executor = getattr(self, "_strategy_ranking_executor", None)
        if executor is None:
            return
        self._strategy_ranking_executor = None
        try:
            executor.shutdown(wait=bool(wait), cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=bool(wait))

    def _normalize_strategy_ranking_frame(self, dataset):
        if dataset is None:
            return None
        frame = dataset.copy() if hasattr(dataset, "copy") else pd.DataFrame(dataset)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if frame.empty:
            return None

        lowered = {str(column).strip().lower(): column for column in frame.columns}
        if all(name in lowered for name in ("timestamp", "open", "high", "low", "close", "volume")):
            normalized = frame[[lowered[name] for name in ("timestamp", "open", "high", "low", "close", "volume")]].copy()
            normalized.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        elif frame.shape[1] >= 6:
            normalized = frame.iloc[:, :6].copy()
            normalized.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        else:
            return None

        for column in ("open", "high", "low", "close", "volume"):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized.dropna(subset=["open", "high", "low", "close"], inplace=True)
        if normalized.empty:
            return None
        return normalized.reset_index(drop=True)

    def _strategy_auto_assignment_timeframes(self, timeframe=None):
        preferred = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip().lower() or "1h"
        configured = getattr(self, "strategy_assignment_scan_timeframes", None)
        if isinstance(configured, str):
            raw_timeframes = [configured]
        elif isinstance(configured, (list, tuple, set)) and configured:
            raw_timeframes = list(configured)
        elif self._is_spot_only_exchange_profile(exchange=self._active_exchange_code()):
            raw_timeframes = ["1h", "4h"]
        else:
            raw_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        normalized = []
        for item in [preferred, *raw_timeframes]:
            value = str(item or "").strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _strategy_auto_assignment_symbol_limit(self):
        policy = self._symbol_universe_policy()
        return int(policy.get("auto_assignment_limit", 0) or 0)

    def _startup_strategy_auto_assignment_delay_seconds(self, exchange=None):
        exchange_code = self._active_exchange_code(exchange=exchange)
        if exchange_code != "coinbase":
            return 0.0
        return max(0.0, float(getattr(self, "COINBASE_FAST_START_AUTO_ASSIGN_DELAY_SECONDS", 0.0) or 0.0))

    async def _run_deferred_strategy_auto_assignment(self, delay_seconds, symbols=None, timeframe=None):
        try:
            await asyncio.sleep(max(0.0, float(delay_seconds or 0.0)))
            if not getattr(self, "connected", False) or getattr(self, "broker", None) is None:
                return None
            task = self.schedule_strategy_auto_assignment(symbols=symbols, timeframe=timeframe, force=False)
            if task is None:
                return None
            return await task
        finally:
            current_task = asyncio.current_task()
            if getattr(self, "_strategy_auto_assignment_deferred_task", None) is current_task:
                self._strategy_auto_assignment_deferred_task = None

    def _schedule_startup_strategy_auto_assignment(self, symbols=None, timeframe=None, exchange=None):
        deferred_task = getattr(self, "_strategy_auto_assignment_deferred_task", None)
        if deferred_task is not None and not deferred_task.done():
            deferred_task.cancel()
        self._strategy_auto_assignment_deferred_task = None

        if not bool(getattr(self, "strategy_auto_assignment_enabled", True)):
            self.strategy_auto_assignment_ready = True
            return None

        delay_seconds = self._startup_strategy_auto_assignment_delay_seconds(exchange=exchange)
        scheduled_symbols = None
        if delay_seconds <= 0:
            return self.schedule_strategy_auto_assignment(symbols=scheduled_symbols, timeframe=timeframe, force=False)

        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        tracked_symbols = list(scheduled_symbols or [])
        if scheduled_symbols is None:
            tracked_symbols = self._rotating_discovery_batch(
                limit=self._strategy_auto_assignment_symbol_limit(),
                advance=False,
                exchange=exchange,
            )
        symbol_limit = int(self._strategy_auto_assignment_symbol_limit() or 0)
        if symbol_limit > 0:
            tracked_symbols = tracked_symbols[:symbol_limit]

        delay_label = int(round(delay_seconds))
        self.strategy_auto_assignment_ready = False
        self.strategy_auto_assignment_in_progress = False
        self._update_strategy_auto_assignment_progress(
            completed=0,
            total=len(tracked_symbols),
            current_symbol="",
            timeframe=timeframe_value,
            message=(
                f"Coinbase fast mode is letting the terminal settle first. "
                f"Automatic strategy ranking will start in about {delay_label} seconds."
            ),
            failed_symbols=[],
            scan_timeframes=list(self._strategy_auto_assignment_timeframes(timeframe=timeframe_value)),
        )
        terminal = getattr(self, "terminal", None)
        system_console = getattr(terminal, "system_console", None) if terminal is not None else None
        if system_console is not None:
            system_console.log(
                (
                    f"Coinbase fast mode enabled: delaying automatic strategy scan for about "
                    f"{delay_label} seconds so the terminal can finish loading."
                ),
                "INFO",
            )

        task = self._create_task(
            self._run_deferred_strategy_auto_assignment(
                delay_seconds,
                symbols=scheduled_symbols,
                timeframe=timeframe_value,
            ),
            "startup_strategy_auto_assignment",
        )
        self._strategy_auto_assignment_deferred_task = task
        return task

    def _best_strategy_rankings_across_timeframes(self, rankings):
        best_by_strategy = {}
        for row in list(rankings or []):
            if not isinstance(row, dict):
                continue
            strategy_name = Strategy.normalize_strategy_name(row.get("strategy_name"))
            if not strategy_name:
                continue
            candidate = dict(row)
            candidate["strategy_name"] = strategy_name
            candidate["timeframe"] = str(candidate.get("timeframe") or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
            candidate_score = float(candidate.get("score", 0.0) or 0.0)
            existing = best_by_strategy.get(strategy_name)
            existing_score = float(existing.get("score", 0.0) or 0.0) if isinstance(existing, dict) else float("-inf")
            if existing is None or candidate_score > existing_score:
                best_by_strategy[strategy_name] = candidate

        ordered = sorted(
            best_by_strategy.values(),
            key=lambda item: (
                -float(item.get("score", 0.0) or 0.0),
                -float(item.get("total_profit", 0.0) or 0.0),
                -float(item.get("sharpe_ratio", 0.0) or 0.0),
                str(item.get("timeframe") or ""),
            ),
        )
        for index, item in enumerate(ordered, start=1):
            item["rank"] = index
        return ordered

    def save_ranked_strategies_for_symbol(self, symbol, rankings, timeframe=None, assignment_source="manual", persist=True):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        assignment_source = str(assignment_source or "manual").strip().lower()
        if assignment_source not in {"manual", "auto"}:
            assignment_source = "manual"

        cleaned_rows = []
        for index, row in enumerate(list(rankings or []), start=1):
            if not isinstance(row, dict):
                continue
            strategy_name = Strategy.normalize_strategy_name(row.get("strategy_name"))
            if not strategy_name:
                continue
            cleaned_rows.append(
                {
                    "strategy_name": strategy_name,
                    "score": float(row.get("score", 0.0) or 0.0),
                    "weight": float(row.get("weight", 0.0) or 0.0),
                    "symbol": normalized_symbol,
                    "timeframe": str(row.get("timeframe") or timeframe or self.time_frame or "").strip(),
                    "assignment_mode": "ranked",
                    "assignment_source": assignment_source,
                    "rank": int(row.get("rank", index) or index),
                    "total_profit": float(row.get("total_profit", 0.0) or 0.0),
                    "sharpe_ratio": float(row.get("sharpe_ratio", 0.0) or 0.0),
                    "win_rate": float(row.get("win_rate", 0.0) or 0.0),
                    "final_equity": float(row.get("final_equity", 0.0) or 0.0),
                    "max_drawdown": float(row.get("max_drawdown", 0.0) or 0.0),
                    "closed_trades": int(row.get("closed_trades", 0) or 0),
                }
            )
        cleaned_rows.sort(key=lambda item: (-float(item.get("score", 0.0) or 0.0), int(item.get("rank", 0) or 0)))
        if cleaned_rows:
            self.symbol_strategy_rankings[normalized_symbol] = cleaned_rows
        else:
            self.symbol_strategy_rankings.pop(normalized_symbol, None)
        if persist:
            self._persist_strategy_symbol_state()
        return list(cleaned_rows)

    def schedule_strategy_auto_assignment(self, symbols=None, timeframe=None, force=False):
        deferred_task = getattr(self, "_strategy_auto_assignment_deferred_task", None)
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if deferred_task is not None and deferred_task is not current_task and not deferred_task.done():
            deferred_task.cancel()
            self._strategy_auto_assignment_deferred_task = None
        if not bool(getattr(self, "strategy_auto_assignment_enabled", True)) and not force:
            self.strategy_auto_assignment_ready = True
            return None
        source_symbols = (
            self._strategy_auto_assignment_symbols(symbols=symbols, advance_rotation=(symbols is None and self._active_exchange_code() == "coinbase"))
            if not force
            else self._strategy_auto_assignment_symbols(symbols=symbols)
        )
        if not force:
            _all_symbols, missing_symbols, restored_symbols = self._partition_strategy_auto_assignment_symbols(
                symbols=symbols,
                symbol_candidates=source_symbols,
            )
            if restored_symbols and not missing_symbols:
                self._strategy_auto_assignment_task = None
                self._restore_saved_strategy_assignments(
                    restored_symbols,
                    timeframe=timeframe,
                )
                return None
            if missing_symbols:
                symbols = list(missing_symbols)
            else:
                symbols = list(source_symbols or [])
        task = getattr(self, "_strategy_auto_assignment_task", None)
        if task is not None and not task.done():
            return task
        self.strategy_auto_assignment_ready = False
        self._strategy_auto_assignment_task = asyncio.get_event_loop().create_task(
            self.auto_rank_and_assign_strategies(symbols=symbols, timeframe=timeframe, force=force)
        )
        return self._strategy_auto_assignment_task

    async def auto_rank_and_assign_strategies(self,
                                              symbols=None, timeframe=None, force=False, min_candles=120, history_limit=240):
        if not bool(getattr(self, "strategy_auto_assignment_enabled", True)) and not force:
            self.strategy_auto_assignment_ready = True
            return self.strategy_auto_assignment_status()

        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        symbol_candidates = self._strategy_auto_assignment_symbols(
            symbols=symbols,
            advance_rotation=(symbols is None and self._active_exchange_code() == "coinbase"),
        )
        symbol_limit = int(self._strategy_auto_assignment_symbol_limit() or 0)
        if symbol_limit > 0:
            symbol_candidates = symbol_candidates[:symbol_limit]
        restored_symbols = []
        if not force:
            _all_symbols, missing_symbols, restored_symbols = self._partition_strategy_auto_assignment_symbols(
                symbols=symbols,
                symbol_candidates=symbol_candidates,
            )
            symbol_candidates = list(missing_symbols)
            if symbol_limit > 0:
                symbol_candidates = symbol_candidates[:symbol_limit]

        registry = self._strategy_registry_for_auto_assignment()
        available_strategy_names = list(getattr(registry, "list", lambda: [])() or [])
        if restored_symbols and not symbol_candidates:
            return self._restore_saved_strategy_assignments(restored_symbols, timeframe=timeframe_value)
        if not symbol_candidates or not available_strategy_names:
            self.strategy_auto_assignment_in_progress = False
            self.strategy_auto_assignment_ready = True
            self._update_strategy_auto_assignment_progress(
                completed=len(symbol_candidates),
                total=len(symbol_candidates),
                current_symbol="",
                timeframe=timeframe_value,
                message="No symbols or strategies available for automatic assignment.",
                failed_symbols=[],
            )
            return self.strategy_auto_assignment_status()

        self.strategy_auto_assignment_in_progress = True
        self.strategy_auto_assignment_ready = False
        timeframe_candidates = self._strategy_auto_assignment_timeframes(timeframe=timeframe_value)
        preview_strategy_names = self._strategy_names_for_auto_assignment(
            symbol_candidates[0],
            available_strategy_names,
        )
        preview_count = len(preview_strategy_names) or len(available_strategy_names)
        scan_message = (
            f"Scanning {len(symbol_candidates)} symbols across {len(timeframe_candidates)} timeframes "
            f"and ranking {preview_count} market-fit strategies."
        )
        if restored_symbols:
            scan_message = (
                f"Loaded saved strategy assignments for {len(restored_symbols)} "
                f"symbol{'s' if len(restored_symbols) != 1 else ''}. "
                f"Scanning {len(symbol_candidates)} new symbol{'s' if len(symbol_candidates) != 1 else ''} "
                f"across {len(timeframe_candidates)} timeframes and ranking {preview_count} market-fit strategies."
            )
        self._update_strategy_auto_assignment_progress(
            completed=0,
            total=len(symbol_candidates),
            current_symbol="",
            timeframe=timeframe_value,
            message=scan_message,
            failed_symbols=[]
        )
        terminal = getattr(self, "terminal", None)
        system_console = getattr(terminal, "system_console", None) if terminal is not None else None
        if system_console is not None:
            system_console.log(
                (
                    f"Scanning {len(symbol_candidates)} symbols across {len(timeframe_candidates)} timeframes "
                    f"and ranking {preview_count} market-fit strategies before manual overrides unlock."
                ),
                "INFO",
            )

        assigned_symbols = []
        skipped_symbols = []
        failed_symbols = []
        refreshed_preferences = False
        ranker = self._build_strategy_ranker(registry)

        try:
            for index, symbol in enumerate(symbol_candidates, start=1):
                self._update_strategy_auto_assignment_progress(
                    completed=index - 1,
                    total=len(symbol_candidates),
                    current_symbol=symbol,
                    timeframe=timeframe_value,
                    message=f"Scanning {symbol} ({index}/{len(symbol_candidates)}) and ranking strategies.",
                    failed_symbols=failed_symbols,
                )

                combined_records = []
                resolved_timeframes = []
                strategy_names = self._strategy_names_for_auto_assignment(
                    symbol,
                    available_strategy_names,
                )
                if not strategy_names:
                    failed_symbols.append({"symbol": symbol, "reason": "No market-fit strategies were available for ranking."})
                    continue
                for candidate_timeframe in timeframe_candidates:
                    symbol_cache = getattr(self, "candle_buffers", {}).get(symbol, {})
                    frame = self._normalize_strategy_ranking_frame(symbol_cache.get(candidate_timeframe) if isinstance(symbol_cache, dict) else None)
                    if frame is None or len(frame) < max(20, int(min_candles or 20)):
                        try:
                            fetched = await self.request_candle_data(
                                symbol,
                                timeframe=candidate_timeframe,
                                limit=max(int(history_limit or 240), int(min_candles or 120)),
                            )
                        except Exception as exc:
                            fetched = None
                            if not any(
                                    item.get("symbol") == symbol and str(item.get("timeframe") or "") == candidate_timeframe
                                    for item in failed_symbols
                            ):
                                failed_symbols.append({"symbol": symbol, "timeframe": candidate_timeframe, "reason": str(exc)})
                        frame = self._normalize_strategy_ranking_frame(fetched)
                        if frame is None:
                            symbol_cache = getattr(self, "candle_buffers", {}).get(symbol, {})
                            frame = self._normalize_strategy_ranking_frame(symbol_cache.get(candidate_timeframe) if isinstance(symbol_cache, dict) else None)

                    if frame is None or len(frame) < max(20, int(min_candles or 20)):
                        continue

                    results = await self._run_strategy_ranking(
                        ranker,
                        data=frame,
                        symbol=symbol,
                        timeframe=candidate_timeframe,
                        strategy_names=strategy_names,
                    )
                    records = results.to_dict("records") if results is not None and not getattr(results, "empty", True) else []
                    for record in records:
                        if isinstance(record, dict):
                            record["timeframe"] = str(record.get("timeframe") or candidate_timeframe).strip() or candidate_timeframe
                    records = self._apply_strategy_market_context_bias(records, symbol)
                    if records:
                        combined_records.extend(records)
                        resolved_timeframes.append(candidate_timeframe)

                records = self._best_strategy_rankings_across_timeframes(combined_records)
                if not records:
                    if not any(item.get("symbol") == symbol for item in failed_symbols):
                        failed_symbols.append(
                            {
                                "symbol": symbol,
                                "reason": f"No ranked strategies were produced for {symbol} across the scanned timeframes.",
                            }
                        )
                    continue

                locked = self.symbol_strategy_assignment_locked(symbol)
                if force or not locked:
                    assigned = self.assign_ranked_strategies_to_symbol(
                        symbol,
                        records,
                        top_n=1,
                        timeframe=timeframe_value,
                        assignment_source="auto",
                        lock_symbol=False,
                        refresh_preferences=False,
                    )
                    if assigned:
                        assigned_symbols.append(symbol)
                        refreshed_preferences = True
                else:
                    self.save_ranked_strategies_for_symbol(
                        symbol,
                        records,
                        timeframe=timeframe_value,
                        assignment_source="auto",
                        persist=True,
                    )
                    skipped_symbols.append(symbol)

                best_label = "no ranked strategy"
                if records:
                    best_row = records[0]
                    best_label = f"{best_row.get('strategy_name', 'Strategy')} @ {best_row.get('timeframe', timeframe_value)}"
                self._update_strategy_auto_assignment_progress(
                    completed=index,
                    total=len(symbol_candidates),
                    current_symbol=symbol,
                    timeframe=str(records[0].get("timeframe") or timeframe_value) if records else timeframe_value,
                    message=f"Scanned {index}/{len(symbol_candidates)} symbols. Best fit for {symbol}: {best_label}.",
                    failed_symbols=failed_symbols,
                    scan_timeframes=list(timeframe_candidates),
                    resolved_timeframes=list(resolved_timeframes),
                )

            if refreshed_preferences:
                trading_system = getattr(self, "trading_system", None)
                if trading_system is not None and hasattr(trading_system, "refresh_strategy_preferences"):
                    try:
                        trading_system.refresh_strategy_preferences()
                    except Exception:
                        pass

            self.strategy_auto_assignment_in_progress = False
            self.strategy_auto_assignment_ready = True
            summary_message = (
                f"Automatic strategy assignment completed: {len(assigned_symbols)} symbols assigned, "
                f"{len(restored_symbols)} saved symbols restored, "
                f"{len(skipped_symbols)} manual overrides preserved, {len(failed_symbols)} symbols skipped."
            )
            self._update_strategy_auto_assignment_progress(
                completed=len(symbol_candidates),
                total=len(symbol_candidates),
                current_symbol="",
                timeframe=timeframe_value,
                message=summary_message,
                failed_symbols=failed_symbols,
                scan_timeframes=list(timeframe_candidates),
            )
            if system_console is not None:
                system_console.log(summary_message, "INFO")
            return {
                "assigned_symbols": list(assigned_symbols),
                "restored_symbols": list(restored_symbols),
                "skipped_symbols": list(skipped_symbols),
                "failed_symbols": list(failed_symbols),
                "timeframe": timeframe_value,
                "scan_timeframes": list(timeframe_candidates),
            }
        except asyncio.CancelledError:
            self.strategy_auto_assignment_in_progress = False
            self.strategy_auto_assignment_ready = False
            self._update_strategy_auto_assignment_progress(
                completed=int((getattr(self, "strategy_auto_assignment_progress", {}) or {}).get("completed", 0) or 0),
                total=len(symbol_candidates),
                current_symbol="",
                timeframe=timeframe_value,
                message="Automatic strategy assignment was cancelled.",
                failed_symbols=failed_symbols,
            )
            raise
        except Exception as exc:
            self.strategy_auto_assignment_in_progress = False
            self.strategy_auto_assignment_ready = False
            failure_message = f"Automatic strategy assignment failed: {exc}"
            self._update_strategy_auto_assignment_progress(
                completed=int((getattr(self, "strategy_auto_assignment_progress", {}) or {}).get("completed", 0) or 0),
                total=len(symbol_candidates),
                current_symbol="",
                timeframe=timeframe_value,
                message=failure_message,
                failed_symbols=failed_symbols,
            )
            if system_console is not None:
                system_console.log(failure_message, "ERROR")
            raise

    def ranked_strategies_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        return list(self.symbol_strategy_rankings.get(normalized_symbol, []) or [])

    def raw_assigned_strategies_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        return list(self.symbol_strategy_assignments.get(normalized_symbol, []) or [])

    def strategy_assignment_state_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        explicit_rows = self.raw_assigned_strategies_for_symbol(normalized_symbol)
        active_rows = self.assigned_strategies_for_symbol(normalized_symbol)
        ranked_rows = self.ranked_strategies_for_symbol(normalized_symbol)
        if explicit_rows:
            mode = str(explicit_rows[0].get("assignment_mode") or "").strip().lower()
            if mode not in {"single", "ranked"}:
                mode = "ranked" if len(explicit_rows) > 1 else "single"
        else:
            mode = "default"
        return {
            "symbol": normalized_symbol,
            "mode": mode,
            "explicit_rows": explicit_rows,
            "active_rows": active_rows,
            "ranked_rows": ranked_rows,
            "locked": self.symbol_strategy_assignment_locked(normalized_symbol),
        }

    def assigned_strategies_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        assigned = list(self.symbol_strategy_assignments.get(normalized_symbol, []) or [])
        if assigned:
            if self.multi_strategy_enabled or len(assigned) <= 1:
                return assigned
            primary = dict(assigned[0])
            primary["weight"] = 1.0
            primary["rank"] = 1
            return [primary]
        fallback_name = Strategy.normalize_strategy_name(getattr(self, "strategy_name", "Trend Following"))
        return [
            {
                "strategy_name": fallback_name,
                "score": 1.0,
                "weight": 1.0,
                "symbol": normalized_symbol,
                "timeframe": str(getattr(self, "time_frame", "") or "").strip(),
                "rank": 1,
            }
        ]

    def adaptive_strategy_profiles_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if not normalized_symbol:
            return []

        state = self.strategy_assignment_state_for_symbol(normalized_symbol)
        active_rows = list(state.get("active_rows", []) or [])
        ranked_rows = list(state.get("ranked_rows", []) or [])
        source_rows = list(active_rows) + list(ranked_rows)
        if not source_rows:
            source_rows = list(self.assigned_strategies_for_symbol(normalized_symbol) or [])

        active_keys = {
            (
                str(row.get("strategy_name") or "").strip(),
                str(row.get("timeframe") or "").strip(),
            )
            for row in active_rows
            if isinstance(row, dict)
        }
        ranked_keys = {
            (
                str(row.get("strategy_name") or "").strip(),
                str(row.get("timeframe") or "").strip(),
            )
            for row in ranked_rows
            if isinstance(row, dict)
        }

        trading_system = getattr(self, "trading_system", None)
        profile_resolver = getattr(trading_system, "adaptive_profile_for_strategy", None) if trading_system is not None else None
        seen = set()
        profiles = []
        for row in list(source_rows or []):
            if not isinstance(row, dict):
                continue
            strategy_name = str(row.get("strategy_name") or "").strip()
            timeframe = str(row.get("timeframe") or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
            if not strategy_name:
                continue
            fingerprint = (strategy_name, timeframe)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            profile = dict(
                profile_resolver(normalized_symbol, strategy_name, timeframe=timeframe) or {}
            ) if callable(profile_resolver) else {}
            mode = "candidate"
            if fingerprint in active_keys and fingerprint in ranked_keys:
                mode = "active + ranked"
            elif fingerprint in active_keys:
                mode = "active"
            elif fingerprint in ranked_keys:
                mode = "ranked"

            profiles.append(
                {
                    "symbol": normalized_symbol,
                    "strategy_name": strategy_name,
                    "timeframe": timeframe,
                    "mode": mode,
                    "adaptive_weight": float(profile.get("adaptive_weight", 1.0) or 1.0),
                    "sample_size": int(profile.get("sample_size", 0) or 0),
                    "win_rate": profile.get("win_rate"),
                    "average_pnl": profile.get("average_pnl"),
                    "scope": str(profile.get("scope") or "none").strip() or "none",
                    "assignment_score": float(row.get("score", 0.0) or 0.0),
                    "assignment_weight": float(row.get("weight", 0.0) or 0.0),
                }
            )

        profiles.sort(
            key=lambda row: (
                float(row.get("adaptive_weight", 1.0) or 1.0),
                int(row.get("sample_size", 0) or 0),
                float(row.get("assignment_score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return profiles

    def adaptive_strategy_detail_for_symbol(self, symbol, strategy_name, timeframe=None, limit=8):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        normalized_strategy = str(strategy_name or "").strip()
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        if not normalized_symbol or not normalized_strategy:
            return {}

        trading_system = getattr(self, "trading_system", None)
        resolver = getattr(trading_system, "adaptive_trade_samples_for_strategy", None) if trading_system is not None else None
        if not callable(resolver):
            return {}

        try:
            return dict(
                resolver(
                    normalized_symbol,
                    normalized_strategy,
                    timeframe=timeframe_value,
                    limit=limit,
                )
                or {}
            )
        except Exception:
            self.logger.debug(
                "Unable to load adaptive strategy detail for %s / %s",
                normalized_symbol,
                normalized_strategy,
                exc_info=True,
            )
            return {}

    def adaptive_strategy_timeline_for_symbol(self, symbol, strategy_name, timeframe=None, limit=16):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        normalized_strategy = str(strategy_name or "").strip()
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        if not normalized_symbol or not normalized_strategy:
            return {}

        trading_system = getattr(self, "trading_system", None)
        resolver = getattr(trading_system, "adaptive_weight_timeline_for_strategy", None) if trading_system is not None else None
        if not callable(resolver):
            return {}

        try:
            return dict(
                resolver(
                    normalized_symbol,
                    normalized_strategy,
                    timeframe=timeframe_value,
                    limit=limit,
                )
                or {}
            )
        except Exception:
            self.logger.debug(
                "Unable to load adaptive strategy timeline for %s / %s",
                normalized_symbol,
                normalized_strategy,
                exc_info=True,
            )
            return {}

    def _strategy_feedback_rows(self, limit=150):
        requested_limit = max(20, int(limit or 150))
        exchange_code = self._active_exchange_code() if hasattr(self, "_active_exchange_code") else None
        cache = dict(getattr(self, "_strategy_feedback_cache", {}) or {})
        now = time.monotonic()
        if (
                cache
                and now < float(cache.get("expires_at", 0.0) or 0.0)
                and int(cache.get("limit", 0) or 0) >= requested_limit
                and str(cache.get("exchange") or "").strip().lower() == str(exchange_code or "").strip().lower()
        ):
            return list(cache.get("rows") or [])

        repository = getattr(self, "trade_repository", None)
        if repository is None or not hasattr(repository, "get_trades"):
            return []

        try:
            trades = list(repository.get_trades(limit=requested_limit, exchange=exchange_code) or [])
        except TypeError:
            try:
                trades = list(repository.get_trades(limit=requested_limit) or [])
            except Exception:
                self.logger.debug("Unable to load trade feedback rows", exc_info=True)
                return []
            if exchange_code:
                trades = [
                    trade
                    for trade in trades
                    if self._trade_row_exchange_value(trade) == str(exchange_code or "").strip().lower()
                ]
        except Exception:
            self.logger.debug("Unable to load trade feedback rows", exc_info=True)
            return []

        tracker = getattr(self, "feedback_experiment_tracker", None)
        if tracker is not None and hasattr(tracker, "records"):
            tracker.records = []

        def _numeric(value):
            if value in (None, "", "-"):
                return None
            try:
                numeric = float(value)
            except Exception:
                return None
            if not math.isfinite(numeric):
                return None
            return numeric

        grouped = {}
        for trade in list(trades or []):
            strategy_name = str(getattr(trade, "strategy_name", "") or "").strip()
            symbol_text = str(getattr(trade, "symbol", "") or "").strip()
            if not strategy_name or not symbol_text:
                continue

            pnl = _numeric(getattr(trade, "pnl", None))
            status = str(getattr(trade, "status", "") or "").strip().lower()
            outcome = str(
                derive_trade_outcome(
                    outcome=getattr(trade, "outcome", None),
                    pnl=pnl,
                    status=status,
                )
                or ""
            ).strip().lower()
            closed_like = (
                    pnl is not None
                    or outcome in {"win", "loss", "flat"}
                    or status in {"filled", "closed"}
            )
            if not closed_like:
                continue

            normalized_symbol = self._normalize_strategy_symbol_key(symbol_text)
            timeframe_value = str(
                getattr(trade, "timeframe", "") or getattr(self, "time_frame", "1h") or "1h"
            ).strip() or "1h"
            fingerprint = (strategy_name, normalized_symbol, timeframe_value)
            bucket = grouped.setdefault(
                fingerprint,
                {
                    "strategy_name": strategy_name,
                    "symbol": normalized_symbol,
                    "timeframe": timeframe_value,
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "flats": 0,
                    "net_pnl": 0.0,
                    "fees": 0.0,
                    "fee_count": 0,
                    "journaled": 0,
                    "adaptive_weight_sum": 0.0,
                    "adaptive_weight_count": 0,
                    "adaptive_score_sum": 0.0,
                    "adaptive_score_count": 0,
                    "last_trade_at": None,
                },
            )

            bucket["trades"] += 1
            if outcome == "win" or (pnl is not None and pnl > 0):
                bucket["wins"] += 1
            elif outcome == "loss" or (pnl is not None and pnl < 0):
                bucket["losses"] += 1
            else:
                bucket["flats"] += 1

            if pnl is not None:
                bucket["net_pnl"] += pnl
            fee = _numeric(getattr(trade, "fee", None))
            if fee is not None:
                bucket["fees"] += fee
                bucket["fee_count"] += 1

            if any(
                    str(getattr(trade, field, "") or "").strip()
                    for field in ("reason", "setup", "outcome", "lessons")
            ):
                bucket["journaled"] += 1

            adaptive_weight = _numeric(getattr(trade, "adaptive_weight", None))
            if adaptive_weight is not None:
                bucket["adaptive_weight_sum"] += adaptive_weight
                bucket["adaptive_weight_count"] += 1
            adaptive_score = _numeric(getattr(trade, "adaptive_score", None))
            if adaptive_score is not None:
                bucket["adaptive_score_sum"] += adaptive_score
                bucket["adaptive_score_count"] += 1

            timestamp_value = getattr(trade, "timestamp", None)
            if timestamp_value is not None and bucket.get("last_trade_at") is None:
                bucket["last_trade_at"] = timestamp_value

        rows = []
        for bucket in grouped.values():
            trade_count = int(bucket.get("trades", 0) or 0)
            if trade_count <= 0:
                continue

            wins = int(bucket.get("wins", 0) or 0)
            losses = int(bucket.get("losses", 0) or 0)
            net_pnl = float(bucket.get("net_pnl", 0.0) or 0.0)
            avg_pnl = net_pnl / float(trade_count)
            journal_rate = float(bucket.get("journaled", 0) or 0) / float(trade_count)
            win_rate = float(wins) / float(trade_count)
            average_fee = None
            if int(bucket.get("fee_count", 0) or 0) > 0:
                average_fee = float(bucket.get("fees", 0.0) or 0.0) / float(int(bucket.get("fee_count", 0) or 1))
            average_adaptive_weight = None
            if int(bucket.get("adaptive_weight_count", 0) or 0) > 0:
                average_adaptive_weight = (
                        float(bucket.get("adaptive_weight_sum", 0.0) or 0.0)
                        / float(int(bucket.get("adaptive_weight_count", 0) or 1))
                )
            average_adaptive_score = None
            if int(bucket.get("adaptive_score_count", 0) or 0) > 0:
                average_adaptive_score = (
                        float(bucket.get("adaptive_score_sum", 0.0) or 0.0)
                        / float(int(bucket.get("adaptive_score_count", 0) or 1))
                )

            feedback_bias = 0.0
            if trade_count >= 3:
                feedback_bias += max(-0.20, min(0.20, (win_rate - 0.5) * 0.8))
                if net_pnl > 0:
                    feedback_bias += 0.08
                elif net_pnl < 0:
                    feedback_bias -= 0.08
                if journal_rate >= 0.60:
                    feedback_bias += 0.03
                elif journal_rate < 0.25:
                    feedback_bias -= 0.03
            feedback_multiplier = max(0.75, min(1.25, 1.0 + feedback_bias))

            improving = trade_count >= 3 and feedback_multiplier >= 1.08 and net_pnl >= 0.0
            degrading = trade_count >= 3 and feedback_multiplier <= 0.92 and net_pnl <= 0.0
            note_bits = []
            if improving:
                note_bits.append("Recent live trades support this setup.")
            elif degrading:
                note_bits.append("Recent live trades suggest trimming exposure.")
            else:
                note_bits.append("Live feedback is still maturing.")
            if journal_rate < 0.35:
                note_bits.append("Journal coverage is thin.")
            if average_adaptive_weight is not None:
                note_bits.append(f"Adaptive avg {average_adaptive_weight:.2f}.")

            row = {
                "strategy_name": str(bucket.get("strategy_name") or "").strip(),
                "symbol": str(bucket.get("symbol") or "").strip(),
                "timeframe": str(bucket.get("timeframe") or "1h").strip() or "1h",
                "trades": trade_count,
                "wins": wins,
                "losses": losses,
                "flats": int(bucket.get("flats", 0) or 0),
                "win_rate": win_rate,
                "net_pnl": net_pnl,
                "avg_pnl": avg_pnl,
                "journal_rate": journal_rate,
                "feedback_multiplier": feedback_multiplier,
                "degrading": degrading,
                "improving": improving,
                "average_fee": average_fee,
                "average_adaptive_weight": average_adaptive_weight,
                "average_adaptive_score": average_adaptive_score,
                "last_trade_at": bucket.get("last_trade_at"),
                "note": " ".join(bit for bit in note_bits if bit),
            }
            rows.append(row)

            if tracker is not None and hasattr(tracker, "add_record"):
                tracker.add_record(
                    name=f"{row['strategy_name']} live feedback",
                    strategy_name=row["strategy_name"],
                    symbol=row["symbol"],
                    timeframe=row["timeframe"],
                    parameters={"source": "trade_feedback", "exchange": str(exchange_code or "")},
                    dataset_metadata={"scope": "live_recent_trades"},
                    metrics={
                        "trades": row["trades"],
                        "wins": row["wins"],
                        "losses": row["losses"],
                        "flats": row["flats"],
                        "win_rate": row["win_rate"],
                        "net_pnl": row["net_pnl"],
                        "avg_pnl": row["avg_pnl"],
                        "journal_rate": row["journal_rate"],
                        "feedback_multiplier": row["feedback_multiplier"],
                        "average_fee": row["average_fee"],
                        "average_adaptive_weight": row["average_adaptive_weight"],
                        "average_adaptive_score": row["average_adaptive_score"],
                    },
                    notes=row["note"],
                )

        rows.sort(
            key=lambda item: (
                float(item.get("feedback_multiplier", 1.0) or 1.0),
                int(item.get("trades", 0) or 0),
                float(item.get("net_pnl", 0.0) or 0.0),
            ),
            reverse=True,
        )

        tracker_frame = pd.DataFrame()
        if tracker is not None and hasattr(tracker, "to_frame"):
            try:
                tracker_frame = tracker.to_frame()
            except Exception:
                tracker_frame = pd.DataFrame()

        self._strategy_feedback_cache = {
            "exchange": exchange_code,
            "limit": requested_limit,
            "expires_at": now + 15.0,
            "rows": list(rows),
            "tracker_frame": tracker_frame,
        }
        return list(rows)

    def strategy_feedback_summary(self, limit=150):
        rows = list(self._strategy_feedback_rows(limit=limit) or [])
        cache = dict(getattr(self, "_strategy_feedback_cache", {}) or {})
        tracker_frame = cache.get("tracker_frame")
        if tracker_frame is None:
            tracker_frame = pd.DataFrame()

        if not rows:
            return {
                "summary": "No closed trades are available yet for live strategy feedback.",
                "rows": [],
                "overview_rows": [],
                "improving": [],
                "degrading": [],
                "tracker_frame": tracker_frame,
            }

        overview_map = {}
        for row in rows:
            key = (
                str(row.get("strategy_name") or "").strip(),
                str(row.get("timeframe") or "1h").strip() or "1h",
            )
            bucket = overview_map.setdefault(
                key,
                {
                    "strategy_name": key[0],
                    "timeframe": key[1],
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "flats": 0,
                    "net_pnl": 0.0,
                    "weighted_feedback_sum": 0.0,
                    "journaled_weight_sum": 0.0,
                },
            )
            trades = int(row.get("trades", 0) or 0)
            bucket["trades"] += trades
            bucket["wins"] += int(row.get("wins", 0) or 0)
            bucket["losses"] += int(row.get("losses", 0) or 0)
            bucket["flats"] += int(row.get("flats", 0) or 0)
            bucket["net_pnl"] += float(row.get("net_pnl", 0.0) or 0.0)
            bucket["weighted_feedback_sum"] += float(row.get("feedback_multiplier", 1.0) or 1.0) * float(trades)
            bucket["journaled_weight_sum"] += float(row.get("journal_rate", 0.0) or 0.0) * float(trades)

        overview_rows = []
        for bucket in overview_map.values():
            trades = int(bucket.get("trades", 0) or 0)
            if trades <= 0:
                continue
            overview_rows.append(
                {
                    "strategy_name": bucket["strategy_name"],
                    "timeframe": bucket["timeframe"],
                    "trades": trades,
                    "win_rate": float(bucket.get("wins", 0) or 0) / float(trades),
                    "net_pnl": float(bucket.get("net_pnl", 0.0) or 0.0),
                    "feedback_multiplier": float(bucket.get("weighted_feedback_sum", 0.0) or 0.0) / float(trades),
                    "journal_rate": float(bucket.get("journaled_weight_sum", 0.0) or 0.0) / float(trades),
                }
            )

        overview_rows.sort(
            key=lambda item: (
                float(item.get("feedback_multiplier", 1.0) or 1.0),
                float(item.get("net_pnl", 0.0) or 0.0),
                int(item.get("trades", 0) or 0),
            ),
            reverse=True,
        )

        improving = [
            dict(item)
            for item in rows
            if bool(item.get("improving"))
        ][:5]
        degrading = [
            dict(item)
            for item in sorted(
                rows,
                key=lambda item: (
                    float(item.get("feedback_multiplier", 1.0) or 1.0),
                    float(item.get("net_pnl", 0.0) or 0.0),
                ),
            )
            if bool(item.get("degrading"))
        ][:5]

        total_trades = sum(int(item.get("trades", 0) or 0) for item in rows)
        leader = overview_rows[0] if overview_rows else None
        watch_item = degrading[0] if degrading else None
        summary_bits = [f"{len(rows)} live strategy profile(s) from {total_trades} recent trade(s)."]
        if leader is not None:
            summary_bits.append(
                f"Leader: {leader['strategy_name']} {leader['timeframe']} at {leader['feedback_multiplier']:.2f}x."
            )
        if watch_item is not None:
            summary_bits.append(
                f"Watchlist: {watch_item['strategy_name']} {watch_item['timeframe']} on {watch_item['symbol']}."
            )

        return {
            "summary": " ".join(summary_bits),
            "rows": rows,
            "overview_rows": overview_rows,
            "improving": improving,
            "degrading": degrading,
            "tracker_frame": tracker_frame,
        }

    def strategy_portfolio_profile_for_symbol(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        if not normalized_symbol:
            return []

        base_rows = list(self.assigned_strategies_for_symbol(normalized_symbol) or [])
        if not base_rows:
            return []

        adaptive_rows = list(self.adaptive_strategy_profiles_for_symbol(normalized_symbol) or [])
        adaptive_map = {
            (
                str(row.get("strategy_name") or "").strip(),
                str(row.get("timeframe") or "1h").strip() or "1h",
            ): dict(row)
            for row in adaptive_rows
            if isinstance(row, dict)
        }

        feedback_rows = list(self._strategy_feedback_rows(limit=200) or [])
        feedback_exact = {}
        feedback_rollup = {}
        for row in feedback_rows:
            key = (
                str(row.get("strategy_name") or "").strip(),
                str(row.get("timeframe") or "1h").strip() or "1h",
            )
            if str(row.get("symbol") or "").strip() == normalized_symbol:
                current = feedback_exact.get(key)
                if current is None or int(row.get("trades", 0) or 0) > int(current.get("trades", 0) or 0):
                    feedback_exact[key] = dict(row)

            bucket = feedback_rollup.setdefault(
                key,
                {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "net_pnl": 0.0,
                    "weighted_feedback_sum": 0.0,
                    "journaled_weight_sum": 0.0,
                },
            )
            trades = int(row.get("trades", 0) or 0)
            bucket["trades"] += trades
            bucket["wins"] += int(row.get("wins", 0) or 0)
            bucket["losses"] += int(row.get("losses", 0) or 0)
            bucket["net_pnl"] += float(row.get("net_pnl", 0.0) or 0.0)
            bucket["weighted_feedback_sum"] += float(row.get("feedback_multiplier", 1.0) or 1.0) * float(trades)
            bucket["journaled_weight_sum"] += float(row.get("journal_rate", 0.0) or 0.0) * float(trades)

        finalized_rollup = {}
        for key, bucket in feedback_rollup.items():
            trades = int(bucket.get("trades", 0) or 0)
            if trades <= 0:
                continue
            win_rate = float(bucket.get("wins", 0) or 0) / float(trades)
            feedback_multiplier = float(bucket.get("weighted_feedback_sum", 0.0) or 0.0) / float(trades)
            finalized_rollup[key] = {
                "strategy_name": key[0],
                "timeframe": key[1],
                "trades": trades,
                "win_rate": win_rate,
                "net_pnl": float(bucket.get("net_pnl", 0.0) or 0.0),
                "feedback_multiplier": feedback_multiplier,
                "journal_rate": float(bucket.get("journaled_weight_sum", 0.0) or 0.0) / float(trades),
                "improving": trades >= 3 and feedback_multiplier >= 1.08 and float(bucket.get("net_pnl", 0.0) or 0.0) >= 0.0,
                "degrading": trades >= 3 and feedback_multiplier <= 0.92 and float(bucket.get("net_pnl", 0.0) or 0.0) <= 0.0,
            }

        managed_rows = []
        for base_row in base_rows:
            strategy_name = str(base_row.get("strategy_name") or "").strip()
            timeframe_value = str(base_row.get("timeframe") or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
            key = (strategy_name, timeframe_value)
            adaptive_profile = dict(adaptive_map.get(key) or {})
            feedback_profile = dict(feedback_exact.get(key) or finalized_rollup.get(key) or {})

            base_weight = max(0.0001, float(base_row.get("weight", 0.0) or 0.0))
            base_score = float(base_row.get("score", 0.0) or 0.0)
            adaptive_weight = max(0.50, min(1.60, float(adaptive_profile.get("adaptive_weight", 1.0) or 1.0)))
            feedback_multiplier = max(0.75, min(1.25, float(feedback_profile.get("feedback_multiplier", 1.0) or 1.0)))
            managed_weight_raw = base_weight * adaptive_weight * feedback_multiplier
            managed_score = base_score * adaptive_weight * feedback_multiplier

            reason_bits = [f"base {base_weight:.2f}"]
            if adaptive_profile:
                reason_bits.append(f"adaptive {adaptive_weight:.2f}")
            if feedback_profile:
                reason_bits.append(
                    f"live {feedback_multiplier:.2f} from {int(feedback_profile.get('trades', 0) or 0)} trade(s)"
                )
                if feedback_profile.get("degrading"):
                    reason_bits.append("trimmed by recent live results")
                elif feedback_profile.get("improving"):
                    reason_bits.append("boosted by recent live results")
            else:
                reason_bits.append("no live trade feedback yet")

            managed_row = dict(base_row)
            managed_row.update(
                {
                    "symbol": normalized_symbol,
                    "timeframe": timeframe_value,
                    "base_weight": base_weight,
                    "base_score": base_score,
                    "score": managed_score,
                    "adaptive_weight": adaptive_weight,
                    "feedback_multiplier": feedback_multiplier,
                    "feedback_trades": int(feedback_profile.get("trades", 0) or 0),
                    "feedback_win_rate": feedback_profile.get("win_rate"),
                    "feedback_net_pnl": feedback_profile.get("net_pnl"),
                    "feedback_journal_rate": feedback_profile.get("journal_rate"),
                    "feedback_scope": "symbol" if key in feedback_exact else ("global" if feedback_profile else "none"),
                    "management_reason": " | ".join(bit for bit in reason_bits if bit),
                    "managed_weight_raw": managed_weight_raw,
                    "portfolio_weight": 0.0,
                }
            )
            managed_rows.append(managed_row)

        managed_rows.sort(
            key=lambda item: (
                float(item.get("managed_weight_raw", 0.0) or 0.0),
                float(item.get("score", 0.0) or 0.0),
            ),
            reverse=True,
        )

        total_weight = sum(float(item.get("managed_weight_raw", 0.0) or 0.0) for item in managed_rows)
        if total_weight <= 0.0:
            total_weight = float(len(managed_rows) or 1)

        for index, row in enumerate(managed_rows, start=1):
            portfolio_weight = float(row.get("managed_weight_raw", 0.0) or 0.0) / float(total_weight)
            row["weight"] = portfolio_weight
            row["portfolio_weight"] = portfolio_weight
            row["rank"] = index
        return managed_rows

    def clear_symbol_strategy_assignment(self, symbol):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        removed = list(self.symbol_strategy_assignments.pop(normalized_symbol, []) or [])
        self._mark_symbol_strategy_assignment_locked(normalized_symbol, True)
        self._persist_strategy_symbol_state()

        trading_system = getattr(self, "trading_system", None)
        if trading_system is not None and hasattr(trading_system, "refresh_strategy_preferences"):
            try:
                trading_system.refresh_strategy_preferences()
            except Exception:
                pass
        return removed

    def assign_strategy_to_symbol(self, symbol, strategy_name, timeframe=None):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        normalized_strategy = Strategy.normalize_strategy_name(strategy_name)
        if not normalized_symbol:
            raise ValueError("Select a symbol before assigning a strategy.")
        if not normalized_strategy:
            raise ValueError("Select a valid strategy before assigning it to a symbol.")

        self.multi_strategy_enabled = True
        assigned = [
            {
                "strategy_name": normalized_strategy,
                "score": 1.0,
                "weight": 1.0,
                "symbol": normalized_symbol,
                "timeframe": str(timeframe or self.time_frame or "").strip(),
                "assignment_mode": "single",
                "assignment_source": "manual",
                "rank": 1,
                "total_profit": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "final_equity": 0.0,
                "max_drawdown": 0.0,
                "closed_trades": 0,
            }
        ]
        self.symbol_strategy_assignments[normalized_symbol] = assigned
        self._mark_symbol_strategy_assignment_locked(normalized_symbol, True)
        self._persist_strategy_symbol_state()

        trading_system = getattr(self, "trading_system", None)
        if trading_system is not None and hasattr(trading_system, "refresh_strategy_preferences"):
            try:
                trading_system.refresh_strategy_preferences()
            except Exception:
                pass
        return list(assigned)

    def active_strategy_weight_map(self):
        if not self.multi_strategy_enabled:
            return {Strategy.normalize_strategy_name(getattr(self, "strategy_name", "Trend Following")): 1.0}

        totals = {}
        for rows in (self.symbol_strategy_assignments or {}).values():
            for row in list(rows or []):
                if not isinstance(row, dict):
                    continue
                strategy_name = Strategy.normalize_strategy_name(row.get("strategy_name"))
                if not strategy_name:
                    continue
                base_weight = max(0.0001, float(row.get("weight", 0.0) or 0.0))
                totals[strategy_name] = totals.get(strategy_name, 0.0) + (
                        base_weight * self._server_feedback_multiplier(strategy_name)
                )
        if not totals:
            return {Strategy.normalize_strategy_name(getattr(self, "strategy_name", "Trend Following")): 1.0}
        total_weight = sum(totals.values())
        if total_weight <= 0:
            return {name: 1.0 / len(totals) for name in totals}
        return {name: value / total_weight for name, value in totals.items()}

    def broker_supports_hedging(self, broker=None):
        broker = broker or getattr(self, "broker", None)
        if broker is None:
            return False
        resolver = getattr(broker, "supports_hedging", None)
        if callable(resolver):
            try:
                return bool(resolver())
            except Exception:
                return False
        advertised = getattr(broker, "hedging_supported", None)
        if advertised is not None:
            return bool(advertised)
        exchange_name = str(
            getattr(broker, "exchange_name", None)
            or getattr(getattr(broker, "config", None), "exchange", None)
            or ""
        ).strip().lower()
        return exchange_name in {"oanda"}

    def hedging_is_active(self, broker=None):
        return bool(getattr(self, "hedging_enabled", True)) and self.broker_supports_hedging(broker)

    def assign_ranked_strategies_to_symbol(
            self,
            symbol,
            rankings,
            top_n=None,
            timeframe=None,
            assignment_source="manual",
            lock_symbol=None,
            refresh_preferences=True,
    ):
        normalized_symbol = self._normalize_strategy_symbol_key(symbol)
        limit = max(1, int(top_n or self.max_symbol_strategies or 1))
        self.max_symbol_strategies = limit
        assignment_source = str(assignment_source or "manual").strip().lower()
        if assignment_source not in {"manual", "auto"}:
            assignment_source = "manual"
        if lock_symbol is None:
            lock_symbol = assignment_source != "auto"

        cleaned_rows = self.save_ranked_strategies_for_symbol(
            normalized_symbol,
            rankings,
            timeframe=timeframe,
            assignment_source=assignment_source,
            persist=False,
        )
        top_rows = cleaned_rows[:limit]
        if not top_rows:
            self.symbol_strategy_assignments.pop(normalized_symbol, None)
            self._mark_symbol_strategy_assignment_locked(normalized_symbol, bool(lock_symbol))
            self._persist_strategy_symbol_state()
            return []

        self.multi_strategy_enabled = True
        weight_seed = [max(0.0001, float(item.get("score", 0.0) or 0.0)) for item in top_rows]
        total_weight = sum(weight_seed) or float(len(top_rows))
        assigned = []
        for index, item in enumerate(top_rows, start=1):
            assigned_item = dict(item)
            assigned_item["rank"] = index
            assigned_item["weight"] = float(weight_seed[index - 1] / total_weight)
            assigned_item["assignment_source"] = assignment_source
            assigned.append(assigned_item)
        self.symbol_strategy_assignments[normalized_symbol] = assigned
        self._mark_symbol_strategy_assignment_locked(normalized_symbol, bool(lock_symbol))
        self._persist_strategy_symbol_state()

        trading_system = getattr(self, "trading_system", None)
        if refresh_preferences and trading_system is not None and hasattr(trading_system, "refresh_strategy_preferences"):
            try:
                trading_system.refresh_strategy_preferences()
            except Exception:
                pass
        return assigned

    async def submit_market_chat_trade(
            self,
            symbol,
            side,
            amount,
            quantity_mode=None,
            order_type="market",
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
    ):
        return await self.submit_trade_with_preflight(
            symbol=symbol,
            side=side,
            amount=amount,
            quantity_mode=quantity_mode,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            source="chatgpt",
            strategy_name="Sopotek Pilot",
            reason="Sopotek Pilot trade command",
        )

    @staticmethod
    def _is_user_directed_trade_source(source):
        return str(source or "").strip().lower() == "manual"

    @staticmethod
    def _normalize_trade_side(side):
        normalized = str(side or "").strip().lower()
        return "sell" if normalized in {"sell", "short"} else "buy"

    @staticmethod
    def _position_side_from_trade_side(side):
        return "short" if AppController._normalize_trade_side(side) == "sell" else "long"

    @staticmethod
    def _opposite_trade_side(side):
        return "sell" if AppController._normalize_trade_side(side) == "buy" else "buy"

    async def _user_trade_market_context(self, symbol, *, timeframe=None, reference_price=None):
        normalized_symbol = str(symbol or "").strip().upper()
        resolved_timeframe = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        reference = self._safe_balance_metric(reference_price)
        fallback_distance = max(abs(float(reference or 0.0)) * 0.002, 1e-6) if reference not in (None, "") else 1e-6
        context = {
            "symbol": normalized_symbol,
            "timeframe": resolved_timeframe,
            "trend": "mixed",
            "preferred_side": None,
            "confidence": 0.0,
            "latest_price": float(reference) if reference not in (None, "") else None,
            "ema_fast": None,
            "ema_slow": None,
            "rsi": None,
            "support": None,
            "resistance": None,
            "atr": None,
            "risk_distance": fallback_distance,
            "reason": "No strong directional bias was available.",
        }


        try:
            tick = await self._safe_fetch_ticker(normalized_symbol)
        except Exception:
            tick = None
        try:
            candles = await self._safe_fetch_ohlcv(normalized_symbol, timeframe=resolved_timeframe, limit=120)
        except Exception:
            candles = None

        if isinstance(tick, dict):
            tick_price = self._safe_balance_metric(
                tick.get("price") or tick.get("last") or tick.get("bid") or tick.get("ask")
            )
            if tick_price is not None and tick_price > 0:
                context["latest_price"] = float(tick_price)
                context["risk_distance"] = max(abs(float(tick_price)) * 0.002, 1e-6)

        if not isinstance(candles, list) or not candles:
            if context["latest_price"] is not None and context["latest_price"] > 0:
                context["reason"] = "Technical candle history was unavailable, so the trade will use a conservative fallback risk distance."
            return context

        frame = pd.DataFrame(candles)
        if frame.shape[1] < 6:
            return context
        frame = frame.iloc[:, :6].copy()
        frame.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["high", "low", "close"])
        if frame.empty:
            return context

        closes = frame["close"]
        highs = frame["high"]
        lows = frame["low"]
        latest_close = self._safe_balance_metric(context.get("latest_price")) or float(closes.iloc[-1])
        ema_fast = float(closes.ewm(span=min(20, max(len(closes), 2)), adjust=False).mean().iloc[-1])
        ema_slow_span = 50 if len(closes) >= 50 else max(21, min(len(closes), 50))
        ema_slow = float(closes.ewm(span=ema_slow_span, adjust=False).mean().iloc[-1])
        rsi = self._market_chat_rsi(closes, period=14)
        window = min(20, len(frame))
        support = float(lows.tail(window).min())
        resistance = float(highs.tail(window).max())
        prev_close = closes.shift(1).fillna(closes)
        tr = pd.concat(
            [
                (highs - lows).abs(),
                (highs - prev_close).abs(),
                (lows - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = float(tr.tail(min(len(tr), 14)).mean()) if not tr.empty else 0.0
        risk_distance = atr * 1.5 if atr > 0 else max(abs(float(latest_close)) * 0.002, 1e-6)

        trend = "mixed"
        preferred_side = None
        if latest_close >= ema_fast >= ema_slow:
            trend = "bullish"
            preferred_side = "buy"
        elif latest_close <= ema_fast <= ema_slow:
            trend = "bearish"
            preferred_side = "sell"

        if preferred_side == "buy" and rsi is not None and float(rsi) < 52.0:
            preferred_side = None
            trend = "mixed"
        elif preferred_side == "sell" and rsi is not None and float(rsi) > 48.0:
            preferred_side = None
            trend = "mixed"

        trend_strength = min(1.0, abs(float(ema_fast) - float(ema_slow)) / max(abs(float(latest_close)), 1e-9) / 0.02)
        rsi_strength = 0.0
        if rsi is not None:
            rsi_strength = min(1.0, abs(float(rsi) - 50.0) / 20.0)
        confidence = ((trend_strength * 0.65) + (rsi_strength * 0.35)) if preferred_side else 0.0
        if preferred_side == "buy":
            reason = "EMA trend and RSI both support a bullish continuation."
        elif preferred_side == "sell":
            reason = "EMA trend and RSI both support a bearish continuation."
        else:
            reason = "EMA and RSI are mixed, so no strong directional bias is active."

        context.update(
            {
                "trend": trend,
                "preferred_side": preferred_side,
                "confidence": float(max(0.0, min(confidence, 0.99))),
                "latest_price": float(latest_close),
                "ema_fast": float(ema_fast),
                "ema_slow": float(ema_slow),
                "rsi": float(rsi) if rsi is not None else None,
                "support": float(support),
                "resistance": float(resistance),
                "atr": float(atr),
                "risk_distance": float(max(risk_distance, 1e-6)),
                "reason": reason,
            }
        )
        return context

    def _suggest_user_trade_levels(self, symbol, side, entry_price, market_context, *, reward_multiple=None):
        entry = self._safe_balance_metric(entry_price)
        if entry is None or entry <= 0:
            return None, None

        normalized_side = self._normalize_trade_side(side)
        reward_ratio = max(1.0, float(reward_multiple or getattr(self, "user_trade_min_reward_risk", 1.5) or 1.5))
        risk_distance = max(
            self._safe_balance_metric((market_context or {}).get("risk_distance")) or 0.0,
            abs(float(entry)) * 0.002,
            1e-6,
            )
        support = self._safe_balance_metric((market_context or {}).get("support"))
        resistance = self._safe_balance_metric((market_context or {}).get("resistance"))

        if normalized_side == "sell":
            stop_loss = float(entry) + risk_distance
            if resistance is not None and resistance > float(entry):
                stop_loss = max(stop_loss, resistance)
            take_profit = float(entry) - (abs(float(stop_loss) - float(entry)) * reward_ratio)
            if support is not None and support < float(entry):
                take_profit = min(take_profit, support)
        else:
            stop_loss = float(entry) - risk_distance
            if support is not None and support < float(entry):
                stop_loss = min(stop_loss, support)
            take_profit = float(entry) + (abs(float(entry) - float(stop_loss)) * reward_ratio)
            if resistance is not None and resistance > float(entry):
                take_profit = max(take_profit, resistance)
        return float(stop_loss), float(take_profit)

    async def _assess_user_trade_review(
            self,
            *,
            symbol,
            side,
            amount_units,
            reference_price,
            stop_loss=None,
            take_profit=None,
            timeframe=None,
    ):
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_side = self._normalize_trade_side(side)
        entry_price = self._safe_balance_metric(reference_price)
        if entry_price is None or entry_price <= 0:
            return {
                "is_bad": False,
                "action": "keep",
                "summary": "",
                "reasons": [],
                "replacement_side": normalized_side,
                "replacement_amount_units": float(abs(self._safe_balance_metric(amount_units) or 0.0)),
                "replacement_stop_loss": self._safe_balance_metric(stop_loss),
                "replacement_take_profit": self._safe_balance_metric(take_profit),
                "market_context": {},
                "reward_risk": None,
            }

        market_context = await self._user_trade_market_context(
            normalized_symbol,
            timeframe=timeframe,
            reference_price=entry_price,
        )
        min_reward_risk = max(1.0, float(getattr(self, "user_trade_min_reward_risk", 1.5) or 1.5))
        bias_threshold = max(
            0.5,
            min(0.95, float(getattr(self, "user_trade_bias_confidence_threshold", 0.72) or 0.72)),
        )
        structural_reasons = []
        monitor_reasons = []
        entry_value = float(entry_price)
        stop_value = self._safe_balance_metric(stop_loss)
        take_value = self._safe_balance_metric(take_profit)

        stop_valid = stop_value is not None and stop_value > 0 and (
                (normalized_side == "buy" and stop_value < entry_value)
                or (normalized_side == "sell" and stop_value > entry_value)
        )
        take_valid = take_value is not None and take_value > 0 and (
                (normalized_side == "buy" and take_value > entry_value)
                or (normalized_side == "sell" and take_value < entry_value)
        )

        suggested_stop, suggested_take = self._suggest_user_trade_levels(
            normalized_symbol,
            normalized_side,
            entry_value,
            market_context,
            reward_multiple=min_reward_risk,
        )
        replacement_side = normalized_side
        replacement_stop = float(stop_value) if stop_valid and stop_value is not None else suggested_stop
        replacement_take = float(take_value) if take_valid and take_value is not None else suggested_take
        reward_risk = None

        if stop_value is None:
            structural_reasons.append("Stop loss was missing, so the trade had no defined downside protection.")
        elif not stop_valid:
            structural_reasons.append("Stop loss was on the wrong side of entry for this direction.")

        if take_value is None:
            structural_reasons.append("Take profit was missing, so the trade had no defined exit target.")
        elif not take_valid:
            structural_reasons.append("Take profit was on the wrong side of entry for this direction.")

        if replacement_stop is not None and replacement_take is not None:
            risk_distance = abs(entry_value - float(replacement_stop))
            reward_distance = abs(float(replacement_take) - entry_value)
            if risk_distance > 1e-9:
                reward_risk = reward_distance / risk_distance
                if reward_risk + 1e-9 < min_reward_risk:
                    structural_reasons.append(
                        f"Reward-to-risk was only {reward_risk:.2f}:1, below the {min_reward_risk:.2f}:1 minimum."
                    )
                    if normalized_side == "sell":
                        replacement_take = float(entry_value - (risk_distance * min_reward_risk))
                    else:
                        replacement_take = float(entry_value + (risk_distance * min_reward_risk))
                    reward_risk = min_reward_risk

        preferred_side = str((market_context or {}).get("preferred_side") or "").strip().lower()
        bias_confidence = float((market_context or {}).get("confidence", 0.0) or 0.0)
        if preferred_side and preferred_side != normalized_side and bias_confidence >= bias_threshold:
            replacement_side = preferred_side
            replacement_stop, replacement_take = self._suggest_user_trade_levels(
                normalized_symbol,
                replacement_side,
                entry_value,
                market_context,
                reward_multiple=min_reward_risk,
            )
            structural_reasons.append(
                (
                    f"Trade direction conflicted with the live {str((market_context or {}).get('trend') or 'mixed').title()} "
                    f"bias ({bias_confidence:.0%} confidence). {str((market_context or {}).get('reason') or '').strip()}"
                ).strip()
            )

        recommended_amount_units = float(abs(self._safe_balance_metric(amount_units) or 0.0))
        risk_context = {}
        try:
            risk_context = await self._resolve_trade_risk_context(
                normalized_symbol,
                entry_value,
                dict(getattr(self, "balances", {}) or {}),
                broker=getattr(self, "broker", None),
            )
        except Exception:
            risk_context = {}
        trading_system = getattr(self, "trading_system", None)
        risk_engine = getattr(trading_system, "risk_engine", None)
        if risk_engine is not None and recommended_amount_units > 0:
            try:
                allowed, adjusted_units, risk_reason = risk_engine.adjust_trade(
                    float(entry_value),
                    recommended_amount_units,
                    symbol=normalized_symbol,
                    stop_price=replacement_stop,
                    quote_to_account_rate=risk_context.get("quote_to_account_rate", 1.0),
                    pip_size=risk_context.get("pip_size"),
                )
            except Exception:
                allowed, adjusted_units, risk_reason = True, recommended_amount_units, ""
            adjusted_units = max(0.0, float(adjusted_units or 0.0))
            if not allowed or adjusted_units <= 0:
                structural_reasons.append(
                    str(risk_reason or "Risk controls do not allow this trade at the current size.").strip()
                )
                recommended_amount_units = 0.0
            elif adjusted_units + 1e-9 < recommended_amount_units:
                monitor_reasons.append(
                    str(risk_reason or "Risk controls require a smaller position size.").strip()
                )
                recommended_amount_units = adjusted_units

        action = "keep"
        reasons = list(structural_reasons) + list(monitor_reasons)
        if structural_reasons:
            action = "reverse" if replacement_side != normalized_side else "correct"
            if recommended_amount_units <= 0:
                action = "close"
        elif monitor_reasons:
            action = "warn"

        summary = " ".join(str(reason).strip() for reason in reasons if str(reason).strip()).strip()
        return {
            "is_bad": bool(structural_reasons),
            "monitor_only": bool(monitor_reasons and not structural_reasons),
            "action": action,
            "summary": summary,
            "reasons": list(reasons),
            "structural_reasons": list(structural_reasons),
            "monitor_reasons": list(monitor_reasons),
            "replacement_side": replacement_side,
            "replacement_amount_units": float(recommended_amount_units),
            "replacement_stop_loss": self._safe_balance_metric(replacement_stop),
            "replacement_take_profit": self._safe_balance_metric(replacement_take),
            "market_context": dict(market_context or {}),
            "reward_risk": reward_risk,
        }

    async def _recommend_user_trade_monitor_action_with_openai(
            self,
            *,
            monitor,
            position,
            current_price,
            adverse_distance,
    ):
        api_key = str(getattr(self, "openai_api_key", "") or "").strip()
        if not api_key:
            return None

        payload_context = {
            "symbol": str((monitor or {}).get("symbol") or (position or {}).get("symbol") or "").strip().upper(),
            "position_side": str(
                (position or {}).get("position_side")
                or (position or {}).get("side")
                or (monitor or {}).get("position_side")
                or ""
            ).strip().lower(),
            "current_amount_units": float(abs(self._safe_balance_metric((position or {}).get("amount")) or 0.0)),
            "recommended_amount_units": float(abs(self._safe_balance_metric((monitor or {}).get("recommended_amount_units")) or 0.0)),
            "entry_price": self._safe_balance_metric((position or {}).get("entry_price") or (monitor or {}).get("entry_price")),
            "current_price": self._safe_balance_metric(current_price),
            "stop_loss": self._safe_balance_metric((monitor or {}).get("stop_loss")),
            "take_profit": self._safe_balance_metric((monitor or {}).get("take_profit")),
            "adverse_distance": float(abs(self._safe_balance_metric(adverse_distance) or 0.0)),
            "risk_distance": self._safe_balance_metric((monitor or {}).get("risk_distance")),
            "summary": str((monitor or {}).get("summary") or "").strip(),
            "market_context": dict((monitor or {}).get("market_context") or {}),
            "pnl": self._safe_balance_metric((position or {}).get("pnl")),
        }
        payload = {
            "model": self.openai_model or "gpt-5-mini",
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a conservative trade risk assistant inside Sopotek Quant System. "
                        "A manual trade is oversized and the market is moving against it. "
                        "Return only compact JSON with keys recommendation and reason. "
                        "recommendation must be one of trim, exit, or hold. "
                        "Never recommend increasing risk."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload_context, default=str),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400:
                        self.logger.debug("OpenAI risk monitor request failed: %s", data)
                        return None
        except Exception:
            self.logger.debug("OpenAI risk monitor request failed", exc_info=True)
            return None

        response_text = data.get("output_text")
        if not isinstance(response_text, str) or not response_text.strip():
            parts = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    content_text = content.get("text")
                    if isinstance(content_text, str) and content_text.strip():
                        parts.append(content_text.strip())
            response_text = "\n".join(parts)

        recommendation = self._extract_json_object(response_text)
        if not isinstance(recommendation, dict):
            plain_text = str(response_text or "").strip()
            return {"recommendation": "", "reason": plain_text} if plain_text else None

        return {
            "recommendation": str(recommendation.get("recommendation") or "").strip().lower(),
            "reason": str(recommendation.get("reason") or "").strip(),
        }

    def _notify_user_trade_review(self, title, message, *, level="WARN"):
        terminal = getattr(self, "terminal", None)
        if terminal is not None:
            console = getattr(terminal, "system_console", None)
            if console is not None and hasattr(console, "log"):
                try:
                    console.log(str(message), level)
                except Exception:
                    pass
            notifier = getattr(terminal, "_push_notification", None)
            if callable(notifier):
                try:
                    notifier(
                        title,
                        str(message),
                        level=level,
                        source="trade",
                        dedupe_seconds=2.0,
                    )
                except Exception:
                    pass
        else:
            log_method = getattr(self.logger, "warning" if str(level).upper() == "WARN" else "info", None)
            if callable(log_method):
                log_method(str(message))

    async def _queue_monitored_user_trade_position(
            self,
            *,
            order,
            review,
            timeframe=None,
    ):
        if not isinstance(order, dict) or not bool(getattr(self, "user_trade_risk_monitor_enabled", True)):
            return None

        order_symbol = str(order.get("symbol") or "").strip().upper()
        if not order_symbol:
            return None
        recommended_units = float(abs(self._safe_balance_metric(review.get("replacement_amount_units")) or 0.0))
        actual_units = float(
            abs(
                self._safe_balance_metric(order.get("amount"))
                or self._safe_balance_metric(order.get("amount_units"))
                or 0.0
            )
        )
        if actual_units <= 0 or recommended_units + 1e-9 >= actual_units:
            return None

        order_id = str(order.get("id") or order.get("order_id") or "").strip()
        original_side = self._normalize_trade_side(order.get("side"))
        entry_price = self._safe_balance_metric(
            order.get("reference_price") or order.get("price") or order.get("avg_price") or order.get("entry_price")
        )
        stop_loss = self._safe_balance_metric(review.get("replacement_stop_loss") or order.get("stop_loss"))
        risk_distance = abs(float(entry_price) - float(stop_loss)) if entry_price and stop_loss else None
        if risk_distance is None or risk_distance <= 0:
            risk_distance = self._safe_balance_metric((review.get("market_context") or {}).get("risk_distance"))
        if risk_distance is None or risk_distance <= 0:
            risk_distance = max(abs(float(entry_price or 0.0)) * 0.002, 1e-6)
        adverse_fraction = max(
            0.1,
            min(1.0, float(getattr(self, "user_trade_risk_monitor_adverse_move_fraction", 0.35) or 0.35)),
        )
        adverse_threshold = max(float(risk_distance) * adverse_fraction, abs(float(entry_price or 0.0)) * 0.0015, 1e-6)

        monitored_positions = getattr(self, "_monitored_user_trade_positions", None)
        if not isinstance(monitored_positions, dict):
            monitored_positions = {}
            self._monitored_user_trade_positions = monitored_positions

        key = order_id or f"{order_symbol}:{self._position_side_from_trade_side(original_side)}"
        payload = {
            "created_at": time.time(),
            "symbol": order_symbol,
            "position_side": self._position_side_from_trade_side(original_side),
            "original_order_id": order_id or None,
            "original_side": original_side,
            "current_amount_units": actual_units,
            "recommended_amount_units": recommended_units,
            "entry_price": self._safe_balance_metric(entry_price),
            "stop_loss": stop_loss,
            "take_profit": self._safe_balance_metric(review.get("replacement_take_profit") or order.get("take_profit")),
            "risk_distance": float(risk_distance),
            "adverse_threshold": float(adverse_threshold),
            "summary": str(review.get("summary") or "").strip(),
            "reasons": list(review.get("monitor_reasons") or review.get("reasons") or []),
            "market_context": dict(review.get("market_context") or {}),
            "timeframe": str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h",
            "warnings_sent": 0,
            "last_warning_at": 0.0,
            "ai_recommendation": "",
            "ai_reason": "",
            "ai_consulted": False,
            "last_price": self._safe_balance_metric(entry_price),
        }
        monitored_positions[key] = payload
        await self._record_trade_audit(
            "user_trade_risk_monitoring_started",
            status="monitoring",
            symbol=order_symbol,
            side=original_side,
            order_type=order.get("type") or "market",
            source=order.get("source"),
            order_id=order_id or None,
            message=str(review.get("summary") or "User trade risk monitoring started."),
            payload={"review": dict(review or {}), "order": dict(order or {}), "monitor": dict(payload)},
        )
        return payload

    async def _queue_pending_user_trade_review(
            self,
            *,
            order,
            review,
            timeframe=None,
    ):
        if not isinstance(order, dict):
            return None
        order_symbol = str(order.get("symbol") or "").strip().upper()
        if not order_symbol:
            return None
        order_id = str(order.get("id") or order.get("order_id") or "").strip()
        key = order_id or f"{order_symbol}:{time.time()}"
        original_side = self._normalize_trade_side(order.get("side"))
        pending_reviews = getattr(self, "_pending_user_trade_reviews", None)
        if not isinstance(pending_reviews, dict):
            pending_reviews = {}
            self._pending_user_trade_reviews = pending_reviews
        payload = {
            "created_at": time.time(),
            "symbol": order_symbol,
            "position_side": self._position_side_from_trade_side(original_side),
            "replacement_side": self._normalize_trade_side(review.get("replacement_side") or order.get("side")),
            "replacement_amount_units": float(
                review.get("replacement_amount_units")
                or abs(self._safe_balance_metric(order.get("amount")) or 0.0)
            ),
            "replacement_stop_loss": self._safe_balance_metric(review.get("replacement_stop_loss")),
            "replacement_take_profit": self._safe_balance_metric(review.get("replacement_take_profit")),
            "replacement_reason": str(review.get("summary") or "").strip(),
            "action": str(review.get("action") or "correct").strip().lower() or "correct",
            "timeframe": str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h",
            "attempts": 0,
            "last_attempt_at": 0.0,
            "original_order_id": order_id or None,
            "original_side": original_side,
        }
        pending_reviews[key] = payload
        await self._record_trade_audit(
            "user_trade_review_pending",
            status="pending",
            symbol=order_symbol,
            side=payload["replacement_side"],
            order_type="market",
            source=order.get("source"),
            order_id=order_id or None,
            message=str(review.get("summary") or "User trade review is waiting for the live position snapshot."),
            payload={"review": dict(review or {}), "order": dict(order or {}), "pending": dict(payload)},
        )
        return payload

    async def _close_position_for_user_trade_review(self, position, *, amount=None):
        broker = getattr(self, "broker", None)
        if broker is None:
            raise RuntimeError("Connect a broker before the trade review can close positions.")

        normalized_symbol = str((position or {}).get("symbol") or "").strip().upper()
        close_amount = abs(
            float(
                self._safe_balance_metric(amount)
                or self._safe_balance_metric((position or {}).get("amount"))
                or 0.0
            )
        )
        if not normalized_symbol or close_amount <= 0:
            raise RuntimeError("Trade review could not resolve a valid live position to close.")

        position_side = str((position or {}).get("position_side") or (position or {}).get("side") or "").strip().lower()
        position_id = str((position or {}).get("position_id") or (position or {}).get("id") or "").strip() or None
        result = None
        if hasattr(broker, "close_position"):
            try:
                result = await broker.close_position(
                    normalized_symbol,
                    amount=close_amount,
                    order_type="market",
                    position=position,
                    position_side=position_side or None,
                    position_id=position_id,
                )
            except TypeError:
                result = await broker.close_position(normalized_symbol, amount=close_amount)
        if result is None:
            close_side = "buy" if position_side in {"short", "sell"} else "sell"
            result = await broker.create_order(
                symbol=normalized_symbol,
                side=close_side,
                amount=close_amount,
                type="market",
                params={"positionFill": "REDUCE_ONLY"} if self.hedging_is_active(broker) else None,
            )
        if result is None:
            raise RuntimeError(f"Trade review failed to close the live {normalized_symbol} position.")
        return result

    async def _process_pending_user_trade_position_reviews(self, positions):
        pending = dict(getattr(self, "_pending_user_trade_reviews", {}) or {})
        if not pending:
            return

        normalized_positions = []
        for item in list(positions or []):
            if isinstance(item, dict):
                normalized_positions.append(dict(item))

        now = time.time()
        for key, payload in list(pending.items()):
            created_at = float(payload.get("created_at", now) or now)
            if (now - created_at) > 180.0:
                self._pending_user_trade_reviews.pop(key, None)
                await self._record_trade_audit(
                    "user_trade_review_expired",
                    status="expired",
                    symbol=payload.get("symbol"),
                    side=payload.get("replacement_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=payload.get("original_order_id"),
                    message="User trade review expired before a matching live position was found.",
                    payload=dict(payload),
                )
                continue

            if (now - float(payload.get("last_attempt_at", 0.0) or 0.0)) < 5.0:
                continue

            target_symbol = str(payload.get("symbol") or "").strip().upper()
            target_side = str(payload.get("position_side") or "").strip().lower()
            match = next(
                (
                    position
                    for position in normalized_positions
                    if str(position.get("symbol") or "").strip().upper() == target_symbol
                       and (
                               not target_side
                               or str(position.get("position_side") or position.get("side") or "").strip().lower() == target_side
                       )
                ),
                None,
            )
            if match is None:
                continue

            payload["last_attempt_at"] = now
            payload["attempts"] = int(payload.get("attempts", 0) or 0) + 1

            try:
                close_result = await self._close_position_for_user_trade_review(match)
                await self._record_trade_audit(
                    "user_trade_review_close",
                    status=str((close_result or {}).get("status") or "submitted"),
                    symbol=target_symbol,
                    side=self._opposite_trade_side(payload.get("original_side")),
                    order_type="market",
                    source="manual_review",
                    order_id=(close_result or {}).get("id") if isinstance(close_result, dict) else None,
                    message=f"Trade review closed the live {target_symbol} position before replacement.",
                    payload={"position": dict(match), "pending": dict(payload)},
                )

                replacement = None
                if str(payload.get("action") or "correct").strip().lower() != "close":
                    replacement = await self.submit_trade_with_preflight(
                        symbol=target_symbol,
                        side=payload.get("replacement_side"),
                        amount=float(payload.get("replacement_amount_units") or abs(float(match.get("amount", 0.0) or 0.0))),
                        quantity_mode=None,
                        order_type="market",
                        price=None,
                        stop_price=None,
                        stop_loss=payload.get("replacement_stop_loss"),
                        take_profit=payload.get("replacement_take_profit"),
                        source="manual_review",
                        strategy_name="Manual Review",
                        reason=f"User trade auto-corrected: {payload.get('replacement_reason')}",
                        timeframe=payload.get("timeframe"),
                    )

                self._pending_user_trade_reviews.pop(key, None)
                summary = str(payload.get("replacement_reason") or "User trade review replaced the position.").strip()
                if isinstance(replacement, dict):
                    replacement["review_action"] = payload.get("action")
                    replacement["review_reason"] = summary
                    replacement["intervention_taken"] = True
                    replacement["intervention_summary"] = summary
                    replacement["review_replaced_order_id"] = payload.get("original_order_id")
                self._notify_user_trade_review("User Trade Corrected", summary, level="WARN")
            except Exception as exc:
                if int(payload.get("attempts", 0) or 0) >= 3:
                    self._pending_user_trade_reviews.pop(key, None)
                await self._record_trade_audit(
                    "user_trade_review_error",
                    status="error",
                    symbol=target_symbol,
                    side=payload.get("replacement_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=payload.get("original_order_id"),
                    message=str(exc),
                    payload={"position": dict(match), "pending": dict(payload)},
                )

    async def _process_monitored_user_trade_positions(self, positions):
        monitored = dict(getattr(self, "_monitored_user_trade_positions", {}) or {})
        if not monitored:
            return

        normalized_positions = []
        for item in list(positions or []):
            if isinstance(item, dict):
                normalized_positions.append(dict(item))

        now = time.time()
        grace_seconds = max(15.0, float(getattr(self, "user_trade_risk_monitor_grace_seconds", 60.0) or 60.0))
        for key, payload in list(monitored.items()):
            created_at = float(payload.get("created_at", now) or now)
            if (now - created_at) > 900.0:
                self._monitored_user_trade_positions.pop(key, None)
                await self._record_trade_audit(
                    "user_trade_risk_monitor_expired",
                    status="expired",
                    symbol=payload.get("symbol"),
                    side=payload.get("original_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=payload.get("original_order_id"),
                    message="Risk monitoring expired before the oversized user trade needed intervention.",
                    payload=dict(payload),
                )
                continue

            target_symbol = str(payload.get("symbol") or "").strip().upper()
            target_side = str(payload.get("position_side") or "").strip().lower()
            match = next(
                (
                    position
                    for position in normalized_positions
                    if str(position.get("symbol") or "").strip().upper() == target_symbol
                       and (
                               not target_side
                               or str(position.get("position_side") or position.get("side") or "").strip().lower() == target_side
                       )
                ),
                None,
            )
            if match is None:
                continue

            current_amount = float(abs(self._safe_balance_metric(match.get("amount")) or 0.0))
            recommended_amount = float(abs(self._safe_balance_metric(payload.get("recommended_amount_units")) or 0.0))
            if current_amount <= 0:
                self._monitored_user_trade_positions.pop(key, None)
                continue
            if current_amount <= recommended_amount + 1e-9:
                self._monitored_user_trade_positions.pop(key, None)
                await self._record_trade_audit(
                    "user_trade_risk_monitor_resolved",
                    status="resolved",
                    symbol=target_symbol,
                    side=payload.get("original_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=payload.get("original_order_id"),
                    message="The user trade risk exposure was reduced to the recommended size before intervention.",
                    payload={"position": dict(match), "monitor": dict(payload)},
                )
                continue

            entry_price = self._safe_balance_metric(match.get("entry_price") or payload.get("entry_price"))
            current_price = self._safe_balance_metric(
                match.get("mark_price")
                or match.get("market_price")
                or match.get("price")
                or payload.get("last_price")
            )
            if current_price is None or current_price <= 0:
                current_price = self._safe_balance_metric((payload.get("market_context") or {}).get("latest_price"))
            if entry_price is None or entry_price <= 0 or current_price is None or current_price <= 0:
                continue

            adverse_distance = (
                max(0.0, float(entry_price) - float(current_price))
                if target_side in {"long", "buy"}
                else max(0.0, float(current_price) - float(entry_price))
            )
            payload["last_price"] = float(current_price)
            adverse_threshold = max(float(payload.get("adverse_threshold") or 0.0), abs(float(entry_price)) * 0.0015, 1e-6)
            if adverse_distance + 1e-9 < adverse_threshold:
                continue

            if (now - created_at) < grace_seconds:
                if (now - float(payload.get("last_warning_at", 0.0) or 0.0)) >= 15.0:
                    payload["last_warning_at"] = now
                    payload["warnings_sent"] = int(payload.get("warnings_sent", 0) or 0) + 1
                    self._notify_user_trade_review(
                        "User Trade Risk Watch",
                        (
                            f"{str(payload.get('summary') or '').strip()} "
                            f"The live {target_symbol} position is still oversized and has moved "
                            f"{adverse_distance:.4f} against the entry. "
                            "If the exposure is not reduced before the grace window expires, the system will step in."
                        ).strip(),
                        level="WARN",
                    )
                continue

            ai_note = None
            if not bool(payload.get("ai_consulted")):
                ai_note = await self._recommend_user_trade_monitor_action_with_openai(
                    monitor=payload,
                    position=match,
                    current_price=current_price,
                    adverse_distance=adverse_distance,
                )
                payload["ai_consulted"] = True
                if isinstance(ai_note, dict):
                    payload["ai_recommendation"] = str(ai_note.get("recommendation") or "").strip().lower()
                    payload["ai_reason"] = str(ai_note.get("reason") or "").strip()
            else:
                ai_note = {
                    "recommendation": str(payload.get("ai_recommendation") or "").strip().lower(),
                    "reason": str(payload.get("ai_reason") or "").strip(),
                }

            base_action = "close" if recommended_amount <= 0 else "trim"
            ai_recommendation = str((ai_note or {}).get("recommendation") or "").strip().lower()
            effective_action = "close" if ai_recommendation == "exit" else base_action
            intervention_amount = current_amount if effective_action == "close" else max(0.0, current_amount - recommended_amount)
            if intervention_amount <= 1e-9:
                self._monitored_user_trade_positions.pop(key, None)
                continue

            try:
                close_result = await self._close_position_for_user_trade_review(match, amount=intervention_amount)
                self._monitored_user_trade_positions.pop(key, None)
                ai_reason = str((ai_note or {}).get("reason") or "").strip()
                summary = (
                    f"{str(payload.get('summary') or '').strip()} "
                    f"The market moved {adverse_distance:.4f} against the entry while the position remained oversized."
                ).strip()
                if effective_action == "trim" and recommended_amount > 0:
                    summary = (
                        f"{summary} The system reduced the position from {current_amount:.6f} to "
                        f"{recommended_amount:.6f} units to bring it back inside the recommended risk."
                    ).strip()
                else:
                    summary = f"{summary} The system closed the full position to stop further unmanaged risk.".strip()
                if ai_reason:
                    summary = f"{summary} ChatGPT risk note: {ai_reason}".strip()

                await self._record_trade_audit(
                    "user_trade_risk_monitor_action",
                    status=str((close_result or {}).get("status") or "submitted"),
                    symbol=target_symbol,
                    side=payload.get("original_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=(close_result or {}).get("id") if isinstance(close_result, dict) else None,
                    message=summary,
                    payload={
                        "position": dict(match),
                        "monitor": dict(payload),
                        "close_result": dict(close_result) if isinstance(close_result, dict) else close_result,
                        "effective_action": effective_action,
                    },
                )
                self._notify_user_trade_review("User Trade Risk Controlled", summary, level="WARN")
            except Exception as exc:
                await self._record_trade_audit(
                    "user_trade_risk_monitor_error",
                    status="error",
                    symbol=target_symbol,
                    side=payload.get("original_side"),
                    order_type="market",
                    source="manual_review",
                    order_id=payload.get("original_order_id"),
                    message=str(exc),
                    payload={"position": dict(match), "monitor": dict(payload)},
                )

    async def _process_user_trade_position_safety(self, positions):
        await self._process_pending_user_trade_position_reviews(positions)
        await self._process_monitored_user_trade_positions(positions)

    def queue_pending_user_trade_position_reviews(self, positions):
        if not bool(getattr(self, "user_trade_autocorrect_enabled", True)):
            return None
        if not bool(getattr(self, "_pending_user_trade_reviews", {})) and not bool(
                getattr(self, "_monitored_user_trade_positions", {})
        ):
            return None
        task = getattr(self, "_pending_user_trade_review_task", None)
        if task is not None and not task.done():
            return task
        runner = self._process_user_trade_position_safety(list(positions or []))
        create_task = getattr(self, "_create_task", None)
        if callable(create_task):
            self._pending_user_trade_review_task = create_task(runner, "pending_user_trade_review")
        else:
            self._pending_user_trade_review_task = asyncio.create_task(runner)
        return self._pending_user_trade_review_task

    async def _handle_user_trade_review(
            self,
            order,
            *,
            symbol,
            side,
            order_type,
            price=None,
            stop_price=None,
            stop_loss=None,
            take_profit=None,
            source=None,
            timeframe=None,
    ):
        if not isinstance(order, dict) or not bool(getattr(self, "user_trade_autocorrect_enabled", True)):
            return order
        if bool(order.get("hybrid_server")):
            return order
        if not self._is_user_directed_trade_source(source):
            return order

        order_symbol = str(order.get("symbol") or symbol or "").strip().upper()
        actual_amount = abs(
            float(
                self._safe_balance_metric(order.get("amount"))
                or self._safe_balance_metric(order.get("amount_units"))
                or 0.0
            )
        )
        reference_price = (
                self._safe_balance_metric(order.get("price"))
                or self._safe_balance_metric(order.get("reference_price"))
                or self._safe_balance_metric(price)
        )
        review = await self._assess_user_trade_review(
            symbol=order_symbol,
            side=side,
            amount_units=actual_amount,
            reference_price=reference_price,
            stop_loss=order.get("stop_loss", stop_loss),
            take_profit=order.get("take_profit", take_profit),
            timeframe=timeframe,
        )
        order["review_action"] = str(review.get("action") or "keep")
        order["review_reason"] = str(review.get("summary") or "").strip()
        order["review_reasons"] = list(review.get("reasons") or [])
        order["risk_monitoring_active"] = False

        if not review.get("is_bad") and not review.get("monitor_only"):
            await self._record_trade_audit(
                "user_trade_review_pass",
                status="ok",
                symbol=order_symbol,
                side=self._normalize_trade_side(order.get("side") or side),
                order_type=order.get("type") or order_type,
                source=source,
                order_id=order.get("id") or order.get("order_id"),
                message="User-directed trade review approved the order.",
                payload={"review": dict(review), "order": dict(order)},
            )
            return order

        if review.get("monitor_only"):
            monitor = await self._queue_monitored_user_trade_position(
                order=order,
                review=review,
                timeframe=timeframe,
            )
            order["risk_monitoring_active"] = monitor is not None
            order["intervention_pending"] = False
            order["intervention_taken"] = False
            order["intervention_summary"] = str(review.get("summary") or "").strip()
            await self._record_trade_audit(
                "user_trade_risk_warning",
                status="monitoring",
                symbol=order_symbol,
                side=self._normalize_trade_side(order.get("side") or side),
                order_type=order.get("type") or order_type,
                source=source,
                order_id=order.get("id") or order.get("order_id"),
                message=str(review.get("summary") or "User-directed trade is oversized and is now being monitored."),
                payload={"review": dict(review), "order": dict(order), "monitor": dict(monitor or {})},
            )
            if monitor is not None:
                self._notify_user_trade_review(
                    "User Trade Risk Warning",
                    (
                        f"{str(review.get('summary') or '').strip()} "
                        f"The system is watching this position closely and will step in if price keeps moving against it."
                    ).strip(),
                    level="WARN",
                )
            return order

        await self._record_trade_audit(
            "user_trade_review_flagged",
            status="flagged",
            symbol=order_symbol,
            side=self._normalize_trade_side(order.get("side") or side),
            order_type=order.get("type") or order_type,
            source=source,
            order_id=order.get("id") or order.get("order_id"),
            message=str(review.get("summary") or "User-directed trade review flagged the trade."),
            payload={"review": dict(review), "order": dict(order)},
        )

        normalized_status = str(order.get("status") or "").strip().lower()
        order_id = str(order.get("id") or order.get("order_id") or "").strip()
        cancelable_order = bool(order_id) and (
                normalized_status in {"open", "pending", "new", "accepted"}
                or (str(order_type or "market").strip().lower() != "market" and normalized_status in {"submitted", "placed"})
        )

        broker = getattr(self, "broker", None)
        if cancelable_order and broker is not None and hasattr(broker, "cancel_order"):
            try:
                try:
                    await broker.cancel_order(order_id, symbol=order_symbol)
                except TypeError:
                    await broker.cancel_order(order_id)
                replacement = None
                if str(review.get("action") or "correct").strip().lower() != "close":
                    replacement = await self.submit_trade_with_preflight(
                        symbol=order_symbol,
                        side=review.get("replacement_side"),
                        amount=float(review.get("replacement_amount_units") or actual_amount),
                        quantity_mode=None,
                        order_type=order_type,
                        price=order.get("price", price),
                        stop_price=order.get("stop_price", stop_price),
                        stop_loss=review.get("replacement_stop_loss"),
                        take_profit=review.get("replacement_take_profit"),
                        source="manual_review",
                        strategy_name="Manual Review",
                        reason=f"User trade auto-corrected: {review.get('summary')}",
                        timeframe=timeframe,
                    )
                if isinstance(replacement, dict):
                    replacement["review_action"] = review.get("action")
                    replacement["review_reason"] = str(review.get("summary") or "").strip()
                    replacement["review_reasons"] = list(review.get("reasons") or [])
                    replacement["intervention_taken"] = True
                    replacement["intervention_summary"] = str(review.get("summary") or "").strip()
                    replacement["review_replaced_order_id"] = order_id or None
                else:
                    order["status"] = "canceled"
                    order["intervention_taken"] = True
                    order["intervention_pending"] = False
                    order["intervention_summary"] = str(review.get("summary") or "").strip()
                    order["review_replaced_order_id"] = order_id or None
                self._notify_user_trade_review(
                    "User Trade Corrected",
                    str(review.get("summary") or "The user-directed order was canceled and replaced with a safer trade."),
                    level="WARN",
                )
                return replacement if replacement is not None else order
            except Exception as exc:
                await self._record_trade_audit(
                    "user_trade_review_cancel_error",
                    status="error",
                    symbol=order_symbol,
                    side=self._normalize_trade_side(order.get("side") or side),
                    order_type=order.get("type") or order_type,
                    source=source,
                    order_id=order_id or None,
                    message=str(exc),
                    payload={"review": dict(review), "order": dict(order)},
                )

        pending = await self._queue_pending_user_trade_review(
            order=order,
            review=review,
            timeframe=timeframe,
        )
        order["intervention_pending"] = pending is not None
        order["intervention_taken"] = False
        order["intervention_summary"] = str(review.get("summary") or "").strip()
        self._notify_user_trade_review(
            "User Trade Flagged",
            (
                f"{str(review.get('summary') or '').strip()} "
                "The system will close and replace the position as soon as the live position snapshot is available."
            ).strip(),
            level="WARN",
        )
        return order

    def market_chat_position_summary(self, open_window=True):
        terminal = getattr(self, "terminal", None)
        if terminal is None or not hasattr(terminal, "_position_analysis_window_payload"):
            return None

        try:
            payload = terminal._position_analysis_window_payload() or {}
        except Exception:
            return None

        if open_window and hasattr(terminal, "_open_position_analysis_window"):
            try:
                terminal._open_position_analysis_window()
            except Exception:
                pass

        if not payload.get("available"):
            exchange = str(payload.get("exchange") or getattr(getattr(self, "broker", None), "exchange_name", "") or "-")
            return f"Position analysis is not available because no broker is currently connected. Last broker context: {exchange}."

        positions = list(payload.get("positions", []) or [])
        broker_label = str(payload.get("exchange") or "-").upper()
        if not positions:
            nav = payload.get("nav")
            balance = payload.get("balance")
            return (
                "Position Analysis window opened.\n"
                f"Broker: {broker_label} | Equity/NAV: {nav if nav is not None else '-'} | Balance/Cash: {balance if balance is not None else '-'}\n"
                "No open positions were found."
            )

        total_unrealized = sum(float(item.get("pnl", 0.0) or 0.0) for item in positions)
        total_realized = sum(float(item.get("realized_pnl", 0.0) or 0.0) for item in positions)
        total_margin = sum(float(item.get("margin_used", 0.0) or 0.0) for item in positions)
        total_value = sum(abs(float(item.get("value", 0.0) or 0.0)) for item in positions)
        winner = max(positions, key=lambda item: float(item.get("pnl", 0.0) or 0.0))
        loser = min(positions, key=lambda item: float(item.get("pnl", 0.0) or 0.0))
        largest = max(positions, key=lambda item: abs(float(item.get("value", 0.0) or 0.0)))
        long_count = sum(1 for item in positions if str(item.get("side", "")).lower() == "long")
        short_count = sum(1 for item in positions if str(item.get("side", "")).lower() == "short")
        closeout = payload.get("margin_closeout_percent")
        closeout_guard = self.margin_closeout_snapshot(payload.get("balances"))

        lines = [
            "Position Analysis window opened.",
            (
                f"Broker: {broker_label}"
                f" | Equity/NAV: {payload.get('nav', '-')}"
                f" | Balance/Cash: {payload.get('balance', '-')}"
                f" | Unrealized P/L: {total_unrealized:.2f}"
                f" | Realized P/L: {total_realized:.2f}"
            ),
            (
                f"Open positions: {len(positions)}"
                f" | Long: {long_count}"
                f" | Short: {short_count}"
                f" | Margin Used: {total_margin:.2f}"
                f" | Total Exposure: {total_value:.2f}"
            ),
            (
                f"Biggest winner: {winner.get('symbol', '-')} {float(winner.get('pnl', 0.0) or 0.0):.2f}"
                f" | Biggest loser: {loser.get('symbol', '-')} {float(loser.get('pnl', 0.0) or 0.0):.2f}"
            ),
            f"Largest exposure: {largest.get('symbol', '-')} value {float(largest.get('value', 0.0) or 0.0):.2f}",
        ]
        if closeout is not None:
            lines.append(f"Margin closeout percent: {closeout}")
        if closeout_guard.get("enabled"):
            lines.append(
                f"Margin closeout guard: {'BLOCKING' if closeout_guard.get('blocked') else 'monitoring'} "
                f"at {float(closeout_guard.get('threshold', 0.0) or 0.0):.2%}."
            )
        lines.append("Use Tools -> Position Analysis for the detailed table.")
        return "\n".join(lines)

    # Backward-compatible alias
    def market_chat_oanda_position_summary(self, open_window=True):
        return self.market_chat_position_summary(open_window=open_window)

    async def market_chat_quant_pm_summary(self, open_window=True):
        terminal = getattr(self, "terminal", None)
        if terminal is None or not hasattr(terminal, "_quant_pm_payload"):
            return None

        if open_window and hasattr(terminal, "_open_quant_pm_window"):
            try:
                terminal._open_quant_pm_window()
            except Exception:
                pass

        try:
            payload = await terminal._quant_pm_payload()
        except Exception:
            payload = {}

        if not payload.get("available"):
            broker_label = str(
                payload.get("exchange")
                or getattr(getattr(self, "broker", None), "exchange_name", "")
                or "-"
            ).upper()
            return (
                "Quant PM is not available yet because the trading system is not fully active. "
                f"Current broker context: {broker_label}."
            )

        def fmt_money(value):
            try:
                numeric = float(value)
            except Exception:
                return "-"
            return f"${numeric:,.2f}"

        def fmt_pct(value):
            try:
                numeric = float(value)
            except Exception:
                return "-"
            return f"{numeric:.2%}"

        strategy_rows = list(payload.get("strategy_rows") or [])
        position_rows = list(payload.get("position_rows") or [])
        allocation = dict(payload.get("allocation_snapshot") or {})
        risk = dict(payload.get("risk_snapshot") or {})
        institutional = dict(payload.get("institutional_status") or {})
        behavior = dict(payload.get("behavior_status") or {})
        health_attention = [self._plain_text(str(item)) for item in (payload.get("health_attention") or []) if str(item).strip()]
        top_strategy = strategy_rows[0] if strategy_rows else {}
        top_position = position_rows[0] if position_rows else {}
        correlation_rows = list(payload.get("correlation_rows") or [])
        account = self._plain_text(str(payload.get("account") or "Profile unavailable"))
        equity_label = fmt_money(payload.get("equity"))

        lines = [
            "Quant PM window opened.",
            (
                f"Broker: {str(payload.get('exchange') or '-').upper()} | "
                f"Account: {account} | "
                f"Mode: {payload.get('mode', 'PAPER')} | "
                f"Equity: {equity_label} | "
                f"Health: {self._plain_text(str(payload.get('health') or 'Not run'))}"
            ),
            (
                f"Allocator: {self._plain_text(str((payload.get('allocator_status') or {}).get('allocation_model') or '-'))} | "
                f"Target Weight: {fmt_pct(allocation.get('target_weight'))} | "
                f"Strategy: {self._plain_text(str(allocation.get('strategy_name') or top_strategy.get('strategy') or '-'))}"
            ),
            (
                f"Institutional Risk: {self._plain_text(str(risk.get('reason') or 'No recent decision'))} | "
                f"Trade VaR: {fmt_pct(risk.get('trade_var_pct'))} | "
                f"Gross Exposure: {fmt_pct(risk.get('gross_exposure_pct'))}"
            ),
            (
                f"Behavior Guard: {self._plain_text(str(behavior.get('summary') or behavior.get('state') or '-'))} | "
                f"Top strategy exposure: {self._plain_text(str(top_strategy.get('strategy') or '-'))} "
                f"{fmt_money(top_strategy.get('exposure'))}"
            ),
        ]
        if health_attention:
            lines.append(f"Health attention: {' | '.join(health_attention[:3])}")
        if top_position:
            lines.append(
                "Largest live position: "
                f"{self._plain_text(str(top_position.get('symbol') or '-'))} "
                f"{self._plain_text(str(top_position.get('direction') or '-'))} | "
                f"Exposure {fmt_money(top_position.get('exposure'))}"
            )
        if correlation_rows:
            anchor_row = correlation_rows[0]
            anchor_symbol = str(anchor_row.get("symbol") or "").upper().strip()
            peers = []
            for key, value in anchor_row.items():
                if key == "symbol":
                    continue
                try:
                    numeric = float(value or 0.0)
                except Exception:
                    numeric = 0.0
                peers.append((str(key), abs(numeric), numeric))
            peers.sort(key=lambda item: item[1], reverse=True)
            if peers:
                peer_symbol, _, corr_value = peers[0]
                lines.append(f"Highest visible correlation: {anchor_symbol} vs {peer_symbol} at {corr_value:.2f}.")
        if institutional:
            lines.append(
                f"Portfolio limits: VaR {fmt_pct(institutional.get('max_portfolio_risk'))}, "
                f"symbol cap {fmt_pct(institutional.get('max_symbol_exposure_pct'))}, "
                f"gross cap {fmt_pct(institutional.get('max_gross_exposure_pct'))}."
            )
        lines.append("Use Tools -> Quant PM for the full allocator, exposure, and correlation view.")
        return "\n".join(lines)

    def market_chat_command_guide(self):
        return (
            "Sopotek Pilot Commands\n"
            "\n"
            "General\n"
            "- help\n"
            "- show commands\n"
            "- show app status\n"
            "- take a screenshot\n"
            "\n"
            "Trading Control\n"
            "- start ai trading\n"
            "- stop ai trading\n"
            "- set ai scope all\n"
            "- set ai scope selected\n"
            "- set ai scope watchlist\n"
            "- set ai scope best ranked\n"
            "- activate kill switch\n"
            "- resume trading\n"
            "\n"
            "Windows and Tools\n"
            "- open settings\n"
            "- open system health\n"
            "- open recommendations\n"
            "- open performance\n"
            "- open quant pm\n"
            "- open ml research\n"
            "- open closed journal\n"
            "- open journal review\n"
            "- open logs\n"
            "- open position analysis\n"
            "- open oanda positions\n"
            "- open documentation\n"
            "- open api docs\n"
            "- open about\n"
            "- open manual trade\n"
            "\n"
            "Refresh Actions\n"
            "- refresh markets\n"
            "- reload balances\n"
            "- refresh chart\n"
            "- refresh orderbook\n"
            "\n"
            "Telegram\n"
            "- show telegram status\n"
            "- enable telegram\n"
            "- disable telegram\n"
            "- restart telegram\n"
            "- send telegram test message\n"
            "- telegram slash commands: /status /management /balances /positions /orders /recommendations /performance /history /analysis\n"
            "- telegram control commands: /settings /health /quantpm /journal /review /logs /refreshmarkets /reloadbalances /refreshchart /refreshorderbook\n"
            "- telegram trading control: /autotradeon /autotradeoff /killswitch /resume /chartshot\n"
            "\n"
            "Trading Commands\n"
            "- trade buy EUR/USD amount 0.01 lots confirm\n"
            "- trade sell GBP/USD amount 2000 type limit price 1.2710 sl 1.2750 tp 1.2620 confirm\n"
            "- trade buy BTC/USDT amount 0.25 type stop_limit trigger 65010 price 64990 confirm\n"
            "- cancel order id 123456 confirm\n"
            "- cancel orders for EUR/USD confirm\n"
            "- close position EUR/USD confirm\n"
            "- close position EUR/USD amount 0.01 lots confirm\n"
            "\n"
            "Analysis\n"
            "- show bug summary\n"
            "- show error log\n"
            "- show quant pm summary\n"
            "- show my broker position analysis with equity, NAV, and P/L\n"
            "- show trade history analysis\n"
            "- summarize current recommendations and why\n"
            "- summarize the latest news affecting my active symbols"
        )

    def _market_chat_log_file_paths(self):
        root_dir = Path(__file__).resolve().parents[2]
        candidates = []
        seen = set()

        for directory in (
                Path("logs"),
                Path("src") / "logs",
                root_dir / "logs",
        ):
            try:
                resolved = directory.resolve()
            except Exception:
                resolved = directory
            if not resolved.exists() or not resolved.is_dir():
                continue
            for name in ("native_crash.log", "errors.log", "system.log", "app.log"):
                path = resolved / name
                if not path.exists():
                    continue
                key = str(path).lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(path)

        return candidates

    def _tail_log_lines(self, path, max_lines=240):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        lines = [line.rstrip() for line in text.splitlines()]
        lines = [line for line in lines if line.strip()]
        if max_lines <= 0:
            return lines
        return lines[-max_lines:]

    def _format_log_timestamp(self, path):
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "unknown time"

    def _market_chat_native_crash_summary(self, path):
        lines = self._tail_log_lines(path, max_lines=320)
        if not lines:
            return None

        frame_pattern = re.compile(r'File "([^"]+)", line (\d+) in (\S+)')
        frames = []
        capture = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Current thread "):
                capture = True
                continue
            if not capture:
                continue
            if stripped.startswith("Current thread's C stack"):
                break
            match = frame_pattern.search(stripped)
            if match:
                filename = Path(match.group(1)).name
                frames.append(f"{filename}:{match.group(2)} in {match.group(3)}")

        if frames:
            summary = (
                f"{path.name} updated {self._format_log_timestamp(path)}: native crash trace captured. "
                f"Top frame {frames[0]}."
            )
            if len(frames) > 1:
                summary += f" Next frame {frames[1]}."
            return summary

        last_line = self._plain_text(lines[-1])
        if not last_line:
            return None
        return f"{path.name} updated {self._format_log_timestamp(path)}: {last_line}"

    def _market_chat_regular_log_summary(self, path, max_entries=2):
        lines = self._tail_log_lines(path, max_lines=320)
        if not lines:
            return None

        include_tokens = (
            "uncaught exception",
            "traceback",
            "error calling python override",
            "exception",
            "critical",
            "fatal",
            "cleanup error",
            "task ",
            "native crash",
        )
        ignore_tokens = (
            "trade rejected by portfolio allocator",
            "trade rejected by institutional risk engine",
            "trade rejected by risk engine",
            "skipping ",
            "using polling market data",
            "broker ready",
            "initializing broker",
        )

        matches = []
        seen = set()
        for line in reversed(lines):
            lowered = line.lower()
            if not any(token in lowered for token in include_tokens):
                continue
            if any(token in lowered for token in ignore_tokens):
                continue
            cleaned = self._plain_text(line)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            matches.append(cleaned)
            if len(matches) >= max_entries:
                break

        if not matches:
            return None

        matches.reverse()
        return (
                f"{path.name} updated {self._format_log_timestamp(path)}: "
                + " | ".join(matches)
        )

    def market_chat_error_log_summary(self, open_window=True, max_entries=4):
        if open_window:
            try:
                self.market_chat_open_window("logs")
            except Exception:
                pass

        paths = self._market_chat_log_file_paths()
        if not paths:
            return "I could not find any local log files yet."

        findings = []
        quiet_files = []
        for path in paths:
            if path.name == "native_crash.log":
                summary = self._market_chat_native_crash_summary(path)
            else:
                summary = self._market_chat_regular_log_summary(path)
            if summary:
                findings.append(summary)
            else:
                quiet_files.append(path.name)

        if not findings:
            quiet_text = ", ".join(quiet_files) if quiet_files else "available logs"
            return (
                "I checked the local logs and did not find recent crash or exception signatures. "
                f"Quiet logs: {quiet_text}."
            )

        lines = ["Bug summary from local logs:"]
        for item in findings[: max(1, int(max_entries or 4))]:
            lines.append(f"- {item}")
        if quiet_files:
            lines.append(f"No recent bug signatures in: {', '.join(quiet_files[:4])}.")
        lines.append("Use Tools -> Logs for the full log view.")
        return "\n".join(lines)

    def market_chat_set_ai_trading(self, enabled):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return False, "Open the trading terminal first."

        setter = getattr(terminal, "_set_autotrading_enabled", None)
        if not callable(setter):
            return False, "AI trading controls are not available in this terminal session."

        target = bool(enabled)
        is_active = bool(getattr(terminal, "autotrading_enabled", False))
        scope_label = getattr(terminal, "_autotrade_scope_label", lambda: "All Symbols")()
        scope_value = str(getattr(terminal, "autotrade_scope_value", "all") or "all").lower()

        if target and is_active:
            return True, f"AI trading is already ON. Scope: {scope_label}."
        if (not target) and (not is_active):
            return True, "AI trading is already OFF."

        if target and bool(getattr(self, "is_emergency_stop_active", lambda: False)()):
            return False, "Emergency lock is active. Clear the kill switch before enabling AI trading."

        if target and not getattr(self, "trading_system", None):
            return False, "AI trading cannot start because the trading system is not initialized yet."

        if target:
            active_symbols = []
            resolver = getattr(self, "get_active_autotrade_symbols", None)
            if callable(resolver):
                try:
                    active_symbols = list(resolver() or [])
                except Exception:
                    active_symbols = []
            if not active_symbols:
                if scope_value == "watchlist":
                    return False, "AI trading cannot start because the watchlist scope has no checked symbols."
                if scope_value == "selected":
                    return False, "AI trading cannot start because there is no active selected symbol yet."
                if scope_value == "ranked":
                    return False, "AI trading cannot start because the best-ranked scope has no tradable symbols yet."
                return False, "AI trading cannot start because no symbols are available for the chosen AI scope."

        setter(target)
        is_active = bool(getattr(terminal, "autotrading_enabled", False))
        if target and is_active:
            return True, f"AI trading is ON. Scope: {scope_label}."
        if (not target) and (not is_active):
            return True, "AI trading is OFF."

        return False, "AI trading state did not change. Check the terminal for more details."

    async def market_chat_app_status_summary(self, show_panel=True):
        terminal = getattr(self, "terminal", None)
        if terminal is not None and show_panel:
            dock = getattr(terminal, "system_status_dock", None)
            try:
                if dock is not None and not dock.isVisible():
                    terminal._show_system_status_panel()
                elif dock is not None:
                    dock.raise_()
                    dock.activateWindow()
            except Exception:
                pass

        status_lines = ["System status opened."]
        try:
            status_lines.append(self._plain_text(await self.telegram_status_text()))
        except Exception:
            status_lines.append("Runtime status is available in the System Status panel.")

        behavior = self.get_behavior_guard_status() or {}
        if behavior:
            status_lines.append(
                f"Behavior Guard: {self._plain_text(behavior.get('summary') or 'Active')} | "
                f"Reason: {self._plain_text(behavior.get('reason') or 'No active restriction')}"
            )
        status_lines.append(f"Health Check: {self.get_health_check_summary()}")
        return "\n".join(line for line in status_lines if line)

    def _market_chat_open_orders_snapshot(self):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return []
        active_snapshot = getattr(terminal, "_active_open_orders_snapshot", None)
        if callable(active_snapshot):
            try:
                snapshot = list(active_snapshot() or [])
            except Exception:
                snapshot = []
            return [dict(item) for item in snapshot if isinstance(item, dict)]
        snapshot = list(getattr(terminal, "_latest_open_orders_snapshot", []) or [])
        normalized = []
        normalizer = getattr(terminal, "_normalize_open_order_entry", None)
        for item in snapshot:
            if callable(normalizer):
                try:
                    entry = normalizer(item)
                except Exception:
                    entry = None
                if entry is not None:
                    payload = dict(entry)
                    payload["_raw"] = item
                    normalized.append(payload)
                    continue
            if isinstance(item, dict):
                payload = dict(item)
                payload.setdefault("_raw", item)
                normalized.append(payload)
        return normalized

    def _market_chat_positions_snapshot(self):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return []
        active_snapshot = getattr(terminal, "_active_positions_snapshot", None)
        if callable(active_snapshot):
            try:
                snapshot = list(active_snapshot() or [])
            except Exception:
                snapshot = []
            return [dict(item) for item in snapshot if isinstance(item, dict)]
        snapshot = list(getattr(terminal, "_latest_positions_snapshot", []) or [])
        normalized = []
        normalizer = getattr(terminal, "_normalize_position_entry", None)
        for item in snapshot:
            if callable(normalizer):
                try:
                    entry = normalizer(item)
                except Exception:
                    entry = None
                if entry is not None:
                    payload = dict(entry)
                    payload["_raw"] = item
                    normalized.append(payload)
                    continue
            if isinstance(item, dict):
                payload = dict(item)
                payload.setdefault("_raw", item)
                normalized.append(payload)
        return normalized

    async def cancel_market_chat_order(self, order_id=None, symbol=None, cancel_all_for_symbol=False):
        broker = getattr(self, "broker", None)
        if broker is None:
            raise RuntimeError("Connect a broker before canceling orders from Sopotek Pilot.")

        normalized_symbol = str(symbol or "").strip().upper()
        normalized_id = str(order_id or "").strip()
        orders = self._market_chat_open_orders_snapshot()
        matches = []
        for order in orders:
            candidate_id = str(order.get("order_id") or order.get("id") or "").strip()
            candidate_symbol = str(order.get("symbol") or "").strip().upper()
            if normalized_id and candidate_id == normalized_id:
                matches.append(order)
            elif normalized_symbol and candidate_symbol == normalized_symbol:
                matches.append(order)

        if normalized_id and not matches:
            raise RuntimeError(f"No open order with id {normalized_id} was found.")
        if normalized_symbol and not matches:
            raise RuntimeError(f"No open orders for {normalized_symbol} were found.")
        if not normalized_id and not normalized_symbol:
            raise RuntimeError("Cancel order command needs an order id or symbol.")
        if normalized_symbol and len(matches) > 1 and not cancel_all_for_symbol and not normalized_id:
            ids = ", ".join(str(item.get("order_id") or item.get("id") or "-") for item in matches[:5])
            raise RuntimeError(
                f"Multiple open orders found for {normalized_symbol}. Use 'cancel orders for {normalized_symbol} confirm' or specify an order id. Matches: {ids}"
            )

        targets = matches if cancel_all_for_symbol or normalized_id else matches[:1]
        results = []
        for order in targets:
            target_id = str(order.get("order_id") or order.get("id") or "").strip()
            target_symbol = str(order.get("symbol") or normalized_symbol or "").strip().upper() or None
            if not target_id:
                continue
            if self._hybrid_trading_available():
                try:
                    result = await self._cancel_order_via_hybrid_server(target_id)
                    results.append(
                        result
                        if result is not None
                        else {"id": target_id, "symbol": target_symbol, "status": "cancel_requested", "hybrid_server": True}
                    )
                    continue
                except Exception as exc:
                    self.hybrid_server_last_error = str(exc)
                    self.logger.warning("Hybrid cancel request failed; falling back to local broker path: %s", exc)
            if hasattr(broker, "cancel_order"):
                try:
                    result = await broker.cancel_order(target_id, symbol=target_symbol)
                except TypeError:
                    result = await broker.cancel_order(target_id)
            else:
                raise RuntimeError("Current broker does not support cancel_order.")
            results.append(result if result is not None else {"id": target_id, "symbol": target_symbol})

        terminal = getattr(self, "terminal", None)
        if terminal is not None and hasattr(terminal, "_schedule_open_orders_refresh"):
            terminal._schedule_open_orders_refresh()
        return results

    async def close_market_chat_position(self, symbol, amount=None, quantity_mode=None, position=None, position_side=None, position_id=None):
        broker = getattr(self, "broker", None)
        if broker is None:
            raise RuntimeError("Connect a broker before closing positions from Sopotek Pilot.")

        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise RuntimeError("Close position command needs a symbol.")

        positions = self._market_chat_positions_snapshot()
        selected_position = position if isinstance(position, dict) else None
        selected_side = str(
            position_side
            or (selected_position or {}).get("position_side")
            or (selected_position or {}).get("side")
            or ""
        ).strip().lower()
        selected_id = str(
            position_id
            or (selected_position or {}).get("position_id")
            or (selected_position or {}).get("id")
            or ""
        ).strip().lower()

        matches = [
            item
            for item in positions
            if str(item.get("symbol") or "").strip().upper() == normalized_symbol
        ]
        if selected_id:
            matches = [
                item
                for item in matches
                if str(item.get("position_id") or item.get("id") or "").strip().lower() == selected_id
            ]
        if selected_side:
            matches = [
                item
                for item in matches
                if str(item.get("position_side") or item.get("side") or "").strip().lower() == selected_side
            ]
        if selected_position is not None and not matches:
            matches = [selected_position]
        if len(matches) > 1 and self.hedging_is_active(broker):
            raise RuntimeError(
                f"Multiple hedge legs are open for {normalized_symbol}. Choose the specific LONG or SHORT position from Positions or Position Analysis."
            )
        target = matches[0] if matches else None
        if target is None:
            raise RuntimeError(f"No open position for {normalized_symbol} was found.")

        resolved_amount = None
        if amount is not None:
            if quantity_mode is None and isinstance(target, dict):
                try:
                    resolved_amount = abs(float(amount))
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("Close position amount must be numeric.") from exc
            else:
                try:
                    quantity = self.normalize_trade_quantity(normalized_symbol, amount, quantity_mode=quantity_mode)
                except ValueError as exc:
                    raise RuntimeError(str(exc)) from exc
                resolved_amount = float(quantity["amount_units"])

        target_position_id = str(target.get("position_id") or target.get("id") or "").strip()
        if self._hybrid_trading_available() and target_position_id:
            try:
                result = await self._close_position_via_hybrid_server(target_position_id)
                terminal = getattr(self, "terminal", None)
                if terminal is not None:
                    if hasattr(terminal, "_schedule_positions_refresh"):
                        terminal._schedule_positions_refresh()
                    if hasattr(terminal, "_schedule_open_orders_refresh"):
                        terminal._schedule_open_orders_refresh()
                return result if result is not None else {"position_id": target_position_id, "status": "close_requested", "hybrid_server": True}
            except Exception as exc:
                self.hybrid_server_last_error = str(exc)
                self.logger.warning("Hybrid close-position request failed; falling back to local broker path: %s", exc)

        result = None
        if hasattr(broker, "close_position"):
            try:
                result = await broker.close_position(
                    normalized_symbol,
                    amount=resolved_amount,
                    order_type="market",
                    position=target,
                    position_side=selected_side or target.get("position_side") or target.get("side"),
                    position_id=selected_id or target.get("position_id") or target.get("id"),
                )
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                result = await broker.close_position(normalized_symbol, amount=resolved_amount)

        if result is None:
            side = str(target.get("side") or "").strip().lower()
            close_side = "buy" if side in {"short", "sell"} else "sell"
            fallback_amount = resolved_amount
            if fallback_amount is None:
                fallback_amount = abs(float(target.get("amount", target.get("units", 0.0)) or 0.0))
            if fallback_amount <= 0:
                raise RuntimeError(f"Unable to determine a valid close amount for {normalized_symbol}.")
            result = await broker.create_order(
                symbol=normalized_symbol,
                side=close_side,
                amount=fallback_amount,
                type="market",
                params={"positionFill": "REDUCE_ONLY"} if self.hedging_is_active(broker) else None,
            )

        terminal = getattr(self, "terminal", None)
        if terminal is not None:
            if hasattr(terminal, "_schedule_positions_refresh"):
                terminal._schedule_positions_refresh()
            if hasattr(terminal, "_schedule_open_orders_refresh"):
                terminal._schedule_open_orders_refresh()
        return result

    def market_chat_open_window(self, target):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return "Terminal UI is not available."

        target_key = str(target or "").strip().lower()
        if target_key in {"status", "system status"}:
            dock = getattr(terminal, "system_status_dock", None)
            if dock is not None and not dock.isVisible():
                terminal._show_system_status_panel()
            elif dock is not None:
                dock.raise_()
                dock.activateWindow()
            return "System Status panel opened."

        mapping = {
            "settings": ("_open_settings", "Settings window opened."),
            "system health": ("_open_system_health_window", "System Health window opened."),
            "recommendations": ("_open_recommendations_window", "Trade Recommendations window opened."),
            "performance": ("_open_performance", "Performance Analytics window opened."),
            "quant pm": ("_open_quant_pm_window", "Quant PM window opened."),
            "quant dashboard": ("_open_quant_pm_window", "Quant PM window opened."),
            "ml research": ("_open_ml_research_window", "ML Research Lab window opened."),
            "closed journal": ("_open_closed_journal_window", "Closed Trade Journal window opened."),
            "journal review": ("_open_trade_journal_review_window", "Journal Review window opened."),
            "logs": ("_open_logs", "System Logs window opened."),
            "ml monitor": ("_open_ml_monitor", "ML Signal Monitor window opened."),
            "position analysis": ("_open_position_analysis_window", "Position Analysis window opened."),
            "oanda positions": ("_open_position_analysis_window", "Position Analysis window opened."),
            "documentation": ("_open_docs", "Documentation window opened."),
            "api docs": ("_open_api_docs", "API Reference window opened."),
            "about": ("_show_about", "About window opened."),
            "manual trade": ("_open_manual_trade", "Manual Trade window opened."),
            "market chat": ("_open_market_chat_window", "Sopotek Pilot window opened."),
        }
        method_name, success_message = mapping.get(target_key, (None, None))
        if not method_name or not hasattr(terminal, method_name):
            return None
        getattr(terminal, method_name)()
        return success_message

    def _available_market_chat_symbols(self):
        ordered = []
        def add_symbol(symbol):
            normalized = str(symbol or "").upper().strip()
            if normalized and normalized not in ordered:
                ordered.append(normalized)

        for symbol in list(getattr(self, "symbols", []) or []):
            add_symbol(symbol)

        broker = getattr(self, "broker", None)
        if broker is not None:
            for symbol in list(getattr(broker, "symbols", []) or []):
                add_symbol(symbol)
            markets = getattr(getattr(broker, "exchange", None), "markets", None)
            if isinstance(markets, dict):
                for symbol in markets.keys():
                    add_symbol(symbol)

        terminal = getattr(self, "terminal", None)
        current_symbol = None
        if terminal is not None and hasattr(terminal, "_current_chart_symbol"):
            try:
                current_symbol = terminal._current_chart_symbol()
            except Exception:
                current_symbol = None
        if current_symbol:
            normalized = str(current_symbol).upper().strip()
            if normalized:
                if normalized in ordered:
                    ordered.remove(normalized)
                ordered.insert(0, normalized)
        return ordered

    def _extract_market_chat_timeframe(self, question):
        lowered = str(question or "").strip().lower()
        match = re.search(r"\b(1m|3m|5m|15m|30m|45m|1h|2h|4h|6h|8h|12h|1d|3d|1w)\b", lowered)
        if match:
            return match.group(1)
        return str(getattr(self, "time_frame", "1h") or "1h").strip() or "1h"

    def _resolve_market_chat_symbol(self, question):
        text = str(question or "").strip().upper()
        if not text:
            return ""

        available = self._available_market_chat_symbols()
        available_set = set(available)
        available_compact = {
            re.sub(r"[^A-Z0-9]", "", symbol): symbol
            for symbol in available
            if str(symbol or "").strip()
        }

        for base, quote in re.findall(r"\b([A-Z0-9]{1,20})\s*[/:_-]\s*([A-Z0-9]{1,20})\b", text):
            candidate = f"{base}/{quote}"
            if candidate in available_set:
                return candidate
            compact_candidate = re.sub(r"[^A-Z0-9]", "", candidate)
            if compact_candidate in available_compact:
                return available_compact[compact_candidate]
            return candidate

        for token in re.findall(r"\b[A-Z0-9][A-Z0-9._/-]{0,23}\b", text):
            normalized_token = token.strip().upper()
            if normalized_token in available_set:
                return normalized_token
            compact_token = re.sub(r"[^A-Z0-9]", "", normalized_token)
            if compact_token in available_compact:
                return available_compact[compact_token]

        collapsed_available = {}
        for symbol in available:
            collapsed_available[re.sub(r"[^A-Z0-9]", "", symbol)] = symbol
        for token in re.findall(r"\b[A-Z0-9]{4,24}\b", text):
            if token in collapsed_available:
                return collapsed_available[token]

        base_candidates = []
        for token in re.findall(r"\b[A-Z0-9]{1,20}\b", text):
            matches = [symbol for symbol in available if symbol.startswith(f"{token}/")]
            if matches:
                ranked = self._prioritize_symbols_for_trading(matches, top_n=len(matches))
                if ranked:
                    base_candidates.append(ranked[0])
        return base_candidates[0] if base_candidates else ""

    def _should_answer_market_snapshot(self, question, symbol):
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            return False

        lowered = str(question or "").strip().lower()
        if not lowered:
            return False

        blocked_tokens = (
            "trade ",
            "cancel order",
            "cancel orders",
            "close position",
            "open settings",
            "open system health",
            "open recommendations",
            "open performance",
            "open quant pm",
            "open logs",
            "open ml monitor",
            "open position analysis",
            "take screenshot",
            "capture screenshot",
            "telegram",
        )
        if any(token in lowered for token in blocked_tokens):
            return False

        snapshot_tokens = (
            "price",
            "quote",
            "scan",
            "technical",
            "analysis",
            "analyze",
            "analyse",
            "trend",
            "rsi",
            "ema",
            "support",
            "resistance",
            "snapshot",
            "market",
            "what about",
            "how is",
            "what do you think",
        )
        if any(token in lowered for token in snapshot_tokens):
            return True

        compact_question = re.sub(r"[^a-z0-9]", "", lowered)
        compact_symbol = normalized_symbol.lower().replace("/", "")
        if compact_question in {compact_symbol, normalized_symbol.lower().replace("/", ""), normalized_symbol.lower()}:
            return True

        explicit_pair = normalized_symbol.lower() in lowered or compact_symbol in compact_question
        return explicit_pair and len(lowered.split()) <= 4

    @staticmethod
    def _market_chat_rsi(close_series, period=14):
        if close_series is None or len(close_series) < 2:
            return None
        delta = close_series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        last_gain = float(avg_gain.iloc[-1]) if len(avg_gain) else 0.0
        last_loss = float(avg_loss.iloc[-1]) if len(avg_loss) else 0.0
        if last_loss <= 0:
            if last_gain <= 0:
                return 50.0
            return 100.0
        rs = last_gain / last_loss
        return 100.0 - (100.0 / (1.0 + rs))

    async def market_chat_market_snapshot(self, symbol, timeframe=None):
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            return None

        resolved_timeframe = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        tick = await self._safe_fetch_ticker(normalized_symbol)
        candles = await self._safe_fetch_ohlcv(normalized_symbol, timeframe=resolved_timeframe, limit=120)

        if not isinstance(candles, list) or not candles:
            if isinstance(tick, dict):
                last_price = float(tick.get("price") or tick.get("last") or tick.get("bid") or tick.get("ask") or 0.0)
                if last_price > 0:
                    bid = float(tick.get("bid") or 0.0)
                    ask = float(tick.get("ask") or 0.0)
                    spread_pct = ((ask - bid) / last_price * 100.0) if bid > 0 and ask > 0 and last_price > 0 else None
                    lines = [
                        f"{normalized_symbol} snapshot ({resolved_timeframe})",
                        f"Last: {last_price:,.4f}",
                    ]
                    if bid > 0 and ask > 0:
                        spread_line = f"Bid/Ask: {bid:,.4f} / {ask:,.4f}"
                        if spread_pct is not None:
                            spread_line += f" | Spread: {spread_pct:.3f}%"
                        lines.append(spread_line)
                    lines.append("Technical scan is unavailable because candle history could not be loaded yet.")
                    return "\n".join(lines)
            return (
                f"I couldn't pull a live {normalized_symbol} snapshot right now. "
                f"Market data status: {self.get_market_stream_status()}."
            )

        frame = pd.DataFrame(candles)
        if frame.shape[1] < 6:
            return f"{normalized_symbol} data loaded, but the candle format is incomplete for analysis."
        frame = frame.iloc[:, :6].copy()
        frame.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["high", "low", "close"])
        if frame.empty:
            return f"{normalized_symbol} candle history is currently empty after cleanup."

        closes = frame["close"]
        highs = frame["high"]
        lows = frame["low"]
        latest_close = float(closes.iloc[-1])

        bid = ask = 0.0
        if isinstance(tick, dict):
            bid = float(tick.get("bid") or 0.0)
            ask = float(tick.get("ask") or 0.0)
            tick_last = float(tick.get("price") or tick.get("last") or 0.0)
            if tick_last > 0:
                latest_close = tick_last

        ema_fast = float(closes.ewm(span=min(20, max(len(closes), 2)), adjust=False).mean().iloc[-1])
        ema_slow_span = 50 if len(closes) >= 50 else max(21, min(len(closes), 50))
        ema_slow = float(closes.ewm(span=ema_slow_span, adjust=False).mean().iloc[-1])
        rsi = self._market_chat_rsi(closes, period=14)

        window = min(20, len(frame))
        support = float(lows.tail(window).min())
        resistance = float(highs.tail(window).max())

        previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else latest_close
        change_pct = ((latest_close - previous_close) / previous_close * 100.0) if previous_close else 0.0

        if latest_close >= ema_fast >= ema_slow:
            trend = "Bullish"
        elif latest_close <= ema_fast <= ema_slow:
            trend = "Bearish"
        else:
            trend = "Mixed"

        lines = [f"{normalized_symbol} snapshot ({resolved_timeframe})", f"Last: {latest_close:,.4f} | Change: {change_pct:+.2f}%"]
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / latest_close * 100.0) if latest_close > 0 else 0.0
            lines.append(f"Bid/Ask: {bid:,.4f} / {ask:,.4f} | Spread: {spread_pct:.3f}%")
        lines.append(f"Trend: {trend} | EMA20: {ema_fast:,.4f} | EMA50: {ema_slow:,.4f}")
        if rsi is not None:
            lines.append(f"RSI14: {float(rsi):.1f}")
        lines.append(f"Support/Resistance ({window} candles): {support:,.4f} / {resistance:,.4f}")
        return "\n".join(lines)

    async def handle_market_chat_action(self, question):
        lowered = str(question or "").strip().lower()
        if not lowered:
            return None

        if lowered in {"help", "commands", "show commands", "list commands"} or any(
                token in lowered
                for token in (
                        "what can you do",
                        "what can sopotek pilot do",
                        "how do i control",
                        "manage the app",
                        "control the app",
                        "list of command",
                        "list of commands",
                        "command list",
                )
        ):
            return self.market_chat_command_guide()

        if "telegram" not in lowered and any(
                token in lowered for token in ("show app status", "show status", "app status", "system status", "status summary")
        ):
            return await self.market_chat_app_status_summary(show_panel=True)

        if any(
                token in lowered
                for token in (
                        "show bug summary",
                        "bug summary",
                        "show bugs",
                        "recent bugs",
                        "any bugs",
                        "what bugs",
                        "show error log",
                        "error log",
                        "show crash log",
                        "crash log",
                        "recent errors",
                )
        ):
            return self.market_chat_error_log_summary(open_window=True)

        window_targets = [
            ("open settings", "settings"),
            ("open preferences", "settings"),
            ("show settings", "settings"),
            ("open system health", "system health"),
            ("show system health", "system health"),
            ("open recommendations", "recommendations"),
            ("show recommendations", "recommendations"),
            ("open performance", "performance"),
            ("show performance", "performance"),
            ("open quant pm", "quant pm"),
            ("show quant pm", "quant pm"),
            ("open quant dashboard", "quant dashboard"),
            ("show quant dashboard", "quant dashboard"),
            ("open ml research", "ml research"),
            ("show ml research", "ml research"),
            ("open closed journal", "closed journal"),
            ("show closed journal", "closed journal"),
            ("open journal review", "journal review"),
            ("show journal review", "journal review"),
            ("open logs", "logs"),
            ("show logs", "logs"),
            ("open ml monitor", "ml monitor"),
            ("show ml monitor", "ml monitor"),
            ("open position analysis", "position analysis"),
            ("show position analysis", "position analysis"),
            ("open oanda positions", "oanda positions"),
            ("show oanda positions", "oanda positions"),
            ("open documentation", "documentation"),
            ("show documentation", "documentation"),
            ("open api docs", "api docs"),
            ("show api docs", "api docs"),
            ("open about", "about"),
            ("show about", "about"),
            ("open manual trade", "manual trade"),
            ("show manual trade", "manual trade"),
        ]
        for token, target in window_targets:
            if token in lowered:
                message = self.market_chat_open_window(target)
                if message:
                    return message

        terminal = getattr(self, "terminal", None)
        if terminal is not None:
            scope_match = re.search(
                r"(?:set|change|switch)\s+(?:ai\s+)?scope\s+(all|selected|selected symbol|watchlist|ranked|best ranked|top ranked)",
                lowered,
            )
            if scope_match:
                scope = self._normalize_autotrade_scope(scope_match.group(1))
                if hasattr(terminal, "_apply_autotrade_scope"):
                    terminal._apply_autotrade_scope(scope)
                    return f"AI scope set to {getattr(terminal, '_autotrade_scope_label', lambda: scope.title())()}."

            if any(
                    token in lowered
                    for token in (
                            "start ai trading",
                            "enable ai trading",
                            "turn on ai trading",
                            "start auto trading",
                            "enable auto trading",
                            "turn on auto trading",
                            "start the ai trading",
                    )
            ):
                _ok, message = self.market_chat_set_ai_trading(True)
                return message

            if any(
                    token in lowered
                    for token in (
                            "stop ai trading",
                            "disable ai trading",
                            "turn off ai trading",
                            "stop auto trading",
                            "disable auto trading",
                            "turn off auto trading",
                            "pause ai trading",
                    )
            ):
                _ok, message = self.market_chat_set_ai_trading(False)
                return message

            if any(token in lowered for token in ("activate kill switch", "engage kill switch", "emergency stop", "trigger kill switch")):
                if hasattr(terminal, "_activate_emergency_stop_async"):
                    await terminal._activate_emergency_stop_async()
                    return "Emergency kill switch engaged. Auto trading is OFF, open orders are being canceled, and tracked positions are being closed."

            if any(token in lowered for token in ("resume trading", "clear kill switch", "disable kill switch", "resume after kill switch")):
                if bool(getattr(self, "is_emergency_stop_active", lambda: False)()):
                    self.clear_emergency_stop()
                    if hasattr(terminal, "_update_kill_switch_button"):
                        terminal._update_kill_switch_button()
                    if hasattr(terminal, "_refresh_terminal"):
                        terminal._refresh_terminal()
                    return "Emergency lock cleared. Auto trading remains OFF until you enable it again."
                return "Emergency lock is not active."

            if any(token in lowered for token in ("refresh markets", "reload markets", "update markets")):
                if hasattr(terminal, "_refresh_markets"):
                    terminal._refresh_markets()
                    return "Market Watch refresh requested."

            if any(token in lowered for token in ("reload balances", "refresh balances", "reload balance", "refresh balance")):
                if hasattr(terminal, "_reload_balance"):
                    terminal._reload_balance()
                    return "Balance reload requested."

            if any(token in lowered for token in ("refresh chart", "reload chart")):
                if hasattr(terminal, "_refresh_active_chart_data"):
                    terminal._refresh_active_chart_data()
                    return "Active chart refresh requested."

            if any(token in lowered for token in ("refresh orderbook", "reload orderbook")):
                if hasattr(terminal, "_refresh_active_orderbook"):
                    terminal._refresh_active_orderbook()
                    return "Orderbook refresh requested."

        cancel_symbol_match = re.search(
            r"cancel\s+orders?\s+(?:for|on)\s+([A-Za-z0-9_:/.-]+)",
            lowered,
        )
        cancel_id_match = re.search(
            r"cancel\s+orders?\s+(?:id\s+)?([A-Za-z0-9_-]{3,})",
            lowered,
        )
        if cancel_symbol_match or ("cancel order" in lowered or "cancel orders" in lowered):
            symbol = cancel_symbol_match.group(1).upper() if cancel_symbol_match else None
            order_id = None
            if not symbol and cancel_id_match:
                token = cancel_id_match.group(1)
                if token.upper() not in {"FOR", "ON", "ALL"}:
                    order_id = token
            if "confirm" not in lowered:
                target_text = f"symbol={symbol}" if symbol else f"order_id={order_id or '?'}"
                return (
                    "Cancel-order command detected but not executed.\n"
                    "Add the word CONFIRM to execute it.\n"
                    f"Parsed target: {target_text}"
                )
            try:
                results = await self.cancel_market_chat_order(
                    order_id=order_id,
                    symbol=symbol,
                    cancel_all_for_symbol=bool(symbol),
                )
            except Exception as exc:
                return f"Cancel-order command failed: {exc}"
            count = len(results or [])
            if symbol:
                return f"Canceled {count} open order(s) for {symbol}."
            return f"Canceled order {order_id}." if count else f"No cancellation was performed for order {order_id}."

        close_match = re.search(
            r"close\s+(?:(long|short)\s+)?position\s+([A-Za-z0-9_:/.-]+)(?:\s+(?:amount|size|units)\s+([-+]?\d*\.?\d+)(?:\s+(lots?|units?))?)?",
            lowered,
        )
        if close_match:
            position_side, symbol, amount_text, quantity_mode = close_match.groups()
            if "confirm" not in lowered:
                side_text = f" side={position_side.upper()}" if position_side else ""
                mode_text = f" {quantity_mode}" if quantity_mode else ""
                return (
                    "Close-position command detected but not executed.\n"
                    "Add the word CONFIRM to execute it.\n"
                    f"Parsed target: symbol={symbol.upper()}{side_text} amount={amount_text or 'full position'}{mode_text}"
                )
            amount = float(amount_text) if amount_text else None
            try:
                try:
                    result = await self.close_market_chat_position(
                        symbol.upper(),
                        amount=amount,
                        quantity_mode=quantity_mode,
                        position_side=position_side,
                    )
                except TypeError:
                    result = await self.close_market_chat_position(
                        symbol.upper(),
                        amount=amount,
                        quantity_mode=quantity_mode,
                    )
            except Exception as exc:
                return f"Close-position command failed: {exc}"
            status = str(result.get("status") or "submitted").replace("_", " ").upper() if isinstance(result, dict) else "SUBMITTED"
            order_id = str(result.get("order_id") or result.get("id") or "-") if isinstance(result, dict) else "-"
            amount_label = f"{amount} {quantity_mode}" if amount is not None and quantity_mode else amount if amount is not None else "FULL POSITION"
            lines = [
                "Close-position command executed.\n",
                f"Symbol: {symbol.upper()}\n",
            ]
            if position_side:
                lines.append(f"Side: {position_side.upper()}\n")
            lines.extend(
                [
                    f"Amount: {amount_label}\n",
                    f"Status: {status}\n",
                    f"Order ID: {order_id}",
                ]
            )
            return "".join(lines)

        if (
                any(token in lowered for token in ("position analysis", "broker positions", "my positions", "account positions"))
                and any(token in lowered for token in ("position", "positions", "nav", "equity", "margin", "p/l", "pl"))
        ) or (
                "oanda" in lowered and any(token in lowered for token in ("position", "positions", "nav", "margin", "p/l", "pl"))
        ):
            summary = self.market_chat_position_summary(open_window=True)
            if summary:
                return summary

        if any(
                token in lowered
                for token in (
                        "quant pm",
                        "quant dashboard",
                        "portfolio allocator",
                        "capital at risk",
                        "portfolio risk dashboard",
                )
        ) and any(token in lowered for token in ("show", "open", "summary", "analysis", "analyze", "analyse")):
            summary = await self.market_chat_quant_pm_summary(open_window=True)
            if summary:
                return summary

        if any(
                token in lowered
                for token in (
                        "trade history analysis",
                        "analyze trade history",
                        "analyse trade history",
                        "trade journal analysis",
                        "review my trades",
                        "analyze my trades",
                        "analyse my trades",
                )
        ):
            return await self.market_chat_trade_history_summary(limit=400, open_window=True)

        if any(token in lowered for token in ("take screenshot", "take picture", "capture screenshot", "capture screen", "take a picture")):
            path = await self.capture_app_screenshot(prefix="market_chat")
            if path:
                return f"Screenshot captured successfully.\nPath: {path}"
            return "Unable to capture a screenshot right now."

        trade_match = re.search(
            r"(?:^|\b)trade\s+(buy|sell)\s+([A-Za-z0-9_:/.-]+)"
            r"(?:\s+(?:amount|size|units)\s+([-+]?\d*\.?\d+)(?:\s+(lots?|units?))?)?"
            r"(?:\s+type\s+(market|limit|stop_limit|stop-limit|stop\s+limit))?"
            r"(?:\s+(?:price|at)\s+([-+]?\d*\.?\d+))?"
            r"(?:\s+(?:trigger|stop_price|stoptrigger|stop_trigger|stop\s+trigger)\s+([-+]?\d*\.?\d+))?"
            r"(?:\s+(?:sl|stop|stop_loss)\s+([-+]?\d*\.?\d+))?"
            r"(?:\s+(?:tp|take_profit|takeprofit)\s+([-+]?\d*\.?\d+))?",
            lowered,
        )
        if trade_match:
            side, symbol, amount_text, quantity_mode, order_type, price_text, stop_price_text, sl_text, tp_text = trade_match.groups()
            if "confirm" not in lowered:
                mode_text = f" {quantity_mode}" if quantity_mode else ""
                return (
                    "Trade command detected but not executed.\n"
                    "Add the word CONFIRM to place it.\n"
                    f"Parsed command: side={side.upper()} symbol={symbol.upper()} amount={amount_text or '?'}{mode_text} "
                    f"type={(order_type or 'market').replace('-', '_').replace(' ', '_').upper()} "
                    f"price={price_text or '-'} trigger={stop_price_text or '-'} sl={sl_text or '-'} tp={tp_text or '-'}"
                )

            if not amount_text:
                return "Trade command needs an amount. Example: trade buy EUR/USD amount 0.01 lots confirm"

            amount = float(amount_text)
            if amount <= 0:
                return "Trade amount must be positive."

            resolved_type = (order_type or "market").strip().lower().replace("-", "_").replace(" ", "_")
            price = float(price_text) if price_text else None
            stop_price = float(stop_price_text) if stop_price_text else None
            stop_loss = float(sl_text) if sl_text else None
            take_profit = float(tp_text) if tp_text else None
            if resolved_type == "limit" and (price is None or price <= 0):
                return "Limit trade commands need a positive price."
            if resolved_type == "stop_limit":
                if price is None or price <= 0:
                    return "Stop-limit trade commands need a positive limit price."
                if stop_price is None or stop_price <= 0:
                    return "Stop-limit trade commands need a positive trigger price."

            try:
                trade_kwargs = {
                    "symbol": symbol.upper(),
                    "side": side,
                    "amount": amount,
                    "order_type": resolved_type,
                    "price": price,
                    "stop_price": stop_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                }
                if quantity_mode:
                    trade_kwargs["quantity_mode"] = quantity_mode
                order = await self.submit_market_chat_trade(**trade_kwargs)
            except Exception as exc:
                return f"Trade command failed: {exc}"

            status = str(order.get("status") or "submitted").replace("_", " ").upper()
            order_id = str(order.get("order_id") or order.get("id") or "-")
            amount_mode = str(order.get("requested_quantity_mode") or quantity_mode or "units").strip() or "units"
            applied_amount = order.get("applied_requested_mode_amount", amount)
            requested_amount = order.get("requested_amount", amount)
            sizing_summary = str(order.get("sizing_summary") or "").strip()
            ai_sizing_reason = str(order.get("ai_sizing_reason") or "").strip()
            final_symbol = str(order.get("symbol") or symbol or "").strip().upper() or str(symbol or "").strip().upper()
            final_side = str(order.get("side") or side or "").strip().upper() or str(side or "").strip().upper()
            final_type = str(order.get("type") or resolved_type or "").strip().replace("-", "_").replace(" ", "_").upper()
            review_summary = str(order.get("intervention_summary") or order.get("review_reason") or "").strip()
            requested_line = (
                f"\nRequested Amount: {requested_amount} {amount_mode}"
                if bool(order.get("size_adjusted"))
                else ""
            )
            sizing_line = f"\nSizing: {sizing_summary}" if sizing_summary else ""
            ai_line = f"\nChatGPT Size Note: {ai_sizing_reason}" if ai_sizing_reason else ""
            review_line = ""
            if review_summary:
                if bool(order.get("risk_monitoring_active")) and not bool(order.get("intervention_pending")):
                    prefix = "Risk Watch"
                else:
                    prefix = "Auto-Review Pending" if bool(order.get("intervention_pending")) else "Auto-Review"
                review_line = f"\n{prefix}: {review_summary}"
            return (
                f"Trade command executed.\n"
                f"Status: {status}\n"
                f"Symbol: {final_symbol}\n"
                f"Side: {final_side}\n"
                f"Amount: {applied_amount} {amount_mode}\n"
                f"Type: {final_type}\n"
                f"Order ID: {order_id}"
                f"{requested_line}"
                f"{sizing_line}"
                f"{ai_line}"
                f"{review_line}"
            )

        market_symbol = self._resolve_market_chat_symbol(question)
        if self._should_answer_market_snapshot(question, market_symbol):
            timeframe = self._extract_market_chat_timeframe(question)
            snapshot = await self.market_chat_market_snapshot(market_symbol, timeframe=timeframe)
            if snapshot:
                return snapshot

        if "telegram" not in lowered:
            return None

        if any(token in lowered for token in ("telegram status", "status telegram", "telegram info", "telegram summary", "manage telegram")):
            return self.telegram_management_text()

        if any(token in lowered for token in ("disable telegram", "turn off telegram", "stop telegram")):
            await self._set_telegram_enabled_state(False)
            return self.telegram_management_text() + "\n\nTelegram has been disabled."

        if any(token in lowered for token in ("enable telegram", "turn on telegram", "start telegram")):
            if not str(getattr(self, "telegram_bot_token", "") or "").strip():
                return "Telegram cannot be enabled because the bot token is not configured in Settings -> Integrations."
            if not str(getattr(self, "telegram_chat_id", "") or "").strip():
                return "Telegram cannot be enabled because the chat ID is not configured in Settings -> Integrations."
            await self._set_telegram_enabled_state(True)
            return self.telegram_management_text() + "\n\nTelegram has been enabled."

        if any(token in lowered for token in ("restart telegram", "reconnect telegram", "refresh telegram")):
            if not str(getattr(self, "telegram_bot_token", "") or "").strip():
                return "Telegram cannot be restarted because the bot token is not configured."
            await self._restart_telegram_service()
            return self.telegram_management_text() + "\n\nTelegram restart requested."

        if any(token in lowered for token in ("test telegram", "send telegram test", "telegram test message")):
            if not str(getattr(self, "telegram_bot_token", "") or "").strip():
                return "Telegram test failed because the bot token is not configured."
            if not str(getattr(self, "telegram_chat_id", "") or "").strip():
                return "Telegram test failed because the chat ID is not configured."
            if not getattr(self, "telegram_enabled", False):
                await self._set_telegram_enabled_state(True)
            sent = await self.send_test_telegram_message()
            if sent:
                return self.telegram_management_text() + "\n\nTest message sent to Telegram."
            return self.telegram_management_text() + "\n\nTelegram test message could not be sent."

        return None

    def _autotrade_symbol_pools(self, available_symbols=None, catalog_symbols=None):
        available = self._normalize_symbol_sequence(
            getattr(self, "symbols", []) if available_symbols is None else available_symbols
        )
        if catalog_symbols is None:
            catalog = self._normalize_symbol_sequence(
                (getattr(self, "_symbol_universe_tiers", {}) or {}).get("catalog", [])
            )
            if not catalog:
                broker_symbols = getattr(getattr(self, "broker", None), "symbols", None)
                catalog = self._normalize_symbol_sequence(broker_symbols or available)
        else:
            catalog = self._normalize_symbol_sequence(catalog_symbols)

        merged_catalog = []
        for source in (available, catalog):
            for symbol in source:
                if symbol and symbol not in merged_catalog:
                    merged_catalog.append(symbol)
        return available, merged_catalog or list(available)

    def _best_ranked_autotrade_symbols(
            self,
            available_symbols=None,
            catalog_symbols=None,
            broker_type=None,
            exchange=None,
            limit=None,
    ):
        available, catalog = self._autotrade_symbol_pools(
            available_symbols=available_symbols,
            catalog_symbols=catalog_symbols,
        )
        candidates = list(catalog or available)
        if not candidates:
            return []

        policy = self._symbol_universe_policy(broker_type=broker_type, exchange=exchange)
        resolved_limit = int(limit or policy.get("auto_assignment_limit", 0) or 0)
        if resolved_limit <= 0:
            resolved_limit = len(candidates)

        scored = []
        for index, symbol in enumerate(candidates):
            ranked_rows = self.ranked_strategies_for_symbol(symbol)
            top_row = ranked_rows[0] if ranked_rows else {}
            scored.append(
                {
                    "symbol": symbol,
                    "index": index,
                    "ranked": bool(ranked_rows),
                    "score": float(top_row.get("score", 0.0) or 0.0),
                    "sharpe_ratio": float(top_row.get("sharpe_ratio", 0.0) or 0.0),
                    "total_profit": float(top_row.get("total_profit", 0.0) or 0.0),
                    "win_rate": float(top_row.get("win_rate", 0.0) or 0.0),
                }
            )

        ranked_symbols = []
        if any(item["ranked"] for item in scored):
            ranked_symbols = [
                item["symbol"]
                for item in sorted(
                    [item for item in scored if item["ranked"]],
                    key=lambda item: (
                        -item["score"],
                        -item["sharpe_ratio"],
                        -item["total_profit"],
                        -item["win_rate"],
                        item["index"],
                    ),
                )
            ]

        fallback_source = self._prioritize_symbols_for_trading(
            available or candidates,
            top_n=len(available or candidates),
            )
        resolved = []
        for source in (ranked_symbols, fallback_source, candidates):
            for symbol in source:
                if symbol and symbol not in resolved:
                    resolved.append(symbol)
                if len(resolved) >= resolved_limit:
                    return resolved
        return resolved[:resolved_limit]

    def get_best_ranked_autotrade_symbols(
            self,
            available_symbols=None,
            catalog_symbols=None,
            broker_type=None,
            exchange=None,
            limit=None,
    ):
        return self._best_ranked_autotrade_symbols(
            available_symbols=available_symbols,
            catalog_symbols=catalog_symbols,
            broker_type=broker_type,
            exchange=exchange,
            limit=limit,
        )

    def set_autotrade_scope(self, scope):
        normalized = self._normalize_autotrade_scope(scope)
        self.autotrade_scope = normalized
        self.settings.setValue("autotrade/scope", normalized)
        self._sync_session_scoped_state()

    def set_autotrade_watchlist(self, symbols):
        normalized = sorted(
            {
                self._normalize_market_data_symbol(symbol)
                for symbol in (symbols or [])
                if str(symbol).strip()
            }
        )
        broker_type = self._active_broker_type()
        exchange_code = self._active_exchange_code()
        if broker_type or exchange_code:
            normalized = self._filter_symbols_for_trading(normalized, broker_type, exchange=exchange_code)
        self.autotrade_watchlist = set(normalized)
        self.settings.setValue("autotrade/watchlist", json.dumps(normalized))
        self._refresh_symbol_universe_tiers()
        self._sync_session_scoped_state()

    def _current_autotrade_selected_symbol(self):
        terminal = getattr(self, "terminal", None)
        if terminal is not None:
            current_chart_symbol = None
            if hasattr(terminal, "_current_chart_symbol"):
                try:
                    current_chart_symbol = terminal._current_chart_symbol()
                except Exception:
                    current_chart_symbol = None
            if current_chart_symbol:
                return str(current_chart_symbol).upper().strip()

            picker = getattr(terminal, "symbol_picker", None)
            if picker is not None:
                try:
                    symbol = picker.currentText()
                except Exception:
                    symbol = ""
                if symbol:
                    return str(symbol).upper().strip()

        for symbol in getattr(self, "symbols", []) or []:
            if symbol:
                return str(symbol).upper().strip()
        return ""

    def is_symbol_enabled_for_autotrade(
            self,
            symbol,
            *,
            available_symbols=None,
            catalog_symbols=None,
            selected_symbol=None,
            broker_type=None,
            exchange=None,
    ):
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return False

        available, catalog = self._autotrade_symbol_pools(
            available_symbols=available_symbols,
            catalog_symbols=catalog_symbols,
        )
        available_set = set(available)
        catalog_set = set(catalog or available)
        scope = self._normalize_autotrade_scope(getattr(self, "autotrade_scope", "all"))
        if scope == "selected":
            current_selected = str(
                selected_symbol if selected_symbol is not None else self._current_autotrade_selected_symbol()
            ).upper().strip()
            return bool(current_selected) and normalized == current_selected and normalized in catalog_set
        if scope == "watchlist":
            return normalized in set(getattr(self, "autotrade_watchlist", set()) or set()) and normalized in catalog_set
        if scope == "ranked":
            ranked_symbols = self._best_ranked_autotrade_symbols(
                available_symbols=available,
                catalog_symbols=catalog,
                broker_type=broker_type,
                exchange=exchange,
            )
            return normalized in set(ranked_symbols)
        return normalized in available_set

    def get_active_autotrade_symbols(
            self,
            *,
            available_symbols=None,
            catalog_symbols=None,
            selected_symbol=None,
            broker_type=None,
            exchange=None,
    ):
        available, catalog = self._autotrade_symbol_pools(
            available_symbols=available_symbols,
            catalog_symbols=catalog_symbols,
        )
        if not available and not catalog:
            return []

        scope = self._normalize_autotrade_scope(getattr(self, "autotrade_scope", "all"))
        if scope == "selected":
            selected = str(
                selected_symbol if selected_symbol is not None else self._current_autotrade_selected_symbol()
            ).upper().strip()
            candidate_pool = set(catalog or available)
            return [selected] if selected and selected in candidate_pool else []
        if scope == "watchlist":
            watchlist = set(getattr(self, "autotrade_watchlist", set()) or set())
            return [symbol for symbol in (catalog or available) if symbol in watchlist]
        if scope == "ranked":
            return self._best_ranked_autotrade_symbols(
                available_symbols=available,
                catalog_symbols=catalog,
                broker_type=broker_type,
                exchange=exchange,
            )
        return available

    async def _start_market_stream(self):
        exchange = (self.config.broker.exchange or "").lower() if self.config and self.config.broker else ""

        if exchange == "stellar":
            self.ws_manager = None
            self.logger.info("Using polling market data for Stellar Horizon")
            await self._start_ticker_polling()
            return

        if exchange == "solana":
            self.ws_manager = None
            self.logger.info("Using polling market data for Solana DEX")
            await self._start_ticker_polling()
            return

        try:
            self.ws_bus = EventBus()
            self.ws_bus.subscribe(EventType.MARKET_TICK, self._on_ws_market_tick)

            ws_client = self._build_ws_client(exchange)
            if ws_client is None:
                self.ws_manager = None
                await self._start_ticker_polling()
                return

            self.ws_manager = ws_client
            self._ws_bus_task = self._create_task(self.ws_bus.start(), "ws_event_bus")
            self._ws_task = self._create_task(ws_client.connect(), "ws_connect")

            def _ws_done(t):
                try:
                    exc = t.exception()
                    if exc:
                        self.logger.error("WebSocket stream failed: %s", exc)
                        self._create_task(self._start_ticker_polling(), "ticker_poll_fallback")
                except asyncio.CancelledError:
                    pass

            self._ws_task.add_done_callback(_ws_done)

            if self._ticker_task and not self._ticker_task.done():
                self._ticker_task.cancel()
                self._ticker_task = None

            self.logger.info("WebSocket market data enabled for %s", exchange)

        except Exception as e:
            self.logger.error("WebSocket init failed for %s: %s. Falling back to polling.", exchange, e)
            await self._start_ticker_polling()

    def _build_ws_client(self, exchange):
        symbols = self.symbols[:50]

        if exchange.startswith("binance"):
            return BinanceUsWebSocket(symbols=symbols, event_bus=self.ws_bus, exchange_name=exchange)

        if exchange == "coinbase":
            products = [s.replace("/", "-") for s in symbols]
            return CoinbaseWebSocket(symbols=products, event_bus=self.ws_bus)

        if exchange == "alpaca":
            broker_cfg = getattr(self, "config", None)
            broker_cfg = getattr(broker_cfg, "broker", None)
            options = dict(getattr(broker_cfg, "options", None) or {})
            params = dict(getattr(broker_cfg, "params", None) or {})
            return AlpacaWebSocket(
                api_key=self.config.broker.api_key,
                secret_key=self.config.broker.secret,
                symbols=symbols,
                event_bus=self.ws_bus,
                feed=options.get("market_data_feed") or params.get("market_data_feed") or "iex",
                sandbox=bool(getattr(getattr(self, "broker", None), "paper", False)),
                max_symbols=options.get("alpaca_ws_symbol_limit") or params.get("alpaca_ws_symbol_limit"),
            )

        if exchange == "oanda":
            broker_cfg = getattr(getattr(self, "config", None), "broker", None)
            broker_obj = getattr(self, "broker", None)
            token = (
                    getattr(broker_cfg, "api_key", None)
                    or getattr(broker_cfg, "token", None)
                    or getattr(broker_obj, "token", None)
            )
            account_id = getattr(broker_cfg, "account_id", None) or getattr(broker_obj, "account_id", None)
            mode = getattr(broker_cfg, "mode", None) or getattr(broker_obj, "mode", "practice")
            if not token or not account_id:
                self.logger.warning("Oanda live stream requires both API token and account ID; falling back to polling.")
                return None
            return OandaWebSocket(
                token=token,
                account_id=account_id,
                symbols=symbols,
                event_bus=self.ws_bus,
                mode=mode,
            )

        if exchange == "paper":
            return PaperWebSocket(broker=self.broker, symbols=symbols, event_bus=self.ws_bus, interval=1.0)

        return None

    async def _on_ws_market_tick(self, event):
        """Handle incoming WebSocket market tick events.

        - Validates data structure and required symbol field.
        - Normalizes bid/ask fallback to last price when missing.
        - Updates ticker stream/buffer and emits ticker signal for UI updates.
        """
        try:
            data = event.data if hasattr(event, "data") else None
            if not isinstance(data, dict):
                return

            symbol = data.get("symbol")
            if not symbol:
                return

            data = self._prepare_ticker_snapshot(symbol, data)
            normalized_symbol = self._normalize_market_data_symbol(data.get("symbol") or symbol) or str(symbol).strip().upper()
            bid = float(data.get("bid") or data.get("bp") or 0)
            ask = float(data.get("ask") or data.get("ap") or 0)
            last = float(data.get("price") or data.get("last") or 0)

            # Ensure we have non-zero bid/ask values, else use last price.
            if bid == 0 and ask == 0:
                bid = last
                ask = last

            self.ticker_stream.update(normalized_symbol, data)
            self.ticker_buffer.update(normalized_symbol, data)
            self.ticker_signal.emit(normalized_symbol, bid, ask)

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            # Do not interrupt stream processing for a single bad message.
            self.logger.error("WS tick handling error: %s", e)

    async def _start_ticker_polling(self):
        """Ensure polling loop task is scheduled and single-instance.

        Cancels existing ticker polling task before creating a new one.
        """
        if self._ticker_task and not self._ticker_task.done():
            self._ticker_task.cancel()

        self._ticker_task = self._create_task(self._ticker_loop(), "ticker_poll")

    async def _ticker_loop(self):
        """Polling loop that updates ticker data for active symbols.

        - Uses different polling cadence for Stellar due to rate limits.
        - Uses broker-specific fetch methods in _safe_fetch_ticker.
        - Emits ticker updates through ticker_signal for UI/logic consumers.
        """
        # Default in case an exception occurs before broker_name is set.
        broker_name = "unknown"

        while self.connected and self.broker is not None:
            try:
                broker_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").lower()
                if broker_name == "stellar":
                    max_symbols = 10
                    sleep_seconds = 4.0
                elif broker_name == "solana":
                    max_symbols = 12
                    sleep_seconds = 3.0
                elif broker_name == "coinbase":
                    max_symbols = self.COINBASE_TICKER_POLL_LIMIT
                    sleep_seconds = self.COINBASE_TICKER_POLL_SECONDS
                elif broker_name in SPOT_ONLY_EXCHANGES:
                    max_symbols = 12
                    sleep_seconds = 1.5
                else:
                    max_symbols = 30
                    sleep_seconds = 1.0

                for symbol in self.symbols[:max_symbols]:
                    # Fetch latest ticker safely based on broker API availability.
                    ticker = await self._safe_fetch_ticker(symbol)
                    if not isinstance(ticker, dict):
                        continue
                    ticker = self._prepare_ticker_snapshot(symbol, ticker)

                    bid = float(ticker.get("bid") or ticker.get("bidPrice") or ticker.get("bp") or 0)
                    ask = float(ticker.get("ask") or ticker.get("askPrice") or ticker.get("ap") or 0)
                    last = float(ticker.get("last") or ticker.get("price") or 0)

                    # If both bid/ask are missing, fallback to last price to avoid zero spreads.
                    if bid == 0 and ask == 0:
                        bid = last
                        ask = last

                    self.ticker_stream.update(symbol, ticker)
                    self.ticker_buffer.update(symbol, ticker)

                    self.ticker_signal.emit(symbol, bid, ask)
                    
                    # Check SL/TP on ticker update
                    self._check_and_close_sl_tp_on_ticker(symbol, bid, ask)

                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except (TypeError, ValueError, RuntimeError, OSError) as e:
                # Keep running and fall back to a safe sleep interval based on broker type.
                self.logger.error("Ticker polling error: %s", e)
                await asyncio.sleep(4.0 if broker_name in {"stellar", "solana"} else 1.0)

    def _cached_ticker_snapshot(self, symbol):
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            return None

        stream = getattr(self, "ticker_stream", None)
        if stream is not None and hasattr(stream, "get"):
            try:
                cached = stream.get(normalized_symbol) or stream.get(symbol)
            except Exception:
                cached = None
            if isinstance(cached, dict):
                return dict(cached)

        buffer = getattr(self, "ticker_buffer", None)
        if buffer is not None and hasattr(buffer, "latest"):
            try:
                cached = buffer.latest(normalized_symbol) or buffer.latest(symbol)
            except Exception:
                cached = None
            if isinstance(cached, dict):
                return dict(cached)

        return None

    def _is_transient_market_data_error(self, exc):
        if isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError, OSError)):
            return True
        message = str(exc or "").strip().lower()
        return any(
            token in message
            for token in (
                "getaddrinfo failed",
                "cannot connect to host",
                "name or service not known",
                "temporary failure in name resolution",
                "network is unreachable",
                "connection refused",
                "connection reset",
                "host is unreachable",
                "cannot write to closing transport",
                "session is closed",
                "connector is closed",
                "server disconnected",
            )
        )

    def _is_reconnecting_market_data_error(self, exc):
        message = str(exc or "").strip().lower()
        return any(
            token in message
            for token in (
                "cannot write to closing transport",
                "session is closed",
                "connector is closed",
                "server disconnected",
            )
        )

    def _is_unsupported_market_symbol_error(self, exc):
        name = str(getattr(getattr(exc, "__class__", None), "__name__", "") or "").strip().lower()
        message = str(exc or "").strip().lower()
        if "badsymbol" in name:
            return True
        return any(
            token in message
            for token in (
                "does not have market symbol",
                "unknown symbol",
                "invalid symbol",
                "symbol not found",
                "unsupported symbol",
            )
        )

    @staticmethod
    def _looks_like_native_contract_symbol(symbol):
        text = str(symbol or "").strip().upper()
        if not text or "/" in text or "_" in text:
            return False
        if "PERP" in text:
            return True
        return bool(
            re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
            or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
        )

    @staticmethod
    def _normalize_market_data_symbol(symbol):
        text = str(symbol or "").strip().upper()
        if AppController._looks_like_native_contract_symbol(text):
            return text
        return text.replace("_", "/").replace("-", "/")

    @staticmethod
    def _symbol_leg_has_alpha(value):
        return bool(re.search(r"[A-Z]", str(value or "").upper()))

    def _is_plausible_market_symbol(self, symbol, broker_type=None, exchange=None):
        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if not normalized_symbol:
            return False
        if " " in normalized_symbol:
            return False
        if "/" not in normalized_symbol:
            return True

        base, quote_segment = normalized_symbol.split("/", 1)
        quote, settle = (quote_segment.split(":", 1) + [""])[:2]

        for leg in (base, quote):
            if not leg or not re.fullmatch(r"[A-Z0-9]{2,20}", leg):
                return False
            if not self._symbol_leg_has_alpha(leg):
                return False

        if settle:
            if not re.fullmatch(r"[A-Z0-9]{2,20}", settle):
                return False
            if not self._symbol_leg_has_alpha(settle):
                return False

        return True

    def _log_invalid_market_symbol(self, symbol):
        normalized_symbol = self._normalize_market_data_symbol(symbol) or str(symbol or "").strip()
        if not normalized_symbol:
            return
        self._log_market_data_warning_once(
            f"invalid-symbol:{normalized_symbol}",
            (
                f"Ignoring malformed market symbol {normalized_symbol}. "
                "The app will skip scans and live market data for this symbol until a valid market is selected."
            ),
            interval_seconds=120.0,
        )

    def _broker_supports_market_symbol(self, symbol):
        normalized_symbol = self._normalize_market_data_symbol(symbol)
        if not normalized_symbol:
            return False
        if not self._is_plausible_market_symbol(normalized_symbol):
            return False

        broker = getattr(self, "broker", None)
        if broker is None:
            return False

        supports_symbol = getattr(broker, "supports_symbol", None)
        if callable(supports_symbol):
            try:
                return bool(supports_symbol(normalized_symbol))
            except Exception:
                pass

        symbols = getattr(broker, "symbols", None)
        if isinstance(symbols, (list, tuple, set)):
            normalized_symbols = {
                self._normalize_market_data_symbol(item)
                for item in symbols
                if str(item or "").strip()
            }
            if normalized_symbols:
                return normalized_symbol in normalized_symbols

        return True

    def _log_unsupported_market_symbol(self, broker_name, symbol):
        normalized_symbol = self._normalize_market_data_symbol(symbol) or str(symbol or "").strip()
        market_label = broker_name.upper() if broker_name else "BROKER"
        self._log_market_data_warning_once(
            f"unsupported-symbol:{broker_name}:{normalized_symbol}",
            (
                f"{market_label} does not support market symbol {normalized_symbol} on the active broker. "
                "The app will skip live market data for this symbol until you switch to a supported market."
            ),
            interval_seconds=120.0,
        )

    def _log_market_data_warning_once(self, key, message, *, interval_seconds=60.0):
        timestamps = getattr(self, "_market_data_warning_timestamps", None)
        if not isinstance(timestamps, dict):
            timestamps = {}
            self._market_data_warning_timestamps = timestamps

        now = time.monotonic()
        interval_value = max(1.0, float(interval_seconds or 60.0))
        last_logged = float(timestamps.get(key, 0.0) or 0.0)
        if (now - last_logged) < interval_value:
            return

        timestamps[key] = now
        self.logger.warning(message)

        terminal = getattr(self, "terminal", None)
        system_console = getattr(terminal, "system_console", None)
        if system_console is not None and hasattr(system_console, "log"):
            try:
                system_console.log(message, level="WARN")
            except Exception:
                pass

    def _trim_application_caches(self):
        """Periodically trim application caches to prevent unbounded memory growth.

        This method is called by a QTimer (every 5 minutes) to clean up:
        - Stale market data warning timestamps
        - Old news cache entries
        - Oversized trade close entry cache
        - Stale strategy feedback cache entries
        """
        try:
            now = time.monotonic()

            # Trim market data warning timestamps: keep only recent (< 24 hours)
            timestamps = getattr(self, "_market_data_warning_timestamps", None)
            if isinstance(timestamps, dict):
                stale_cutoff = now - (24 * 3600)
                stale_keys = [k for k, v in timestamps.items() if float(v or 0) < stale_cutoff]
                for key in stale_keys:
                    timestamps.pop(key, None)

            # Trim news cache: keep only recent entries
            news_cache = getattr(self, "_news_cache", None)
            if isinstance(news_cache, dict):
                # Keep last 1000 news entries
                if len(news_cache) > 1000:
                    sorted_keys = sorted(
                        news_cache.keys(),
                        key=lambda k: news_cache[k].get("timestamp", 0),
                        reverse=True
                    )
                    keys_to_remove = sorted_keys[1000:]
                    for key in keys_to_remove:
                        news_cache.pop(key, None)

            # Trim trade close entry cache: keep only recent
            cache = getattr(self, "_trade_close_entry_cache", None)
            if isinstance(cache, dict) and len(cache) > 100:
                sorted_keys = sorted(cache.keys(), reverse=True)
                keys_to_remove = sorted_keys[100:]
                for key in keys_to_remove:
                    cache.pop(key, None)

        except Exception:
            pass

    def _check_and_close_sl_tp_on_ticker(self, symbol: str, bid: float, ask: float) -> None:
        """Check if any positions hit SL/TP and close them.

        This method is called on each ticker update to check if open positions
        should be closed due to stop loss or take profit being hit.
        """
        if self._position_manager is None:
            return

        normalized_symbol = str(symbol or "").strip().upper()
        mid_price = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid if bid > 0 else ask

        # Update the current price for this symbol
        trade = self._position_manager.get_open_trade(normalized_symbol)
        if trade is not None and mid_price > 0:
            trade.current_price = mid_price

            # Check if position should close
            if trade.should_close_for_tp():
                self._emit_sl_tp_triggered_event(normalized_symbol, trade, "take_profit", mid_price)
                self._position_manager.close_trade(normalized_symbol, reason="take_profit_hit", exit_price=mid_price)
            elif trade.should_close_for_sl():
                self._emit_sl_tp_triggered_event(normalized_symbol, trade, "stop_loss", mid_price)
                self._position_manager.close_trade(normalized_symbol, reason="stop_loss_hit", exit_price=mid_price)

    def _emit_sl_tp_triggered_event(self, symbol: str, trade: Any, trigger_type: str, close_price: float) -> None:
        """Emit an event when SL or TP is triggered.

        Triggers:
        - Event bus notification
        - Terminal UI update
        - Trade notifications (email, SMS, Telegram)
        """
        try:
            event_type = "trade_take_profit_hit" if trigger_type == "take_profit" else "trade_stop_loss_hit"
            pnl = trade.pnl if hasattr(trade, "pnl") else 0.0

            # Emit to event bus
            event_data = {
                "symbol": symbol,
                "trigger_type": trigger_type,
                "close_price": close_price,
                "pnl": pnl,
                "trade_id": getattr(trade, "trade_id", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.event_bus.emit(EventType.CUSTOM, event_data)

            # Update terminal if available
            terminal = getattr(self, "terminal", None)
            if terminal is not None and hasattr(terminal, "_schedule_positions_refresh"):
                try:
                    terminal._schedule_positions_refresh()
                except Exception:
                    pass

            # Send notifications
            self._send_sl_tp_notification(symbol, trigger_type, close_price, pnl)

        except Exception as e:
            self.logger.error(f"Error emitting SL/TP event: {e}")

    def _send_sl_tp_notification(self, symbol: str, trigger_type: str, close_price: float, pnl: float) -> None:
        """Send notifications for SL/TP triggered events."""
        try:
            if not bool(getattr(self, "trade_close_notifications_enabled", False)):
                return

            trigger_label = "Take Profit" if trigger_type == "take_profit" else "Stop Loss"
            message = f"{symbol}: {trigger_label} triggered at {close_price:.6f}, P/L: {pnl:.2f}"

            # Telegram
            if bool(getattr(self, "trade_close_notify_telegram", False)):
                telegram_service = getattr(self, "telegram_service", None)
                if telegram_service is not None and hasattr(telegram_service, "send_notification"):
                    try:
                        telegram_service.send_notification(message)
                    except Exception:
                        pass

            # Email
            if bool(getattr(self, "trade_close_notify_email", False)):
                email_service = getattr(self, "email_trade_notification_service", None)
                if email_service is not None and hasattr(email_service, "send_trade_notification"):
                    try:
                        email_service.send_trade_notification(
                            subject=f"{trigger_label} Hit: {symbol}",
                            body=message,
                        )
                    except Exception:
                        pass

            # SMS
            if bool(getattr(self, "trade_close_notify_sms", False)):
                sms_service = getattr(self, "sms_trade_notification_service", None)
                if sms_service is not None and hasattr(sms_service, "send_trade_notification"):
                    try:
                        sms_service.send_trade_notification(message)
                    except Exception:
                        pass

        except Exception as e:
            self.logger.debug(f"Error sending SL/TP notification: {e}")

    def _initialize_position_in_manager(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        **kwargs
    ) -> None:
        """Register a position with the position manager.

        This should be called when a new order fills or position is opened.
        """
        if self._position_manager is None:
            return

        try:
            self._position_manager.open_trade(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                **{k: v for k, v in kwargs.items() if k not in {"symbol", "quantity", "entry_price", "stop_loss", "take_profit"}},
            )
        except Exception as e:
            self.logger.debug(f"Error initializing position in manager for {symbol}: {e}")

    async def _safe_fetch_ticker(self, symbol):
        """Return normalized ticker updates from broker, with fallbacks.

        This handles brokers that have either fetch_ticker or fetch_price and
        ensures the app has a consistent dict representation for ticker updates.
        """
        if not self.broker:
            return None

        requested_symbol = self._normalize_market_data_symbol(symbol)
        normalized_symbol = self._resolve_preferred_market_symbol(requested_symbol) or requested_symbol
        if not normalized_symbol:
            return None
        if not self._is_plausible_market_symbol(normalized_symbol):
            self._log_invalid_market_symbol(normalized_symbol)
            return None

        broker_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").strip().lower()
        network_label = (
            "Stellar Horizon"
            if broker_name == "stellar"
            else ("Solana DEX" if broker_name == "solana" else (broker_name.upper() if broker_name else "Market data"))
        )

        if not self._broker_supports_market_symbol(normalized_symbol):
            self._log_unsupported_market_symbol(broker_name, normalized_symbol)
            return None

        # Primary path: use broker's native fetch_ticker call when available.
        if hasattr(self.broker, "fetch_ticker"):
            try:
                tick = await self.broker.fetch_ticker(normalized_symbol)
                if isinstance(tick, dict):
                    return self._cache_ticker_snapshot(normalized_symbol, tick)
            except (TypeError, ValueError, RuntimeError, AttributeError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if self._is_transient_market_data_error(exc):
                    cached_tick = self._cached_ticker_snapshot(normalized_symbol) or self._cached_ticker_snapshot(symbol)
                    if isinstance(cached_tick, dict):
                        self._log_market_data_warning_once(
                            f"ticker-cache:{broker_name}:{str(symbol or '').upper().strip()}",
                            f"{network_label} is temporarily unreachable for {symbol}. Using cached ticker data while the connection recovers.",
                            interval_seconds=45.0 if broker_name in {"stellar", "solana"} else 30.0,
                        )
                        return cached_tick

                    reconnecting = self._is_reconnecting_market_data_error(exc)
                    self._log_market_data_warning_once(
                        f"ticker-offline:{broker_name}",
                        (
                            f"{network_label} session is reconnecting after a transport shutdown. "
                            "The app will retry automatically."
                        )
                        if reconnecting
                        else f"{network_label} is temporarily unreachable ({exc}). The app will keep retrying automatically.",
                        interval_seconds=60.0 if broker_name in {"stellar", "solana"} else 30.0,
                    )
                    return None
                self.logger.debug("Ticker fetch failed for %s: %s", symbol, exc)
            except Exception as exc:
                if self._is_unsupported_market_symbol_error(exc):
                    self._log_unsupported_market_symbol(broker_name, normalized_symbol)
                    return None
                self.logger.debug("Ticker fetch failed for %s: %s", symbol, exc)

        # Secondary fallback: if only fetch_price is available, synthesize bid/ask.
        if hasattr(self.broker, "fetch_price"):
            try:
                price = await self.broker.fetch_price(normalized_symbol)
                if price is None:
                    return None
                price = float(price)
                return self._cache_ticker_snapshot(normalized_symbol, {
                    "symbol": normalized_symbol,
                    "price": price,
                    "bid": price * 0.9998,
                    "ask": price * 1.0002,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "_received_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as exc:
                if self._is_unsupported_market_symbol_error(exc):
                    self._log_unsupported_market_symbol(broker_name, normalized_symbol)
                    return None
                self.logger.debug("Price fetch failed for %s: %s", symbol, exc)

        return None

    async def evaluate_live_readiness_report_async(self, symbol=None, timeframe=None):
        normalized_symbol = self._primary_runtime_symbol(symbol)
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        if normalized_symbol:
            try:
                await self._assess_trade_market_data_guard(normalized_symbol, timeframe=timeframe_value)
            except Exception:
                self.logger.debug(
                    "Async live readiness warmup failed for %s %s",
                    normalized_symbol,
                    timeframe_value,
                    exc_info=True,
                )
        return self.get_live_readiness_report(symbol=normalized_symbol, timeframe=timeframe_value)

    def _normalize_public_trade_rows(self, symbol, rows, limit=40):
        normalized = []
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue

            price = self._normalize_history_float(
                raw.get("price") or raw.get("rate") or raw.get("last")
            )
            amount = self._normalize_history_float(
                raw.get("amount")
                or raw.get("size")
                or raw.get("qty")
                or raw.get("quantity")
                or raw.get("volume")
            )
            cost = self._normalize_history_float(
                raw.get("cost") or raw.get("notional") or raw.get("quoteVolume")
            )

            if cost is None and price is not None and amount is not None:
                cost = price * amount

            if price is None and cost is None:
                continue

            side = str(raw.get("side") or raw.get("taker_side") or raw.get("direction") or "").strip().lower()
            timestamp = (
                    raw.get("datetime")
                    or raw.get("timestamp")
                    or raw.get("time")
                    or raw.get("created_at")
            )

            normalized.append(
                {
                    "symbol": str(raw.get("symbol") or symbol or "").strip() or symbol,
                    "side": side if side in {"buy", "sell"} else "unknown",
                    "price": price,
                    "amount": amount,
                    "notional": cost,
                    "timestamp": timestamp,
                    "time": self._history_timestamp_text(timestamp) or str(timestamp or "-"),
                }
            )

        return normalized[: max(1, int(limit or 40))]

    async def _safe_fetch_recent_trades(self, symbol, limit=40):
        if not symbol:
            return []

        resolved_symbol = self._resolve_preferred_market_symbol(symbol) or self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        broker = getattr(self, "broker", None)
        if broker is not None and hasattr(broker, "fetch_trades"):
            try:
                rows = await broker.fetch_trades(resolved_symbol, limit=limit)
                normalized = self._normalize_public_trade_rows(resolved_symbol, rows, limit=limit)
                if normalized:
                    return normalized
            except TypeError:
                try:
                    rows = await broker.fetch_trades(resolved_symbol)
                    normalized = self._normalize_public_trade_rows(resolved_symbol, rows, limit=limit)
                    if normalized:
                        return normalized
                except Exception as exc:
                    self.logger.debug("Recent trade fetch failed for %s: %s", symbol, exc)
            except Exception as exc:
                self.logger.debug("Recent trade fetch failed for %s: %s", symbol, exc)

        tick = await self._safe_fetch_ticker(resolved_symbol)
        if not isinstance(tick, dict):
            return []

        price = self._normalize_history_float(tick.get("price") or tick.get("last") or tick.get("bid"))
        if price is None or price <= 0:
            return []

        bid = self._normalize_history_float(tick.get("bid")) or price * 0.9997
        ask = self._normalize_history_float(tick.get("ask")) or price * 1.0003
        now = datetime.now(timezone.utc)
        synthetic = [
            {
                "symbol": symbol,
                "side": "sell",
                "price": bid,
                "amount": 0.35,
                "notional": bid * 0.35,
                "timestamp": now.isoformat(),
                "time": self._history_timestamp_text(now),
            },
            {
                "symbol": symbol,
                "side": "buy",
                "price": ask,
                "amount": 0.42,
                "notional": ask * 0.42,
                "timestamp": now.isoformat(),
                "time": self._history_timestamp_text(now),
            },
        ]
        return synthetic[: max(1, min(int(limit or 2), len(synthetic)))]

    def _active_exchange_code(self, exchange=None):
        normalized = str(exchange or "").strip().lower()
        if normalized:
            return normalized

        broker = getattr(self, "broker", None)
        if broker is not None:
            name = getattr(broker, "exchange_name", None)
            if name:
                return str(name).strip().lower()

        config = getattr(self, "config", None)
        broker_config = getattr(config, "broker", None)
        if broker_config is not None and getattr(broker_config, "exchange", None):
            return str(broker_config.exchange).strip().lower()

        return None

    def _active_market_data_exchange_code(self):
        exchange = self._active_exchange_code()
        if exchange == "oanda":
            component = _normalize_forex_candle_price_component(
                getattr(self, "forex_candle_price_component", "bid")
            )
            return f"{exchange}:{component}"
        return exchange
    @staticmethod
    def _filter_ohlcv_rows_by_time_range(rows, start_time=None, end_time=None):
        start_boundary = _normalize_history_boundary(start_time, end_of_day=False)
        end_boundary = _normalize_history_boundary(end_time, end_of_day=True)
        if start_boundary is None and end_boundary is None:
            return list(rows or [])

        filtered = []
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            try:
                timestamp = pd.Timestamp(row[0])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize("UTC")
                else:
                    timestamp = timestamp.tz_convert("UTC")
            except Exception:
                continue
            if start_boundary is not None and timestamp < start_boundary:
                continue
            if end_boundary is not None and timestamp > end_boundary:
                continue
            filtered.append(list(row[:6]))
        return filtered

    async def _persist_candles_to_db(self, symbol, timeframe, candles):
        repository = getattr(self, "market_data_repository", None)
        if repository is None or not candles:
            return 0

        exchange = self._active_market_data_exchange_code()
        try:
            return await asyncio.to_thread(
                repository.save_candles,
                symbol,
                timeframe,
                candles,
                exchange,
            )
        except Exception as exc:
            self.logger.debug("Candle persistence failed for %s %s: %s", symbol, timeframe, exc)
            return 0

    async def _load_candles_from_db(self, symbol, timeframe="1h", limit=200, start_time=None, end_time=None):
        repository = getattr(self, "market_data_repository", None)
        if repository is None:
            return []

        exchange = self._active_market_data_exchange_code()
        try:
            return await asyncio.to_thread(
                repository.get_candles,
                symbol,
                timeframe,
                limit,
                exchange,
                start_time,
                end_time,
            )
        except Exception as exc:
            self.logger.debug("Candle DB load failed for %s %s: %s", symbol, timeframe, exc)
            return []

    async def _load_recent_trades(self, limit=200):
        repository = getattr(self, "trade_repository", None)
        if repository is None:
            return []

        try:
            trades = await asyncio.to_thread(self._repository_trade_rows_for_active_exchange, limit)
        except Exception as exc:
            self.logger.debug("Trade DB load failed: %s", exc)
            return []

        normalized = []
        for trade in reversed(trades):
            normalized.append(self._performance_trade_payload_from_record(trade))

        return normalized

    def _resolve_history_limit(self, limit=None):
        value = limit if limit is not None else getattr(self, "limit", self.MAX_HISTORY_LIMIT)
        try:
            resolved = max(100, int(value))
        except Exception:
            resolved = self.MAX_HISTORY_LIMIT

        return min(resolved, self.MAX_HISTORY_LIMIT)

    def _resolve_backtest_history_limit(self, limit=None):
        value = limit if limit is not None else getattr(self, "limit", self.MAX_HISTORY_LIMIT)
        try:
            resolved = max(100, int(value))
        except Exception:
            resolved = self.MAX_BACKTEST_HISTORY_LIMIT

        return min(resolved, self.MAX_BACKTEST_HISTORY_LIMIT)

    def handle_trade_execution(self, trade):
        if not isinstance(trade, dict):
            return
        trade = dict(trade)
        if not str(trade.get("exchange") or "").strip():
            trade["exchange"] = self._active_exchange_code()
        trade_session_id = str(trade.get("session_id") or "").strip()
        active_session_id = str(getattr(self, "active_session_id", None) or "").strip()
        trade_matches_active_session = not trade_session_id or trade_session_id == active_session_id

        status = str(trade.get("status") or "").strip().lower().replace("-", "_")
        order_id = str(trade.get("order_id") or "").strip()
        should_record = status in {"filled", "closed"} or trade.get("pnl") not in (None, "")
        if should_record and trade_matches_active_session and order_id:
            self._performance_recorded_orders.add(order_id)

        if should_record and trade_matches_active_session and getattr(self, "performance_engine", None) is not None:
            self.performance_engine.record_trade(trade)

        # Initialize position in position manager if trade is filled
        if status == "filled" and trade_matches_active_session:
            try:
                symbol = str(trade.get("symbol") or "").strip().upper()
                quantity = float(trade.get("quantity") or trade.get("amount") or 0.0)
                entry_price = float(trade.get("price") or trade.get("entry_price") or 0.0)
                stop_loss = trade.get("stop_loss")
                take_profit = trade.get("take_profit")
                if symbol and quantity and entry_price:
                    self._initialize_position_in_manager(
                        symbol=symbol,
                        quantity=quantity,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        strategy_name=trade.get("strategy_name", "unknown"),
                        expected_horizon=trade.get("expected_horizon", "medium"),
                        signal_expiry_time=trade.get("signal_expiry_time"),
                        volatility_at_entry=float(trade.get("volatility_at_entry", 0.0) or 0.0),
                        signal_strength=float(trade.get("signal_strength", 0.0) or 0.0),
                        asset_class=trade.get("asset_class", "unknown"),
                        regime=trade.get("regime"),
                        metadata=trade.get("metadata", {}),
                        trade_id=trade.get("order_id", trade.get("trade_id", "")),
                    )
            except Exception as e:
                self.logger.debug(f"Error initializing position in manager: {e}")

        self.trade_signal.emit(trade)
        if self.terminal is not None and trade_matches_active_session:
            system_console = getattr(self.terminal, "system_console", None)
            if system_console is not None:
                source = str(trade.get("source") or "bot").strip().lower() or "bot"
                symbol = str(trade.get("symbol") or "-").strip().upper() or "-"
                reason = str(
                    trade.get("reason")
                    or trade.get("message")
                    or (
                        ((trade.get("raw") or {}) if isinstance(trade.get("raw"), dict) else {}).get("error")
                    )
                    or ""
                ).strip()
                if trade.get("blocked_by_guard"):
                    system_console.log(
                        f"{source.title()} trade blocked for {symbol}: {reason or 'Behavior guard blocked the trade.'}",
                        "WARN",
                    )
                elif status in {"rejected", "skipped", "failed", "error"}:
                    system_console.log(
                        f"{source.title()} trade {status.replace('_', ' ')} for {symbol}: "
                        f"{reason or 'No rejection reason was supplied by the broker or safety checks.'}",
                        "ERROR" if status in {"rejected", "failed", "error"} else "WARN",
                    )
        telegram_service = getattr(self, "telegram_service", None)
        self._dispatch_trade_close_notifications(trade)
        if telegram_service is not None and not is_trade_close_event(trade):
            self._create_task(telegram_service.notify_trade(trade), "telegram_trade_notify")
        if should_record and trade_matches_active_session:
            self._create_task(self._sync_trade_to_server(trade), "tradeadviser_trade_sync")

    def _extract_balance_equity_value(self, balances):
        if not isinstance(balances, dict):
            return None

        direct_equity = self._balance_metric_value(
            balances,
            "nav",
            "equity",
            "net_liquidation",
            "account_value",
            "total_account_value",
            "balance",
            "cash",
        )
        if direct_equity is not None:
            return direct_equity

        cash_value = self._balance_metric_value(balances, "cash")
        position_value = self._balance_metric_value(balances, "position_value", "positions_value")
        if cash_value is not None or position_value is not None:
            return float(cash_value or 0.0) + float(position_value or 0.0)

        total = balances.get("total")
        if isinstance(total, dict):
            for currency in ("USDT", "USD", "USDC", "BUSD", "EUR", "GBP"):
                value = total.get(currency)
                if value is None:
                    continue
                try:
                    return float(value)
                except Exception:
                    continue
            if len(total) == 1:
                sole_currency = str(next(iter(total.keys())) or "").upper().strip()
                if sole_currency not in {"USDT", "USD", "USDC", "BTC","XLM","BUSD", "EUR", "GBP"}:
                    return None
                try:
                    return float(next(iter(total.values())))
                except Exception:
                    return None
        return None

    def _update_performance_equity(self, balances=None):
        perf = getattr(self, "performance_engine", None)
        if perf is None or not hasattr(perf, "update_equity"):
            return None

        equity = self._extract_balance_equity_value(balances if balances is not None else getattr(self, "balances", {}))
        if equity is None or equity ==0:
            return 0.0

        existing = getattr(perf, "equity_curve", None)
        if isinstance(existing, list) and existing:
            try:
                last_value = float(existing[-1])
            except Exception:
                last_value = None
            if last_value is not None and abs(last_value - float(equity)) <= 1e-9:
                return equity

        try:
            perf.update_equity(equity)
            self._persist_performance_history()
            self._persist_equity_snapshot(equity, balances if balances is not None else getattr(self, "balances", {}))
        except Exception:
            self.logger.debug("Performance equity update failed", exc_info=True)
            return None

        return equity

    def _safe_balance_metric(self, value):
        if value is None:
            return None
        if isinstance(value, dict):
            for currency in ("USDT", "USD", "USDC", "BUSD","BTC","XLM"):
                if currency in value:
                    numeric = self._safe_balance_metric(value.get(currency))
                    if numeric is not None:
                        return numeric
            for nested in value.values():
                numeric = self._safe_balance_metric(nested)
                if numeric is not None:
                    return numeric
            return None
        try:
            return float(value)
        except Exception:

            import traceback
            traceback.print_exc()
            return None

    def _balance_metric_value(self, balances, *keys):
        if not isinstance(balances, dict):
            return None
        account = dict(balances.get("raw") or {})
        candidates = []
        for key in keys:
            if key is None:
                continue
            key_text = str(key).strip()
            if not key_text:
                continue
            variants = {
                key_text,
                key_text.lower(),
                key_text.upper(),
                key_text.replace("_", ""),
                key_text.replace("_", "").lower(),
                key_text.replace("_", "").upper(),
                key_text.replace("_", "-"),
                key_text.replace("_", " "),
                "".join(part.capitalize() for part in key_text.split("_")),
            }
            parts = [part for part in key_text.split("_") if part]
            if parts:
                variants.add(parts[0].lower() + "".join(part.capitalize() for part in parts[1:]))
            for variant in variants:
                if variant not in candidates:
                    candidates.append(variant)

        for source in (account, balances):
            if not isinstance(source, dict):
                continue
            for candidate in candidates:
                if candidate in source:
                    numeric = self._safe_balance_metric(source.get(candidate))
                    if numeric is not None:
                        return numeric
        return None

    def margin_closeout_snapshot(self, balances=None):
        balances = balances if isinstance(balances, dict) else getattr(self, "balances", {}) or {}
        threshold = max(0.01, min(1.0, float(getattr(self, "max_margin_closeout_pct", 0.50) or 0.50)))
        enabled = bool(getattr(self, "margin_closeout_guard_enabled", True))
        ratio = self._balance_metric_value(
            balances,
            "margin_closeout_percent",
            "margin_closeout_pct",
            "margin_closeout",
            "margin_ratio",
        )
        source = "reported"
        if ratio is not None and ratio > 1.0 and ratio <= 100.0:
            ratio = ratio / 100.0
        if ratio is None:
            margin_used = self._balance_metric_value(balances, "margin_used", "used_margin", "used")
            equity = self._balance_metric_value(
                balances,
                "nav",
                "equity",
                "net_liquidation",
                "account_value",
                "total_account_value",
                "balance",
            )
            if margin_used is not None and equity is not None and equity > 0:
                ratio = max(0.0, float(margin_used) / float(equity))
                source = "derived"

        warning_threshold = max(0.0, min(threshold, threshold * 0.8))
        blocked = bool(enabled and ratio is not None and ratio >= threshold)
        warning = bool(enabled and ratio is not None and ratio >= warning_threshold)
        if ratio is None:
            reason = "Margin closeout risk metric is not available from the current broker balance payload."
        elif blocked:
            reason = (
                f"Margin closeout risk is {ratio:.2%}, above the configured limit of {threshold:.2%}. "
                "New trades are blocked."
            )
        elif warning:
            reason = (
                f"Margin closeout risk is {ratio:.2%}. Guard threshold is {threshold:.2%}."
            )
        else:
            reason = (
                f"Margin closeout risk is {ratio:.2%}. Guard threshold is {threshold:.2%}."
            )
        return {
            "enabled": enabled,
            "available": ratio is not None,
            "ratio": ratio,
            "threshold": threshold,
            "warning_threshold": warning_threshold,
            "warning": warning,
            "blocked": blocked,
            "source": source,
            "reason": reason,
        }

    def _update_behavior_guard_equity(self, balances=None):
        guard = getattr(self, "behavior_guard", None)
        if guard is None:
            return
        equity = self._extract_balance_equity_value(balances if balances is not None else getattr(self, "balances", {}))
        if equity is None:
            return
        try:
            guard.record_equity(equity)
        except Exception:
            self.logger.debug("Behavior guard equity update failed", exc_info=True)

    def current_trading_mode(self):
        broker_config = getattr(getattr(self, "config", None), "broker", None)
        value = getattr(broker_config, "mode", None) or getattr(getattr(self, "broker", None), "mode", None) or "paper"
        return str(value or "paper").strip().lower()

    def is_live_mode(self):
        mode = self.current_trading_mode()
        broker_config = getattr(getattr(self, "config", None), "broker", None)
        exchange = str(getattr(broker_config, "exchange", "") or "").strip().lower()
        return mode == "live" and exchange != "paper"

    def current_account_label(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            broker_status = dict(runtime.get("broker_status") or {})
            account_label = str(
                broker_status.get("account_label")
                or broker_status.get("account")
                or ""
            ).strip()
            if account_label:
                return account_label
        broker = getattr(self, "broker", None)
        broker_config = getattr(getattr(self, "config", None), "broker", None)
        return resolve_account_label(broker, broker_config)

    def _resolve_broker_capability(self, method_name):
        broker = getattr(self, "broker", None)
        if broker is None:
            return False
        exchange_has = getattr(broker, "_exchange_has", None)
        if callable(exchange_has):
            try:
                return bool(exchange_has(method_name))
            except Exception:
                pass
        return callable(getattr(broker, method_name, None))

    def get_broker_capabilities(self):
        broker = getattr(self, "broker", None)
        if broker is None:
            return {}

        markets = getattr(getattr(broker, "exchange", None), "markets", None)
        supported_venues = self.supported_market_venues()
        option_market_available = "option" in supported_venues
        derivative_market_available = "derivative" in supported_venues
        otc_market_available = "otc" in supported_venues
        if isinstance(markets, dict) and markets:
            option_market_available = option_market_available or any(
                bool((market or {}).get("option")) for market in markets.values()
            )

        return {
            "connectivity": self._resolve_broker_capability("fetch_status"),
            "trading": self._resolve_broker_capability("create_order"),
            "cancel_orders": self._resolve_broker_capability("cancel_all_orders") or self._resolve_broker_capability("cancel_order"),
            "positions": self._resolve_broker_capability("fetch_positions"),
            "open_orders": self._resolve_broker_capability("fetch_open_orders"),
            "closed_orders": self._resolve_broker_capability("fetch_closed_orders"),
            "order_tracking": self._resolve_broker_capability("fetch_order"),
            "orderbook": self._resolve_broker_capability("fetch_orderbook") or self._resolve_broker_capability("fetch_order_book"),
            "candles": self._resolve_broker_capability("fetch_ohlcv"),
            "ticker": self._resolve_broker_capability("fetch_ticker"),
            "recent_trades": self._resolve_broker_capability("fetch_trades"),
            "derivatives_market": derivative_market_available,
            "options_market": option_market_available,
            "otc_market": otc_market_available,
            "supported_market_venues": supported_venues,
        }

    def _primary_runtime_symbol(self, symbol=None):
        broker_type = self._active_broker_type()
        exchange_code = self._active_exchange_code()
        candidates = [symbol]

        resolver = getattr(self, "get_active_autotrade_symbols", None)
        if callable(resolver):
            try:
                candidates.extend(list(resolver() or []))
            except Exception:
                pass

        candidates.extend(list(getattr(self, "symbols", []) or []))
        for candidate in candidates:
            normalized = self._resolve_preferred_market_symbol(candidate) or self._normalize_market_data_symbol(candidate)
            if normalized and self._is_plausible_market_symbol(normalized, broker_type=broker_type, exchange=exchange_code):
                return normalized
        return ""

    def _market_data_provider_summary(self):
        broker = getattr(self, "broker", None)
        exchange_code = self._active_exchange_code()
        if broker is None:
            return {
                "market_data_provider": "Not connected",
                "swap_provider": "",
                "wallet_configured": False,
                "signer_configured": False,
            }

        swap_provider = ""
        if exchange_code == "solana":
            market_data_provider = str(getattr(broker, "market_data_provider", "gecko") or "gecko").strip().upper()
            swap_provider = str(getattr(broker, "swap_provider", "jupiter") or "jupiter").strip().upper()
        elif exchange_code == "stellar":
            market_data_provider = "Stellar Horizon"
        elif exchange_code == "oanda":
            market_data_provider = "OANDA REST"
        else:
            market_data_provider = str(getattr(broker, "exchange_name", exchange_code or "broker") or "broker").strip().upper()

        wallet_configured = bool(str(getattr(broker, "wallet_address", "") or "").strip())
        signer_configured = bool(str(getattr(broker, "secret", "") or "").strip())
        return {
            "market_data_provider": market_data_provider,
            "swap_provider": swap_provider,
            "wallet_configured": wallet_configured,
            "signer_configured": signer_configured,
        }

    def get_broker_capability_profile(self):
        broker = getattr(self, "broker", None)
        capabilities = self.get_broker_capabilities()
        exchange_code = self._active_exchange_code()
        profile = self._market_data_provider_summary()
        account_label = self.current_account_label()
        live_mode = self.is_live_mode()
        connected = self._broker_is_connected(broker)
        supports_lots = bool(exchange_code == "oanda")

        summary_bits = [
            f"{str(exchange_code or 'broker').upper()} {'LIVE' if live_mode else 'PAPER'}",
            "connected" if connected else "disconnected",
            f"account {account_label}",
        ]
        if profile.get("market_data_provider"):
            summary_bits.append(f"data {profile['market_data_provider']}")
        if profile.get("swap_provider"):
            summary_bits.append(f"swap {profile['swap_provider']}")

        return {
            "exchange": exchange_code,
            "mode": self.current_trading_mode(),
            "live_mode": live_mode,
            "connected": connected,
            "account_label": account_label,
            "health_summary": self.get_health_check_summary(),
            "market_data_provider": profile.get("market_data_provider"),
            "swap_provider": profile.get("swap_provider"),
            "wallet_configured": bool(profile.get("wallet_configured")),
            "signer_configured": bool(profile.get("signer_configured")),
            "okx_trade_api_ready": bool(getattr(broker, "okx_trade_api_ready", False)),
            "supports_lots": supports_lots,
            "supports_recent_trades": bool(capabilities.get("recent_trades")),
            "supports_public_market_data": bool(capabilities.get("ticker") or capabilities.get("candles") or capabilities.get("orderbook")),
            "supported_market_venues": list(capabilities.get("supported_market_venues") or []),
            "trade_venue_preference": self._active_market_trade_preference_value(),
            "symbols_loaded": len(list(getattr(self, "symbols", []) or [])),
            "live_order_ready": bool(capabilities.get("trading") and connected),
            "capabilities": dict(capabilities or {}),
            "summary": " | ".join(bit for bit in summary_bits if bit),
        }

    def get_market_data_health_snapshot(self, symbol=None, timeframe=None):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            payload = dict(runtime.get("market_data_health") or {})
            if payload:
                payload.setdefault("stream_status", self.get_market_stream_status())
                payload.setdefault("symbol", str(symbol or payload.get("symbol") or "").strip())
                payload.setdefault("timeframe", str(timeframe or payload.get("timeframe") or getattr(self, "time_frame", "1h") or "1h").strip() or "1h")
                return payload

        normalized_symbol = self._primary_runtime_symbol(symbol)
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        provider_profile = self._market_data_provider_summary()

        if not normalized_symbol:
            return {
                "symbol": "",
                "timeframe": timeframe_value,
                "stream_status": self.get_market_stream_status(),
                "market_data_provider": provider_profile.get("market_data_provider"),
                "swap_provider": provider_profile.get("swap_provider"),
                "quote": {"supported": True, "fresh": None, "age_seconds": None, "age_label": "unknown"},
                "candles": {"supported": True, "fresh": None, "age_seconds": None, "age_label": "unknown", "timeframe": timeframe_value},
                "orderbook": {"supported": bool(self.get_broker_capabilities().get("orderbook")), "fresh": None, "age_seconds": None, "age_label": "unknown"},
                "summary": "No active symbol is available for data-health monitoring yet.",
            }

        quote_threshold = max(1.0, float(getattr(self, "QUOTE_STALE_SECONDS", 20.0) or 20.0))
        candle_threshold_seconds = max(
            float(getattr(self, "CANDLE_STALE_MIN_SECONDS", 60.0) or 60.0),
            float(timeframe_seconds(timeframe_value, default=60)) * float(getattr(self, "CANDLE_STALE_MULTIPLIER", 3.0) or 3.0),
            )
        orderbook_threshold = max(1.0, float(getattr(self, "ORDERBOOK_STALE_SECONDS", 20.0) or 20.0))

        ticker_snapshot = self._cached_ticker_snapshot(normalized_symbol)
        quote_age_seconds = age_seconds((ticker_snapshot or {}).get("_received_at") or (ticker_snapshot or {}).get("timestamp"))
        quote_fresh = quote_age_seconds is not None and quote_age_seconds <= quote_threshold

        candle_timestamp = self._latest_cached_candle_timestamp(normalized_symbol, timeframe=timeframe_value)
        candle_age_seconds = age_seconds(candle_timestamp)
        candle_fresh = candle_age_seconds is not None and candle_age_seconds <= candle_threshold_seconds

        orderbook_supported = bool(self.get_broker_capabilities().get("orderbook"))
        orderbook_snapshot = None
        orderbook_buffer = getattr(self, "orderbook_buffer", None)
        if orderbook_buffer is not None and hasattr(orderbook_buffer, "get"):
            try:
                orderbook_snapshot = orderbook_buffer.get(normalized_symbol)
            except Exception:
                orderbook_snapshot = None
        orderbook_age_seconds = age_seconds((orderbook_snapshot or {}).get("updated_at"))
        orderbook_fresh = orderbook_age_seconds is not None and orderbook_age_seconds <= orderbook_threshold

        summary_bits = [
            f"{normalized_symbol} via {provider_profile.get('market_data_provider') or 'market data'}",
            f"quote {'fresh' if quote_fresh else 'stale'} ({format_age_label(quote_age_seconds)})",
            f"candles {'fresh' if candle_fresh else 'stale'} ({format_age_label(candle_age_seconds)})",
        ]
        if orderbook_supported:
            summary_bits.append(f"orderbook {'fresh' if orderbook_fresh else 'stale'} ({format_age_label(orderbook_age_seconds)})")

        return {
            "symbol": normalized_symbol,
            "timeframe": timeframe_value,
            "stream_status": self.get_market_stream_status(),
            "market_data_provider": provider_profile.get("market_data_provider"),
            "swap_provider": provider_profile.get("swap_provider"),
            "quote": {
                "supported": True,
                "fresh": quote_fresh,
                "age_seconds": quote_age_seconds,
                "age_label": format_age_label(quote_age_seconds),
                "threshold_seconds": quote_threshold,
                "threshold_label": format_age_label(quote_threshold),
            },
            "candles": {
                "supported": True,
                "fresh": candle_fresh,
                "age_seconds": candle_age_seconds,
                "age_label": format_age_label(candle_age_seconds),
                "threshold_seconds": candle_threshold_seconds,
                "threshold_label": format_age_label(candle_threshold_seconds),
                "timeframe": timeframe_value,
            },
            "orderbook": {
                "supported": orderbook_supported,
                "fresh": orderbook_fresh if orderbook_supported else None,
                "age_seconds": orderbook_age_seconds,
                "age_label": format_age_label(orderbook_age_seconds),
                "threshold_seconds": orderbook_threshold if orderbook_supported else None,
                "threshold_label": format_age_label(orderbook_threshold) if orderbook_supported else "",
            },
            "summary": " | ".join(summary_bits),
        }

    def get_live_readiness_report(self, symbol=None, timeframe=None):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            payload = dict(runtime.get("live_readiness") or {})
            if payload:
                payload.setdefault("symbol", str(symbol or payload.get("symbol") or "").strip())
                payload.setdefault("timeframe", str(timeframe or payload.get("timeframe") or getattr(self, "time_frame", "1h") or "1h").strip() or "1h")
                payload.setdefault("market_data", dict(runtime.get("market_data_health") or {}))
                self._latest_live_readiness_report = dict(payload)
                return payload

        profile = self.get_broker_capability_profile()
        capabilities = dict(profile.get("capabilities") or {})
        live_mode = bool(profile.get("live_mode"))
        exchange_code = str(profile.get("exchange") or "").strip().lower()
        normalized_symbol = self._primary_runtime_symbol(symbol)
        timeframe_value = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        data_health = self.get_market_data_health_snapshot(normalized_symbol, timeframe=timeframe_value)

        checks = []

        def _add(name, status, detail):
            checks.append(
                {
                    "name": str(name or "").strip(),
                    "status": str(status or "warn").strip().lower(),
                    "detail": str(detail or "").strip(),
                }
            )

        connected = bool(profile.get("connected"))
        _add(
            "Broker Session",
            "pass" if connected else ("fail" if live_mode else "warn"),
            "Broker session is connected." if connected else "Broker session is not connected.",
        )
        trading_ready = bool(capabilities.get("trading"))
        _add(
            "Order Route",
            "pass" if trading_ready else ("fail" if live_mode else "warn"),
            "Order submission route is available." if trading_ready else "The active broker profile does not expose order submission.",
        )
        account_label = str(profile.get("account_label") or "Not set").strip()
        _add(
            "Account Identity",
            "pass" if account_label != "Not set" else ("fail" if live_mode else "warn"),
            f"Account identity resolved to {account_label}." if account_label != "Not set" else "No broker account identity is set.",
        )
        if exchange_code == "solana":
            wallet_ready = bool(profile.get("wallet_configured"))
            signer_ready = bool(profile.get("signer_configured"))
            _add(
                "Wallet",
                "pass" if wallet_ready else ("fail" if live_mode else "warn"),
                "Wallet address is configured." if wallet_ready else "Solana wallet address is not configured.",
            )
            _add(
                "Signer",
                "pass" if signer_ready else ("fail" if live_mode else "warn"),
                "Private signer key is configured." if signer_ready else "Solana private signer key is missing for live swaps.",
            )

        guard_locked = bool(self.is_emergency_stop_active())
        _add(
            "Behavior Guard",
            "fail" if guard_locked else "pass",
            "Emergency stop is active." if guard_locked else "Behavior guard is clear for new entries.",
        )
        _add(
            "Runtime Symbol",
            "pass" if normalized_symbol else ("fail" if live_mode else "warn"),
            f"Primary runtime symbol is {normalized_symbol}." if normalized_symbol else "No active symbol is available for readiness checks.",
        )

        quote = dict(data_health.get("quote") or {})
        candles = dict(data_health.get("candles") or {})
        orderbook = dict(data_health.get("orderbook") or {})
        _add(
            "Quote Feed",
            "pass" if quote.get("fresh") else ("fail" if live_mode else "warn"),
            f"Quote data age {quote.get('age_label') or 'unknown'} (threshold {quote.get('threshold_label') or 'n/a'}).",
        )
        _add(
            "Candle Feed",
            "pass" if candles.get("fresh") else ("fail" if live_mode else "warn"),
            (
                f"Candle data age {candles.get('age_label') or 'unknown'} for {candles.get('timeframe') or timeframe_value} "
                f"(threshold {candles.get('threshold_label') or 'n/a'})."
            ),
        )
        if orderbook.get("supported"):
            _add(
                "Orderbook Feed",
                "pass" if orderbook.get("fresh") else ("warn" if not live_mode else "fail"),
                f"Orderbook age {orderbook.get('age_label') or 'unknown'} (threshold {orderbook.get('threshold_label') or 'n/a'}).",
            )
        else:
            _add("Orderbook Feed", "skip", "Orderbook data is not supported by the active broker profile.")

        health_report = list(getattr(self, "health_check_report", []) or [])
        has_failures = any(str(item.get("status") or "").strip().lower() == "fail" for item in health_report if isinstance(item, dict))
        has_warnings = any(str(item.get("status") or "").strip().lower() == "warn" for item in health_report if isinstance(item, dict))
        health_status = "pass"
        if has_failures:
            health_status = "fail"
        elif has_warnings or not health_report:
            health_status = "warn"
        _add(
            "Startup Health",
            health_status,
            self.get_health_check_summary() if health_report else "Startup health checks have not run yet.",
        )

        advisory_checks = []
        for item in checks:
            advisory_item = dict(item)
            if advisory_item.get("status") == "fail":
                advisory_item["status"] = "warn"
            advisory_checks.append(advisory_item)

        blocking = []
        warnings = [item for item in advisory_checks if item["status"] == "warn"]
        ready = True
        if warnings:
            summary = f"Readiness gate disabled. {len(warnings)} advisory warning{'s' if len(warnings) != 1 else ''}."
        else:
            summary = "Readiness gate disabled. Monitoring only."

        report = {
            "ready": ready,
            "summary": summary,
            "symbol": normalized_symbol,
            "timeframe": timeframe_value,
            "checks": advisory_checks,
            "blocking_reasons": [item["detail"] for item in blocking],
            "warning_reasons": [item["detail"] for item in warnings],
            "profile": profile,
            "market_data": data_health,
        }
        self._latest_live_readiness_report = dict(report)
        return report

    def activate_emergency_stop(self, reason="Emergency kill switch active"):
        guard = getattr(self, "behavior_guard", None)
        if guard is None and getattr(getattr(self, "trading_system", None), "behavior_guard", None) is not None:
            guard = self.trading_system.behavior_guard
            self.behavior_guard = guard
        if guard is not None:
            guard.activate_manual_lock(reason)
        if self._hybrid_trading_available():
            self._create_task(
                self._trigger_hybrid_kill_switch(reason),
                "hybrid_kill_switch",
            )

    def clear_emergency_stop(self):
        guard = getattr(self, "behavior_guard", None)
        if guard is not None:
            guard.clear_manual_lock()

    def is_emergency_stop_active(self):
        guard = getattr(self, "behavior_guard", None)
        if guard is None:
            return False
        return bool(getattr(guard, "is_locked", lambda: False)())

    def get_behavior_guard_status(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            payload = dict(runtime.get("behavior_guard_status") or {})
            if payload:
                return payload
        guard = getattr(self, "behavior_guard", None)
        if guard is None:
            return {}
        try:
            return dict(guard.status_snapshot() or {})
        except Exception:
            self.logger.debug("Behavior guard status lookup failed", exc_info=True)
            return {}

    async def run_startup_health_check(self):
        broker = getattr(self, "broker", None)
        if broker is None:
            self.health_check_report = []
            self.health_check_summary = "No broker connected"
            return []

        symbol = next(iter(getattr(self, "symbols", []) or []), None)
        capabilities = self.get_broker_capabilities()
        results = []

        async def _run_check(name, coro_factory, optional=False):
            try:
                detail = await coro_factory()
                results.append({"name": name, "status": "pass", "detail": detail or "OK"})
            except NotImplementedError:
                results.append({"name": name, "status": "skip" if optional else "warn", "detail": "Not supported by broker"})
            except Exception as exc:
                results.append({"name": name, "status": "warn" if optional else "fail", "detail": str(exc)})

        if capabilities.get("connectivity"):
            async def _fetch_connectivity():
                status = await broker.fetch_status()
                if isinstance(status, dict):
                    broker_label = str(status.get("broker") or getattr(broker, "exchange_name", "") or "").upper()
                    status_text = str(status.get("status") or "ok").upper()
                    return f"{broker_label + ' ' if broker_label else ''}{status_text}".strip()
                return status

            await _run_check("Connectivity", _fetch_connectivity)
        else:
            results.append(
                {
                    "name": "Connectivity",
                    "status": "pass" if self._broker_is_connected(broker) else "warn",
                    "detail": "Connected" if self._broker_is_connected(broker) else "Connection state unavailable",
                }
            )

        await _run_check("Balance", lambda: self._fetch_balances(broker))
        if symbol and capabilities.get("ticker"):
            await _run_check("Ticker", lambda: self._safe_fetch_ticker(symbol))
        elif symbol:
            results.append({"name": "Ticker", "status": "skip", "detail": "Ticker endpoint not available"})

        if symbol and capabilities.get("candles"):
            await _run_check(
                "Candles",
                lambda: broker.fetch_ohlcv(symbol, timeframe=getattr(self, "time_frame", "1h"), limit=50),
            )
        elif symbol:
            results.append({"name": "Candles", "status": "skip", "detail": "Candle endpoint not available"})

        if symbol and capabilities.get("orderbook"):
            await _run_check("Orderbook", lambda: broker.fetch_orderbook(symbol, limit=10), optional=True)
        else:
            results.append({"name": "Orderbook", "status": "skip", "detail": "Orderbook not supported"})

        if capabilities.get("open_orders"):
            async def _fetch_open_orders():
                snapshot = getattr(broker, "fetch_open_orders_snapshot", None)
                if callable(snapshot):
                    return await snapshot(symbols=getattr(self, "symbols", []), limit=10)
                if symbol:
                    return await broker.fetch_open_orders(symbol=symbol, limit=10)
                return await broker.fetch_open_orders(limit=10)

            await _run_check("Open Orders", _fetch_open_orders, optional=True)
        else:
            results.append({"name": "Open Orders", "status": "skip", "detail": "Open-order endpoint not supported"})

        if capabilities.get("positions"):
            await _run_check("Positions", lambda: broker.fetch_positions(), optional=True)
        else:
            results.append({"name": "Positions", "status": "skip", "detail": "Position endpoint not supported"})

        results.append(
            {
                "name": "Order Submit Route",
                "status": "pass" if capabilities.get("trading") else "warn",
                "detail": "Execution route available" if capabilities.get("trading") else "Order creation not available",
            }
        )
        results.append(
            {
                "name": "Order Tracking",
                "status": "pass" if capabilities.get("order_tracking") else "warn",
                "detail": "Live order status lookup available" if capabilities.get("order_tracking") else "No live fetch_order support",
            }
        )

        passed = sum(1 for item in results if item["status"] == "pass")
        failed = sum(1 for item in results if item["status"] == "fail")
        warned = sum(1 for item in results if item["status"] == "warn")
        self.health_check_report = results
        if failed:
            self.health_check_summary = f"{passed} pass / {warned} warn / {failed} fail"
        else:
            self.health_check_summary = f"{passed} pass / {warned} warn"
        terminal = getattr(self, "terminal", None)
        notifier = getattr(terminal, "_push_notification", None)
        attention_items = [
            item
            for item in results
            if str((item or {}).get("status") or "").strip().lower() in {"warn", "fail"}
        ]
        notification_signature = (
            self.health_check_summary,
            tuple(
                (
                    str(item.get("name") or "").strip(),
                    str(item.get("status") or "").strip().lower(),
                    str(item.get("detail") or "").strip(),
                )
                for item in attention_items
            ),
        )
        if callable(notifier) and notification_signature != getattr(self, "_startup_health_notification_signature", None):
            self._startup_health_notification_signature = notification_signature
            details = "; ".join(
                f"{item.get('name')}: {item.get('detail')}"
                for item in attention_items[:4]
                if isinstance(item, dict)
            )
            if not details:
                details = "All startup checks passed."
            notifier(
                "Startup health check",
                f"{self.health_check_summary}. {details}",
                level="ERROR" if failed else "WARN" if warned else "INFO",
                source="health",
                dedupe_seconds=5.0,
            )
        return results

    def get_health_check_report(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            report = list(runtime.get("health_check_report") or [])
            if report:
                return report
        return list(self.health_check_report or [])

    def get_health_check_summary(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            summary = str(runtime.get("health_summary") or "").strip()
            if summary:
                return summary
        return str(self.health_check_summary or "Not run")

    def get_pipeline_status_snapshot(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            payload = dict(runtime.get("pipeline_snapshot") or {})
            if payload:
                return payload
        trading_system = getattr(self, "trading_system", None)
        resolver = getattr(trading_system, "pipeline_status_snapshot", None)
        if callable(resolver):
            try:
                return dict(resolver() or {})
            except Exception:
                self.logger.debug("Pipeline status lookup failed", exc_info=True)
        return {}

    def get_pipeline_status_summary(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            summary = str(runtime.get("pipeline_summary") or "").strip()
            if summary:
                return summary
        snapshot = self.get_pipeline_status_snapshot()
        if not snapshot:
            return "Idle"

        counts = {"filled": 0, "submitted": 0, "signal": 0, "approved": 0, "hold": 0, "rejected": 0, "blocked": 0, "skipped": 0}
        for payload in snapshot.values():
            status = str((payload or {}).get("status") or "unknown").strip().lower()
            counts[status] = counts.get(status, 0) + 1

        active = counts.get("filled", 0) + counts.get("submitted", 0) + counts.get("signal", 0) + counts.get("approved", 0)
        guarded = counts.get("rejected", 0) + counts.get("blocked", 0)
        holding = counts.get("hold", 0) + counts.get("skipped", 0)
        return f"{active} active / {guarded} guarded / {holding} idle"

    async def fetch_closed_trade_journal(self, limit=150):
        rows = []
        seen = set()
        repo_rows = []
        try:
            repo_rows = await asyncio.to_thread(
                self._repository_trade_rows_for_active_exchange,
                max(int(limit) * 2, 100),
            )
        except Exception as exc:
            self.logger.debug("Trade DB journal load failed: %s", exc)

        source_map = {}
        for trade in repo_rows or []:
            order_id = str(getattr(trade, "order_id", "") or "").strip()
            if order_id and order_id not in source_map:
                source_map[order_id] = {
                    "trade_db_id": getattr(trade, "id", None),
                    "source": getattr(trade, "source", "") or "",
                    "status": getattr(trade, "status", "") or "",
                    "timestamp": getattr(trade, "timestamp", "") or "",
                    "price": getattr(trade, "price", "") or "",
                    "size": getattr(trade, "quantity", "") or "",
                    "pnl": getattr(trade, "pnl", "") or "",
                    "strategy_name": getattr(trade, "strategy_name", "") or "",
                    "reason": getattr(trade, "reason", "") or "",
                    "confidence": getattr(trade, "confidence", "") or "",
                    "expected_price": getattr(trade, "expected_price", "") or "",
                    "spread_bps": getattr(trade, "spread_bps", "") or "",
                    "slippage_bps": getattr(trade, "slippage_bps", "") or "",
                    "fee": getattr(trade, "fee", "") or "",
                    "stop_loss": getattr(trade, "stop_loss", "") or "",
                    "take_profit": getattr(trade, "take_profit", "") or "",
                    "setup": getattr(trade, "setup", "") or "",
                    "outcome": getattr(trade, "outcome", "") or "",
                    "lessons": getattr(trade, "lessons", "") or "",
                }

        broker = getattr(self, "broker", None)
        if broker is not None and self._resolve_broker_capability("fetch_closed_orders"):
            try:
                broker_rows = await broker.fetch_closed_orders(limit=limit)
            except Exception as exc:
                self.logger.debug("Closed-order journal fetch failed: %s", exc)
                broker_rows = []
            for row in broker_rows or []:
                if not isinstance(row, dict):
                    continue
                order_id = str(row.get("id") or row.get("order_id") or "").strip()
                seen.add(order_id)
                repo_meta = source_map.get(order_id, {})
                rows.append(
                    self._finalize_trade_history_row(
                        {
                            "trade_db_id": repo_meta.get("trade_db_id"),
                            "timestamp": row.get("timestamp") or repo_meta.get("timestamp") or "",
                            "symbol": row.get("symbol") or "",
                            "source": row.get("source") or repo_meta.get("source") or "broker",
                            "side": row.get("side") or "",
                            "price": row.get("average") or row.get("price") or repo_meta.get("price") or "",
                            "size": row.get("filled") or row.get("amount") or repo_meta.get("size") or "",
                            "order_type": row.get("type") or "",
                            "status": row.get("status") or repo_meta.get("status") or "",
                            "order_id": order_id,
                            "pnl": row.get("pnl") or repo_meta.get("pnl") or "",
                            "strategy_name": repo_meta.get("strategy_name") or "",
                            "reason": repo_meta.get("reason") or "",
                            "confidence": repo_meta.get("confidence") or "",
                            "expected_price": repo_meta.get("expected_price") or "",
                            "spread_bps": repo_meta.get("spread_bps") or "",
                            "slippage_bps": repo_meta.get("slippage_bps") or "",
                            "fee": repo_meta.get("fee") or "",
                            "stop_loss": repo_meta.get("stop_loss") or "",
                            "take_profit": repo_meta.get("take_profit") or "",
                            "setup": repo_meta.get("setup") or "",
                            "outcome": repo_meta.get("outcome") or "",
                            "lessons": repo_meta.get("lessons") or "",
                        }
                    )
                )

        for trade in repo_rows or []:
            order_id = str(getattr(trade, "order_id", "") or "").strip()
            if order_id and order_id in seen:
                continue
            status = str(getattr(trade, "status", "") or "").strip().lower()
            if status not in {"filled", "closed", "canceled", "cancelled", "rejected", "expired", "failed"}:
                continue
            rows.append(
                self._finalize_trade_history_row(
                    {
                        "trade_db_id": getattr(trade, "id", None),
                        "timestamp": getattr(trade, "timestamp", "") or "",
                        "symbol": getattr(trade, "symbol", "") or "",
                        "source": getattr(trade, "source", "") or "",
                        "side": getattr(trade, "side", "") or "",
                        "price": getattr(trade, "price", "") or "",
                        "size": getattr(trade, "quantity", "") or "",
                        "order_type": getattr(trade, "order_type", "") or "",
                        "status": getattr(trade, "status", "") or "",
                        "order_id": order_id,
                        "pnl": getattr(trade, "pnl", "") or "",
                        "strategy_name": getattr(trade, "strategy_name", "") or "",
                        "reason": getattr(trade, "reason", "") or "",
                        "confidence": getattr(trade, "confidence", "") or "",
                        "expected_price": getattr(trade, "expected_price", "") or "",
                        "spread_bps": getattr(trade, "spread_bps", "") or "",
                        "slippage_bps": getattr(trade, "slippage_bps", "") or "",
                        "fee": getattr(trade, "fee", "") or "",
                        "stop_loss": getattr(trade, "stop_loss", "") or "",
                        "take_profit": getattr(trade, "take_profit", "") or "",
                        "setup": getattr(trade, "setup", "") or "",
                        "outcome": getattr(trade, "outcome", "") or "",
                        "lessons": getattr(trade, "lessons", "") or "",
                    }
                )
            )

        rows.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return rows[:limit]

    def _normalize_history_float(self, value):
        if value in (None, "", "-"):
            return None
        try:
            numeric = float(value)
        except Exception:
            return None
        if not math.isfinite(numeric):
            return None
        return numeric

    def _normalize_ohlcv_timestamp(self, value):
        if value in (None, ""):
            return None, None

        try:
            numeric = float(value)
        except Exception:
            numeric = None

        try:
            if numeric is not None and math.isfinite(numeric):
                timestamp = pd.Timestamp(
                    numeric,
                    unit="ms" if abs(numeric) > 1e11 else "s",
                    tz="UTC",
                )
            else:
                text = str(value).strip()
                if not text:
                    return None, None
                timestamp = pd.Timestamp(text)
                if pd.isna(timestamp):
                    return None, None
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize("UTC")
                else:
                    timestamp = timestamp.tz_convert("UTC")
        except Exception:
            return None, None

        if pd.isna(timestamp):
            return None, None

        # Reject placeholder/index-style timestamps that would otherwise render
        # charts around the Unix epoch (for example 1, 2, 3 => 1970-01-01).
        min_timestamp = pd.Timestamp("1990-01-01T00:00:00+00:00")
        max_timestamp = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=365 * 5)
        if timestamp < min_timestamp or timestamp > max_timestamp:
            return None, None

        try:
            timestamp_ms = int(timestamp.timestamp() * 1000)
        except Exception:
            return None, None

        if timestamp_ms <= 0:
            return None, None

        return timestamp.isoformat(), timestamp_ms

    def _normalize_ohlcv_row(self, row):
        if isinstance(row, dict):
            timestamp_value = row.get("timestamp") or row.get("time") or row.get("datetime")
            open_value = row.get("open") or row.get("o")
            high_value = row.get("high") or row.get("h")
            low_value = row.get("low") or row.get("l")
            close_value = row.get("close") or row.get("c")
            volume_value = row.get("volume", row.get("v", 0.0))
        elif isinstance(row, (list, tuple)) and len(row) >= 6:
            timestamp_value, open_value, high_value, low_value, close_value, volume_value = row[:6]
        else:
            return None

        timestamp_text, timestamp_ms = self._normalize_ohlcv_timestamp(timestamp_value)
        if timestamp_text is None or timestamp_ms is None:
            return None

        open_numeric = self._normalize_history_float(open_value)
        high_numeric = self._normalize_history_float(high_value)
        low_numeric = self._normalize_history_float(low_value)
        close_numeric = self._normalize_history_float(close_value)
        volume_numeric = self._normalize_history_float(volume_value)

        ohlc_values = [open_numeric, high_numeric, low_numeric, close_numeric]
        if any(value is None or value <= 0 for value in ohlc_values):
            return None

        normalized_high = max(ohlc_values)
        normalized_low = min(ohlc_values)
        normalized_volume = max(volume_numeric or 0.0, 0.0)

        return {
            "timestamp_ms": timestamp_ms,
            "row": [
                timestamp_text,
                float(open_numeric),
                float(normalized_high),
                float(normalized_low),
                float(close_numeric),
                float(normalized_volume),
            ],
        }

    def _sanitize_ohlcv_rows(self, symbol, timeframe, rows, *, requested_limit=50000, source_label="broker"):
        normalized_symbol = str(symbol or "").upper().strip() or "UNKNOWN"
        normalized_timeframe = str(timeframe or self.time_frame or "1h").strip() or "1h"
        deduped_rows = {}
        malformed_count = 0
        duplicate_count = 0

        for row in rows or []:
            normalized = self._normalize_ohlcv_row(row)
            if normalized is None:
                malformed_count += 1
                continue

            timestamp_ms = normalized["timestamp_ms"]
            if timestamp_ms in deduped_rows:
                duplicate_count += 1
            deduped_rows[timestamp_ms] = normalized["row"]

        cleaned_rows = [deduped_rows[key] for key in sorted(deduped_rows)]
        if requested_limit is not None:
            try:
                limit_value = max(1, int(requested_limit))
            except Exception:
                limit_value = None
            if limit_value is not None:
                cleaned_rows = cleaned_rows[-limit_value:]

        if malformed_count or duplicate_count:
            detail_parts = []
            if malformed_count:
                detail_parts.append(f"dropped {malformed_count} malformed row(s)")
            if duplicate_count:
                detail_parts.append(f"replaced {duplicate_count} duplicate timestamp row(s)")
            self._log_market_data_warning_once(
                f"ohlcv-sanitize:{source_label}:{normalized_symbol}:{normalized_timeframe}",
                (
                        f"Sanitized OHLCV data for {normalized_symbol} ({normalized_timeframe}) from {source_label}: "
                        f"kept {len(cleaned_rows)} row(s), " + ", ".join(detail_parts) + "."
                ),
                interval_seconds=30.0,
            )

        return cleaned_rows

    def _history_timestamp_text(self, value):
        if value in (None, ""):
            return ""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc).isoformat()
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

    def _finalize_trade_history_row(self, row):
        if not isinstance(row, dict):
            return row
        finalized = dict(row)
        finalized["outcome"] = (
                derive_trade_outcome(
                    outcome=finalized.get("outcome"),
                    pnl=finalized.get("pnl"),
                    status=finalized.get("status"),
                )
                or ""
        )
        return finalized

    def _normalize_broker_trade_history_row(self, row, repo_meta=None):
        if not isinstance(row, dict):
            return None
        repo_meta = dict(repo_meta or {})

        order_id = str(
            row.get("order_id")
            or row.get("orderID")
            or row.get("id")
            or row.get("tradeID")
            or row.get("clientOrderId")
            or ""
        ).strip()
        symbol = str(row.get("symbol") or row.get("instrument") or "").strip()

        side = row.get("side")
        if not side:
            units = self._normalize_history_float(
                row.get("currentUnits") or row.get("units") or row.get("amount") or row.get("filled")
            )
            if units is not None:
                side = "buy" if units >= 0 else "sell"
        size = self._normalize_history_float(
            row.get("amount")
            or row.get("filled")
            or row.get("units")
            or row.get("currentUnits")
            or row.get("initialUnits")
            or repo_meta.get("size")
        )
        if size is not None:
            size = abs(size)

        timestamp = (
                row.get("timestamp")
                or row.get("datetime")
                or row.get("time")
                or row.get("closeTime")
                or row.get("openTime")
                or repo_meta.get("timestamp")
                or ""
        )
        status = str(
            row.get("status")
            or row.get("state")
            or row.get("orderState")
            or repo_meta.get("status")
            or "filled"
        ).strip().lower()

        normalized = {
            "trade_db_id": repo_meta.get("trade_db_id"),
            "timestamp": self._history_timestamp_text(timestamp),
            "symbol": symbol,
            "source": repo_meta.get("source") or "broker_trade_history",
            "side": str(side or "").strip().lower(),
            "price": row.get("price") or row.get("average") or row.get("averagePrice") or repo_meta.get("price") or "",
            "size": size if size is not None else "",
            "order_type": row.get("type") or repo_meta.get("order_type") or "",
            "status": status,
            "order_id": order_id,
            "pnl": row.get("pnl") or row.get("realizedPL") or row.get("pl") or repo_meta.get("pnl") or "",
            "strategy_name": repo_meta.get("strategy_name") or "",
            "reason": repo_meta.get("reason") or "",
            "confidence": repo_meta.get("confidence") or "",
            "expected_price": repo_meta.get("expected_price") or "",
            "spread_bps": repo_meta.get("spread_bps") or "",
            "slippage_bps": repo_meta.get("slippage_bps") or "",
            "fee": row.get("fee") or row.get("commission") or row.get("cost") or repo_meta.get("fee") or "",
            "stop_loss": repo_meta.get("stop_loss") or "",
            "take_profit": repo_meta.get("take_profit") or "",
            "setup": repo_meta.get("setup") or "",
            "outcome": repo_meta.get("outcome") or "",
            "lessons": repo_meta.get("lessons") or "",
            "history_kind": "broker_trade",
        }
        if not normalized["symbol"] and not normalized["order_id"]:
            return None
        return self._finalize_trade_history_row(normalized)

    def _trade_history_dedupe_key(self, row):
        if not isinstance(row, dict):
            return ""
        order_id = str(row.get("order_id") or "").strip()
        if order_id:
            return f"order:{order_id}"
        timestamp = self._history_timestamp_text(row.get("timestamp"))
        symbol = str(row.get("symbol") or "").strip().upper()
        side = str(row.get("side") or "").strip().lower()
        price = self._normalize_history_float(row.get("price"))
        size = self._normalize_history_float(row.get("size"))
        return f"row:{timestamp}|{symbol}|{side}|{price}|{size}"

    async def fetch_trade_history(self, limit=300):
        limit = max(50, int(limit or 300))
        rows = list(await self.fetch_closed_trade_journal(limit=limit) or [])
        seen = {self._trade_history_dedupe_key(row) for row in rows if self._trade_history_dedupe_key(row)}

        source_map = {}
        for row in rows:
            order_id = str(row.get("order_id") or "").strip()
            if order_id and order_id not in source_map:
                source_map[order_id] = dict(row)

        broker = getattr(self, "broker", None)
        broker_rows = []
        if broker is not None:
            try:
                if self._resolve_broker_capability("fetch_my_trades"):
                    broker_rows = await broker.fetch_my_trades(limit=limit)
                elif self._resolve_broker_capability("fetch_trades"):
                    broker_rows = await broker.fetch_trades(None, limit=limit)
            except TypeError:
                try:
                    broker_rows = await broker.fetch_trades(limit=limit)
                except Exception as exc:
                    self.logger.debug("Trade-history fetch failed: %s", exc)
                    broker_rows = []
            except Exception as exc:
                self.logger.debug("Trade-history fetch failed: %s", exc)
                broker_rows = []

        for raw_row in broker_rows or []:
            order_id = str(
                (raw_row or {}).get("order_id")
                or (raw_row or {}).get("orderID")
                or (raw_row or {}).get("id")
                or ""
            ).strip()
            normalized = self._normalize_broker_trade_history_row(raw_row, repo_meta=source_map.get(order_id))
            if normalized is None:
                continue
            key = self._trade_history_dedupe_key(normalized)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(normalized)

        rows.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return rows[:limit]

    def _trade_history_stats(self, rows):
        stats = {
            "trade_count": 0,
            "pnl_count": 0,
            "wins": 0,
            "losses": 0,
            "flat": 0,
            "net_pnl": 0.0,
            "avg_pnl": None,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": None,
            "fees": 0.0,
            "avg_fee": None,
            "avg_slippage": None,
            "journal_coverage": None,
            "best_symbol": None,
            "worst_symbol": None,
            "strategy_rows": [],
            "symbol_rows": [],
            "recent_trades": [],
            "source_breakdown": {},
        }
        if not rows:
            return stats

        strategy_map = {}
        symbol_map = {}
        slippage_values = []
        fee_values = []
        journal_complete = 0

        for row in rows:
            stats["trade_count"] += 1
            source = str(row.get("source") or "unknown").strip().lower() or "unknown"
            stats["source_breakdown"][source] = stats["source_breakdown"].get(source, 0) + 1

            symbol = str(row.get("symbol") or "-").strip().upper() or "-"
            strategy = str(row.get("strategy_name") or "Unspecified").strip() or "Unspecified"
            pnl = self._normalize_history_float(row.get("pnl"))
            fee = self._normalize_history_float(row.get("fee"))
            slippage = self._normalize_history_float(row.get("slippage_bps"))

            stats["recent_trades"].append(
                {
                    "timestamp": self._history_timestamp_text(row.get("timestamp")),
                    "symbol": symbol,
                    "side": str(row.get("side") or "").upper(),
                    "status": str(row.get("status") or "").upper(),
                    "pnl": pnl,
                    "source": source,
                }
            )

            if fee is not None:
                stats["fees"] += fee
                fee_values.append(fee)
            if slippage is not None:
                slippage_values.append(slippage)

            if str(row.get("reason") or "").strip() and str(row.get("lessons") or "").strip():
                journal_complete += 1

            if strategy not in strategy_map:
                strategy_map[strategy] = {"strategy": strategy, "trades": 0, "wins": 0, "net_pnl": 0.0}
            if symbol not in symbol_map:
                symbol_map[symbol] = {"symbol": symbol, "trades": 0, "wins": 0, "net_pnl": 0.0}
            strategy_map[strategy]["trades"] += 1
            symbol_map[symbol]["trades"] += 1

            if pnl is None:
                continue
            stats["pnl_count"] += 1
            stats["net_pnl"] += pnl
            strategy_map[strategy]["net_pnl"] += pnl
            symbol_map[symbol]["net_pnl"] += pnl
            if pnl > 0:
                stats["wins"] += 1
                stats["gross_profit"] += pnl
                strategy_map[strategy]["wins"] += 1
                symbol_map[symbol]["wins"] += 1
            elif pnl < 0:
                stats["losses"] += 1
                stats["gross_loss"] += abs(pnl)
            else:
                stats["flat"] += 1

        if stats["pnl_count"] > 0:
            stats["avg_pnl"] = stats["net_pnl"] / float(stats["pnl_count"])
            total_decisions = stats["wins"] + stats["losses"] + stats["flat"]
            if total_decisions > 0:
                stats["win_rate"] = stats["wins"] / float(total_decisions)
            if stats["gross_loss"] > 0:
                stats["profit_factor"] = stats["gross_profit"] / stats["gross_loss"]
            elif stats["gross_profit"] > 0:
                stats["profit_factor"] = float("inf")
        else:
            stats["win_rate"] = None
        stats["journal_coverage"] = journal_complete / float(stats["trade_count"]) if stats["trade_count"] else None
        stats["avg_fee"] = (sum(fee_values) / len(fee_values)) if fee_values else None
        stats["avg_slippage"] = (sum(slippage_values) / len(slippage_values)) if slippage_values else None

        strategy_rows = []
        for item in strategy_map.values():
            trades = int(item["trades"] or 0)
            strategy_rows.append(
                {
                    "strategy": item["strategy"],
                    "trades": trades,
                    "win_rate": (item["wins"] / float(trades)) if trades else None,
                    "net_pnl": item["net_pnl"],
                }
            )
        strategy_rows.sort(key=lambda item: (item.get("net_pnl") or 0.0, item.get("trades") or 0), reverse=True)
        stats["strategy_rows"] = strategy_rows[:5]

        symbol_rows = []
        for item in symbol_map.values():
            trades = int(item["trades"] or 0)
            symbol_rows.append(
                {
                    "symbol": item["symbol"],
                    "trades": trades,
                    "win_rate": (item["wins"] / float(trades)) if trades else None,
                    "net_pnl": item["net_pnl"],
                }
            )
        symbol_rows.sort(key=lambda item: (item.get("net_pnl") or 0.0, item.get("trades") or 0), reverse=True)
        stats["symbol_rows"] = symbol_rows[:5]
        if symbol_rows:
            stats["best_symbol"] = max(symbol_rows, key=lambda item: item.get("net_pnl") or 0.0)
            stats["worst_symbol"] = min(symbol_rows, key=lambda item: item.get("net_pnl") or 0.0)

        stats["recent_trades"] = stats["recent_trades"][:8]
        return stats

    async def get_trade_history_analysis(self, limit=300):
        rows = await self.fetch_trade_history(limit=limit)
        return {
            "rows": rows,
            "stats": self._trade_history_stats(rows),
        }

    async def market_chat_trade_history_summary(self, limit=300, open_window=True):
        analysis = await self.get_trade_history_analysis(limit=limit)
        rows = list(analysis.get("rows") or [])
        stats = dict(analysis.get("stats") or {})

        terminal = getattr(self, "terminal", None)
        if open_window and terminal is not None:
            try:
                terminal._open_closed_journal_window()
                terminal._open_trade_journal_review_window()
            except Exception:
                pass

        if not rows:
            return "Trade history analysis is not available yet because no closed broker or stored trades were found."

        source_parts = [
            f"{name}: {count}"
            for name, count in sorted((stats.get("source_breakdown") or {}).items(), key=lambda item: item[1], reverse=True)
        ]
        win_rate = self._safe_balance_metric(stats.get("win_rate"))
        win_rate_text = "-" if win_rate is None else f"{win_rate * 100.0:.1f}%"
        lines = [
            "Trade history analysis loaded.",
            (
                f"Trades: {stats.get('trade_count', 0)}"
                f" | With PnL: {stats.get('pnl_count', 0)}"
                f" | Net PnL: {float(stats.get('net_pnl', 0.0) or 0.0):.2f}"
                f" | Win rate: {win_rate_text}"
            ),
        ]
        if stats.get("avg_pnl") is not None or stats.get("profit_factor") is not None:
            profit_factor = stats.get("profit_factor")
            pf_text = "-" if profit_factor is None else ("infinite" if profit_factor == float("inf") else f"{float(profit_factor):.2f}")
            avg_slippage = stats.get("avg_slippage")
            avg_slippage_text = "-" if avg_slippage is None else f"{float(avg_slippage):.2f} bps"
            lines.append(
                f"Avg trade: {float(stats.get('avg_pnl') or 0.0):.2f} | Profit factor: {pf_text} | "
                f"Fees: {float(stats.get('fees', 0.0) or 0.0):.2f} | Avg slippage: {avg_slippage_text}"
            )
        if source_parts:
            lines.append("Sources: " + " | ".join(source_parts[:4]))
        best_symbol = stats.get("best_symbol")
        worst_symbol = stats.get("worst_symbol")
        if best_symbol is not None:
            lines.append(f"Best symbol: {best_symbol.get('symbol')} ({float(best_symbol.get('net_pnl') or 0.0):.2f})")
        if worst_symbol is not None:
            lines.append(f"Worst symbol: {worst_symbol.get('symbol')} ({float(worst_symbol.get('net_pnl') or 0.0):.2f})")
        top_strategy = next(iter(stats.get("strategy_rows") or []), None)
        if top_strategy is not None:
            lines.append(
                f"Top strategy: {top_strategy.get('strategy')} | Trades: {top_strategy.get('trades')} | "
                f"Net PnL: {float(top_strategy.get('net_pnl') or 0.0):.2f}"
            )
        recent = list(stats.get("recent_trades") or [])[:3]
        if recent:
            recent_bits = []
            for item in recent:
                pnl = item.get("pnl")
                pnl_text = "-" if pnl is None else f"{float(pnl):.2f}"
                outcome_text = str(item.get("outcome") or item.get("status") or "").strip()
                recent_bits.append(f"{item.get('symbol')} {item.get('side')} {outcome_text} pnl {pnl_text}")
            lines.append("Recent trades: " + " ; ".join(recent_bits))
        lines.append("Use Tools -> Closed Journal and Journal Review for the detailed history and review.")
        return "\n".join(lines)

    async def telegram_status_text(self):
        scope = self._autotrade_scope_display_name(getattr(self, "autotrade_scope", "all"))
        return (
            "<b>Sopotek Status</b>\n"
            f"Connected: <b>{'YES' if self.connected else 'NO'}</b>\n"
            f"Exchange: <code>{getattr(getattr(self, 'broker', None), 'exchange_name', '-') or '-'}</code>\n"
            f"AI Scope: <b>{scope}</b>\n"
            f"Symbols Loaded: <code>{len(getattr(self, 'symbols', []) or [])}</code>\n"
            f"Market Data: <code>{self.get_market_stream_status()}</code>\n"
            f"Timeframe: <code>{getattr(self, 'time_frame', '1h')}</code>\n"
            f"Balances: {await self.telegram_balances_text(compact=True)}"
        )

    async def telegram_balances_text(self, compact=False):
        balances = getattr(self, "balances", {}) or {}
        if isinstance(balances, dict) and isinstance(balances.get("total"), dict):
            source = balances.get("total") or {}
        elif isinstance(balances, dict):
            source = {
                key: value for key, value in balances.items()
                if isinstance(value, (int, float)) and key not in {"free", "used", "total", "info"}
            }
        else:
            source = {}

        ranked = []
        for asset, value in source.items():
            try:
                numeric = float(value)
            except Exception:
                continue
            if abs(numeric) <= 1e-12:
                continue
            ranked.append((str(asset).upper(), numeric))
        ranked.sort(key=lambda item: abs(item[1]), reverse=True)

        if not ranked:
            return "<code>-</code>" if compact else "<b>Balances</b>\nNo balance data available."

        lines = [f"<code>{asset}: {amount:,.6f}</code>" for asset, amount in ranked[:8]]
        return " | ".join(lines[:4]) if compact else "<b>Balances</b>\n" + "\n".join(lines)

    async def telegram_positions_text(self):
        positions = self._market_chat_positions_snapshot()
        if not positions:
            return "<b>Positions</b>\nNo open positions."

        lines = ["<b>Positions</b>"]
        for position in positions[:10]:
            lines.append(
                f"<code>{position.get('symbol', '-')}</code> | {position.get('side', '-')} | "
                f"size {position.get('size', position.get('amount', '-'))} | PnL {position.get('pnl', '-')}"
            )
        return "\n".join(lines)

    async def telegram_open_orders_text(self):
        orders = self._market_chat_open_orders_snapshot()
        if not orders:
            return "<b>Open Orders</b>\nNo open orders."

        lines = ["<b>Open Orders</b>"]
        for order in orders[:10]:
            lines.append(
                f"<code>{order.get('symbol', '-')}</code> | {order.get('side', '-')} | {order.get('status', '-')} | "
                f"qty {order.get('amount', order.get('size', '-'))} | px {order.get('price', '-')}"
            )
        return "\n".join(lines)

    async def telegram_recommendations_text(self):
        terminal = getattr(self, "terminal", None)
        if terminal is None or not hasattr(terminal, "_recommendation_rows"):
            return "<b>Recommendations</b>\nRecommendations are not available right now."
        try:
            rows = list(terminal._recommendation_rows() or [])
        except Exception:
            rows = []
        if not rows:
            return "<b>Recommendations</b>\nNo active recommendations yet."

        lines = ["<b>Recommendations</b>"]
        for row in rows[:8]:
            lines.append(
                f"<code>{row.get('symbol', '-')}</code> | {row.get('action', '-')} | "
                f"conf {row.get('confidence', '-')} | {row.get('why', row.get('reason', '-'))}"
            )
        return "\n".join(lines)

    async def telegram_performance_text(self):
        terminal = getattr(self, "terminal", None)
        if terminal is None or not hasattr(terminal, "_build_performance_snapshot"):
            return "<b>Performance</b>\nPerformance analytics are not available right now."

        try:
            snapshot = terminal._build_performance_snapshot() or {}
        except Exception:
            snapshot = {}
        if not snapshot:
            return "<b>Performance</b>\nNo performance snapshot is available yet."

        return (
            "<b>Performance</b>\n"
            f"Equity: <code>{snapshot.get('equity', '-')}</code>\n"
            f"Net PnL: <code>{snapshot.get('net_pnl', '-')}</code>\n"
            f"Win Rate: <code>{snapshot.get('win_rate_label', '-')}</code>\n"
            f"Max Drawdown: <code>{snapshot.get('max_drawdown_label', '-')}</code>\n"
            f"Profit Factor: <code>{snapshot.get('profit_factor_label', '-')}</code>\n"
            f"Fees: <code>{snapshot.get('fees_label', '-')}</code>\n"
            f"Avg Slippage: <code>{snapshot.get('avg_slippage_label', '-')}</code>"
        )

    async def telegram_settings_text(self, open_window=True):
        opened_message = ""
        if open_window:
            try:
                opened_message = str(self.market_chat_open_window("settings") or "").strip()
            except Exception:
                opened_message = ""

        market_type = str(getattr(self, "market_trade_preference", "auto") or "auto").strip() or "auto"
        timeframe = str(getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        scope = self._autotrade_scope_display_name(getattr(self, "autotrade_scope", "all"))
        broker_label = str(getattr(getattr(self, "broker", None), "exchange_name", "-") or "-").upper()
        telegram_snapshot = self.telegram_status_snapshot()
        lines = []
        if opened_message:
            lines.append(opened_message)
        else:
            lines.append("Settings summary loaded.")
        lines.extend(
            [
                f"Broker: {broker_label}",
                f"Timeframe: {timeframe}",
                f"AI Scope: {scope}",
                f"Market Venue: {market_type}",
                f"Database Mode: {str(getattr(self, 'database_mode', 'local') or 'local').upper()}",
                f"Risk Profile: {str(getattr(self, 'risk_profile_name', '-') or '-')}",
                (
                    f"News Feed: {'ON' if bool(getattr(self, 'news_enabled', False)) else 'OFF'}"
                    f" | News AutoTrade: {'ON' if bool(getattr(self, 'news_autotrade_enabled', False)) else 'OFF'}"
                ),
                (
                    f"Telegram: {'ON' if telegram_snapshot.get('enabled') else 'OFF'}"
                    f" | Configured: {'YES' if telegram_snapshot.get('configured') else 'NO'}"
                    f" | Can Send: {'YES' if telegram_snapshot.get('can_send') else 'NO'}"
                ),
            ]
        )
        return "\n".join(lines)

    async def telegram_health_text(self, open_window=True):
        summary = await self.market_chat_app_status_summary(show_panel=open_window)
        return str(summary or "System health summary is not available right now.").strip()

    async def telegram_quant_pm_text(self, open_window=True):
        summary = await self.market_chat_quant_pm_summary(open_window=open_window)
        return str(summary or "Quant PM summary is not available right now.").strip()

    async def telegram_journal_text(self, open_window=True):
        return await self.market_chat_trade_history_summary(limit=300, open_window=open_window)

    async def telegram_journal_review_text(self, period="Weekly", open_window=True):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return "Journal review is not available right now."

        if open_window and hasattr(terminal, "_open_trade_journal_review_window"):
            try:
                terminal._open_trade_journal_review_window()
            except Exception:
                pass

        helpers = [
            "_journal_review_bounds",
            "_rows_for_journal_period",
            "_journal_review_analysis_rows",
            "_summarize_journal_rows",
            "_journal_review_mistakes",
            "_journal_review_edge_decay",
        ]
        if not all(hasattr(terminal, name) for name in helpers):
            return await self.market_chat_trade_history_summary(limit=300, open_window=open_window)

        try:
            rows = await self.fetch_trade_history(limit=700)
        except Exception:
            rows = []
        if not rows:
            return "Journal review is not available yet because no closed trades were found."

        mode, previous_start, current_start, now = terminal._journal_review_bounds(period)
        current_rows = terminal._journal_review_analysis_rows(
            terminal._rows_for_journal_period(rows, current_start, now)
        )
        previous_rows = terminal._journal_review_analysis_rows(
            terminal._rows_for_journal_period(rows, previous_start, current_start)
        )
        current_stats = terminal._summarize_journal_rows(current_rows)
        previous_stats = terminal._summarize_journal_rows(previous_rows)
        mistakes = list(terminal._journal_review_mistakes(current_rows, current_stats) or [])
        edge_decay = list(terminal._journal_review_edge_decay(current_stats, previous_stats) or [])

        def fmt_money(value):
            try:
                return f"{float(value):.2f}"
            except Exception:
                return "-"

        def fmt_pct(value):
            try:
                return f"{float(value) * 100.0:.1f}%"
            except Exception:
                return "-"

        profit_factor = current_stats.get("profit_factor")
        profit_factor_text = "-"
        if profit_factor is not None:
            try:
                profit_factor_text = f"{float(profit_factor):.2f}"
            except Exception:
                profit_factor_text = "-"

        lines = [
            "Journal review loaded.",
            (
                f"Period: {mode}"
                f" | Trades: {int(current_stats.get('trade_count') or 0)}"
                f" | Net PnL: {fmt_money(current_stats.get('net_pnl'))}"
                f" | Win rate: {fmt_pct(current_stats.get('win_rate'))}"
            ),
            (
                f"Avg trade: {fmt_money(current_stats.get('avg_pnl'))}"
                f" | Profit factor: {profit_factor_text}"
                f" | Journal coverage: {fmt_pct(current_stats.get('journal_coverage'))}"
            ),
        ]
        top_strategy = next(iter(current_stats.get("strategy_rows") or []), None)
        if top_strategy is not None:
            lines.append(
                f"Top strategy: {top_strategy.get('strategy')} | Trades: {top_strategy.get('trades')} | "
                f"Net PnL: {fmt_money(top_strategy.get('net_pnl'))}"
            )
        if mistakes:
            lines.append("Review focus: " + " | ".join(str(item) for item in mistakes[:2]))
        if edge_decay:
            lines.append("Edge decay: " + " | ".join(str(item) for item in edge_decay[:2]))
        lines.append("Use Tools -> Closed Journal and Journal Review for the full annotated breakdown.")
        return "\n".join(lines)

    async def telegram_logs_text(self, open_window=True):
        return str(self.market_chat_error_log_summary(open_window=open_window) or "No log summary is available right now.").strip()

    async def telegram_position_analysis_text(self, open_window=True):
        summary = self.market_chat_position_summary(open_window=open_window)
        if not summary:
            return "<b>Position Analysis</b>\nPosition analysis is not available right now."
        return f"<b>Position Analysis</b>\n<pre>{self._plain_text(summary)}</pre>"

    async def telegram_open_chart(self, symbol, timeframe=None):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return {"ok": False, "message": "Terminal is not available."}

        requested_symbol = str(symbol or "").upper().strip()
        requested_timeframe = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        if not requested_symbol:
            return {"ok": False, "message": "A symbol is required."}

        try:
            terminal._open_symbol_chart(requested_symbol, requested_timeframe)
            chart = terminal._chart_for_symbol(requested_symbol) if hasattr(terminal, "_chart_for_symbol") else None
            if chart is not None and hasattr(terminal, "_schedule_chart_data_refresh"):
                terminal._schedule_chart_data_refresh(chart)
            QApplication.processEvents()
            await asyncio.sleep(0.25)
            QApplication.processEvents()
        except Exception as exc:
            return {"ok": False, "message": f"Unable to open chart {requested_symbol}: {exc}"}

        chart = terminal._chart_for_symbol(requested_symbol) if hasattr(terminal, "_chart_for_symbol") else None
        if chart is None:
            return {"ok": False, "message": f"Chart {requested_symbol} could not be opened."}
        return {
            "ok": True,
            "message": f"Chart opened for {requested_symbol} ({requested_timeframe}).",
            "symbol": requested_symbol,
            "timeframe": requested_timeframe,
        }

    async def capture_chart_screenshot(self, symbol=None, timeframe=None, prefix="chart"):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return None

        requested_symbol = str(symbol or "").upper().strip()
        requested_timeframe = str(timeframe or getattr(self, "time_frame", "1h") or "1h").strip() or "1h"
        if requested_symbol:
            open_result = await self.telegram_open_chart(requested_symbol, requested_timeframe)
            if not open_result.get("ok"):
                return None

        chart = None
        if requested_symbol and hasattr(terminal, "_chart_for_symbol"):
            chart = terminal._chart_for_symbol(requested_symbol)
        if chart is None and hasattr(terminal, "_current_chart_widget"):
            chart = terminal._current_chart_widget()
        if chart is None:
            return None

        safe_symbol = sanitize_screenshot_fragment(
            str(getattr(chart, "symbol", requested_symbol or "chart")),
            "chart",
        )
        try:
            QApplication.processEvents()
            await asyncio.sleep(0.15)
            QApplication.processEvents()
            return capture_widget_to_output(chart, prefix=prefix, suffix=safe_symbol)
        except Exception as exc:
            self.logger.debug("Chart screenshot capture failed: %s", exc)
            return None

    async def capture_telegram_screenshot(self):
        return await self.capture_app_screenshot(prefix="telegram")

    async def capture_app_screenshot(self, prefix="market_chat"):
        terminal = getattr(self, "terminal", None)
        if terminal is None:
            return None

        try:
            return capture_widget_to_output(terminal, prefix=prefix)
        except Exception as exc:
            self.logger.debug("App screenshot capture failed: %s", exc)
            return None

    def _plain_text(self, value):
        text = str(value or "")
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = (
            text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
        )
        return re.sub(r"\s+", " ", text).strip()

    def _openai_news_focus_symbols(self):
        symbols = []
        terminal = getattr(self, "terminal", None)
        active_chart = None
        if terminal is not None and hasattr(terminal, "_current_chart_widget"):
            try:
                active_chart = terminal._current_chart_widget()
            except Exception:
                active_chart = None

        for value in [
            getattr(active_chart, "symbol", None),
            getattr(terminal, "symbol", None) if terminal is not None else None,
        ]:
            symbol = str(value or "").upper().strip()
            if symbol and symbol not in symbols:
                symbols.append(symbol)

        if terminal is not None and hasattr(terminal, "_recommendation_rows"):
            try:
                for item in list(terminal._recommendation_rows() or [])[:3]:
                    symbol = str(item.get("symbol") or "").upper().strip()
                    if symbol and symbol not in symbols:
                        symbols.append(symbol)
            except Exception:
                pass

        for symbol in list(getattr(self, "symbols", []) or [])[:3]:
            normalized = str(symbol or "").upper().strip()
            if normalized and normalized not in symbols:
                symbols.append(normalized)

        return symbols[:3]

    async def _openai_news_context(self, question=""):
        if not getattr(self, "news_enabled", False):
            return []

        lowered = str(question or "").lower()
        wants_news = any(
            token in lowered
            for token in ("news", "headline", "headlines", "event", "events", "rss", "sentiment", "impact")
        )
        symbols = self._openai_news_focus_symbols()
        if not symbols:
            return []

        lines = []
        for symbol in symbols:
            try:
                cached = self._news_cache.get(symbol, {})
                events = list(cached.get("events", []) or [])
                if wants_news or not events:
                    events = await self.request_news(symbol, force=wants_news, max_age_seconds=300)
                if not events:
                    continue
                bias = self.news_service.summarize_news_bias(events)
                direction = self._plain_text(bias.get("direction") or "neutral")
                reason = self._plain_text(bias.get("reason") or "")
                headline = self._plain_text(bias.get("headline") or "")
                score = bias.get("score")
                try:
                    score_text = f"{float(score):.2f}"
                except Exception:
                    score_text = "0.00"
                recent = []
                for event in list(events[:3]):
                    title = self._plain_text(event.get("title") or "")
                    source = self._plain_text(event.get("source") or "News")
                    impact = event.get("impact")
                    try:
                        impact_text = f"{float(impact):.2f}"
                    except Exception:
                        impact_text = "-"
                    if title:
                        recent.append(f"{source}: {title} (impact {impact_text})")
                line = f"News for {symbol}: bias {direction} score {score_text}"
                if reason:
                    line += f" | reason: {reason}"
                if headline:
                    line += f" | headline summary: {headline}"
                if recent:
                    line += " | recent: " + " ; ".join(recent)
                lines.append(line)
            except Exception as exc:
                self.logger.debug("OpenAI news context failed for %s: %s", symbol, exc)
        return lines

    async def _build_openai_runtime_context(self, question=""):
        terminal = getattr(self, "terminal", None)
        broker = getattr(self, "broker", None)
        context_parts = [
            "Sopotek runtime context:",
            f"Connected: {self.connected}",
            f"Mode: {self.current_trading_mode()}",
            f"Exchange: {getattr(broker, 'exchange_name', '-') or '-'}",
            f"Account: {self.current_account_label()}",
            f"Market Data: {self.get_market_stream_status()}",
            f"Telegram: {self.telegram_management_text().replace(chr(10), ' | ')}",
            f"AI Scope: {self._autotrade_scope_display_name(getattr(self, 'autotrade_scope', 'all'))}",
            f"Symbols Loaded: {len(getattr(self, 'symbols', []) or [])}",
            f"Default Timeframe: {getattr(self, 'time_frame', '1h')}",
            f"Health Check: {self.get_health_check_summary()}",
        ]
        bug_summary = self.market_chat_error_log_summary(open_window=False, max_entries=2)
        if bug_summary:
            context_parts.append("Bug Log Summary: " + self._plain_text(bug_summary))

        if terminal is not None:
            active_chart = None
            if hasattr(terminal, "_current_chart_widget"):
                try:
                    active_chart = terminal._current_chart_widget()
                except Exception:
                    active_chart = None
            if active_chart is not None:
                context_parts.append(
                    f"Active Chart: {getattr(active_chart, 'symbol', '-') or '-'} {getattr(active_chart, 'timeframe', '-') or '-'}"
                )
            context_parts.append(
                f"AI Trading Enabled: {bool(getattr(terminal, 'autotrading_enabled', False))}"
            )

        balances_text = self._plain_text(await self.telegram_balances_text(compact=False))
        positions_text = self._plain_text(await self.telegram_positions_text())
        orders_text = self._plain_text(await self.telegram_open_orders_text())
        if balances_text:
            context_parts.append(f"Balances: {balances_text}")
        if positions_text:
            context_parts.append(f"Positions: {positions_text}")
        if orders_text:
            context_parts.append(f"Open Orders: {orders_text}")
        position_summary = self.market_chat_position_summary(open_window=False)
        if position_summary:
            context_parts.append("Position Analysis: " + self._plain_text(position_summary))

        behavior = self.get_behavior_guard_status() or {}
        if behavior:
            summary = self._plain_text(behavior.get("summary") or "Active")
            reason = self._plain_text(behavior.get("reason") or "")
            cooldown = self._plain_text(behavior.get("cooldown_until") or "")
            behavior_line = f"Behavior Guard: {summary}"
            if reason:
                behavior_line += f" | Reason: {reason}"
            if cooldown:
                behavior_line += f" | Cooldown: {cooldown}"
            context_parts.append(behavior_line)

        if terminal is not None and hasattr(terminal, "_performance_snapshot"):
            try:
                snapshot = terminal._performance_snapshot() or {}
            except Exception:
                snapshot = {}
            if snapshot:
                context_parts.append(
                    f"Performance Headline: {self._plain_text(snapshot.get('headline') or 'Unavailable')}"
                )
                metrics = snapshot.get("metrics", {}) or {}
                selected_metrics = []
                for key in (
                        "Equity",
                        "Net PnL",
                        "Return",
                        "Win Rate",
                        "Profit Factor",
                        "Max Drawdown",
                        "Fees",
                        "Avg Slippage",
                        "Execution Drag",
                ):
                    text = self._plain_text((metrics.get(key) or {}).get("text"))
                    if text and text != "-":
                        selected_metrics.append(f"{key}: {text}")
                if selected_metrics:
                    context_parts.append("Performance Metrics: " + " | ".join(selected_metrics))

        if terminal is not None and hasattr(terminal, "_recommendation_rows"):
            try:
                recommendations = list(terminal._recommendation_rows() or [])[:5]
            except Exception:
                recommendations = []
            if recommendations:
                lines = []
                for item in recommendations:
                    symbol = self._plain_text(item.get("symbol") or "-")
                    action = self._plain_text(item.get("action") or item.get("side") or "-")
                    confidence = item.get("confidence")
                    why = self._plain_text(item.get("why") or item.get("reason") or "")

                    try:
                        confidence_text = f"{float(confidence):.2f}"
                    except Exception:
                        confidence_text = self._plain_text(confidence)
                    fragment = f"{symbol} {action}"
                    if confidence_text:
                        fragment += f" conf {confidence_text}"
                    if why:
                        fragment += f" because {why}"
                    lines.append(fragment.strip())
                if lines:
                    context_parts.append("Top Recommendations: " + " ; ".join(lines))

        try:
            trade_history_analysis = await self.get_trade_history_analysis(limit=250)
        except Exception:
            trade_history_analysis = {"rows": [], "stats": {}}
        trade_stats = dict(trade_history_analysis.get("stats") or {})
        if trade_stats.get("trade_count"):
            trade_bits = [
                f"trades {int(trade_stats.get('trade_count') or 0)}",
                f"net pnl {float(trade_stats.get('net_pnl') or 0.0):.2f}",
            ]
            if trade_stats.get("win_rate") is not None:
                trade_bits.append(f"win rate {float(trade_stats.get('win_rate')) * 100.0:.1f}%")
            if trade_stats.get("profit_factor") is not None:
                profit_factor = trade_stats.get("profit_factor")
                trade_bits.append(
                    "profit factor "
                    + ("infinite" if profit_factor == float("inf") else f"{float(profit_factor):.2f}")
                )
            if trade_stats.get("journal_coverage") is not None:
                trade_bits.append(f"journal coverage {float(trade_stats.get('journal_coverage')) * 100.0:.1f}%")
            context_parts.append("Trade History Analysis: " + " | ".join(trade_bits))

            best_symbol = trade_stats.get("best_symbol")
            worst_symbol = trade_stats.get("worst_symbol")
            if best_symbol is not None or worst_symbol is not None:
                best_text = (
                    f"best {self._plain_text(best_symbol.get('symbol'))} {float(best_symbol.get('net_pnl') or 0.0):.2f}"
                    if best_symbol is not None else ""
                )
                worst_text = (
                    f"worst {self._plain_text(worst_symbol.get('symbol'))} {float(worst_symbol.get('net_pnl') or 0.0):.2f}"
                    if worst_symbol is not None else ""
                )
                context_parts.append("Trade History Symbols: " + " | ".join(part for part in (best_text, worst_text) if part))

            strategy_rows = list(trade_stats.get("strategy_rows") or [])[:3]
            if strategy_rows:
                strategy_bits = []
                for item in strategy_rows:
                    fragment = (
                        f"{self._plain_text(item.get('strategy'))}: trades {int(item.get('trades') or 0)}, "
                        f"net pnl {float(item.get('net_pnl') or 0.0):.2f}"
                    )
                    if item.get("win_rate") is not None:
                        fragment += f", win rate {float(item.get('win_rate')) * 100.0:.1f}%"
                    strategy_bits.append(fragment)
                context_parts.append("Trade History Strategies: " + " ; ".join(strategy_bits))

            recent_rows = list(trade_stats.get("recent_trades") or [])[:5]
            if recent_rows:
                recent_bits = []
                for item in recent_rows:
                    pnl = item.get("pnl")
                    pnl_text = "-" if pnl is None else f"{float(pnl):.2f}"
                    recent_bits.append(
                        f"{self._plain_text(item.get('symbol'))} {self._plain_text(item.get('side'))} "
                        f"{self._plain_text(item.get('status'))} pnl {pnl_text}"
                    )
                context_parts.append("Recent Trade History: " + " ; ".join(recent_bits))

        if terminal is not None and hasattr(terminal, "symbols_table") and hasattr(terminal, "_market_watch_row_snapshot"):
            market_rows = []
            try:
                for row in range(min(5, terminal.symbols_table.rowCount())):
                    snapshot = terminal._market_watch_row_snapshot(row)
                    symbol = self._plain_text(snapshot.get("symbol"))
                    if not symbol:
                        continue
                    bid = self._plain_text(snapshot.get("bid"))
                    ask = self._plain_text(snapshot.get("ask"))
                    status = self._plain_text(snapshot.get("status"))
                    market_rows.append(f"{symbol} bid {bid} ask {ask} status {status}")
            except Exception:
                market_rows = []
            if market_rows:
                context_parts.append("Market Watch: " + " ; ".join(market_rows))

        news_lines = await self._openai_news_context(question=question)
        if news_lines:
            context_parts.extend(news_lines)

        return "\n".join(part for part in context_parts if part)

    async def ask_openai_about_app(self, question, conversation=None):
        action_result = await self.handle_market_chat_action(question)
        if action_result:
            return action_result

        api_key = str(getattr(self, "openai_api_key", "") or "").strip()
        if not api_key:
            return "OpenAI API key is not configured in Settings -> Integrations."

        context_text = await self._build_openai_runtime_context(question=question)
        history_items = []
        for item in list(conversation or [])[-8:]:
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            history_items.append({"role": role, "content": content})
        payload = {
            "model": self.openai_model or "gpt-5-mini",
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are an assistant inside Sopotek Quant System. "
                        "Answer briefly, practically, and honestly using the provided app and market context. "
                        "You can discuss the app, market behavior, balances, equity, performance, profitability, "
                        "recommendations, behavior guard status, and recent news/headline context. "
                        "If data is missing, say so clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": context_text,
                },
                *history_items,
                {
                    "role": "user",
                    "content": f"Question: {question}",
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400:
                        message = data.get("error", {}).get("message") or str(data)
                        return f"OpenAI request failed: {message}"
        except Exception as exc:
            return f"OpenAI request failed: {exc}"

        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()

        parts = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                content_text = content.get("text")
                if isinstance(content_text, str) and content_text.strip():
                    parts.append(content_text.strip())
        if parts:
            return "\n".join(parts)
        return "OpenAI returned no text."

    def market_chat_voice_available(self):
        return bool(self.market_chat_voice_input_available() or self.market_chat_voice_output_available())

    def market_chat_voice_input_available(self):
        service = getattr(self, "voice_service", None)
        return bool(service is not None and service.available())

    def _windows_market_chat_voice_available(self):
        service = getattr(self, "voice_service", None)
        return bool(service is not None and service.available())

    def _resolve_market_chat_output_provider(self, output_provider=None):
        requested = str(
            output_provider if output_provider is not None else getattr(self, "voice_output_provider", "windows") or "windows"
        ).strip().lower() or "windows"
        if requested not in {"windows", "openai"}:
            requested = "windows"
        if requested == "openai":
            if str(getattr(self, "openai_api_key", "") or "").strip():
                return "openai"
            if self._windows_market_chat_voice_available():
                return "windows"
        return requested

    def market_chat_voice_output_available(self):
        output_provider = self._resolve_market_chat_output_provider()
        if output_provider == "openai":
            return bool(str(getattr(self, "openai_api_key", "") or "").strip())
        return self._windows_market_chat_voice_available()

    def market_chat_voice_provider_choices(self):
        service = getattr(self, "voice_service", None)
        if service is None:
            return [("windows", "Windows"), ("google", "Google")]
        return list(service.available_recognition_providers())

    def market_chat_voice_output_provider_choices(self):
        return [("windows", "Windows"), ("openai", "OpenAI")]

    def _current_market_chat_voice_name(self):
        output_provider = str(getattr(self, "voice_output_provider", "windows") or "windows").strip().lower() or "windows"
        if output_provider == "openai":
            voice_name = str(getattr(self, "voice_openai_name", "alloy") or "alloy").strip().lower() or "alloy"
            return voice_name if voice_name in self.OPENAI_TTS_VOICES else "alloy"
        return str(getattr(self, "voice_windows_name", "") or "").strip()

    def market_chat_voice_state(self):
        service = getattr(self, "voice_service", None)
        provider = str(getattr(self, "voice_provider", "windows") or "windows").strip().lower() or "windows"
        output_provider = str(getattr(self, "voice_output_provider", "windows") or "windows").strip().lower() or "windows"
        effective_output_provider = self._resolve_market_chat_output_provider(output_provider)
        voice_name = str(self._current_market_chat_voice_name() or "").strip()
        google_ready = bool(service is not None and service.recognition_provider_available("google"))
        windows_ready = bool(service is not None and service.recognition_provider_available("windows"))
        return {
            "provider": provider,
            "recognition_provider": provider,
            "output_provider": output_provider,
            "effective_output_provider": effective_output_provider,
            "output_fallback": output_provider != effective_output_provider,
            "voice_name": voice_name,
            "google_available": google_ready,
            "windows_available": windows_ready,
            "listen_available": self.market_chat_voice_input_available(),
            "speak_available": self.market_chat_voice_output_available(),
            "voice_available": self.market_chat_voice_available(),
            "openai_available": bool(getattr(self, "openai_api_key", "")),
            "openai_model": self.OPENAI_TTS_MODEL,
        }

    async def market_chat_list_voices(self, output_provider=None):
        resolved_provider = self._resolve_market_chat_output_provider(output_provider)
        if resolved_provider == "openai":
            return list(self.OPENAI_TTS_VOICES)
        service = getattr(self, "voice_service", None)
        if service is None:
            return []
        voices = await service.list_voices()
        return [str(item).strip() for item in voices if str(item).strip()]

    def set_market_chat_voice(self, voice_name, output_provider=None):
        normalized = str(voice_name or "").strip()
        resolved_provider = str(
            output_provider if output_provider is not None else getattr(self, "voice_output_provider", "windows") or "windows"
        ).strip().lower() or "windows"
        service = getattr(self, "voice_service", None)
        if resolved_provider == "openai":
            normalized = normalized.lower()
            if normalized and normalized not in self.OPENAI_TTS_VOICES:
                normalized = "alloy"
            self.voice_openai_name = normalized or "alloy"
            self.settings.setValue("integrations/voice_openai_name", self.voice_openai_name)
        else:
            self.voice_windows_name = normalized
            if service is not None:
                service.set_voice(normalized)
            self.settings.setValue("integrations/voice_windows_name", self.voice_windows_name)
        self.voice_name = self._current_market_chat_voice_name()
        self.settings.setValue("integrations/voice_name", self.voice_name)
        return self.voice_name

    def set_market_chat_voice_provider(self, provider):
        normalized = str(provider or "windows").strip().lower() or "windows"
        if normalized not in {"windows", "google"}:
            normalized = "windows"
        self.voice_provider = normalized
        service = getattr(self, "voice_service", None)
        if service is not None:
            service.set_recognition_provider(normalized)
        self.settings.setValue("integrations/voice_provider", normalized)
        return normalized

    def set_market_chat_voice_output_provider(self, provider):
        normalized = str(provider or "windows").strip().lower() or "windows"
        if normalized not in {"windows", "openai"}:
            normalized = "windows"
        self.voice_output_provider = normalized
        self.voice_name = self._current_market_chat_voice_name()
        service = getattr(self, "voice_service", None)
        if service is not None and normalized == "windows":
            service.set_voice(self.voice_name)
        self.settings.setValue("integrations/voice_output_provider", normalized)
        self.settings.setValue("integrations/voice_name", self.voice_name)
        return normalized

    async def market_chat_listen(self, timeout_seconds=8):
        service = getattr(self, "voice_service", None)
        if service is None:
            return {"ok": False, "message": "Voice service is not initialized.", "text": ""}
        return await service.listen(timeout_seconds=timeout_seconds, provider=getattr(self, "voice_provider", "windows"))

    async def market_chat_speak(self, text):
        requested_output_provider = str(getattr(self, "voice_output_provider", "windows") or "windows").strip().lower() or "windows"
        output_provider = self._resolve_market_chat_output_provider(requested_output_provider)
        if output_provider == "openai":
            result = await self._market_chat_speak_openai(text, voice_name=self._current_market_chat_voice_name())
            if result.get("ok") or not self._windows_market_chat_voice_available():
                return result
            service = getattr(self, "voice_service", None)
            if service is None:
                return result
            fallback = await service.speak(text, voice_name=str(getattr(self, "voice_windows_name", "") or "").strip())
            if fallback.get("ok"):
                fallback["message"] = (
                    f"OpenAI speech failed ({result.get('message') or 'unknown error'}). Used Windows speech instead."
                )
            return fallback
        service = getattr(self, "voice_service", None)
        if service is None:
            return {"ok": False, "message": "Voice service is not initialized."}
        return await service.speak(text, voice_name=str(getattr(self, "voice_windows_name", "") or "").strip())

    async def _market_chat_speak_openai(self, text, voice_name="alloy"):
        message = str(text or "").strip()
        if not message:
            return {"ok": False, "message": "No text was provided to speak."}

        api_key = str(getattr(self, "openai_api_key", "") or "").strip()
        if not api_key:
            return {"ok": False, "message": "OpenAI API key is not configured in Settings -> Integrations."}

        normalized_voice = str(voice_name or "alloy").strip().lower() or "alloy"
        if normalized_voice not in self.OPENAI_TTS_VOICES:
            normalized_voice = "alloy"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload_candidates = [
            {
                "model": self.OPENAI_TTS_MODEL,
                "voice": normalized_voice,
                "input": message,
                "response_format": "wav",
            },
            {
                "model": self.OPENAI_TTS_MODEL,
                "voice": normalized_voice,
                "input": message,
                "format": "wav",
            },
        ]

        audio_bytes = b""
        last_error = ""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                for payload in payload_candidates:
                    async with session.post("https://api.openai.com/v1/audio/speech", json=payload, headers=headers) as response:
                        if response.status >= 400:
                            try:
                                data = await response.json(content_type=None)
                                last_error = data.get("error", {}).get("message") or str(data)
                            except Exception:
                                last_error = await response.text()
                            continue
                        audio_bytes = await response.read()
                        if audio_bytes:
                            break
        except Exception as exc:
            return {"ok": False, "message": f"OpenAI voice playback failed: {exc}"}

        if not audio_bytes:
            return {"ok": False, "message": f"OpenAI voice playback failed: {last_error or 'empty audio returned.'}"}
        if winsound is None:
            return {"ok": False, "message": "OpenAI voice playback is currently available only on Windows."}

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
                handle.write(audio_bytes)
                temp_path = handle.name
            await asyncio.to_thread(winsound.PlaySound, temp_path, winsound.SND_FILENAME)
        except Exception as exc:
            return {"ok": False, "message": f"OpenAI voice playback failed: {exc}"}
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

        self.voice_openai_name = normalized_voice
        self.voice_name = normalized_voice
        self.settings.setValue("integrations/voice_openai_name", normalized_voice)
        self.settings.setValue("integrations/voice_name", normalized_voice)
        return {"ok": True, "message": f"Reply spoken with OpenAI voice {normalized_voice}."}

    async def test_openai_connection(self, api_key=None, model=None):
        resolved_key = str(api_key if api_key is not None else getattr(self, "openai_api_key", "") or "").strip()
        if not resolved_key:
            return {"ok": False, "message": "OpenAI API key is not configured."}

        resolved_model = str(model if model is not None else getattr(self, "openai_model", "gpt-5-mini") or "gpt-5-mini").strip() or "gpt-5-mini"
        payload = {
            "model": resolved_model,
            "input": [
                {"role": "system", "content": "Reply in one short sentence."},
                {"role": "user", "content": "Say OpenAI connection OK and today's UTC date."},
            ],
        }
        headers = {
            "Authorization": f"Bearer {resolved_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400:
                        message = data.get("error", {}).get("message") or str(data)
                        return {"ok": False, "message": f"OpenAI request failed: {message}"}
        except Exception as exc:
            return {"ok": False, "message": f"OpenAI request failed: {exc}"}

        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return {"ok": True, "message": text.strip()}

        parts = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                content_text = content.get("text")
                if isinstance(content_text, str) and content_text.strip():
                    parts.append(content_text.strip())
        if parts:
            return {"ok": True, "message": "\n".join(parts)}
        return {"ok": False, "message": "OpenAI returned no text."}

    async def _safe_fetch_ohlcv(self, symbol, timeframe="1h", limit=200, start_time=None, end_time=None, history_scope="runtime"):
        requested_symbol = self._normalize_market_data_symbol(symbol)
        normalized_symbol = self._resolve_preferred_market_symbol(requested_symbol) or requested_symbol
        if not normalized_symbol:
            return []
        if not self._is_plausible_market_symbol(normalized_symbol):
            self._log_invalid_market_symbol(normalized_symbol)
            return []

        if str(history_scope or "runtime").strip().lower() == "backtest":
            limit = self._resolve_backtest_history_limit(limit)
        else:
            limit = self._resolve_history_limit(limit)
        range_requested = start_time is not None or end_time is not None
        broker_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").strip().lower()
        if self.broker and not self._broker_supports_market_symbol(normalized_symbol):
            self._log_unsupported_market_symbol(broker_name, normalized_symbol)
            return []

        # Preferred native broker OHLCV.
        if self.broker and hasattr(self.broker, "fetch_ohlcv"):
            try:
                data = await self.broker.fetch_ohlcv(
                    normalized_symbol,
                    timeframe=timeframe,
                    limit=limit,
                    start_time=start_time,
                    end_time=end_time,
                )
                data = self._sanitize_ohlcv_rows(
                    normalized_symbol,
                    timeframe,
                    data,
                    requested_limit=limit,
                    source_label="broker",

                )
                if range_requested and data:
                    data = self._filter_ohlcv_rows_by_time_range(
                        data,
                        start_time=start_time,
                        end_time=end_time,
                    )
                if data:
                    await self._persist_candles_to_db(normalized_symbol, timeframe, data)
                    return data
            except TypeError:
                try:
                    data = await self.broker.fetch_ohlcv(normalized_symbol, timeframe=timeframe, limit=limit)
                    data = self._sanitize_ohlcv_rows(
                        normalized_symbol,
                        timeframe,
                        data,
                        requested_limit=limit,
                        source_label="broker",
                    )
                    if range_requested and data:
                        data = self._filter_ohlcv_rows_by_time_range(
                            data,
                            start_time=start_time,
                            end_time=end_time,
                        )
                    if data:
                        await self._persist_candles_to_db(normalized_symbol, timeframe, data)
                        return data
                except Exception:
                    pass
            except Exception:
                pass

        cached_data = await self._load_candles_from_db(
            normalized_symbol,
            timeframe=timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )
        cached_data = self._sanitize_ohlcv_rows(
            normalized_symbol,
            timeframe,
            cached_data,
            requested_limit=limit,
            source_label="cache",
        )
        if cached_data:
            return cached_data

        if range_requested:
            return []

        # Avoid fabricating historical candles from a single live tick. That creates
        # duplicate timestamps, misleading price action, and noisy sanitizer warnings.
        return []

    async def _safe_fetch_orderbook(self, symbol, limit=20):
        resolved_symbol = self._resolve_preferred_market_symbol(symbol) or self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        if self.broker and hasattr(self.broker, "fetch_orderbook"):
            try:
                book = await self.broker.fetch_orderbook(resolved_symbol, limit=limit)
                if isinstance(book, dict):
                    return book
            except Exception as exc:
                self.logger.debug("Orderbook fetch failed for %s: %s", symbol, exc)

        tick = await self._safe_fetch_ticker(resolved_symbol)
        if not isinstance(tick, dict):
            return {"bids": [], "asks": []}

        bid = float(tick.get("bid") or tick.get("price") or tick.get("last") or 0)
        ask = float(tick.get("ask") or tick.get("price") or tick.get("last") or 0)
        if bid <= 0 and ask <= 0:
            return {"bids": [], "asks": []}

        if bid <= 0:
            bid = ask * 0.999
        if ask <= 0:
            ask = bid * 1.001

        bids = [[bid * (1 - (i * 0.0005)), max(1.0, 100 - i)] for i in range(min(limit, 100))]
        asks = [[ask * (1 + (i * 0.0005)), max(1.0, 100 - i)] for i in range(min(limit, 100))]
        return {"bids": bids, "asks": asks}

    async def request_orderbook(self, symbol, limit=100):
        if not symbol:
            return

        now = time.monotonic()
        broker_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").lower()
        min_interval = 4.0 if broker_name in {"stellar", "solana"} else 1.0

        in_flight = self._orderbook_tasks.get(symbol)
        if in_flight and not in_flight.done():
            return

        cached = self.orderbook_buffer.get(symbol) or {}
        last_requested = self._orderbook_last_request_at.get(symbol, 0.0)
        if cached and (now - last_requested) < min_interval:
            bids = cached.get("bids") or []
            asks = cached.get("asks") or []
            self.orderbook_signal.emit(symbol, bids, asks)
            return

        self._orderbook_last_request_at[symbol] = now
        current_task = asyncio.current_task()
        if current_task is not None:
            self._orderbook_tasks[symbol] = current_task

        try:
            orderbook = await self._safe_fetch_orderbook(symbol, limit=limit)
            bids = orderbook.get("bids") if isinstance(orderbook, dict) else []
            asks = orderbook.get("asks") if isinstance(orderbook, dict) else []

            bids = bids or []
            asks = asks or []

            self.orderbook_buffer.update(symbol, bids, asks)
            self.orderbook_signal.emit(symbol, bids, asks)
        except Exception as exc:
            self.logger.debug("Orderbook request failed for %s: %s", symbol, exc)
            self.orderbook_buffer.update(symbol, [], [])
            self.orderbook_signal.emit(symbol, [], [])
        finally:
            active_task = self._orderbook_tasks.get(symbol)
            if active_task is current_task:
                self._orderbook_tasks.pop(symbol, None)

    async def request_recent_trades(self, symbol, limit=40):
        if not symbol:
            return

        now = time.monotonic()
        broker_name = str(getattr(getattr(self, "broker", None), "exchange_name", "") or "").lower()
        min_interval = 5.0 if broker_name in {"stellar", "solana"} else 1.5

        in_flight = self._recent_trades_tasks.get(symbol)
        if in_flight and not in_flight.done():
            return

        cached = list(self._recent_trades_cache.get(symbol) or [])
        last_requested = self._recent_trades_last_request_at.get(symbol, 0.0)
        if cached and (now - last_requested) < min_interval:
            self.recent_trades_signal.emit(symbol, cached[: max(1, int(limit or len(cached)))])
            return

        self._recent_trades_last_request_at[symbol] = now
        current_task = asyncio.current_task()
        if current_task is not None:
            self._recent_trades_tasks[symbol] = current_task

        try:
            trades = await self._safe_fetch_recent_trades(symbol, limit=limit)
            normalized = self._normalize_public_trade_rows(symbol, trades, limit=limit)
            self._recent_trades_cache[symbol] = normalized
            self.recent_trades_signal.emit(symbol, normalized)
        except Exception as exc:
            self.logger.debug("Recent trade request failed for %s: %s", symbol, exc)
            self._recent_trades_cache[symbol] = []
            self.recent_trades_signal.emit(symbol, [])
        finally:
            active_task = self._recent_trades_tasks.get(symbol)
            if active_task is current_task:
                self._recent_trades_tasks.pop(symbol, None)

    def publish_ai_signal(self, symbol, signal, candles=None):
        if not symbol or not isinstance(signal, dict):
            return
        if getattr(self, "_session_closing", False):
            return
        terminal = getattr(self, "terminal", None)
        if terminal is not None and getattr(terminal, "_ui_shutting_down", False):
            return

        side = str(signal.get("side", "hold")).upper()
        reasoning = dict(signal.get("reasoning") or {})
        decision = str(reasoning.get("decision") or signal.get("reasoning_decision") or "").strip().upper()
        monitor_signal = side
        if decision and decision not in {"APPROVE", "NEUTRAL"}:
            monitor_signal = decision
        confidence = float(reasoning.get("confidence", signal.get("confidence", 0.0)) or 0.0)

        closes = []
        for row in candles or []:
            if isinstance(row, (list, tuple)) and len(row) >= 5:
                try:
                    closes.append(float(row[4]))
                except Exception:
                    continue

        volatility = 0.0
        if len(closes) >= 2:
            returns = []
            for i in range(1, len(closes)):
                prev = closes[i - 1]
                cur = closes[i]
                if prev:
                    returns.append((cur - prev) / prev)
            if returns:
                mean_ret = sum(returns) / len(returns)
                variance = sum((r - mean_ret) ** 2 for r in returns) / max(len(returns) - 1, 1)
                volatility = variance ** 0.5

        regime = "RANGE"
        if side == "BUY":
            regime = "TREND_UP"
        elif side == "SELL":
            regime = "TREND_DOWN"

        reason_text = str(reasoning.get("reasoning") or signal.get("reason", "") or "").strip()
        warnings = [str(item).strip() for item in list(reasoning.get("warnings") or signal.get("warnings") or []) if str(item).strip()]
        if warnings:
            warning_text = "Warnings: " + " | ".join(warnings[:3])
            reason_text = f"{reason_text} {warning_text}".strip()

        raw_market_hours = signal.get("market_hours")
        if not isinstance(raw_market_hours, dict):
            raw_market_hours = dict(signal.get("metadata") or {}).get("market_hours")
        market_hours = dict(raw_market_hours or {}) if isinstance(raw_market_hours, dict) else {}
        if not market_hours:
            market_session = signal.get("market_session")
            high_liquidity = signal.get("high_liquidity_session")
            asset_type = signal.get("asset_type")
            market_open = signal.get("market_open")
            trade_allowed = signal.get("trade_allowed")
            if any(
                    value is not None and str(value).strip() != ""
                    for value in (market_session, high_liquidity, asset_type, market_open, trade_allowed)
            ):
                market_hours = {
                    "asset_type": str(asset_type or "").strip() or None,
                    "session": str(market_session or "").strip() or None,
                    "high_liquidity": high_liquidity if high_liquidity is not None else None,
                    "market_open": bool(market_open) if market_open is not None else None,
                    "trade_allowed": bool(trade_allowed) if trade_allowed is not None else None,
                }

        payload = {
            "symbol": symbol,
            "signal": monitor_signal,
            "confidence": confidence,
            "regime": regime,
            "volatility": round(float(volatility), 6),
            "reason": reason_text,
            "decision": decision or side,
            "risk": str(reasoning.get("risk") or signal.get("risk") or "").strip(),
            "warnings": warnings,
            "provider": str(reasoning.get("provider") or signal.get("reasoning_provider") or "").strip(),
            "mode": str(reasoning.get("mode") or signal.get("reasoning_mode") or "").strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": str(signal.get("session_id") or "").strip(),
            "session_label": str(signal.get("session_label") or "").strip(),
            "market_hours": market_hours,
            "market_session": str(market_hours.get("session") or signal.get("market_session") or "").strip(),
            "high_liquidity_session": market_hours.get("high_liquidity"),
        }

        self.ai_signal_monitor.emit(payload)

    def publish_strategy_debug(self, symbol, signal, candles=None, features=None):
        if not symbol or not isinstance(signal, dict):
            return
        if getattr(self, "_session_closing", False):
            return
        terminal = getattr(self, "terminal", None)
        if terminal is not None and getattr(terminal, "_ui_shutting_down", False):
            return

        feature_row = None
        if features is not None:
            try:
                if not features.empty:
                    feature_row = features.iloc[-1]
            except Exception:
                feature_row = None

        index_value = len(candles or []) - 1
        price_value = 0.0
        if candles:
            last_row = candles[-1]
            if isinstance(last_row, (list, tuple)) and len(last_row) >= 5:
                index_value = last_row[0]
                try:
                    price_value = float(last_row[4])
                except Exception:
                    price_value = 0.0

        payload = {
            "symbol": symbol,
            "index": index_value,
            "price": price_value,
            "signal": str(signal.get("side", "hold")).upper(),
            "rsi": round(float(feature_row["rsi"]), 4) if feature_row is not None and "rsi" in feature_row else 0.0,
            "ema_fast": round(float(feature_row["ema_fast"]), 6) if feature_row is not None and "ema_fast" in feature_row else 0.0,
            "ema_slow": round(float(feature_row["ema_slow"]), 6) if feature_row is not None and "ema_slow" in feature_row else 0.0,
            "ml_probability": round(float(signal.get("confidence", 0.0) or 0.0), 4),
            "reason": str(signal.get("reason", "")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": str(signal.get("session_id") or "").strip(),
            "session_label": str(signal.get("session_label") or "").strip(),
        }

        self.strategy_debug_signal.emit(payload)

    async def request_candle_data(self, symbol, timeframe="1h", limit=None, start_time=None, end_time=None, history_scope="runtime"):
        if not symbol:
            return

        requested_symbol = self._normalize_market_data_symbol(symbol) or str(symbol or "").strip().upper()
        resolved_symbol = self._resolve_preferred_market_symbol(requested_symbol) or requested_symbol
        if not self._is_plausible_market_symbol(resolved_symbol):
            self._log_invalid_market_symbol(resolved_symbol)
            return
        if str(history_scope or "runtime").strip().lower() == "backtest":
            limit = self._resolve_backtest_history_limit(limit)
        else:
            limit = self._resolve_history_limit(limit)
        fetcher = getattr(self, "_safe_fetch_ohlcv")
        fetch_kwargs = {
            "timeframe": timeframe,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "history_scope": history_scope,
        }
        try:
            signature = inspect.signature(fetcher)
        except (TypeError, ValueError):
            signature = None
        if signature is not None:
            accepts_var_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            if not accepts_var_kwargs:
                supported = {
                    name
                    for name, parameter in signature.parameters.items()
                    if parameter.kind in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    )
                }
                fetch_kwargs = {
                    name: value
                    for name, value in fetch_kwargs.items()
                    if name in supported
                }
        # Run blocking fetch on executor to prevent UI freezing
        loop = asyncio.get_running_loop()
        candles = await loop.run_in_executor(
            None,
            lambda: asyncio.run(fetcher(resolved_symbol, **fetch_kwargs))
        ) if asyncio.iscoroutinefunction(fetcher) else await loop.run_in_executor(
            None,
            lambda: fetcher(resolved_symbol, **fetch_kwargs)
        )
        candles = self._sanitize_ohlcv_rows(
            resolved_symbol,
            timeframe,
            candles,
            requested_limit=limit,
            source_label="runtime",
        )
        received_count = len(candles) if isinstance(candles, list) else 0
        if start_time is None and end_time is None:
            minimum_required_count = None
            if str(history_scope or "runtime").strip().lower() != "backtest":
                minimum_required_count = min(max(int(limit or 0), 0), 120)
            self._notify_market_data_shortfall(
                resolved_symbol,
                timeframe,
                received_count,
                limit,
                minimum_required_count=minimum_required_count,
            )
        if not candles:
            return

        df = pd.DataFrame(candles)
        if df.shape[1] >= 6:
            df = df.iloc[:, :6]
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]

        # Keep nested cache for symbol/timeframe lookups.
        cache_symbols = [resolved_symbol]
        if requested_symbol and requested_symbol != resolved_symbol:
            cache_symbols.append(requested_symbol)
        for cache_symbol in cache_symbols:
            symbol_cache = self.candle_buffers.setdefault(cache_symbol, {})
            symbol_cache[timeframe] = df

        # Keep legacy buffer path updated with latest close candle rows.
        for cache_symbol in cache_symbols:
            for _, row in df.tail(200).iterrows():
                self.candle_buffer.update(
                    cache_symbol,
                    {
                        "timestamp": row["timestamp"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    },
                )

        candle_signal = getattr(self, "candle_signal", None)
        if candle_signal is not None:
            try:
                candle_signal.emit(resolved_symbol, df)
            except RuntimeError:
                pass
        return df

    def _notify_market_data_shortfall(self, symbol, timeframe, received_count, requested_count, minimum_required_count=None):
        normalized_symbol = str(symbol or "").upper().strip()
        normalized_timeframe = str(timeframe or self.time_frame or "1h").strip() or "1h"
        try:
            requested = max(0, int(requested_count or 0))
        except Exception:
            requested = 0
        try:
            received = max(0, int(received_count or 0))
        except Exception:
            received = 0
        try:
            minimum_required = max(0, int(minimum_required_count or 0))
        except Exception:
            minimum_required = 0

        if not normalized_symbol or requested <= 0:
            return

        notice_cache = getattr(self, "_market_data_shortfall_notices", None)
        if not isinstance(notice_cache, dict):
            notice_cache = {}
            self._market_data_shortfall_notices = notice_cache
        cache_key = (normalized_symbol, normalized_timeframe)

        shortfall = max(0, requested - received)
        if received >= requested or shortfall <= 1:
            notice_cache.pop(cache_key, None)
            return
        if minimum_required > 0 and received >= min(requested, minimum_required):
            notice_cache.pop(cache_key, None)
            return

        if notice_cache.get(cache_key) == (received, requested):
            return
        notice_cache[cache_key] = (received, requested)

        if received <= 0:
            message = (
                f"Not enough data for {normalized_symbol} ({normalized_timeframe}): no candles were returned. "
                "Try another timeframe, load more history, or wait for more market data."
            )
        else:
            message = (
                f"Not enough data for {normalized_symbol} ({normalized_timeframe}): received {received} of "
                f"{requested} requested candles. Indicators, AI signals, and backtests may be limited."
            )

        if getattr(self, "logger", None) is not None:
            self.logger.warning(message)

        terminal = getattr(self, "terminal", None)
        system_console = getattr(terminal, "system_console", None) if terminal is not None else None
        if system_console is not None:
            system_console.log(message, "WARN")

    async def _warmup_visible_candles(self):
        # Preload a very small working set so startup stays responsive.
        warm_symbols = list(dict.fromkeys(self.symbols[:2]))
        tasks = [
            self.request_candle_data(symbol=s, timeframe=self.time_frame, limit=180)
            for s in warm_symbols
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _cleanup_session(self, stop_trading=True, close_broker=False, wait_for_background_workers=False):
        self._session_closing = True
        async def _await_cleanup_step(label, coro):
            try:
                return await coro
            except Exception:
                self.logger.exception("Cleanup step failed: %s", label)
                return None

        def _run_cleanup_step(label, func):
            try:
                return func()
            except Exception:
                self.logger.exception("Cleanup step failed: %s", label)
                return None

        try:
            stop_telegram_service = getattr(self, "_stop_telegram_service", None)
            if callable(stop_telegram_service):
                await _await_cleanup_step("stop telegram service", stop_telegram_service())

            sms_trade_notification_service = getattr(self, "sms_trade_notification_service", None)
            close_sms_trade_notification_service = (
                getattr(sms_trade_notification_service, "close", None)
                if sms_trade_notification_service is not None
                else None
            )
            if callable(close_sms_trade_notification_service):
                await _await_cleanup_step(
                    "close SMS trade notification service",
                    close_sms_trade_notification_service(),
                )

            news_service = getattr(self, "news_service", None)
            close_news_service = getattr(news_service, "close", None) if news_service is not None else None
            if callable(close_news_service):
                await _await_cleanup_step("close news service", close_news_service())

            news_cache = getattr(self, "_news_cache", None)
            if news_cache is not None and hasattr(news_cache, "clear"):
                _run_cleanup_step("clear news cache", news_cache.clear)

            news_inflight = getattr(self, "_news_inflight", None)
            if news_inflight is not None and hasattr(news_inflight, "clear"):
                _run_cleanup_step("clear in-flight news requests", news_inflight.clear)

            auto_assignment_task = getattr(self, "_strategy_auto_assignment_task", None)
            if auto_assignment_task is not None and not auto_assignment_task.done():
                _run_cleanup_step("cancel strategy auto-assignment task", auto_assignment_task.cancel)
            self._strategy_auto_assignment_task = None

            deferred_assignment_task = getattr(self, "_strategy_auto_assignment_deferred_task", None)
            if deferred_assignment_task is not None and not deferred_assignment_task.done():
                _run_cleanup_step("cancel deferred strategy auto-assignment task", deferred_assignment_task.cancel)
            self._strategy_auto_assignment_deferred_task = None

            _run_cleanup_step(
                "shutdown strategy ranking executor",
                lambda: self._shutdown_strategy_ranking_executor(wait=wait_for_background_workers),
            )

            terminal_restore_task = getattr(self, "_terminal_runtime_restore_task", None)
            if terminal_restore_task is not None and not terminal_restore_task.done():
                _run_cleanup_step("cancel terminal runtime restore task", terminal_restore_task.cancel)
            self._terminal_runtime_restore_task = None

            self.strategy_auto_assignment_in_progress = False
            self.strategy_auto_assignment_ready = not bool(getattr(self, "strategy_auto_assignment_enabled", True))
            _run_cleanup_step(
                "reset strategy auto-assignment progress",
                lambda: self._update_strategy_auto_assignment_progress(
                    completed=0,
                    total=0,
                    current_symbol="",
                    timeframe=str(getattr(self, "time_frame", "1h") or "1h"),
                    message="Waiting to scan symbols.",
                    failed_symbols=[],
                ),
            )

            ticker_task = getattr(self, "_ticker_task", None)
            if ticker_task is not None and not ticker_task.done():
                _run_cleanup_step("cancel ticker task", ticker_task.cancel)
            self._ticker_task = None
            recovery_task = getattr(self, "_market_stream_recovery_task", None)
            if recovery_task is not None and not recovery_task.done():
                _run_cleanup_step("cancel market stream recovery task", recovery_task.cancel)
            self._market_stream_recovery_task = None

            ws_task = getattr(self, "_ws_task", None)
            if ws_task is not None and not ws_task.done():
                _run_cleanup_step("cancel websocket task", ws_task.cancel)
            self._ws_task = None

            ws_bus_task = getattr(self, "_ws_bus_task", None)
            if ws_bus_task is not None and not ws_bus_task.done():
                _run_cleanup_step("cancel websocket bus task", ws_bus_task.cancel)
            self._ws_bus_task = None
            self.ws_bus = None
            self.ws_manager = None

            trading_system = getattr(self, "trading_system", None)
            if stop_trading and trading_system is not None:
                try:
                    await _await_cleanup_step(
                        "stop trading system",
                        trading_system.stop(wait_for_background_workers=wait_for_background_workers),
                    )
                except TypeError:
                    await _await_cleanup_step("stop trading system", trading_system.stop())
                self.trading_system = None
                self.behavior_guard = None
                self._live_agent_decision_events = {}
                self._live_agent_runtime_feed = []

            terminals = []
            primary_terminal = getattr(self, "terminal", None)
            if primary_terminal is not None:
                terminals.append(primary_terminal)
            for terminal in list(self._session_terminal_registry().values()):
                if terminal is not None and terminal not in terminals:
                    terminals.append(terminal)
            for terminal in terminals:
                _run_cleanup_step("mark terminal as shutting down", lambda target=terminal: setattr(target, "_ui_shutting_down", True))
                disconnect_signals = getattr(terminal, "_disconnect_controller_signals", None)
                if callable(disconnect_signals):
                    _run_cleanup_step("disconnect terminal controller signals", disconnect_signals)
                stack = getattr(self, "stack", None)
                if stack is not None and hasattr(stack, "removeWidget"):
                    _run_cleanup_step("remove terminal widget", lambda target=terminal: stack.removeWidget(target))
                delete_later = getattr(terminal, "deleteLater", None)
                if callable(delete_later):
                    _run_cleanup_step("schedule terminal deletion", delete_later)
            self.session_terminals = {}
            self.terminal = None

            broker = getattr(self, "broker", None)
            if close_broker and broker is not None:
                close_broker_coro = getattr(broker, "close", None)
                if callable(close_broker_coro):
                    await _await_cleanup_step("close broker", close_broker_coro())
                self.broker = None
        finally:
            # Stop cache trimming timer
            cache_trim_timer = getattr(self, "_cache_trim_timer", None)
            if cache_trim_timer is not None and hasattr(cache_trim_timer, "stop"):
                try:
                    cache_trim_timer.stop()
                except Exception:
                    self.logger.debug("Cache trim timer stop failed", exc_info=False)

            self._session_closing = False

    def get_market_stream_status(self):
        if self.is_hybrid_server_authoritative():
            runtime = self._hybrid_runtime_snapshot()
            market_data_health = dict(runtime.get("market_data_health") or {})
            status = str(market_data_health.get("stream_status") or "Authoritative Stream").strip()
            return status or "Authoritative Stream"
        ws_task = getattr(self, "_ws_task", None)
        if ws_task and not ws_task.done():
            return "Running"
        ticker_task = getattr(self, "_ticker_task", None)
        if ticker_task and not ticker_task.done():
            return "Polling"
        if self._schedule_polling_market_stream_recovery():
            return "Restarting"
        return "Stopped"

    def _schedule_polling_market_stream_recovery(self):
        exchange = self._active_exchange_code()
        if exchange not in {"oanda", "stellar", "solana"}:
            return False
        if not bool(getattr(self, "connected", False)) or getattr(self, "broker", None) is None:
            return False
        ticker_task = getattr(self, "_ticker_task", None)
        if ticker_task is not None and not ticker_task.done():
            return False

        recovery_task = getattr(self, "_market_stream_recovery_task", None)
        if recovery_task is not None and not recovery_task.done():
            return True

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return False

        self.logger.warning(
            "Polling market data task is not active for %s; scheduling recovery.",
            exchange.upper(),
        )
        self._market_stream_recovery_task = self._create_task(
            self._start_ticker_polling(),
            "ticker_poll_recovery",
        )
        return True

    async def logout(self):
        try:
            await self._cleanup_session(stop_trading=True, close_broker=True)
            if getattr(self, "session_manager", None) is not None:
                await self.session_manager.close_all()
            await self._teardown_hybrid_session(clear_status=True)

            self.connected = False
            self.active_session_id = None
            self.connection_signal.emit("disconnected")

        finally:
            self.stack.setCurrentWidget(self.dashboard)
            self.dashboard.setEnabled(True)
            self.dashboard.connect_button.setText("CONNECT")

    async def shutdown_for_exit(self):
        trading_system = getattr(self, "trading_system", None)
        try:
            await self._cleanup_session(
                stop_trading=True,
                close_broker=True,
                wait_for_background_workers=True,
            )
            if getattr(self, "session_manager", None) is not None:
                await self.session_manager.close_all()
            await self._teardown_hybrid_session(clear_status=False)
        except Exception:
            self.logger.exception("Exit cleanup failed")
        finally:
            self.connected = False
            try:
                self.connection_signal.emit("disconnected")
            except Exception:
                pass
            self._shutdown_strategy_ranking_executor(wait=True)
            if trading_system is not None:
                shutdown_signal_executor = getattr(trading_system, "_shutdown_signal_selection_executor", None)
                if callable(shutdown_signal_executor):
                    try:
                        shutdown_signal_executor(wait=True)
                    except Exception:
                        self.logger.debug("Signal selection executor shutdown failed during exit", exc_info=True)

    async def get_price(self, symbol):
        tick = await self._safe_fetch_ticker(symbol)
        if not tick:
            raise RuntimeError("Price unavailable")
        return float(tick.get("price") or tick.get("last") or 0)


    async def shutdown(self):
        await self.event_bus.shutdown()