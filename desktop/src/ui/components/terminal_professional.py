"""Terminal UI Improvements Module - Professional Terminal System."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QDockWidget, QVBoxLayout,
    QStatusBar, QToolBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject


class TerminalState(Enum):
    """Terminal operational states."""
    INITIALIZING = "initializing"
    READY = "ready"
    TRADING = "trading"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class TerminalConfig:
    """Terminal configuration settings."""
    chart_buffer_size: int = 500
    update_interval_ms: int = 500
    max_panels: int = 8
    auto_layout: bool = True
    remember_layout: bool = True
    theme: str = "dark"
    font_size: int = 10


class TerminalPanel(ABC):
    """Base class for terminal dock panels."""

    def __init__(self, name: str, title: str, logger: logging.Logger | None = None):
        self.name = name
        self.title = title
        self.logger = logger or logging.getLogger(f"Panel.{name}")
        self._widget: QWidget | None = None

    @abstractmethod
    def create_widget(self) -> QWidget:
        """Create the panel widget."""
        pass

    @abstractmethod
    def update(self, data: dict[str, Any]) -> None:
        """Update panel with new data."""
        pass

    @abstractmethod
    def on_session_changed(self, session_id: str) -> None:
        """Handle active session change."""
        pass

    def get_widget(self) -> QWidget:
        """Get or create the widget."""
        if self._widget is None:
            self._widget = self.create_widget()
        return self._widget

    def cleanup(self) -> None:
        """Clean up resources."""
        self.logger.debug("Cleaning up panel: %s", self.name)


class TerminalSignals(QObject):
    """Terminal event signals."""
    state_changed = pyqtSignal(TerminalState)
    session_changed = pyqtSignal(str)  # session_id
    panel_updated = pyqtSignal(str, dict)  # panel_name, data
    error_occurred = pyqtSignal(str, Exception)  # message, exception
    market_data_updated = pyqtSignal(dict)
    trade_executed = pyqtSignal(dict)


class ProfessionalTerminal(QMainWindow):
    """Professional terminal interface with improved architecture."""

    def __init__(
        self,
        config: TerminalConfig | None = None,
        logger: logging.Logger | None = None
    ):
        super().__init__()
        self.config = config or TerminalConfig()
        self.logger = logger or logging.getLogger("ProfessionalTerminal")
        self.signals = TerminalSignals()
        self._state = TerminalState.INITIALIZING
        self._panels: dict[str, TerminalPanel] = {}
        self._active_session_id: str | None = None
        self._panel_widgets: dict[str, QDockWidget] = {}
        self._setup_ui()
        self.logger.info("Terminal initialized")

    def _setup_ui(self) -> None:
        """Setup terminal UI components."""
        self.setWindowTitle("TradeAdviser Terminal - Professional Edition")
        self.setMinimumSize(1600, 900)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self._setup_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status()

        self.logger.debug("UI setup complete")

    def _setup_toolbar(self) -> None:
        """Setup toolbar with common actions."""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        self.logger.debug("Toolbar created")

    def register_panel(self, panel: TerminalPanel) -> None:
        """Register a terminal panel.
        
        Args:
            panel: Panel to register
        """
        if panel.name in self._panels:
            self.logger.warning("Panel already registered: %s", panel.name)
            return

        if len(self._panels) >= self.config.max_panels:
            self.logger.warning("Maximum panels reached: %d", self.config.max_panels)
            return

        self._panels[panel.name] = panel
        widget = panel.get_widget()
        dock = QDockWidget(panel.title)
        dock.setObjectName(panel.name)
        dock.setWidget(widget)
        
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._panel_widgets[panel.name] = dock
        
        self.logger.info("Registered panel: %s", panel.name)

    def unregister_panel(self, panel_name: str) -> None:
        """Unregister a terminal panel.
        
        Args:
            panel_name: Name of panel to unregister
        """
        if panel_name not in self._panels:
            self.logger.warning("Panel not registered: %s", panel_name)
            return

        panel = self._panels.pop(panel_name)
        dock = self._panel_widgets.pop(panel_name, None)
        
        if dock:
            self.removeDockWidget(dock)
            dock.deleteLater()

        panel.cleanup()
        self.logger.info("Unregistered panel: %s", panel_name)

    def set_active_session(self, session_id: str) -> None:
        """Set active trading session.
        
        Args:
            session_id: ID of session to activate
        """
        if self._active_session_id == session_id:
            return

        old_session = self._active_session_id
        self._active_session_id = session_id
        
        # Notify all panels
        for panel in self._panels.values():
            try:
                panel.on_session_changed(session_id)
            except Exception as e:
                self.logger.error(
                    "Error updating panel %s for session change: %s",
                    panel.name, e
                )

        self.signals.session_changed.emit(session_id)
        self._update_status()
        self.logger.info("Active session changed: %s -> %s", old_session, session_id)

    def update_panel(self, panel_name: str, data: dict[str, Any]) -> None:
        """Update panel with new data.
        
        Args:
            panel_name: Name of panel to update
            data: Data to update with
        """
        if panel_name not in self._panels:
            self.logger.warning("Panel not found: %s", panel_name)
            return

        try:
            panel = self._panels[panel_name]
            panel.update(data)
            self.signals.panel_updated.emit(panel_name, data)
        except Exception as e:
            self.logger.error("Error updating panel %s: %s", panel_name, e)
            self.signals.error_occurred.emit(f"Panel update failed: {panel_name}", e)

    def set_state(self, state: TerminalState) -> None:
        """Set terminal state.
        
        Args:
            state: New terminal state
        """
        if self._state == state:
            return

        old_state = self._state
        self._state = state
        self.signals.state_changed.emit(state)
        self._update_status()
        self.logger.info("Terminal state changed: %s -> %s", old_state, state)

    def get_state(self) -> TerminalState:
        """Get current terminal state."""
        return self._state

    def _update_status(self) -> None:
        """Update status bar."""
        status_text = f"State: {self._state.value}"
        if self._active_session_id:
            status_text += f" | Session: {self._active_session_id}"
        self.status_bar.showMessage(status_text)

    def show_error(self, message: str, exception: Exception | None = None) -> None:
        """Show error to user.
        
        Args:
            message: Error message
            exception: Exception if available
        """
        self.logger.error(message, exc_info=exception)
        self.signals.error_occurred.emit(message, exception)
        self.status_bar.showMessage(f"ERROR: {message}", 5000)

    def cleanup(self) -> None:
        """Cleanup terminal resources."""
        self.logger.info("Cleaning up terminal")
        for panel_name in list(self._panels.keys()):
            self.unregister_panel(panel_name)
        self.set_state(TerminalState.SHUTDOWN)


# Legacy compatibility shim
class TerminalLegacyAdapter:
    """Adapter for integrating with legacy terminal code."""

    def __init__(self, terminal: ProfessionalTerminal):
        self.terminal = terminal
        self.logger = terminal.logger

    def emit(self, signal_name: str, *args: Any) -> None:
        """Emit a signal (legacy interface)."""
        try:
            signal = getattr(self.terminal.signals, signal_name, None)
            if signal is not None and hasattr(signal, 'emit'):
                signal.emit(*args)
        except Exception as e:
            self.logger.error("Error emitting signal %s: %s", signal_name, e)

    def register_callback(
        self,
        signal_name: str,
        callback: Callable[..., None]
    ) -> None:
        """Register callback for signal (legacy interface)."""
        try:
            signal = getattr(self.terminal.signals, signal_name, None)
            if signal is not None and hasattr(signal, 'connect'):
                signal.connect(callback)
        except Exception as e:
            self.logger.error(
                "Error registering callback for %s: %s",
                signal_name, e
            )
