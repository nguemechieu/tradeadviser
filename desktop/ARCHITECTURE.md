"""Desktop Dashboard Architecture - Visual Documentation"""

import os

# This file is best viewed in a markdown viewer or in VS Code

ARCHITECTURE_DIAGRAM = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    SOPOTEK DESKTOP DASHBOARD ARCHITECTURE                 ║
╚════════════════════════════════════════════════════════════════════════════╝


┌─────────────────────────────────────────────────────────────────────────────
│ APPLICATION STARTUP FLOW
└─────────────────────────────────────────────────────────────────────────────

    ┌──────────────┐
    │  main.py     │
    │   (Entry)    │
    └────┬─────────┘
         │
         ├─→ Create QApplication
         │
         ├─→ Initialize Managers:
         │   ├─ DesktopSessionManager
         │   ├─ ServerAPIClient  
         │   └─ QuickLaunchProfileManager
         │
         ├─→ Create AppController
         │
         └─→ Create EnhancedMainWindow
             │
             └─→ _check_authentication()
                 │
                 ├─→ IF session exists
                 │   └─ Show DashboardHomeScreen
                 │
                 └─→ IF no session
                     └─ Show AuthDialog


┌─────────────────────────────────────────────────────────────────────────────
│ USER AUTHENTICATION FLOW
└─────────────────────────────────────────────────────────────────────────────

    ┌─────────────────────┐
    │  AuthDialog.show()  │
    └──────────┬──────────┘
               │
         User enters credentials
               │
               ├─→ Check local session file
               │   └─ ~/.tradeadviser/session.json
               │
               └─→ Send login request
                   │
                   ├─→ ServerAPIClient.login(email, password)
                   │   │
                   │   └─→ POST /auth/login
                   │       └─ Returns: { token, user_info }
                   │
                   └─→ Save session locally
                       ├─ Store token
                       ├─ Store user_info
                       └─ Set authenticated=true
                           │
                           └─→ Emit: authenticated(user_info)
                               │
                               └─→ MainWindow.on_user_authenticated()
                                   │
                                   └─→ Show DashboardHomeScreen


┌─────────────────────────────────────────────────────────────────────────────
│ DASHBOARD HOME SCREEN LAYOUT
└─────────────────────────────────────────────────────────────────────────────

    ┌────────────────────────────────────────────────────────┐
    │                  Sopotek Quant System                  │
    │                                                        │
    │  [Sopotek Logo]          👤 John Trader               │
    │                    ⚙ Settings  🚪 Logout              │
    ├────────────────────────────────────────────────────────┤
    │                                                        │
    │  Quick Launch Profiles                                │
    │                                                        │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
    │  │  Alpaca Live │  │ Binance Paper│  │  OANDA Forex │ │
    │  │ Local Mode   │  │Remote Mode   │  │ Local Mode   │ │
    │  │ Last: Today  │  │ Last: Monday │  │ Last: Friday │ │
    │  └──────────────┘  └──────────────┘  └──────────────┘ │
    │                                                        │
    │  ┌──────────────┐                                      │
    │  │  Coinbase    │                                      │
    │  │ Remote Mode  │                                      │
    │  │ Last: Sunday │                                      │
    │  └──────────────┘                                      │
    │                                                        │
    │                        [+ Add New Profile]            │
    │                                                        │
    └────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────
│ QUICK LAUNCH PROFILE CREATION FLOW
└─────────────────────────────────────────────────────────────────────────────

    User clicks "+ Add New Profile"
         │
         └─→ BrokerConfigDialog.show()
             │
             ├─ Select Broker Type
             │  (Alpaca, Binance, Coinbase, etc.)
             │
             ├─ Enter Credentials
             │  ├─ API Key
             │  ├─ Secret Key
             │  └─ Additional settings
             │
             ├─ Select Mode
             │  ├─ LOCAL  (save to ~/.tradeadviser/profiles/)
             │  └─ REMOTE (sync to server)
             │
             ├─ Click Save
             │  │
             │  └─→ BrokerConfigDialog.config_saved signal
             │      │
             │      └─→ AppController._on_broker_config_saved()
             │          │
             │          ├─→ QuickLaunchProfileManager.create_profile()
             │          │   └─ Save to ~/.tradeadviser/profiles/profiles.json
             │          │
             │          ├─→ IF REMOTE mode:
             │          │   └─ Sync to server
             │          │       └─ POST /users/broker-config
             │          │
             │          └─→ DashboardHomeScreen.add_profile()
             │              └─ Update display with new profile


