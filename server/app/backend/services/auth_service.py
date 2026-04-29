from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any

from repository.api_key_repository import ApiKeyRepository


class AuthService:
    def __init__(self, api_key_repository: ApiKeyRepository):
        self.api_key_repository = api_key_repository

    async def create_api_key(
            self,
            *,
            user_id: str,
            name: str,
            scopes: list[str],
            expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Create a TradeAdviser API key.

        The raw API key is returned only once.
        Only the SHA-256 hash should be stored in the database.
        """

        raw_key = f"ta_live_{secrets.token_urlsafe(48)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key_prefix = raw_key[:16]

        record = await self.api_key_repository.create_api_key(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes,
            expires_at=expires_at,
        )

        return {
            **self.api_key_repository.to_public_dict(record),
            "api_key": raw_key,
            "message": "Save this key now. It will not be shown again.",
        }

    async def list_api_keys(
            self,
            *,
            user_id: str,
    ) -> list[dict[str, Any]]:
        records = await self.api_key_repository.list_for_user(user_id=user_id)

        return [
            self.api_key_repository.to_public_dict(record)
            for record in records
        ]

    async def get_api_key(
            self,
            *,
            user_id: str,
            key_id: str,
    ) -> dict[str, Any]:
        record = await self.api_key_repository.get_for_user(
            user_id=user_id,
            key_id=key_id,
        )

        if record is None:
            raise ValueError("API key not found.")

        return self.api_key_repository.to_public_dict(record)

    async def update_api_key(
            self,
            *,
            user_id: str,
            key_id: str,
            data: dict[str, Any],
    ) -> dict[str, Any]:
        record = await self.api_key_repository.update_api_key(
            user_id=user_id,
            key_id=key_id,
            data=data,
        )

        return self.api_key_repository.to_public_dict(record)

    async def revoke_api_key(
            self,
            *,
            user_id: str,
            key_id: str,
    ) -> dict[str, Any]:
        revoked = await self.api_key_repository.revoke_api_key(
            user_id=user_id,
            key_id=key_id,
        )

        if not revoked:
            raise ValueError("API key not found.")

        return {
            "message": "API key revoked.",
            "key_id": key_id,
            "revoked": True,
        }

    async def validate_api_key(
            self,
            *,
            raw_key: str,
            required_scope: str | None = None,
    ) -> dict[str, Any]:
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        record = await self.api_key_repository.validate_key_hash(key_hash)

        if record is None:
            raise ValueError("Invalid or expired API key.")

        if required_scope is not None:
            has_scope = self.api_key_repository.require_scope(
                record,
                required_scope,
            )

            if not has_scope:
                raise ValueError("API key does not have the required scope.")

        return self.api_key_repository.to_public_dict(record)