from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.audit import AuditStatus


class AuditCreate(BaseModel):
    url: HttpUrl


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    status: AuditStatus
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime