"""Symbol System Integration Guide

This module shows how to integrate the symbol caching system with brokers
and how to use it in the application.
"""

from src.symbols import SymbolManager, SymbolMetadata
from typing import List


class BrokerSymbolProvider:
    """Template for integrating broker symbol data."""
    
    def __init__(self, symbol_manager: SymbolManager):
        self.symbol_manager = symbol_manager
    
    def setup(self):
        """Setup broker symbol provider."""
        # Initialize symbol manager
        self.symbol_manager.initialize()
        
        # Configure sync policy
        self.symbol_manager.set_sync_policy(
            min_interval_minutes=60,      # Sync at least every hour
            force_full_sync_hours=24,     # Force full sync daily
            max_cache_age_days=7          # Keep symbols up to 7 days
        )
        
        # Register this broker's symbol fetcher
        self.symbol_manager.register_broker_fetcher(
            'coinbase',
            self.fetch_coinbase_symbols
        )
        
        # Listen for sync events
        self.symbol_manager.on_sync_completed(self._on_sync_completed)
    
    def fetch_coinbase_symbols(self) -> List[SymbolMetadata]:
        """
        Fetch symbols from Coinbase.
        This is called when sync is triggered.
        """
        # TODO: Replace with actual Coinbase API call
        symbols = []
        
        # Example: fetching crypto symbols
        crypto_pairs = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD']
        
        for pair in crypto_pairs:
            metadata = SymbolMetadata(
                symbol=pair,
                name=f"Coinbase {pair}",
                asset_class='crypto',
                exchange='COINBASE',
                currency='USD',
                min_price_increment=0.01,
                min_order_qty=0.00001,
                is_tradable=True,
                is_shortable=False,
                fractional_allowed=True
            )
            symbols.append(metadata)
        
        return symbols
    
    def _on_sync_completed(self, result):
        """Callback when sync completes."""
        print(f"Sync completed: {result}")
        print(f"Added: {result.symbols_added}, Updated: {result.symbols_updated}")
    
    def should_sync(self, broker: str) -> bool:
        """Check if broker needs sync."""
        # This is automatically checked by sync manager
        # but you can manually check here
        from src.symbols import SymbolCache
        cache = SymbolCache()
        return cache.should_sync_with_broker(broker, min_interval_minutes=60)
    
    def get_trading_symbols(self) -> List[str]:
        """Get list of symbols available for trading."""
        return self.symbol_manager.get_tradable_symbols()
    
    def search_symbol(self, query: str) -> List[tuple]:
        """Search for a symbol."""
        return self.symbol_manager.search_symbols(query)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_basic_usage():
    """Basic usage of symbol manager."""
    
    # Create symbol manager
    symbol_mgr = SymbolManager(storage_dir="data/symbols")
    
    # Initialize
    symbol_mgr.initialize()
    
    # Sync from a broker (automatic checking if sync needed)
    if symbol_mgr.sync_broker('coinbase'):
        print("Sync successful!")
    
    # Query symbols
    all_symbols = symbol_mgr.get_all_symbols()
    print(f"Total symbols: {len(all_symbols)}")
    
    # Get specific symbol
    btc = symbol_mgr.get_symbol('BTC-USD')
    if btc:
        print(f"BTC: {btc.name}, Tradable: {btc.is_tradable}")
    
    # Search
    results = symbol_mgr.search_symbols('BTC')
    print(f"Search results: {results}")
    
    # Shutdown
    symbol_mgr.shutdown()


def example_with_broker_integration():
    """Example with broker integration."""
    
    symbol_mgr = SymbolManager()
    symbol_mgr.initialize()
    
    # Define broker symbol fetcher
    def fetch_symbols_from_broker() -> List[SymbolMetadata]:
        """Fetch from your actual broker API."""
        # Call your broker API here
        # broker_api = BrokerAPI()
        # return broker_api.get_symbols()
        return []
    
    # Register the fetcher
    symbol_mgr.register_broker_fetcher('my_broker', fetch_symbols_from_broker)
    
    # Sync when needed
    symbol_mgr.sync_broker('my_broker', force=True)
    
    # Use cached symbols
    symbols = symbol_mgr.get_tradable_symbols()
    for symbol in symbols[:5]:
        meta = symbol_mgr.get_symbol(symbol)
        print(f"{symbol}: {meta.name}")
    
    symbol_mgr.shutdown()


def example_auto_sync_on_connect():
    """Example: Auto-sync when broker connects."""
    
    symbol_mgr = SymbolManager()
    symbol_mgr.initialize()
    
    class MyBroker:
        def __init__(self, symbol_mgr):
            self.symbol_mgr = symbol_mgr
            self.connected = False
        
        def connect(self):
            """Connect to broker."""
            self.connected = True
            
            # Auto-sync symbols when connected
            if self.symbol_mgr.sync_broker('my_broker'):
                print("Symbols synced after broker connection")
        
        def get_symbols(self) -> List[str]:
            """Get available symbols."""
            return self.symbol_mgr.get_tradable_symbols()
    
    broker = MyBroker(symbol_mgr)
    broker.connect()
    
    symbols = broker.get_symbols()
    print(f"Available symbols: {len(symbols)}")
    
    symbol_mgr.shutdown()


def example_sync_statistics():
    """Example: View sync statistics."""
    
    symbol_mgr = SymbolManager()
    symbol_mgr.initialize()
    
    # Get cache statistics
    cache_stats = symbol_mgr.get_cache_stats()
    print("Cache Stats:")
    print(f"  Total symbols: {cache_stats['total_symbols']}")
    print(f"  Hit rate: {cache_stats['hit_rate']}")
    print(f"  Asset classes: {cache_stats['asset_classes']}")
    
    # Get sync statistics
    sync_stats = symbol_mgr.get_sync_stats()
    print("\nSync Stats:")
    print(f"  Total syncs: {sync_stats['total_syncs']}")
    print(f"  Successful: {sync_stats['successful_syncs']}")
    print(f"  Failed: {sync_stats['failed_syncs']}")
    print(f"  Total added: {sync_stats['total_symbols_added']}")
    
    # Get sync history
    history = symbol_mgr.get_sync_history('coinbase', limit=10)
    for result in history:
        print(f"  {result.timestamp}: {result}")
    
    symbol_mgr.shutdown()


def example_maintenance():
    """Example: Cache maintenance operations."""
    
    symbol_mgr = SymbolManager()
    symbol_mgr.initialize()
    
    # Backup cache
    backup_file = symbol_mgr.backup_cache()
    print(f"Backed up to: {backup_file}")
    
    # Export to CSV
    symbol_mgr.export_symbols_csv('symbols_export.csv')
    print("Exported to CSV")
    
    # Clean up old symbols
    removed = symbol_mgr.cleanup_old_symbols()
    print(f"Cleaned up {removed} old symbols")
    
    symbol_mgr.shutdown()


if __name__ == '__main__':
    print("Symbol System Integration Examples\n")
    
    # Run examples
    print("1. Basic Usage:")
    example_basic_usage()
    
    print("\n2. With Broker Integration:")
    example_with_broker_integration()
    
    print("\n3. Auto-sync on Connect:")
    example_auto_sync_on_connect()
    
    print("\n4. Sync Statistics:")
    example_sync_statistics()
    
    print("\n5. Maintenance:")
    example_maintenance()
