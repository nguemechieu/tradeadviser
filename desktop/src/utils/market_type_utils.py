"""Market type detection and utilities.

Provides functions to determine market type based on venue, asset class,
and instrument metadata.
"""

from contracts.enums import AssetClass, MarketType, VenueKind


def detect_market_type(
    venue: VenueKind,
    asset_class: AssetClass = AssetClass.UNKNOWN,
    symbol: str | None = None,
    metadata: dict | None = None,
) -> MarketType:
    """Detect market type based on venue, asset class, and metadata.

    Args:
        venue: The trading venue/exchange
        asset_class: The asset class of the instrument
        symbol: The instrument symbol (for heuristic detection)
        metadata: Instrument metadata that may contain market type hints

    Returns:
        The detected MarketType
    """
    if metadata is None:
        metadata = {}

    # Check for explicit market type in metadata
    if "market_type" in metadata:
        try:
            return MarketType(metadata["market_type"])
        except (ValueError, KeyError):
            pass

    # Detect based on asset class
    if asset_class == AssetClass.FUTURE:
        # Determine if it's a future or perpetual
        if "perpetual" in metadata or "perp" in (symbol or "").lower():
            return MarketType.PERPS
        return MarketType.FUTURES

    elif asset_class == AssetClass.EQUITY:
        return MarketType.STOCKS

    elif asset_class == AssetClass.INDEX:
        return MarketType.INDICES

    elif asset_class == AssetClass.OPTION:
        # Options could be futures-based
        if "perpetual" in metadata or "perp" in (symbol or "").lower():
            return MarketType.PERPS
        return MarketType.FUTURES

    elif asset_class == AssetClass.CRYPTO:
        # Crypto can be spot or perpetual
        if "perpetual" in metadata or "perp" in (symbol or "").lower():
            return MarketType.PERPS
        return MarketType.SPOT

    elif asset_class == AssetClass.FOREX:
        # Forex typically trades spot (immediate settlement) or futures
        if "perpetual" in metadata or "perp" in (symbol or "").lower():
            return MarketType.PERPS
        if "futures" in metadata or "future" in (symbol or "").lower():
            return MarketType.FUTURES
        return MarketType.SPOT

    # Venue-specific heuristics
    if venue == VenueKind.COINBASE:
        # Coinbase has spot, stocks, and perpetual (perps) products
        if "perp" in (symbol or "").lower() or "perpetual" in metadata:
            return MarketType.PERPS
        if asset_class == AssetClass.EQUITY:
            return MarketType.STOCKS
        return MarketType.SPOT

    elif venue == VenueKind.BINANCE:
        # Binance has spot, futures, and perps
        if "perp" in (symbol or "").lower() or "perpetual" in metadata:
            return MarketType.PERPS
        if "future" in (symbol or "").lower() or "futures" in metadata:
            return MarketType.FUTURES
        return MarketType.SPOT

    elif venue == VenueKind.IBKR:
        # IBKR has stocks, options, futures, and derivatives
        if "option" in metadata or asset_class == AssetClass.OPTION:
            return MarketType.FUTURES
        if "future" in (symbol or "").lower() or asset_class == AssetClass.FUTURE:
            return MarketType.FUTURES
        if asset_class == AssetClass.EQUITY:
            return MarketType.STOCKS
        # Default to stocks for IBKR if asset class is unknown
        if asset_class == AssetClass.UNKNOWN:
            return MarketType.STOCKS
        return MarketType.STOCKS

    elif venue == VenueKind.ALPACA:
        # Alpaca primarily stocks
        return MarketType.STOCKS

    elif venue == VenueKind.SCHWAB:
        # Schwab stocks and options
        if asset_class == AssetClass.OPTION:
            return MarketType.FUTURES  # Options are treated as derivatives/futures
        return MarketType.STOCKS

    elif venue == VenueKind.OANDA:
        # OANDA forex and spot CFDs
        if "perpetual" in metadata or "perp" in (symbol or "").lower():
            return MarketType.PERPS
        return MarketType.SPOT

    elif venue == VenueKind.PAPER:
        # Paper trading can be any type; infer from asset class
        if asset_class == AssetClass.FUTURE:
            if "perpetual" in metadata or "perp" in (symbol or "").lower():
                return MarketType.PERPS
            return MarketType.FUTURES
        elif asset_class == AssetClass.EQUITY:
            return MarketType.STOCKS
        elif asset_class == AssetClass.INDEX:
            return MarketType.INDICES
        return MarketType.SPOT

    # Default fallback
    return MarketType.UNKNOWN


def get_market_type_display_name(market_type: MarketType) -> str:
    """Get a user-friendly display name for a market type.

    Args:
        market_type: The market type to display

    Returns:
        A human-readable display name
    """
    display_names = {
        MarketType.SPOT: "Spot",
        MarketType.FUTURES: "Futures",
        MarketType.PERPS: "Perpetuals",
        MarketType.STOCKS: "Stocks",
        MarketType.INDICES: "Indices",
        MarketType.COMMODITIES: "Commodities",
        MarketType.UNKNOWN: "Unknown",
    }
    return display_names.get(market_type, market_type.value)
