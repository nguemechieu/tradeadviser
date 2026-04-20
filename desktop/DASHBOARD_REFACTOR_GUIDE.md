"""DESKTOP DASHBOARD REFACTOR - INTEGRATION GUIDE

This guide shows how to integrate the refactored desktop dashboard with
authentication flow, quick launch profiles, and remote configuration.
"""

# ============================================================================
# OVERVIEW
# ============================================================================
"""
The refactored desktop dashboard introduces:

1. AUTHENTICATION FLOW
   - Login required on startup
   - Session persistence
   - Automatic session resumption

2. QUICK LAUNCH PROFILES
   - Save broker configurations as reusable profiles
   - One-click launch of saved profiles
   - Recent profile suggestions

3. REMOTE CONFIGURATION
   - Sync profiles to server
   - Load profiles from server
   - Manage multiple broker configs

4. DASHBOARD HOME SCREEN
   - User profile display
   - Quick launch cards
   - Settings and logout options
"""

# ============================================================================
# FILE STRUCTURE
# ============================================================================
"""
sqs_desktop/src/
├── ui/components/
│   ├── enhanced_main_window.py       [NEW] Main window with auth flow
│   ├── dialogs/
│   │   ├── auth_dialog.py           [EXISTING] Login/signup dialog
│   │   ├── broker_config_dialog.py  [EXISTING] Broker configuration
│   │   ├── dashboard_home.py        [NEW] Home screen with quick launch
│   │   └── auth_middleware.py       [EXISTING] Signal coordination
│   └── app_controller.py            [EXISTING - UPDATE NEEDED]
├── session_manager.py               [EXISTING] Session persistence
├── server_api_client.py             [EXISTING] Server communication
├── quick_launch_manager.py          [NEW] Profile management
└── main.py                          [UPDATE NEEDED]
"""

# ============================================================================
# STEP 1: UPDATE MAIN ENTRY POINT
# ============================================================================

# FILE: sqs_desktop/src/main.py
# UPDATE: Use EnhancedMainWindow instead of MainWindow

from ui.components.enhanced_main_window import EnhancedMainWindow
from ui.components.app_controller import AppController
from session_manager import DesktopSessionManager
from server_api_client import ServerAPIClient
from quick_launch_manager import QuickLaunchProfileManager
from PySide6.QtWidgets import QApplication
import sys


def main():
    app = QApplication(sys.argv)
    
    # Initialize managers
    session_manager = DesktopSessionManager()
    server_api_client = ServerAPIClient()
    profile_manager = QuickLaunchProfileManager(session_manager, server_api_client)
    
    # Create controller
    controller = AppController(
        session_manager=session_manager,
        server_api_client=server_api_client,
        profile_manager=profile_manager
    )
    
    # Create enhanced main window
    window = EnhancedMainWindow(
        controller=controller,
        session_manager=session_manager,
        server_api_client=server_api_client
    )
    
    # Connect authentication signals
    window.authenticated.connect(controller.on_authenticated)
    window.unauthenticated.connect(controller.on_unauthenticated)
    window.profile_launched.connect(controller.on_profile_launched)
    
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())


# ============================================================================
# STEP 2: UPDATE APP CONTROLLER
# ============================================================================

# FILE: sqs_desktop/src/ui/components/app_controller.py
# ADD THESE IMPORTS AND METHODS:

# At top of file:
from quick_launch_manager import QuickLaunchProfileManager

# In AppController.__init__:
def __init__(self, session_manager, server_api_client, profile_manager):
    # ... existing code ...
    self.profile_manager = profile_manager
    self.current_user = None


# Add these methods to AppController:

def show_broker_config_dialog(self):
    """Show broker configuration dialog."""
    from ui.components.dialogs.broker_config_dialog import BrokerConfigDialog
    
    dialog = BrokerConfigDialog(self.server_api_client)
    dialog.config_saved.connect(self._on_broker_config_saved)
    dialog.exec()

