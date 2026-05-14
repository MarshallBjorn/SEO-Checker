import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.auth.dependencies import CurrentUserDep, DbDep, SessionDataDep
from app.middleware.ssrf import is_safe_url
from app.models.audit import Audit, AuditStatus
from app.models.user import UserRole
from app.schemas.audit import AuditSettings
from app.tasks.audit import run_audit
from app.templating import templates

router = APIRouter()


def _ctx(request, user, session_data, **extra) -> dict:
    ctx = {
        "request": request,
        "user": user,
        "csrf_token": session_data.get("csrf_token", "") if session_data else "",
    }
    ctx.update(extra)
    return ctx


@router.get("/", response_class=HTMLResponse)
async def index(user: CurrentUserDep):
    return RedirectResponse("/dashboard" if user else "/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: CurrentUserDep, session_data: SessionDataDep):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", _ctx(request, user, session_data))


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: CurrentUserDep, session_data: SessionDataDep):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "register.html", _ctx(request, user, session_data))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, user: CurrentUserDep, session_data: SessionDataDep, db: DbDep
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    result = await db.execute(
        select(Audit).where(Audit.user_id == user.id).order_by(Audit.created_at.desc()).limit(10)
    )
    audits = list(result.scalars().all())
    return templates.TemplateResponse(
        request, "dashboard.html", _ctx(request, user, session_data, audits=audits)
    )


@router.get("/audit/new", response_class=HTMLResponse)
async def audit_form(request: Request, user: CurrentUserDep, session_data: SessionDataDep):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "audit_form.html", _ctx(request, user, session_data))


@router.post("/ui/audit", response_class=HTMLResponse)
async def ui_create_audit(
    request: Request,
    user: CurrentUserDep,
    session_data: SessionDataDep,
    db: DbDep,
    url: Annotated[str, Form()],
    user_agent: Annotated[str, Form()] = "chrome_desktop",
    timeout_ms: Annotated[int, Form()] = 30000,
    viewport_mobile: Annotated[bool, Form()] = False,
    weight_meta: Annotated[int, Form()] = 20,
    weight_headings: Annotated[int, Form()] = 10,
    weight_images: Annotated[int, Form()] = 15,
    weight_links: Annotated[int, Form()] = 10,
    weight_performance: Annotated[int, Form()] = 25,
    weight_technicals: Annotated[int, Form()] = 10,
    weight_accessibility: Annotated[int, Form()] = 10,
    enable_meta: Annotated[bool, Form()] = False,
    enable_headings: Annotated[bool, Form()] = False,
    enable_images: Annotated[bool, Form()] = False,
    enable_links: Annotated[bool, Form()] = False,
    enable_performance: Annotated[bool, Form()] = False,
    enable_technicals: Annotated[bool, Form()] = False,
    enable_accessibility: Annotated[bool, Form()] = False,
):
    if user is None:
        return HTMLResponse(
            '<p class="text-red-600">Sesja wygasła — zaloguj się ponownie.</p>', status_code=403
        )

    try:
        audit_settings = AuditSettings(
            timeout_ms=timeout_ms,
            user_agent=user_agent,
            viewport="mobile" if viewport_mobile else "desktop",
            weight_meta=weight_meta,
            weight_headings=weight_headings,
            weight_images=weight_images,
            weight_links=weight_links,
            weight_performance=weight_performance,
            weight_technicals=weight_technicals,
            weight_accessibility=weight_accessibility,
            enable_meta=enable_meta,
            enable_headings=enable_headings,
            enable_images=enable_images,
            enable_links=enable_links,
            enable_performance=enable_performance,
            enable_technicals=enable_technicals,
            enable_accessibility=enable_accessibility,
        )
    except ValidationError:
        return HTMLResponse(
            '<p class="text-red-600">Nieprawidłowe ustawienia audytu.</p>', status_code=400
        )

    if not await asyncio.to_thread(is_safe_url, url):
        return HTMLResponse(
            '<p class="text-red-600">URL niedozwolony — adres prywatny/lokalny lub zły schemat.</p>',  # noqa: E501
            status_code=400,
        )

    audit = Audit(
        url=url,
        user_id=user.id,
        status=AuditStatus.PENDING,
        settings=audit_settings.model_dump(),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    run_audit.delay(str(audit.id))

    return templates.TemplateResponse(
        request, "partials/audit_status.html", _ctx(request, user, session_data, audit=audit)
    )


@router.get("/ui/audit/{audit_id}/status", response_class=HTMLResponse)
async def ui_audit_status(
    request: Request,
    audit_id: UUID,
    user: CurrentUserDep,
    session_data: SessionDataDep,
    db: DbDep,
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if audit is None or (audit.user_id != user.id and user.role != UserRole.ADMIN):
        raise HTTPException(status_code=404, detail="Audit not found")
    return templates.TemplateResponse(
        request,
        "partials/audit_status.html",
        _ctx(request, user, session_data, audit=audit),  # noqa: E501
    )


@router.get("/audit/{audit_id}", response_class=HTMLResponse)
async def audit_detail(
    request: Request,
    audit_id: UUID,
    user: CurrentUserDep,
    session_data: SessionDataDep,
    db: DbDep,
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    result = await db.execute(select(Audit).where(Audit.id == audit_id))
    audit = result.scalar_one_or_none()
    if audit is None or (audit.user_id != user.id and user.role != UserRole.ADMIN):
        raise HTTPException(status_code=404, detail="Audit not found")
    return templates.TemplateResponse(
        request, "audit_result.html", _ctx(request, user, session_data, audit=audit)
    )


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request, user: CurrentUserDep, session_data: SessionDataDep, db: DbDep):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    result = await db.execute(
        select(Audit).where(Audit.user_id == user.id).order_by(Audit.created_at.desc())
    )
    audits = list(result.scalars().all())
    return templates.TemplateResponse(
        request, "audit_history.html", _ctx(request, user, session_data, audits=audits)
    )


@router.get("/compare", response_class=HTMLResponse)
async def compare(
    request: Request,
    user: CurrentUserDep,
    session_data: SessionDataDep,
    db: DbDep,
    a: UUID,
    b: UUID,
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    async def _load(aid: UUID) -> Audit:
        res = await db.execute(select(Audit).where(Audit.id == aid))
        audit = res.scalar_one_or_none()
        if audit is None or (audit.user_id != user.id and user.role != UserRole.ADMIN):  # noqa: E501
            raise HTTPException(status_code=404, detail="Audit not found")
        return audit

    audit_a = await _load(a)
    audit_b = await _load(b)
    return templates.TemplateResponse(
        request,
        "audit_compare.html",
        _ctx(request, user, session_data, audit_a=audit_a, audit_b=audit_b),
    )
