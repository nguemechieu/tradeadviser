"""Symbol Manager - High-level interface for symbol operations."""

import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime

from .symbol_cache import SymbolCache, SymbolMetadata
from .symbol_storage import SymbolStorage
from .symbol_sync_manager import SymbolSyncManager, SyncPolicy, SyncResult


class SymbolManager:
    """Main interface for symbol cache, storage, and sync operations."""
    
    def __init__(self, storage_dir: str = "data/symbols", logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.cache = SymbolCache(logger=self.logger)
        self.storage = SymbolStorage(storage_dir=storage_dir)
        self.sync_manager = SymbolSyncManager(self.cache, self.storage, logger=self.logger)
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the symbol manager."""
        try:
            self.sync_manager.initialize()
            self._initialized = True
            self.logger.info("Symbol manager initialized")
            return True
        except Exception as e:
            self.logger.exception(f"Error initializing symbol manager: {e}")
            return False
    
    def shutdown(self):
        """Shutdown symbol manager."""
        self.sync_manager.shutdown()
        self._initialized = False
        self.logger.info("Symbol manager shutdown")
    
    # ===================
    # Broker Integration
    # ===================
    
    def register_broker_fetcher(self, broker: str, 
                               fetcher: Callable[[], List[SymbolMetadata]]):
        """Register a broker symbol fetcher function."""
        self.sync_manager.register_broker(broker, fetcher)
    
    def sync_broker(self, broker: str, force: bool = False) -> bool:
        """Sync symbols from a broker."""
        result = self.sync_manager.sync_broker_symbols(broker, force=force)
        self.logger.info(f"Sync result: {result}")
        return result.success
    
    def sync_all_brokers(self, force: bool = False) -> bool:
        """Sync all brokers."""
        results = self.sync_manager.sync_all_brokers(force=force)
        success_count = sum(1 for r in results if r.success)
        self.logger.info(f"Synced {success_count}/{len(results)} brokers")
        return all(r.success for r in results)
    
    # ===================
    # Symbol Queries
    # ===================
    
    def get_symbol(self, symbol: str) -> Optional[SymbolMetadata]:
        """Get symbol metadata."""
        return self.cache.get_symbol(symbol)
    
    def has_symbol(self, symbol: str) -> bool:
        """Check if symbol exists in cache."""
        return self.cache.has_symbol(symbol)
    
    def get_all_symbols(self) -> List[str]:
        """Get all cached symbols."""
        return self.cache.get_all_symbols()
    
    def get_symbols_by_asset_class(self, asset_class: str) -> List[str]:
        """Get symbols by asset class."""
        return self.cache.get_symbols_by_asset_class(asset_class)
    
    def get_symbols_by_exchange(self, exchange: str) -> List[str]:
        """Get symbols by exchange."""
        return self.cache.get_symbols_by_exchange(exchange)
    
    def get_tradable_symbols(self) -> List[str]:
        """Get all tradable symbols."""
        return self.cache.get_tradable_symbols()
    
    def get_shortable_symbols(self) -> List[str]:
        """Get all shortable symbols."""
        return self.cache.get_shortable_symbols()
    
    def search_symbols(self, query: str, limit: int = 20) -> List[tuple]:
        """Search for symbols."""
        return self.cache.search_symbols(query, limit=limit)
    
    def get_symbol_count(self) -> int:
        """Get total symbol count."""
        return self.cache.metrics.total_symbols
    
    # ===================
    # Statistics
    # ===================
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def get_sync_stats(self) -> dict:
        """Get sync statistics."""
        return self.sync_manager.get_sync_stats()
    
    def get_sync_history(self, broker: Optional[str] = None) -> List[SyncResult]:
        """Get sync history."""
        return self.sync_manager.get_sync_history(broker=broker)
    
    # ===================
    # Configuration
    # ===================
    
    def set_sync_policy(self, 
                       min_interval_minutes: int = 60,
                       force_full_sync_hours: int = 24,
                       max_cache_age_days: int = 7):
        """Configure sync policy."""
        policy = SyncPolicy(
            min_interval_minutes=min_interval_minutes,
            force_full_sync_hours=force_full_sync_hours,
            max_cache_age_days=max_cache_age_days
        )
        self.sync_manager.set_sync_policy(policy)
    
    # ===================
    # Maintenance
    # ===================
    
    def cleanup_old_symbols(self) -> int:
        """Remove old/delisted symbols."""
        return self.sync_manager.cleanup_old_symbols()
    
    def backup_cache(self) -> Optional[str]:
        """Create a backup of symbol cache."""
        backup_path = self.storage.backup_symbols()
        return str(backup_path) if backup_path else None
    
    def export_symbols_csv(self, filepath: str) -> bool:
        """Export symbols to CSV."""
        return self.storage.export_to_csv(self.cache.symbols, filepath)
    
    # ===================
    # Event Listeners
    # ===================
    
    def on_sync_completed(self, callback: Callable[[SyncResult], None]):
        """Register callback for sync completion."""
        self.sync_manager.subscribe(callback)
    
    # ===================
    # Utility
    # ===================
    
    def clear_cache(self):
        """Clear all symbols from cache."""
        self.cache.clear()
        self.logger.warning("Symbol cache cleared")
    
    def reload_from_disk(self) -> int:
        """Reload symbols from disk."""
        self.clear_cache()
        symbols = self.storage.load_symbols()
        return self.cache.add_symbols(list(symbols.values()))
