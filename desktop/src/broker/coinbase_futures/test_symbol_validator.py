"""Unit tests for Coinbase derivatives symbol validation.

Tests cover:
- Symbol format validation (perpetuals and expiring)
- Symbol construction
- Format conversion
- Error handling
- Batch operations
"""

import pytest
from datetime import datetime

from symbol_validator import (
    CoinbaseDerivativeSymbolError,
    construct_expiring_symbol,
    construct_perpetual_symbol,
    convert_from_normalized_symbol,
    convert_symbols_list,
    convert_to_normalized_symbol,
    extract_base_currency,
    extract_contract_type,
    is_derivative_symbol,
    validate_derivative_symbol,
    validate_symbols_list,
)


class TestValidateDerivativeSymbol:
    """Test symbol validation."""
    
    def test_valid_perpetual_symbols(self):
        """Test validation of perpetual symbols."""
        assert validate_derivative_symbol("BTC-PERP") == ("BTC", "PERP")
        assert validate_derivative_symbol("ETH-PERP") == ("ETH", "PERP")
        assert validate_derivative_symbol("SOL-PERP") == ("SOL", "PERP")
        assert validate_derivative_symbol("AAPL-PERP") == ("AAPL", "PERP")
    
    def test_valid_expiring_symbols(self):
        """Test validation of expiring contract symbols."""
        assert validate_derivative_symbol("BTC-20260419") == ("BTC", "20260419")
        assert validate_derivative_symbol("ETH-20250321") == ("ETH", "20250321")
        assert validate_derivative_symbol("SOL-20260630") == ("SOL", "20260630")
    
    def test_case_insensitive(self):
        """Test that validation is case-insensitive."""
        assert validate_derivative_symbol("btc-perp") == ("BTC", "PERP")
        assert validate_derivative_symbol("eth-perp") == ("ETH", "PERP")
        assert validate_derivative_symbol("btc-20260419") == ("BTC", "20260419")
    
    def test_whitespace_stripping(self):
        """Test that whitespace is stripped."""
        assert validate_derivative_symbol("  BTC-PERP  ") == ("BTC", "PERP")
        assert validate_derivative_symbol("\tETH-PERP\n") == ("ETH", "PERP")
    
    def test_invalid_perpetual_format(self):
        """Test rejection of invalid perpetual formats."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC")  # Missing -PERP
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTCPERP")  # Missing hyphen
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC-PERPETUAL")  # Wrong suffix
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC/PERP")  # Wrong separator
    
    def test_invalid_expiring_format(self):
        """Test rejection of invalid expiring formats."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC-2026041")  # Wrong date length
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC-20260132")  # Invalid month
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC-99999999")  # Invalid date
    
    def test_invalid_base_currency(self):
        """Test rejection of invalid base currencies."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("-PERP")  # Missing base
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("VERYLONGCURRENCYNAME-PERP")  # Too long
    
    def test_internal_format_rejected(self):
        """Test that internal format is rejected."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC/USD:PERP")
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("ETH/USDC:20260419")


class TestIsDerivativeSymbol:
    """Test derivative symbol checking."""
    
    def test_valid_symbols(self):
        """Test identification of valid symbols."""
        assert is_derivative_symbol("BTC-PERP") is True
        assert is_derivative_symbol("ETH-20260419") is True
        assert is_derivative_symbol("SOL-PERP") is True
    
    def test_invalid_symbols(self):
        """Test rejection of invalid symbols."""
        assert is_derivative_symbol("BTC") is False
        assert is_derivative_symbol("BTC/USD:PERP") is False
        assert is_derivative_symbol("INVALID") is False
        assert is_derivative_symbol("") is False


class TestConstructPerpetualSymbol:
    """Test perpetual symbol construction."""
    
    def test_valid_construction(self):
        """Test constructing valid perpetual symbols."""
        assert construct_perpetual_symbol("BTC") == "BTC-PERP"
        assert construct_perpetual_symbol("ETH") == "ETH-PERP"
        assert construct_perpetual_symbol("SOL") == "SOL-PERP"
    
    def test_case_normalization(self):
        """Test that case is normalized."""
        assert construct_perpetual_symbol("btc") == "BTC-PERP"
        assert construct_perpetual_symbol("Eth") == "ETH-PERP"
    
    def test_invalid_base_currency(self):
        """Test rejection of invalid base currencies."""
        with pytest.raises(ValueError):
            construct_perpetual_symbol("")  # Empty
        
        with pytest.raises(ValueError):
            construct_perpetual_symbol("VERYLONGCURRENCYNAME")  # Too long
        
        with pytest.raises(ValueError):
            construct_perpetual_symbol("BTC-")  # Contains hyphen


class TestConstructExpiringSymbol:
    """Test expiring symbol construction."""
    
    def test_construct_from_string(self):
        """Test constructing from date string."""
        assert construct_expiring_symbol("BTC", "20260419") == "BTC-20260419"
        assert construct_expiring_symbol("ETH", "20250321") == "ETH-20250321"
    
    def test_construct_from_datetime(self):
        """Test constructing from datetime object."""
        date = datetime(2026, 4, 19)
        assert construct_expiring_symbol("BTC", date) == "BTC-20260419"
        
        date = datetime(2025, 3, 21)
        assert construct_expiring_symbol("ETH", date) == "ETH-20250321"
    
    def test_case_normalization(self):
        """Test case normalization."""
        assert construct_expiring_symbol("btc", "20260419") == "BTC-20260419"
    
    def test_invalid_date(self):
        """Test rejection of invalid dates."""
        with pytest.raises(ValueError):
            construct_expiring_symbol("BTC", "20260132")  # Invalid month
        
        with pytest.raises(ValueError):
            construct_expiring_symbol("BTC", "202604")  # Wrong format
        
        with pytest.raises(ValueError):
            construct_expiring_symbol("BTC", "26040419")  # Wrong order


