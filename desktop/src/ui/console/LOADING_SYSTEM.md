# Console Loading System

Non-blocking data loading system for terminal/console operations in Sopotek Quant System desktop application.

## Overview

The loading system prevents UI freezing when performing long-running operations like:
- Market data fetches
- Backtesting/simulations
- File I/O operations
- Data processing and calculations
- Database queries

## Components

### 1. **LoadingManager**
Central manager for async/threaded operations.

```python
from sqs_desktop.src.ui.console.loader import LoadingManager

loading_manager = LoadingManager(parent_widget)

# Run async operation
result = await loading_manager.load_async(
    task_id="unique_id",
    name="Display Name",
    coro=async_function(args)
)
```

**Signals:**
- `task_started(task_id, name)` - Task begins
- `task_progress(task_id, progress, message)` - Progress update (0-100%)
- `task_completed(task_id, elapsed)` - Task finished
- `task_error(task_id, error)` - Task failed
- `all_tasks_complete()` - All tasks done

### 2. **SystemConsole**
Updated QTextEdit-based console with loading UI.

```python
from sqs_desktop.src.ui.console.system_console import SystemConsole

console = SystemConsole()

# Show loading indicator
console.set_loading(True, "Loading data...")

# Update progress (0-100)
console.update_loading_progress(50)

# Log messages
console.log("Step 1 complete", level="INFO")

# Hide loading
console.clear_loading()
```

**Methods:**
- `set_loading(is_loading, message, progress)` - Show/hide loading state
- `update_loading_progress(progress)` - Update progress bar
- `clear_loading()` - Clear loading UI
- `log(message, level)` - Log with level

**Levels:** "INFO", "SUCCESS", "ERROR", "PROGRESS"

### 3. **ConsoleLoaderIntegration**
Connects LoadingManager signals to SystemConsole UI.

```python
from sqs_desktop.src.ui.console.loader import ConsoleLoaderIntegration

console = SystemConsole()
loading_manager = LoadingManager(console)
integration = ConsoleLoaderIntegration(console, loading_manager)

# Now loading_manager signals automatically update console
```

### 4. **LoadingIndicator**
ASCII spinner and progress bar utilities.

```python
from sqs_desktop.src.ui.console.loader import LoadingIndicator

# Get spinner frame (0-9)
spinner = LoadingIndicator.get_spinner(frame=0)  # "⠋"

# Get progress bar
bar = LoadingIndicator.get_progress_bar(progress=75, width=20)
# "[██████████░░░░░░░░] 75%"

console.log(f"{spinner} Processing... {bar}")
```

### 5. **LoadingTask**
Data class tracking individual task state.

```python
task = loading_manager.get_task("task_id")

# Properties:
print(task.status)     # LoadingState enum
print(task.progress)   # 0-100%
print(task.elapsed)    # Elapsed time
print(task.error)      # Error message if failed
print(str(task))       # Formatted string representation
```

## Usage Patterns

### Pattern 1: Simple Async Data Load

```python
async def fetch_market_data(symbols: list[str]) -> dict:
    """Fetch data from external API."""
    # Simulate network request
    await asyncio.sleep(2)
    return {"prices": {sym: 100.0 for sym in symbols}}

# In your controller/widget:
result = await loading_manager.load_async(
    task_id="market_fetch",
    name="Fetching Market Data",
    coro=fetch_market_data(["AAPL", "GOOGL"])
)
```

### Pattern 2: Progress Reporting

```python
async def backtest_strategy(trades: list) -> dict:
    """Run backtest with progress updates."""
    total = len(trades)
    results = []
    
    for i, trade in enumerate(trades):
        # Process trade
        result = await process_trade(trade)
        results.append(result)
        
        # Report progress
        progress = ((i + 1) / total) * 100
        # Loading manager will emit progress signal
        
        await asyncio.sleep(0.1)
    
    return {"total": total, "results": results}
```

### Pattern 3: Multiple Concurrent Operations

```python
# Launch several operations in parallel
tasks = [
    loading_manager.load_async(
        task_id=f"fetch_{symbol}",
        name=f"Fetching {symbol}",
        coro=fetch_data(symbol)
    )
    for symbol in ["AAPL", "GOOGL", "MSFT"]
]

# Wait for all to complete
results = await asyncio.gather(*tasks)

# Or use the signal:
loading_manager.all_tasks_complete.connect(on_all_done)
```

