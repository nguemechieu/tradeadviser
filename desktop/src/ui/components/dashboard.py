import re
from pathlib import Path
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from broker.coinbase_credentials import coinbase_validation_error, normalize_coinbase_credentials
from config.config import AppConfig, BrokerConfig, RiskConfig, SystemConfig
from config.credential_manager import CredentialManager
from broker.market_venues import MARKET_VENUE_CHOICES, supported_market_venues_for_profile
from ui.components.i18n import apply_runtime_translations, iter_supported_languages
from ui.components.loading_overlay import LoadingOverlay

# Import new broker classification system
from broker import (
    AssetClass,
    MarketType,
    BrokerProfile,
    BROKER_PROFILES,
    get_broker_profile,
    select_brokers,
    BrokerSelector,
    BrokerValidator,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT_DIR / "assets"

LOGO_PATH = ASSETS_DIR / "logo.png"
SPINNER_PATH = ASSETS_DIR / "spinner.gif"

# Asset class options matching new broker classification system
ASSET_CLASS_OPTIONS = [
    ("Forex", "forex"),
    ("Crypto", "crypto"),
    ("Stocks", "stocks"),  # User-facing label per requirements
    ("Options", "options"),
    ("Futures", "futures"),
    ("Paper Trading", "paper"),
]

# Map old broker type names to new asset classes for backward compatibility
ASSET_CLASS_MAP = {
    "crypto": AssetClass.CRYPTO,
    "forex": AssetClass.FOREX,
    "stocks": AssetClass.STOCK,  # "Stocks" UI â†’ STOCK enum
    "equity": AssetClass.EQUITY,
    "options": AssetClass.OPTIONS,
    "futures": AssetClass.FUTURES,
    "derivatives": AssetClass.FUTURES,  # Treat derivatives as futures
    "paper": None,
}

# Brokers by asset class (generated from BROKER_PROFILES)
def _get_brokers_by_asset_class():
    """Generate exchange options by asset class from broker profiles."""
    by_class = {}
    for asset_class in [AssetClass.FOREX, AssetClass.CRYPTO, AssetClass.STOCK, AssetClass.OPTIONS, AssetClass.FUTURES]:
        profiles = select_brokers(asset_class=asset_class)
        by_class[asset_class.value.lower()] = [p.broker_id for p in profiles]
    return by_class

EXCHANGE_MAP_NEW = _get_brokers_by_asset_class()

# Fallback exchange map for backward compatibility
EXCHANGE_MAP = {
    "crypto": EXCHANGE_MAP_NEW.get("crypto", ["coinbase", "binance", "bybit"]),
    "forex": EXCHANGE_MAP_NEW.get("forex", ["oanda_us"]),
    "stocks": EXCHANGE_MAP_NEW.get("stocks", ["alpaca", "schwab", "ibkr"]),
    "options": EXCHANGE_MAP_NEW.get("options", ["schwab", "ibkr"]),
    "futures": EXCHANGE_MAP_NEW.get("futures", ["ibkr"]),
    "derivatives": EXCHANGE_MAP_NEW.get("futures", ["ibkr"]),
    "paper": ["paper"],
}

# Old crypto exchange map (kept for backward compatibility with Solana/Stellar special handling)
CRYPTO_EXCHANGE_MAP = {
    "us": [
        "binanceus",
        "coinbase",
        "solana",
        "stellar",
        "kraken",
        "kucoin",
        "bybit",
        "okx",
        "gateio",
        "bitget",
    ],
    "global": [
        "binance",
        "coinbase",
        "solana",
        "stellar",
        "kraken",
        "kucoin",
        "bybit",
        "okx",
        "gateio",
        "bitget",
    ],
}

DERIVATIVE_EXCHANGE_MAP = {
    "options": ["schwab"],
    "futures": ["ibkr", "amp", "tradovate"],
    "derivatives": ["ibkr", "schwab", "amp", "tradovate"],
}

# Old options (kept for backward compatibility with UI)
BROKER_TYPE_OPTIONS = [
    "crypto",
    "forex",
    "stocks",
    "options",
    "futures",
    "derivatives",
    "paper",
]

CUSTOMER_REGION_OPTIONS = [
    ("US", "us"),
    ("Outside US", "global"),
]

IBKR_CONNECTION_MODE_OPTIONS = [
    ("Web API", "webapi"),
    ("TWS / IB Gateway", "tws"),
]

IBKR_WEBAPI_ENVIRONMENT_OPTIONS = [
    ("Client Portal Gateway", "gateway"),
    ("Hosted Web API", "hosted"),
]

SCHWAB_ENVIRONMENT_OPTIONS = [
    ("Sandbox", "sandbox"),
    ("Production", "production"),
]

# Market type options generated from new broker classification system
def _get_market_type_choices():
    """Generate market type choices from broker classification system."""
    choices = [("Auto", "auto")]
    
    # Group market types by category for better UI organization
    market_types_by_category = {
        "Forex": [
            (MarketType.MARGIN_FX, "Leveraged FX (OANDA, IBKR)"),
            (MarketType.SPOT_FX, "Spot FX"),
            (MarketType.FX_CFD, "FX CFD"),
        ],
        "Crypto": [
            (MarketType.SPOT_CRYPTO, "Spot Crypto"),
            (MarketType.CRYPTO_PERPETUAL, "Crypto Perpetuals"),
            (MarketType.CRYPTO_MARGIN, "Crypto Margin"),
        ],
        "Equities": [
            (MarketType.CASH_STOCK, "Cash Stocks"),
            (MarketType.STOCK_MARGIN, "Stock Margin"),
            (MarketType.SHORT_STOCK, "Short Stocks"),
            (MarketType.STOCK_OPTION, "Stock Options"),
        ],
        "Derivatives": [
            (MarketType.LISTED_FUTURE, "Listed Futures"),
            (MarketType.LISTED_OPTION, "Listed Options"),
            (MarketType.STOCK_CFD, "Stock CFD"),
            (MarketType.EQUITY_CFD, "Equity CFD"),
        ],
    }
    
    for category, types in market_types_by_category.items():
        for market_type, label in types:
            choices.append((f"{category}: {label}", market_type.value.lower()))
    
    return choices

MARKET_TYPE_CHOICES_NEW = _get_market_type_choices()


BROKER_COPY = {
    "crypto": "Multi-venue crypto routing with support for spot, futures, and leverage trading.",
    "forex": "Leveraged FX trading and OTC forex market access with risk management.",
    "stocks": "Equities trading with support for cash, margin, options, and fractional shares.",
    "options": "Contract-aware options sessions with Greeks-aware execution workflows.",
    "futures": "Futures routing built for margin-aware workflows, rollover context, and contract metadata.",
    "derivatives": "A broader derivatives setup that keeps option and futures-capable broker paths visible in one place.",
    "paper": "A zero-risk rehearsal mode that still feels like the real desk experience.",
}

EXCHANGE_CREDENTIAL_SCHEMAS = {
    "default": {
        "api_label": "API Key",
        "api_placeholder": "Public key or broker token",
        "secret_label": "Secret",
        "secret_placeholder": "Secret key",
        "secret_echo": QLineEdit.Password,
        "password_label": "Passphrase",
        "password_placeholder": "Exchange passphrase when required",
        "password_echo": QLineEdit.Password,
        "account_label": "Account ID",
        "account_placeholder": "Optional account identifier",
        "show_password": False,
        "show_account": False,
        "required_fields": ("api", "secret"),
        "field_targets": {
            "api": "api_key",
            "secret": "secret",
            "password": "password",
            "account": "account_id",
        },
        "field_fallbacks": {
            "password": ("passphrase",),
        },
    },
    "stellar": {
        "api_label": "Public Key",
        "api_placeholder": "Stellar public key",
        "secret_label": "Private Key",
        "secret_placeholder": "Stellar private key",
        "required_fields": ("api",),
    },
    "solana": {
        "api_label": "Wallet or OKX API Key",
        "api_placeholder": "Solana wallet address or OKX Trade API key",
        "secret_label": "Private Key or OKX Secret",
        "secret_placeholder": "Solana private key or OKX API secret",
        "password_label": "Passphrase / Jupiter Key",
        "password_placeholder": "OKX passphrase or legacy Jupiter API key",
        "password_echo": QLineEdit.Password,
        "account_label": "Project ID or RPC URL",
        "account_placeholder": "Optional OKX project id or custom Solana RPC URL",
        "show_password": True,
        "show_account": True,
        "required_fields": (),
        "field_targets": {
            "api": "api_key",
            "secret": "secret",
            "password": "password",
            "account": "account_id",
        },
        "field_fallbacks": {
            "password": ("passphrase", "options.okx_passphrase", "options.jupiter_api_key"),
            "account": ("options.okx_project_id", "options.rpc_url"),
        },
    },
    "coinbase": {
        "api_label": "Key Name or ID",
        "api_placeholder": "organizations/.../apiKeys/... or key id",
        "secret_label": "Private Key",
        "secret_placeholder": "Private key PEM or full Coinbase key JSON",
    },
    "oanda": {
        "api_label": "Account ID",
        "api_placeholder": "Oanda account ID",
        "secret_label": "API Key",
        "secret_placeholder": "Oanda API key",
        "secret_echo": QLineEdit.Normal,
        "required_fields": ("api", "secret"),
        "field_targets": {
            "api": "account_id",
            "secret": "api_key",
        },
    },
    "schwab": {
        "api_label": "App Key / Client ID",
        "api_placeholder": "Schwab app key / client id",
        "secret_label": "Client Secret",
        "secret_placeholder": "Optional Schwab client secret",
        "password_label": "Redirect URI",
        "password_placeholder": "http://127.0.0.1:8000/api/callback",
        "password_echo": QLineEdit.Normal,
        "account_label": "Account Hash / Profile",
        "account_placeholder": "Optional Schwab account hash or profile label",
        "show_password": True,
        "show_account": True,
        "required_fields": ("api", "password"),
        "field_targets": {
            "api": "api_key",
            "secret": "secret",
            "password": "password",
            "account": "options.account_hash",
        },
        "field_fallbacks": {
            "password": ("options.redirect_uri",),
            "account": ("account_id",),
        },
    },
    "amp": {
        "api_label": "Username",
        "api_placeholder": "AMP username",
        "secret_label": "Password",
        "secret_placeholder": "AMP password",
        "password_label": "API Key",
        "password_placeholder": "Optional AMP API key",
        "password_echo": QLineEdit.Normal,
        "account_label": "API Secret",
        "account_placeholder": "Optional AMP API secret",
        "show_password": True,
        "show_account": True,
        "required_fields": ("api", "secret"),
        "field_targets": {
            "api": "options.username",
            "secret": "password",
            "password": "api_key",
            "account": "secret",
        },
        "field_fallbacks": {
            "api": ("api_key",),
            "secret": ("password", "secret"),
            "password": ("api_key",),
            "account": ("secret", "account_id"),
        },
    },
    "tradovate": {
        "api_label": "Username",
        "api_placeholder": "Tradovate username",
        "secret_label": "Password",
        "secret_placeholder": "Tradovate password",
        "password_label": "Company ID",
        "password_placeholder": "Optional Tradovate company id",
        "password_echo": QLineEdit.Normal,
        "account_label": "Security Code",
        "account_placeholder": "Optional Tradovate security code",
        "show_password": True,
        "show_account": True,
        "required_fields": ("api", "secret"),
        "field_targets": {
            "api": "options.username",
            "secret": "password",
            "password": "api_key",
            "account": "secret",
        },
        "field_fallbacks": {
            "api": ("api_key",),
            "secret": ("password", "secret"),
            "password": ("api_key",),
            "account": ("secret", "account_id"),
        },
    },
    "ibkr": {
        "api_label": "Base URL",
        "api_placeholder": "https://127.0.0.1:8000/api/ibkr",
        "secret_label": "Session Token",
        "secret_placeholder": "Optional IBKR Web API session token",
        "password_label": "WebSocket URL",
        "password_placeholder": "Optional websocket override",
        "password_echo": QLineEdit.Normal,
        "account_label": "Account ID / Profile",
        "account_placeholder": "Optional IBKR account id override",
        "show_password": True,
        "show_account": True,
        "required_fields": (),
        "field_targets": {
            "api": "options.base_url",
            "secret": "api_key",
            "password": "options.websocket_url",
            "account": "account_id",
        },
    },
}


# ============================================================================
# Helper Functions - Bridge old system with new broker classification system
# ============================================================================

def _get_broker_profile_for_selection(exchange_type, exchange):
    """Get broker profile from legacy exchange type/exchange names."""
    try:
        # Map old exchange names to broker IDs
        broker_id_map = {
            # Forex
            ("forex", "oanda"): "oanda_us",
            # Crypto
            ("crypto", "coinbase"): "coinbase",
            ("crypto", "binance"): "binance_futures",
            ("crypto", "bybit"): "bybit_futures",
            # Stocks
            ("stocks", "alpaca"): "alpaca",
            # Options & Futures
            ("options", "schwab"): "schwab",
            ("futures", "ibkr"): "ibkr",
            ("derivatives", "ibkr"): "ibkr",
            # Paper
            ("paper", "paper"): "paper",
        }
        
        broker_id = broker_id_map.get((exchange_type, exchange))
        if broker_id:
            return get_broker_profile(broker_id)
        
        # Try direct lookup
        return get_broker_profile(exchange)
    except Exception:
        return None


def _get_supported_market_types_for_broker(broker_id):
    """Get supported market types for a broker profile."""
    try:
        profile = get_broker_profile(broker_id)
        if profile:
            return profile.market_types
    except Exception:
        pass
    return []


def _validate_broker_market_type(exchange_type, exchange, market_type):
    """Validate that a market type is supported by a broker."""
    try:
        profile = _get_broker_profile_for_selection(exchange_type, exchange)
        if not profile:
            return True  # Allow if profile not found (backward compat)
        
        if market_type == "auto":
            return True  # Auto is always valid
        
        # Convert string market type to enum
        for market in profile.market_types:
            if market.value.lower() == str(market_type).lower():
                return True
        return False
    except Exception:
        return True  # Allow if validation fails


"""The dashboard is the launchpad for trading sessions, where customers configure broker access and review session readiness before"""
class Dashboard(QWidget):
    login_requested = Signal(object)
    LAST_PROFILE_SETTING = "dashboard/last_profile"

    def __init__(self, controller):
        super().__init__()

        self.controller = controller
        self._field_blocks = {}
        self._current_layout_mode = None
        self._ibkr_last_connection_mode = None
        self._ibkr_mode_field_memory = {"webapi": {}, "tws": {}}
        self._platform_sync_status_tone = "idle"
        self.settings = getattr(controller, "settings", None) or QSettings("TradeAdviser", "TradingPlatform")

        self.setWindowTitle("TradeAdviser")
        self.resize(1320, 880)

        self._apply_styles()
        self._build_ui()
        self._connect_signals()
        self.apply_platform_sync_profile(self._platform_sync_profile())
        self.loading_overlay = LoadingOverlay(self, title="Preparing trading session...")
        if hasattr(self.controller, "language_changed"):
            self.controller.language_changed.connect(lambda _code: self.apply_language())

        self._update_exchange_list(self.exchange_type_box.currentText())
        self._load_accounts_index()
        self._load_last_account()
        self._update_optional_fields()
        self._update_broker_hint()
        self._update_session_preview()
        self.refresh_active_sessions()
        self.apply_language()
        self._sync_shell_layout()

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #0b1220;
                color: #d7dfeb;
                font-family: "Segoe UI", "Aptos", sans-serif;
            }
            QScrollArea {
                border: 0;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #0f1726;
                width: 10px;
                margin: 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #24324a;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QFrame#heroPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #101827, stop:0.6 #0f1726, stop:1 #0b1220);
                border: 1px solid #24324a;
                border-radius: 28px;
            }
            QFrame#connectPanel {
                background: #101827;
                color: #d7dfeb;
                border: 1px solid #24324a;
                border-radius: 28px;
            }
            QFrame#glassCard {
                background-color: #101b2d;
                border: 1px solid #24344f;
                border-radius: 20px;
            }
            QFrame#marketStrip {
                background: #0f1727;
                border: 1px solid #24344f;
                border-radius: 18px;
            }
            QFrame#summaryCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #101b2d, stop:1 #0f1727);
                border: 1px solid #24344f;
                border-radius: 22px;
            }
            QFrame#statPill {
                background: #0f1726;
                border: 1px solid #24324a;
                border-radius: 16px;
            }
            QLabel#eyebrow {
                color: #8fa3bf;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.18em;
                text-transform: uppercase;
            }
            QLabel#heroTitle {
                font-size: 34px;
                font-weight: 800;
                color: #f4f8ff;
            }
            QLabel#heroLead {
                font-size: 14px;
                line-height: 1.5;
                color: #9fb0c7;
            }
            QLabel#heroSectionTitle {
                color: #e6edf7;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#heroSectionBody {
                color: #9fb0c7;
                font-size: 13px;
            }
            QLabel#panelTitle {
                color: #f4f8ff;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#panelBody {
                color: #9fb0c7;
                font-size: 14px;
            }
            QLabel#sectionLabel {
                color: #8fa3bf;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
            }
            QLabel#fieldLabel {
                color: #9fb0c7;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.05em;
                text-transform: uppercase;
            }
            QLabel#hintLabel {
                color: #8fa3bf;
                font-size: 12px;
            }
            QLabel#pillLabel {
                color: #8fa3bf;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#pillValue {
                color: #f4f8ff;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#summaryTitle {
                color: #f4f8ff;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#summaryBody {
                color: #9fb0c7;
                font-size: 13px;
            }
            QLabel#summaryMeta {
                color: #65a3ff;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#marketTitle {
                color: #dfe8f5;
                font-size: 15px;
                font-weight: 800;
            }
            QLabel#marketBody {
                color: #9fb0c7;
                font-size: 12px;
            }
            QLabel#checkTitle {
                color: #d7dfeb;
                font-size: 13px;
            }
            QLabel#checkStateGood {
                color: #34c27a;
                font-size: 12px;
                font-weight: 800;
            }
            QLabel#checkStateWarn {
                color: #f0a35e;
                font-size: 12px;
                font-weight: 800;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 12px;
                padding: 11px 12px;
                min-height: 22px;
                font-size: 14px;
                selection-background-color: #2a7fff;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
                border-color: #4f638d;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #65a3ff;
            }
            QComboBox::drop-down {
                border: 0;
                width: 26px;
            }
            QComboBox QAbstractItemView {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                selection-background-color: #2a7fff;
            }
            QCheckBox {
                color: #c7d2e0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid #2d3a56;
                background: #162033;
            }
            QCheckBox::indicator:checked {
                background: #2a7fff;
                border: 1px solid #65a3ff;
            }
            QPushButton#presetButton,
            QPushButton#secondaryButton {
                background-color: #162033;
                color: #d7dfeb;
                border: 1px solid #2d3a56;
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton#presetButton:hover,
            QPushButton#secondaryButton:hover {
                background: #1b2940;
                border-color: #4f638d;
            }
            QPushButton#connectButton {
                background: #2a7fff;
                color: white;
                border: 0;
                border-radius: 16px;
                padding: 15px 20px;
                font-size: 15px;
                font-weight: 800;
            }
            QPushButton#connectButton:hover {
                background: #3d8dff;
            }
            QPushButton#connectButton:pressed {
                background: #1f68d6;
            }
            """
        )

    def _tr(self, key, **kwargs):
        """Translate a key using controller translation support.

        Falls back to returning the key directly when no translation method exists.
        """
        if hasattr(self.controller, "tr"):
            return self.controller.tr(key, **kwargs)
        return key

    def _language_box_current_code(self):
        """Return currently selected language code from language dropdown."""
        if not hasattr(self, "language_box") or self.language_box is None:
            return None
        return self.language_box.currentData()

    def _selected_customer_region(self):
        """Return selected customer region for crypto routing."""
        if not hasattr(self, "customer_region_box") or self.customer_region_box is None:
            return "us"
        return str(self.customer_region_box.currentData() or "us").strip().lower()

    def _normalize_ibkr_connection_mode(self, value):
        normalized = str(value or "webapi").strip().lower() or "webapi"
        return normalized if normalized in {"webapi", "tws"} else "webapi"

    def _selected_ibkr_connection_mode(self):
        if not hasattr(self, "ibkr_connection_mode_box") or self.ibkr_connection_mode_box is None:
            return "webapi"
        return self._normalize_ibkr_connection_mode(self.ibkr_connection_mode_box.currentData())

    def _selected_ibkr_environment(self):
        if not hasattr(self, "ibkr_environment_box") or self.ibkr_environment_box is None:
            return "gateway"
        return str(self.ibkr_environment_box.currentData() or "gateway").strip().lower() or "gateway"

    def _selected_schwab_environment(self):
        if not hasattr(self, "schwab_environment_box") or self.schwab_environment_box is None:
            return "sandbox"
        return str(self.schwab_environment_box.currentData() or "sandbox").strip().lower() or "sandbox"

    def _platform_sync_profile(self):
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "platform_sync_profile"):
            try:
                payload = dict(controller.platform_sync_profile() or {})
                if payload:
                    return payload
            except Exception:
                pass
        return {
            "base_url": "http://127.0.0.1:8000",
            "email": "",
            "password": "",
            "sync_enabled": False,
            "remember_me": True,
            "last_sync_status": "idle",
            "last_sync_message": "Ready to sync this desktop with TradeAdviser server.",
        }

    def apply_platform_sync_profile(self, profile):
        payload = dict(profile or {})
        if hasattr(self, "server_url_input"):
            self.server_url_input.setText(
                str(payload.get("base_url") or "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000"
            )
        if hasattr(self, "server_email_input"):
            self.server_email_input.setText(str(payload.get("email") or "").strip())
        if hasattr(self, "server_password_input"):
            self.server_password_input.setText(str(payload.get("password") or "").strip())
        if hasattr(self, "sync_workspace_checkbox"):
            self.sync_workspace_checkbox.setChecked(bool(payload.get("sync_enabled")))

        message = str(payload.get("last_sync_message") or "Ready to sync this desktop with TradeAdviser server.").strip()
        tone = str(payload.get("last_sync_status") or "idle").strip().lower() or "idle"
        self.set_platform_sync_status(message, tone=tone)

    def set_platform_sync_status(self, message, *, tone="info"):
        text = str(message or "Ready to sync this desktop with TradeAdviser server.").strip()
        normalized_tone = str(tone or "info").strip().lower() or "info"
        palette = {
            "busy": "#8ec5ff",
            "success": "#6ee7b7",
            "error": "#fca5a5",
            "idle": "#94a3b8",
            "info": "#94a3b8",
        }
        self._platform_sync_status_tone = normalized_tone
        if hasattr(self, "platform_sync_status_label"):
            self.platform_sync_status_label.setText(text)
            self.platform_sync_status_label.setStyleSheet(f"color: {palette.get(normalized_tone, '#94a3b8')};")

    def _current_platform_sync_profile(self):
        merged = dict(self._platform_sync_profile() or {})
        merged.update(
            {
                "base_url": str(getattr(self, "server_url_input", None).text() if hasattr(self, "server_url_input") else "").strip(),
                "email": str(getattr(self, "server_email_input", None).text() if hasattr(self, "server_email_input") else "").strip().lower(),
                "password": str(getattr(self, "server_password_input", None).text() if hasattr(self, "server_password_input") else "").strip(),
                "sync_enabled": bool(
                    getattr(self, "sync_workspace_checkbox", None).isChecked()
                    if hasattr(self, "sync_workspace_checkbox")
                    else False
                ),
            }
        )
        return merged

    def _persist_platform_sync_profile(self):
        profile = self._current_platform_sync_profile()
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "save_platform_sync_profile"):
            try:
                profile = dict(controller.save_platform_sync_profile(profile) or profile)
            except Exception:
                raise
        return profile

    def _selected_profile_name(self):
        current_text = str(self.saved_account_box.currentText() or "").strip()
        if not current_text or self.saved_account_box.currentData() == "__recent__":
            return ""
        return current_text

    def _workspace_settings_payload(self):
        resolved = self._resolved_broker_inputs()
        broker_options = dict(resolved.get("options") or {})
        solana_values = self._solana_field_values()
        exchange = str(self.exchange_box.currentText() or "paper").strip().lower() or "paper"
        broker_type = str(self.exchange_type_box.currentText() or "paper").strip().lower() or "paper"
        mode = str(self.mode_box.currentText() or "paper").strip().lower() or "paper"
        if broker_type == "paper" or exchange == "paper":
            broker_type = "paper"
            exchange = "paper"
            mode = "paper"

        return {
            "language": str(
                self._language_box_current_code()
                or getattr(self.controller, "language_code", "en")
                or "en"
            ).strip()
            or "en",
            "broker_type": broker_type,
            "exchange": exchange,
            "customer_region": self._selected_customer_region(),
            "mode": mode,
            "market_type": str(self.market_type_box.currentData() or "auto").strip().lower() or "auto",
            "ibkr_connection_mode": self._selected_ibkr_connection_mode(),
            "ibkr_environment": self._selected_ibkr_environment(),
            "ibkr_base_url": str(broker_options.get("base_url") or "").strip(),
            "ibkr_websocket_url": str(broker_options.get("websocket_url") or "").strip(),
            "ibkr_host": str(broker_options.get("host") or "").strip(),
            "ibkr_port": str(broker_options.get("port") or "").strip(),
            "ibkr_client_id": str(broker_options.get("client_id") or "").strip(),
            "schwab_environment": self._selected_schwab_environment(),
            "api_key": str(resolved.get("api_key") or "").strip(),
            "secret": str(resolved.get("secret") or "").strip(),
            "password": str(resolved.get("password") or "").strip(),
            "account_id": str(resolved.get("account_id") or "").strip(),
            "risk_percent": int(self.risk_input.value()),
            "remember_profile": bool(self.remember_checkbox.isChecked()),
            "profile_name": self._selected_profile_name(),
            "desktop_sync_enabled": bool(
                self.sync_workspace_checkbox.isChecked() if hasattr(self, "sync_workspace_checkbox") else False
            ),
            "solana": {
                "wallet_address": str(solana_values.get("wallet_address") or "").strip(),
                "private_key": str(solana_values.get("private_key") or "").strip(),
                "rpc_url": str(solana_values.get("rpc_url") or "").strip(),
                "jupiter_api_key": str(solana_values.get("jupiter_api_key") or "").strip(),
                "okx_api_key": str(solana_values.get("okx_api_key") or "").strip(),
                "okx_secret": str(solana_values.get("okx_secret_key") or "").strip(),
                "okx_passphrase": str(solana_values.get("okx_passphrase") or "").strip(),
                "okx_project_id": str(solana_values.get("okx_project_id") or "").strip(),
            },
        }

    def apply_workspace_settings(self, payload):
        settings = dict(payload or {})
        language_code = str(settings.get("language") or "en").strip() or "en"
        language_index = self.language_box.findData(language_code)
        if language_index >= 0:
            self.language_box.setCurrentIndex(language_index)

        broker_type = str(settings.get("broker_type") or "paper").strip().lower() or "paper"
        if broker_type not in BROKER_TYPE_OPTIONS:
            broker_type = "paper"
        self.exchange_type_box.setCurrentText(broker_type)

        customer_region = str(settings.get("customer_region") or "us").strip().lower() or "us"
        customer_region_index = self.customer_region_box.findData(customer_region)
        self.customer_region_box.setCurrentIndex(customer_region_index if customer_region_index >= 0 else 0)

        self._update_exchange_list(broker_type)
        exchange = str(settings.get("exchange") or "paper").strip().lower() or "paper"
        if self.exchange_box.findText(exchange) >= 0:
            self.exchange_box.setCurrentText(exchange)

        ibkr_mode_index = self.ibkr_connection_mode_box.findData(
            self._normalize_ibkr_connection_mode(settings.get("ibkr_connection_mode"))
        )
        self.ibkr_connection_mode_box.setCurrentIndex(ibkr_mode_index if ibkr_mode_index >= 0 else 0)
        ibkr_environment_index = self.ibkr_environment_box.findData(
            str(settings.get("ibkr_environment") or "gateway").strip().lower() or "gateway"
        )
        self.ibkr_environment_box.setCurrentIndex(ibkr_environment_index if ibkr_environment_index >= 0 else 0)
        schwab_environment_index = self.schwab_environment_box.findData(
            str(settings.get("schwab_environment") or "sandbox").strip().lower() or "sandbox"
        )
        self.schwab_environment_box.setCurrentIndex(schwab_environment_index if schwab_environment_index >= 0 else 0)

        broker = {
            "type": broker_type,
            "exchange": exchange,
            "customer_region": customer_region,
            "mode": str(settings.get("mode") or "paper").strip().lower() or "paper",
            "api_key": str(settings.get("api_key") or "").strip(),
            "secret": str(settings.get("secret") or "").strip(),
            "password": str(settings.get("password") or "").strip(),
            "account_id": str(settings.get("account_id") or "").strip(),
            "options": {
                "market_type": str(settings.get("market_type") or "auto").strip().lower() or "auto",
                "customer_region": customer_region,
            },
        }
        if exchange == "ibkr":
            broker["options"].update(
                {
                    "connection_mode": str(settings.get("ibkr_connection_mode") or "webapi").strip().lower() or "webapi",
                    "environment": str(settings.get("ibkr_environment") or "gateway").strip().lower() or "gateway",
                    "base_url": str(settings.get("ibkr_base_url") or "").strip(),
                    "websocket_url": str(settings.get("ibkr_websocket_url") or "").strip(),
                    "host": str(settings.get("ibkr_host") or "").strip(),
                    "port": str(settings.get("ibkr_port") or "").strip(),
                    "client_id": str(settings.get("ibkr_client_id") or "").strip(),
                }
            )
        elif exchange == "schwab":
            broker["options"].update(
                {
                    "environment": str(settings.get("schwab_environment") or "sandbox").strip().lower() or "sandbox",
                    "redirect_uri": str(settings.get("password") or "").strip(),
                    "account_hash": str(settings.get("account_id") or "").strip(),
                }
            )
        elif exchange == "solana":
            solana = dict(settings.get("solana") or {})
            broker["options"].update(
                {
                    "wallet_address": str(solana.get("wallet_address") or "").strip(),
                    "private_key": str(solana.get("private_key") or "").strip(),
                    "rpc_url": str(solana.get("rpc_url") or "").strip(),
                    "jupiter_api_key": str(solana.get("jupiter_api_key") or "").strip(),
                    "okx_api_key": str(solana.get("okx_api_key") or "").strip(),
                    "okx_secret_key": str(solana.get("okx_secret") or "").strip(),
                    "okx_passphrase": str(solana.get("okx_passphrase") or "").strip(),
                    "okx_project_id": str(solana.get("okx_project_id") or "").strip(),
                }
            )

        self._update_optional_fields()
        self._populate_credential_fields(broker)
        self._refresh_market_type_options()
        self.mode_box.setCurrentText(str(settings.get("mode") or "paper").strip().lower() or "paper")
        market_type_index = self.market_type_box.findData(
            str(settings.get("market_type") or "auto").strip().lower() or "auto"
        )
        self.market_type_box.setCurrentIndex(market_type_index if market_type_index >= 0 else 0)
        self.risk_input.setValue(int(settings.get("risk_percent") or 2))
        self.remember_checkbox.setChecked(bool(settings.get("remember_profile", True)))

        self._update_optional_fields()
        self._update_broker_hint()
        self._update_session_preview()

    def _request_workspace_pull(self):
        controller = getattr(self, "controller", None)
        profile = self._persist_platform_sync_profile()
        if controller is not None and hasattr(controller, "request_platform_workspace_pull"):
            controller.request_platform_workspace_pull(profile)

    def _request_workspace_push(self, *, interactive=True):
        controller = getattr(self, "controller", None)
        profile = self._persist_platform_sync_profile()
        payload = self._workspace_settings_payload()
        if controller is not None and hasattr(controller, "request_platform_workspace_push"):
            controller.request_platform_workspace_push(payload, profile, interactive=interactive)

    def _crypto_exchange_options_for_region(self):
        """Return available crypto exchange options based on selected region."""
        return list(CRYPTO_EXCHANGE_MAP.get(self._selected_customer_region(), CRYPTO_EXCHANGE_MAP["us"]))

    def _credential_field_schema(self):
        """Generate labels/placeholders and input modes for broker credential fields."""
        broker_type = self.exchange_type_box.currentText() if hasattr(self, "exchange_type_box") else ""
        exchange = self.exchange_box.currentText() if hasattr(self, "exchange_box") else ""

        schema = dict(EXCHANGE_CREDENTIAL_SCHEMAS["default"])
        schema.update(
            {
                "api_label": self._tr("dashboard.api_key"),
                "secret_label": self._tr("dashboard.secret"),
                "password_label": self._tr("dashboard.passphrase"),
                "account_label": self._tr("dashboard.account_id"),
            }
        )
        schema["field_targets"] = dict(schema.get("field_targets") or {})
        schema["field_fallbacks"] = dict(schema.get("field_fallbacks") or {})

        schema_key = None
        if exchange in EXCHANGE_CREDENTIAL_SCHEMAS:
            schema_key = exchange
        elif broker_type == "forex":
            schema_key = "oanda"

        if schema_key and schema_key != "default":
            override = EXCHANGE_CREDENTIAL_SCHEMAS[schema_key]
            merged_targets = dict(schema["field_targets"])
            merged_targets.update(dict(override.get("field_targets") or {}))
            merged_fallbacks = dict(schema["field_fallbacks"])
            merged_fallbacks.update(dict(override.get("field_fallbacks") or {}))
            schema.update(
                {
                    key: value
                    for key, value in override.items()
                    if key not in {"field_targets", "field_fallbacks"}
                }
            )
            schema["field_targets"] = merged_targets
            schema["field_fallbacks"] = merged_fallbacks

        if exchange == "ibkr":
            connection_mode = self._selected_ibkr_connection_mode()
            if connection_mode == "tws":
                schema.update(
                    {
                        "api_label": "Host",
                        "api_placeholder": "127.0.0.1",
                        "secret_label": "Port",
                        "secret_placeholder": "7497 for paper, 7496 for live",
                        "secret_echo": QLineEdit.Normal,
                        "password_label": "Client ID",
                        "password_placeholder": "1",
                        "password_echo": QLineEdit.Normal,
                        "account_label": "Account ID / Profile",
                        "account_placeholder": "Optional TWS account id or profile",
                        "show_password": True,
                        "show_account": True,
                        "required_fields": ("api", "secret", "password"),
                        "field_targets": {
                            "api": "options.host",
                            "secret": "options.port",
                            "password": "options.client_id",
                            "account": "account_id",
                        },
                    }
                )
            else:
                schema.update(
                    {
                        "api_label": "Base URL",
                        "api_placeholder": "https://127.0.0.1:5000/v1/api",
                        "secret_label": "Session Token",
                        "secret_placeholder": "Optional IBKR Web API bearer/session token",
                        "secret_echo": QLineEdit.Password,
                        "password_label": "WebSocket URL",
                        "password_placeholder": "Optional ws(s) override",
                        "password_echo": QLineEdit.Normal,
                        "account_label": "Account ID / Profile",
                        "account_placeholder": "Optional IBKR account id or profile",
                        "show_password": True,
                        "show_account": True,
                        "required_fields": ("api",),
                        "field_targets": {
                            "api": "options.base_url",
                            "secret": "api_key",
                            "password": "options.websocket_url",
                            "account": "account_id",
                        },
                    }
                )

        if exchange in {"okx", "kucoin"}:
            schema["show_password"] = True

        return schema

    @staticmethod
    def _schema_target_paths(target):
        """Normalize a schema target entry into a tuple of target paths."""
        if not target:
            return ()
        if isinstance(target, (tuple, list)):
            return tuple(path for path in target if path)
        return (target,)

    @staticmethod
    def _mapping_value(mapping, path):
        """Read a dotted path from a nested dictionary structure."""
        current = mapping
        for part in str(path or "").split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    @staticmethod
    def _set_mapping_value(mapping, path, value):
        """Write a dotted path into a nested dictionary structure."""
        if value is None or value == "":
            return
        parts = str(path or "").split(".")
        current = mapping
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value
        current[parts[-1]] = value

    @staticmethod
    def _looks_like_url(value):
        text = str(value or "").strip().lower()
        return text.startswith("http://") or text.startswith("https://")

    @staticmethod
    def _looks_like_solana_wallet(value):
        try:
            from broker.solana_broker import SolanaBroker
        except Exception:
            return False
        return SolanaBroker._looks_like_base58_key(str(value or "").strip(), expected_lengths=(32,))

    @staticmethod
    def _looks_like_solana_private_key(value):
        try:
            from broker.solana_broker import SolanaBroker
        except Exception:
            return False
        try:
            probe = SolanaBroker.__new__(SolanaBroker)
            probe._normalize_private_key_bytes(str(value or "").strip())
        except Exception:
            return False
        return True

    def _solana_field_values(self):
        """Return the dedicated Solana dashboard values."""
        is_paper_exchange = self.exchange_type_box.currentText() == "paper" or self.exchange_box.currentText() == "paper"
        if is_paper_exchange:
            return {
                "wallet_address": "",
                "private_key": "",
                "rpc_url": "",
                "jupiter_api_key": "",
                "okx_api_key": "",
                "okx_secret_key": "",
                "okx_passphrase": "",
                "okx_project_id": "",
            }
        return {
            "wallet_address": self.solana_wallet_address_input.text().strip(),
            "private_key": self.solana_private_key_input.text().strip(),
            "rpc_url": self.solana_rpc_url_input.text().strip(),
            "jupiter_api_key": self.solana_jupiter_api_key_input.text().strip(),
            "okx_api_key": self.solana_okx_api_key_input.text().strip(),
            "okx_secret_key": self.solana_okx_secret_input.text().strip(),
            "okx_passphrase": self.solana_okx_passphrase_input.text().strip(),
            "okx_project_id": self.solana_okx_project_id_input.text().strip(),
        }

    def _solana_okx_credentials_complete(self):
        values = self._solana_field_values()
        return bool(
            values["okx_api_key"]
            and values["okx_secret_key"]
            and values["okx_passphrase"]
        )

    def _solana_has_any_route_credentials(self):
        values = self._solana_field_values()
        return bool(self._solana_okx_credentials_complete() or values["jupiter_api_key"])

    def _solana_live_execution_ready(self):
        values = self._solana_field_values()
        return bool(
            values["wallet_address"]
            and values["private_key"]
            and self._solana_has_any_route_credentials()
        )

    def _dashboard_field_values(self, schema=None):
        """Return the current credential values keyed by raw dashboard field names."""
        schema = schema or self._credential_field_schema()
        is_paper = self.exchange_type_box.currentText() == "paper" or self.exchange_box.currentText() == "paper"
        return {
            "api": "" if is_paper else self.api_input.text().strip(),
            "secret": "" if is_paper else self.secret_input.text().strip(),
            "password": (
                ""
                if is_paper or not schema.get("show_password")
                else self.password_input.text().strip()
            ),
            "account": (
                ""
                if is_paper or not schema.get("show_account")
                else self.account_id_input.text().strip()
            ),
        }

    @staticmethod
    def _schema_label_key(field_name):
        """Return the schema key that stores a raw field's visible label."""
        return {
            "api": "api_label",
            "secret": "secret_label",
            "password": "password_label",
            "account": "account_label",
        }[field_name]

    def _schema_field_has_value(self, schema, resolved, field_name):
        """Return whether a required dashboard field resolved into broker config data."""
        for path in self._schema_target_paths((schema.get("field_targets") or {}).get(field_name)):
            value = self._mapping_value(resolved, path)
            if str(value or "").strip():
                return True
        return False

    def _schema_field_value_from_broker(self, schema, broker, field_name):
        """Read a saved broker value back into the matching dashboard field."""
        candidate_paths = []
        candidate_paths.extend(
            self._schema_target_paths((schema.get("field_targets") or {}).get(field_name))
        )
        candidate_paths.extend(
            self._schema_target_paths((schema.get("field_fallbacks") or {}).get(field_name))
        )
        for path in candidate_paths:
            value = self._mapping_value(broker, path)
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _populate_credential_fields(self, broker, schema=None):
        """Populate the dashboard credential inputs from a saved broker payload."""
        schema = schema or self._credential_field_schema()
        exchange = self.exchange_box.currentText()
        if exchange == "solana":
            options = dict((broker or {}).get("options") or {})
            raw_api = str((broker or {}).get("api_key") or "").strip()
            raw_secret = str((broker or {}).get("secret") or "").strip()
            raw_password = str(
                (broker or {}).get("password")
                or (broker or {}).get("passphrase")
                or ""
            ).strip()
            raw_account = str((broker or {}).get("account_id") or "").strip()

            wallet_address = str(options.get("wallet_address") or "").strip()
            private_key = str(options.get("private_key") or "").strip()
            rpc_url = str(options.get("rpc_url") or "").strip()
            jupiter_api_key = str(options.get("jupiter_api_key") or "").strip()
            okx_api_key = str(options.get("okx_api_key") or "").strip()
            okx_secret_key = str(options.get("okx_secret_key") or "").strip()
            okx_passphrase = str(options.get("okx_passphrase") or "").strip()
            okx_project_id = str(options.get("okx_project_id") or "").strip()

            if not wallet_address and self._looks_like_solana_wallet(raw_api):
                wallet_address = raw_api
            if not private_key and self._looks_like_solana_private_key(raw_secret):
                private_key = raw_secret

            if not okx_api_key and raw_api and raw_api != wallet_address:
                okx_api_key = raw_api
            if not okx_secret_key and raw_secret and raw_secret != private_key:
                okx_secret_key = raw_secret

            if raw_password:
                if okx_api_key or okx_secret_key or okx_passphrase:
                    okx_passphrase = okx_passphrase or raw_password
                else:
                    jupiter_api_key = jupiter_api_key or raw_password

            if raw_account:
                if self._looks_like_url(raw_account):
                    rpc_url = rpc_url or raw_account
                else:
                    okx_project_id = okx_project_id or raw_account

            self.solana_wallet_address_input.setText(wallet_address)
            self.solana_private_key_input.setText(private_key)
            self.solana_rpc_url_input.setText(rpc_url)
            self.solana_jupiter_api_key_input.setText(jupiter_api_key)
            self.solana_okx_api_key_input.setText(okx_api_key)
            self.solana_okx_secret_input.setText(okx_secret_key)
            self.solana_okx_passphrase_input.setText(okx_passphrase)
            self.solana_okx_project_id_input.setText(okx_project_id)
            self.api_input.clear()
            self.secret_input.clear()
            self.password_input.clear()
            self.account_id_input.clear()
            return

        self.api_input.setText(self._schema_field_value_from_broker(schema, broker, "api"))
        self.secret_input.setText(self._schema_field_value_from_broker(schema, broker, "secret"))
        self.password_input.setText(self._schema_field_value_from_broker(schema, broker, "password"))
        self.account_id_input.setText(self._schema_field_value_from_broker(schema, broker, "account"))

    def _apply_credential_field_schema(self):
        """Apply credential field schema to the current UI elements."""
        schema = self._credential_field_schema()

        api_block = self._field_blocks.get("api")
        if api_block is not None:
            api_block.label_widget.setText(schema["api_label"])
        self.api_input.setPlaceholderText(schema["api_placeholder"])

        secret_block = self._field_blocks.get("secret")
        if secret_block is not None:
            secret_block.label_widget.setText(schema["secret_label"])
        self.secret_input.setPlaceholderText(schema["secret_placeholder"])
        self.secret_input.setEchoMode(schema["secret_echo"])

        password_block = self._field_blocks.get("password")
        if password_block is not None:
            password_block.label_widget.setText(schema["password_label"])
        self.password_input.setPlaceholderText(schema["password_placeholder"])
        self.password_input.setEchoMode(schema["password_echo"])

        account_block = self._field_blocks.get("account_id")
        if account_block is not None:
            account_block.label_widget.setText(schema["account_label"])
        self.account_id_input.setPlaceholderText(schema["account_placeholder"])

        self._apply_solana_field_schema()

    def _apply_solana_field_schema(self):
        """Apply Solana-specific labels and placeholders."""
        if not hasattr(self, "solana_credentials_panel"):
            return
        self.solana_credentials_title.setText("Solana Routing")
        self.solana_wallet_title.setText("Wallet Signing")
        self.solana_okx_title.setText("OKX Trade API")
        self._field_blocks["solana_wallet_address"].label_widget.setText("Wallet Address")
        self._field_blocks["solana_private_key"].label_widget.setText("Private Key")
        self._field_blocks["solana_rpc_url"].label_widget.setText("RPC URL")
        self._field_blocks["solana_jupiter_api_key"].label_widget.setText("Legacy Jupiter API Key")
        self._field_blocks["solana_okx_api_key"].label_widget.setText("OKX API Key")
        self._field_blocks["solana_okx_secret"].label_widget.setText("OKX Secret")
        self._field_blocks["solana_okx_passphrase"].label_widget.setText("OKX Passphrase")
        self._field_blocks["solana_okx_project_id"].label_widget.setText("OKX Project ID")
        self.solana_wallet_address_input.setPlaceholderText("Solana wallet address for balances and live signing")
        self.solana_private_key_input.setPlaceholderText("Private key for live swaps")
        self.solana_rpc_url_input.setPlaceholderText("Optional custom Solana RPC URL")
        self.solana_jupiter_api_key_input.setPlaceholderText("Optional legacy Jupiter API key fallback")
        self.solana_okx_api_key_input.setPlaceholderText("OKX API key for Solana quotes and routing")
        self.solana_okx_secret_input.setPlaceholderText("OKX secret key")
        self.solana_okx_passphrase_input.setPlaceholderText("OKX passphrase")
        self.solana_okx_project_id_input.setPlaceholderText("Optional OKX project id")

    def _resolved_solana_inputs(self):
        """Return normalized Solana broker credential values from dedicated UI inputs."""
        values = self._solana_field_values()
        resolved = {
            "api_key": values["okx_api_key"] or None,
            "secret": values["okx_secret_key"] or None,
            "password": values["okx_passphrase"] or None,
            "account_id": values["okx_project_id"] or None,
            "options": {},
        }
        for key in ("wallet_address", "private_key", "rpc_url", "jupiter_api_key"):
            text = str(values.get(key) or "").strip()
            if text:
                resolved["options"][key] = text
        if resolved["api_key"]:
            resolved["options"]["okx_api_key"] = resolved["api_key"]
        if resolved["secret"]:
            resolved["options"]["okx_secret_key"] = resolved["secret"]
        if resolved["password"]:
            resolved["options"]["okx_passphrase"] = resolved["password"]
        if resolved["account_id"]:
            resolved["options"]["okx_project_id"] = resolved["account_id"]
        return resolved

    def _resolved_broker_inputs(self):
        """Return normalized broker credential values from UI inputs."""
        exchange = self.exchange_box.currentText()
        if exchange == "solana":
            return self._resolved_solana_inputs()

        schema = self._credential_field_schema()
        field_values = self._dashboard_field_values(schema)

        if exchange == "coinbase":
            field_values["api"], field_values["secret"], field_values["password"] = normalize_coinbase_credentials(
                field_values["api"],
                field_values["secret"],
                field_values["password"],
            )

        resolved = {
            "api_key": None,
            "secret": None,
            "password": None,
            "account_id": None,
            "options": {},
        }
        for field_name, value in field_values.items():
            if not value:
                continue
            for path in self._schema_target_paths((schema.get("field_targets") or {}).get(field_name)):
                self._set_mapping_value(resolved, path, value)

        if exchange == "ibkr":
            resolved.setdefault("options", {})
            resolved["options"]["connection_mode"] = self._selected_ibkr_connection_mode()
            resolved["options"]["environment"] = self._selected_ibkr_environment()
            if resolved["options"]["connection_mode"] == "tws":
                resolved["options"]["paper"] = self.mode_box.currentText() != "live"
            else:
                resolved["options"]["paper"] = False
        elif exchange == "schwab":
            resolved.setdefault("options", {})
            resolved["options"]["environment"] = self._selected_schwab_environment()
            if field_values.get("password"):
                resolved["options"]["redirect_uri"] = field_values["password"]

        return resolved

    @staticmethod
    def _strip_wrapped_quotes(value):
        """Remove surrounding single or double quotes from a string value."""
        text = str(value or "").strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            return text[1:-1].strip()
        return text

    @classmethod
    def _coinbase_validation_error(cls, api_key, secret, password=None):
        """Validate Coinbase credentials and return an error message if invalid."""
        return coinbase_validation_error(api_key, secret, password=password)

    def _build_ui(self):
        """Build the dashboard UI structure and layout."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(28, 28, 28, 28)

        self.shell = QWidget()
        self.shell_layout = QBoxLayout(QBoxLayout.LeftToRight, self.shell)
        self.shell_layout.setContentsMargins(0, 0, 0, 0)
        self.shell_layout.setSpacing(22)

        self.hero_panel = self._build_hero_panel()
        self.connect_panel = self._build_connect_panel()
        self.shell_layout.addWidget(self.hero_panel, 7)
        self.shell_layout.addWidget(self.connect_panel, 5)

        outer_layout.addWidget(self.shell)
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _build_hero_panel(self):
        """Build and return the dashboard hero status overview panel."""
        panel = QFrame()
        panel.setObjectName("heroPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(34, 34, 34, 34)
        panel_layout.setSpacing(22)

        top_row = QHBoxLayout()
        top_row.setSpacing(18)

        logo = QLabel()
        pixmap = QPixmap(str(LOGO_PATH)) if LOGO_PATH.exists() else QPixmap()
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        logo.setFixedSize(116, 116)
        logo.setAlignment(Qt.AlignCenter)
        top_row.addWidget(logo, 0, Qt.AlignTop)

        headline_col = QVBoxLayout()
        headline_col.setSpacing(8)

        self.eyebrow_label = QLabel("AI Trading Command Deck")
        self.eyebrow_label.setObjectName("eyebrow")
        headline_col.addWidget(self.eyebrow_label)

        self.hero_title_label = QLabel("TradeAdviser")
        self.hero_title_label.setObjectName("heroTitle")
        self.hero_title_label.setWordWrap(True)
        headline_col.addWidget(self.hero_title_label)

        self.hero_lead_label = QLabel(
            "Configure broker access and risk profile before launching the trading terminal. "
            "Strategy assignment happens automatically per symbol after launch, with terminal overrides available when needed."
        )
        self.hero_lead_label.setObjectName("heroLead")
        self.hero_lead_label.setWordWrap(True)
        headline_col.addWidget(self.hero_lead_label)

        top_row.addLayout(headline_col, 1)
        panel_layout.addLayout(top_row)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(12)
        pills_row.addWidget(self._create_stat_pill("Session", "Paper", value_attr="session_pill_value"))
        pills_row.addWidget(self._create_stat_pill("Readiness", "58%", value_attr="readiness_pill_value"))
        pills_row.addWidget(self._create_stat_pill("Market Reach", "Multi-Asset", value_attr="market_pill_value"))
        pills_row.addWidget(self._create_stat_pill("Workspace", "Open", value_attr="workspace_pill_value"))
        panel_layout.addLayout(pills_row)

        market_card = QFrame()
        market_card.setObjectName("glassCard")
        market_layout = QVBoxLayout(market_card)
        market_layout.setContentsMargins(20, 20, 20, 20)
        market_layout.setSpacing(12)

        self.market_title_label = QLabel("Desk Snapshot")
        self.market_title_label.setObjectName("heroSectionTitle")
        market_layout.addWidget(self.market_title_label)

        self.market_body_label = QLabel(
            "Use the dashboard like a pre-flight panel: confirm broker type, credentials, and risk posture before the terminal takes over."
        )
        self.market_body_label.setObjectName("heroSectionBody")
        self.market_body_label.setWordWrap(True)
        market_layout.addWidget(self.market_body_label)

        self.market_primary = self._create_market_strip("Primary Venue", "Venue routing stays aligned with customer region and launch mode.")
        self.market_secondary = self._create_market_strip("Strategy Routing", "Per-symbol strategy ranking starts after launch, and terminal overrides stay available.")
        self.market_tertiary = self._create_market_strip("Operator Signal", "Saved profile support keeps repeat sessions faster and safer.")
        market_layout.addWidget(self.market_primary)
        market_layout.addWidget(self.market_secondary)
        market_layout.addWidget(self.market_tertiary)
        panel_layout.addWidget(market_card)

        lower_grid = QGridLayout()
        lower_grid.setHorizontalSpacing(14)
        lower_grid.setVerticalSpacing(14)

        checklist_card = QFrame()
        checklist_card.setObjectName("glassCard")
        checklist_layout = QVBoxLayout(checklist_card)
        checklist_layout.setContentsMargins(20, 20, 20, 20)
        checklist_layout.setSpacing(12)

        self.checklist_title_label = QLabel("Launch Checklist")
        self.checklist_title_label.setObjectName("heroSectionTitle")
        checklist_layout.addWidget(self.checklist_title_label)

        self.check_credentials = self._create_checklist_row("Credentials", "Needs input")
        self.check_broker = self._create_checklist_row("Broker setup", "Ready")
        self.check_strategy = self._create_checklist_row("Strategy routing", "Automatic")
        self.check_risk = self._create_checklist_row("Risk profile", "Conservative")
        checklist_layout.addWidget(self.check_credentials)
        checklist_layout.addWidget(self.check_broker)
        checklist_layout.addWidget(self.check_strategy)
        checklist_layout.addWidget(self.check_risk)
        checklist_layout.addStretch(1)

        notes_card = QFrame()
        notes_card.setObjectName("glassCard")
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(20, 20, 20, 20)
        notes_layout.setSpacing(10)

        self.notes_title_label = QLabel("Session Notes")
        self.notes_title_label.setObjectName("heroSectionTitle")
        notes_layout.addWidget(self.notes_title_label)

        self.notes_bullet_labels = []
        for line in [
            "Paper mode is the safest way to verify broker setup and chart loading.",
            "Broker-specific fields appear only when the selected venue requires them.",
            "Saved profiles help repeat sessions start faster.",
            "Live sessions should be reviewed carefully before launch.",
        ]:
            item = QLabel(line)
            item.setObjectName("heroSectionBody")
            item.setWordWrap(True)
            notes_layout.addWidget(item)
            self.notes_bullet_labels.append(item)

        lower_grid.addWidget(checklist_card, 0, 0)
        lower_grid.addWidget(notes_card, 0, 1)
        panel_layout.addLayout(lower_grid)
        panel_layout.addStretch(1)
        return panel

    def _build_connect_panel(self):
        """Build and return the broker connection configuration panel."""
        panel = QFrame()
        panel.setObjectName("connectPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 28, 28, 28)
        panel_layout.setSpacing(16)

        self.connect_title_label = QLabel("Launch Session")
        self.connect_title_label.setObjectName("panelTitle")
        panel_layout.addWidget(self.connect_title_label)

        self.connect_body_label = QLabel(
            "Choose broker access, session mode, credentials, and risk settings before opening the trading workspace."
        )
        self.connect_body_label.setObjectName("panelBody")
        self.connect_body_label.setWordWrap(True)
        panel_layout.addWidget(self.connect_body_label)

        quick_launch_card = QFrame()
        quick_launch_card.setObjectName("summaryCard")
        quick_launch_layout = QVBoxLayout(quick_launch_card)
        quick_launch_layout.setContentsMargins(18, 18, 18, 18)
        quick_launch_layout.setSpacing(8)

        self.quick_launch_title = QLabel("Quick Launch")
        self.quick_launch_title.setObjectName("summaryTitle")
        quick_launch_layout.addWidget(self.quick_launch_title)

        self.quick_launch_body = QLabel(
            "Launch the terminal from the top of the dashboard, then return here only when you need to adjust broker or risk settings."
        )
        self.quick_launch_body.setObjectName("summaryBody")
        self.quick_launch_body.setWordWrap(True)
        quick_launch_layout.addWidget(self.quick_launch_body)

        self.quick_launch_meta = QLabel("Choose profile  |  Confirm mode  |  Open terminal")
        self.quick_launch_meta.setObjectName("summaryMeta")
        self.quick_launch_meta.setWordWrap(True)
        quick_launch_layout.addWidget(self.quick_launch_meta)

        self.quick_launch_button = QPushButton("Open Paper Terminal")
        self.quick_launch_button.setObjectName("connectButton")
        self.quick_launch_button.setMinimumHeight(52)
        quick_launch_layout.addWidget(self.quick_launch_button)

        panel_layout.addWidget(quick_launch_card)

        self.presets_label = QLabel("Quick Presets")
        self.presets_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.presets_label)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)
        self.paper_preset_button = self._create_preset_button("Paper Warmup")
        self.crypto_preset_button = self._create_preset_button("Crypto Live")
        self.fx_preset_button = self._create_preset_button("FX Live")
        presets_row.addWidget(self.paper_preset_button)
        presets_row.addWidget(self.crypto_preset_button)
        presets_row.addWidget(self.fx_preset_button)
        panel_layout.addLayout(presets_row)

        self.profile_label = QLabel("Saved Profiles")
        self.profile_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.profile_label)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(10)
        self.saved_account_box = QComboBox()
        self.saved_account_box.addItem("Recent profiles")
        profile_row.addWidget(self._wrap_field("Choose Profile", self.saved_account_box), 1)

        self.refresh_accounts_button = QPushButton("Refresh")
        self.refresh_accounts_button.setObjectName("secondaryButton")
        profile_row.addWidget(self.refresh_accounts_button, 0, Qt.AlignBottom)
        panel_layout.addLayout(profile_row)

        language_row = QHBoxLayout()
        language_row.setSpacing(10)
        self.language_box = QComboBox()
        for code, label in iter_supported_languages():
            self.language_box.addItem(label, code)
        language_row.addWidget(self._wrap_field("Language", self.language_box, block_name="language"), 1)
        panel_layout.addLayout(language_row)

        self.market_label = QLabel("Market Access")
        self.market_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.market_label)

        market_row = QHBoxLayout()
        market_row.setSpacing(10)
        self.exchange_type_box = QComboBox()
        self.exchange_type_box.addItems(BROKER_TYPE_OPTIONS)
        self.exchange_box = QComboBox()
        market_row.addWidget(self._wrap_field("Broker Type", self.exchange_type_box), 1)
        market_row.addWidget(self._wrap_field("Exchange", self.exchange_box), 1)
        panel_layout.addLayout(market_row)

        jurisdiction_row = QHBoxLayout()
        jurisdiction_row.setSpacing(10)
        self.customer_region_box = QComboBox()
        for label, value in CUSTOMER_REGION_OPTIONS:
            self.customer_region_box.addItem(label, value)
        saved_region = str(self.settings.value("dashboard/customer_region", "us") or "us").strip().lower()
        region_index = self.customer_region_box.findData(saved_region)
        self.customer_region_box.setCurrentIndex(region_index if region_index >= 0 else 0)
        jurisdiction_row.addWidget(self._wrap_field("Customer Region", self.customer_region_box, block_name="customer_region"), 1)
        jurisdiction_row.addStretch(1)
        panel_layout.addLayout(jurisdiction_row)

        strategy_row = QHBoxLayout()
        strategy_row.setSpacing(10)
        self.mode_box = QComboBox()
        self.mode_box.addItems(["live", "paper"])
        self.market_type_box = QComboBox()
        for label, value in MARKET_VENUE_CHOICES:
            self.market_type_box.addItem(label, value)
        strategy_row.addWidget(self._wrap_field("Mode", self.mode_box), 1)
        strategy_row.addWidget(self._wrap_field("Venue", self.market_type_box), 1)
        strategy_row.addStretch(1)
        panel_layout.addLayout(strategy_row)

        ibkr_row = QHBoxLayout()
        ibkr_row.setSpacing(10)
        self.ibkr_connection_mode_box = QComboBox()
        for label, value in IBKR_CONNECTION_MODE_OPTIONS:
            self.ibkr_connection_mode_box.addItem(label, value)
        ibkr_row.addWidget(self._wrap_field("IBKR Connection", self.ibkr_connection_mode_box, block_name="ibkr_connection_mode"), 1)

        self.ibkr_environment_box = QComboBox()
        for label, value in IBKR_WEBAPI_ENVIRONMENT_OPTIONS:
            self.ibkr_environment_box.addItem(label, value)
        ibkr_row.addWidget(self._wrap_field("IBKR Environment", self.ibkr_environment_box, block_name="ibkr_environment"), 1)
        ibkr_row.addStretch(1)
        panel_layout.addLayout(ibkr_row)

        schwab_row = QHBoxLayout()
        schwab_row.setSpacing(10)
        self.schwab_environment_box = QComboBox()
        for label, value in SCHWAB_ENVIRONMENT_OPTIONS:
            self.schwab_environment_box.addItem(label, value)
        schwab_row.addWidget(
            self._wrap_field("Schwab Environment", self.schwab_environment_box, block_name="schwab_environment"),
            1,
        )
        schwab_row.addStretch(1)
        panel_layout.addLayout(schwab_row)

        self.credentials_label = QLabel("Credentials")
        self.credentials_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.credentials_label)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Public key or broker token")
        panel_layout.addWidget(self._wrap_field("API Key", self.api_input, block_name="api"))

        self.secret_input = QLineEdit()
        self.secret_input.setEchoMode(QLineEdit.Password)
        self.secret_input.setPlaceholderText("Secret key")
        panel_layout.addWidget(self._wrap_field("Secret", self.secret_input, block_name="secret"))

        credential_row = QHBoxLayout()
        credential_row.setSpacing(10)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Exchange passphrase when required")
        credential_row.addWidget(self._wrap_field("Passphrase", self.password_input, block_name="password"), 1)

        self.account_id_input = QLineEdit()
        self.account_id_input.setPlaceholderText("Required for Oanda")
        credential_row.addWidget(self._wrap_field("Account ID", self.account_id_input, block_name="account_id"), 1)
        panel_layout.addLayout(credential_row)

        self.solana_credentials_panel = QFrame()
        self.solana_credentials_panel.setObjectName("glassCard")
        solana_layout = QVBoxLayout(self.solana_credentials_panel)
        solana_layout.setContentsMargins(18, 18, 18, 18)
        solana_layout.setSpacing(12)

        self.solana_credentials_title = QLabel("Solana Routing")
        self.solana_credentials_title.setObjectName("sectionLabel")
        solana_layout.addWidget(self.solana_credentials_title)

        self.solana_wallet_title = QLabel("Wallet Signing")
        self.solana_wallet_title.setObjectName("fieldLabel")
        solana_layout.addWidget(self.solana_wallet_title)

        solana_wallet_row = QHBoxLayout()
        solana_wallet_row.setSpacing(10)
        self.solana_wallet_address_input = QLineEdit()
        self.solana_wallet_address_input.setPlaceholderText("Solana wallet address for balances and live signing")
        solana_wallet_row.addWidget(
            self._wrap_field("Wallet Address", self.solana_wallet_address_input, block_name="solana_wallet_address"),
            1,
        )
        self.solana_private_key_input = QLineEdit()
        self.solana_private_key_input.setEchoMode(QLineEdit.Password)
        self.solana_private_key_input.setPlaceholderText("Private key for live swaps")
        solana_wallet_row.addWidget(
            self._wrap_field("Private Key", self.solana_private_key_input, block_name="solana_private_key"),
            1,
        )
        solana_layout.addLayout(solana_wallet_row)

        solana_wallet_options_row = QHBoxLayout()
        solana_wallet_options_row.setSpacing(10)
        self.solana_rpc_url_input = QLineEdit()
        self.solana_rpc_url_input.setPlaceholderText("Optional custom Solana RPC URL")
        solana_wallet_options_row.addWidget(
            self._wrap_field("RPC URL", self.solana_rpc_url_input, block_name="solana_rpc_url"),
            1,
        )
        self.solana_jupiter_api_key_input = QLineEdit()
        self.solana_jupiter_api_key_input.setEchoMode(QLineEdit.Password)
        self.solana_jupiter_api_key_input.setPlaceholderText("Optional legacy Jupiter API key fallback")
        solana_wallet_options_row.addWidget(
            self._wrap_field(
                "Legacy Jupiter API Key",
                self.solana_jupiter_api_key_input,
                block_name="solana_jupiter_api_key",
            ),
            1,
        )
        solana_layout.addLayout(solana_wallet_options_row)

        self.solana_okx_title = QLabel("OKX Trade API")
        self.solana_okx_title.setObjectName("fieldLabel")
        solana_layout.addWidget(self.solana_okx_title)

        solana_okx_row = QHBoxLayout()
        solana_okx_row.setSpacing(10)
        self.solana_okx_api_key_input = QLineEdit()
        self.solana_okx_api_key_input.setPlaceholderText("OKX API key for Solana quotes and routing")
        solana_okx_row.addWidget(
            self._wrap_field("OKX API Key", self.solana_okx_api_key_input, block_name="solana_okx_api_key"),
            1,
        )
        self.solana_okx_secret_input = QLineEdit()
        self.solana_okx_secret_input.setEchoMode(QLineEdit.Password)
        self.solana_okx_secret_input.setPlaceholderText("OKX secret key")
        solana_okx_row.addWidget(
            self._wrap_field("OKX Secret", self.solana_okx_secret_input, block_name="solana_okx_secret"),
            1,
        )
        solana_layout.addLayout(solana_okx_row)

        solana_okx_options_row = QHBoxLayout()
        solana_okx_options_row.setSpacing(10)
        self.solana_okx_passphrase_input = QLineEdit()
        self.solana_okx_passphrase_input.setEchoMode(QLineEdit.Password)
        self.solana_okx_passphrase_input.setPlaceholderText("OKX passphrase")
        solana_okx_options_row.addWidget(
            self._wrap_field(
                "OKX Passphrase",
                self.solana_okx_passphrase_input,
                block_name="solana_okx_passphrase",
            ),
            1,
        )
        self.solana_okx_project_id_input = QLineEdit()
        self.solana_okx_project_id_input.setPlaceholderText("Optional OKX project id")
        solana_okx_options_row.addWidget(
            self._wrap_field(
                "OKX Project ID",
                self.solana_okx_project_id_input,
                block_name="solana_okx_project_id",
            ),
            1,
        )
        solana_layout.addLayout(solana_okx_options_row)
        panel_layout.addWidget(self.solana_credentials_panel)

        self.risk_label = QLabel("Risk and Persistence")
        self.risk_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.risk_label)

        risk_row = QHBoxLayout()
        risk_row.setSpacing(10)
        self.risk_input = QSpinBox()
        self.risk_input.setRange(1, 100)
        self.risk_input.setValue(2)
        self.risk_input.setSuffix(" %")
        risk_row.addWidget(self._wrap_field("Risk Budget", self.risk_input), 1)

        self.remember_checkbox = QCheckBox("Save this broker profile")
        self.remember_checkbox.setChecked(True)
        remember_wrap = QWidget()
        remember_layout = QVBoxLayout(remember_wrap)
        remember_layout.setContentsMargins(0, 18, 0, 0)
        remember_layout.addWidget(self.remember_checkbox)
        risk_row.addWidget(remember_wrap, 1)
        panel_layout.addLayout(risk_row)

        self.platform_sync_label = QLabel("TradeAdviser Server Sync")
        self.platform_sync_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.platform_sync_label)

        self.platform_sync_card = QFrame()
        self.platform_sync_card.setObjectName("glassCard")
        platform_sync_layout = QVBoxLayout(self.platform_sync_card)
        platform_sync_layout.setContentsMargins(18, 18, 18, 18)
        platform_sync_layout.setSpacing(10)

        platform_sync_row = QHBoxLayout()
        platform_sync_row.setSpacing(10)
        self.server_url_input = QLineEdit()
        self.server_url_input.setPlaceholderText("http://127.0.0.1:8000")
        platform_sync_row.addWidget(self._wrap_field("Server URL", self.server_url_input), 1)
        self.server_email_input = QLineEdit()
        self.server_email_input.setPlaceholderText("Your TradeAdviser account email or username")
        platform_sync_row.addWidget(self._wrap_field("Account Email", self.server_email_input), 1)
        platform_sync_layout.addLayout(platform_sync_row)

        platform_sync_credentials_row = QHBoxLayout()
        platform_sync_credentials_row.setSpacing(10)
        self.server_password_input = QLineEdit()
        self.server_password_input.setEchoMode(QLineEdit.Password)
        self.server_password_input.setPlaceholderText("TradeAdviser account password")
        platform_sync_credentials_row.addWidget(self._wrap_field("Account Password", self.server_password_input), 1)
        self.sync_workspace_checkbox = QCheckBox("Sync this workspace with TradeAdviser server on connect")
        sync_checkbox_wrap = QWidget()
        sync_checkbox_layout = QVBoxLayout(sync_checkbox_wrap)
        sync_checkbox_layout.setContentsMargins(0, 18, 0, 0)
        sync_checkbox_layout.addWidget(self.sync_workspace_checkbox)
        platform_sync_credentials_row.addWidget(sync_checkbox_wrap, 1)
        platform_sync_layout.addLayout(platform_sync_credentials_row)

        platform_sync_actions_row = QHBoxLayout()
        platform_sync_actions_row.setSpacing(8)
        self.sync_now_button = QPushButton("Sync Now")
        self.sync_now_button.setObjectName("secondaryButton")
        platform_sync_actions_row.addWidget(self.sync_now_button)
        self.load_from_server_button = QPushButton("Load From Server")
        self.load_from_server_button.setObjectName("secondaryButton")
        platform_sync_actions_row.addWidget(self.load_from_server_button)
        platform_sync_actions_row.addStretch(1)
        platform_sync_layout.addLayout(platform_sync_actions_row)

        self.platform_sync_status_label = QLabel("Ready to sync this desktop with TradeAdviser server.")
        self.platform_sync_status_label.setObjectName("hintLabel")
        self.platform_sync_status_label.setWordWrap(True)
        platform_sync_layout.addWidget(self.platform_sync_status_label)

        panel_layout.addWidget(self.platform_sync_card)

        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.setSpacing(8)

        self.summary_title = QLabel("Paper desk ready")
        self.summary_title.setObjectName("summaryTitle")
        summary_layout.addWidget(self.summary_title)

        self.summary_body = QLabel("Start with a paper rehearsal, verify the broker shape, then move into the full terminal.")
        self.summary_body.setObjectName("summaryBody")
        self.summary_body.setWordWrap(True)
        summary_layout.addWidget(self.summary_body)

        self.summary_meta = QLabel("Risk 2%  |  Strategy Auto per symbol  |  Profile not saved yet")
        self.summary_meta.setObjectName("summaryMeta")
        self.summary_meta.setWordWrap(True)
        summary_layout.addWidget(self.summary_meta)

        self.live_guard_checkbox = QCheckBox("I understand this session can place live orders.")
        self.live_guard_checkbox.setVisible(False)
        summary_layout.addWidget(self.live_guard_checkbox)

        self.workspace_status_label = QLabel("Workspace access: enabled")
        self.workspace_status_label.setObjectName("hintLabel")
        self.workspace_status_label.setWordWrap(True)
        summary_layout.addWidget(self.workspace_status_label)

        panel_layout.addWidget(summary_card)

        self.broker_hint = QLabel()
        self.broker_hint.setObjectName("hintLabel")
        self.broker_hint.setWordWrap(True)
        panel_layout.addWidget(self.broker_hint)

        self.spinner = QLabel()
        self.spinner.setAlignment(Qt.AlignCenter)
        self.spinner.setVisible(False)
        self.spinner_movie = QMovie(str(SPINNER_PATH)) if SPINNER_PATH.exists() else None
        if self.spinner_movie is not None:
            self.spinner.setMovie(self.spinner_movie)
        panel_layout.addWidget(self.spinner)

        self.connect_button = QPushButton("Open Paper Terminal")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.setMinimumHeight(56)
        panel_layout.addWidget(self.connect_button)

        self.active_sessions_label = QLabel("Active Sessions")
        self.active_sessions_label.setObjectName("sectionLabel")
        panel_layout.addWidget(self.active_sessions_label)

        active_sessions_row = QHBoxLayout()
        active_sessions_row.setSpacing(8)
        self.active_session_box = QComboBox()
        self.active_session_box.addItem("No active sessions", "")
        active_sessions_row.addWidget(self._wrap_field("Session Registry", self.active_session_box), 1)

        self.activate_session_button = QPushButton("Activate")
        self.activate_session_button.setObjectName("secondaryButton")
        active_sessions_row.addWidget(self.activate_session_button, 0, Qt.AlignBottom)

        self.start_session_button = QPushButton("Start")
        self.start_session_button.setObjectName("secondaryButton")
        active_sessions_row.addWidget(self.start_session_button, 0, Qt.AlignBottom)

        self.stop_session_button = QPushButton("Stop")
        self.stop_session_button.setObjectName("secondaryButton")
        active_sessions_row.addWidget(self.stop_session_button, 0, Qt.AlignBottom)

        self.destroy_session_button = QPushButton("Remove")
        self.destroy_session_button.setObjectName("secondaryButton")
        active_sessions_row.addWidget(self.destroy_session_button, 0, Qt.AlignBottom)

        self.refresh_sessions_button = QPushButton("Refresh")
        self.refresh_sessions_button.setObjectName("secondaryButton")
        active_sessions_row.addWidget(self.refresh_sessions_button, 0, Qt.AlignBottom)
        panel_layout.addLayout(active_sessions_row)

        self.active_sessions_summary = QLabel("No sessions connected yet.")
        self.active_sessions_summary.setObjectName("hintLabel")
        self.active_sessions_summary.setWordWrap(True)
        panel_layout.addWidget(self.active_sessions_summary)

        self.footer_label = QLabel(
            "Start in paper mode when testing a new broker path. "
            "Per-symbol strategy assignment happens after launch, and the terminal can still override it when needed."
        )
        self.footer_label.setObjectName("hintLabel")
        self.footer_label.setWordWrap(True)
        panel_layout.addWidget(self.footer_label)

        panel_layout.addStretch(1)
        return panel

    def _create_stat_pill(self, label, value, value_attr=None):
        """Create a reusable stat pill widget for status display."""
        pill = QFrame()
        pill.setObjectName("statPill")
        pill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(pill)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        label_widget = QLabel(label)
        label_widget.setObjectName("pillLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("pillValue")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        if value_attr:
            setattr(self, value_attr, value_widget)
        return pill

    def _create_market_strip(self, title, body):
        """Create a reusable market status strip with title and description."""
        card = QFrame()
        card.setObjectName("marketStrip")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("marketTitle")
        body_label = QLabel(body)
        body_label.setObjectName("marketBody")
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)

        card.title_label = title_label
        card.body_label = body_label
        return card

    def _create_checklist_row(self, title, state):
        """Create a checklist row widget for launch status indicators."""
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("checkTitle")
        state_label = QLabel(state)
        state_label.setObjectName("checkStateWarn")

        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(state_label)

        row.title_label = title_label
        row.state_label = state_label
        return row

    def _create_preset_button(self, text):
        """Create a styled preset button."""
        button = QPushButton(text)
        button.setObjectName("presetButton")
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _wrap_field(self, label_text, widget, block_name=None):
        """Wrap a field input widget with a label and optional field block registration."""
        block = QFrame()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(7)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        block_layout.addWidget(label)
        block_layout.addWidget(widget)
        block.label_widget = label
        block.field_widget = widget

        if block_name:
            self._field_blocks[block_name] = block

        return block

    def _connect_signals(self):
        """Wire UI events to their corresponding handlers."""
        self.exchange_type_box.currentTextChanged.connect(self._update_exchange_list)
        self.exchange_type_box.currentTextChanged.connect(self._update_optional_fields)
        self.exchange_type_box.currentTextChanged.connect(self._update_broker_hint)
        self.exchange_type_box.currentTextChanged.connect(self._update_session_preview)
        self.customer_region_box.currentIndexChanged.connect(self._handle_customer_region_changed)
        self.exchange_box.currentTextChanged.connect(self._update_optional_fields)
        self.exchange_box.currentTextChanged.connect(self._update_broker_hint)
        self.exchange_box.currentTextChanged.connect(self._update_session_preview)
        self.mode_box.currentTextChanged.connect(self._update_broker_hint)
        self.mode_box.currentTextChanged.connect(self._update_session_preview)
        self.mode_box.currentTextChanged.connect(self._sync_ibkr_default_fields)
        self.ibkr_connection_mode_box.currentIndexChanged.connect(self._update_optional_fields)
        self.ibkr_connection_mode_box.currentIndexChanged.connect(self._update_broker_hint)
        self.ibkr_connection_mode_box.currentIndexChanged.connect(self._update_session_preview)
        self.ibkr_connection_mode_box.currentIndexChanged.connect(self._sync_ibkr_default_fields)
        self.ibkr_environment_box.currentIndexChanged.connect(self._update_broker_hint)
        self.ibkr_environment_box.currentIndexChanged.connect(self._update_session_preview)
        self.schwab_environment_box.currentIndexChanged.connect(self._update_broker_hint)
        self.schwab_environment_box.currentIndexChanged.connect(self._update_session_preview)
        self.market_type_box.currentIndexChanged.connect(self._update_session_preview)
        self.risk_input.valueChanged.connect(self._update_session_preview)
        self.api_input.textChanged.connect(self._update_session_preview)
        self.secret_input.textChanged.connect(self._update_session_preview)
        self.password_input.textChanged.connect(self._update_session_preview)
        self.account_id_input.textChanged.connect(self._update_session_preview)
        self.solana_wallet_address_input.textChanged.connect(self._update_session_preview)
        self.solana_private_key_input.textChanged.connect(self._update_session_preview)
        self.solana_rpc_url_input.textChanged.connect(self._update_session_preview)
        self.solana_jupiter_api_key_input.textChanged.connect(self._update_session_preview)
        self.solana_okx_api_key_input.textChanged.connect(self._update_session_preview)
        self.solana_okx_secret_input.textChanged.connect(self._update_session_preview)
        self.solana_okx_passphrase_input.textChanged.connect(self._update_session_preview)
        self.solana_okx_project_id_input.textChanged.connect(self._update_session_preview)
        self.remember_checkbox.toggled.connect(self._update_session_preview)
        self.live_guard_checkbox.toggled.connect(self._update_session_preview)
        self.server_url_input.editingFinished.connect(self._persist_platform_sync_profile)
        self.server_email_input.editingFinished.connect(self._persist_platform_sync_profile)
        self.server_password_input.editingFinished.connect(self._persist_platform_sync_profile)
        self.sync_workspace_checkbox.toggled.connect(lambda _checked: self._persist_platform_sync_profile())
        self.saved_account_box.currentTextChanged.connect(self._load_selected_account)
        self.refresh_accounts_button.clicked.connect(self._load_accounts_index)
        self.refresh_sessions_button.clicked.connect(self.refresh_active_sessions)
        self.activate_session_button.clicked.connect(self._activate_selected_session)
        self.start_session_button.clicked.connect(self._start_selected_session)
        self.stop_session_button.clicked.connect(self._stop_selected_session)
        self.destroy_session_button.clicked.connect(self._destroy_selected_session)
        self.language_box.currentIndexChanged.connect(self._on_language_changed)
        self.paper_preset_button.clicked.connect(lambda: self._apply_preset("paper"))
        self.crypto_preset_button.clicked.connect(lambda: self._apply_preset("crypto"))
        self.fx_preset_button.clicked.connect(lambda: self._apply_preset("forex"))
        self.sync_now_button.clicked.connect(lambda: self._request_workspace_push(interactive=True))
        self.load_from_server_button.clicked.connect(self._request_workspace_pull)
        self.connect_button.clicked.connect(self._on_connect)
        self.quick_launch_button.clicked.connect(self._on_connect)

    def _on_language_changed(self, _index):
        """Handle language selection changes from the UI."""
        language_code = self._language_box_current_code()
        if not language_code or not hasattr(self.controller, "set_language"):
            return
        self.controller.set_language(language_code)

    def apply_language(self):
        """Apply translations to all UI text elements based on selected language."""
        previous_language = getattr(self, "_applied_language_code", None)
        self.setWindowTitle(self._tr("dashboard.window_title"))

        self.eyebrow_label.setText(self._tr("dashboard.hero_eyebrow"))
        self.hero_title_label.setText(self._tr("dashboard.hero_title"))
        self.hero_lead_label.setText(self._tr("dashboard.hero_lead"))
        self.market_title_label.setText(self._tr("dashboard.desk_snapshot_title"))
        self.market_body_label.setText(self._tr("dashboard.desk_snapshot_body"))
        self.market_primary.title_label.setText(self._tr("dashboard.market_primary_title"))
        self.market_secondary.title_label.setText(self._tr("dashboard.market_secondary_title"))
        self.market_tertiary.title_label.setText(self._tr("dashboard.market_tertiary_title"))

        self.checklist_title_label.setText(self._tr("dashboard.launch_checklist_title"))
        self.check_credentials.title_label.setText(self._tr("dashboard.check_credentials_title"))
        self.check_broker.title_label.setText(self._tr("dashboard.check_broker_title"))
        self.check_strategy.title_label.setText(self._tr("dashboard.check_strategy_title"))
        self.check_risk.title_label.setText(self._tr("dashboard.check_risk_title"))

        self.notes_title_label.setText(self._tr("dashboard.notes_title"))
        for label, key in zip(
            self.notes_bullet_labels,
            (
                "dashboard.notes_bullet_1",
                "dashboard.notes_bullet_2",
                "dashboard.notes_bullet_3",
                "dashboard.notes_bullet_4",
            ),
        ):
            label.setText(self._tr(key))

        self.connect_title_label.setText(self._tr("dashboard.connect_title"))
        self.connect_body_label.setText(self._tr("dashboard.connect_body"))
        self.presets_label.setText(self._tr("dashboard.quick_presets"))
        self.paper_preset_button.setText(self._tr("dashboard.paper_preset"))
        self.crypto_preset_button.setText(self._tr("dashboard.crypto_preset"))
        self.fx_preset_button.setText(self._tr("dashboard.fx_preset"))
        self.profile_label.setText(self._tr("dashboard.saved_profiles"))
        self.refresh_accounts_button.setText(self._tr("dashboard.refresh"))
        self.market_label.setText(self._tr("dashboard.market_access"))
        self.credentials_label.setText(self._tr("dashboard.credentials"))
        self.risk_label.setText(self._tr("dashboard.risk_persistence"))
        self.remember_checkbox.setText(self._tr("dashboard.save_profile"))

        field_labels = {
            "language": "dashboard.language",
            "customer_region": None,
            "api": "dashboard.api_key",
            "secret": "dashboard.secret",
            "password": "dashboard.passphrase",
            "account_id": "dashboard.account_id",
            "ibkr_connection_mode": None,
            "ibkr_environment": None,
            "schwab_environment": None,
        }
        for block_name, key in field_labels.items():
            block = self._field_blocks.get(block_name)
            if block is not None:
                if block_name == "customer_region":
                    block.label_widget.setText("Customer Region")
                elif block_name == "ibkr_connection_mode":
                    block.label_widget.setText("IBKR Connection")
                elif block_name == "ibkr_environment":
                    block.label_widget.setText("IBKR Environment")
                elif block_name == "schwab_environment":
                    block.label_widget.setText("Schwab Environment")
                else:
                    block.label_widget.setText(self._tr(key) if key else block.label_widget.text())

        self.password_input.setPlaceholderText("Exchange passphrase when required")
        self._apply_credential_field_schema()

        if self.language_box is not None:
            current_code = getattr(self.controller, "language_code", self._language_box_current_code())
            self.language_box.blockSignals(True)
            for index, (code, label) in enumerate(iter_supported_languages()):
                self.language_box.setItemText(index, label)
                if code == current_code:
                    self.language_box.setCurrentIndex(index)
            self.language_box.blockSignals(False)

        recent_text = self._tr("dashboard.recent_profiles")
        if self.saved_account_box.count() > 0:
            self.saved_account_box.blockSignals(True)
            self.saved_account_box.setItemText(0, recent_text)
            self.saved_account_box.setItemData(0, "__recent__")
            self.saved_account_box.blockSignals(False)

        profile_block = self.saved_account_box.parentWidget()
        if profile_block is not None and hasattr(profile_block, "label_widget"):
            profile_block.label_widget.setText(self._tr("dashboard.choose_profile"))

        exchange_type_block = self.exchange_type_box.parentWidget()
        if exchange_type_block is not None and hasattr(exchange_type_block, "label_widget"):
            exchange_type_block.label_widget.setText(self._tr("dashboard.broker_type"))

        exchange_block = self.exchange_box.parentWidget()
        if exchange_block is not None and hasattr(exchange_block, "label_widget"):
            exchange_block.label_widget.setText(self._tr("dashboard.exchange"))

        mode_block = self.mode_box.parentWidget()
        if mode_block is not None and hasattr(mode_block, "label_widget"):
            mode_block.label_widget.setText(self._tr("dashboard.mode"))

        market_type_block = self.market_type_box.parentWidget()
        if market_type_block is not None and hasattr(market_type_block, "label_widget"):
            market_type_block.label_widget.setText("Venue")

        risk_block = self.risk_input.parentWidget()
        if risk_block is not None and hasattr(risk_block, "label_widget"):
            risk_block.label_widget.setText(self._tr("dashboard.risk_budget"))

        self._update_session_preview()
        apply_runtime_translations(
            self,
            getattr(self.controller, "language_code", "en"),
            previous_language=previous_language,
        )
        self._applied_language_code = getattr(self.controller, "language_code", "en")

    def _load_accounts_index(self):
        """Load available saved broker profiles into the profile combo box."""
        current = self.saved_account_box.currentText()
        accounts = CredentialManager.list_accounts()
        self.saved_account_box.blockSignals(True)
        self.saved_account_box.clear()
        self.saved_account_box.addItem(self._tr("dashboard.recent_profiles"), "__recent__")
        self.saved_account_box.addItems(accounts)
        if current in accounts:
            self.saved_account_box.setCurrentText(current)
        self.saved_account_box.blockSignals(False)
        self._update_session_preview()

    def _load_selected_account(self, account_name):
        """Load a saved account settings profile and populate form fields."""
        if not account_name or self.saved_account_box.currentData() == "__recent__":
            return

        creds = CredentialManager.load_account(account_name)
        if not creds:
            return

        CredentialManager.touch_account(account_name)
        self.settings.setValue(self.LAST_PROFILE_SETTING, account_name)

        broker = creds.get("broker", {})
        self.exchange_type_box.setCurrentText(broker.get("type", "crypto"))
        exchange_value = str(broker.get("exchange", "") or "").strip().lower()
        default_region = "global" if exchange_value == "binance" else "us"
        region_value = str(
            broker.get("customer_region")
            or (broker.get("options", {}) or {}).get("customer_region")
            or default_region
        ).strip().lower()
        region_index = self.customer_region_box.findData(region_value)
        self.customer_region_box.setCurrentIndex(region_index if region_index >= 0 else 0)
        self._update_exchange_list(broker.get("type", "crypto"))
        self.exchange_box.setCurrentText(broker.get("exchange", ""))
        ibkr_options = dict(broker.get("options", {}) or {})
        ibkr_mode_index = self.ibkr_connection_mode_box.findData(
            self._normalize_ibkr_connection_mode(ibkr_options.get("connection_mode"))
        )
        self.ibkr_connection_mode_box.setCurrentIndex(ibkr_mode_index if ibkr_mode_index >= 0 else 0)
        ibkr_environment_index = self.ibkr_environment_box.findData(
            str(ibkr_options.get("environment") or "gateway").strip().lower() or "gateway"
        )
        self.ibkr_environment_box.setCurrentIndex(ibkr_environment_index if ibkr_environment_index >= 0 else 0)
        schwab_environment_index = self.schwab_environment_box.findData(
            str(ibkr_options.get("environment") or "sandbox").strip().lower() or "sandbox"
        )
        self.schwab_environment_box.setCurrentIndex(schwab_environment_index if schwab_environment_index >= 0 else 0)
        self._update_optional_fields()
        self._populate_credential_fields(broker)
        self._refresh_market_type_options()
        self.mode_box.setCurrentText(broker.get("mode", "paper"))
        market_type_index = self.market_type_box.findData((broker.get("options", {}) or {}).get("market_type", "auto"))
        self.market_type_box.setCurrentIndex(market_type_index if market_type_index >= 0 else 0)
        self.risk_input.setValue(int(creds.get("risk", {}).get("risk_percent", 2) or 2))

        self._update_optional_fields()
        self._update_broker_hint()
        self._update_session_preview()

    def _load_last_account(self):
        """Load last used profile at startup if available."""
        accounts = CredentialManager.list_accounts()
        if not accounts:
            return
        saved_last = str(self.settings.value(self.LAST_PROFILE_SETTING, "") or "").strip()
        target = saved_last if saved_last in accounts else accounts[0]
        self.saved_account_box.setCurrentText(target)
        self._load_selected_account(target)

    def _apply_preset(self, preset_name):
        """Apply a preset configuration for quick session setup."""
        if preset_name == "paper":
            self.exchange_type_box.setCurrentText("paper")
            self._update_exchange_list("paper")
            self.exchange_box.setCurrentText("paper")
            self.mode_box.setCurrentText("paper")
            self._refresh_market_type_options()
            auto_index = self.market_type_box.findData("auto")
            self.market_type_box.setCurrentIndex(auto_index if auto_index >= 0 else 0)
            self.risk_input.setValue(2)
        elif preset_name == "crypto":
            self.exchange_type_box.setCurrentText("crypto")
            region_index = self.customer_region_box.findData("us")
            if region_index >= 0:
                self.customer_region_box.setCurrentIndex(region_index)
            self._update_exchange_list("crypto")
            if self.exchange_box.findText("binanceus") >= 0:
                self.exchange_box.setCurrentText("binanceus")
            self.mode_box.setCurrentText("live")
            self._refresh_market_type_options()
            spot_index = self.market_type_box.findData("spot")
            self.market_type_box.setCurrentIndex(spot_index if spot_index >= 0 else 0)
            self.risk_input.setValue(2)
        elif preset_name == "forex":
            self.exchange_type_box.setCurrentText("forex")
            self._update_exchange_list("forex")
            self.exchange_box.setCurrentText("oanda")
            self.mode_box.setCurrentText("live")
            self._refresh_market_type_options()
            otc_index = self.market_type_box.findData("otc")
            self.market_type_box.setCurrentIndex(otc_index if otc_index >= 0 else 0)
            self.risk_input.setValue(1)

        self._update_optional_fields()
        self._update_broker_hint()
        self._update_session_preview()

    def _handle_customer_region_changed(self):
        """Handle changes to customer region and update dependent fields."""
        region = self._selected_customer_region()
        self.settings.setValue("dashboard/customer_region", region)
        if self.exchange_type_box.currentText() == "crypto":
            self._update_exchange_list("crypto")
        self._update_optional_fields()
        self._update_broker_hint()
        self._update_session_preview()

    def _update_exchange_list(self, exchange_type):
        """Update the exchange dropdown list when broker type changes."""
        current = self.exchange_box.currentText()
        if exchange_type == "crypto":
            exchanges = self._crypto_exchange_options_for_region()
        else:
            exchanges = EXCHANGE_MAP.get(exchange_type, [])

        self.exchange_box.blockSignals(True)
        self.exchange_box.clear()
        self.exchange_box.addItems(exchanges)
        if current in exchanges:
            self.exchange_box.setCurrentText(current)
        elif exchanges:
            self.exchange_box.setCurrentIndex(0)
        self.exchange_box.blockSignals(False)

    def _refresh_market_type_options(self):
        """Refresh the market-type options to only include supported venues for the selected profile."""
        current = str(self.market_type_box.currentData() or "auto").strip().lower() or "auto"
        
        exchange_type = self.exchange_type_box.currentText()
        exchange = self.exchange_box.currentText()
        
        # Get supported market types from broker profile
        supported_market_types = []
        try:
            profile = _get_broker_profile_for_selection(exchange_type, exchange)
            if profile:
                supported_market_types = [mt.value.lower() for mt in profile.market_types]
        except Exception:
            pass
        
        # Fall back to old system if profile not found
        if not supported_market_types:
            try:
                supported = supported_market_venues_for_profile(exchange_type, exchange)
                supported_market_types = list(supported) if supported else ["auto"]
            except Exception:
                supported_market_types = ["auto"]
        
        self.market_type_box.blockSignals(True)
        self.market_type_box.clear()
        
        # Add auto option always
        self.market_type_box.addItem("Auto", "auto")
        
        # Add supported market types
        for label, value in MARKET_TYPE_CHOICES_NEW:
            if value == "auto":
                continue  # Already added
            if not supported_market_types or value in supported_market_types or value == current:
                self.market_type_box.addItem(label, value)
        
        # Set current value
        target = current if current in [d for _, d in [(self.market_type_box.itemData(i), self.market_type_box.itemData(i)) for i in range(self.market_type_box.count())]] else "auto"
        index = self.market_type_box.findData(target)
        self.market_type_box.setCurrentIndex(index if index >= 0 else 0)
        self.market_type_box.blockSignals(False)

    def _sync_ibkr_default_fields(self):
        exchange = self.exchange_box.currentText()
        if exchange != "ibkr":
            self._ibkr_last_connection_mode = None
            return

        connection_mode = self._selected_ibkr_connection_mode()
        previous_mode = self._ibkr_last_connection_mode
        if previous_mode and previous_mode != connection_mode:
            self._remember_ibkr_mode_fields(previous_mode)
            self._apply_ibkr_mode_fields(connection_mode)
        else:
            defaults = self._ibkr_mode_defaults(connection_mode)
            if connection_mode == "tws":
                if not self.api_input.text().strip():
                    self.api_input.setText(defaults["api"])
                if not self.secret_input.text().strip() or self.secret_input.text().strip() in {"7496", "7497"}:
                    self.secret_input.setText(defaults["secret"])
                if not self.password_input.text().strip():
                    self.password_input.setText(defaults["password"])
            elif not self.api_input.text().strip():
                self.api_input.setText(defaults["api"])

        self._ibkr_last_connection_mode = connection_mode

    def _ibkr_mode_defaults(self, connection_mode):
        normalized = self._normalize_ibkr_connection_mode(connection_mode)
        if normalized == "tws":
            return {
                "api": "127.0.0.1",
                "secret": "7496" if self.mode_box.currentText() == "live" else "7497",
                "password": "1",
            }
        return {
            "api": "https://127.0.0.1:5000/v1/api",
            "secret": "",
            "password": "",
        }

    def _remember_ibkr_mode_fields(self, connection_mode):
        normalized = self._normalize_ibkr_connection_mode(connection_mode)
        self._ibkr_mode_field_memory[normalized] = {
            "api": self.api_input.text().strip(),
            "secret": self.secret_input.text().strip(),
            "password": self.password_input.text().strip(),
        }

    def _apply_ibkr_mode_fields(self, connection_mode):
        normalized = self._normalize_ibkr_connection_mode(connection_mode)
        values = dict(self._ibkr_mode_field_memory.get(normalized) or {})
        defaults = self._ibkr_mode_defaults(normalized)
        self.api_input.setText(str(values.get("api") or defaults["api"]))
        self.secret_input.setText(str(values.get("secret") or defaults["secret"]))
        self.password_input.setText(str(values.get("password") or defaults["password"]))

    def _update_optional_fields(self):
        """Show/hide broker-specific form fields based on selected exchange type."""
        broker_type = self.exchange_type_box.currentText()
        exchange = self.exchange_box.currentText()
        schema = self._credential_field_schema()
        is_paper = broker_type == "paper" or exchange == "paper"
        is_solana = exchange == "solana" and not is_paper
        self._refresh_market_type_options()
        self._sync_ibkr_default_fields()

        self._field_blocks["api"].setVisible((not is_paper) and not is_solana)
        self._field_blocks["secret"].setVisible((not is_paper) and not is_solana)
        self._field_blocks["account_id"].setVisible((not is_paper) and (not is_solana) and bool(schema.get("show_account")))
        self._field_blocks["password"].setVisible((not is_paper) and (not is_solana) and bool(schema.get("show_password")))
        self.solana_credentials_panel.setVisible(is_solana)
        self._field_blocks["customer_region"].setVisible(broker_type == "crypto" and not is_paper)
        self._field_blocks["ibkr_connection_mode"].setVisible(exchange == "ibkr" and not is_paper)
        self._field_blocks["ibkr_environment"].setVisible(
            exchange == "ibkr" and not is_paper and self._selected_ibkr_connection_mode() == "webapi"
        )
        self._field_blocks["schwab_environment"].setVisible(exchange == "schwab" and not is_paper)

        if is_paper:
            self.mode_box.blockSignals(True)
            self.mode_box.setCurrentText("paper")
            self.mode_box.blockSignals(False)
            self.mode_box.setEnabled(False)
        else:
            self.mode_box.setEnabled(True)

        venue_enabled = self.market_type_box.count() > 1
        self.market_type_box.setEnabled(venue_enabled)
        if not venue_enabled:
            self.market_type_box.blockSignals(True)
            self.market_type_box.setCurrentIndex(0)
            self.market_type_box.blockSignals(False)

        self._apply_credential_field_schema()

    def _update_broker_hint(self):
        """Update broker hint text describing selected broker/mode constraints."""
        broker_type = self.exchange_type_box.currentText()
        exchange = self.exchange_box.currentText()
        mode = self.mode_box.currentText()
        market_type = self.market_type_box.currentData()
        customer_region = self._selected_customer_region()

        copy = BROKER_COPY.get(broker_type, "Configure a broker session and launch the terminal.")
        if exchange:
            copy = f"{exchange.upper()} in {mode.upper()} mode. {copy}"
        if exchange and exchange != "paper":
            copy += f" Trading venue preference: {str(market_type or 'auto').upper()}."
        if broker_type == "crypto" and exchange and exchange != "paper":
            if mode == "paper":
                copy += " Paper mode uses Sopotek's local paper broker with live public market data from the selected exchange."
            if exchange == "binanceus":
                copy += " Binance US is reserved for US customers."
            elif exchange == "binance":
                copy += " Binance.com is for customers outside the US."
            elif exchange == "coinbase":
                copy += (
                    " For Coinbase Advanced Trade, paste the API key name in the first field "
                    "and the privateKey value in the second field."
                )
                if str(market_type or "").strip().lower() == "derivative":
                    copy += " Derivative venue now defaults to Coinbase futures routing."
            copy += f" Customer region: {customer_region.upper()}."
        if exchange == "stellar":
            copy += (
                " Use your Stellar public key in the first field. "
                "The private key is optional for read-only market data, but required for order execution."
            )
        elif exchange == "solana":
            copy += (
                " Solana now uses a dedicated routing panel. "
                "Keep wallet signing details separate from OKX Trade API credentials, and use the legacy Jupiter field only when you need the older fallback route. "
                "Live Solana execution still requires a wallet address and matching private key for local signing."
            )
        elif exchange == "oanda" or broker_type == "forex":
            copy += " Enter Oanda account ID in the first field and API key in the second field."
        elif exchange == "schwab":
            copy += (
                " Schwab uses an OAuth browser sign-in rather than exchange-style API keys. "
                "Enter the App Key / Client ID, your registered redirect URI, and optionally the client secret if your Schwab app requires it. "
                "The final field can pin a specific account hash after account discovery."
            )
            copy += f" Environment: {self._selected_schwab_environment().upper()}."
        elif exchange == "amp":
            copy += (
                " Enter the AMP username and password first. "
                "The extra fields can carry optional AMP API credentials when your endpoint expects them."
            )
        elif exchange == "tradovate":
            copy += (
                " Enter the Tradovate username and password first. "
                "Company ID and security code are only needed on environments that require them."
            )
        elif exchange == "ibkr":
            connection_mode = self._selected_ibkr_connection_mode()
            if connection_mode == "tws":
                copy += (
                    " TWS mode uses the dedicated socket-based IBKR family. "
                    "Host, port, and client ID map to Trader Workstation or IB Gateway directly."
                )
            else:
                copy += (
                    " Web API mode uses the Client Portal / Gateway family. "
                    "Base URL points to the gateway or hosted Web API, while the token field is only needed when your session bootstrap requires it."
                )
            copy += " Use the account field only when you want to force a specific account id or profile."
        self.broker_hint.setText(copy)

    def _set_check_state(self, row, text, is_ready):
        """Set the state label and style of a checklist row."""
        row.state_label.setText(text)
        row.state_label.setObjectName("checkStateGood" if is_ready else "checkStateWarn")
        row.state_label.style().unpolish(row.state_label)
        row.state_label.style().polish(row.state_label)

    def _update_session_preview(self):
        """Update the dashboard session preview and readiness indicators."""
        broker_type = self.exchange_type_box.currentText()
        exchange = self.exchange_box.currentText() or "paper"
        customer_region = self._selected_customer_region()
        mode = self.mode_box.currentText()
        schema = self._credential_field_schema()
        market_type = str(self.market_type_box.currentData() or "auto").upper()
        strategy = "Auto per-symbol assignment"
        risk_value = self.risk_input.value()
        ibkr_transport = self._selected_ibkr_connection_mode() if exchange == "ibkr" else None

        is_paper = broker_type == "paper" or exchange == "paper" or mode == "paper"
        needs_credentials = exchange != "paper" and broker_type != "paper"

        resolved = self._resolved_broker_inputs()
        required_fields = tuple(schema.get("required_fields") or ())
        if exchange == "solana":
            solana_values = self._solana_field_values()
            credentials_ready = True if is_paper else self._solana_live_execution_ready()
            has_optional_account = bool(solana_values["rpc_url"] or solana_values["okx_project_id"])
        else:
            credentials_ready = not needs_credentials or all(
                self._schema_field_has_value(schema, resolved, field_name)
                for field_name in required_fields
            )
            has_optional_account = bool(self._dashboard_field_values(schema).get("account"))

        readiness = 20
        readiness += 20 if exchange else 0
        readiness += 15 if mode else 0
        readiness += 15 if risk_value <= 3 else 8
        readiness += 20 if credentials_ready else 0
        readiness += 10 if (not schema.get("show_account") or has_optional_account) else 0
        readiness = max(0, min(100, readiness))

        session_label = "Paper" if is_paper else "Live"
        market_reach = {
            "crypto": "Crypto Desk",
            "forex": "FX Desk",
            "stocks": "Equity Desk",
            "options": "Options Desk",
            "futures": "Futures Desk",
            "derivatives": "Derivatives Desk",
            "paper": "Paper Desk",
        }.get(broker_type, "Multi-Asset")

        self.session_pill_value.setText(session_label)
        self.readiness_pill_value.setText(f"{readiness}%")
        self.market_pill_value.setText(market_reach)
        self.workspace_pill_value.setText("OPEN")
        self.workspace_status_label.setText("Workspace access is enabled for all active sessions.")

        venue_label = exchange.upper() if exchange else "PAPER"
        strategy_copy = "The system ranks strategies per symbol after launch, and terminal users can still override assignments when needed."
        mode_copy = "paper rehearsal" if is_paper else "live execution"

        self.market_primary.body_label.setText(
            f"{venue_label} selected with {mode_copy} framing and {customer_region.upper()} customer routing."
        )
        self.market_secondary.body_label.setText(f"{strategy}. {strategy_copy}")
        self.market_tertiary.body_label.setText(
            f"Risk budget is {risk_value}%. Venue {market_type}. Profiles are {'saved' if self.remember_checkbox.isChecked() else 'temporary'} for this session."
        )

        broker_ready = bool(exchange)
        strategy_ready = True
        risk_ready = risk_value <= 3

        self._set_check_state(self.check_credentials, "Ready" if credentials_ready else "Needs input", credentials_ready)
        self._set_check_state(self.check_broker, "Ready" if broker_ready else "Choose venue", broker_ready)
        self._set_check_state(self.check_strategy, "Auto or terminal-managed", strategy_ready)
        self._set_check_state(self.check_risk, "Conservative" if risk_ready else "Aggressive", risk_ready)

        if is_paper:
            self.summary_title.setText("Paper desk ready")
            self.summary_body.setText(
                "This setup is optimized for a safer rehearsal. You can validate the broker shape, charts, and automatic strategy routing before taking live risk."
            )
            self.quick_launch_title.setText("Quick Launch")
            self.quick_launch_body.setText(
                "Paper mode is ready for a fast terminal launch. Use the launch button here instead of scrolling through the full configuration stack."
            )
            if exchange == "schwab":
                self.connect_button.setText("Sign In With Schwab")
            else:
                self.connect_button.setText("Open Paper Terminal")
            self.live_guard_checkbox.setVisible(False)
            self.live_guard_checkbox.setChecked(False)
        else:
            self.summary_title.setText(f"{venue_label} live launch")
            self.summary_body.setText(
                "This session is configured for live execution. Review credentials, account details, and risk posture before entering the terminal. Strategy assignment will happen automatically per symbol after launch."
            )
            self.quick_launch_title.setText(f"{venue_label} live launch")
            self.quick_launch_body.setText(
                "The terminal can open from the top of the dashboard once credentials and live-order confirmation are in place."
            )
            if exchange == "schwab":
                self.connect_button.setText("Sign In With Schwab")
            else:
                self.connect_button.setText("Launch Live Trading Terminal")
            self.live_guard_checkbox.setVisible(True)
            self.live_guard_checkbox.setText(
                f"I understand {venue_label} can place live orders on this account."
            )

        profile_state = self.saved_account_box.currentText()
        profile_copy = profile_state if profile_state and profile_state != "Recent profiles" else "Profile not saved yet"
        transport_copy = f"  |  IBKR {ibkr_transport.upper()}" if ibkr_transport else ""
        self.summary_meta.setText(f"Risk {risk_value}%  |  Strategy Auto per symbol{transport_copy}  |  {profile_copy}")
        self.quick_launch_meta.setText(
            f"{session_label}  |  {venue_label}  |  Risk {risk_value}%  |  {profile_copy}"
        )
        self.quick_launch_button.setText(self.connect_button.text())

    def _confirm_live_launch(self, exchange, account_id):
        """Request explicit user confirmation before allowing live trading launch."""
        confirmation = QMessageBox.question(
            self,
            "Confirm Live Trading",
            (
                f"You are about to open a LIVE trading session for {str(exchange or '').upper() or 'the selected broker'}.\n\n"
                f"Account: {account_id or 'Not set'}\n"
                "Mode: LIVE\n\n"
                "Use paper mode whenever you are testing a new strategy or broker path.\n"
                "Continue only if you intend to allow real orders."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return False

        typed, ok = QInputDialog.getText(
            self,
            "Type LIVE To Continue",
            "Type LIVE to confirm this real-money session:",
        )
        return bool(ok and str(typed).strip().upper() == "LIVE")

    def _sync_shell_layout(self):
        """Switch layout orientation based on window width for responsive behavior."""
        is_compact = self.width() < 1220
        desired_mode = QBoxLayout.TopToBottom if is_compact else QBoxLayout.LeftToRight
        if desired_mode == self._current_layout_mode:
            return

        self._current_layout_mode = desired_mode
        self.shell_layout.setDirection(desired_mode)

        if is_compact:
            self.hero_panel.setMinimumWidth(0)
            self.connect_panel.setMaximumWidth(16777215)
        else:
            self.hero_panel.setMinimumWidth(540)
            self.connect_panel.setMaximumWidth(520)

    def resizeEvent(self, event):
        """Handle resize events to reflow layout responsively."""
        super().resizeEvent(event)
        self._sync_shell_layout()

    def _on_connect(self):
        """Validate input and emit login request when connecting the session."""
        exchange = self.exchange_box.currentText()
        broker_type = self.exchange_type_box.currentText()
        customer_region = self._selected_customer_region()
        schema = self._credential_field_schema()
        resolved = self._resolved_broker_inputs()
        api_key = resolved.get("api_key")
        secret = resolved.get("secret")
        password = resolved.get("password")
        account_id = resolved.get("account_id")

        missing_fields = []
        if exchange != "paper" and broker_type != "paper":
            for field_name in tuple(schema.get("required_fields") or ()):
                if not self._schema_field_has_value(schema, resolved, field_name):
                    missing_fields.append(field_name)
        if missing_fields:
            missing_label = schema.get(self._schema_label_key(missing_fields[0]), "Credential")
            QMessageBox.warning(
                self,
                "Missing Credentials",
                f"{missing_label} is required for this broker session.",
            )
            return
        if exchange in {"binance", "binanceus"} and api_key and any(ch.isspace() for ch in api_key):
            QMessageBox.warning(
                self,
                "Invalid API Key",
                "The Binance API key contains spaces or line breaks. Paste the key exactly as issued by the exchange.",
            )
            return
        if exchange in {"binance", "binanceus"} and secret and any(ch.isspace() for ch in secret):
            QMessageBox.warning(
                self,
                "Invalid Secret",
                "The Binance secret contains spaces or line breaks. Paste the secret exactly as issued by the exchange.",
            )
            return
        if exchange == "coinbase":
            coinbase_error = self._coinbase_validation_error(api_key, secret, password=password)
            if coinbase_error:
                QMessageBox.warning(
                    self,
                    "Invalid Coinbase Credentials",
                    coinbase_error,
                )
                return
        if exchange == "solana":
            solana_values = self._solana_field_values()
            okx_labels = {
                "OKX API Key": solana_values["okx_api_key"],
                "OKX Secret": solana_values["okx_secret_key"],
                "OKX Passphrase": solana_values["okx_passphrase"],
            }
            if any(okx_labels.values()) and not self._solana_okx_credentials_complete():
                missing_okx = [label for label, value in okx_labels.items() if not str(value or "").strip()]
                QMessageBox.warning(
                    self,
                    "Incomplete OKX Trade API Credentials",
                    "Complete the OKX API key, secret, and passphrase fields together.\n\n"
                    f"Missing: {', '.join(missing_okx)}",
                )
                return
            if self.mode_box.currentText() == "live":
                if not solana_values["wallet_address"] or not solana_values["private_key"]:
                    QMessageBox.warning(
                        self,
                        "Missing Solana Signer",
                        "Live Solana sessions require both a wallet address and matching private key in the Solana routing panel.",
                    )
                    return
                if not (self._solana_okx_credentials_complete() or solana_values["jupiter_api_key"]):
                    QMessageBox.warning(
                        self,
                        "Missing Solana Route Credentials",
                        "Provide either the full OKX Trade API credential set or a legacy Jupiter API key before launching live Solana trading.",
                    )
                    return
        if broker_type == "crypto" and exchange == "binance" and customer_region == "us":
            QMessageBox.warning(
                self,
                "Binance Jurisdiction",
                "Binance.com is not available for US customers. Switch the customer region to Outside US or use Binance US.",
            )
            return
        if broker_type == "crypto" and exchange == "binanceus" and customer_region != "us":
            QMessageBox.warning(
                self,
                "Binance US Jurisdiction",
                "Binance US is only available for US customers. Switch the customer region to US or choose Binance for non-US customers.",
            )
            return
        if self.mode_box.currentText() == "live" and exchange != "paper" and broker_type != "paper":
            if not self.live_guard_checkbox.isChecked():
                QMessageBox.warning(
                    self,
                    "Live Safety Check",
                    "Tick the live-order acknowledgement before launching a live session.",
                )
                return
            if not self._confirm_live_launch(exchange, account_id):
                QMessageBox.information(
                    self,
                    "Live Session Canceled",
                    "Live launch canceled. The terminal was not opened.",
                )
                return

        broker_options = dict(resolved.get("options") or {})
        broker_options.update(
            {
                "market_type": str(self.market_type_box.currentData() or "auto"),
                "customer_region": customer_region,
                "candle_price_component": str(
                    getattr(self.controller, "forex_candle_price_component", "bid") or "bid"
                ).strip().lower(),
            }
        )
        if exchange == "coinbase" and str(broker_options.get("market_type") or "").strip().lower() == "derivative":
            broker_options.setdefault("defaultSubType", "future")
        if exchange == "schwab":
            selected_profile = str(self.saved_account_box.currentText() or "").strip()
            if not selected_profile or selected_profile == self._tr("dashboard.recent_profiles"):
                selected_profile = f"schwab_{re.sub(r'[^A-Za-z0-9_.-]+', '_', str(account_id or api_key or 'profile'))[:24]}"
            broker_options["profile_name"] = selected_profile
        if exchange == "ibkr":
            broker_options["connection_mode"] = self._selected_ibkr_connection_mode()
            broker_options["environment"] = self._selected_ibkr_environment()
            broker_options["paper"] = (
                self.mode_box.currentText() != "live"
                if broker_options["connection_mode"] == "tws"
                else False
            )
        broker_config = BrokerConfig(
            type=broker_type,
            exchange=exchange,
            customer_region=customer_region,
            mode=self.mode_box.currentText(),
            api_key=api_key,
            secret=secret,
            password=password or None,
            account_id=account_id or None,
            options=broker_options,
        )

        config = AppConfig(
            broker=broker_config,
            risk=RiskConfig(risk_percent=self.risk_input.value()),
            system=SystemConfig(),
            strategy=str(getattr(self.controller, "strategy_name", "Trend Following") or "Trend Following"),
        )

        if self.remember_checkbox.isChecked():
            profile_seed = "paper"
            for candidate in (
                broker_options.get("host"),
                broker_options.get("base_url"),
                broker_options.get("username"),
                broker_options.get("wallet_address"),
                broker_options.get("okx_api_key"),
                account_id,
                api_key,
                broker_options.get("account_hash"),
            ):
                candidate_text = str(candidate or "").strip()
                if candidate_text:
                    profile_seed = re.sub(r"[^A-Za-z0-9_.-]+", "_", candidate_text)
                    break
            profile_name = f"{exchange}_{profile_seed[:6]}"
            broker_options["profile_name"] = profile_name
            payload = config.model_dump() if hasattr(config, "model_dump") else config.dict()
            CredentialManager.save_account(profile_name, payload)
            self.settings.setValue(self.LAST_PROFILE_SETTING, profile_name)
            self._load_accounts_index()
            self.saved_account_box.setCurrentText(profile_name)

        sync_profile = self._persist_platform_sync_profile()
        if bool(sync_profile.get("sync_enabled")):
            self._request_workspace_push(interactive=False)

        self.create_session(exchange, config)

    def create_session(self, exchange_name, config):
        _ = exchange_name
        self.show_loading()
        self.login_requested.emit(config)

    def refresh_active_sessions(self):
        controller = getattr(self, "controller", None)
        if controller is None or not hasattr(controller, "list_trading_sessions"):
            return
        try:
            sessions = list(controller.list_trading_sessions() or [])
        except Exception:
            sessions = []

        self.active_session_box.blockSignals(True)
        self.active_session_box.clear()
        if not sessions:
            self.active_session_box.addItem("No active sessions", "")
            self.active_sessions_summary.setText("No sessions connected yet.")
            self.activate_session_button.setEnabled(False)
            self.start_session_button.setEnabled(False)
            self.stop_session_button.setEnabled(False)
            self.destroy_session_button.setEnabled(False)
            self.active_session_box.blockSignals(False)
            return

        aggregate = {}
        if hasattr(controller, "aggregate_session_portfolio"):
            try:
                aggregate = dict(controller.aggregate_session_portfolio() or {})
            except Exception:
                aggregate = {}

        active_session_id = ""
        summary_lines = []
        for session in sessions:
            session_id = str(session.get("session_id") or "").strip()
            label = str(session.get("label") or session_id or "Session").strip()
            status = str(session.get("status") or "unknown").upper()
            self.active_session_box.addItem(f"{label} [{status}]", session_id)
            summary_lines.append(
                f"{label}: {status}, equity {float(session.get('equity') or 0.0):,.2f}, "
                f"positions {int(session.get('positions_count') or 0)}, orders {int(session.get('open_orders_count') or 0)}."
            )
            if session.get("active"):
                active_session_id = session_id

        if active_session_id:
            index = self.active_session_box.findData(active_session_id)
            if index >= 0:
                self.active_session_box.setCurrentIndex(index)
        aggregate_summary = (
            f"{int(aggregate.get('session_count') or len(sessions))} sessions"
            f" | running {int(aggregate.get('running_sessions') or 0)}"
            f" | equity {float(aggregate.get('total_equity') or 0.0):,.2f}"
            f" | exposure {float(aggregate.get('total_gross_exposure') or 0.0):,.2f}"
            f" | unrealized PnL {float(aggregate.get('total_unrealized_pnl') or 0.0):,.2f}"
        )
        details = " ".join(summary_lines[:3])
        self.active_sessions_summary.setText(f"{aggregate_summary}. {details}".strip())
        self.activate_session_button.setEnabled(True)
        self.start_session_button.setEnabled(True)
        self.stop_session_button.setEnabled(True)
        self.destroy_session_button.setEnabled(True)
        self.active_session_box.blockSignals(False)

    def _selected_session_id(self):
        return str(self.active_session_box.currentData() or "").strip()

    def _activate_selected_session(self):
        session_id = self._selected_session_id()
        controller = getattr(self, "controller", None)
        if session_id and controller is not None and hasattr(controller, "request_session_activation"):
            controller.request_session_activation(session_id)

    def _start_selected_session(self):
        session_id = self._selected_session_id()
        controller = getattr(self, "controller", None)
        if session_id and controller is not None and hasattr(controller, "request_session_start"):
            controller.request_session_start(session_id)

    def _stop_selected_session(self):
        session_id = self._selected_session_id()
        controller = getattr(self, "controller", None)
        if session_id and controller is not None and hasattr(controller, "request_session_stop"):
            controller.request_session_stop(session_id)

    def _destroy_selected_session(self):
        session_id = self._selected_session_id()
        controller = getattr(self, "controller", None)
        if session_id and controller is not None and hasattr(controller, "request_session_destroy"):
            controller.request_session_destroy(session_id)

    def show_loading(self):
        """Show loading status while connecting to the trading terminal."""
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting TradeAdviser Session...")
        self.spinner.setVisible(True)
        if self.spinner_movie is not None:
            self.spinner_movie.start()
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.set_loading(
                "Preparing your TradeAdviser trading session...",
                "Authenticating the broker, loading account context, and opening the terminal.",
            )

    def hide_loading(self):
        """Hide loading status and restore the connect button state."""
        self.spinner.setVisible(False)
        if self.spinner_movie is not None:
            self.spinner_movie.stop()
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.clear_loading()
        self.connect_button.setEnabled(True)
        self._update_session_preview()

