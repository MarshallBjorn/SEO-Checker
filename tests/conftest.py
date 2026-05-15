import uuid

import pytest
import redis.asyncio as aioredis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.auth.sessions as sessions_mod
import app.db as db_mod
from app.config import settings as app_settings
from app.main import app
from app.middleware import audit_log as audit_log_mw
from app.middleware import csrf as csrf_mw


@pytest.fixture(autouse=True)
def _patch_app_for_tests(monkeypatch):
    # 1. NullPool — każda sesja DB dostaje świeże połączenie asyncpg
    #    (eliminuje "another operation is in progress" przy TestClient)
    engine = create_async_engine(app_settings.database_url, poolclass=NullPool, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "async_engine", engine)
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(audit_log_mw, "AsyncSessionLocal", session_factory)

    # 2. Wyłącz BaseHTTPMiddleware (znany konflikt z asyncpg + TestClient task group).
    #    Logowanie akcji i CSRF testujemy osobno — tu nas tylko blokują.
    async def _passthrough(self, request, call_next):
        return await call_next(request)

    monkeypatch.setattr(audit_log_mw.AuditLogMiddleware, "dispatch", _passthrough)
    monkeypatch.setattr(csrf_mw.CSRFMiddleware, "dispatch", _passthrough)

    # 3. Slowapi off — 3/min na /auth/register wywaliłoby kolejne testy
    from app.middleware.rate_limit import limiter

    limiter.enabled = False

    # 4. Celery delay — no-op (nie kolejkujemy realnych audytów)
    from app.tasks import audit as audit_task

    monkeypatch.setattr(audit_task.run_audit, "delay", lambda *a, **kw: None)

    # 5. Re-init klienta Redis — module-level klient z poprzedniego testu
    #    trzyma się starego event loopa i rzuca "Event loop is closed"
    monkeypatch.setattr(
        sessions_mod,
        "_redis",
        aioredis.from_url(app_settings.session_redis_url, decode_responses=True),
    )


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"
