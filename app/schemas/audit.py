from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.audit import AuditStatus


class AuditSettings(BaseModel):
    timeout_ms: int = Field(default=30000, ge=5000, le=60000)
    crawl_depth: int = Field(default=1, ge=1, le=3)
    user_agent: Literal["googlebot", "chrome_desktop", "mobile_safari"] = "chrome_desktop"
    viewport: Literal["desktop", "mobile"] = "desktop"
    follow_redirects: bool = True

    # wagi kategorii (suwaki UI)
    weight_meta: int = Field(default=20, ge=0, le=100)
    weight_headings: int = Field(default=10, ge=0, le=100)
    weight_images: int = Field(default=15, ge=0, le=100)
    weight_links: int = Field(default=10, ge=0, le=100)
    weight_performance: int = Field(default=25, ge=0, le=100)
    weight_technicals: int = Field(default=10, ge=0, le=100)
    weight_accessibility: int = Field(default=10, ge=0, le=100)

    # on/off kategorie (przełączniki UI)
    enable_meta: bool = True
    enable_headings: bool = True
    enable_images: bool = True
    enable_links: bool = True
    enable_performance: bool = True
    enable_technicals: bool = True
    enable_accessibility: bool = True


class AuditCreate(BaseModel):
    url: HttpUrl
    settings: AuditSettings = Field(default_factory=AuditSettings)


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    status: AuditStatus
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class AuditListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    status: AuditStatus
    created_at: datetime
    updated_at: datetime
