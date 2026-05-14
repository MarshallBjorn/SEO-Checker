from app.auditor.collectors.base import CategoryResult
from app.schemas.audit import AuditSettings

CATEGORY_WEIGHT_FIELD = {
    "meta": "weight_meta",
    "headings": "weight_headings",
    "images": "weight_images",
    "links": "weight_links",
    "performance": "weight_performance",
    "technicals": "weight_technicals",
    "accessibility": "weight_accessibility",
}


def final_score(results: list[CategoryResult], settings: AuditSettings) -> int:
    """Final score = średnia ważona score'ów kategorii wg wag z AuditSettings."""
    total_weight = 0
    weighted_sum = 0
    for r in results:
        weight = getattr(settings, CATEGORY_WEIGHT_FIELD[r.category], 0)
        total_weight += weight
        weighted_sum += weight * r.score
    if total_weight == 0:
        return 0
    return round(weighted_sum / total_weight)
