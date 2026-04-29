from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.token import AuthToken


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TokenRepository:
    """
    Async repository for auth access/refresh token persistence.

    Expected AuthToken model fields:
        id
        user_id

        token_hash
        refresh_token_hash
        token_type

        expires_at
        refresh_expires_at

        revoked_at
        created_at
        last_used_at

        device_name
        device_id
        ip_address
        user_agent
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Create
    # ============================================================

    async def create_token(
            self,
            *,
            user_id: str | UUID,
            token_hash: str,
            refresh_token_hash: str,
            expires_at: datetime,
            refresh_expires_at: datetime,
            token_type: str = "bearer",
            device_name: str | None = None,
            device_id: str | None = None,
            ip_address: str | None = None,
            user_agent: str | None = None,
    ) -> AuthToken:
        record = AuthToken(
            user_id=user_id,
            token_hash=token_hash,
            refresh_token_hash=refresh_token_hash,
            token_type=token_type,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            device_name=device_name,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        return record

    # ============================================================
    # Getters
    # ============================================================

    async def get_by_id(self, token_id: str | UUID) -> AuthToken | None:
        stmt = select(AuthToken).where(AuthToken.id == token_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_access_hash(self, token_hash: str) -> AuthToken | None:
        stmt = select(AuthToken).where(AuthToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_refresh_hash(self, refresh_token_hash: str) -> AuthToken | None:
        stmt = select(AuthToken).where(
            AuthToken.refresh_token_hash == refresh_token_hash
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
            self,
            user_id: str | UUID,
            *,
            include_revoked: bool = False,
            limit: int = 100,
    ) -> list[AuthToken]:
        stmt = (
            select(AuthToken)
            .where(AuthToken.user_id == user_id)
            .order_by(AuthToken.created_at.desc())
            .limit(max(1, int(limit)))
        )

        if not include_revoked:
            stmt = stmt.where(AuthToken.revoked_at.is_(None))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_user(
            self,
            user_id: str | UUID,
            *,
            limit: int = 100,
    ) -> list[AuthToken]:
        now = utc_now()

        stmt = (
            select(AuthToken)
            .where(AuthToken.user_id == user_id)
            .where(AuthToken.revoked_at.is_(None))
            .where(AuthToken.refresh_expires_at > now)
            .order_by(AuthToken.created_at.desc())
            .limit(max(1, int(limit)))
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ============================================================
    # State Checks
    # ============================================================

    @staticmethod
    def is_access_token_active(record: AuthToken) -> bool:
        now = utc_now()

        if getattr(record, "revoked_at", None) is not None:
            return False

        expires_at = getattr(record, "expires_at", None)
        if expires_at is None:
            return False

        return expires_at > now

    @staticmethod
    def is_refresh_token_active(record: AuthToken) -> bool:
        now = utc_now()

        if getattr(record, "revoked_at", None) is not None:
            return False

        refresh_expires_at = getattr(record, "refresh_expires_at", None)
        if refresh_expires_at is None:
            return False

        return refresh_expires_at > now

    async def validate_access_hash(self, token_hash: str) -> AuthToken | None:
        record = await self.get_by_access_hash(token_hash)

        if record is None:
            return None

        if not self.is_access_token_active(record):
            return None

        await self.mark_used(record.id)

        return record

    async def validate_refresh_hash(self, refresh_token_hash: str) -> AuthToken | None:
        record = await self.get_by_refresh_hash(refresh_token_hash)

        if record is None:
            return None

        if not self.is_refresh_token_active(record):
            return None

        await self.mark_used(record.id)

        return record

    # ============================================================
    # Updates
    # ============================================================

    async def mark_used(self, token_id: str | UUID) -> None:
        stmt = (
            update(AuthToken)
            .where(AuthToken.id == token_id)
            .values(last_used_at=utc_now())
        )

        await self.db.execute(stmt)
        await self.db.flush()

    async def rotate_token(
            self,
            token_id: str | UUID,
            *,
            token_hash: str,
            refresh_token_hash: str,
            expires_at: datetime,
            refresh_expires_at: datetime,
    ) -> AuthToken:
        stmt = (
            update(AuthToken)
            .where(AuthToken.id == token_id)
            .values(
                token_hash=token_hash,
                refresh_token_hash=refresh_token_hash,
                expires_at=expires_at,
                refresh_expires_at=refresh_expires_at,
                revoked_at=None,
                last_used_at=utc_now(),
            )
            .returning(AuthToken)
        )

        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            raise ValueError("Token record not found.")

        await self.db.flush()
        return record

    # ============================================================
    # Revoke
    # ============================================================

    async def revoke(self, token_id: str | UUID) -> bool:
        stmt = (
            update(AuthToken)
            .where(AuthToken.id == token_id)
            .where(AuthToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.scalar_one_or_none() is not None

    async def revoke_by_access_hash(self, token_hash: str) -> bool:
        stmt = (
            update(AuthToken)
            .where(AuthToken.token_hash == token_hash)
            .where(AuthToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.scalar_one_or_none() is not None

    async def revoke_by_refresh_hash(self, refresh_token_hash: str) -> bool:
        stmt = (
            update(AuthToken)
            .where(AuthToken.refresh_token_hash == refresh_token_hash)
            .where(AuthToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.scalar_one_or_none() is not None

    async def revoke_all_for_user(self, user_id: str | UUID) -> int:
        stmt = (
            update(AuthToken)
            .where(AuthToken.user_id == user_id)
            .where(AuthToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    async def revoke_other_tokens_for_user(
            self,
            user_id: str | UUID,
            *,
            keep_token_id: str | UUID,
    ) -> int:
        stmt = (
            update(AuthToken)
            .where(AuthToken.user_id == user_id)
            .where(AuthToken.id != keep_token_id)
            .where(AuthToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    # ============================================================
    # Cleanup
    # ============================================================

    async def delete_expired(self) -> int:
        now = utc_now()

        stmt = (
            delete(AuthToken)
            .where(AuthToken.refresh_expires_at <= now)
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    async def delete_revoked(self) -> int:
        stmt = (
            delete(AuthToken)
            .where(AuthToken.revoked_at.is_not(None))
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    async def delete_for_user(self, user_id: str | UUID) -> int:
        stmt = (
            delete(AuthToken)
            .where(AuthToken.user_id == user_id)
            .returning(AuthToken.id)
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return len(list(result.scalars().all()))

    # ============================================================
    # Serialization
    # ============================================================

    @staticmethod
    def to_public_dict(record: AuthToken) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "user_id": str(record.user_id),
            "token_type": getattr(record, "token_type", "bearer"),
            "expires_at": record.expires_at.isoformat()
            if getattr(record, "expires_at", None)
            else None,
            "refresh_expires_at": record.refresh_expires_at.isoformat()
            if getattr(record, "refresh_expires_at", None)
            else None,
            "revoked_at": record.revoked_at.isoformat()
            if getattr(record, "revoked_at", None)
            else None,
            "created_at": record.created_at.isoformat()
            if getattr(record, "created_at", None)
            else None,
            "last_used_at": record.last_used_at.isoformat()
            if getattr(record, "last_used_at", None)
            else None,
            "device_name": getattr(record, "device_name", None),
            "device_id": getattr(record, "device_id", None),
            "ip_address": getattr(record, "ip_address", None),
            "user_agent": getattr(record, "user_agent", None),
            "active": TokenRepository.is_refresh_token_active(record),
        }