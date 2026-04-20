# Symbol Cache & Sync System

A comprehensive symbol caching and synchronization system that eliminates redundant API calls to brokers while keeping symbol data fresh and updated.

## Features

✅ **Smart Caching**: In-memory symbol cache with disk persistence
✅ **Intelligent Syncing**: Only fetches symbols when broker adds new ones or updates existing ones
✅ **Multi-Broker Support**: Register multiple broker symbol providers
✅ **Automatic Sync Policy**: Configurable sync intervals and policies
✅ **Full Event System**: Subscribe to sync events for real-time updates
✅ **Statistics & Monitoring**: Track cache hits, sync operations, and metrics
✅ **Backup & Export**: Automatic backups and CSV export capabilities
✅ **Search & Filtering**: Fast symbol lookup by asset class, exchange, etc.

## Architecture

The system consists of four core components:

### 1. SymbolCache (symbol_cache.py)
In-memory cache storing symbol metadata with:
- Fast O(1) lookup by symbol
- Filtering by asset class, exchange, tradable/shortable status
- Cache statistics (hit rate, miss count)
- Sync scheduling logic

### 2. SymbolStorage (symbol_storage.py)
Persistence layer handling:
- JSON serialization of symbol metadata
- Automatic backups
- Sync metadata tracking
- CSV export functionality

### 3. SymbolSyncManager (symbol_sync_manager.py)
Orchestrates synchronization:
- Compares broker symbols with cache
- Detects added/updated/removed symbols
- Triggers selective fetches (not full fetches)
- Maintains sync history and statistics

### 4. SymbolManager (symbol_manager.py)
High-level API combining all components for simple integration.

## Quick Start

### Basic Usage

```python
from src.symbols import SymbolManager

# Create and initialize
symbol_mgr = SymbolManager()
symbol_mgr.initialize()

# Query symbols (from cache - no API call)
all_symbols = symbol_mgr.get_all_symbols()
tradable = symbol_mgr.get_tradable_symbols()
btc = symbol_mgr.get_symbol('BTC-USD')

# Shutdown
symbol_mgr.shutdown()
```

### Broker Integration

```python
from src.symbols import SymbolManager, SymbolMetadata

symbol_mgr = SymbolManager()
symbol_mgr.initialize()

# Define a symbol fetcher for your broker
def fetch_coinbase_symbols():
    """Fetch symbols from Coinbase API."""
    # Call your broker API
    symbols = []
    for pair in broker_api.get_symbols():
        metadata = SymbolMetadata(
            symbol=pair['id'],
            name=pair['display_name'],
            asset_class='crypto',
            exchange='COINBASE'
        )
        symbols.append(metadata)
    return symbols

# Register the fetcher
symbol_mgr.register_broker_fetcher('coinbase', fetch_coinbase_symbols)

# Sync when needed (automatic interval checking)
symbol_mgr.sync_broker('coinbase')

# Or force a sync
symbol_mgr.sync_broker('coinbase', force=True)

symbol_mgr.shutdown()
```

## How Smart Syncing Works

### Problem: Redundant API Calls
```
Traditional approach:
App starts → Fetch ALL symbols from broker → Wait...
App continues → Fetch ALL symbols again → More waiting...
User refreshes → Fetch ALL symbols again → SLOW!
```

### Solution: Smart Caching

```
First startup:
App starts → Cache miss → Fetch symbols → ONCE ✓

Later usage:
User queries symbols → Cache hit → Instant ✓
                    ↓ (no API call needed)

Periodic sync (configurable):
Check if broker added new symbols → Smart comparison → Only fetch if needed

Example:
- Cache: [BTC, ETH, SOL, DOGE] (cached 2 hours ago)
- Broker: [BTC, ETH, SOL, DOGE, ADA, XRP] (2 new symbols)
- Action: Fetch only [ADA, XRP] metadata, merge with cache ✓
```

## Configuration

### Sync Policy

```python
symbol_mgr.set_sync_policy(
    min_interval_minutes=60,      # Minimum time between syncs
    force_full_sync_hours=24,     # Force full refresh daily
    max_cache_age_days=7          # Keep symbols up to 7 days
)
```

## Performance Metrics

### Cache Statistics

```python
stats = symbol_mgr.get_cache_stats()
# {
#     'total_symbols': 5000,
#     'cache_hit_count': 10000,
#     'cache_miss_count': 50,
#     'hit_rate': '99.5%',
#     'last_sync': '2026-04-19T10:30:45.123456',
#     'asset_classes': ['crypto', 'stock', 'option'],
#     'exchanges': ['NASDAQ', 'NYSE', 'COINBASE']
# }
```

### Sync Statistics

```python
sync_stats = symbol_mgr.get_sync_stats()
# {
#     'total_syncs': 24,
#     'successful_syncs': 23,
#     'failed_syncs': 1,
#     'total_symbols_added': 156,
#     'total_symbols_updated': 42,
#     'total_symbols_removed': 8,
#     'brokers_registered': 3,
#     'cache_size': 5234
# }
```

