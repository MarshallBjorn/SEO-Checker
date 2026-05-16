from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.auth.dependencies import CurrentUserDep, DbDep, SessionDataDep
from app.models.audit import Audit
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
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


def _guard(user) -> RedirectResponse | None:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Wymagane uprawnienia administratora")
    return None


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, user: CurrentUserDep, session_data: SessionDataDep, db: DbDep
):
    if (redirect := _guard(user)) is not None:
        return redirect
    users_count = await db.scalar(select(func.count(User.id)))
    audits_count = await db.scalar(select(func.count(Audit.id)))
    logs_count = await db.scalar(select(func.count(AuditLog.id)))
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context=_ctx(
            request,
            user,
            session_data,
            users_count=users_count,
            audits_count=audits_count,
            logs_count=logs_count,
        ),
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request, user: CurrentUserDep, session_data: SessionDataDep, db: DbDep
):
    if (redirect := _guard(user)) is not None:
        return redirect
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = list(result.scalars().all())
    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context=_ctx(request, user, session_data, users=users),
    )


@router.get("/audit-log", response_class=HTMLResponse)
async def admin_audit_log(
    request: Request, user: CurrentUserDep, session_data: SessionDataDep, db: DbDep
):
    if (redirect := _guard(user)) is not None:
        return redirect
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    logs = list(result.scalars().all())
    return templates.TemplateResponse(
        request=request,
        name="admin_audit_log.html",
        context=_ctx(request, user, session_data, logs=logs),
    )


@router.get("/backups", response_class=HTMLResponse)
async def admin_backups(request: Request, user: CurrentUserDep, session_data: SessionDataDep):
    if (redirect := _guard(user)) is not None:
        return redirect
    from app.services.backup import list_snapshots

    snapshots = await list_snapshots()
    return templates.TemplateResponse(
        request=request,
        name="admin_backups.html",
        context=_ctx(request, user, session_data, snapshots=snapshots),
    )


@router.post("/backups/trigger")
async def admin_trigger_backup(user: CurrentUserDep, session_data: SessionDataDep):
    if (redirect := _guard(user)) is not None:
        return redirect
    from app.tasks.backup import run_backup

    run_backup.delay()
    return {"status": "triggered"}
