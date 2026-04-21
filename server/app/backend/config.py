"""Server configuration for the hybrid Sopotek architecture."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Process configuration for the server trading core."""

    app_name: str = "Sopotek Quant System Server"
    api_prefix: str = "/api/v1"
    ws_path: str = "/ws/events"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="SOPOTEK_SERVER_",
        extra="ignore",
    )
    
    
settings = ServerSettings()