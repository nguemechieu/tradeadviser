"""Ready-to-integrate loading system setup for app_controller.

Copy the key lines from this file into your app_controller.py to activate the loading system.
"""

# ============================================================================
# STEP 1: Add these imports to the top of app_controller.py
# ============================================================================

import asyncio  # Add if not already present
from sqs_desktop.src.ui.console.loader import (
    LoadingManager,
    ConsoleLoaderIntegration,
)


# ============================================================================
# STEP 2: Add these lines to AppController.__init__()
# ============================================================================

# After existing UI initialization, add:

class AppController(QMainWindow):
    """Main application controller."""
    
    def __init__(self):
        super().__init__()
        
        # ... existing code ...
        
        # Initialize console (if not already done)
        self.console = SystemConsole()
        
        # *** ADD LOADING SYSTEM HERE ***
        # Initialize loading manager for non-blocking operations
        self.loading_manager = LoadingManager(self)
        
        # Connect loading manager signals to console UI
        self.loader_integration = ConsoleLoaderIntegration(
            self.console,
            self.loading_manager
        )
        
        # Optional: Connect to other signals for UI control
        self.loading_manager.task_started.connect(self._on_task_started)
        self.loading_manager.all_tasks_complete.connect(self._on_all_tasks_done)
        
        self.console.log("✓ Loading system initialized", level="INFO")


# ============================================================================
# STEP 3: Add optional signal handlers (recommended for better UX)
# ============================================================================

    def _on_task_started(self, task_id: str, name: str) -> None:
        """Disable UI while loading."""
        # Disable buttons/controls during load
        self.load_button.setEnabled(False)
        self.trade_button.setEnabled(False)
    
    def _on_all_tasks_done(self) -> None:
        """Re-enable UI after loading."""
        # Re-enable buttons/controls
        self.load_button.setEnabled(True)
        self.trade_button.setEnabled(True)


# ============================================================================
# STEP 4: Example - Convert a blocking operation to async
# ============================================================================

# BEFORE (freezes UI):
def load_portfolio(self):
    """Load portfolio data - blocks UI!"""
    self.console.log("Loading portfolio...")
    portfolio = self.api.get_portfolio()  # ← FREEZES HERE
    self.console.log(f"Loaded {len(portfolio)} positions")
    return portfolio


# AFTER (non-blocking):
async def load_portfolio(self):
    """Load portfolio data without freezing UI."""
    return await self.loading_manager.load_async(
        task_id="portfolio_load",
        name="Loading Portfolio",
        coro=self._fetch_portfolio_impl()
    )

async def _fetch_portfolio_impl(self):
    """Actual portfolio fetch (can still be blocking)."""
    portfolio = self.api.get_portfolio()  # Still blocks, but in separate thread
    self.console.log(f"Loaded {len(portfolio)} positions")
    return portfolio


# ============================================================================
# STEP 5: Update button click handlers
# ============================================================================

# BEFORE (sync call):
def on_load_portfolio_clicked(self):
    """Portfolio button clicked."""
    data = self.load_portfolio()  # Blocks!
    self.update_portfolio_view(data)


# AFTER (async call):
def on_load_portfolio_clicked(self):
    """Portfolio button clicked - non-blocking."""
    # Schedule async operation without blocking
    asyncio.create_task(self._handle_load_portfolio())

async def _handle_load_portfolio(self):
    """Handle portfolio load asynchronously."""
    try:
        data = await self.load_portfolio()
        self.update_portfolio_view(data)
    except Exception as e:
        self.console.log(f"Failed to load portfolio: {e}", level="ERROR")


# ============================================================================
# STEP 6: Convert other long-running operations similarly
# ============================================================================

# Market data
async def load_market_data(self, symbols: list[str]):
    return await self.loading_manager.load_async(
        task_id=f"market_{datetime.now().timestamp()}",
        name=f"Fetching {len(symbols)} symbols",
        coro=self._fetch_market_impl(symbols)
    )

# Backtesting
async def run_backtest(self, config: dict):
    return await self.loading_manager.load_async(
        task_id="backtest_001",
        name="Running Backtest",
        coro=self._backtest_engine.run(config)
    )

# File operations
async def load_csv_file(self, filepath: str):
    return await self.loading_manager.load_async(
        task_id=f"csv_{Path(filepath).stem}",
        name=f"Loading {Path(filepath).name}",
        coro=self._load_csv_impl(filepath)
    )


# ============================================================================
# STEP 7: Minimal complete example
# ============================================================================

class MinimalAppController(QMainWindow):
    """Minimal example with loading system."""
    
    def __init__(self):
        super().__init__()
        self.console = SystemConsole()
        
        # Initialize loading system (3 lines!)
        self.loading_manager = LoadingManager(self)
        ConsoleLoaderIntegration(self.console, self.loading_manager)
        
        # Create button
        self.load_btn = QPushButton("Load Data")
        self.load_btn.clicked.connect(self.on_load_clicked)
    
    def on_load_clicked(self):
        """Button clicked - run async operation."""
        asyncio.create_task(self.load_data())
    
    async def load_data(self):
        """Load data without freezing UI."""
        result = await self.loading_manager.load_async(
            task_id="load_001",
            name="Loading Data",
            coro=self._simulate_load()
        )
        self.console.log(f"✓ Loaded: {result}")
    
    async def _simulate_load(self):
        """Simulated long-running operation."""
        import time
        time.sleep(5)  # Blocks, but in separate event loop
        return "Success!"


# ============================================================================
# STEP 8: Verification checklist
# ============================================================================

"""
After integrating, verify:

□ Imports added to app_controller.py
□ LoadingManager initialized in __init__()
□ ConsoleLoaderIntegration created
□ At least one method converted to async
□ Button handler uses asyncio.create_task()
□ Console logs show loading progress
□ UI remains responsive during loads
□ Progress bar appears/disappears correctly
□ No errors in console output

Expected behavior:
- Loading bar appears when operation starts
- Status message shows what's loading
- UI buttons/controls remain responsive
- Progress updates (if implemented)
- Loading bar disappears when done
- Result displayed in console
"""


# ============================================================================
# Summary of changes required
# ============================================================================

"""
Minimal integration requires:

1. Add 2 imports:
   - import asyncio
   - from sqs_desktop.src.ui.console.loader import (LoadingManager, ConsoleLoaderIntegration)

2. Initialize in __init__() (3 lines):
   self.loading_manager = LoadingManager(self)
   ConsoleLoaderIntegration(self.console, self.loading_manager)

3. Convert blocking methods to async:
   - Add async keyword
   - Wrap in loading_manager.load_async()

4. Update callers:
   - Replace direct calls with asyncio.create_task(method())
   - Add try/except for error handling

Total: ~30-50 lines of changes for full integration
Time: 15-30 minutes for initial setup
Testing: Run existing tests + manual verification

Benefits gained:
✓ No UI freezing during data loads
✓ Visual progress feedback
✓ Better user experience
✓ Professional appearance
✓ Concurrent operation support
"""