┌─────────────────────────────────────────────────────────────────────────────
│ QUICK LAUNCH PROFILE USAGE FLOW  
└─────────────────────────────────────────────────────────────────────────────

    User clicks profile card
         │
         └─→ DashboardHomeScreen.launch_profile signal
             │
             └─→ MainWindow._on_launch_profile()
                 │
                 └─→ AppController.on_profile_launched()
                     │
                     ├─→ Get profile from QuickLaunchProfileManager
                     │
                     ├─→ Mark as "last_used"
                     │
                     ├─→ Extract broker and config
                     │
                     └─→ Initialize broker connection
                         ├─ Create BrokerManager
                         ├─ Load credentials from config
                         ├─ Test connection
                         ├─ Start market data streams
                         └─ Show trading dashboard


┌─────────────────────────────────────────────────────────────────────────────
│ REMOTE PROFILE SYNC FLOW
└─────────────────────────────────────────────────────────────────────────────

    User enables "REMOTE" mode when saving profile
         │
         └─→ AppController detects REMOTE mode
             │
             └─→ QuickLaunchProfileManager.sync_profile_to_server()
                 │
                 ├─→ ServerAPIClient.save_broker_config()
                 │   │
                 │   └─→ POST /users/broker-config
                 │       ├─ Body:
                 │       │  ├─ name: "Alpaca_20240419_103000"
                 │       │  ├─ broker: "alpaca"
                 │       │  ├─ config: { api_key, secret_key, ... }
                 │       │  └─ description: "..."
                 │       │
                 │       └─ Returns: { success: true }
                 │
                 └─→ Update local profile
                     ├─ Set mode = "REMOTE"
                     └─ Set synced_at = <timestamp>


┌─────────────────────────────────────────────────────────────────────────────
│ PROFILE MANAGEMENT - PULL FROM SERVER
└─────────────────────────────────────────────────────────────────────────────

    User logs in
         │
         └─→ AppController.on_authenticated()
             │
             └─→ Async: QuickLaunchProfileManager.pull_profiles_from_server()
                 │
                 ├─→ ServerAPIClient.list_broker_configs()
                 │   │
                 │   └─→ GET /users/broker-configs
                 │       └─ Returns: [
                 │           { name: "Alpaca_...", broker: "alpaca", ... },
                 │           { name: "Binance_...", broker: "binance", ... }
                 │         ]
                 │
                 └─→ For each profile on server:
                     ├─→ ServerAPIClient.get_broker_config(name)
                     │   └─→ GET /users/broker-config/{name}
                     │
                     └─→ Save locally with mode="REMOTE"
                         └─ ~/.tradeadviser/profiles/profiles.json


┌─────────────────────────────────────────────────────────────────────────────
│ DATA STORAGE STRUCTURE
└─────────────────────────────────────────────────────────────────────────────

    ~/.tradeadviser/
    ├── session.json
    │   {
    │     "authenticated": true,
    │     "token": "eyJhbGciOiJIUzI1NiIs...",
    │     "user_info": {
    │       "user_id": "12345",
    │       "username": "trader",
    │       "email": "trader@example.com",
    │       "display_name": "John Trader",
    │       "role": "trader"
    │     },
    │     "created_at": "2024-04-19T10:00:00",
    │     "expires_at": "2024-04-20T10:00:00"
    │   }
    │
    └── profiles/
        └── profiles.json
            {
              "Alpaca Live Trading": {
                "name": "Alpaca Live Trading",
                "broker": "alpaca",
                "mode": "LOCAL",
                "config": {
                  "api_key": "xxx",
                  "secret_key": "yyy",
                  "paper": false
                },
                "created_at": "2024-04-15T14:30:00",
                "updated_at": "2024-04-19T10:00:00",
                "last_used": "2024-04-19T10:15:00"
              },
              "Binance Paper": {
                "name": "Binance Paper",
                "broker": "binance",
                "mode": "REMOTE",
                "config": { ... },
                "synced_at": "2024-04-19T09:30:00"
              }
            }


