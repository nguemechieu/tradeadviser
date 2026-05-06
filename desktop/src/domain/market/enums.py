"""Market classification enums - Core domain model for multi-asset trading platform.

This module defines the fundamental enumeration types used throughout the trading
platform to classify markets, instruments, venues, and trading modes. All enums use
string values (StrEnum) for seamless serialization and logging.

Type hierarchy:
- MarketType: Broad financial category (CRYPTO, FOREX, STOCK, COMMODITY, etc.)
- InstrumentType: Product structure (SPOT, PERPETUAL_FUTURE, OPTION, etc.)
- VenueType: Kind of execution venue (CENTRALIZED_EXCHANGE, BROKER, etc.)
- Venue: Specific broker/exchange/network (COINBASE, BINANCE, ALPACA, etc.)
- AssetClass: Portfolio/risk grouping (CRYPTO_ASSET, EQUITY, DERIVATIVE, etc.)
- TradingMode: Execution environment (LIVE, PAPER, BACKTEST, etc.)
- SettlementType: Settlement mechanism (CASH, CRYPTO, PERPETUAL, etc.)
- MarketDataType: Real-time data feeds (TICKER, TRADE, ORDER_BOOK, etc.)
- MarketRoute: Composite routing rule combining market/instrument/venue types
"""

from enum import StrEnum, Enum
from typing import ClassVar


# ============================================================================
# MARKET TYPE - Broad Financial Category
# ============================================================================

class MarketType(StrEnum):
    """Broad financial market category."""
    
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    COMMODITY = "commodity"
    BOND = "bond"
    FUTURES = "futures"
    OPTIONS = "options"
    CFD = "cfd"
    SYNTHETIC = "synthetic"
    TOKENIZED_ASSET = "tokenized_asset"
    UNKNOWN = "unknown"
    
    @property
    def is_crypto(self) -> bool:
        """True if this is cryptocurrency market."""
        return self == MarketType.CRYPTO
    
    @property
    def is_forex(self) -> bool:
        """True if this is foreign exchange market."""
        return self == MarketType.FOREX
    
    @property
    def is_equity_like(self) -> bool:
        """True if this is equity, ETF, or index (traditional equities)."""
        return self in (MarketType.STOCK, MarketType.ETF, MarketType.INDEX)
    
    @property
    def is_derivative_market(self) -> bool:
        """True if this is derivatives (futures, options, CFD)."""
        return self in (MarketType.FUTURES, MarketType.OPTIONS, MarketType.CFD)
    
    @property
    def is_traditional_market(self) -> bool:
        """True if this is traditional financial market (stocks, bonds, commodities)."""
        return self in (
            MarketType.STOCK,
            MarketType.ETF,
            MarketType.INDEX,
            MarketType.BOND,
            MarketType.COMMODITY,
            MarketType.FOREX,
        )


# ============================================================================
# INSTRUMENT TYPE - Exact Product Structure
# ============================================================================

class InstrumentType(StrEnum):
    """Exact product structure or contract type."""
    
    SPOT = "spot"
    MARGIN_SPOT = "margin_spot"
    FOREX_SPOT = "forex_spot"
    MARGIN_FX = "margin_fx"
    CFD = "cfd"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    FUTURE = "future"
    PERPETUAL_FUTURE = "perpetual_future"
    OPTION = "option"
    WARRANT = "warrant"
    BOND = "bond"
    COMMODITY_SPOT = "commodity_spot"
    TOKENIZED_STOCK = "tokenized_stock"
    TOKENIZED_INDEX = "tokenized_index"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"
    
    @property
    def is_spot(self) -> bool:
        """True if this is a spot/physical settlement instrument."""
        return self in (
            InstrumentType.SPOT,
            InstrumentType.FOREX_SPOT,
            InstrumentType.STOCK,
            InstrumentType.ETF,
            InstrumentType.INDEX,
            InstrumentType.COMMODITY_SPOT,
            InstrumentType.TOKENIZED_STOCK,
            InstrumentType.TOKENIZED_INDEX,
        )
    
    @property
    def is_margin_product(self) -> bool:
        """True if this requires margin/leverage."""
        return self in (
            InstrumentType.MARGIN_SPOT,
            InstrumentType.MARGIN_FX,
            InstrumentType.CFD,
        )
    
    @property
    def is_derivative(self) -> bool:
        """True if this is a derivative (contract-based, not spot)."""
        return self in (
            InstrumentType.PERPETUAL_FUTURE,
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.CFD,
            InstrumentType.WARRANT,
            InstrumentType.MARGIN_SPOT,
            InstrumentType.MARGIN_FX,
        )
    
    @property
    def expires(self) -> bool:
        """True if this instrument has an expiration date."""
        return self in (
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.WARRANT,
        )
    
    @property
    def is_perpetual(self) -> bool:
        """True if this is perpetual (no expiration)."""
        return self in (
            InstrumentType.PERPETUAL_FUTURE,
            InstrumentType.SPOT,
            InstrumentType.MARGIN_SPOT,
            InstrumentType.FOREX_SPOT,
            InstrumentType.MARGIN_FX,
            InstrumentType.CFD,
        )


# ============================================================================
# VENUE TYPE - Kind of Execution Venue
# ============================================================================

class VenueType(StrEnum):
    """Kind of execution venue or market infrastructure."""
    
    CENTRALIZED_EXCHANGE = "centralized_exchange"
    DECENTRALIZED_EXCHANGE = "decentralized_exchange"
    BROKER = "broker"
    BANK_LIQUIDITY_PROVIDER = "bank_liquidity_provider"
    ECN = "ecn"
    BLOCKCHAIN_NETWORK = "blockchain_network"
    OTC_DESK = "otc_desk"
    CLEARING_EXCHANGE = "clearing_exchange"
    SIMULATED = "simulated"
    UNKNOWN = "unknown"
    
    @property
    def is_exchange(self) -> bool:
        """True if this is an exchange (CEX or DEX)."""
        return self in (
            VenueType.CENTRALIZED_EXCHANGE,
            VenueType.DECENTRALIZED_EXCHANGE,
            VenueType.CLEARING_EXCHANGE,
        )
    
    @property
    def is_broker(self) -> bool:
        """True if this is a broker or liquidity provider."""
        return self in (
            VenueType.BROKER,
            VenueType.BANK_LIQUIDITY_PROVIDER,
            VenueType.ECN,
            VenueType.OTC_DESK,
        )
    
    @property
    def is_blockchain_native(self) -> bool:
        """True if this is blockchain-based (DEX or network)."""
        return self in (
            VenueType.DECENTRALIZED_EXCHANGE,
            VenueType.BLOCKCHAIN_NETWORK,
        )
    
    @property
    def requires_account_credentials(self) -> bool:
        """True if this venue requires API key/password credentials."""
        return self in (
            VenueType.CENTRALIZED_EXCHANGE,
            VenueType.BROKER,
            VenueType.BANK_LIQUIDITY_PROVIDER,
            VenueType.ECN,
        )
    
    @property
    def requires_wallet_credentials(self) -> bool:
        """True if this venue requires wallet secret/mnemonic."""
        return self in (
            VenueType.DECENTRALIZED_EXCHANGE,
            VenueType.BLOCKCHAIN_NETWORK,
        )


# ============================================================================
# VENUE - Specific Broker/Exchange/Network
# ============================================================================

class Venue(StrEnum):
    """Specific broker, centralized exchange, DEX, blockchain network, or simulation venue."""
    
    # Centralized crypto exchanges
    COINBASE = "coinbase"
    BINANCE = "binance"
    BINANCE_US = "binance_us"
    KRAKEN = "kraken"
    BYBIT = "bybit"
    OKX = "okx"
    
    # Blockchain networks (DEX-native)
    STELLAR = "stellar"
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    
    # Forex/Fiat brokers
    OANDA = "oanda"
    FOREX_COM = "forex_com"
    
    # Stock brokers
    ALPACA = "alpaca"
    INTERACTIVE_BROKERS = "interactive_brokers"
    SCHWAB = "schwab"
    
    # Simulated/Testing
    PAPER = "paper"
    BACKTEST = "backtest"
    
    UNKNOWN = "unknown"
    
    @property
    def display_name(self) -> str:
        """Human-readable venue name."""
        return Venue._METADATA.get(str(self), {}).get("display_name", str(self))
    
    @property
    def venue_type(self) -> "VenueType":
        """Venue type classification."""
        return Venue._METADATA.get(str(self), {}).get("venue_type", VenueType.UNKNOWN)
    
    @property
    def supports_crypto(self) -> bool:
        """True if venue supports cryptocurrency trading."""
        return Venue._METADATA.get(str(self), {}).get("supports_crypto", False)
    
    @property
    def supports_fiat(self) -> bool:
        """True if venue supports fiat currency trading."""
        return Venue._METADATA.get(str(self), {}).get("supports_fiat", False)
    
    @property
    def supports_derivatives(self) -> bool:
        """True if venue supports derivatives (futures, perpetuals, options)."""
        return Venue._METADATA.get(str(self), {}).get("supports_derivatives", False)
    
    @property
    def is_broker(self) -> bool:
        """True if this is a broker (not an exchange)."""
        return self.venue_type == VenueType.BROKER
    
    @property
    def is_centralized_exchange(self) -> bool:
        """True if this is a centralized exchange."""
        return self.venue_type == VenueType.CENTRALIZED_EXCHANGE
    
    @property
    def is_blockchain_network(self) -> bool:
        """True if this is a blockchain network."""
        return self.venue_type == VenueType.BLOCKCHAIN_NETWORK
    
    @property
    def is_simulated(self) -> bool:
        """True if this is paper trading or backtest."""
        return self.venue_type == VenueType.SIMULATED


