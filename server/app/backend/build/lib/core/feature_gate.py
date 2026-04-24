from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth_service import get_current_user
from backend.db.session import get_db_session
from backend.models.user import User


async def is_feature_allowed(session: AsyncSession, user: User, feature_name: str) -> bool:
    del session, user, feature_name
    return True


def require_feature(feature_name: str) -> Callable[..., Awaitable[User]]:
    async def dependency(
        session: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> User:
        del session, feature_name
        return current_user

    return dependency
