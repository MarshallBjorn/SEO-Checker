from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.audit import Audit, AuditStatus
from app.schemas.audit import AuditCreate, AuditResponse
from app.tasks.audit import run_audit

router = APIRouter()


@router.post("", response_model=AuditResponse, status_code=status.HTTP_201_CREATED)
async def create_audit(
    payload: AuditCreate,
    db: AsyncSession = Depends(get_session),
) -> Audit:
    audit = Audit(url=str(payload.url), status=AuditStatus.PENDING)
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    run_audit.delay(str(audit.id))
    return audit


@router.get("/{audit_id}", response_model=AuditResponse)
async def get_audit(
    audit_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> Audit:
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit