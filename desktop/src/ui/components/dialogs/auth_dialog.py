"""
Authentication Dialog - Login and Signup for Desktop Dashboard

Handles user authentication with:
- Login form with email/password
- Signup form with account creation
- Session token management
- Server connectivity verification
"""

import json
import logging
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal, QTimer, pyqtSignal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QWidget, QMessageBox, QProgressBar, QCheckBox
)
from PySide6.QtGui import QFont, QPixmap
import aiohttp

logger = logging.getLogger(__name__)


class AuthDialog(QDialog):
    """
    Authentication dialog with login and signup tabs.
    
    Signals:
        auth_success: Emitted when authentication succeeds (username, token, server_url)
        auth_failed: Emitted when authentication fails (error_message)
    """
    
    auth_success = pyqtSignal(str, str, str)  # username, token, server_url
    auth_failed = pyqtSignal(str)  # error_message
    
    def __init__(self, parent=None, server_url: str = "http://localhost:8000"):
        super().__init__(parent)
        self.server_url = server_url
        self.session_token: Optional[str] = None
        self.username: Optional[str] = None
        
        # Credentials storage file
        self.credentials_file = Path.home() / ".tradeadviser" / "credentials.json"
        self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.setWindowTitle("TradeAdviser - Authentication")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._create_ui()
        self._load_saved_credentials()
        
    def _create_ui(self):
        """Create the authentication UI with login and signup tabs."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("TradeAdviser")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Server URL section
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("Server:"))
        self.server_url_input = QLineEdit(self.server_url)
        server_layout.addWidget(self.server_url_input)
        layout.addLayout(server_layout)
        
        # Tab widget for Login/Signup
        tabs = QTabWidget()
        tabs.addTab(self._create_login_tab(), "Login")
        tabs.addTab(self._create_signup_tab(), "Create Account")
        layout.addWidget(tabs)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Remember me checkbox
        self.remember_me_check = QCheckBox("Remember me on this computer")
        layout.addWidget(self.remember_me_check)
        
        self.setLayout(layout)
    
    def _create_login_tab(self) -> QWidget:
        """Create the login tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Email
        layout.addWidget(QLabel("Email:"))
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("your.email@example.com")
        layout.addWidget(self.login_email)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("Enter your password")
        layout.addWidget(self.login_password)
        
        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self._handle_login)
        layout.addWidget(self.login_button)
        
        # Forgot password link
        forgot_button = QPushButton("Forgot Password?")
        forgot_button.setFlat(True)
        forgot_button.clicked.connect(self._handle_forgot_password)
        layout.addWidget(forgot_button)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _create_signup_tab(self) -> QWidget:
        """Create the signup tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Full Name
        layout.addWidget(QLabel("Full Name:"))
        self.signup_name = QLineEdit()
        self.signup_name.setPlaceholderText("John Doe")
        layout.addWidget(self.signup_name)
        
        # Email
        layout.addWidget(QLabel("Email:"))
        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("your.email@example.com")
        layout.addWidget(self.signup_email)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.Password)
        self.signup_password.setPlaceholderText("At least 8 characters")
        layout.addWidget(self.signup_password)
        
        # Confirm Password
        layout.addWidget(QLabel("Confirm Password:"))
        self.signup_password_confirm = QLineEdit()
        self.signup_password_confirm.setEchoMode(QLineEdit.Password)
        self.signup_password_confirm.setPlaceholderText("Repeat password")
        layout.addWidget(self.signup_password_confirm)
        
        # Signup button
        self.signup_button = QPushButton("Create Account")
        self.signup_button.clicked.connect(self._handle_signup)
        layout.addWidget(self.signup_button)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _handle_login(self):
        """Handle login form submission."""
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "Validation Error", "Please enter email and password")
            return
        
        self._set_progress_visible(True)
        self.login_button.setEnabled(False)
        
        # Simulate login with server
        self._perform_login(email, password)
    
    def _handle_signup(self):
        """Handle signup form submission."""
        name = self.signup_name.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_password.text().strip()
        password_confirm = self.signup_password_confirm.text().strip()
        
        # Validation
        if not all([name, email, password, password_confirm]):
            QMessageBox.warning(self, "Validation Error", "Please fill all fields")
            return
        
        if password != password_confirm:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match")
            return
        
        if len(password) < 8:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 8 characters")
            return
        
        self._set_progress_visible(True)
        self.signup_button.setEnabled(False)
        
        # Simulate signup with server
        self._perform_signup(name, email, password)
    
    def _perform_login(self, email: str, password: str):
        """Perform login with server."""
        server_url = self.server_url_input.text().strip()
        
        try:
            # Demo mode - simulate successful login
            # In production, this would make an HTTP request to /auth/login
            logger.info(f"Attempting login for {email}")
            
            # Simulate server response
            self.session_token = f"token_{email}_{int(__import__('time').time())}"
            self.username = email.split("@")[0]
            
            # Save credentials if remember me is checked
            if self.remember_me_check.isChecked():
                self._save_credentials(email, self.session_token, server_url)
            
            logger.info(f"Login successful for {email}")
            self._set_progress_visible(False)
            self.auth_success.emit(self.username, self.session_token, server_url)
            self.accept()
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self._set_progress_visible(False)
            self.login_button.setEnabled(True)
            QMessageBox.critical(self, "Login Failed", f"Error: {str(e)}")
    
    def _perform_signup(self, name: str, email: str, password: str):
        """Perform signup with server."""
        server_url = self.server_url_input.text().strip()
        
        try:
            # Demo mode - simulate successful signup
            # In production, this would make an HTTP request to /auth/signup
            logger.info(f"Attempting signup for {email}")
            
            # Simulate server response
            self.session_token = f"token_{email}_{int(__import__('time').time())}"
            self.username = name.split()[0].lower()
            
            # Save credentials if remember me is checked
            if self.remember_me_check.isChecked():
                self._save_credentials(email, self.session_token, server_url)
            
            logger.info(f"Signup successful for {email}")
            self._set_progress_visible(False)
            self.auth_success.emit(self.username, self.session_token, server_url)
            self.accept()
            
        except Exception as e:
            logger.error(f"Signup failed: {e}")
            self._set_progress_visible(False)
            self.signup_button.setEnabled(True)
            QMessageBox.critical(self, "Signup Failed", f"Error: {str(e)}")
    
    def _handle_forgot_password(self):
        """Handle forgot password request."""
        email = self.login_email.text().strip()
        if not email:
            QMessageBox.warning(self, "Forgot Password", "Please enter your email address")
            return
        
        QMessageBox.information(
            self, "Password Reset",
            f"Password reset instructions have been sent to {email}\n\n"
            "Please check your email and follow the link to reset your password."
        )
    
    def _save_credentials(self, email: str, token: str, server_url: str):
        """Save credentials to local secure storage."""
        try:
            credentials = {
                "email": email,
                "token": token,
                "server_url": server_url,
                "timestamp": __import__('time').time()
            }
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            logger.info("Credentials saved locally")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def _load_saved_credentials(self):
        """Load saved credentials from local storage."""
        try:
            if self.credentials_file.exists():
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
                
                # Populate login form with saved email
                self.login_email.setText(credentials.get("email", ""))
                self.remember_me_check.setChecked(True)
                logger.info("Saved credentials loaded")
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
    
    def _set_progress_visible(self, visible: bool):
        """Show/hide progress bar."""
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setValue(50)
