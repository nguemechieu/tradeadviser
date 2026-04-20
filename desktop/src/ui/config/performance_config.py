# UI Performance Configuration for Sopotek Quant System

# Table Display Settings
TABLE_MAX_VISIBLE_ROWS = 100              # Show only N most recent rows per table
TABLE_PAGINATION_BATCH_SIZE = 50          # Load rows in batches of N
TABLE_LAZY_LOAD_DELAY_MS = 10             # Delay between batch loads (milliseconds)

# Signal Throttling Settings
SIGNAL_THROTTLE_MS = 500                  # Minimum time between signal handler invocations
TICKER_SIGNAL_THROTTLE_MS = 1000          # Ticker update throttle
CANDLE_SIGNAL_THROTTLE_MS = 500           # Candle update throttle
EQUITY_SIGNAL_THROTTLE_MS = 1000          # Equity update throttle
ORDERBOOK_SIGNAL_THROTTLE_MS = 500        # Orderbook update throttle

# Refresh Interval Settings
POSITIONS_REFRESH_INTERVAL_MS = 2000      # Refresh positions every N milliseconds
OPEN_ORDERS_REFRESH_INTERVAL_MS = 2000    # Refresh open orders every N milliseconds
ASSETS_REFRESH_INTERVAL_MS = 5000         # Refresh assets every N milliseconds
ORDER_HISTORY_REFRESH_INTERVAL_MS = 5000  # Refresh order history every N milliseconds
TRADE_HISTORY_REFRESH_INTERVAL_MS = 5000  # Refresh trade history every N milliseconds

# Chart Rendering Settings
CHART_MAX_CANDLES = 500                   # Maximum candles to render per chart
CHART_CACHE_ENABLED = True                # Enable plot caching for performance
CHART_ANIMATION_ENABLED = False           # Disable animations for speed

# Market Watch Settings
MARKET_WATCH_MAX_SYMBOLS = 50             # Maximum symbols to display
MARKET_WATCH_POLL_INTERVAL_MS = 1000      # Ticker polling interval

# AI Signal Monitor Settings
AI_SIGNAL_TABLE_MAX_ROWS = 50             # Maximum AI signal rows to display
AI_SIGNAL_TABLE_REFRESH_MIN_MS = 500      # Minimum refresh interval

# Performance Monitoring Settings
PERF_LOG_THRESHOLD_MS = 100               # Log operations exceeding N milliseconds
PERF_MONITORING_ENABLED = True            # Enable performance monitoring
PERF_LOG_UI_OPERATIONS = True             # Log slow UI operations

# Worker Thread Settings
WORKER_POOL_SIZE = 4                      # Number of background worker threads
ASYNC_BATCH_SIZE = 10                     # Items per batch for async operations

# Debouncing Settings
SEARCH_FILTER_DEBOUNCE_MS = 300           # Debounce for search/filter inputs
RESIZE_DEBOUNCE_MS = 200                  # Debounce for window resize events
KEYBOARD_INPUT_DEBOUNCE_MS = 100          # Debounce for keyboard inputs

# Memory Optimization
HISTORY_CACHE_MAX_SIZE = 10000            # Maximum cached historical records
QUOTE_CACHE_MAX_AGE_SECONDS = 60          # Discard quotes older than N seconds

# Feature Flags
ENABLE_VIRTUAL_SCROLLING = True           # Use virtual scrolling for tables
ENABLE_ASYNC_TABLE_LOADING = True         # Use lazy loading for large tables
ENABLE_WORKER_THREADS = True              # Use background threads for I/O
ENABLE_SIGNAL_THROTTLING = True           # Throttle high-frequency signals
BATCH_UI_UPDATES = True                   # Batch UI updates for better performance