# Metadata: display name and venue characteristics
# Assign metadata after enum creation to avoid Python enum parsing issues
Venue._METADATA = {
    "coinbase": {
        "display_name": "Coinbase",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "binance": {
        "display_name": "Binance",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "binance_us": {
        "display_name": "Binance US",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": False,
    },
    "kraken": {
        "display_name": "Kraken",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "bybit": {
        "display_name": "Bybit",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": False,
        "supports_derivatives": True,
    },
    "okx": {
        "display_name": "OKX",
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "stellar": {
        "display_name": "Stellar",
        "venue_type": VenueType.BLOCKCHAIN_NETWORK,
        "supports_crypto": True,
        "supports_fiat": False,
        "supports_derivatives": False,
    },
    "ethereum": {
        "display_name": "Ethereum",
        "venue_type": VenueType.BLOCKCHAIN_NETWORK,
        "supports_crypto": True,
        "supports_fiat": False,
        "supports_derivatives": False,
    },
    "solana": {
        "display_name": "Solana",
        "venue_type": VenueType.BLOCKCHAIN_NETWORK,
        "supports_crypto": True,
        "supports_fiat": False,
        "supports_derivatives": False,
    },
    "oanda": {
        "display_name": "OANDA",
        "venue_type": VenueType.BROKER,
        "supports_crypto": False,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "forex_com": {
        "display_name": "Forex.com",
        "venue_type": VenueType.BROKER,
        "supports_crypto": False,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "alpaca": {
        "display_name": "Alpaca",
        "venue_type": VenueType.BROKER,
        "supports_crypto": False,
        "supports_fiat": True,
        "supports_derivatives": False,
    },
    "interactive_brokers": {
        "display_name": "Interactive Brokers",
        "venue_type": VenueType.BROKER,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "schwab": {
        "display_name": "Charles Schwab",
        "venue_type": VenueType.BROKER,
        "supports_crypto": False,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "paper": {
        "display_name": "Paper Trading",
        "venue_type": VenueType.SIMULATED,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "backtest": {
        "display_name": "Backtest",
        "venue_type": VenueType.SIMULATED,
        "supports_crypto": True,
        "supports_fiat": True,
        "supports_derivatives": True,
    },
    "unknown": {
        "display_name": "Unknown",
        "venue_type": VenueType.UNKNOWN,
        "supports_crypto": False,
        "supports_fiat": False,
        "supports_derivatives": False,
    },
}



# ============================================================================
# ASSET CLASS - Portfolio/Risk Grouping
# ============================================================================

class AssetClass(StrEnum):
    """Asset class for portfolio and risk grouping."""
    
    CRYPTO_ASSET = "crypto_asset"
    FIAT_CURRENCY = "fiat_currency"
    EQUITY = "equity"
    EQUITY_INDEX = "equity_index"
    COMMODITY = "commodity"
    FIXED_INCOME = "fixed_income"
    DERIVATIVE = "derivative"
    CASH = "cash"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"
    
    @property
    def is_risk_asset(self) -> bool:
        """True if this is a risky asset (not cash or derivatives)."""
        return self in (
            AssetClass.CRYPTO_ASSET,
            AssetClass.EQUITY,
            AssetClass.EQUITY_INDEX,
            AssetClass.COMMODITY,
            AssetClass.FIXED_INCOME,
        )
    
    @property
    def is_cash_like(self) -> bool:
        """True if this is cash or cash-like (low volatility)."""
        return self in (AssetClass.CASH, AssetClass.FIAT_CURRENCY)


# ============================================================================
# TRADING MODE - Execution Environment
# ============================================================================

class TradingMode(StrEnum):
    """Trading mode or execution environment."""
    
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"
    FORWARD_TEST = "forward_test"
    SIMULATION = "simulation"
    SANDBOX = "sandbox"
    
    @property
    def sends_real_orders(self) -> bool:
        """True if this mode actually sends real orders to venues."""
        return self == TradingMode.LIVE
    
    @property
    def is_test_mode(self) -> bool:
        """True if this is a testing/simulation mode (not live)."""
        return self != TradingMode.LIVE


# ============================================================================
# SETTLEMENT TYPE - Settlement Mechanism
# ============================================================================

class SettlementType(StrEnum):
    """Settlement mechanism for trades."""
    
    PHYSICAL = "physical"
    CASH = "cash"
    CRYPTO = "crypto"
    FIAT = "fiat"
    STABLECOIN = "stablecoin"
    PERPETUAL = "perpetual"
    NONE = "none"
    UNKNOWN = "unknown"
    
    @property
    def has_settlement(self) -> bool:
        """True if this type involves actual settlement."""
        return self in (
            SettlementType.PHYSICAL,
            SettlementType.CASH,
            SettlementType.CRYPTO,
            SettlementType.FIAT,
            SettlementType.STABLECOIN,
        )
    
    @property
    def is_cash_settled(self) -> bool:
        """True if this settles in cash/fiat (not physical/crypto)."""
        return self in (SettlementType.CASH, SettlementType.FIAT)
    
    @property
    def is_perpetual(self) -> bool:
        """True if this is perpetual (no settlement date)."""
        return self == SettlementType.PERPETUAL


# ============================================================================
# MARKET DATA TYPE - Real-Time Data Feeds
# ============================================================================

class MarketDataType(StrEnum):
    """Real-time market data feed types."""
    
    TICKER = "ticker"
    QUOTE = "quote"
    TRADE = "trade"
    ORDER_BOOK = "order_book"
    CANDLE = "candle"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LIQUIDATION = "liquidation"
    NEWS = "news"
    ECONOMIC_CALENDAR = "economic_calendar"
    UNKNOWN = "unknown"
    
    @property
    def is_realtime_price_data(self) -> bool:
        """True if this is real-time price data (ticker, quote, trade, candle)."""
        return self in (
            MarketDataType.TICKER,
            MarketDataType.QUOTE,
            MarketDataType.TRADE,
            MarketDataType.CANDLE,
        )
    
    @property
    def is_derivative_data(self) -> bool:
        """True if this is derivative-specific data."""
        return self in (
            MarketDataType.FUNDING_RATE,
            MarketDataType.OPEN_INTEREST,
            MarketDataType.LIQUIDATION,
        )


# ============================================================================
# MARKET ROUTE - Composite Routing Rule
# ============================================================================

class MarketRoute(StrEnum):
    """Composite routing rule mapping market type + instrument type + venue type."""
    
    CRYPTO_SPOT_CEX = "crypto_spot_cex"
    CRYPTO_SPOT_DEX = "crypto_spot_dex"
    CRYPTO_PERPETUAL_CEX = "crypto_perpetual_cex"
    CRYPTO_PERPETUAL_DEX = "crypto_perpetual_dex"
    CRYPTO_NETWORK_SWAP = "crypto_network_swap"
    FOREX_MARGIN_BROKER = "forex_margin_broker"
    STOCK_BROKER = "stock_broker"
    STOCK_MARGIN_BROKER = "stock_margin_broker"
    ETF_BROKER = "etf_broker"
    INDEX_CFD_BROKER = "index_cfd_broker"
    FUTURES_EXCHANGE = "futures_exchange"
    OPTIONS_BROKER = "options_broker"
    COMMODITY_CFD_BROKER = "commodity_cfd_broker"
    PAPER_ROUTE = "paper_route"
    BACKTEST_ROUTE = "backtest_route"
    UNKNOWN_ROUTE = "unknown_route"
    
    @property
    def market_type(self) -> MarketType:
        """Market type for this route."""
        route_key = str(self)
        return MarketRoute._ROUTES.get(route_key, {}).get("market_type", MarketType.UNKNOWN)
    
    @property
    def instrument_type(self) -> InstrumentType:
        """Instrument type for this route."""
        route_key = str(self)
        return MarketRoute._ROUTES.get(route_key, {}).get("instrument_type", InstrumentType.UNKNOWN)
    
    @property
    def venue_type(self) -> VenueType:
        """Venue type for this route."""
        route_key = str(self)
        return MarketRoute._ROUTES.get(route_key, {}).get("venue_type", VenueType.UNKNOWN)
    
    @classmethod
    def matches(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
        venue_type: VenueType,
    ) -> bool:
        """Check if this route matches the given combination."""
        for route in cls:
            if (
                route.market_type == market_type
                and route.instrument_type == instrument_type
                and route.venue_type == venue_type
            ):
                return True
        return False
    
    @classmethod
    def resolve(
        cls,
        market_type: MarketType,
        instrument_type: InstrumentType,
        venue_type: VenueType,
    ) -> "MarketRoute":
        """Resolve a market route from market/instrument/venue types.
        
        Returns UNKNOWN_ROUTE if no exact match is found.
        """
        for route in cls:
            if (
                route.market_type == market_type
                and route.instrument_type == instrument_type
                and route.venue_type == venue_type
            ):
                return route
        return cls.UNKNOWN_ROUTE


# Route metadata: market type, instrument type, venue type combinations
# Assign after enum creation to avoid Python enum parsing issues
MarketRoute._ROUTES = {
    "crypto_spot_cex": {
        "market_type": MarketType.CRYPTO,
        "instrument_type": InstrumentType.SPOT,
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
    },
    "crypto_spot_dex": {
        "market_type": MarketType.CRYPTO,
        "instrument_type": InstrumentType.SPOT,
        "venue_type": VenueType.DECENTRALIZED_EXCHANGE,
    },
    "crypto_perpetual_cex": {
        "market_type": MarketType.CRYPTO,
        "instrument_type": InstrumentType.PERPETUAL_FUTURE,
        "venue_type": VenueType.CENTRALIZED_EXCHANGE,
    },
    "crypto_perpetual_dex": {
        "market_type": MarketType.CRYPTO,
        "instrument_type": InstrumentType.PERPETUAL_FUTURE,
        "venue_type": VenueType.DECENTRALIZED_EXCHANGE,
    },
    "crypto_network_swap": {
        "market_type": MarketType.CRYPTO,
        "instrument_type": InstrumentType.SPOT,
        "venue_type": VenueType.BLOCKCHAIN_NETWORK,
    },
    "forex_margin_broker": {
        "market_type": MarketType.FOREX,
        "instrument_type": InstrumentType.MARGIN_FX,
        "venue_type": VenueType.BROKER,
    },
    "stock_broker": {
        "market_type": MarketType.STOCK,
        "instrument_type": InstrumentType.STOCK,
        "venue_type": VenueType.BROKER,
    },
    "stock_margin_broker": {
        "market_type": MarketType.STOCK,
        "instrument_type": InstrumentType.MARGIN_SPOT,
        "venue_type": VenueType.BROKER,
    },
    "etf_broker": {
        "market_type": MarketType.ETF,
        "instrument_type": InstrumentType.ETF,
        "venue_type": VenueType.BROKER,
    },
    "index_cfd_broker": {
        "market_type": MarketType.INDEX,
        "instrument_type": InstrumentType.CFD,
        "venue_type": VenueType.BROKER,
    },
    "futures_exchange": {
        "market_type": MarketType.FUTURES,
        "instrument_type": InstrumentType.FUTURE,
        "venue_type": VenueType.CLEARING_EXCHANGE,
    },
    "options_broker": {
        "market_type": MarketType.OPTIONS,
        "instrument_type": InstrumentType.OPTION,
        "venue_type": VenueType.BROKER,
    },
    "commodity_cfd_broker": {
        "market_type": MarketType.COMMODITY,
        "instrument_type": InstrumentType.CFD,
        "venue_type": VenueType.BROKER,
    },
    "paper_route": {
        "market_type": MarketType.UNKNOWN,
        "instrument_type": InstrumentType.UNKNOWN,
        "venue_type": VenueType.SIMULATED,
    },
    "backtest_route": {
        "market_type": MarketType.UNKNOWN,
        "instrument_type": InstrumentType.UNKNOWN,
        "venue_type": VenueType.SIMULATED,
    },
    "unknown_route": {
        "market_type": MarketType.UNKNOWN,
        "instrument_type": InstrumentType.UNKNOWN,
        "venue_type": VenueType.UNKNOWN,
    },
}

