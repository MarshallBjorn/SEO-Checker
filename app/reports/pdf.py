import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.models.audit import Audit
from app.reports.charts import render_issue_bar_chart, render_radar_chart

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _data_uri(png: bytes | None) -> str | None:
    if not png:
        return None
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def render_audit_pdf(audit: Audit) -> bytes:
    result = audit.result or {}
    categories = result.get("categories", {})
    category_scores = result.get("category_scores", {})
    issues_per_category = {k: len(v.get("issues", [])) for k, v in categories.items()}
    screenshots = result.get("screenshots", {})

    radar_uri = _data_uri(render_radar_chart(category_scores)) if category_scores else None
    bar_uri = (
        _data_uri(render_issue_bar_chart(issues_per_category)) if issues_per_category else None
    )  # noqa: E501

    html = _env.get_template("audit_report.html").render(  # noqa: E501
        audit=audit,
        result=result,
        categories=categories,
        radar_uri=radar_uri,
        bar_uri=bar_uri,
        desktop_shot="data:image/png;base64," + screenshots["desktop"]
        if screenshots.get("desktop")
        else None,
        mobile_shot="data:image/png;base64," + screenshots["mobile"]
        if screenshots.get("mobile")
        else None,
    )
    return HTML(string=html).write_pdf()
