from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_key import ApiKey


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TRADEADVISER_API_KEY_SCOPES: set[str] = {
    "read:account",
    "read:portfolio",
    "read:market-data",
    "read:orders",
    "write:orders",
    "trade:paper",
    "trade:live",
    "admin:workspace",
}


class ApiKeyRepository:
    """
    Async repository for TradeAdviser API keys.

    This repository stores and returns API key metadata.

    Security rule:
        Never store the raw API key.
        Store only:
            - key_hash
            - key_prefix
            - metadata
    """

    def __init__(self, db: AsyncSession):
        self.db = db



    # ============================================================
    # Getters
    # ============================================================

    async def get_by_id(
            self,
            key_id: str | UUID,
    ) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_user(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
    ) -> ApiKey | None:
        stmt = (
            select(ApiKey)
            .where(ApiKey.id == key_id)
            .where(ApiKey.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(
            self,
            key_hash: str,
    ) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
            self,
            user_id: str | UUID,
            *,
            include_revoked: bool = False,
            include_inactive: bool = True,
            limit: int = 100,
    ) -> list[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
            .limit(max(1, int(limit)))
        )

        if not include_revoked:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))

        if not include_inactive:
            stmt = stmt.where(ApiKey.is_active.is_(True))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_user(
            self,
            user_id: str | UUID,
            *,
            limit: int = 100,
    ) -> list[ApiKey]:
        now = utc_now()

        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .where(ApiKey.is_active.is_(True))
            .where(ApiKey.revoked_at.is_(None))
            .where((ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now))
            .order_by(ApiKey.created_at.desc())
            .limit(max(1, int(limit)))
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # Validation
    # ============================================================

    async def validate_key_hash(
            self,
            key_hash: str,
    ) -> ApiKey | None:
        record = await self.get_by_hash(key_hash)

        if record is None:
         return None

        if not self.is_record_active(record):
         return None

        await self.mark_used(cast(str | UUID, cast(object, record.id)))
        return record

    @staticmethod
    def is_record_active(record: ApiKey) -> bool:
        now = utc_now()

        if not bool(getattr(record, "is_active", False)):
            return False

        if getattr(record, "revoked_at", None) is not None:
            return False

        expires_at = getattr(record, "expires_at", None)
        if expires_at is not None and expires_at <= now:
            return False

        return True

    @classmethod
    def require_scope(
            cls,
            record: ApiKey,
            scope: str,
    ) -> bool:
        scopes = set(getattr(record, "scopes", []) or [])
        return scope in scopes

    # ============================================================
    # Updates
    # ============================================================

    async def update_api_key(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
            data: dict[str, Any],
    ) -> ApiKey:
        record = await self.get_for_user(user_id=user_id, key_id=key_id)

        if record is None:
            raise ValueError("API key not found.")

        update_data: dict[str, Any] = {}

        if "name" in data and data["name"] is not None:
            clean_name = str(data["name"]).strip()
            if not clean_name:
                raise ValueError("API key name cannot be empty.")
            update_data["name"] = clean_name

        if "scopes" in data and data["scopes"] is not None:
            clean_scopes = self.normalize_scopes(data["scopes"])
            invalid_scopes = self.invalid_scopes(clean_scopes)

            if invalid_scopes:
                raise ValueError(f"Invalid API key scopes: {', '.join(invalid_scopes)}")

            update_data["scopes"] = clean_scopes

        if "is_active" in data and data["is_active"] is not None:
            update_data["is_active"] = bool(data["is_active"])

        if "expires_at" in data:
            update_data["expires_at"] = data["expires_at"]

        if not update_data:
            return record

        update_data["updated_at"] = utc_now()

        stmt = (
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .where(ApiKey.user_id == user_id)
            .values(**update_data)
            .returning(ApiKey)
        )

        result = await self.db.execute(stmt)
        updated = result.scalar_one_or_none()

        if updated is None:
            raise ValueError("API key not found.")

        await self.db.flush()
        return updated

    async def rename_api_key(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
            name: str,
    ) -> ApiKey:
        return await self.update_api_key(
            user_id=user_id,
            key_id=key_id,
            data={"name": name},
        )

    async def set_scopes(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
            scopes: list[str],
    ) -> ApiKey:
        return await self.update_api_key(
            user_id=user_id,
            key_id=key_id,
            data={"scopes": scopes},
        )

    async def set_active(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
            is_active: bool,
    ) -> ApiKey:
        return await self.update_api_key(
            user_id=user_id,
            key_id=key_id,
            data={"is_active": is_active},
        )

    async def mark_used(
            self,
            key_id: str | UUID,
    ) -> str|None:
        """

        :rtype: None
        """
        stmt = (
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(last_used_at=utc_now())
        )

        await self.db.execute(stmt)
        await self.db.flush()

    # ============================================================
    # Revoke
    # ============================================================

    async def revoke_api_key(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
    ) -> bool:
        stmt = (
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .where(ApiKey.user_id == user_id)
            .where(ApiKey.revoked_at.is_(None))
            .values(
                is_active=False,
                revoked_at=utc_now(),
                updated_at=utc_now(),
            )
            .returning(ApiKey.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.scalar_one_or_none() is not None

    async def revoke_all_for_user(
            self,
            user_id: str | UUID,
    ) -> int:
        stmt = (
            update(ApiKey)
            .where(ApiKey.user_id == user_id)
            .where(ApiKey.revoked_at.is_(None))
            .values(
                is_active=False,
                revoked_at=utc_now(),
                updated_at=utc_now(),
            )
            .returning(ApiKey.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    # ============================================================
    # Delete / Cleanup
    # ============================================================

    async def delete_api_key(
            self,
            *,
            user_id: str | UUID,
            key_id: str | UUID,
    ) -> bool:
        """
        Hard-delete an API key.

        Prefer revoke_api_key() for production auditability.
        """

        stmt = (
            delete(ApiKey)
            .where(ApiKey.id == key_id)
            .where(ApiKey.user_id == user_id)
            .returning(ApiKey.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.scalar_one_or_none() is not None

    async def delete_revoked(self) -> int:
        stmt = (
            delete(ApiKey)
            .where(ApiKey.revoked_at.is_not(None))
            .returning(ApiKey.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    async def delete_expired(self) -> int:
        now = utc_now()

        stmt = (
            delete(ApiKey)
            .where(ApiKey.expires_at.is_not(None))
            .where(ApiKey.expires_at <= now)
            .returning(ApiKey.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    # ============================================================
    # Scope Helpers
    # ============================================================

    @staticmethod
    def normalize_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
        if not scopes:
            return []

        return sorted(
            {
                str(scope).strip()
                for scope in scopes
                if str(scope or "").strip()
            }
        )

    @staticmethod
    def invalid_scopes(scopes: list[str]) -> list[str]:
        return [
            scope
            for scope in scopes
            if scope not in TRADEADVISER_API_KEY_SCOPES
        ]

    # ============================================================
    # Serialization
    # ============================================================

    @staticmethod
    def to_public_dict(record: ApiKey) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "key_id": str(record.id),
            "user_id": str(record.user_id),
            "name": record.name,
            "key_prefix": record.key_prefix,
            "scopes": list(record.scopes or []),
            "is_active": bool(record.is_active),
            "active": ApiKeyRepository.is_record_active(record),
            "created_at": record.created_at.isoformat()
            if getattr(record, "created_at", None)
            else None,
            "updated_at": record.updated_at.isoformat()
            if getattr(record, "updated_at", None)
            else None,
            "expires_at": record.expires_at.isoformat()
            if getattr(record, "expires_at", None)
            else None,
            "revoked_at": record.revoked_at.isoformat()
            if getattr(record, "revoked_at", None)
            else None,
            "last_used_at": record.last_used_at.isoformat()
            if getattr(record, "last_used_at", None)
            else None,
        }

    # ============================================================
    # Create
    # ============================================================

    async def create_api_key(
        self,
        *,
        user_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
        scopes: list[str],
        expires_at: datetime | None = None,
) -> ApiKey:
     clean_name = str(name or "").strip()

     if not clean_name:
        raise ValueError("API key name is required.")

     clean_scopes = self.normalize_scopes(scopes)
     invalid_scopes = self.invalid_scopes(clean_scopes)

     if invalid_scopes:
        raise ValueError(f"Invalid API key scopes: {', '.join(invalid_scopes)}")

     record = ApiKey(
        user_id=user_id,
        name=clean_name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=clean_scopes,
        expires_at=expires_at,
        is_active=True,
    )

     self.db.add(record)
     await self.db.flush()
     await self.db.refresh(record)

     return record