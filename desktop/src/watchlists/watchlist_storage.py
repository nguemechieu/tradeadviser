"""Watchlist Storage - Persistence layer for watchlists."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from .watchlist_manager import Watchlist


class WatchlistStorage:
    """Manages persistence of watchlists to disk."""
    
    def __init__(self, storage_dir: str = "data/watchlists"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.watchlists_file = self.storage_dir / "watchlists.json"
    
    def save_watchlists(self, watchlists: Dict[str, Watchlist]) -> bool:
        """Save all watchlists to disk."""
        try:
            data = {
                'version': 1,
                'saved_at': datetime.utcnow().isoformat(),
                'watchlists': {k: v.to_dict() for k, v in watchlists.items()}
            }
            
            with open(self.watchlists_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(watchlists)} watchlists to {self.watchlists_file}")
            return True
        except Exception as e:
            self.logger.exception(f"Error saving watchlists: {e}")
            return False
    
    def load_watchlists(self) -> Dict[str, Watchlist]:
        """Load all watchlists from disk."""
        if not self.watchlists_file.exists():
            self.logger.info("No watchlists file found, starting fresh")
            return {}
        
        try:
            with open(self.watchlists_file, 'r') as f:
                data = json.load(f)
            
            watchlists = {}
            for wl_id, wl_data in data.get('watchlists', {}).items():
                try:
                    watchlists[wl_id] = Watchlist.from_dict(wl_data)
                except Exception as e:
                    self.logger.warning(f"Failed to load watchlist {wl_id}: {e}")
            
            self.logger.info(f"Loaded {len(watchlists)} watchlists from {self.watchlists_file}")
            return watchlists
        except Exception as e:
            self.logger.exception(f"Error loading watchlists: {e}")
            return {}
    
    def backup_watchlists(self) -> Optional[Path]:
        """Create a backup of current watchlists."""
        try:
            backup_file = self.storage_dir / f"watchlists_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            if self.watchlists_file.exists():
                with open(self.watchlists_file, 'r') as src:
                    data = json.load(src)
                
                with open(backup_file, 'w') as dst:
                    json.dump(data, dst, indent=2)
                
                self.logger.info(f"Created backup: {backup_file}")
                return backup_file
        except Exception as e:
            self.logger.exception(f"Error creating backup: {e}")
        
        return None
