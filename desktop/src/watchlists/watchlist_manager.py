"""Watchlist Manager - Manages trading watchlists."""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum


class WatchlistType(str, Enum):
    """Types of watchlists."""
    CUSTOM = "custom"
    SECTOR = "sector"  # Group by sector
    ASSET_CLASS = "asset_class"  # Stocks, Options, Crypto, etc.
    PERFORMANCE = "performance"  # High performers, low performers
    VOLATILITY = "volatility"  # High/low volatility stocks
    SCREENER = "screener"  # Screening criteria based


@dataclass
class WatchlistSymbol:
    """A symbol in a watchlist with metadata."""
    symbol: str
    added_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""
    target_price: Optional[float] = None
    alert_on_target: bool = False
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'added_at': self.added_at.isoformat(),
            'notes': self.notes,
            'target_price': self.target_price,
            'alert_on_target': self.alert_on_target
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        data = dict(data)
        if isinstance(data.get('added_at'), str):
            data['added_at'] = datetime.fromisoformat(data['added_at'])
        return cls(**data)


@dataclass
class Watchlist:
    """A watchlist containing multiple symbols."""
    id: str
    name: str
    watchlist_type: WatchlistType = WatchlistType.CUSTOM
    symbols: Dict[str, WatchlistSymbol] = field(default_factory=dict)
    description: str = ""
    is_public: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    
    def add_symbol(self, symbol: str, notes: str = "", target_price: Optional[float] = None) -> bool:
        """Add symbol to watchlist."""
        if symbol not in self.symbols:
            self.symbols[symbol] = WatchlistSymbol(
                symbol=symbol,
                notes=notes,
                target_price=target_price
            )
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove symbol from watchlist."""
        if symbol in self.symbols:
            del self.symbols[symbol]
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def get_symbol(self, symbol: str) -> Optional[WatchlistSymbol]:
        """Get symbol from watchlist."""
        return self.symbols.get(symbol)
    
    def get_all_symbols(self) -> List[str]:
        """Get all symbols in watchlist."""
        return list(self.symbols.keys())
    
    def update_symbol_notes(self, symbol: str, notes: str) -> bool:
        """Update notes for a symbol."""
        if symbol in self.symbols:
            self.symbols[symbol].notes = notes
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def update_symbol_target(self, symbol: str, target_price: Optional[float]) -> bool:
        """Update target price for a symbol."""
        if symbol in self.symbols:
            self.symbols[symbol].target_price = target_price
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'watchlist_type': self.watchlist_type.value,
            'symbols': {k: v.to_dict() for k, v in self.symbols.items()},
            'description': self.description,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        data = dict(data)
        data['watchlist_type'] = WatchlistType(data.get('watchlist_type', 'custom'))
        
        symbols_dict = {}
        for sym, sym_data in data.get('symbols', {}).items():
            symbols_dict[sym] = WatchlistSymbol.from_dict(sym_data)
        data['symbols'] = symbols_dict
        
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return cls(**data)


class WatchlistManager:
    """Manages all watchlists for the user."""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.watchlists: Dict[str, Watchlist] = {}
        self._listeners = []
    
    # ===================
    # Watchlist Management
    # ===================
    
    def create_watchlist(self, watchlist_id: str, name: str, 
                        watchlist_type: WatchlistType = WatchlistType.CUSTOM,
                        description: str = "") -> Watchlist:
        """Create a new watchlist."""
        watchlist = Watchlist(
            id=watchlist_id,
            name=name,
            watchlist_type=watchlist_type,
            description=description
        )
        self.watchlists[watchlist_id] = watchlist
        self.logger.info(f"Created watchlist: {name} ({watchlist_id})")
        self._notify_listeners('watchlist_created', watchlist)
        return watchlist
    
    def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist."""
        if watchlist_id in self.watchlists:
            watchlist = self.watchlists[watchlist_id]
            del self.watchlists[watchlist_id]
            self.logger.info(f"Deleted watchlist: {watchlist.name}")
            self._notify_listeners('watchlist_deleted', watchlist)
            return True
        return False
    
    def get_watchlist(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get a watchlist by ID."""
        return self.watchlists.get(watchlist_id)
    
    def get_all_watchlists(self) -> List[Watchlist]:
        """Get all watchlists."""
        return list(self.watchlists.values())
    
    def get_watchlists_for_symbol(self, symbol: str) -> List[Watchlist]:
        """Get all watchlists containing a symbol."""
        return [wl for wl in self.watchlists.values() if symbol in wl.symbols]
    
    def rename_watchlist(self, watchlist_id: str, new_name: str) -> bool:
        """Rename a watchlist."""
        if watchlist_id in self.watchlists:
            self.watchlists[watchlist_id].name = new_name
            self.watchlists[watchlist_id].updated_at = datetime.utcnow()
            self.logger.info(f"Renamed watchlist {watchlist_id} to {new_name}")
            self._notify_listeners('watchlist_updated', self.watchlists[watchlist_id])
            return True
        return False
    
    # ===================
    # Symbol Management
    # ===================
    
    def add_symbol(self, watchlist_id: str, symbol: str, 
                  notes: str = "", target_price: Optional[float] = None) -> bool:
        """Add symbol to watchlist."""
        if watchlist_id in self.watchlists:
            result = self.watchlists[watchlist_id].add_symbol(symbol, notes, target_price)
            if result:
                self.logger.info(f"Added {symbol} to watchlist {watchlist_id}")
                self._notify_listeners('symbol_added', self.watchlists[watchlist_id])
            return result
        return False
    
    def remove_symbol(self, watchlist_id: str, symbol: str) -> bool:
        """Remove symbol from watchlist."""
        if watchlist_id in self.watchlists:
            result = self.watchlists[watchlist_id].remove_symbol(symbol)
            if result:
                self.logger.info(f"Removed {symbol} from watchlist {watchlist_id}")
                self._notify_listeners('symbol_removed', self.watchlists[watchlist_id])
            return result
        return False
    
    def get_watchlist_symbols(self, watchlist_id: str) -> List[str]:
        """Get all symbols in a watchlist."""
        if watchlist_id in self.watchlists:
            return self.watchlists[watchlist_id].get_all_symbols()
        return []
    
    def is_in_watchlist(self, watchlist_id: str, symbol: str) -> bool:
        """Check if symbol is in watchlist."""
        if watchlist_id in self.watchlists:
            return symbol in self.watchlists[watchlist_id].symbols
        return False
    
    # ===================
    # Listeners
    # ===================
    
    def subscribe(self, callback) -> None:
        """Subscribe to watchlist changes."""
        self._listeners.append(callback)
    
    def unsubscribe(self, callback) -> None:
        """Unsubscribe from watchlist changes."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self, event: str, data) -> None:
        """Notify all listeners of changes."""
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception as e:
                self.logger.exception(f"Error in watchlist listener: {e}")
