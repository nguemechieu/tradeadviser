"""Application configuration using environment variables."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        os.getenv(
            "SOPOTEK_DATABASE_URL",
            "postgresql+asyncpg://sopotek:sopotek_local@localhost:5432/sopotek_trading"
        )
    )
    
    # API
    API_TITLE: str = "TradeAdviser API"
    API_VERSION: str = "2.0.0"
    API_DESCRIPTION: str = "REST API for Sopotek Quantitative Trading Platform"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sopotek-dev-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings instance.
    
    Returns:
        Settings: Application configuration
    """
    return Settings()