class TestExtractComponents:
    """Test component extraction."""
    
    def test_extract_base_currency(self):
        """Test extracting base currency."""
        assert extract_base_currency("BTC-PERP") == "BTC"
        assert extract_base_currency("ETH-20260419") == "ETH"
        assert extract_base_currency("SOL-PERP") == "SOL"
    
    def test_extract_contract_type(self):
        """Test extracting contract type."""
        assert extract_contract_type("BTC-PERP") == "PERP"
        assert extract_contract_type("ETH-20260419") == "20260419"
        assert extract_contract_type("SOL-20250321") == "20250321"
    
    def test_extract_from_invalid_symbol(self):
        """Test extraction error handling."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            extract_base_currency("INVALID")
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            extract_contract_type("BTC/USD:PERP")


class TestFormatConversion:
    """Test conversion between normalized and derivative formats."""
    
    def test_from_normalized_perpetual(self):
        """Test converting normalized to derivative format - perpetuals."""
        assert convert_from_normalized_symbol("BTC/USD:PERP") == "BTC-PERP"
        assert convert_from_normalized_symbol("ETH/USDC:PERP") == "ETH-PERP"
        assert convert_from_normalized_symbol("SOL/USD:PERP") == "SOL-PERP"
    
    def test_from_normalized_expiring(self):
        """Test converting normalized to derivative format - expiring."""
        assert convert_from_normalized_symbol("BTC/USD:20260419") == "BTC-20260419"
        assert convert_from_normalized_symbol("ETH/USDC:20250321") == "ETH-20250321"
    
    def test_to_normalized_perpetual(self):
        """Test converting derivative to normalized format - perpetuals."""
        assert convert_to_normalized_symbol("BTC-PERP") == "BTC/USD:PERP"
        assert convert_to_normalized_symbol("ETH-PERP", quote_currency="USDC") == "ETH/USDC:PERP"
    
    def test_to_normalized_expiring(self):
        """Test converting derivative to normalized format - expiring."""
        assert convert_to_normalized_symbol("BTC-20260419") == "BTC/USD:20260419"
        assert convert_to_normalized_symbol("SOL-20250321", quote_currency="USDC") == "SOL/USDC:20250321"
    
    def test_invalid_normalized_format(self):
        """Test rejection of invalid normalized formats."""
        with pytest.raises(ValueError):
            convert_from_normalized_symbol("BTC-PERP")  # Already in derivative format
        
        with pytest.raises(ValueError):
            convert_from_normalized_symbol("BTC:USD:PERP")  # Wrong format


class TestBatchOperations:
    """Test batch validation and conversion."""
    
    def test_validate_symbols_list(self):
        """Test batch validation."""
        results = validate_symbols_list([
            "BTC-PERP",
            "ETH-20260419",
            "SOL-PERP",
            "INVALID",
            "BTC",
        ])
        
        assert results["valid"] == ["BTC-PERP", "ETH-20260419", "SOL-PERP"]
        assert results["invalid"] == ["INVALID", "BTC"]
        assert "INVALID" in results["errors"]
        assert "BTC" in results["errors"]
    
    def test_convert_symbols_from_normalized(self):
        """Test batch conversion from normalized format."""
        results = convert_symbols_list(
            [
                "BTC/USD:PERP",
                "ETH/USDC:20260419",
                "SOL/USD:PERP",
            ],
            from_format="normalized"
        )
        
        assert results["converted"] == ["BTC-PERP", "ETH-20260419", "SOL-PERP"]
        assert results["failed"] == []
        assert results["errors"] == {}
    
    def test_convert_symbols_to_normalized(self):
        """Test batch conversion to normalized format."""
        results = convert_symbols_list(
            [
                "BTC-PERP",
                "ETH-20260419",
                "SOL-PERP",
            ],
            from_format="derivative",
            quote_currency="USD"
        )
        
        assert results["converted"] == ["BTC/USD:PERP", "ETH/USD:20260419", "SOL/USD:PERP"]
        assert results["failed"] == []
        assert results["errors"] == {}
    
    def test_batch_conversion_with_errors(self):
        """Test batch conversion with mixed valid/invalid symbols."""
        results = convert_symbols_list(
            [
                "BTC-PERP",
                "INVALID",
                "ETH-20260419",
                "BTC/WRONG:FORMAT",
            ],
            from_format="derivative"
        )
        
        assert results["converted"] == ["BTC/USD:PERP", "ETH/USD:20260419"]
        assert results["failed"] == ["INVALID", "BTC/WRONG:FORMAT"]
        assert len(results["errors"]) == 2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_string(self):
        """Test handling of empty strings."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("")
        
        assert is_derivative_symbol("") is False
    
    def test_none_value(self):
        """Test handling of None values."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol(None)
    
    def test_unicode_characters(self):
        """Test rejection of unicode characters."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC-PERP™")
        
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("₿TC-PERP")
    
    def test_multiple_hyphens(self):
        """Test rejection of multiple hyphens."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("BTC--PERP")
    
    def test_very_long_base_currency(self):
        """Test rejection of very long base currencies."""
        with pytest.raises(CoinbaseDerivativeSymbolError):
            validate_derivative_symbol("VERYLONGNAME-PERP")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
