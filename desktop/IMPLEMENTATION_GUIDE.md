"""PRACTICAL IMPLEMENTATION GUIDE - Step-by-Step Integration"""

# ============================================================================
# SECTION 1: UPDATE main.py
# ============================================================================

# FILE: sqs_desktop/src/main.py

"""
BEFORE (minimal setup):
    from ui.components.main_window import MainWindow
    from ui.components.app_controller import AppController
    
    window = MainWindow(controller)

AFTER (with new components):
"""

# ============== NEW main.py ===============

import sys
import logging
from PySide6.QtWidgets import QApplication

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for Sopotek Desktop."""
    app = QApplication(sys.argv)
    
    try:
        # Initialize core managers
        from session_manager import DesktopSessionManager
        from server_api_client import ServerAPIClient
        from quick_launch_manager import QuickLaunchProfileManager
        
        session_manager = DesktopSessionManager()
        server_api_client = ServerAPIClient()
        profile_manager = QuickLaunchProfileManager(
            session_manager,
            server_api_client
        )
        
        logger.info("Initialized managers")
        
        # Create app controller with new components
        from ui.components.app_controller import AppController
        
        controller = AppController(
            session_manager=session_manager,
            server_api_client=server_api_client,
            profile_manager=profile_manager
        )
        
        logger.info("Created app controller")
        
        # Create enhanced main window
        from ui.components.enhanced_main_window import EnhancedMainWindow
        
        window = EnhancedMainWindow(
            controller=controller,
            session_manager=session_manager,
            server_api_client=server_api_client
        )
        
        # Connect authentication signals
        window.authenticated.connect(controller.on_authenticated)
        window.unauthenticated.connect(controller.on_unauthenticated)
        window.profile_launched.connect(controller.on_profile_launched)
        
        # Connect broker config signals
        from ui.components.auth_middleware import AuthenticationMiddleware
        auth_middleware = AuthenticationMiddleware()
        auth_middleware.broker_configured.connect(
            controller.on_broker_config_saved
        )
        
        logger.info("Created main window")
        window.show()
        
        return app.exec()
    
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# ============================================================================
# SECTION 2: EXTEND AppController
# ============================================================================

# FILE: sqs_desktop/src/ui/components/app_controller.py
# ADD THESE METHODS TO EXISTING AppController CLASS:

# ===== Add to imports =====
import asyncio
from datetime import datetime

# ===== Add to __init__ =====
def __init__(self, session_manager=None, server_api_client=None, profile_manager=None):
    """Initialize app controller with new managers."""
    # ... existing initialization code ...
    
    self.session_manager = session_manager
    self.server_api_client = server_api_client
    self.profile_manager = profile_manager
    self.current_user = None


# ===== Add these new methods =====

def show_broker_config_dialog(self):
    """Show broker configuration dialog for adding/editing profiles."""
    from ui.components.dialogs.broker_config_dialog import BrokerConfigDialog
    
    dialog = BrokerConfigDialog(self.server_api_client)
    dialog.config_saved.connect(self._on_broker_config_saved)
    dialog.exec()

def _on_broker_config_saved(self, broker_name: str, config: dict, mode: str):
    """Handle broker configuration save from dialog.
    
    Args:
        broker_name: Broker type (alpaca, binance, etc.)
        config: Broker credentials and settings
        mode: Storage mode (LOCAL or REMOTE)
    """
    if not self.profile_manager:
        logger.error("Profile manager not initialized")
        return
    
    try:
        # Generate profile name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_name = f"{broker_name}_{timestamp}"
        
        # Create and save profile
        self.profile_manager.create_profile(
            name=profile_name,
            broker=broker_name,
            broker_config=config,
            mode=mode,
            description=f"Auto-created on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        logger.info(f"Created profile: {profile_name} ({mode} mode)")
        
        # Sync to server if remote mode
        if mode == "REMOTE":
            asyncio.create_task(
                self.profile_manager.sync_profile_to_server(profile_name)
            )
        
        # Notify home screen to refresh profiles
        from ui.components.dialogs.dashboard_home import DashboardHomeScreen
        # This will be emitted through signals in enhanced main window
    
    except Exception as e:
        logger.error(f"Error saving broker config: {e}")

def on_authenticated(self, user_info: dict):
    """Handle user authentication.
    
    Args:
        user_info: Dictionary with user information
    """
    self.current_user = user_info
    logger.info(f"User authenticated: {user_info.get('username')}")
    
    # Optional: Load user's profiles from server
    if self.profile_manager:
        try:
            asyncio.create_task(self._load_user_profiles())
        except Exception as e:
            logger.warning(f"Could not load profiles: {e}")

async def _load_user_profiles(self):
    """Load user's profiles from server on authentication."""
    if not self.profile_manager:
        return
    
    try:
        results = await self.profile_manager.pull_profiles_from_server()
        logger.info(f"Loaded {len(results)} profiles from server")
    except Exception as e:
        logger.warning(f"Error loading profiles from server: {e}")

