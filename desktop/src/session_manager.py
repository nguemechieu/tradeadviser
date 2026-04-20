"""
Session Manager - Desktop Authentication State Management

Handles:
- User session lifecycle
- Token management
- Server connectivity
- Credential persistence
- Multi-profile support
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """User session information."""
    username: str
    email: Optional[str] = None
    token: str = ""
    server_url: str = "http://localhost:8000"
    created_at: str = ""
    expires_at: str = ""
    broker: Optional[str] = None
    broker_mode: Optional[str] = None  # "local" or "remote"
    
    def is_valid(self) -> bool:
        """Check if session is still valid."""
        if not self.token:
            return False
        
        if self.expires_at:
            try:
                expires = datetime.fromisoformat(self.expires_at)
                if expires < datetime.now():
                    return False
            except (ValueError, TypeError):
                pass
        
        return True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class DesktopSessionManager:
    """
    Manages user session state for desktop application.
    
    Responsibilities:
    - Store and retrieve session information
    - Handle token refresh
    - Manage login/logout
    - Persist session across app restarts
    """
    
    def __init__(self):
        self.session_file = Path.home() / ".tradeadviser" / "session.json"
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.current_session: Optional[UserSession] = None
        self._load_session()
    
    def create_session(
        self,
        username: str,
        token: str,
        server_url: str = "http://localhost:8000",
        email: Optional[str] = None,
        broker: Optional[str] = None,
        broker_mode: str = "local"
    ) -> UserSession:
        """Create a new user session."""
        now = datetime.now()
        # Token expires in 24 hours
        expires = now + timedelta(hours=24)
        
        self.current_session = UserSession(
            username=username,
            email=email or f"{username}@tradeadviser.local",
            token=token,
            server_url=server_url,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            broker=broker,
            broker_mode=broker_mode
        )
        
        self._save_session()
        logger.info(f"Session created for user: {username}")
        return self.current_session
    
    def get_session(self) -> Optional[UserSession]:
        """Get current valid session."""
        if self.current_session and self.current_session.is_valid():
            return self.current_session
        return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.get_session() is not None
    
    def logout(self):
        """Logout current user."""
        if self.current_session:
            logger.info(f"Logging out user: {self.current_session.username}")
        
        self.current_session = None
        self._clear_session()
    
    def refresh_token(self, new_token: str, server_url: str = None):
        """Refresh session token."""
        if not self.current_session:
            logger.warning("No active session to refresh")
            return
        
        self.current_session.token = new_token
        if server_url:
            self.current_session.server_url = server_url
        
        # Extend expiration
        now = datetime.now()
        expires = now + timedelta(hours=24)
        self.current_session.expires_at = expires.isoformat()
        
        self._save_session()
        logger.info(f"Token refreshed for user: {self.current_session.username}")
    
    def update_broker_config(self, broker: str, mode: str = "local"):
        """Update current broker configuration."""
        if not self.current_session:
            logger.warning("No active session to update")
            return
        
        self.current_session.broker = broker
        self.current_session.broker_mode = mode
        self._save_session()
        logger.info(f"Broker updated: {broker} ({mode})")
    
    def _save_session(self):
        """Save session to disk."""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(
                    self.current_session.to_dict() if self.current_session else None,
                    f,
                    indent=2
                )
            logger.debug(f"Session saved to {self.session_file}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def _load_session(self):
        """Load session from disk."""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                
                if data:
                    self.current_session = UserSession(**data)
                    
                    # Check if session is still valid
                    if self.current_session.is_valid():
                        logger.info(f"Session restored for user: {self.current_session.username}")
                    else:
                        logger.info("Saved session has expired")
                        self.current_session = None
                        self._clear_session()
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
    
    def _clear_session(self):
        """Clear session from disk."""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
            logger.debug("Session cleared")
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def get_session_info(self) -> Optional[Dict]:
        """Get current session information as dictionary."""
        session = self.get_session()
        if session:
            return {
                "username": session.username,
                "email": session.email,
                "server": session.server_url,
                "broker": session.broker,
                "broker_mode": session.broker_mode,
                "expires_at": session.expires_at
            }
        return None


# Global session manager instance
_session_manager: Optional[DesktopSessionManager] = None


def get_session_manager() -> DesktopSessionManager:
    """Get or create global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = DesktopSessionManager()
    return _session_manager