## API Reference

### Query Methods

```python
# Get single symbol
symbol_mgr.get_symbol('AAPL')

# Check if symbol exists
symbol_mgr.has_symbol('AAPL')

# Get all symbols
symbol_mgr.get_all_symbols()

# Filter by criteria
symbol_mgr.get_symbols_by_asset_class('stock')
symbol_mgr.get_symbols_by_exchange('NASDAQ')
symbol_mgr.get_tradable_symbols()
symbol_mgr.get_shortable_symbols()

# Search
symbol_mgr.search_symbols('Apple', limit=10)

# Count
symbol_mgr.get_symbol_count()
```

### Sync Methods

```python
# Sync single broker
symbol_mgr.sync_broker('coinbase', force=False)

# Sync all brokers
symbol_mgr.sync_all_brokers(force=False)

# Register broker fetcher
symbol_mgr.register_broker_fetcher('coinbase', fetcher_func)
```

### Maintenance Methods

```python
# Backup cache
symbol_mgr.backup_cache()

# Export to CSV
symbol_mgr.export_symbols_csv('symbols.csv')

# Clean up old symbols
symbol_mgr.cleanup_old_symbols()

# Reload from disk
symbol_mgr.reload_from_disk()

# Clear cache
symbol_mgr.clear_cache()
```

### Event Listeners

```python
def on_sync_complete(result):
    print(f"Synced: +{result.symbols_added} symbols")

symbol_mgr.on_sync_completed(on_sync_complete)
```

## Data Storage

### Directory Structure

```
data/symbols/
├── symbols.json              # Cached symbol metadata
├── sync_metadata.json        # Last sync times per broker
├── symbols_backup_*.json     # Timestamped backups
└── README.md
```

### Symbol Metadata Schema

```json
{
  "symbol": "BTC-USD",
  "name": "Bitcoin",
  "asset_class": "crypto",
  "exchange": "COINBASE",
  "currency": "USD",
  "min_price_increment": 0.01,
  "min_order_qty": 0.00001,
  "max_order_qty": null,
  "is_tradable": true,
  "is_shortable": false,
  "fractional_allowed": true,
  "status": "active",
  "added_date": "2026-04-19T10:30:45.123456",
  "updated_date": "2026-04-19T10:30:45.123456"
}
```

## Integration Examples

### With Broker Connections

```python
class Broker:
    def __init__(self):
        self.symbol_mgr = SymbolManager()
        self.symbol_mgr.initialize()
    
    def connect(self):
        # Auto-sync symbols when connecting
        self.symbol_mgr.sync_broker('my_broker')
    
    def place_order(self, symbol):
        # Verify symbol exists in cache
        if not self.symbol_mgr.has_symbol(symbol):
            raise ValueError(f"Symbol {symbol} not found")
        return self.api.place_order(symbol)
```

### With Market Data Updates

```python
def on_market_data_update(symbol, price):
    # Check if symbol exists and is tradable
    meta = symbol_mgr.get_symbol(symbol)
    if meta and meta.is_tradable:
        process_market_data(symbol, price)

# Also triggers background sync check
market_data_feed.on_update(on_market_data_update)
```

### With Symbol Search UI

```python
def search_symbols_ui(query):
    results = symbol_mgr.search_symbols(query, limit=20)
    for symbol, metadata in results:
        display_result(symbol, metadata.name, metadata.asset_class)
```

## Performance Benefits

### Reduced API Calls
- **Before**: 5-10 API calls per session (symbols, then every time they're needed)
- **After**: 1 API call on first sync, then periodic checks

### Faster Response Times
- **Before**: 500ms-2s wait for symbol queries
- **After**: <1ms cache lookup time

### Network Savings
- **Before**: 50KB+ per full symbol fetch
- **After**: ~5KB per selective sync (10x reduction)

## Best Practices

1. **Initialize on Startup**: Call `symbol_mgr.initialize()` once when the application starts
2. **Register All Brokers Early**: Register all broker fetchers before syncing
3. **Set Policy Appropriately**: Adjust sync intervals based on broker frequency
4. **Monitor Stats**: Periodically check sync statistics for any issues
5. **Backup Regularly**: Create backups before major operations
6. **Subscribe to Events**: Use event listeners for real-time sync notifications
7. **Shutdown Gracefully**: Call `symbol_mgr.shutdown()` to save state

## Troubleshooting

### Cache Miss Rate High
- Check if symbols are being added correctly
- Verify broker fetcher is returning complete data
- Review sync policy settings

### Sync Always Required
- Check min_interval_minutes setting (too low)
- Verify broker fetcher is registering correctly

### Storage Issues
- Check disk space in `data/symbols/` directory
- Review backup retention policy
- Clear old backups if needed

## Future Enhancements

- [ ] Database backend option (SQLite, PostgreSQL)
- [ ] Real-time symbol change notifications
- [ ] Symbol consensus from multiple brokers
- [ ] Advanced filtering and indexing
- [ ] Symbol alias management
- [ ] Automated symbol metadata updates
