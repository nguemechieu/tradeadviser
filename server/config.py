"""Application configuration using environment variables."""

import os
from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sopotek:sopotek_local@localhost:5432/sopotek_trading"
    
    # API
    API_TITLE: str = "TradeAdviser API"
    API_VERSION: str = "2.0.0"
    API_DESCRIPTION: str = "REST API for Sopotek Quantitative Trading Platform"
    
    # Security
    SECRET_KEY: str = "sopotek-dev-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS - read as string from env, parse via property
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    # Logging
    LOG_LEVEL: str = "info"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins or ["*"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings instance.
    
    Returns:
        Settings: Application configuration
    """
    return Settings()
    
    Returns:
        Settings: Application configuration
    """
    return Settings()
