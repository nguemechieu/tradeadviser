"""Comprehensive tests for broker classification and selection system.

Tests cover:
- OANDA margin FX vs CFD classification
- Coinbase spot crypto
- Alpaca cash vs margin vs fractional
- Schwab stock and options
- Interactive Brokers multi-asset
- Risk routing
- Backward compatibility
- Broker validation
"""

import pytest

from broker.broker_classification import (
    AssetClass,
    BrokerProfile,
    MarketType,
    VenueType,
    BROKER_PROFILES,
    get_broker_profile,
    get_risk_engine_key,
    select_brokers,
    validate_broker_for_trade,
)
from broker.broker_selector import (
    BrokerSelector,
    BrokerValidator,
    route_broker_for_trade,
)


class TestAssetClassEnums:
    """Test asset class enum values."""

    def test_asset_classes_exist(self):
        """Verify all required asset classes exist."""
        assert AssetClass.FOREX
        assert AssetClass.CRYPTO
        assert AssetClass.STOCK
        assert AssetClass.EQUITY
        assert AssetClass.FUTURES
        assert AssetClass.OPTIONS
        assert AssetClass.CFD

    def test_asset_class_values(self):
        """Verify asset class enum values."""
        assert AssetClass.FOREX.value == "forex"
        assert AssetClass.CRYPTO.value == "crypto"
        assert AssetClass.STOCK.value == "stock"
        assert AssetClass.EQUITY.value == "equity"


class TestMarketTypeEnums:
    """Test market type enum values."""

    def test_forex_market_types(self):
        """Verify forex market types."""
        assert MarketType.SPOT_FX
        assert MarketType.MARGIN_FX
        assert MarketType.FX_CFD
        assert MarketType.FX_FUTURE
        assert MarketType.FX_OPTION

    def test_crypto_market_types(self):
        """Verify crypto market types."""
        assert MarketType.SPOT_CRYPTO
        assert MarketType.CRYPTO_MARGIN
        assert MarketType.CRYPTO_PERPETUAL
        assert MarketType.CRYPTO_FUTURE
        assert MarketType.CRYPTO_OPTION

    def test_stock_market_types(self):
        """Verify stock market types."""
        assert MarketType.CASH_STOCK
        assert MarketType.CASH_EQUITY
        assert MarketType.FRACTIONAL_STOCK
        assert MarketType.STOCK_MARGIN
        assert MarketType.EQUITY_MARGIN
        assert MarketType.SHORT_STOCK
        assert MarketType.STOCK_CFD
        assert MarketType.STOCK_OPTION


class TestVenueTypeEnums:
    """Test venue type enums."""

    def test_venue_types(self):
        """Verify venue types exist."""
        assert VenueType.EXCHANGE
        assert VenueType.OTC
        assert VenueType.BROKER_DEALER
        assert VenueType.ECN
        assert VenueType.HYBRID


class TestOANDAProfiles:
    """Test OANDA broker profile classification."""

    def test_oanda_us_is_margin_fx_not_cfd(self):
        """OANDA US must be MARGIN_FX, not CFD for US users."""
        oanda_us = get_broker_profile("oanda_us")
        assert oanda_us is not None
        assert oanda_us.region == "US"
        assert AssetClass.FOREX in oanda_us.asset_classes
        assert MarketType.MARGIN_FX in oanda_us.market_types
        assert not oanda_us.is_cfd_broker
        assert oanda_us.supports_leverage
        assert oanda_us.supports_margin

    def test_oanda_cfd_is_cfd(self):
        """OANDA CFD profile must have CFD market type."""
        oanda_cfd = get_broker_profile("oanda_cfd")
        assert oanda_cfd is not None
        assert oanda_cfd.is_cfd_broker
        assert MarketType.FX_CFD in oanda_cfd.market_types
        assert oanda_cfd.region == "Global"

    def test_oanda_profiles_different(self):
        """OANDA US and CFD profiles must be different."""
        oanda_us = get_broker_profile("oanda_us")
        oanda_cfd = get_broker_profile("oanda_cfd")
        assert oanda_us != oanda_cfd
        assert oanda_us.is_cfd_broker != oanda_cfd.is_cfd_broker

    def test_oanda_us_risk_engine(self):
        """OANDA US should route to margin_fx risk engine."""
        oanda_us = get_broker_profile("oanda_us")
        assert oanda_us.risk_engine_key == "margin_fx"


