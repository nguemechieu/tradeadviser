SPOT_ONLY_EXCHANGES = {"binanceus"}

MARKET_VENUE_CHOICES = [
    ("Auto", "auto"),
    ("Spot", "spot"),
    ("Derivative", "derivative"),
    ("Options", "option"),
    ("OTC", "otc"),
]

VALID_MARKET_VENUES = {value for _label, value in MARKET_VENUE_CHOICES}


def normalize_market_venue(value, default="auto"):
    normalized = str(value or default).strip().lower() or default
    if normalized not in VALID_MARKET_VENUES:
        return default
    return normalized


def market_venue_to_market_types(venue_key):
    """Map market venue preference to list of possible MarketType values.
    
    Args:
        venue_key: Market venue key from MARKET_VENUE_CHOICES ("spot", "derivative", etc.)
    
    Returns:
        List of MarketType strings that could apply to this venue
    """
    from contracts.enums import MarketType
    
    mapping = {
        "auto": [
            MarketType.SPOT.value,
            MarketType.FUTURES.value,
            MarketType.PERPS.value,
            MarketType.STOCKS.value,
            MarketType.INDICES.value,
            MarketType.COMMODITIES.value,
        ],
        "spot": [MarketType.SPOT.value, MarketType.STOCKS.value],
        "derivative": [
            MarketType.FUTURES.value,
            MarketType.PERPS.value,
            MarketType.INDICES.value,
            MarketType.COMMODITIES.value,
        ],
        "option": [MarketType.FUTURES.value],  # Options are treated as derivative futures
        "otc": [MarketType.SPOT.value],
    }
    
    return mapping.get(venue_key, mapping["auto"])


def supported_market_venues_for_profile(broker_type=None, exchange=None):
    normalized_type = str(broker_type or "").strip().lower()
    normalized_exchange = str(exchange or "").strip().lower()

    if normalized_exchange in {"schwab", "tdameritrade"}:
        return ["auto", "option"]

    if normalized_exchange in {"ib", "ibkr", "interactivebrokers", "interactive_brokers"}:
        return ["auto", "spot", "derivative", "option"]

    if normalized_exchange in {"amp", "ampfutures", "tradovate"}:
        return ["auto", "derivative"]

    if normalized_exchange == "coinbase":
        return ["auto", "spot", "derivative"]

    if normalized_exchange in SPOT_ONLY_EXCHANGES:
        return ["auto", "spot"]

    if normalized_exchange in {"stellar", "solana"}:
        return ["auto", "spot"]

    if normalized_type == "forex" or normalized_exchange == "oanda":
        return ["auto", "otc"]

    if normalized_type == "stocks" or normalized_exchange == "alpaca":
        return ["auto", "spot"]

    if normalized_type == "options":
        return ["auto", "option"]

    if normalized_type == "futures":
        return ["auto", "derivative"]

    if normalized_type == "derivatives":
        return ["auto", "derivative", "option"]

    if normalized_type == "paper" or normalized_exchange == "paper":
        return ["auto", "spot", "derivative", "option", "otc"]

    if normalized_type == "crypto":
        return ["auto", "spot", "derivative", "option"]

    return ["auto", "spot"]
