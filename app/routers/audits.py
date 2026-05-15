import asyncio
import re
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_user
from app.db import get_session
from app.middleware.rate_limit import limiter
from app.middleware.ssrf import is_safe_url
from app.models.audit import Audit, AuditStatus
from app.models.user import User, UserRole
from app.reports.charts import render_issue_bar_chart, render_radar_chart
from app.reports.pdf import render_audit_pdf
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


@router.get("/{audit_id}/pdf")
async def get_audit_pdf(audit_id: UUID, db: SessionDep, user: UserDep) -> Response:
    audit = await _get_owned_audit(audit_id, db, user)
    if audit.status != AuditStatus.DONE:
        raise HTTPException(status_code=409, detail="Audyt jeszcze nie zakończony")
    pdf_bytes = await asyncio.to_thread(render_audit_pdf, audit)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_audit_filename(audit.url)}"'},
    )


def _audit_filename(url: str) -> str:
    host = urlparse(url).hostname or "audit"
    if host.startswith("www."):
        host = host[4:]
    name = host.rsplit(".", 1)[0]  # ucina TLD (.com, .pl, ...)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name) or "audit"
    return f"audit-{name}.pdf"


@router.get("/{audit_id}/chart.png")
async def get_audit_chart(
    audit_id: UUID,
    db: SessionDep,
    user: UserDep,
    chart_type: Annotated[str, Query(alias="type")] = "radar",
) -> Response:
    audit = await _get_owned_audit(audit_id, db, user)
    if audit.status != AuditStatus.DONE:
        raise HTTPException(status_code=409, detail="Audyt jeszcze nie zakończony")

    result = audit.result or {}
    if chart_type == "bar":
        categories = result.get("categories", {})
        data = {k: len(v.get("issues", [])) for k, v in categories.items()}
        png = await asyncio.to_thread(render_issue_bar_chart, data)
    else:
        png = await asyncio.to_thread(render_radar_chart, result.get("category_scores", {}))

    return Response(content=png, media_type="image/png")
