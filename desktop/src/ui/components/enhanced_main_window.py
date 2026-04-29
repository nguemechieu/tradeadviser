"""Enhanced main window with authentication flow and dashboard."""

import logging

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox

logger = logging.getLogger(__name__)


class EnhancedMainWindow(QMainWindow):
    """Main window with authentication flow and dashboard management."""
    
    # Signals
    authenticated = Signal(dict)  # user_info
    unauthenticated = Signal()
    profile_launched = Signal(str)  # profile_name
    broker_configured = Signal(str, dict)  # broker_name, config
    
    # Screen indices
    SCREEN_HOME = 0
    SCREEN_DASHBOARD = 1
    SCREEN_CONFIG = 2
    
    def __init__(self, controller, session_manager, server_api_client):
        super().__init__()
        
        self.controller = controller
        self.session_manager = session_manager
        self.server_api_client = server_api_client
        self.current_user = None
        
        # Initialize UI
        self.setWindowTitle("TradeAdviser-Desktop")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create stacked widget for screen management
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Create screens
        self._create_screens()
        self._create_menu()
        
        # Check authentication state on startup
        QTimer.singleShot(0, self._check_authentication)
    
    def _create_screens(self):
        """Create application screens."""
        # Import here to avoid circular imports
        from ui.components.dialogs.dashboard_home import DashboardHomeScreen
        
        # Home/Dashboard screen
        self.home_screen = DashboardHomeScreen(self.session_manager, self.server_api_client)
        self.home_screen.launch_profile.connect(self._on_launch_profile)
        self.home_screen.configure_broker.connect(self.controller.show_broker_config_dialog)
        self.home_screen.logout_requested.connect(self._on_logout)
        self.stacked_widget.addWidget(self.home_screen)  # Index 0
    
    def _create_menu(self):
        """Create menu bar."""
        menu = self.menuBar()
        
        # File menu
        file_menu = menu.addMenu("File")
        
        self.login_action = QAction("Login", self)
        self.login_action.triggered.connect(self.controller.show_login_dialog)
        file_menu.addAction(self.login_action)
        
        self.logout_action = QAction("Logout", self)
        self.logout_action.triggered.connect(self._on_logout)
        self.logout_action.setVisible(False)
        file_menu.addAction(self.logout_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Profile menu
        profile_menu = menu.addMenu("Profile")
        
        manage_action = QAction("Manage Profiles", self)
        manage_action.triggered.connect(self._show_manage_profiles)
        profile_menu.addAction(manage_action)
        
        sync_action = QAction("Sync with Server", self)
        sync_action.triggered.connect(self._show_sync_dialog)
        profile_menu.addAction(sync_action)
        
        # Help menu
        help_menu = menu.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _check_authentication(self):
        """Check if user is already authenticated."""
        session = self.session_manager.get_session()
        
        if session and session.get("authenticated"):
            # User is authenticated, show home screen
            self._on_authenticated(session.get("user_info", {}))
        else:
            # Show login dialog
            self.controller.show_login_dialog()
    
    def on_user_authenticated(self, user_info: dict, token: str, server_url: str):
        """Handle user authentication.
        
        Args:
            user_info: User information
            token: Authentication token
            server_url: Server URL
        """
        self.current_user = user_info
        self.home_screen.set_user(user_info)
        self.authenticated.emit(user_info)
        self.login_action.setVisible(False)
        self.logout_action.setVisible(True)
        self.stacked_widget.setCurrentIndex(self.SCREEN_HOME)
        logger.info(f"User authenticated: {user_info.get('username')}")
    
    def _on_authenticated(self, user_info: dict):
        """Internal handler for authentication."""
        self.current_user = user_info
        self.home_screen.set_user(user_info)
        self.authenticated.emit(user_info)
        self.login_action.setVisible(False)
        self.logout_action.setVisible(True)
        self.stacked_widget.setCurrentIndex(self.SCREEN_HOME)
    
    def _on_logout(self):
        """Handle logout."""
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.session_manager.logout()
            self.current_user = None
            self.unauthenticated.emit()
            self.login_action.setVisible(True)
            self.logout_action.setVisible(False)
            self.controller.show_login_dialog()
            logger.info("User logged out")
    
    def _on_launch_profile(self, profile_name: str):
        """Handle quick launch profile selection.
        
        Args:
            profile_name: Selected profile name
        """
        logger.info(f"Launching profile: {profile_name}")
        self.profile_launched.emit(profile_name)
        
        # TODO: Initialize broker connection with profile settings
        # This would typically:
        # 1. Load profile config
        # 2. Connect to broker
        # 3. Switch to main trading dashboard
        # 4. Start market data streaming
        
        QMessageBox.information(
            self,
            "Profile Launched",
            f"Profile '{profile_name}' configuration loaded.\n"
            f"Ready to start trading."
        )
    
    def _show_manage_profiles(self):
        """Show profile management dialog."""
        # TODO: Implement profile management dialog
        QMessageBox.information(
            self,
            "Manage Profiles",
            "Profile management coming soon!"
        )
    
    def _show_sync_dialog(self):
        """Show profile synchronization dialog."""
        # TODO: Implement sync dialog with server
        QMessageBox.information(
            self,
            "Sync Profiles",
            "Server synchronization coming soon!"
        )
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About TradeAdviser",
            "TradeAdviser v2.0.0\n\n"
            "Professional quantitative trading platform\n\n"
            "© 2024 TradeAdviser, Inc."
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.current_user:
            reply = QMessageBox.question(
                self,
                "Exit",
                "Exit TradeAdviser?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        
        event.accept()
