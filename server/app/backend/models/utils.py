from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UtilsBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TwoFactorSetupRequest(UtilsBaseModel):
    password: str = Field(min_length=1)


class TwoFactorVerifyRequest(UtilsBaseModel):
    code: str = Field(min_length=4, max_length=12)
    remember_device: bool = False


class TwoFactorDisableRequest(UtilsBaseModel):
    password: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=12)


class CreateApiKeyRequest(UtilsBaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class UpdateApiKeyRequest(UtilsBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    scopes: list[str] | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None