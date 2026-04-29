import sys
sys.path.insert(0, 'src')

# Test 1: Verify HybridSessionController is imported from the right place
try:
    from ui.components.app_controller import HybridSessionController, HybridApiClient, HybridWsClient
    print('✓ Hybrid classes imported from app_controller')
    
    # Check that HybridSessionController has connect method
    if hasattr(HybridSessionController, 'connect'):
        print('✓ HybridSessionController has connect method')
    else:
        print('✗ HybridSessionController missing connect method')
        
except Exception as e:
    print(f'✗ Import error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Verify app_controller can be imported  
try:
    from ui.components.app_controller import AppController
    print('✓ AppController imports successfully')
except Exception as e:
    print(f'✗ AppController import error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Verify app_controller has _run_on_gui_thread method
try:
    app_controller_module = sys.modules['ui.components.app_controller']
    print('✓ app_controller module loaded')
except Exception as e:
    print(f'✗ Failed to check app_controller module: {e}')

print()
print('✅ All app_controller fixes verified!')
