"""Quick Reference - Broker Classification System

=== ASSET CLASSES ===
FOREX, CRYPTO, STOCK, EQUITY, FUTURES, OPTIONS, CFD

=== MARKET TYPES (Examples) ===
FOREX: SPOT_FX, MARGIN_FX, FX_CFD, FX_FUTURE, FX_OPTION
CRYPTO: SPOT_CRYPTO, CRYPTO_MARGIN, CRYPTO_PERPETUAL, CRYPTO_FUTURE, CRYPTO_OPTION
STOCK: CASH_STOCK, CASH_EQUITY, FRACTIONAL_STOCK, STOCK_MARGIN, EQUITY_MARGIN, SHORT_STOCK, STOCK_CFD, STOCK_OPTION
DERIVATIVES: LISTED_FUTURE, LISTED_OPTION

=== VENUE TYPES ===
EXCHANGE, OTC, BROKER_DEALER, ECN, HYBRID

=== KEY BROKER PROFILES ===

OANDA_US
  - Asset: FOREX
  - Market: MARGIN_FX (NOT CFD)
  - Venue: OTC
  - Margin/Leverage: Yes
  - Risk Engine: margin_fx

OANDA_CFD
  - Asset: FOREX, CFD
  - Market: FX_CFD, STOCK_CFD, EQUITY_CFD
  - Venue: OTC
  - CFD Broker: Yes
  - Risk Engine: cfd

COINBASE
  - Asset: CRYPTO
  - Market: SPOT_CRYPTO
  - Venue: EXCHANGE
  - Margin/Leverage: No
  - Risk Engine: spot_crypto

COINBASE_FUTURES
  - Asset: CRYPTO, FUTURES
  - Market: CRYPTO_PERPETUAL
  - Venue: EXCHANGE
  - Margin/Leverage: Yes
  - Risk Engine: perpetual

ALPACA
  - Asset: STOCK, EQUITY
  - Market: CASH_STOCK, FRACTIONAL_STOCK
  - Venue: BROKER_DEALER
  - Margin/Leverage: No
  - Risk Engine: stock

ALPACA_MARGIN
  - Asset: STOCK, EQUITY
  - Market: CASH_STOCK, STOCK_MARGIN, FRACTIONAL_STOCK
  - Venue: BROKER_DEALER
  - Margin/Leverage: Yes
  - Risk Engine: stock_margin

SCHWAB
  - Asset: STOCK, EQUITY, OPTIONS
  - Market: CASH_STOCK, STOCK_OPTION
  - Venue: BROKER_DEALER
  - Margin/Leverage: No
  - Options: Yes
  - Risk Engine: stock_options

SCHWAB_MARGIN
  - Asset: STOCK, EQUITY, OPTIONS
  - Market: CASH_STOCK, STOCK_MARGIN, SHORT_STOCK, STOCK_OPTION
  - Venue: BROKER_DEALER
  - Margin/Leverage: Yes
  - Shorting: Yes
  - Risk Engine: stock_margin

IBKR
  - Asset: STOCK, EQUITY, FOREX, FUTURES, OPTIONS
  - Market: (All stock, forex, futures, options types)
  - Venue: HYBRID
  - Margin/Leverage: Yes
  - Shorting: Yes
  - Derivatives: Yes
  - Risk Engine: multi_asset

BINANCE_FUTURES / BYBIT_FUTURES
  - Asset: CRYPTO, FUTURES
  - Market: CRYPTO_PERPETUAL, CRYPTO_FUTURE
  - Venue: EXCHANGE
  - Margin/Leverage: Yes
  - Risk Engine: perpetual

PAPER
  - Asset: All
  - Market: All (for simulation)
  - Venue: HYBRID
  - All capabilities enabled
  - Risk Engine: default

=== COMMON OPERATIONS ===

1. Select Brokers by Criteria:
   from broker import select_brokers, AssetClass
   brokers = select_brokers(asset_class=AssetClass.FOREX, requires_margin=True)

2. Get Specific Broker:
   from broker import get_broker_profile
   oanda = get_broker_profile("oanda_us")

3. Map Legacy Config:
   from broker import BrokerSelector
   profile = BrokerSelector.get_profile_from_legacy_config(
       exchange="oanda", broker_type="forex", customer_region="US"
   )

4. Validate Order:
   from broker import BrokerValidator
   is_valid, msg = BrokerValidator.validate_order_parameters(
       profile, side="BUY", quantity=100, price=150.0
   )

5. Get Risk Engine:
   from broker import get_risk_engine_key, MarketType
   engine = get_risk_engine_key(MarketType.MARGIN_FX)  # Returns "margin_fx"

6. Route to Broker:
   from broker import route_broker_for_trade, AssetClass
   primary, alternatives = route_broker_for_trade(
       asset_class=AssetClass.STOCK, requires_margin=True, region="US"
   )

=== RISK ENGINE ROUTING ===

MARGIN_FX -> margin_fx
SPOT_CRYPTO -> spot_crypto
CRYPTO_PERPETUAL -> perpetual
CASH_STOCK -> stock
FRACTIONAL_STOCK -> fractional_stock
STOCK_MARGIN -> stock_margin
SHORT_STOCK -> short_stock
STOCK_OPTION -> options
EQUITY_OPTION -> options
LISTED_FUTURE -> futures
LISTED_OPTION -> options
FX_CFD -> cfd
STOCK_CFD -> cfd
EQUITY_CFD -> cfd

=== BACKWARD COMPATIBILITY ===

Legacy broker configs still work:
  broker_type="forex" -> AssetClass.FOREX
  broker_type="crypto" -> AssetClass.CRYPTO
  broker_type="stocks" -> AssetClass.STOCK
  exchange="oanda" + region="US" -> oanda_us profile
  exchange="coinbase" -> coinbase profile
  exchange="alpaca" -> alpaca profile (with optional margin variant)

=== VALIDATION FLOW ===

1. Get broker profile (from legacy config or direct)
2. Validate connection: BrokerValidator.validate_connection(profile)
3. Validate symbol: BrokerValidator.validate_symbol(profile, symbol, asset_class, market_type)
4. Validate order parameters: BrokerValidator.validate_order_parameters(profile, side, quantity, price)
5. Validate trade through risk engine using profile.risk_engine_key
6. Execute order

=== IMPORTANT NOTES ===

1. OANDA for US customers is MARGIN_FX (leveraged OTC), NOT CFD
   - Use "oanda_us" profile for US customers
   - Use "oanda_cfd" profile for non-US CFD trading

2. Stock/Equity terminology:
   - Internal: Both "stock" and "equity" are used interchangeably
   - User-facing: Always use "Stocks" in UI
   - Market types use "STOCK" prefix for consistency

3. Spot vs Margin vs Perpetual:
   - SPOT_CRYPTO: No leverage
   - CRYPTO_MARGIN: Leveraged spot trading
   - CRYPTO_PERPETUAL: Perpetual futures (with leverage)

4. Fractional shares:
   - Only Alpaca supports FRACTIONAL_STOCK explicitly
   - Requires special risk engine handling

5. Shorting support:
   - CASH_STOCK: Cannot short
   - STOCK_MARGIN: Can short
   - SHORT_STOCK: Explicit shorting support
"""
