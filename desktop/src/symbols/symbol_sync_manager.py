"""Symbol Sync Manager - Orchestrates symbol syncing with brokers."""

import logging
from typing import Dict, List, Callable, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .symbol_cache import SymbolCache, SymbolMetadata
from .symbol_storage import SymbolStorage


@dataclass
class SyncResult:
    """Result of a sync operation."""
    broker: str
    success: bool
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_removed: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""
    error: Optional[str] = None
    
    def __str__(self) -> str:
        return (f"SyncResult({self.broker}): "
               f"+{self.symbols_added} ~{self.symbols_updated} -{self.symbols_removed} "
               f"{'✓' if self.success else '✗'}")


@dataclass
class SyncPolicy:
    """Policy for when to sync with broker."""
    min_interval_minutes: int = 60  # Minimum time between syncs
    force_full_sync_hours: int = 24  # Force full sync periodically
    max_cache_age_days: int = 7  # Maximum age of cached symbols
    auto_sync: bool = True  # Automatically sync when broker connects
    notify_on_changes: bool = True  # Notify on symbol changes


class SymbolSyncManager:
    """Manages symbol synchronization with brokers."""
    
    def __init__(self, cache: SymbolCache, storage: SymbolStorage, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.cache = cache
        self.storage = storage
        self.sync_policy = SyncPolicy()
        self.sync_history: List[SyncResult] = []
        self._sync_listeners: List[Callable[[SyncResult], None]] = []
        self._broker_symbol_fetchers: Dict[str, Callable] = {}  # broker -> fetcher function
        self._last_symbol_hashes: Dict[str, str] = {}  # Track symbol list changes
    
    # ===================
    # Initialization
    # ===================
    
    def initialize(self) -> bool:
        """Initialize from storage."""
        try:
            # Load cached symbols
            symbols = self.storage.load_symbols()
            for symbol, metadata in symbols.items():
                self.cache.add_symbol(metadata)
            
            # Load sync metadata
            metadata = self.storage.load_sync_metadata()
            for broker, last_sync_str in metadata.items():
                if isinstance(last_sync_str, str):
                    # Reconstruct last sync times
                    try:
                        last_sync = datetime.fromisoformat(last_sync_str)
                        self.cache._last_broker_check[broker] = last_sync
                    except:
                        pass
            
            self.logger.info(f"Initialized symbol sync manager with {len(symbols)} cached symbols")
            return True
        except Exception as e:
            self.logger.exception(f"Error initializing sync manager: {e}")
            return False
    
    def shutdown(self):
        """Shutdown and save state."""
        try:
            # Save symbols
            self.storage.save_symbols(self.cache.symbols)
            
            # Save sync metadata
            metadata = {
                broker: dt.isoformat()
                for broker, dt in self.cache._last_broker_check.items()
            }
            self.storage.save_sync_metadata(metadata)
            
            self.logger.info("Symbol sync manager shutdown - state saved")
        except Exception as e:
            self.logger.exception(f"Error during shutdown: {e}")
    
    # ===================
    # Broker Registration
    # ===================
    
    def register_broker(self, broker_name: str, 
                       symbol_fetcher: Callable[[], List[SymbolMetadata]]):
        """Register a broker symbol fetcher."""
        self._broker_symbol_fetchers[broker_name] = symbol_fetcher
        self.logger.info(f"Registered symbol fetcher for broker: {broker_name}")
    
    def unregister_broker(self, broker_name: str):
        """Unregister a broker."""
        if broker_name in self._broker_symbol_fetchers:
            del self._broker_symbol_fetchers[broker_name]
            self.logger.info(f"Unregistered symbol fetcher for broker: {broker_name}")
    
    # ===================
    # Sync Operations
    # ===================
    
    def sync_broker_symbols(self, broker: str, force: bool = False) -> SyncResult:
        """Sync symbols from a broker."""
        # Check if sync is needed
        if not force and not self.cache.should_sync_with_broker(broker, self.sync_policy.min_interval_minutes):
            self.logger.debug(f"Skipping sync for {broker}: min interval not elapsed")
            return SyncResult(broker, True, message="Skipped - min interval not elapsed")
        
        # Check if fetcher is registered
        if broker not in self._broker_symbol_fetchers:
            self.logger.warning(f"No symbol fetcher registered for {broker}")
            return SyncResult(broker, False, error="No fetcher registered")
        
        try:
            # Fetch symbols from broker
            self.logger.info(f"Fetching symbols from broker: {broker}")
            fetcher = self._broker_symbol_fetchers[broker]
            new_symbols = fetcher()
            
            # Compare with cache
            result = self._compare_and_update(broker, new_symbols)
            
            # Record sync
            self.cache.record_sync(broker, full_sync=True)
            
            # Save state
            self.storage.save_symbols(self.cache.symbols)
            
            # Notify listeners
            self._notify_listeners(result)
            
            # Track in history
            self.sync_history.append(result)
            
            return result
        
        except Exception as e:
            self.logger.exception(f"Error syncing symbols from {broker}: {e}")
            return SyncResult(broker, False, error=str(e))
    
    def sync_all_brokers(self, force: bool = False) -> List[SyncResult]:
        """Sync symbols from all registered brokers."""
        results = []
        for broker in self._broker_symbol_fetchers.keys():
            result = self.sync_broker_symbols(broker, force)
            results.append(result)
        
        return results
    
    # ===================
    # Symbol Comparison
    # ===================
    
    def _compare_and_update(self, broker: str, new_symbols: List[SymbolMetadata]) -> SyncResult:
        """Compare new symbols with cache and update."""
        result = SyncResult(broker=broker, success=True)
        
        # Get current symbols for this broker/asset class
        current_symbols = set(self.cache.get_all_symbols())
        new_symbol_set = set(sym.symbol for sym in new_symbols)
        
        # Calculate changes
        added_symbols = new_symbol_set - current_symbols
        removed_symbols = current_symbols - new_symbol_set
        
        result.symbols_added = len(added_symbols)
        result.symbols_removed = len(removed_symbols)
        
        # Add new symbols
        for symbol in added_symbols:
            sym_data = next((s for s in new_symbols if s.symbol == symbol), None)
            if sym_data:
                self.cache.add_symbol(sym_data)
                self.logger.info(f"Added symbol from {broker}: {symbol}")
        
        # Update existing symbols
        for symbol_meta in new_symbols:
            if symbol_meta.symbol in current_symbols:
                existing = self.cache.get_symbol(symbol_meta.symbol)
                if existing and self._should_update_symbol(existing, symbol_meta):
                    self.cache.add_symbol(symbol_meta)
                    result.symbols_updated += 1
        
        # Handle removed symbols (mark as delisted instead of removing)
        for symbol in removed_symbols:
            existing = self.cache.get_symbol(symbol)
            if existing:
                existing.status = "delisted"
                existing.updated_date = datetime.utcnow()
                self.logger.info(f"Marked symbol as delisted from {broker}: {symbol}")
        
        result.message = f"Synced {len(new_symbols)} symbols from {broker}"
        
        return result
    
    def _should_update_symbol(self, existing: SymbolMetadata, new: SymbolMetadata) -> bool:
        """Check if symbol metadata should be updated."""
        # Update if any key attributes changed
        return (existing.is_tradable != new.is_tradable or
                existing.is_shortable != new.is_shortable or
                existing.status != new.status or
                existing.min_order_qty != new.min_order_qty or
                existing.max_order_qty != new.max_order_qty)
    
    # ===================
    # Event Handling
    # ===================
    
    def subscribe(self, callback: Callable[[SyncResult], None]) -> None:
        """Subscribe to sync events."""
        self._sync_listeners.append(callback)
    
    def unsubscribe(self, callback: Callable[[SyncResult], None]) -> None:
        """Unsubscribe from sync events."""
        if callback in self._sync_listeners:
            self._sync_listeners.remove(callback)
    
    def _notify_listeners(self, result: SyncResult) -> None:
        """Notify all listeners of sync result."""
        for listener in self._sync_listeners:
            try:
                listener(result)
            except Exception as e:
                self.logger.exception(f"Error in sync listener: {e}")
    
    # ===================
    # Query Operations
    # ===================
    
    def get_sync_history(self, broker: Optional[str] = None, limit: int = 50) -> List[SyncResult]:
        """Get sync history."""
        history = self.sync_history
        
        if broker:
            history = [s for s in history if s.broker == broker]
        
        return history[-limit:]
    
    def get_sync_stats(self) -> dict:
        """Get sync statistics."""
        total_syncs = len(self.sync_history)
        successful_syncs = sum(1 for s in self.sync_history if s.success)
        failed_syncs = total_syncs - successful_syncs
        
        total_added = sum(s.symbols_added for s in self.sync_history)
        total_updated = sum(s.symbols_updated for s in self.sync_history)
        total_removed = sum(s.symbols_removed for s in self.sync_history)
        
        return {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'failed_syncs': failed_syncs,
            'total_symbols_added': total_added,
            'total_symbols_updated': total_updated,
            'total_symbols_removed': total_removed,
            'brokers_registered': len(self._broker_symbol_fetchers),
            'cache_size': self.cache.metrics.total_symbols,
        }
    
    # ===================
    # Policy Management
    # ===================
    
    def set_sync_policy(self, policy: SyncPolicy):
        """Set sync policy."""
        self.sync_policy = policy
        self.logger.info(f"Updated sync policy: {policy}")
    
    def should_force_full_sync(self) -> bool:
        """Check if full sync should be forced."""
        if not self.cache.metrics.last_full_sync:
            return True
        
        time_since_full = datetime.utcnow() - self.cache.metrics.last_full_sync
        force_needed = time_since_full >= timedelta(hours=self.sync_policy.force_full_sync_hours)
        
        if force_needed:
            self.logger.info(f"Full sync needed: {time_since_full.total_seconds():.0f}s since last full sync")
        
        return force_needed
    
    # ===================
    # Cleanup Operations
    # ===================
    
    def cleanup_old_symbols(self, max_age_days: Optional[int] = None) -> int:
        """Remove symbols older than max age."""
        if max_age_days is None:
            max_age_days = self.sync_policy.max_cache_age_days
        
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        removed_count = 0
        
        symbols_to_remove = [
            sym for sym, meta in self.cache.symbols.items()
            if meta.updated_date < cutoff_date
        ]
        
        for symbol in symbols_to_remove:
            self.cache.remove_symbol(symbol)
            removed_count += 1
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old symbols")
            self.storage.save_symbols(self.cache.symbols)
        
        return removed_count