class TestCoinbaseProfiles:
    """Test Coinbase broker profiles."""

    def test_coinbase_spot_crypto(self):
        """Coinbase must support spot crypto."""
        coinbase = get_broker_profile("coinbase")
        assert coinbase is not None
        assert AssetClass.CRYPTO in coinbase.asset_classes
        assert MarketType.SPOT_CRYPTO in coinbase.market_types
        assert not coinbase.supports_leverage
        assert not coinbase.supports_margin
        assert coinbase.venue_type == VenueType.EXCHANGE

    def test_coinbase_not_perpetual(self):
        """Coinbase spot should not support perpetual."""
        coinbase = get_broker_profile("coinbase")
        assert MarketType.CRYPTO_PERPETUAL not in coinbase.market_types

    def test_coinbase_futures_has_perpetual(self):
        """Coinbase Futures should support perpetual."""
        coinbase_futures = get_broker_profile("coinbase_futures")
        assert coinbase_futures is not None
        assert MarketType.CRYPTO_PERPETUAL in coinbase_futures.market_types
        assert coinbase_futures.supports_leverage
        assert coinbase_futures.supports_margin

    def test_coinbase_risk_engines(self):
        """Verify Coinbase risk engine routing."""
        coinbase = get_broker_profile("coinbase")
        assert coinbase.risk_engine_key == "spot_crypto"

        coinbase_futures = get_broker_profile("coinbase_futures")
        assert coinbase_futures.risk_engine_key == "perpetual"


class TestAlpacaProfiles:
    """Test Alpaca broker profiles."""

    def test_alpaca_cash_stock(self):
        """Alpaca default should be cash stock without margin."""
        alpaca = get_broker_profile("alpaca")
        assert alpaca is not None
        assert AssetClass.STOCK in alpaca.asset_classes or AssetClass.EQUITY in alpaca.asset_classes
        assert MarketType.CASH_STOCK in alpaca.market_types or MarketType.CASH_EQUITY in alpaca.market_types
        assert alpaca.supports_fractional
        assert not alpaca.supports_margin
        assert not alpaca.supports_leverage

    def test_alpaca_fractional_stock(self):
        """Alpaca should support fractional shares."""
        alpaca = get_broker_profile("alpaca")
        assert alpaca.supports_fractional
        assert MarketType.FRACTIONAL_STOCK in alpaca.market_types

    def test_alpaca_margin_stock(self):
        """Alpaca with margin should have margin stock support."""
        alpaca_margin = get_broker_profile("alpaca_margin")
        assert alpaca_margin is not None
        assert alpaca_margin.supports_margin
        assert alpaca_margin.supports_leverage
        assert MarketType.STOCK_MARGIN in alpaca_margin.market_types or \
               MarketType.EQUITY_MARGIN in alpaca_margin.market_types

    def test_alpaca_default_market_type(self):
        """Alpaca should default to cash stock."""
        alpaca = get_broker_profile("alpaca")
        assert alpaca.default_market_type in {
            MarketType.CASH_STOCK,
            MarketType.CASH_EQUITY,
        }

    def test_alpaca_risk_engines(self):
        """Verify Alpaca risk engine routing."""
        alpaca = get_broker_profile("alpaca")
        assert alpaca.risk_engine_key == "stock"

        alpaca_margin = get_broker_profile("alpaca_margin")
        assert alpaca_margin.risk_engine_key == "stock_margin"