def _on_broker_config_saved(self, broker_name: str, config: dict, mode: str):
    """Handle broker configuration save."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Create profile name from broker and timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    profile_name = f"{broker_name}_{timestamp}"
    
    # Save as quick launch profile
    self.profile_manager.create_profile(
        name=profile_name,
        broker=broker_name,
        broker_config=config,
        mode=mode
    )
    
    logger.info(f"Saved profile: {profile_name}")
    
    # If REMOTE mode, sync to server
    if mode == "REMOTE":
        import asyncio
        asyncio.create_task(
            self.profile_manager.sync_profile_to_server(profile_name)
        )

def on_authenticated(self, user_info: dict):
    """Handle user authentication."""
    self.current_user = user_info
    print(f"User authenticated: {user_info.get('username')}")

def on_unauthenticated(self):
    """Handle user logout."""
    self.current_user = None
    print("User logged out")

def on_profile_launched(self, profile_name: str):
    """Handle profile launch."""
    import logging
    logger = logging.getLogger(__name__)
    
    profile = self.profile_manager.get_profile(profile_name)
    if not profile:
        logger.error(f"Profile not found: {profile_name}")
        return
    
    # Mark as recently used
    self.profile_manager.mark_profile_used(profile_name)
    
    # Load profile configuration
    broker = profile.get("broker")
    config = profile.get("config")
    
    logger.info(f"Loading profile: {profile_name} ({broker})")
    
    # TODO: Initialize broker connection
    # TODO: Start market data streaming
    # TODO: Show main trading dashboard


# ============================================================================
# STEP 3: PROFILE MANAGEMENT USAGE
# ============================================================================

# Create a new profile:
profile_manager.create_profile(
    name="Alpaca Trading",
    broker="alpaca",
    broker_config={
        "api_key": "xxx",
        "secret_key": "xxx",
        "paper": True
    },
    mode="LOCAL"
)

# Update a profile:
profile_manager.update_profile(
    name="Alpaca Trading",
    broker_config={"api_key": "new_key", "secret_key": "new_secret"},
)

# List all profiles:
profiles = profile_manager.list_profiles()
for name, profile in profiles.items():
    print(f"{name}: {profile['broker']}")

# Delete a profile:
profile_manager.delete_profile("Alpaca Trading")

# Sync profile to server:
import asyncio
result = asyncio.run(
    profile_manager.sync_profile_to_server("Alpaca Trading")
)

# Pull profiles from server:
results = asyncio.run(profile_manager.pull_profiles_from_server())

# Export/Import profiles:
profile_manager.export_profile("Alpaca Trading", "/path/to/profile.json")
profile_manager.import_profile("/path/to/profile.json", "Imported Profile")


# ============================================================================
# STEP 4: DASHBOARD HOME SCREEN SIGNALS
# ============================================================================

# In your main window or controller:

from ui.components.dialogs.dashboard_home import DashboardHomeScreen

home = DashboardHomeScreen(session_manager, server_api_client)

# Connect signals:
home.launch_profile.connect(on_profile_launched)
home.configure_broker.connect(on_configure_broker)
home.logout_requested.connect(on_logout)

# Update displayed user info:
home.set_user({
    "user_id": "12345",
    "username": "trader",
    "display_name": "John Trader",
    "email": "trader@example.com",
    "role": "trader"
})

# Add a new profile to display:
home.add_profile("Alpaca Trading", {
    "broker": "alpaca",
    "mode": "LOCAL",
    "last_used": "2024-04-19T10:30:00"
})

# Update an existing profile:
home.update_profile("Alpaca Trading", {
    "broker": "alpaca",
    "mode": "REMOTE",
    "last_used": "2024-04-19T11:00:00"
})


# ============================================================================
# STEP 5: AUTHENTICATION FLOW
# ============================================================================

"""
Flow diagram:

App Start
  ↓
Check Session (session_manager.get_session())
  ├─ Has valid session → Show Home Dashboard
  │                      ↓
  │                 Display Quick Launch Profiles
  │                      ↓
  │                 User clicks profile → Load broker config
  │                      ↓
  │                 Start trading dashboard
  │
  └─ No session → Show Login Dialog
                   ↓
              User enters credentials
                   ↓
              Authenticate with server
                   ↓
              Create local session
                   ↓
              Show Home Dashboard

User Logout
  ↓
session_manager.logout()
  ↓
Clear session from disk
  ↓
Show Login Dialog
"""


# ============================================================================
# STEP 6: REMOTE CONFIGURATION
# ============================================================================

"""
Remote Configuration Flow:

