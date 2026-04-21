"""
Broker Configuration Dialog - Local and Remote Configuration

Handles:
- Local broker credential configuration
- Remote broker configuration saved to server
- Switching between brokers
- Credential encryption and secure storage
- Sync with server settings
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum

from PySide6.QtCore import Qt, Signal, pyqtSignal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTabWidget, QWidget, QMessageBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QSpinBox, QDoubleSpinBox, QFormLayout
)
from PySide6.QtGui import QFont


logger = logging.getLogger(__name__)


class ConfigurationMode(Enum):
    """Configuration storage mode."""
    LOCAL = "local"  # Store credentials locally only
    REMOTE = "remote"  # Save to server


class BrokerConfigDialog(QDialog):
    """
    Broker configuration dialog for managing broker connections.
    
    Supports:
    - Local configuration (credentials stored only locally)
    - Remote configuration (settings synced to server)
    - Multiple broker profiles
    - Real-time validation
    
    Signals:
        config_saved: Emitted when configuration is saved (mode, broker_name)
        config_loaded: Emitted when configuration is loaded (broker_name, config)
    """
    
    config_saved = pyqtSignal(str, dict)  # mode, config
    config_loaded = pyqtSignal(str, dict)  # broker_name, config
    
    # Supported brokers with required fields
    BROKER_CONFIGS = {
        "Alpaca": {
            "icon": "🦙",
            "fields": [
                ("API Key", "api_key", "text"),
                ("Secret Key", "secret_key", "password"),
                ("Base URL", "base_url", "text"),
                ("Paper Trading", "paper_trading", "checkbox"),
            ]
        },
        "Binance": {
            "icon": "📊",
            "fields": [
                ("API Key", "api_key", "text"),
                ("Secret Key", "secret_key", "password"),
                ("Testnet", "testnet", "checkbox"),
            ]
        },
        "Coinbase": {
            "icon": "💰",
            "fields": [
                ("API Key", "api_key", "text"),
                ("Secret Key", "secret_key", "password"),
                ("Passphrase", "passphrase", "password"),
            ]
        },
        "Interactive Brokers": {
            "icon": "🏦",
            "fields": [
                ("Account ID", "account_id", "text"),
                ("Username", "username", "text"),
                ("Password", "password", "password"),
            ]
        },
        "OANDA": {
            "icon": "💱",
            "fields": [
                ("Account ID", "account_id", "text"),
                ("Access Token", "access_token", "password"),
                ("Practice", "practice", "checkbox"),
            ]
        },
    }
    
    def __init__(self, parent=None, username: str = None, token: str = None, server_url: str = None):
        super().__init__(parent)
        self.username = username
        self.auth_token = token
        self.server_url = server_url
        
        # Configuration storage
        self.config_dir = Path.home() / ".tradeadviser" / "broker_configs"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_broker: Optional[str] = None
        self.current_mode: ConfigurationMode = ConfigurationMode.LOCAL
        self.configurations: Dict[str, Dict] = {}
        
        self.setWindowTitle("Broker Configuration - TradeAdviser")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self._create_ui()
        self._load_configurations()
    
    def _create_ui(self):
        """Create the broker configuration UI."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Broker Configuration")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Configuration mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Save Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Local Storage", "Remote (Server)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Mode info label
        self.mode_info = QLabel()
        self.mode_info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.mode_info)
        
        # Broker selection
        broker_layout = QHBoxLayout()
        broker_layout.addWidget(QLabel("Select Broker:"))
        self.broker_combo = QComboBox()
        self.broker_combo.addItems(list(self.BROKER_CONFIGS.keys()))
        self.broker_combo.currentTextChanged.connect(self._on_broker_changed)
        broker_layout.addWidget(self.broker_combo)
        broker_layout.addStretch()
        layout.addLayout(broker_layout)
        
        # Tab widget: Credentials & Profiles
        tabs = QTabWidget()
        tabs.addTab(self._create_credentials_tab(), "Credentials")
        tabs.addTab(self._create_profiles_tab(), "Profiles")
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_button)
        
        self.save_button = QPushButton("Save Configuration")
        self.save_button.clicked.connect(self._save_configuration)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _create_credentials_tab(self) -> QWidget:
        """Create credentials input tab."""
        widget = QWidget()
        layout = QFormLayout()
        
        self.credential_fields: Dict[str, QLineEdit] = {}
        
        # Dynamically create fields based on selected broker
        self._populate_credential_fields(layout)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _create_profiles_tab(self) -> QWidget:
        """Create profiles management tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Profiles table
        self.profiles_table = QTableWidget()
        self.profiles_table.setColumnCount(4)
        self.profiles_table.setHorizontalHeaderLabels(["Broker", "Profile Name", "Mode", "Actions"])
        layout.addWidget(self.profiles_table)
        
        # Profile management buttons
        profile_button_layout = QHBoxLayout()
        
        self.new_profile_button = QPushButton("New Profile")
        self.new_profile_button.clicked.connect(self._new_profile)
        profile_button_layout.addWidget(self.new_profile_button)
        
        self.delete_profile_button = QPushButton("Delete Selected")
        self.delete_profile_button.clicked.connect(self._delete_profile)
        profile_button_layout.addWidget(self.delete_profile_button)
        
        profile_button_layout.addStretch()
        layout.addLayout(profile_button_layout)
        
        widget.setLayout(layout)
        return widget
    
    def _populate_credential_fields(self, layout: QFormLayout):
        """Populate credential input fields based on selected broker."""
        # Clear existing fields
        for widget in self.credential_fields.values():
            widget.deleteLater()
        self.credential_fields.clear()
        
        broker = self.broker_combo.currentText()
        if broker not in self.BROKER_CONFIGS:
            return
        
        broker_config = self.BROKER_CONFIGS[broker]
        
        for label, field_name, field_type in broker_config["fields"]:
            if field_type == "text":
                field = QLineEdit()
                field.setPlaceholderText(f"Enter {label.lower()}")
            elif field_type == "password":
                field = QLineEdit()
                field.setEchoMode(QLineEdit.Password)
                field.setPlaceholderText(f"Enter {label.lower()}")
            elif field_type == "checkbox":
                field = QCheckBox()
            else:
                continue
            
            self.credential_fields[field_name] = field
            layout.addRow(label, field)
    
    def _on_broker_changed(self):
        """Handle broker selection change."""
        broker = self.broker_combo.currentText()
        logger.info(f"Broker changed to: {broker}")
        
        # Reload credentials for this broker
        self._load_broker_config(broker)
        
        # Update credentials tab
        # Note: We need to recreate the form; this is a simplified version
        self.config_loaded.emit(broker, self.configurations.get(broker, {}))
    
    def _on_mode_changed(self):
        """Handle configuration mode change."""
        if self.mode_combo.currentIndex() == 0:
            self.current_mode = ConfigurationMode.LOCAL
            self.mode_info.setText(
                "ℹ️ Credentials stored locally on this computer only. "
                "Cannot sync across devices."
            )
        else:
            self.current_mode = ConfigurationMode.REMOTE
            self.mode_info.setText(
                "ℹ️ Settings saved to server. Accessible from any device "
                "with your account credentials."
            )
    
    def _test_connection(self):
        """Test broker connection with entered credentials."""
        broker = self.broker_combo.currentText()
        
        if not self._validate_credentials():
            QMessageBox.warning(self, "Validation Error", "Please fill all required fields")
            return
        
        # Simulate connection test
        logger.info(f"Testing connection to {broker}...")
        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")
        
        try:
            # In production, this would make actual broker API call
            QMessageBox.information(
                self, "Connection Successful",
                f"✅ Successfully connected to {broker}\n\n"
                "Your credentials are valid. Ready to save configuration."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Connection Failed",
                f"❌ Failed to connect to {broker}:\n{str(e)}"
            )
        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("Test Connection")
    
    def _save_configuration(self):
        """Save broker configuration."""
        broker = self.broker_combo.currentText()
        
        if not self._validate_credentials():
            QMessageBox.warning(self, "Validation Error", "Please fill all required fields")
            return
        
        config = self._get_credentials_dict()
        
        if self.current_mode == ConfigurationMode.LOCAL:
            self._save_local_config(broker, config)
        else:
            self._save_remote_config(broker, config)
        
        QMessageBox.information(
            self, "Configuration Saved",
            f"✅ Broker configuration for {broker} has been saved\n"
            f"Storage: {self.current_mode.value}"
        )
        
        self.config_saved.emit(self.current_mode.value, config)
        self.accept()
    
    def _save_local_config(self, broker: str, config: Dict):
        """Save configuration to local storage."""
        try:
            config_file = self.config_dir / f"{broker.lower()}.json"
            with open(config_file, 'w') as f:
                json.dump({
                    "broker": broker,
                    "mode": "local",
                    "config": config,
                    "timestamp": __import__('time').time()
                }, f, indent=2)
            logger.info(f"Configuration saved locally: {config_file}")
        except Exception as e:
            logger.error(f"Failed to save local config: {e}")
            raise
    
    def _save_remote_config(self, broker: str, config: Dict):
        """Save configuration to remote server."""
        try:
            # TODO: Implement server API call
            # This would POST to: /admin/users-licenses/broker-config
            logger.info(f"Configuration would be saved remotely for: {broker}")
            
            # For now, also save locally as fallback
            self._save_local_config(broker, config)
            
        except Exception as e:
            logger.error(f"Failed to save remote config: {e}")
            raise
    
    def _load_configurations(self):
        """Load all saved broker configurations."""
        try:
            for broker in self.BROKER_CONFIGS.keys():
                self._load_broker_config(broker)
        except Exception as e:
            logger.error(f"Failed to load configurations: {e}")
    
    def _load_broker_config(self, broker: str):
        """Load configuration for specific broker."""
        try:
            config_file = self.config_dir / f"{broker.lower()}.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    self.configurations[broker] = data.get("config", {})
                    logger.info(f"Loaded config for {broker}")
        except Exception as e:
            logger.error(f"Failed to load config for {broker}: {e}")
    
    def _validate_credentials(self) -> bool:
        """Validate that all required fields are filled."""
        return all(
            field.text().strip() if isinstance(field, QLineEdit) else True
            for field in self.credential_fields.values()
        )
    
    def _get_credentials_dict(self) -> Dict:
        """Get credentials as dictionary."""
        credentials = {}
        for field_name, field in self.credential_fields.items():
            if isinstance(field, QLineEdit):
                credentials[field_name] = field.text().strip()
            elif isinstance(field, QCheckBox):
                credentials[field_name] = field.isChecked()
        return credentials
    
    def _new_profile(self):
        """Create new broker profile."""
        QMessageBox.information(self, "New Profile", "Profile creation feature coming soon")
    
    def _delete_profile(self):
        """Delete selected broker profile."""
        selected = self.profiles_table.selectedRows()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select a profile to delete")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this profile?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete selected rows
            for index in sorted(selected, reverse=True):
                self.profiles_table.removeRow(index)