class TestSchwabProfiles:
    """Test Charles Schwab broker profiles."""

    def test_schwab_stock_and_options(self):
        """Schwab should support stocks and options."""
        schwab = get_broker_profile("schwab")
        assert schwab is not None
        assert AssetClass.STOCK in schwab.asset_classes or AssetClass.EQUITY in schwab.asset_classes
        assert AssetClass.OPTIONS in schwab.asset_classes
        assert schwab.supports_options
        assert MarketType.STOCK_OPTION in schwab.market_types or \
               MarketType.EQUITY_OPTION in schwab.market_types

    def test_schwab_no_leverage_default(self):
        """Schwab default should not have leverage."""
        schwab = get_broker_profile("schwab")
        assert not schwab.supports_leverage
        assert not schwab.supports_margin

    def test_schwab_margin_profile(self):
        """Schwab margin profile should have margin support."""
        schwab_margin = get_broker_profile("schwab_margin")
        assert schwab_margin is not None
        assert schwab_margin.supports_margin
        assert schwab_margin.supports_shorting
        assert MarketType.SHORT_STOCK in schwab_margin.market_types


class TestIBKRProfile:
    """Test Interactive Brokers profile."""

    def test_ibkr_multi_asset_class(self):
        """IBKR should support multiple asset classes."""
        ibkr = get_broker_profile("ibkr")
        assert ibkr is not None
        assert AssetClass.STOCK in ibkr.asset_classes or AssetClass.EQUITY in ibkr.asset_classes
        assert AssetClass.FOREX in ibkr.asset_classes
        assert AssetClass.FUTURES in ibkr.asset_classes
        assert AssetClass.OPTIONS in ibkr.asset_classes

    def test_ibkr_stock_futures_options(self):
        """IBKR should support stocks, futures, and options."""
        ibkr = get_broker_profile("ibkr")
        assert ibkr.supports_futures
        assert ibkr.supports_options
        assert ibkr.supports_derivatives

    def test_ibkr_market_types(self):
        """IBKR should have comprehensive market types."""
        ibkr = get_broker_profile("ibkr")
        # Check key market types
        assert MarketType.CASH_STOCK in ibkr.market_types or \
               MarketType.CASH_EQUITY in ibkr.market_types
        assert MarketType.LISTED_FUTURE in ibkr.market_types
        assert MarketType.LISTED_OPTION in ibkr.market_types
        assert MarketType.SPOT_FX in ibkr.market_types or \
               MarketType.MARGIN_FX in ibkr.market_types

    def test_ibkr_venue_type(self):
        """IBKR should be hybrid venue."""
        ibkr = get_broker_profile("ibkr")
        assert ibkr.venue_type == VenueType.HYBRID


class TestRiskEngineRouting:
    """Test risk engine routing by market type."""

    def test_margin_fx_routing(self):
        """MARGIN_FX should route to margin_fx engine."""
        engine = get_risk_engine_key(MarketType.MARGIN_FX)
        assert engine == "margin_fx"

    def test_spot_crypto_routing(self):
        """SPOT_CRYPTO should route to spot_crypto engine."""
        engine = get_risk_engine_key(MarketType.SPOT_CRYPTO)
        assert engine == "spot_crypto"

    def test_crypto_perpetual_routing(self):
        """CRYPTO_PERPETUAL should route to perpetual engine."""
        engine = get_risk_engine_key(MarketType.CRYPTO_PERPETUAL)
        assert engine == "perpetual"

    def test_cash_stock_routing(self):
        """CASH_STOCK should route to stock engine."""
        engine = get_risk_engine_key(MarketType.CASH_STOCK)
        assert engine == "stock"

    def test_fractional_stock_routing(self):
        """FRACTIONAL_STOCK should route to fractional_stock engine."""
        engine = get_risk_engine_key(MarketType.FRACTIONAL_STOCK)
        assert engine == "fractional_stock"

    def test_stock_margin_routing(self):
        """STOCK_MARGIN should route to stock_margin engine."""
        engine = get_risk_engine_key(MarketType.STOCK_MARGIN)
        assert engine == "stock_margin"

    def test_short_stock_routing(self):
        """SHORT_STOCK should route to short_stock engine."""
        engine = get_risk_engine_key(MarketType.SHORT_STOCK)
        assert engine == "short_stock"

    def test_listed_option_routing(self):
        """LISTED_OPTION should route to options engine."""
        engine = get_risk_engine_key(MarketType.LISTED_OPTION)
        assert engine == "options"

    def test_listed_future_routing(self):
        """LISTED_FUTURE should route to futures engine."""
        engine = get_risk_engine_key(MarketType.LISTED_FUTURE)
        assert engine == "futures"

    def test_cfd_routing(self):
        """CFD market types should route to cfd engine."""
        assert get_risk_engine_key(MarketType.FX_CFD) == "cfd"
        assert get_risk_engine_key(MarketType.STOCK_CFD) == "cfd"
        assert get_risk_engine_key(MarketType.EQUITY_CFD) == "cfd"


