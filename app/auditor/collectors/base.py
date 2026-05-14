from dataclasses import dataclass, field
from typing import Literal

from bs4 import BeautifulSoup

from app.schemas.audit import AuditSettings

Severity = Literal["info", "warn", "error"]

_PENALTY = {
    "info": 3,
    "warn": 10,
    "error": 20,
}


@dataclass
class Issue:
    severity: Severity
    message: str
    element: str | None = None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "message": self.message,
            "element": self.element,
        }


@dataclass
class CategoryResult:
    category: str
    score: int
    issues: list[Issue] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "score": self.score,
            "issues": [issue.as_dict() for issue in self.issues],
            "raw": self.raw,
        }


@dataclass
class PageContext:
    url: str
    final_url: str
    status_code: int | None
    html: str
    soup: BeautifulSoup
    settings: AuditSettings
    web_vitals: dict = field(default_factory=dict)


def score_from_issues(issues: list[Issue]) -> int:
    penalty = sum(_PENALTY[issue.severity] for issue in issues)
    return max(0, 100 - penalty)
