from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import get_session
from app.config import settings
from app.db import get_session as get_db_session
from app.models.user import User, UserRole


async def get_session_data(request: Request) -> dict | None:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    return await get_session(session_id)


SessionDataDep = Annotated[dict | None, Depends(get_session_data)]
DbDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    session_data: SessionDataDep,
    db: DbDep,
) -> User | None:
    if not session_data:
        return None
    result = await db.execute(select(User).where(User.id == UUID(session_data["user_id"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


CurrentUserDep = Annotated[User | None, Depends(get_current_user)]


async def require_user(user: CurrentUserDep) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wymagane zalogowanie")
    return user


RequireUserDep = Annotated[User, Depends(require_user)]


async def require_admin(user: RequireUserDep) -> User:
    if user is None or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Wymagane uprawnienia administratora"
        )
    return user
