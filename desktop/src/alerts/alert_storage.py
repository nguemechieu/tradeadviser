"""Alert Storage - Persistence layer for alerts."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from .alert_engine import AlertRule


class AlertStorage:
    """Manages persistence of alert rules to disk."""
    
    def __init__(self, storage_dir: str = "data/alerts"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.alerts_file = self.storage_dir / "alerts.json"
        self.user_alerts_file = self.storage_dir / "user_alerts.json"  # User-created alerts
    
    def save_alerts(self, alerts: Dict[str, AlertRule]) -> bool:
        """Save all alerts to disk."""
        try:
            data = {
                'version': 1,
                'saved_at': datetime.utcnow().isoformat(),
                'alerts': {k: v.to_dict() for k, v in alerts.items()}
            }
            
            with open(self.alerts_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(alerts)} alerts to {self.alerts_file}")
            return True
        except Exception as e:
            self.logger.exception(f"Error saving alerts: {e}")
            return False
    
    def load_alerts(self) -> Dict[str, AlertRule]:
        """Load all alerts from disk."""
        if not self.alerts_file.exists():
            self.logger.info("No alerts file found, starting fresh")
            return {}
        
        try:
            with open(self.alerts_file, 'r') as f:
                data = json.load(f)
            
            alerts = {}
            for alert_id, alert_data in data.get('alerts', {}).items():
                try:
                    alerts[alert_id] = AlertRule.from_dict(alert_data)
                except Exception as e:
                    self.logger.warning(f"Failed to load alert {alert_id}: {e}")
            
            self.logger.info(f"Loaded {len(alerts)} alerts from {self.alerts_file}")
            return alerts
        except Exception as e:
            self.logger.exception(f"Error loading alerts: {e}")
            return {}
    
    def save_user_alerts(self, alerts: Dict[str, AlertRule]) -> bool:
        """Save user-created alerts separately."""
        try:
            data = {
                'version': 1,
                'saved_at': datetime.utcnow().isoformat(),
                'alerts': {k: v.to_dict() for k, v in alerts.items()}
            }
            
            with open(self.user_alerts_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(alerts)} user alerts to {self.user_alerts_file}")
            return True
        except Exception as e:
            self.logger.exception(f"Error saving user alerts: {e}")
            return False
    
    def load_user_alerts(self) -> Dict[str, AlertRule]:
        """Load user-created alerts from disk."""
        if not self.user_alerts_file.exists():
            return {}
        
        try:
            with open(self.user_alerts_file, 'r') as f:
                data = json.load(f)
            
            alerts = {}
            for alert_id, alert_data in data.get('alerts', {}).items():
                try:
                    alerts[alert_id] = AlertRule.from_dict(alert_data)
                except Exception as e:
                    self.logger.warning(f"Failed to load user alert {alert_id}: {e}")
            
            self.logger.info(f"Loaded {len(alerts)} user alerts from {self.user_alerts_file}")
            return alerts
        except Exception as e:
            self.logger.exception(f"Error loading user alerts: {e}")
            return {}
    
    def backup_alerts(self) -> Optional[Path]:
        """Create a backup of current alerts."""
        try:
            backup_file = self.storage_dir / f"alerts_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
            if self.alerts_file.exists():
                with open(self.alerts_file, 'r') as src:
                    data = json.load(src)
                
                with open(backup_file, 'w') as dst:
                    json.dump(data, dst, indent=2)
                
                self.logger.info(f"Created backup: {backup_file}")
                return backup_file
        except Exception as e:
            self.logger.exception(f"Error creating backup: {e}")
        
        return None
