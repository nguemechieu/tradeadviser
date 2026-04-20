"""Symbol Storage - Persistence layer for symbol cache."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .symbol_cache import SymbolMetadata


class SymbolStorage:
    """Manages persistence of symbol cache to disk."""
    
    def __init__(self, storage_dir: str = "data/symbols"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.symbols_file = self.storage_dir / "symbols.json"
        self.sync_metadata_file = self.storage_dir / "sync_metadata.json"
    
    # ===================
    # Save Operations
    # ===================
    
    def save_symbols(self, symbols: Dict[str, SymbolMetadata]) -> bool:
        """Save all symbols to disk."""
        try:
            data = {
                'version': 1,
                'saved_at': datetime.utcnow().isoformat(),
                'symbol_count': len(symbols),
                'symbols': {k: v.to_dict() for k, v in symbols.items()}
            }
            
            with open(self.symbols_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(symbols)} symbols to {self.symbols_file}")
            return True
        except Exception as e:
            self.logger.exception(f"Error saving symbols: {e}")
            return False
    
    def save_sync_metadata(self, metadata: dict) -> bool:
        """Save sync metadata (last sync times, etc)."""
        try:
            data = {
                'saved_at': datetime.utcnow().isoformat(),
                'metadata': metadata
            }
            
            with open(self.sync_metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Saved sync metadata to {self.sync_metadata_file}")
            return True
        except Exception as e:
            self.logger.exception(f"Error saving sync metadata: {e}")
            return False
    
    # ===================
    # Load Operations
    # ===================
    
    def load_symbols(self) -> Dict[str, SymbolMetadata]:
        """Load all symbols from disk."""
        if not self.symbols_file.exists():
            self.logger.info("No symbols file found, starting fresh")
            return {}
        
        try:
            with open(self.symbols_file, 'r') as f:
                data = json.load(f)
            
            symbols = {}
            for symbol, sym_data in data.get('symbols', {}).items():
                try:
                    symbols[symbol] = SymbolMetadata.from_dict(sym_data)
                except Exception as e:
                    self.logger.warning(f"Failed to load symbol {symbol}: {e}")
            
            self.logger.info(f"Loaded {len(symbols)} symbols from {self.symbols_file}")
            return symbols
        except Exception as e:
            self.logger.exception(f"Error loading symbols: {e}")
            return {}
    
    def load_sync_metadata(self) -> dict:
        """Load sync metadata."""
        if not self.sync_metadata_file.exists():
            return {}
        
        try:
            with open(self.sync_metadata_file, 'r') as f:
                data = json.load(f)
            
            return data.get('metadata', {})
        except Exception as e:
            self.logger.exception(f"Error loading sync metadata: {e}")
            return {}
    
    # ===================
    # Backup Operations
    # ===================
    
    def backup_symbols(self) -> Optional[Path]:
        """Create a timestamped backup of symbols."""
        try:
            backup_file = self.storage_dir / f"symbols_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            if self.symbols_file.exists():
                with open(self.symbols_file, 'r') as src:
                    data = json.load(src)
                
                with open(backup_file, 'w') as dst:
                    json.dump(data, dst, indent=2)
                
                self.logger.info(f"Created backup: {backup_file}")
                return backup_file
        except Exception as e:
            self.logger.exception(f"Error creating backup: {e}")
        
        return None
    
    def get_backup_files(self) -> List[Path]:
        """Get all backup files."""
        return list(self.storage_dir.glob("symbols_backup_*.json"))
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """Delete old backups, keeping only the most recent."""
        backups = sorted(self.get_backup_files(), key=lambda p: p.stat().st_mtime, reverse=True)
        
        deleted_count = 0
        for backup in backups[keep_count:]:
            try:
                backup.unlink()
                deleted_count += 1
                self.logger.debug(f"Deleted old backup: {backup.name}")
            except Exception as e:
                self.logger.warning(f"Failed to delete backup {backup.name}: {e}")
        
        return deleted_count
    
    # ===================
    # Utility Operations
    # ===================
    
    def get_cache_size(self) -> dict:
        """Get cache file sizes."""
        sizes = {}
        
        if self.symbols_file.exists():
            sizes['symbols'] = self.symbols_file.stat().st_size
        
        if self.sync_metadata_file.exists():
            sizes['metadata'] = self.sync_metadata_file.stat().st_size
        
        backups_size = sum(f.stat().st_size for f in self.get_backup_files())
        if backups_size > 0:
            sizes['backups'] = backups_size
        
        return sizes
    
    def export_to_csv(self, symbols: Dict[str, SymbolMetadata], filepath: str) -> bool:
        """Export symbols to CSV."""
        try:
            with open(filepath, 'w', newline='') as f:
                # Write header
                f.write("Symbol,Name,AssetClass,Exchange,Currency,MinPriceIncrement,MinOrderQty,MaxOrderQty,IsTradable,IsShortable,FractionalAllowed,Status,AddedDate,UpdatedDate\n")
                
                # Write symbols
                for symbol, metadata in sorted(symbols.items()):
                    f.write(f"{metadata.symbol},\"{metadata.name}\",{metadata.asset_class},{metadata.exchange},"
                           f"{metadata.currency},{metadata.min_price_increment},{metadata.min_order_qty},"
                           f"{metadata.max_order_qty or ''},{'Yes' if metadata.is_tradable else 'No'},"
                           f"{'Yes' if metadata.is_shortable else 'No'},{'Yes' if metadata.fractional_allowed else 'No'},"
                           f"{metadata.status},{metadata.added_date.isoformat()},{metadata.updated_date.isoformat()}\n")
            
            self.logger.info(f"Exported {len(symbols)} symbols to {filepath}")
            return True
        except Exception as e:
            self.logger.exception(f"Error exporting to CSV: {e}")
            return False
