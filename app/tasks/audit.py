import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.audit import Audit, AuditStatus
from app.services.playwright_runner import scrape_basic
from app.tasks.celery_app import celery_app


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False, future=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _run_audit_async(audit_id: str) -> None:
    session_factory = _make_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Audit).where(Audit.id == UUID(audit_id)))
        audit = result.scalar_one_or_none()
        if audit is None:
            return

        audit.status = AuditStatus.RUNNING
        await session.commit()

        try:
            scrape_result = await scrape_basic(
                audit.url, timeout_ms=settings.playwright_timeout_ms
            )
            audit.result = scrape_result
            audit.status = AuditStatus.DONE
        except Exception as e:  # noqa: BLE001
            audit.error = str(e)
            audit.status = AuditStatus.FAILED

        await session.commit()


@celery_app.task(name="run_audit", bind=True, max_retries=3)
def run_audit(self, audit_id: str) -> None:  # noqa: ARG001
    asyncio.run(_run_audit_async(audit_id))