def on_unauthenticated(self):
    """Handle user logout."""
    self.current_user = None
    logger.info("User logged out")

def on_profile_launched(self, profile_name: str):
    """Handle quick launch profile selection.
    
    Args:
        profile_name: Name of profile to launch
    """
    if not self.profile_manager:
        logger.error("Profile manager not initialized")
        return
    
    try:
        profile = self.profile_manager.get_profile(profile_name)
        if not profile:
            logger.error(f"Profile not found: {profile_name}")
            return
        
        # Mark as recently used
        self.profile_manager.mark_profile_used(profile_name)
        
        # Extract profile data
        broker = profile.get("broker")
        config = profile.get("config")
        
        logger.info(f"Launching profile: {profile_name} ({broker})")
        
        # TODO: Connect to broker with config
        # This is where you would:
        # 1. Create broker manager instance
        # 2. Initialize with profile config
        # 3. Start market data streams
        # 4. Show trading dashboard
        
        self._initialize_broker_connection(broker, config)
    
    except Exception as e:
        logger.error(f"Error launching profile: {e}")

def _initialize_broker_connection(self, broker: str, config: dict):
    """Initialize broker connection with profile settings.
    
    Args:
        broker: Broker type
        config: Broker configuration/credentials
    """
    logger.info(f"Initializing connection to {broker}")
    
    # Import broker factory if available
    try:
        from broker.broker_factory import BrokerFactory
        
        # Create broker instance
        broker_instance = BrokerFactory.create_broker(broker, config)
        
        # TODO: Connect to trading dashboard
        logger.info(f"Connected to {broker}")
    
    except Exception as e:
        logger.error(f"Failed to connect to {broker}: {e}")


# ============================================================================
# SECTION 3: UPDATE EnhancedMainWindow CONNECTIONS
# ============================================================================

# FILE: sqs_desktop/src/ui/components/enhanced_main_window.py
# UPDATE the _create_screens method:

def _create_screens(self):
    """Create application screens."""
    from ui.components.dialogs.dashboard_home import DashboardHomeScreen
    
    # Home/Dashboard screen
    self.home_screen = DashboardHomeScreen(self.session_manager, self.server_api_client)
    
    # Connect signals
    self.home_screen.launch_profile.connect(self._on_launch_profile)
    self.home_screen.configure_broker.connect(self.controller.show_broker_config_dialog)
    self.home_screen.logout_requested.connect(self._on_logout)
    
    self.stacked_widget.addWidget(self.home_screen)


# ============================================================================
# SECTION 4: EXAMPLE WORKFLOW CODE
# ============================================================================

# Example 1: Create and save a quick launch profile

def create_quick_launch_profile_example():
    """Example of creating a quick launch profile."""
    from quick_launch_manager import QuickLaunchProfileManager
    from session_manager import DesktopSessionManager
    from server_api_client import ServerAPIClient
    
    session_manager = DesktopSessionManager()
    api_client = ServerAPIClient()
    profile_manager = QuickLaunchProfileManager(session_manager, api_client)
    
    # Create a profile
    profile = profile_manager.create_profile(
        name="Alpaca Paper Trading",
        broker="alpaca",
        broker_config={
            "api_key": "xxx_key_xxx",
            "secret_key": "xxx_secret_xxx",
            "paper": True,
            "base_url": "https://paper-api.alpaca.markets"
        },
        mode="LOCAL"
    )
    
    print(f"Created profile: {profile['name']}")
    print(f"Broker: {profile['broker']}")
    print(f"Mode: {profile['mode']}")