class TestBrokerSelection:
    """Test broker selection by criteria."""

    def test_select_by_asset_class(self):
        """Select brokers by asset class."""
        forex_brokers = select_brokers(asset_class=AssetClass.FOREX)
        assert len(forex_brokers) > 0
        assert all(AssetClass.FOREX in b.asset_classes for b in forex_brokers)

        crypto_brokers = select_brokers(asset_class=AssetClass.CRYPTO)
        assert len(crypto_brokers) > 0
        assert all(AssetClass.CRYPTO in b.asset_classes for b in crypto_brokers)

    def test_select_by_market_type(self):
        """Select brokers by market type."""
        margin_fx_brokers = select_brokers(market_type=MarketType.MARGIN_FX)
        assert len(margin_fx_brokers) > 0
        assert all(MarketType.MARGIN_FX in b.market_types for b in margin_fx_brokers)

        spot_crypto_brokers = select_brokers(market_type=MarketType.SPOT_CRYPTO)
        assert len(spot_crypto_brokers) > 0
        assert all(MarketType.SPOT_CRYPTO in b.market_types for b in spot_crypto_brokers)

    def test_select_by_region(self):
        """Select brokers by region."""
        us_brokers = select_brokers(region="US")
        assert len(us_brokers) > 0
        assert all(b.region == "US" for b in us_brokers)

        global_brokers = select_brokers(region="Global")
        assert len(global_brokers) > 0
        assert all(b.region == "Global" for b in global_brokers)

    def test_select_by_margin_requirement(self):
        """Select brokers that support margin."""
        margin_brokers = select_brokers(requires_margin=True)
        assert len(margin_brokers) > 0
        assert all(b.supports_margin for b in margin_brokers)

    def test_select_by_leverage_requirement(self):
        """Select brokers that support leverage."""
        leverage_brokers = select_brokers(requires_leverage=True)
        assert len(leverage_brokers) > 0
        assert all(b.supports_leverage for b in leverage_brokers)

    def test_select_by_shorting_requirement(self):
        """Select brokers that support shorting."""
        short_brokers = select_brokers(requires_shorting=True)
        assert len(short_brokers) > 0
        assert all(b.supports_shorting for b in short_brokers)

    def test_select_by_fractional_requirement(self):
        """Select brokers that support fractional shares."""
        frac_brokers = select_brokers(requires_fractional=True)
        assert len(frac_brokers) > 0
        assert all(b.supports_fractional for b in frac_brokers)

    def test_complex_selection(self):
        """Select brokers with multiple requirements."""
        brokers = select_brokers(
            asset_class=AssetClass.STOCK,
            requires_margin=True,
            region="US"
        )
        assert len(brokers) > 0
        assert all(AssetClass.STOCK in b.asset_classes or AssetClass.EQUITY in b.asset_classes
                   for b in brokers)
        assert all(b.supports_margin for b in brokers)
        assert all(b.region == "US" for b in brokers)


