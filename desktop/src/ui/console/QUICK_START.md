"""Quick integration guide for adding loading system to app_controller."""

# ============================================================================
# STEP 1: Import LoadingManager and ConsoleLoaderIntegration
# ============================================================================

# In sqs_desktop/src/ui/components/app_controller.py
from sqs_desktop.src.ui.console.loader import LoadingManager, ConsoleLoaderIntegration


# ============================================================================
# STEP 2: Initialize in AppController.__init__()
# ============================================================================

class AppController(QMainWindow):
    """Main application controller."""
    
    def __init__(self):
        super().__init__()
        
        # ... existing code ...
        
        # Initialize loading system
        self.loading_manager = LoadingManager(self)
        self.loader_integration = ConsoleLoaderIntegration(
            self.console,  # SystemConsole instance
            self.loading_manager
        )
        
        self.console.log("Loading system ready", level="INFO")


# ============================================================================
# STEP 3: Convert blocking operations to async
# ============================================================================

# BEFORE (blocking - freezes UI):
def load_market_data(self, symbols):
    data = self.market_api.fetch_prices(symbols)  # Blocks here!
    self.console.log(f"Loaded {len(data)} prices")
    return data


# AFTER (async - no freeze):
async def load_market_data(self, symbols):
    """Load market data without freezing UI."""
    return await self.loading_manager.load_async(
        task_id=f"market_data_{datetime.now().timestamp()}",
        name=f"Fetching {len(symbols)} symbols",
        coro=self._fetch_market_data_impl(symbols)
    )

async def _fetch_market_data_impl(self, symbols):
    """Actual implementation (can still be blocking, runs in thread)."""
    # This can still call sync code; it runs in separate event loop
    data = self.market_api.fetch_prices(symbols)
    self.console.log(f"Loaded {len(data)} prices")
    return data


# ============================================================================
# STEP 4: Update method calls from sync to async
# ============================================================================

# BEFORE:
def on_load_button_clicked(self):
    data = self.load_market_data(["AAPL", "GOOGL"])

# AFTER:
def on_load_button_clicked(self):
    """Button click handler - must use asyncio.create_task()."""
    # Can't await in sync method, so schedule the coroutine
    asyncio.create_task(self.load_market_data(["AAPL", "GOOGL"]))


# ============================================================================
# STEP 5: Add error handling
# ============================================================================

async def load_market_data(self, symbols):
    """Load market data with error handling."""
    try:
        return await self.loading_manager.load_async(
            task_id=f"market_data_{datetime.now().timestamp()}",
            name=f"Fetching {len(symbols)} symbols",
            coro=self._fetch_market_data_impl(symbols)
        )
    except Exception as e:
        self.console.log(f"Failed to load market data: {e}", level="ERROR")
        raise


# ============================================================================
# STEP 6: Enable UI controls conditionally during loading
# ============================================================================

class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ... existing code ...
        
        # Connect signals
        self.loading_manager.task_started.connect(self._on_loading_started)
        self.loading_manager.all_tasks_complete.connect(self._on_loading_complete)
    
    def _on_loading_started(self, task_id, name):
        """Disable UI during loading."""
        self.load_button.setEnabled(False)
        self.market_view.setEnabled(False)
    
    def _on_loading_complete(self):
        """Re-enable UI after loading."""
        self.load_button.setEnabled(True)
        self.market_view.setEnabled(True)


# ============================================================================
# STEP 7: Common operations to convert
# ============================================================================

# Database queries
async def fetch_portfolio(self):
    return await self.loading_manager.load_async(
        task_id="portfolio",
        name="Loading Portfolio",
        coro=self._db.get_portfolio()
    )

# File operations
async def load_csv_file(self, filepath):
    return await self.loading_manager.load_async(
        task_id=f"csv_{Path(filepath).stem}",
        name=f"Loading {Path(filepath).name}",
        coro=self._load_csv_impl(filepath)
    )

async def _load_csv_impl(self, filepath):
    import pandas as pd
    return pd.read_csv(filepath)

# API calls
async def fetch_account_info(self):
    return await self.loading_manager.load_async(
        task_id="account_info",
        name="Fetching Account Information",
        coro=self.broker_client.get_account()
    )

# Backtesting (heavy computation)
async def run_backtest(self, strategy_config):
    return await self.loading_manager.load_async(
        task_id="backtest_001",
        name="Running Backtest",
        coro=self._backtest_engine.run(strategy_config)
    )


# ============================================================================
# STEP 8: Full example with multiple operations
# ============================================================================

class TradingController(AppController):
    """Example trading controller with loading system."""
    
    async def initialize_trading_system(self):
        """Initialize all data without freezing UI."""
        try:
            # Load account info
            account = await self.loading_manager.load_async(
                task_id="init_account",
                name="Loading Account",
                coro=self._fetch_account()
            )
            
            # Load positions
            positions = await self.loading_manager.load_async(
                task_id="init_positions",
                name="Loading Positions",
                coro=self._fetch_positions()
            )
            
            # Load market data
            market_data = await self.loading_manager.load_async(
                task_id="init_market_data",
                name="Loading Market Data",
                coro=self._fetch_market_data()
            )
            
            self.console.log("✓ Trading system ready", level="SUCCESS")
            return {
                "account": account,
                "positions": positions,
                "market": market_data
            }
            
        except Exception as e:
            self.console.log(f"✗ Initialization failed: {e}", level="ERROR")
            raise


# ============================================================================
# STEP 9: Testing
# ============================================================================

import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_load_market_data():
    """Test loading market data."""
    controller = AppController()
    
    # Mock the API
    controller.market_api.fetch_prices = Mock(return_value={"AAPL": 150})
    
    # Load data
    result = await controller.load_market_data(["AAPL"])
    
    # Verify
    assert result == {"AAPL": 150}
    controller.market_api.fetch_prices.assert_called_once_with(["AAPL"])


# ============================================================================
# STEP 10: Performance optimization
# ============================================================================

# Parallel loads (faster)
async def load_all_data_parallel(self):
    """Load multiple data sources in parallel."""
    results = await asyncio.gather(
        self.loading_manager.load_async(
            task_id="data_1",
            name="Loading Data 1",
            coro=self._fetch_data_1()
        ),
        self.loading_manager.load_async(
            task_id="data_2",
            name="Loading Data 2",
            coro=self._fetch_data_2()
        ),
        self.loading_manager.load_async(
            task_id="data_3",
            name="Loading Data 3",
            coro=self._fetch_data_3()
        )
    )
    return results

# Sequential with timeout
async def load_with_timeout(self, coro, timeout=30):
    """Load with timeout."""
    try:
        return await asyncio.wait_for(
            self.loading_manager.load_async(
                task_id="timeout_task",
                name="Operation",
                coro=coro
            ),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        self.console.log("Operation timed out", level="ERROR")


# ============================================================================
# Summary of changes needed:
# ============================================================================

"""
1. Add imports: LoadingManager, ConsoleLoaderIntegration
2. Initialize in __init__(): self.loading_manager = LoadingManager()
3. Convert sync methods to async using await loading_manager.load_async()
4. Update callers to use asyncio.create_task() or await
5. Add error handling with try/except
6. Connect signals for UI enable/disable during loading
7. Update documentation/comments
8. Add unit tests
9. Test with real data loading scenarios
10. Monitor performance and optimize as needed

Key benefits:
✓ UI never freezes during data loads
✓ Progress visible to user
✓ Multiple operations can run concurrently
✓ Error handling is clear
✓ Easy to add new async operations
"""
