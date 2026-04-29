import sys
sys.path.insert(0, "src")

# Test imports
from broker.broker_classification import (
    AssetClass, MarketType, VenueType, BrokerProfile,
    BROKER_PROFILES, get_broker_profile, select_brokers
)
from broker.broker_selector import BrokerSelector, BrokerValidator, route_broker_for_trade

print("? All imports successful")

# Test OANDA US (key requirement)
oanda_us = get_broker_profile("oanda_us")
print(f"? OANDA US profile loaded: {oanda_us.display_name}")
print(f"  - Is MARGIN_FX: {MarketType.MARGIN_FX in oanda_us.market_types}")
print(f"  - Is NOT CFD broker: {not oanda_us.is_cfd_broker}")
print(f"  - Risk engine: {oanda_us.risk_engine_key}")

# Test Coinbase
coinbase = get_broker_profile("coinbase")
print(f"? Coinbase profile loaded: {coinbase.display_name}")
print(f"  - Has SPOT_CRYPTO: {MarketType.SPOT_CRYPTO in coinbase.market_types}")
print(f"  - NOT perpetual: {MarketType.CRYPTO_PERPETUAL not in coinbase.market_types}")

# Test Alpaca
alpaca = get_broker_profile("alpaca")
print(f"? Alpaca profile loaded: {alpaca.display_name}")
print(f"  - Has CASH_STOCK: {MarketType.CASH_STOCK in alpaca.market_types}")
print(f"  - Has fractional: {alpaca.supports_fractional}")
print(f"  - No margin default: {not alpaca.supports_margin}")

# Test selection
forex_brokers = select_brokers(asset_class=AssetClass.FOREX)
print(f"? Selected {len(forex_brokers)} FOREX brokers")

stock_margin_brokers = select_brokers(asset_class=AssetClass.STOCK, requires_margin=True)
print(f"? Selected {len(stock_margin_brokers)} STOCK brokers with margin")

# Test legacy compatibility
legacy = BrokerSelector.get_profile_from_legacy_config(
    exchange="oanda", broker_type="forex", customer_region="US"
)
print(f"? Legacy OANDA config maps to: {legacy.broker_id}")

print("\n? All basic tests passed!")
