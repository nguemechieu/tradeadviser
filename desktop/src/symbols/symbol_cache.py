"""Symbol Cache - In-memory caching of trading symbols with metadata."""

import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict


@dataclass
class SymbolMetadata:
    """Metadata for a symbol."""
    symbol: str
    name: str = ""
    asset_class: str = ""  # stock, crypto, option, future, etc.
    exchange: str = ""
    currency: str = "USD"
    min_price_increment: float = 0.01
    min_order_qty: float = 1.0
    max_order_qty: Optional[float] = None
    is_tradable: bool = True
    is_shortable: bool = True
    fractional_allowed: bool = False
    added_date: datetime = field(default_factory=datetime.utcnow)
    updated_date: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"  # active, delisted, suspended, etc.
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['added_date'] = self.added_date.isoformat()
        data['updated_date'] = self.updated_date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SymbolMetadata':
        """Create from dictionary."""
        data = dict(data)
        if isinstance(data.get('added_date'), str):
            data['added_date'] = datetime.fromisoformat(data['added_date'])
        if isinstance(data.get('updated_date'), str):
            data['updated_date'] = datetime.fromisoformat(data['updated_date'])
        return cls(**data)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    total_symbols: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    last_sync: Optional[datetime] = None
    last_full_sync: Optional[datetime] = None
    sync_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hit_count + self.cache_miss_count
        return (self.cache_hit_count / total * 100) if total > 0 else 0.0


class SymbolCache:
    """In-memory cache for trading symbols."""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.symbols: Dict[str, SymbolMetadata] = {}
        self.metrics = CacheMetrics()
        self._last_broker_check: Dict[str, datetime] = {}  # broker -> last check time
        self._symbol_index: Dict[str, Set[str]] = {}  # index: asset_class, exchange, etc.
    
    # ===================
    # Cache Operations
    # ===================
    
    def add_symbol(self, metadata: SymbolMetadata) -> bool:
        """Add or update a symbol in cache."""
        if metadata.symbol in self.symbols:
            # Update existing
            self.symbols[metadata.symbol].updated_date = datetime.utcnow()
            self.symbols[metadata.symbol] = metadata
            self.logger.debug(f"Updated symbol: {metadata.symbol}")
        else:
            # Add new
            self.symbols[metadata.symbol] = metadata
            self.logger.debug(f"Added symbol: {metadata.symbol}")
        
        # Update indexes
        self._update_indexes(metadata)
        self.metrics.total_symbols = len(self.symbols)
        return True
    
    def add_symbols(self, metadata_list: List[SymbolMetadata]) -> int:
        """Add multiple symbols. Returns count added/updated."""
        count = 0
        for metadata in metadata_list:
            if self.add_symbol(metadata):
                count += 1
        
        self.logger.info(f"Added/updated {count} symbols in cache")
        return count
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove symbol from cache."""
        if symbol in self.symbols:
            del self.symbols[symbol]
            self.metrics.total_symbols = len(self.symbols)
            self.logger.debug(f"Removed symbol: {symbol}")
            return True
        return False
    
    def get_symbol(self, symbol: str) -> Optional[SymbolMetadata]:
        """Get symbol metadata from cache."""
        if symbol in self.symbols:
            self.metrics.cache_hit_count += 1
            return self.symbols[symbol]
        else:
            self.metrics.cache_miss_count += 1
            return None
    
    def has_symbol(self, symbol: str) -> bool:
        """Check if symbol is in cache."""
        return symbol in self.symbols
    
    def get_all_symbols(self) -> List[str]:
        """Get all cached symbols."""
        return list(self.symbols.keys())
    
    def get_all_metadata(self) -> List[SymbolMetadata]:
        """Get all symbol metadata."""
        return list(self.symbols.values())
    
    # ===================
    # Filtering & Indexing
    # ===================
    
    def get_symbols_by_asset_class(self, asset_class: str) -> List[str]:
        """Get all symbols of a specific asset class."""
        return [
            sym for sym, meta in self.symbols.items()
            if meta.asset_class == asset_class
        ]
    
    def get_symbols_by_exchange(self, exchange: str) -> List[str]:
        """Get all symbols on a specific exchange."""
        return [
            sym for sym, meta in self.symbols.items()
            if meta.exchange == exchange
        ]
    
    def get_tradable_symbols(self) -> List[str]:
        """Get all tradable symbols."""
        return [
            sym for sym, meta in self.symbols.items()
            if meta.is_tradable
        ]
    
    def get_shortable_symbols(self) -> List[str]:
        """Get all shortable symbols."""
        return [
            sym for sym, meta in self.symbols.items()
            if meta.is_shortable
        ]
    
    def search_symbols(self, query: str, limit: int = 20) -> List[Tuple[str, SymbolMetadata]]:
        """Search symbols by name or symbol."""
        query_lower = query.lower()
        results = []
        
        for symbol, metadata in self.symbols.items():
            if query_lower in symbol.lower() or query_lower in metadata.name.lower():
                results.append((symbol, metadata))
        
        return results[:limit]
    
    # ===================
    # Sync Management
    # ===================
    
    def record_sync(self, broker: str, full_sync: bool = False):
        """Record a sync operation."""
        now = datetime.utcnow()
        self._last_broker_check[broker] = now
        self.metrics.last_sync = now
        self.metrics.sync_count += 1
        
        if full_sync:
            self.metrics.last_full_sync = now
        
        self.logger.info(f"Recorded sync for broker: {broker} (full={full_sync})")
    
    def should_sync_with_broker(self, broker: str, min_interval_minutes: int = 60) -> bool:
        """Check if should sync with broker for new symbols."""
        if broker not in self._last_broker_check:
            return True  # Never synced before
        
        last_check = self._last_broker_check[broker]
        time_since_check = datetime.utcnow() - last_check
        
        should_sync = time_since_check >= timedelta(minutes=min_interval_minutes)
        
        if should_sync:
            self.logger.debug(f"Should sync with {broker}: {time_since_check.total_seconds():.0f}s since last check")
        
        return should_sync
    
    def get_last_sync_time(self, broker: str) -> Optional[datetime]:
        """Get last sync time for a broker."""
        return self._last_broker_check.get(broker)
    
    # ===================
    # Statistics
    # ===================
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            'total_symbols': self.metrics.total_symbols,
            'cache_hit_count': self.metrics.cache_hit_count,
            'cache_miss_count': self.metrics.cache_miss_count,
            'hit_rate': f"{self.metrics.hit_rate:.1f}%",
            'last_sync': self.metrics.last_sync.isoformat() if self.metrics.last_sync else None,
            'last_full_sync': self.metrics.last_full_sync.isoformat() if self.metrics.last_full_sync else None,
            'sync_count': self.metrics.sync_count,
            'asset_classes': self._get_asset_classes(),
            'exchanges': self._get_exchanges(),
        }
    
    def _get_asset_classes(self) -> List[str]:
        """Get unique asset classes."""
        return list(set(m.asset_class for m in self.symbols.values()))
    
    def _get_exchanges(self) -> List[str]:
        """Get unique exchanges."""
        return list(set(m.exchange for m in self.symbols.values()))
    
    def _update_indexes(self, metadata: SymbolMetadata):
        """Update symbol indexes."""
        if metadata.asset_class:
            if metadata.asset_class not in self._symbol_index:
                self._symbol_index[metadata.asset_class] = set()
            self._symbol_index[metadata.asset_class].add(metadata.symbol)
    
    def clear(self):
        """Clear all cached symbols."""
        self.symbols.clear()
        self._symbol_index.clear()
        self.metrics.total_symbols = 0
        self.logger.info("Symbol cache cleared")
