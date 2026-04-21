"""
Production configuration management module for TradeAdviser Desktop
Handles environment-specific settings and secure credential management
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int = 20
    max_overflow: int = 40
    
    @property
    def connection_string(self) -> str:
        """PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class BrokerConfig:
    """Broker API configuration"""
    api_key: str
    api_secret: str
    account_id: Optional[str] = None
    sandbox: bool = True
    timeout: int = 30
    retry_attempts: int = 3


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"  # json, text
    file: str = "logs/app.log"
    max_size_mb: int = 100
    backup_count: int = 10
    enable_console: bool = True
    enable_file: bool = True


class ProductionConfig:
    """
    Production configuration manager
    Handles environment variables and secure credential loading
    """
    
    def __init__(self, env: Environment = Environment.PRODUCTION):
        self.env = env
        self.config_dir = Path.home() / ".tradeadviser"
        self.config_dir.mkdir(exist_ok=True)
        
        # Load environment variables
        self._load_env_file()
        
        logger.info(f"Initialized production config for {env.value}")
    
    def _load_env_file(self):
        """Load environment variables from .env file"""
        env_path = Path.cwd() / ".env"
        
        if not env_path.exists():
            logger.warning(f".env file not found at {env_path}")
            logger.info("Using environment variables only")
            return
        
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
            logger.info(f"Loaded configuration from {env_path}")
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig(
            host=self._get_env("DB_HOST", "localhost"),
            port=int(self._get_env("DB_PORT", "5432")),
            name=self._get_env("DB_NAME", "tradeadviser"),
            user=self._get_env("DB_USER", "tradeadviser"),
            password=self._get_required_env("DB_PASSWORD"),
            pool_size=int(self._get_env("DB_POOL_SIZE", "20")),
            max_overflow=int(self._get_env("DB_MAX_OVERFLOW", "40")),
        )
    
    @property
    def logging(self) -> LoggingConfig:
        """Get logging configuration"""
        return LoggingConfig(
            level=self._get_env("LOG_LEVEL", "INFO"),
            format=self._get_env("LOG_FORMAT", "json"),
            file=self._get_env("LOG_FILE", "logs/app.log"),
            max_size_mb=int(self._get_env("LOG_MAX_SIZE_MB", "100")),
            backup_count=int(self._get_env("LOG_BACKUP_COUNT", "10")),
        )
    
    @property
    def brokers(self) -> Dict[str, BrokerConfig]:
        """Get broker configurations"""
        brokers = {}
        
        # Interactive Brokers
        if self._get_env("IBKR_API_KEY"):
            brokers["ibkr"] = BrokerConfig(
                api_key=self._get_required_env("IBKR_API_KEY"),
                api_secret=self._get_required_env("IBKR_API_SECRET"),
                account_id=self._get_env("IBKR_ACCOUNT_ID"),
                sandbox=self._get_bool_env("IBKR_SANDBOX", True),
            )
        
        # Schwab
        if self._get_env("SCHWAB_API_KEY"):
            brokers["schwab"] = BrokerConfig(
                api_key=self._get_required_env("SCHWAB_API_KEY"),
                api_secret=self._get_required_env("SCHWAB_API_SECRET"),
                account_id=self._get_env("SCHWAB_ACCOUNT_ID"),
                sandbox=self._get_bool_env("SCHWAB_SANDBOX", True),
            )
        
        # Coinbase
        if self._get_env("COINBASE_API_KEY"):
            brokers["coinbase"] = BrokerConfig(
                api_key=self._get_required_env("COINBASE_API_KEY"),
                api_secret=self._get_required_env("COINBASE_API_SECRET"),
                sandbox=self._get_bool_env("COINBASE_SANDBOX", True),
            )
        
        return brokers
    
    @property
    def api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return {
            "url": self._get_env("API_URL", "http://localhost:8000"),
            "timeout": int(self._get_env("API_TIMEOUT", "30")),
            "retry_attempts": int(self._get_env("API_RETRY_ATTEMPTS", "3")),
            "retry_delay": int(self._get_env("API_RETRY_DELAY", "1")),
        }
    
    @property
    def risk_config(self) -> Dict[str, Any]:
        """Get risk management configuration"""
        return {
            "max_position_size": float(self._get_env("MAX_POSITION_SIZE", "100000")),
            "daily_loss_limit": float(self._get_env("DAILY_LOSS_LIMIT", "5000")),
            "max_open_trades": int(self._get_env("MAX_OPEN_TRADES", "10")),
            "min_account_equity": float(self._get_env("MIN_ACCOUNT_EQUITY", "25000")),
        }
    
    @property
    def feature_flags(self) -> Dict[str, bool]:
        """Get feature flags"""
        return {
            "paper_trading": self._get_bool_env("FEATURE_PAPER_TRADING", True),
            "backtesting": self._get_bool_env("FEATURE_BACKTESTING", True),
            "live_trading": self._get_bool_env("FEATURE_LIVE_TRADING", False),
            "options": self._get_bool_env("FEATURE_OPTIONS", False),
            "crypto": self._get_bool_env("FEATURE_CRYPTO", True),
            "forex": self._get_bool_env("FEATURE_FOREX", False),
        }
    
    @property
    def monitoring(self) -> Dict[str, Any]:
        """Get monitoring configuration"""
        return {
            "enable_metrics": self._get_bool_env("ENABLE_METRICS", True),
            "metrics_port": int(self._get_env("METRICS_PORT", "9090")),
            "enable_error_reporting": self._get_bool_env("ENABLE_ERROR_REPORTING", True),
            "error_reporting_url": self._get_env("ERROR_REPORTING_URL"),
            "enable_performance_monitoring": self._get_bool_env("ENABLE_PERFORMANCE_MONITORING", True),
        }
    
    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with default"""
        return os.getenv(key, default)
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable"""
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"Required environment variable '{key}' not set")
        return value
    
    def _get_bool_env(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def validate(self) -> bool:
        """Validate configuration for current environment"""
        try:
            # Required for all environments
            _ = self.database
            
            # Required for production
            if self.env == Environment.PRODUCTION:
                if not self.feature_flags.get("live_trading"):
                    logger.warning("Live trading is disabled in production")
                
                # Check at least one broker is configured
                if not self.brokers:
                    raise RuntimeError("No brokers configured for production")
            
            logger.info("Configuration validation passed")
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False


# Singleton instance
_config_instance: Optional[ProductionConfig] = None


def get_config(env: Environment = Environment.PRODUCTION) -> ProductionConfig:
    """Get or create production configuration instance"""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ProductionConfig(env)
        _config_instance.validate()
    
    return _config_instance


def reset_config():
    """Reset configuration instance (for testing)"""
    global _config_instance
    _config_instance = None