class TestBrokerValidation:
    """Test broker validation for trades."""

    def test_can_trade_basic(self):
        """Test basic can_trade validation."""
        alpaca = get_broker_profile("alpaca")
        can_trade, reason = validate_broker_for_trade(
            alpaca,
            asset_class=AssetClass.STOCK,
            market_type=MarketType.CASH_STOCK
        )
        assert can_trade
        assert reason == "OK"

    def test_cannot_trade_unsupported_asset(self):
        """Broker should reject unsupported asset class."""
        alpaca = get_broker_profile("alpaca")
        can_trade, reason = validate_broker_for_trade(
            alpaca,
            asset_class=AssetClass.FOREX
        )
        assert not can_trade
        assert "not support" in reason.lower()

    def test_cannot_trade_requires_margin_no_support(self):
        """Broker without margin should reject margin trade."""
        alpaca = get_broker_profile("alpaca")
        can_trade, reason = validate_broker_for_trade(
            alpaca,
            requires_margin=True
        )
        assert not can_trade
        assert "margin" in reason.lower()

    def test_can_trade_with_margin_support(self):
        """Broker with margin should allow margin trade."""
        alpaca_margin = get_broker_profile("alpaca_margin")
        can_trade, reason = validate_broker_for_trade(
            alpaca_margin,
            asset_class=AssetClass.STOCK,
            requires_margin=True
        )
        assert can_trade


class TestBackwardCompatibility:
    """Test backward compatibility with legacy configurations."""

    def test_oanda_forex_legacy(self):
        """Legacy broker=oanda, asset_class=forex should work."""
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange="oanda",
            broker_type="forex"
        )
        assert profile is not None
        assert profile.broker_id == "oanda_us"

    def test_oanda_forex_us_region_legacy(self):
        """Legacy OANDA with US region should select oanda_us."""
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange="oanda",
            broker_type="forex",
            customer_region="US"
        )
        assert profile is not None
        assert profile.broker_id == "oanda_us"

    def test_coinbase_crypto_legacy(self):
        """Legacy broker=coinbase, asset_class=crypto should work."""
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange="coinbase",
            broker_type="crypto"
        )
        assert profile is not None
        assert profile.broker_id == "coinbase"

    def test_alpaca_stocks_legacy(self):
        """Legacy broker=alpaca, asset_class=stocks should work."""
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange="alpaca",
            broker_type="stocks"
        )
        assert profile is not None
        assert "alpaca" in profile.broker_id.lower()

    def test_schwab_stocks_legacy(self):
        """Legacy broker=schwab, asset_class=stocks should work."""
        profile = BrokerSelector.get_profile_from_legacy_config(
            exchange="schwab",
            broker_type="stocks"
        )
        assert profile is not None
        assert "schwab" in profile.broker_id.lower()

    def test_ibkr_multi_asset_legacy(self):
        """Legacy IBKR should work for multiple asset classes."""
        for broker_type in ["stocks", "forex", "futures", "options"]:
            profile = BrokerSelector.get_profile_from_legacy_config(
                exchange="ibkr",
                broker_type=broker_type
            )
            assert profile is not None
            assert profile.broker_id == "ibkr"


class TestBrokerSelector:
    """Test BrokerSelector helper class."""

    def test_select_brokers_with_strings(self):
        """BrokerSelector should accept string asset classes."""
        brokers = BrokerSelector.select_brokers(asset_class="forex")
        assert len(brokers) > 0

        brokers = BrokerSelector.select_brokers(asset_class="crypto")
        assert len(brokers) > 0

        brokers = BrokerSelector.select_brokers(asset_class="stocks")
        assert len(brokers) > 0

    def test_get_risk_engine_for_market(self):
        """BrokerSelector should return correct risk engine."""
        engine = BrokerSelector.get_risk_engine_for_market(MarketType.MARGIN_FX)
        assert engine == "margin_fx"

    def test_route_to_risk_engine(self):
        """BrokerSelector should route broker to risk engine."""
        oanda_us = get_broker_profile("oanda_us")
        engine = BrokerSelector.route_to_risk_engine(oanda_us)
        assert engine == "margin_fx"