┌─────────────────────────────────────────────────────────────────────────────
│ COMPONENT INTERACTION DIAGRAM
└─────────────────────────────────────────────────────────────────────────────

    ┌───────────────────┐
    │   main.py         │
    │   (Entry Point)   │
    └────────┬──────────┘
             │
    ┌────────┴──────────┐
    │                   │
    │   Creates         │
    │                   │
    v                   v
┌──────────────┐  ┌──────────────────────┐
│ AppController│◄─┤EnhancedMainWindow    │
└──────┬───────┘  └──────────┬───────────┘
       │                     │
       │ manages             │ displays
       │                     │
       v                     v
┌─────────────────────────────────────────┐
│  ┌─────────────────────────────────┐    │
│  │  DashboardHomeScreen            │    │
│  │  ┌─────────────────────────────┐│    │
│  │  │  QuickProfileCards          ││    │
│  │  └─────────────────────────────┘│    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
       ▲
       │ reads/writes
       │
┌──────┴───────────────────────────────────┐
│  QuickLaunchProfileManager                │
│  ├─ Create profiles                      │
│  ├─ Update profiles                      │
│  ├─ Delete profiles                      │
│  ├─ Load profiles from disk              │
│  ├─ Save profiles to disk                │
│  ├─ Sync to server                       │
│  └─ Pull from server                     │
└──────┬──────────────────────┬─────────────┘
       │                      │
    File I/O              Network I/O
       │                      │
       v                      v
   ~/.tradeadviser/           ServerAPIClient
   profiles.json         ├─ /auth/login
                         ├─ /auth/signup
                         ├─ /users/broker-config
                         ├─ /users/broker-configs
                         ├─ /users/broker-config/{name}
                         └─ /users/broker-config/test


┌─────────────────────────────────────────────────────────────────────────────
│ STATE MACHINE - WINDOW STATES
└─────────────────────────────────────────────────────────────────────────────

    ┌──────────────────┐
    │  App Start       │
    └────────┬─────────┘
             │
             ├─ Check session
             │
             v
    ┌─────────────────────┐
    │  Session Exists?    │
    └─────────┬───────────┘
         Yes /     \\ No
           /         \\
          v           v
    ┌─────────┐   ┌──────────────────┐
    │ Restore │   │ Show Auth Dialog │
    │ Session │   └────────┬─────────┘
    └────┬────┘            │
         │         User authenticates
         │                 │
         │                 v
         │          ┌─────────────────┐
         │          │ Create Session  │
         │          └────────┬────────┘
         │                   │
         └───────┬───────────┘
                 │
                 v
         ┌──────────────────┐
         │ Show Home        │
         │ Dashboard        │
         └────────┬─────────┘
                  │
        User clicks profile
                  │
                  v
         ┌──────────────────┐
         │ Launch Broker    │
         │ Connection       │
         └────────┬─────────┘
                  │
                  v
         ┌──────────────────┐
         │ Show Trading     │
         │ Dashboard        │
         └──────────────────┘


┌─────────────────────────────────────────────────────────────────────────────
│ KEY FEATURES SUMMARY
└─────────────────────────────────────────────────────────────────────────────

✓ Authentication Required on Startup
  └─ Session persists across app restarts
  └─ Auto-login if valid session exists

✓ Quick Launch Profiles
  └─ Save multiple broker configurations
  └─ One-click launch of saved profiles
  └─ Display last used time

✓ Dual Storage Modes
  └─ LOCAL: Saved to ~/.tradeadviser/profiles/
  └─ REMOTE: Synced to server, accessible from any device

✓ Profile Management
  └─ Create/Update/Delete profiles
  └─ Export profiles to files
  └─ Import profiles from files

✓ Remote Synchronization
  └─ Push profiles to server
  └─ Pull profiles from server
  └─ Real-time sync with multi-device support

✓ User Experience
  └─ Intuitive dashboard cards
  └─ Clear mode indicators (LOCAL/REMOTE)
  └─ Last used timestamp
  └─ One-click logout

"""

def main():
    """Print architecture documentation."""
    print(ARCHITECTURE_DIAGRAM)
    
    # Save to file for documentation
    doc_file = Path(__file__).parent / "ARCHITECTURE.md"
    doc_file.write_text(ARCHITECTURE_DIAGRAM)
    print(f"\n✓ Architecture documentation saved to {doc_file}")


if __name__ == "__main__":
    from pathlib import Path
    main()