# Example 2: Load and launch a profile

async def load_and_launch_profile_example():
    """Example of loading and launching a profile."""
    from quick_launch_manager import QuickLaunchProfileManager
    from session_manager import DesktopSessionManager
    from server_api_client import ServerAPIClient
    
    session_manager = DesktopSessionManager()
    api_client = ServerAPIClient()
    profile_manager = QuickLaunchProfileManager(session_manager, api_client)
    
    # Get all profiles
    profiles = profile_manager.list_profiles()
    
    if profiles:
        # Launch the first profile
        profile_name = list(profiles.keys())[0]
        profile = profile_manager.get_profile(profile_name)
        
        # Mark as used
        profile_manager.mark_profile_used(profile_name)
        
        print(f"Launching: {profile_name}")
        print(f"Broker: {profile['broker']}")
        print(f"Last used: {profile['last_used']}")


# Example 3: Sync profiles to server

async def sync_profiles_to_server_example():
    """Example of syncing profiles to server."""
    from quick_launch_manager import QuickLaunchProfileManager
    from session_manager import DesktopSessionManager
    from server_api_client import ServerAPIClient
    
    session_manager = DesktopSessionManager()
    api_client = ServerAPIClient()
    profile_manager = QuickLaunchProfileManager(session_manager, api_client)
    
    # Sync all profiles
    results = await profile_manager.sync_all_profiles_to_server()
    
    for profile_name, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {profile_name}")


# Example 4: Pull profiles from server

async def pull_profiles_from_server_example():
    """Example of pulling profiles from server."""
    from quick_launch_manager import QuickLaunchProfileManager
    from session_manager import DesktopSessionManager
    from server_api_client import ServerAPIClient
    
    session_manager = DesktopSessionManager()
    api_client = ServerAPIClient()
    profile_manager = QuickLaunchProfileManager(session_manager, api_client)
    
    # Pull all profiles from server
    results = await profile_manager.pull_profiles_from_server()
    
    for profile_name, success in results.items():
        status = "✓ Loaded" if success else "✗ Failed"
        print(f"{status}: {profile_name}")


# ============================================================================
# SECTION 5: QUICK REFERENCE - INTEGRATION CHECKLIST
# ============================================================================

"""
STEP-BY-STEP INTEGRATION CHECKLIST:

Phase 1: Files to Create
□ sqs_desktop/src/ui/components/enhanced_main_window.py
□ sqs_desktop/src/ui/components/dialogs/dashboard_home.py
□ sqs_desktop/src/quick_launch_manager.py
□ sqs_desktop/DASHBOARD_REFACTOR_GUIDE.md (this file)

Phase 2: Files to Update
□ sqs_desktop/src/main.py - Update entry point
□ sqs_desktop/src/ui/components/app_controller.py - Add new methods
□ sqs_desktop/src/ui/components/dialogs/broker_config_dialog.py - Emit config_saved signal
□ sqs_desktop/src/server_api_client.py - Ensure endpoints exist

Phase 3: Testing
□ Test app startup without session (should show login)
□ Test successful login (should show home dashboard)
□ Test profile creation (should appear on dashboard)
□ Test profile launch (should load configuration)
□ Test logout (should show login again)
□ Test session persistence (restart app, should auto-login)
□ Test remote sync (profile should sync to server)

Phase 4: Deployment
□ Package updated desktop app
□ Update version number
□ Create migration guide for existing users
□ Document new features

REQUIRED BACKEND ENDPOINTS:
✓ POST /auth/login
✓ POST /auth/signup
✓ POST /users/broker-config (save)
✓ GET /users/broker-config/{name} (retrieve)
✓ GET /users/broker-configs (list)
✓ DELETE /users/broker-config/{name} (delete)
✓ POST /users/broker-config/test (test connection)

All endpoints are already available in the backend!
"""

# ============================================================================
