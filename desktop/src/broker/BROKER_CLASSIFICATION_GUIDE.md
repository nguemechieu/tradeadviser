"""Broker Classification System - Integration Guide

This guide explains how to use the new broker classification system in your trading app.

## Overview

The broker classification system provides:
1. **Asset Class Classification**: FOREX, CRYPTO, STOCK, EQUITY, FUTURES, OPTIONS, CFD
2. **Market Type Granularity**: Detailed product types (MARGIN_FX vs SPOT_FX vs FX_CFD, etc.)
3. **Broker Profiles**: Complete broker capability descriptions
4. **Smart Broker Selection**: Filter brokers by requirements
5. **Risk Engine Routing**: Automatic risk engine selection
6. **Backward Compatibility**: Works with legacy configurations

## Key Concepts

### Asset Class vs Market Type

Asset Class is the broad category:
- FOREX, CRYPTO, STOCK/EQUITY, FUTURES, OPTIONS, CFD

Market Type is the specific trading product:
- MARGIN_FX (leveraged OTC forex)
- SPOT_CRYPTO (spot cryptocurrency)
- CASH_STOCK (no-leverage stocks)
- STOCK_MARGIN (margin trading)
- CRYPTO_PERPETUAL (perpetual futures)
- etc.

### Critical Design: OANDA

IMPORTANT: OANDA for US customers is classified as:
- **Asset Class**: FOREX
- **Market Type**: MARGIN_FX (NOT CFD)
- **Venue**: OTC
- **Risk Engine**: margin_fx
- **CFD Broker**: False

This is because OANDA in the US is leveraged OTC forex with direct settlement,
NOT CFD-based trading.

For non-US customers wanting CFD trading, use "oanda_cfd" profile instead.

## Using the System

### 1. Select Brokers by Criteria

```python
from broker import select_brokers, AssetClass, MarketType

# Select all MARGIN_FX brokers
brokers = select_brokers(market_type=MarketType.MARGIN_FX)

# Select US stock brokers
brokers = select_brokers(
    asset_class=AssetClass.STOCK,
    region="US"
)

# Select crypto brokers with margin support
brokers = select_brokers(
    asset_class=AssetClass.CRYPTO,
    requires_margin=True
)

# Select stock brokers that support shorting
brokers = select_brokers(
    asset_class=AssetClass.STOCK,
    requires_shorting=True,
    region="US"
)
```

### 2. Get Broker Profile

```python
from broker import get_broker_profile

# Get specific broker
oanda_us = get_broker_profile("oanda_us")
alpaca = get_broker_profile("alpaca")
ibkr = get_broker_profile("ibkr")

# Check capabilities
print(f"Supports margin: {alpaca.supports_margin}")
print(f"Default market type: {alpaca.default_market_type}")
```

### 3. Use BrokerSelector for Legacy Compatibility

```python
from broker import BrokerSelector

# Convert legacy config to profile
profile = BrokerSelector.get_profile_from_legacy_config(
    exchange="oanda",
    broker_type="forex",
    customer_region="US"
)
# Returns: OANDA US profile (MARGIN_FX, not CFD)

# Legacy Alpaca config
profile = BrokerSelector.get_profile_from_legacy_config(
    exchange="alpaca",
    broker_type="stocks"
)
# Returns: Alpaca profile (CASH_STOCK by default)
```

### 4. Validate Orders Before Execution

```python
from broker import BrokerValidator, AssetClass, MarketType

alpaca = get_broker_profile("alpaca")

# Validate trading requirements
is_valid, msg = BrokerValidator.validate_symbol(
    alpaca,
    symbol="AAPL",
    asset_class=AssetClass.STOCK,
    market_type=MarketType.CASH_STOCK
)

# Validate order parameters
is_valid, msg = BrokerValidator.validate_order_parameters(
    alpaca,
    side="BUY",
    quantity=100,
    price=150.00,
    order_type="limit"
)
```

### 5. Route to Risk Engine

```python
from broker import get_risk_engine_key, BrokerSelector, MarketType

# Get risk engine for market type
engine = get_risk_engine_key(MarketType.MARGIN_FX)
# Returns: "margin_fx"

# Get risk engine from broker profile
broker = get_broker_profile("oanda_us")
engine = BrokerSelector.route_to_risk_engine(broker)
# Returns: "margin_fx"
```

### 6. Find Best Broker with Alternatives

```python
from broker import route_broker_for_trade, AssetClass, MarketType

# Find primary broker and alternatives
primary, alternatives = route_broker_for_trade(
    asset_class=AssetClass.STOCK,
    requires_margin=True,
    region="US"
)

if primary:
    print(f"Primary broker: {primary.display_name}")
    if alternatives:
        print("Alternatives:")
        for alt in alternatives:
            print(f"  - {alt.display_name}")
else:
    print("No brokers found")
```

## Integration with Existing Code

### Update Broker Factory (broker_factory.py)

To integrate with the new system, update the factory to use profiles:

```python
from broker import BrokerSelector, get_broker_profile

class BrokerFactory:
    @staticmethod
    def create(config):
        # Get profile from legacy config
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange=config.broker.exchange,
            broker_type=config.broker.type,
            customer_region=config.broker.customer_region
        )
        
        if not profile:
            raise ValueError(
                f"No broker profile for {config.broker.exchange} / {config.broker.type}"
            )
        
        # Validate before creating
        is_valid, msg = BrokerValidator.validate_connection(profile)
        if not is_valid:
            raise ValueError(f"Broker validation failed: {msg}")
        
        # Create broker as before
        broker_class = _load_broker_class(...)
        broker = broker_class(config)
        
        # Attach profile for later reference
        broker.profile = profile
        
        return broker
```

### Update Order Execution (execution flow)

Before executing orders, validate against broker profile:

```python
from broker import BrokerValidator, validate_broker_for_trade

async def execute_order(broker, symbol, side, quantity, market_type=None):
    # Get broker profile
    profile = getattr(broker, 'profile', None)
    if not profile:
        profile = get_broker_profile(broker.exchange_name)
    
    # Validate broker supports the order
    is_valid, msg = validate_broker_for_trade(
        profile,
        asset_class=asset_class,
        market_type=market_type,
        requires_margin=side == "SHORT"  # shorting requires margin capability
    )
    
    if not is_valid:
        raise ValueError(f"Broker cannot execute order: {msg}")
    
    # Validate order parameters
    is_valid, msg = BrokerValidator.validate_order_parameters(
        profile,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type
    )
    
    if not is_valid:
        raise ValueError(f"Order validation failed: {msg}")
    
    # Proceed with execution
    return await broker.submit_order(symbol, side, quantity)
```

### Update Risk Engine Selection

Use market type to select risk engine:

```python
from broker import get_risk_engine_key

async def process_trade(order_info):
    market_type = order_info.get('market_type')
    
    # Get appropriate risk engine
    risk_engine_key = get_risk_engine_key(market_type)
    risk_engine = get_risk_engine(risk_engine_key)
    
    # Validate trade through risk engine
    review = risk_engine.review(order_info)
    if not review.approved:
        return {"status": "rejected", "reason": review.reason}
    
    # Execute trade
    return await execute_trade(order_info)
```

## Broker Profiles Reference

### OANDA
- **OANDA US** (oanda_us): MARGIN_FX, OTC, US only, leveraged forex
- **OANDA CFD** (oanda_cfd): FX_CFD/STOCK_CFD/EQUITY_CFD, Global, CFD-based

### Coinbase
- **Coinbase** (coinbase): SPOT_CRYPTO, Exchange
- **Coinbase Futures** (coinbase_futures): CRYPTO_PERPETUAL, Exchange

### Alpaca
- **Alpaca** (alpaca): CASH_STOCK, no margin (default)
- **Alpaca Margin** (alpaca_margin): CASH_STOCK + STOCK_MARGIN

### Charles Schwab
- **Schwab** (schwab): STOCK + OPTIONS, no margin
- **Schwab Margin** (schwab_margin): STOCK + OPTIONS + STOCK_MARGIN + SHORT_STOCK

### Interactive Brokers
- **IBKR** (ibkr): All asset classes and market types, Global

### Crypto Derivatives
- **Binance Futures** (binance_futures): CRYPTO_PERPETUAL + CRYPTO_FUTURE
- **Bybit** (bybit_futures): CRYPTO_PERPETUAL + CRYPTO_FUTURE

### Paper Trading
- **Paper** (paper): All asset classes and market types for simulation

## Risk Engine Routing

Market types automatically route to risk engines:

| Market Type | Risk Engine |
|---|---|
| MARGIN_FX | margin_fx |
| SPOT_CRYPTO | spot_crypto |
| CRYPTO_PERPETUAL | perpetual |
| CRYPTO_FUTURE | futures |
| CASH_STOCK | stock |
| FRACTIONAL_STOCK | fractional_stock |
| STOCK_MARGIN | stock_margin |
| SHORT_STOCK | short_stock |
| STOCK_OPTION | options |
| EQUITY_OPTION | options |
| LISTED_FUTURE | futures |
| LISTED_OPTION | options |
| FX_CFD / STOCK_CFD / EQUITY_CFD | cfd |

## Backward Compatibility

All legacy configurations continue to work:

```python
# These all work as before:
BrokerFactory.create(config)  # Uses legacy factory
broker.execute_order(...)      # Still supported

# But now you can ALSO use the new system:
from broker import BrokerSelector, get_broker_profile

profile = BrokerSelector.get_profile_from_legacy_config(
    exchange=config.broker.exchange,
    broker_type=config.broker.type
)
```

## Testing

Run the test suite:

```bash
pytest src/broker/tests/test_broker_classification.py -v
```

Key test cases:
- OANDA US is MARGIN_FX, not CFD
- OANDA CFD is CFD-based
- Coinbase spot is not perpetual
- Alpaca cash is no-leverage by default
- Alpaca margin enables margin trading
- Schwab supports options
- IBKR supports all asset classes
- Risk engine routing
- Broker selection by criteria
- Legacy compatibility

## Examples by Use Case

### Trading MARGIN_FX with OANDA (US)

```python
from broker import BrokerSelector, MarketType, AssetClass

# Confirm profile is correct
profile = BrokerSelector.get_profile_from_legacy_config(
    exchange="oanda",
    broker_type="forex",
    customer_region="US"
)
assert profile.broker_id == "oanda_us"
assert MarketType.MARGIN_FX in profile.market_types
assert not profile.is_cfd_broker

# Create broker with config
broker = create_broker(config)
broker.profile = profile

# Execute forex trade
```

### Trading SPOT Crypto with Coinbase

```python
from broker import BrokerSelector, MarketType

profile = BrokerSelector.get_profile_from_legacy_config(
    exchange="coinbase",
    broker_type="crypto"
)
assert profile.broker_id == "coinbase"
assert MarketType.SPOT_CRYPTO in profile.market_types
assert not profile.supports_leverage
```

### Trading Stocks with Margin on Alpaca

```python
from broker import select_brokers, AssetClass

# Select Alpaca with margin support
brokers = select_brokers(
    asset_class=AssetClass.STOCK,
    requires_margin=True
)
# Returns [alpaca_margin profile]

profile = brokers[0]
assert profile.broker_id == "alpaca_margin"
assert profile.supports_margin
```

### Full-Service Multi-Asset with IBKR

```python
from broker import get_broker_profile

profile = get_broker_profile("ibkr")

# Check available asset classes and market types
print(f"Asset classes: {profile.asset_classes}")
print(f"Market types: {profile.market_types}")

# IBKR supports everything globally
```
"""

# This file is documentation only - no executable code below
