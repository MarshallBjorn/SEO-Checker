import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_user
from app.db import get_session
from app.middleware.rate_limit import limiter
from app.middleware.ssrf import is_safe_url
from app.models.audit import Audit, AuditStatus
from app.models.user import User, UserRole
from app.schemas.audit import AuditCreate, AuditListItem, AuditResponse
from app.tasks.audit import run_audit

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(require_user)]


async def _get_owned_audit(audit_id: UUID, db: AsyncSession, user: User) -> Audit:
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Brak dostępu do tego audytu")
    return audit


@router.post("", response_model=AuditResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_audit(
    request: Request, payload: AuditCreate, db: SessionDep, user: UserDep
) -> Audit:
    if not await asyncio.to_thread(is_safe_url, str(payload.url)):
        raise HTTPException(
            status_code=400,
            detail="URL niedozwolony — adres prywatny/lokalny lub nieobsługiwany schemat",
        )

    audit = Audit(
        url=str(payload.url),
        user_id=user.id,
        status=AuditStatus.PENDING,
        settings=payload.settings.model_dump(),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    run_audit.delay(str(audit.id))
    return audit


@router.get("", response_model=list[AuditListItem])
async def list_audits(db: SessionDep, user: UserDep) -> list[Audit]:
    result = await db.execute(
        select(Audit).where(Audit.user_id == user.id).order_by(Audit.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{audit_id}", response_model=AuditResponse)
async def get_audit(audit_id: UUID, db: SessionDep, user: UserDep) -> Audit:
    return await _get_owned_audit(audit_id, db, user)