1. User creates broker profile locally
2. User selects "REMOTE" mode
3. Profile saved to ~/.sopotek/profiles/profiles.json
4. AppController calls profile_manager.sync_profile_to_server()
5. Server receives broker config via /users/broker-config endpoint
6. Profile marked as synced with timestamp

To load from server:
1. User selects "Load from Server"
2. AppController calls profile_manager.pull_profiles_from_server()
3. Server returns list of user's saved profiles
4. Profiles added to local profiles.json
5. Quick Launch shows all profiles (local + remote)

Benefits:
- Access settings from any device
- Backup configurations on server
- No passwords stored locally (for remote mode)
- Quick switching between profiles
"""


# ============================================================================
# STEP 7: SERVER API ENDPOINTS REQUIRED
# ============================================================================

"""
The ServerAPIClient calls these endpoints:

1. POST /auth/login
   - Authenticate user
   - Returns: { token, user_info }

2. POST /auth/signup
   - Create new account
   - Returns: { token, user_info }

3. POST /auth/logout
   - Invalidate token
   - Returns: { success }

4. POST /users/broker-config
   - Save broker configuration
   - Body: { broker, config, description }
   - Returns: { success, profile_id }

5. GET /users/broker-config/{name}
   - Retrieve broker configuration
   - Returns: { broker, config }

6. GET /users/broker-configs
   - List all broker configurations
   - Returns: [{ name, broker, last_updated }]

7. DELETE /users/broker-config/{name}
   - Delete broker configuration
   - Returns: { success }

8. POST /users/broker-config/test
   - Test broker connection
   - Body: { broker, config }
   - Returns: { success, message }
"""


# ============================================================================
# STEP 8: EXAMPLE COMPLETE FLOW
# ============================================================================

"""
1. App starts
   → EnhancedMainWindow checks session
   → No session found
   → Shows AuthDialog

2. User logs in
   → AuthDialog sends credentials to server
   → Server validates and returns token
   → AuthDialog emits auth_success signal
   → MainWindow receives auth_success
   → MainWindow shows DashboardHomeScreen
   → MainWindow updates user display

3. User sees Home Dashboard
   → Dashboard shows quick launch profiles
   → Each profile is a clickable card
   → Cards show: Profile Name, Broker, Mode, Last Used

4. User clicks a profile card
   → Signal: dashboard_home.launch_profile.emit(profile_name)
   → MainWindow receives signal
   → MainWindow calls controller.on_profile_launched()
   → Controller loads profile config
   → Controller initializes broker connection
   → App switches to trading dashboard

5. User configures new broker
   → User clicks "Add New Profile"
   → BrokerConfigDialog opens
   → User selects broker (Alpaca, Binance, etc.)
   → User enters credentials
   → User selects mode (LOCAL or REMOTE)
   → User clicks Save
   → BrokerConfigDialog emits config_saved signal
   → Controller receives signal
   → Controller creates QuickLaunchProfile
   → If REMOTE: sync to server
   → Profile appears on Dashboard

6. User logs out
   → User clicks Logout button
   → App shows confirmation dialog
   → On confirm:
      → session_manager.logout()
      → Session cleared from disk
      → MainWindow shows Login dialog again
"""


# ============================================================================
# STEP 9: TESTING CHECKLIST
# ============================================================================

"""
□ Authentication
  □ Login with valid credentials → Home screen shown
  □ Login with invalid credentials → Error message
  □ Signup creates new account → Redirects to home
  □ Session persists on app restart
  □ Logout clears session

□ Quick Launch Profiles
  □ Create profile → Appears on dashboard
  □ Click profile → Profile loads correctly
  □ Multiple profiles display correctly
  □ Update profile → Changes reflected on dashboard
  □ Delete profile → Removed from dashboard

□ Remote Configuration
  □ Save profile in REMOTE mode → Synced to server
  □ Pull profiles from server → Local list updated
  □ Edit remote profile → Changes sync to server
  □ Settings persist across app restarts

□ User Experience
  □ Dashboard shows current user
  □ Settings button accessible
  □ Logout button accessible
  □ Add New Profile button works
  □ Profile cards display correctly
  □ Last Used timestamp accurate
"""

# ============================================================================
