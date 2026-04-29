from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.backend.models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    """
    Async repository for user account persistence.

    This repository does NOT handle password hashing, token creation,
    or business/security decisions. That belongs in the service layer.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Create
    # ============================================================

    async def create_user(self, data: dict[str, Any]) -> User:
        user = User(**data)

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    # ============================================================
    # Basic Getters
    # ============================================================

    async def get_by_id(self, user_id: str | UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username.strip())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> User | None:
        """
        Used for login.

        Identifier may be:
        - email
        - username
        - phone
        """

        clean_identifier = identifier.strip()
        email_identifier = clean_identifier.lower()

        stmt = select(User).where(
            or_(
                User.email == email_identifier,
                User.username == clean_identifier,
                User.phonenumber == clean_identifier,
                )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ============================================================
    # Availability Checks
    # ============================================================

    async def email_exists(self, email: str) -> bool:
        user = await self.get_by_email(email)
        return user is not None

    async def username_exists(self, username: str) -> bool:
        user = await self.get_by_username(username)
        return user is not None

    async def phone_exists(self, phone: str) -> bool:
        stmt = select(User).where(User.phonenumber == phone.strip())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def is_email_available(self, email: str) -> bool:
        return not await self.email_exists(email)

    async def is_username_available(self, username: str) -> bool:
        return not await self.username_exists(username)

    async def is_phone_available(self, phone: str) -> bool:
        return not await self.phone_exists(phone)

    # ============================================================
    # Update
    # ============================================================

    async def update_user(
            self,
            user_id: str | UUID,
            data: dict[str, Any],
    ) -> User:
        data = dict(data)
        data["updated_at"] = utc_now()

        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(**data)
            .returning(User)
        )

        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("User not found.")

        await self.db.flush()
        return user

    async def update_profile(
            self,
            user_id: str | UUID,
            data: dict[str, Any],
    ) -> User:
        allowed_fields = {
            "username",
            "display_name",
            "firstname",
            "middlename",
            "lastname",
            "phone",
            "birthdate",
            "avatar_url",
            "timezone",
            "locale",
        }

        clean_data = {
            key: value
            for key, value in data.items()
            if key in allowed_fields
        }

        if not clean_data:
            user = await self.get_by_id(user_id)
            if user is None:
                raise ValueError("User not found.")
            return user

        return await self.update_user(user_id, clean_data)

    async def update_password_hash(
            self,
            user_id: str | UUID,
            password_hash: str,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "password_hash": password_hash,
                "password_changed_at": utc_now(),
            },
        )

    # ============================================================
    # Login / Security State
    # ============================================================

    async def mark_login_success(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "last_login_at": utc_now(),
                "failed_login_attempts": 0,
                "locked_until": None,
            },
        )

    async def mark_login_failure(
            self,
            user_id: str | UUID,
            failed_attempts: int,
            locked_until: datetime | None = None,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "failed_login_attempts": failed_attempts,
                "locked_until": locked_until,
            },
        )

    async def lock_user(
            self,
            user_id: str | UUID,
            locked_until: datetime,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "locked_until": locked_until,
            },
        )

    async def unlock_user(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "failed_login_attempts": 0,
                "locked_until": None,
            },
        )

    # ============================================================
    # Email Verification
    # ============================================================

    async def mark_email_verified(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "email_verified": True,
                "email_verified_at": utc_now(),
            },
        )

    async def mark_email_unverified(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "email_verified": False,
                "email_verified_at": None,
            },
        )

    # ============================================================
    # Two-Factor Authentication
    # ============================================================

    async def set_pending_two_factor_secret(
            self,
            user_id: str | UUID,
            secret: str,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "two_factor_pending_secret": secret,
            },
        )

    async def enable_two_factor(
            self,
            user_id: str | UUID,
            secret: str,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "two_factor_enabled": True,
                "two_factor_secret": secret,
                "two_factor_pending_secret": None,
                "two_factor_enabled_at": utc_now(),
            },
        )

    async def disable_two_factor(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "two_factor_enabled": False,
                "two_factor_secret": None,
                "two_factor_pending_secret": None,
                "two_factor_enabled_at": None,
            },
        )

    # ============================================================
    # Account Lifecycle
    # ============================================================

    async def deactivate_account(
            self,
            user_id: str | UUID,
            reason: str | None = None,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "is_active": False,
                "deactivation_reason": reason,
                "deactivated_at": utc_now(),
            },
        )

    async def reactivate_account(
            self,
            user_id: str | UUID,
    ) -> User:
        return await self.update_user(
            user_id,
            {
                "is_active": True,
                "deactivation_reason": None,
                "deactivated_at": None,
            },
        )

    async def soft_delete_account(
            self,
            user_id: str | UUID,
            reason: str | None = None,
    ) -> User:
        """
        Soft delete the account.

        For a financial app, avoid hard-deleting users because trade history,
        audit events, tax records, and broker references may need to remain.
        """

        return await self.update_user(
            user_id,
            {
                "is_active": False,
                "is_deleted": True,
                "deleted_at": utc_now(),
                "delete_reason": reason,
            },
        )

    # ============================================================
    # Admin / Utility
    # ============================================================

    async def list_users(
            self,
            limit: int = 100,
            offset: int = 0,
            include_deleted: bool = False,
    ) -> list[User]:
        stmt = select(User).limit(limit).offset(offset)

        if not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_users(
            self,
            query: str,
            limit: int = 50,
    ) -> list[User]:
        pattern = f"%{query.strip()}%"

        stmt = (
            select(User)
            .where(
                or_(
                    User.email.ilike(pattern),
                    User.username.ilike(pattern),
                    User.display_name.ilike(pattern),
                    User.firstname.ilike(pattern),
                    User.lastname.ilike(pattern),
                    User.middlename.ilike(pattern),
                    User.phonenumber.ilike(pattern),
                )
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_users(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count(User.id))
        result = await self.db.execute(stmt)
        return int(result.scalar_one())