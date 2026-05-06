"""Application Configuration Management System."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any, Optional


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class BrokerConfig:
    """Broker connection configuration."""
    exchange: str = "alpaca"
    mode: str = "paper"  # paper or live
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""
    timeout_sec: float = 30.0
    max_retries: int = 3
    retry_backoff_ms: int = 1000

    def validate(self) -> tuple[bool, str]:
        """Validate broker configuration."""
        if not self.exchange:
            return False, "exchange is required"
        if not self.mode:
            return False, "mode is required"
        if self.mode not in ("paper", "live"):
            return False, f"invalid mode: {self.mode}"
        return True, ""


@dataclass
class StrategyConfig:
    """Strategy execution configuration."""
    name: str = "TrendFollowing"
    timeframe: str = "1h"
    symbols: list[str] = field(default_factory=list)
    enable_multi_strategy: bool = True
    max_signal_agents: int = 5
    minimum_signal_votes: int = 3

    def validate(self) -> tuple[bool, str]:
        """Validate strategy configuration."""
        if not self.name:
            return False, "strategy name is required"
        if not self.timeframe:
            return False, "timeframe is required"
        return True, ""


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_drawdown_pct: float = 10.0
    max_position_size_pct: float = 5.0
    max_gross_exposure_pct: float = 100.0
    max_leverage: Optional[float] = None
    margin_closeout_guard_enabled: bool = True
    max_margin_closeout_pct: float = 50.0
    hedging_enabled: bool = False

    def validate(self) -> tuple[bool, str]:
        """Validate risk configuration."""
        if self.max_drawdown_pct < 0 or self.max_drawdown_pct > 100:
            return False, "max_drawdown_pct must be 0-100"
        if self.max_position_size_pct < 0 or self.max_position_size_pct > 100:
            return False, "max_position_size_pct must be 0-100"
        return True, ""


@dataclass
class NotificationConfig:
    """Notification settings."""
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    email_enabled: bool = False
    email_recipients: list[str] = field(default_factory=list)
    sms_enabled: bool = False
    sms_numbers: list[str] = field(default_factory=list)
    voice_enabled: bool = False

    def validate(self) -> tuple[bool, str]:
        """Validate notification configuration."""
        if self.email_enabled and not self.email_recipients:
            return False, "email_recipients required when email_enabled"
        return True, ""


@dataclass
class TerminalConfig:
    """Terminal UI configuration."""
    chart_buffer_size: int = 500
    update_interval_ms: int = 500
    max_panels: int = 8
    auto_layout: bool = True
    remember_layout: bool = True
    theme: str = "dark"
    font_size: int = 10
    window_width: int = 1600
    window_height: int = 900
    save_window_state: bool = True

    def validate(self) -> tuple[bool, str]:
        """Validate terminal configuration."""
        if self.chart_buffer_size < 100:
            return False, "chart_buffer_size must be >= 100"
        if self.max_panels < 1:
            return False, "max_panels must be >= 1"
        return True, ""


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    file_enabled: bool = True
    file_path: str = "logs/app.log"
    max_file_size_mb: int = 100
    backup_count: int = 5
    console_enabled: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def validate(self) -> tuple[bool, str]:
        """Validate logging configuration."""
        if self.max_file_size_mb < 1:
            return False, "max_file_size_mb must be >= 1"
        return True, ""


@dataclass
class AppConfig:
    """Main application configuration."""
    app_name: str = "TradeAdviser"
    version: str = "2.0.0"
    debug: bool = False
    
    # Sub-configurations
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    terminal: TerminalConfig = field(default_factory=TerminalConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Additional settings
    data_dir: str = "data"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    def validate(self) -> tuple[bool, str]:
        """Validate entire configuration."""
        configs = [
            ("broker", self.broker),
            ("strategy", self.strategy),
            ("risk", self.risk),
            ("notifications", self.notifications),
            ("terminal", self.terminal),
            ("logging", self.logging),
        ]
        
        for name, config in configs:
            valid, msg = config.validate()
            if not valid:
                return False, f"{name}: {msg}"
        
        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Create from dictionary."""
        config = cls()
        
        if "broker" in data:
            config.broker = BrokerConfig(**data.get("broker", {}))
        if "strategy" in data:
            config.strategy = StrategyConfig(**data.get("strategy", {}))
        if "risk" in data:
            config.risk = RiskConfig(**data.get("risk", {}))
        if "notifications" in data:
            config.notifications = NotificationConfig(**data.get("notifications", {}))
        if "terminal" in data:
            config.terminal = TerminalConfig(**data.get("terminal", {}))
        if "logging" in data:
            log_data = data.get("logging", {})
            if "level" in log_data and isinstance(log_data["level"], str):
                log_data["level"] = LogLevel[log_data["level"]]
            config.logging = LoggingConfig(**log_data)
        
        # Copy simple fields
        for key in ("app_name", "version", "debug", "data_dir", "cache_enabled", "cache_ttl_seconds"):
            if key in data:
                setattr(config, key, data[key])
        
        return config

    @classmethod
    def from_json(cls, json_str: str) -> AppConfig:
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str | Path | None = None, logger: logging.Logger | None = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
            logger: Logger instance
        """
        self.config_path = Path(config_path) if config_path else None
        self.logger = logger or logging.getLogger("ConfigManager")
        self.config = AppConfig()

    def load(self) -> bool:
        """Load configuration from file.
        
        Returns:
            True if loaded successfully
        """
        if not self.config_path or not self.config_path.exists():
            self.logger.warning("Config file not found: %s", self.config_path)
            return False

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            self.config = AppConfig.from_dict(data)
            
            valid, msg = self.config.validate()
            if not valid:
                self.logger.error("Invalid configuration: %s", msg)
                return False
            
            self.logger.info("Configuration loaded from %s", self.config_path)
            return True
        except Exception as e:
            self.logger.error("Failed to load config: %s", e, exc_info=True)
            return False

    def save(self) -> bool:
        """Save configuration to file.
        
        Returns:
            True if saved successfully
        """
        if not self.config_path:
            self.logger.warning("Config path not set")
            return False

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                f.write(self.config.to_json())
            self.logger.info("Configuration saved to %s", self.config_path)
            return True
        except Exception as e:
            self.logger.error("Failed to save config: %s", e, exc_info=True)
            return False

    def validate(self) -> tuple[bool, str]:
        """Validate current configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.config.validate()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., 'broker.exchange')
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        parts = key.split('.')
        current = self.config
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return default
        
        return current

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., 'broker.exchange')
            value: Value to set
        """
        parts = key.split('.')
        current = self.config
        
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                self.logger.warning("Path not found: %s", key)
                return
        
        if hasattr(current, parts[-1]):
            setattr(current, parts[-1], value)
            self.logger.debug("Config updated: %s = %s", key, value)
        else:
            self.logger.warning("Setting not found: %s", key)

    def reset_to_defaults(self) -> None:
        """Reset all configuration to defaults."""
        self.config = AppConfig()
        self.logger.info("Configuration reset to defaults")