class TestBrokerValidator:
    """Test BrokerValidator class."""

    def test_validate_connection(self):
        """Validator should check broker has required config."""
        oanda_us = get_broker_profile("oanda_us")
        is_valid, msg = BrokerValidator.validate_connection(oanda_us)
        assert is_valid

    def test_validate_symbol(self):
        """Validator should check symbol is valid for broker."""
        alpaca = get_broker_profile("alpaca")
        is_valid, msg = BrokerValidator.validate_symbol(
            alpaca,
            symbol="AAPL",
            asset_class=AssetClass.STOCK,
            market_type=MarketType.CASH_STOCK
        )
        assert is_valid

    def test_validate_order_parameters(self):
        """Validator should check order parameters."""
        alpaca = get_broker_profile("alpaca")
        is_valid, msg = BrokerValidator.validate_order_parameters(
            alpaca,
            side="BUY",
            quantity=100,
            price=150.0,
            order_type="limit"
        )
        assert is_valid

        # Should reject invalid quantity
        is_valid, msg = BrokerValidator.validate_order_parameters(
            alpaca,
            side="BUY",
            quantity=-100
        )
        assert not is_valid


class TestRouteBrokerForTrade:
    """Test the route_broker_for_trade function."""

    def test_route_margin_fx(self):
        """Should find broker for margin FX trading."""
        primary, alternatives = route_broker_for_trade(
            asset_class=AssetClass.FOREX,
            market_type=MarketType.MARGIN_FX
        )
        assert primary is not None
        assert MarketType.MARGIN_FX in primary.market_types

    def test_route_spot_crypto(self):
        """Should find broker for spot crypto."""
        primary, alternatives = route_broker_for_trade(
            asset_class=AssetClass.CRYPTO,
            market_type=MarketType.SPOT_CRYPTO
        )
        assert primary is not None
        assert MarketType.SPOT_CRYPTO in primary.market_types

    def test_route_stock_with_margin(self):
        """Should find broker for margin stock trading."""
        primary, alternatives = route_broker_for_trade(
            asset_class=AssetClass.STOCK,
            requires_margin=True,
            region="US"
        )
        assert primary is not None
        assert primary.supports_margin

    def test_route_with_alternatives(self):
        """Should return alternative brokers."""
        primary, alternatives = route_broker_for_trade(
            asset_class=AssetClass.STOCK,
            region="US"
        )
        assert primary is not None
        # Alternatives may be empty or have items
        assert isinstance(alternatives, list)

    def test_route_impossible_requirement(self):
        """Should return None when no broker matches."""
        primary, alternatives = route_broker_for_trade(
            asset_class=AssetClass.STOCK,
            region="Mars"  # Non-existent region
        )
        assert primary is None


class TestStockLabelingConvention:
    """Test that 'Stock' is user-facing label for equity assets."""

    def test_alpaca_displays_as_stock(self):
        """Alpaca should display as stock in UI."""
        alpaca = get_broker_profile("alpaca")
        # Check asset classes include both STOCK and EQUITY internally
        assert AssetClass.STOCK in alpaca.asset_classes or \
               AssetClass.EQUITY in alpaca.asset_classes
        # But display should use "Stocks" in market type labels
        assert MarketType.CASH_STOCK in alpaca.market_types or \
               MarketType.CASH_EQUITY in alpaca.market_types

    def test_schwab_stock_option_naming(self):
        """Schwab options should use STOCK_OPTION terminology."""
        schwab = get_broker_profile("schwab")
        # Should have STOCK_OPTION not EQUITY_OPTION
        assert MarketType.STOCK_OPTION in schwab.market_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