### Pattern 4: Manual Loading State Management

```python
# For non-async operations
console.set_loading(True, "Processing...")

# Long operation in separate thread
thread = QThread()
worker = MyWorker()
worker.moveToThread(thread)
worker.finished.connect(thread.quit)
worker.finished.connect(lambda: console.clear_loading())
thread.started.connect(worker.run)
thread.start()

# Update progress as work completes
worker.progress.connect(console.update_loading_progress)
```

### Pattern 5: Error Handling

```python
try:
    result = await loading_manager.load_async(
        task_id="risky_op",
        name="Risky Operation",
        coro=potentially_failing_op()
    )
except Exception as e:
    console.log(f"Operation failed: {e}", level="ERROR")
    # Clear loading UI
    console.clear_loading()
```

## Integration into App Controller

```python
# In your main app_controller.py
from sqs_desktop.src.ui.console.loader import LoadingManager, ConsoleLoaderIntegration

class AppController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize console
        self.console = SystemConsole()
        
        # Initialize loading system
        self.loading_manager = LoadingManager(self)
        self.loader_integration = ConsoleLoaderIntegration(
            self.console,
            self.loading_manager
        )
        
        # Now all long operations should use loading_manager
    
    async def load_portfolio_data(self):
        """Load portfolio data without freezing UI."""
        return await self.loading_manager.load_async(
            task_id="portfolio_load",
            name="Loading Portfolio",
            coro=self._fetch_portfolio()
        )
    
    async def _fetch_portfolio(self):
        """Actual data fetch."""
        # Fetch from server/database
        await asyncio.sleep(2)
        return {"portfolio": {...}}
```

## Best Practices

1. **Always use LoadingManager for network I/O**
   ```python
   # Good: Non-blocking
   await loading_manager.load_async(..., coro=fetch_data())
   
   # Bad: Freezes UI
   data = fetch_data()  # Don't do this synchronously
   ```

2. **Provide meaningful task names**
   ```python
   # Good: Clear what's happening
   name="Fetching Market Data for AAPL"
   
   # Bad: Too generic
   name="Loading"
   ```

3. **Use consistent task IDs**
   ```python
   # Good: Unique and descriptive
   task_id=f"market_fetch_{symbol}_{datetime.now().timestamp()}"
   
   # Bad: Not unique
   task_id="fetch"
   ```

4. **Report progress for long operations**
   ```python
   async def long_op(items):
       for i, item in enumerate(items):
           process(item)
           progress = (i / len(items)) * 100
           loading_manager.update_progress(task_id, progress)
   ```

5. **Always handle errors gracefully**
   ```python
   try:
       result = await loading_manager.load_async(...)
   except Exception as e:
       console.log(f"Error: {e}", level="ERROR")
   finally:
       console.clear_loading()
   ```

## Testing

```python
import pytest
from sqs_desktop.src.ui.console.loader import LoadingManager
from sqs_desktop.src.ui.console.system_console import SystemConsole

@pytest.mark.asyncio
async def test_loading_manager():
    """Test loading manager functionality."""
    manager = LoadingManager()
    
    async def dummy_task():
        await asyncio.sleep(0.1)
        return "done"
    
    result = await manager.load_async(
        task_id="test",
        name="Test Task",
        coro=dummy_task()
    )
    
    assert result == "done"
    task = manager.get_task("test")
    assert task.status == LoadingState.COMPLETE
```

## Performance Considerations

- **Thread Pool**: LoadingManager uses QThread for isolated event loops
- **Memory**: Tasks are stored in manager.tasks dict; clear old tasks periodically
- **Concurrency**: Use `asyncio.gather()` for parallel operations
- **UI Updates**: All UI updates happen on main thread via signals

## Troubleshooting

### UI Still Freezes
- Ensure operation is async/threaded, not blocking
- Check that signals are properly connected
- Verify asyncio.sleep() is used instead of time.sleep()

### Progress Not Updating
- Call `loading_manager.update_progress()` regularly
- Verify signals are connected to UI slots
- Check console.update_loading_progress() is being called

### Memory Leak
- Clear old tasks: `loading_manager.clear_tasks()`
- Disconnect signals when done: `signal.disconnect()`
- Close event loops in workers

## See Also

- [Example Usage](loader_example.py)
- [System Console](system_console.py)
- [PySide6 Async Pattern](https://doc.qt.io/qt-6/qthread.html)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
