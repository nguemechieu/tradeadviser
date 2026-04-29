import sys
sys.path.insert(0, "src")

# Test dashboard imports
try:
    from ui.components.dashboard import (
        BROKER_TYPE_OPTIONS,
        ASSET_CLASS_OPTIONS,
        MARKET_TYPE_CHOICES_NEW,
        _get_broker_profile_for_selection,
        _get_supported_market_types_for_broker,
        _validate_broker_market_type,
    )
    print("? Dashboard imports successful")
except Exception as e:
    print(f"? Dashboard import error: {e}")
    sys.exit(1)

# Test new functions
try:
    # Test broker profile selection
    profile = _get_broker_profile_for_selection("forex", "oanda")
    assert profile is not None, "OANDA profile not found"
    assert profile.broker_id == "oanda_us", f"Expected oanda_us, got {profile.broker_id}"
    print(f"? OANDA profile lookup works: {profile.display_name}")
    
    # Test market type choices
    assert len(MARKET_TYPE_CHOICES_NEW) > 5, "Not enough market type choices"
    print(f"? Market type choices generated: {len(MARKET_TYPE_CHOICES_NEW)} options")
    
    # Test validation
    assert _validate_broker_market_type("forex", "oanda", "margin_fx"), "MARGIN_FX should be valid for OANDA"
    print("? Broker market type validation works")
    
    print("\n? Dashboard broker classification integration successful!")
    
except Exception as e:
    print(f"? Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
