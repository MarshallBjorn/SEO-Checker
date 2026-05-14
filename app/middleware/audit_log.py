import re
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.sessions import get_session
from app.config import settings
from app.db import AsyncSessionLocal
from app.models.audit_log import AuditLog

# (path regex, metoda, nazwa akcji)
_LOGGABLE: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^/auth/login/?$"), "POST", "login"),
    (re.compile(r"^/auth/register/?$"), "POST", "user.register"),
    (re.compile(r"^/auth/logout/?$"), "POST", "logout"),
    (re.compile(r"^/audits/?$"), "POST", "audit.create"),
    (re.compile(r"^/audits/[^/]+/pdf/?$"), "GET", "audit.pdf"),
    (re.compile(r"^/audits/[^/]+/chart\.png$"), "GET", "audit.chart"),
    (re.compile(r"^/admin/.*"), "POST", "admin.action"),
]

_AUDIT_ID_RE = re.compile(r"^/audits/([^/]+)")


def _match_action(path: str, method: str) -> str | None:
    for pattern, expected_method, action in _LOGGABLE:
        if method == expected_method and pattern.match(path):
            return action
    return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        action = _match_action(request.url.path, request.method)
        if action is not None:
            try:
                await self._log(request, response, action)
            except Exception:  # noqa: BLE001 — logowanie nie może wywrócić requestu
                pass
        return response

    async def _log(self, request: Request, response: Response, action: str) -> None:
        user_id: UUID | None = None
        session_id = request.cookies.get(settings.session_cookie_name)
        if session_id:
            session_data = await get_session(session_id)
            if session_data:
                user_id = UUID(session_data["user_id"])

        resource_type: str | None = None
        resource_id: str | None = None
        if action.startswith("audit."):
            resource_type = "audit"
            match = _AUDIT_ID_RE.match(request.url.path)
            if match:
                resource_id = match.group(1)

        client = request.client
        async with AsyncSessionLocal() as db:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=client.host if client else None,
                    user_agent=(request.headers.get("user-agent") or "")[:500] or None,
                    success=response.status_code < 400,
                    details={"status_code": response.status_code, "method": request.method},
                )
            )
            await db.commit()
