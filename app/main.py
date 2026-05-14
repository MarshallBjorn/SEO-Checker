from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import limiter
from app.routers.audits import router as audits_router
from app.routers.auth import router as auth_router

app = FastAPI(title="SEO Auditor", version="0.1.0")


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(CSRFMiddleware)
app.add_middleware(AuditLogMiddleware)


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audits_router, prefix="/audits", tags=["audits"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
