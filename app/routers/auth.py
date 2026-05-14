from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_user
from app.auth.passwords import hash_password, verify_password
from app.auth.sessions import create_session, delete_session
from app.config import settings
from app.db import get_session
from app.models.user import User, UserRole
from app.schemas.user import UserResponse

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_seconds,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    db: SessionDep,
    email: str = Form(...),
    password: str = Form(...),
) -> User:
    email = email.strip().lower()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć min. 8 znaków")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email już zarejestrowany")

    user = User(email=email, password_hash=hash_password(password), role=UserRole.USER)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    session_id, _ = await create_session(str(user.id))
    _set_session_cookie(response, session_id)
    if request.headers.get("HX-Request"):
        response.headers["HX-Redirect"] = "/dashboard"
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    request: Request,
    response: Response,
    db: SessionDep,
    email: str = Form(...),
    password: str = Form(...),
) -> User:
    email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Nieprawidłowy email lub hasło")

    session_id, _ = await create_session(str(user.id))
    _set_session_cookie(response, session_id)
    if request.headers.get("HX-Request"):
        response.headers["HX-Redirect"] = "/dashboard"
    return user


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        await delete_session(session_id)
    response.delete_cookie(settings.session_cookie_name)
    if request.headers.get("HX-Request"):
        response.headers["HX-Redirect"] = "/login"
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(require_user)]) -> User:
    return user
