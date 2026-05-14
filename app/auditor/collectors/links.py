import asyncio
from urllib.parse import urljoin, urlparse

import httpx

from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues

_MAX_CHECK = 40


async def collect(ctx: PageContext) -> CategoryResult:
    soup = ctx.soup
    issues: list[Issue] = []
    host = urlparse(ctx.final_url).netloc

    internal: list[str] = []
    external: list[str] = []
    nofollow_external = 0

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(ctx.final_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc == host:
            internal.append(full)
        else:
            external.append(full)
            if "nofollow" in (a.get("rel") or []):
                nofollow_external += 1

    to_check = list(dict.fromkeys(internal + external))[:_MAX_CHECK]
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:

        async def check(u: str) -> dict | None:
            try:
                r = await client.head(u)
                if r.status_code >= 400:
                    r = await client.get(u)
                if r.status_code >= 400:
                    return {"url": u, "status": r.status_code}
            except Exception:
                return {"url": u, "status": "error"}
            return None

        results = await asyncio.gather(*[check(u) for u in to_check])
    broken = [r for r in results if r]

    if broken:
        issues.append(Issue("error", f"{len(broken)} niedziałających linków (4xx/5xx)"))
    if external and nofollow_external == 0:
        issues.append(Issue("info", 'Żaden link zewnętrzny nie ma rel="nofollow"'))
    if not internal:
        issues.append(Issue("warn", "Brak linków wewnętrznych"))

    raw = {
        "internal_count": len(internal),
        "external_count": len(external),
        "nofollow_external": nofollow_external,
        "broken": broken,
        "checked": len(to_check),
    }
    return CategoryResult("links", score_from_issues(issues), issues, raw)
