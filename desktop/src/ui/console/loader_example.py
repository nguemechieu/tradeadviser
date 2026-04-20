"""Example usage of the loading system for terminal/console operations.

This demonstrates how to use the LoadingManager and SystemConsole integration
to prevent UI freezing during data loading operations.
"""

import asyncio
from .loader import LoadingManager, ConsoleLoaderIntegration, LoadingIndicator
from .system_console import SystemConsole


async def example_long_operation(duration: int = 5) -> dict:
    """Simulate a long-running operation (e.g., data fetch, calculation).
    
    Args:
        duration: Simulated operation duration in seconds
        
    Returns:
        Result dictionary
    """
    steps = 10
    step_duration = duration / steps
    
    for i in range(steps):
        await asyncio.sleep(step_duration)
        # Progress can be tracked here
        progress = ((i + 1) / steps) * 100
        # This would be reported back to the UI
    
    return {"status": "success", "data": "Operation complete"}


class LoaderDemoWidget(SystemConsole):
    """Demo widget showing loading system integration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize loading system
        self.loading_manager = LoadingManager(self)
        self.loader_integration = ConsoleLoaderIntegration(self, self.loading_manager)
        
        # Connect console-specific signals
        self.loading_manager.task_progress.connect(self._on_progress)
        
        self.log("Loading system initialized. Ready for async operations.")
    
    def _on_progress(self, task_id: str, progress: float, message: str) -> None:
        """Update console with progress."""
        self.update_loading_progress(int(progress))
        if message:
            self.log(message)
    
    async def load_data_async(self) -> None:
        """Example: Load data asynchronously without freezing UI."""
        try:
            self.set_loading(True, "Loading data...")
            
            # Run the long operation through the loading manager
            result = await self.loading_manager.load_async(
                task_id="data_load_001",
                name="Data Loading",
                coro=example_long_operation(5)
            )
            
            self.log(f"✓ Data loaded: {result}", level="SUCCESS")
            
        except Exception as e:
            self.log(f"✗ Failed to load data: {e}", level="ERROR")
        finally:
            self.clear_loading()


# ============================================================================
# Usage patterns
# ============================================================================

"""
PATTERN 1: Using LoadingManager with async functions
----------------------------------------------------

async def fetch_market_data(symbols: list[str]) -> dict:
    '''Fetch data from market API.'''
    # ... actual implementation ...
    return data

# In your UI class:
loading_manager = LoadingManager(self)

# Run async operation without blocking UI
result = await loading_manager.load_async(
    task_id="market_data_fetch",
    name="Fetching Market Data",
    coro=fetch_market_data(["AAPL", "GOOGL"])
)


PATTERN 2: Loading with progress updates
-----------------------------------------

async def process_data_with_progress(data: list) -> dict:
    '''Process data with progress tracking.'''
    total = len(data)
    for i, item in enumerate(data):
        # ... process item ...
        progress = ((i + 1) / total) * 100
        # Progress would be reported here
        await asyncio.sleep(0.1)  # Simulate work
    return {"processed": total}


PATTERN 3: Multiple concurrent operations
-------------------------------------------

# Run multiple loading tasks concurrently
tasks = [
    loading_manager.load_async(
        task_id=f"task_{i}",
        name=f"Task {i}",
        coro=long_operation()
    )
    for i in range(3)
]

results = await asyncio.gather(*tasks)


PATTERN 4: SystemConsole with loading
--------------------------------------

console = SystemConsole()
console.set_loading(True, "Loading: 50%")
console.update_loading_progress(50)
console.log("Data chunk 1 loaded", level="INFO")
console.log("Data chunk 2 loaded", level="INFO")
console.clear_loading()


PATTERN 5: ASCII loading indicators
------------------------------------

# Get spinner for animation
spinner = LoadingIndicator.get_spinner(frame=0)  # "⠋"

# Get progress bar
bar = LoadingIndicator.get_progress_bar(progress=75)  # "[██████████░░░░░░░░] 75%"

console.log(f"{spinner} Loading: {bar}")


PATTERN 6: Error handling with loading state
---------------------------------------------

try:
    result = await loading_manager.load_async(
        task_id="critical_operation",
        name="Critical Operation",
        coro=risky_operation()
    )
except Exception as e:
    console.log(f"Operation failed: {e}", level="ERROR")
finally:
    console.clear_loading()  # Always clear loading state


PATTERN 7: Batch operations
----------------------------

async def batch_load_files(file_paths: list[str]) -> list:
    '''Load multiple files with progress.'''
    results = []
    for i, path in enumerate(file_paths):
        data = await load_file(path)
        results.append(data)
        progress = ((i + 1) / len(file_paths)) * 100
        # Report progress: progress
    return results
"""
