"""
Authentication Middleware - Integrates authentication into AppController

Provides:
- Login/logout UI management
- Authentication state checking
- Broker configuration UI management
- Server sync capability
"""

import logging
from typing import Optional

from PySide6.QtCore import pyqtSignal
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from session_manager import get_session_manager, UserSession
from ui.components.dialogs.auth_dialog import AuthDialog
from ui.components.dialogs.broker_config_dialog import BrokerConfigDialog

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(QObject):
    """
    Middleware for handling authentication in the desktop application.
    
    Signals:
        authenticated: User has successfully logged in
        unauthenticated: User has logged out
        broker_configured: Broker has been configured
    """
    
    authenticated = pyqtSignal(UserSession)
    unauthenticated = pyqtSignal()
    broker_configured = pyqtSignal(str, str)  # broker_name, mode
    
    def __init__(self, parent=None, app_controller=None):
        super().__init__(parent)
        self.app_controller = app_controller
        self.session_manager = get_session_manager()
        self.auth_dialog: Optional[AuthDialog] = None
        self.broker_config_dialog: Optional[BrokerConfigDialog] = None
    
    def check_authentication(self) -> bool:
        """Check if user is currently authenticated."""
        return self.session_manager.is_authenticated()
    
    def get_current_session(self) -> Optional[UserSession]:
        """Get current user session."""
        return self.session_manager.get_session()
    
    def show_login_dialog(self, parent=None, server_url: str = "http://localhost:8000"):
        """Show login/signup dialog."""
        logger.info("Showing login dialog")
        
        self.auth_dialog = AuthDialog(parent, server_url)
        self.auth_dialog.auth_success.connect(self._on_auth_success)
        self.auth_dialog.auth_failed.connect(self._on_auth_failed)
        
        self.auth_dialog.exec()
    
    def show_broker_config_dialog(self, parent=None):
        """Show broker configuration dialog."""
        session = self.session_manager.get_session()
        
        if not session:
            QMessageBox.warning(
                parent,
                "Authentication Required",
                "Please log in first to configure a broker."
            )
            self.show_login_dialog(parent)
            return
        
        logger.info(f"Showing broker config dialog for user: {session.username}")
        
        self.broker_config_dialog = BrokerConfigDialog(
            parent,
            username=session.username,
            token=session.token,
            server_url=session.server_url
        )
        self.broker_config_dialog.config_saved.connect(self._on_broker_configured)
        
        self.broker_config_dialog.exec()
    
    def logout(self):
        """Logout current user."""
        session = self.session_manager.get_session()
        
        if session:
            logger.info(f"Logging out user: {session.username}")
            self.session_manager.logout()
            self.unauthenticated.emit()
            
            QMessageBox.information(
                None,
                "Logged Out",
                f"User {session.username} has been logged out successfully."
            )
    
    def _on_auth_success(self, username: str, token: str, server_url: str):
        """Handle successful authentication."""
        logger.info(f"Authentication successful for user: {username}")
        
        # Create session
        session = self.session_manager.create_session(
            username=username,
            token=token,
            server_url=server_url,
            email=f"{username}@sopotek.local"
        )
        
        self.authenticated.emit(session)
        
        # Auto-show broker configuration
        if self.app_controller:
            self.app_controller.show_broker_config_dialog()
    
    def _on_auth_failed(self, error_message: str):
        """Handle authentication failure."""
        logger.error(f"Authentication failed: {error_message}")
    
    def _on_broker_configured(self, mode: str, config: dict):
        """Handle broker configuration."""
        broker = list(config.keys())[0] if config else None
        logger.info(f"Broker configured: {broker} (mode: {mode})")
        
        session = self.session_manager.get_session()
        if session and broker:
            self.session_manager.update_broker_config(broker, mode)
            self.broker_configured.emit(broker, mode)


# Global authentication middleware instance
_auth_middleware: Optional[AuthenticationMiddleware] = None


def get_auth_middleware(app_controller=None) -> AuthenticationMiddleware:
    """Get or create global authentication middleware."""
    global _auth_middleware
    if _auth_middleware is None:
        _auth_middleware = AuthenticationMiddleware(app_controller=app_controller)
    return _auth_middleware
