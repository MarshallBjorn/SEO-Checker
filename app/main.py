from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import limiter
from app.routers.admin import router as admin_router
from app.routers.audits import router as audits_router
from app.routers.auth import router as auth_router
from app.routers.frontend import router as frontend_router

app = FastAPI(title="SEO Auditor", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ostatni dodany = najbardziej zewnętrzny
app.add_middleware(CSRFMiddleware)
app.add_middleware(AuditLogMiddleware)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audits_router, prefix="/audits", tags=["audits"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(frontend_router, tags=["frontend"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
