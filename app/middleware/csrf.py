from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.csrf import verify_csrf_token
from app.auth.sessions import get_session
from app.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
# brak sesji w momencie wywołania — nie ma czego chronić
_EXEMPT_PATHS = {"/auth/login", "/auth/register"}
_FORM_CONTENT_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Chroni żądania form-encoded wysyłane z przeglądarki przez zalogowanego
    użytkownika. HTMX dosyła token nagłówkiem X-CSRF-Token (patrz base.html).
    Żądania JSON API są pomijane — SameSite=lax na ciastku sesji wystarcza,
    bo formularza cross-site nie da się wysłać jako application/json.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        if not content_type.startswith(_FORM_CONTENT_TYPES):
            return await call_next(request)

        session_id = request.cookies.get(settings.session_cookie_name)
        if not session_id:
            return await call_next(request)
        session_data = await get_session(session_id)
        if not session_data:
            return await call_next(request)

        received = request.headers.get("X-CSRF-Token")
        if not verify_csrf_token(session_data.get("csrf_token"), received):
            return JSONResponse(status_code=403, content={"detail": "Nieprawidłowy token CSRF"})

        return await call_next(request)
