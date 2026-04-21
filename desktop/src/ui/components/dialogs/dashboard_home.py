"""Dashboard home screen with quick launch and user info."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap
from pathlib import Path
import asyncio
import json

ROOT_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT_DIR / "assets"


class QuickProfileCard(QFrame):
    """Card showing a quick launch profile."""
    
    clicked = Signal(str)  # profile_name
    
    def __init__(self, profile_name: str, profile_data: dict):
        super().__init__()
        self.profile_name = profile_name
        self.profile_data = profile_data
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 12px;
            }
            QFrame:hover {
                background-color: #e9ecef;
                border: 1px solid #adb5bd;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Profile name
        name_label = QLabel(self.profile_name)
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)
        
        # Profile details
        broker = self.profile_data.get("broker", "Unknown")
        mode = self.profile_data.get("mode", "Local")
        details_label = QLabel(f"{broker} • {mode} Mode")
        details_font = QFont()
        details_font.setPointSize(9)
        details_label.setFont(details_font)
        details_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(details_label)
        
        # Last used
        last_used = self.profile_data.get("last_used", "Never")
        last_label = QLabel(f"Last used: {last_used}")
        last_font = QFont()
        last_font.setPointSize(8)
        last_label.setFont(last_font)
        last_label.setStyleSheet("color: #adb5bd;")
        layout.addWidget(last_label)
        
        layout.addStretch()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.profile_name)


class DashboardHomeScreen(QWidget):
    """Main dashboard home screen with quick launch profiles."""
    
    # Signals
    launch_profile = Signal(str)  # profile_name
    configure_broker = Signal()
    logout_requested = Signal()
    
    def __init__(self, session_manager, server_api_client):
        super().__init__()
        self.session_manager = session_manager
        self.server_api_client = server_api_client
        self.current_user = None
        self.profiles = {}
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
        self._init_ui()
        self._load_profiles()
    
    def _init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ============ Header Section ============
        header_layout = QHBoxLayout()
        
        # Logo and title
        title_label = QLabel("TradeAdviser")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # User info
        self.user_label = QLabel("Guest")
        user_font = QFont()
        user_font.setPointSize(10)
        self.user_label.setFont(user_font)
        self.user_label.setStyleSheet("color: #495057;")
        header_layout.addWidget(self.user_label)
        
        # Settings button
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setMaximumWidth(100)
        settings_btn.clicked.connect(self.show_settings)
        header_layout.addWidget(settings_btn)
        
        # Logout button
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setMaximumWidth(100)
        logout_btn.clicked.connect(self.logout_requested.emit)
        header_layout.addWidget(logout_btn)
        
        main_layout.addLayout(header_layout)
        
        # ============ Quick Launch Section ============
        quick_label = QLabel("Quick Launch Profiles")
        quick_font = QFont()
        quick_font.setPointSize(14)
        quick_font.setBold(True)
        quick_label.setFont(quick_font)
        main_layout.addWidget(quick_label)
        
        # Profiles grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        profiles_container = QWidget()
        self.profiles_grid = QGridLayout(profiles_container)
        self.profiles_grid.setSpacing(12)
        
        scroll.setWidget(profiles_container)
        main_layout.addWidget(scroll, 1)
        
        # ============ Add Profile Section ============
        add_layout = QHBoxLayout()
        add_layout.addStretch()
        
        add_btn = QPushButton("+ Add New Profile")
        add_btn.setMinimumWidth(150)
        add_btn.setMinimumHeight(45)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        add_btn.clicked.connect(self.configure_broker.emit)
        add_layout.addWidget(add_btn)
        
        main_layout.addLayout(add_layout)
    
    def set_user(self, user_info: dict):
        """Update user info display."""
        self.current_user = user_info
        username = user_info.get("username", "User")
        display_name = user_info.get("display_name", username)
        self.user_label.setText(f"👤 {display_name}")
    
    def _load_profiles(self):
        """Load saved profiles from disk."""
        from session_manager import DesktopSessionManager
        
        manager = DesktopSessionManager()
        self.profiles = manager.load_broker_profiles()
        self._refresh_profiles_display()
    
    def _refresh_profiles_display(self):
        """Refresh the profiles grid display."""
        # Clear existing cards
        while self.profiles_grid.count():
            widget = self.profiles_grid.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        
        # Add profile cards
        row = 0
        col = 0
        max_cols = 3
        
        for profile_name, profile_data in self.profiles.items():
            card = QuickProfileCard(profile_name, profile_data)
            card.clicked.connect(self._on_profile_clicked)
            self.profiles_grid.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Add empty message if no profiles
        if not self.profiles:
            empty_label = QLabel("No saved profiles yet.\nCreate one to get started!")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #adb5bd; font-size: 12px;")
            self.profiles_grid.addWidget(empty_label, 0, 0)
    
    def _on_profile_clicked(self, profile_name: str):
        """Handle profile card click."""
        profile_data = self.profiles.get(profile_name, {})
        
        # Show confirmation dialog
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        from PySide6.QtCore import Qt as QtCore
        
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Launch Profile")
        dialog.setText(f"Launch profile '{profile_name}'?")
        dialog.setInformativeText(
            f"Broker: {profile_data.get('broker', 'Unknown')}\n"
            f"Mode: {profile_data.get('mode', 'Local')}"
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        if dialog.exec() == QMessageBox.StandardButton.Ok:
            self.launch_profile.emit(profile_name)
    
    def add_profile(self, profile_name: str, profile_data: dict):
        """Add a new profile to the display."""
        self.profiles[profile_name] = profile_data
        self._refresh_profiles_display()
    
    def update_profile(self, profile_name: str, profile_data: dict):
        """Update an existing profile."""
        if profile_name in self.profiles:
            self.profiles[profile_name].update(profile_data)
            self._refresh_profiles_display()
    
    def remove_profile(self, profile_name: str):
        """Remove a profile."""
        if profile_name in self.profiles:
            del self.profiles[profile_name]
            self._refresh_profiles_display()
    
    def show_settings(self):
        """Open the settings dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setGeometry(100, 100, 400, 300)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Application Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Settings options placeholder
        settings_label = QLabel("Settings options coming soon...")
        settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_label.setStyleSheet("color: #6c757d; padding: 20px;")
        layout.addWidget(settings_label)
        
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setMaximumWidth(100)
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        layout.addWidget(close_btn)
        
        dialog.exec()
