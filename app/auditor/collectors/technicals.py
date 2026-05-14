from urllib.parse import urlparse

import httpx

from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues


async def collect(ctx: PageContext) -> CategoryResult:
    issues: list[Issue] = []
    raw: dict = {}

    parsed = urlparse(ctx.final_url)
    raw["https"] = parsed.scheme == "https"
    if not raw["https"]:
        issues.append(Issue("error", "Strona nie używa HTTPS"))

    base = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_from_robots: str | None = None

    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        try:
            r = await client.get(f"{base}/robots.txt")
            raw["robots_txt"] = r.status_code == 200
            if r.status_code == 200:
                for line in r.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_from_robots = line.split(":", 1)[1].strip()
            else:
                issues.append(Issue("warn", "Brak robots.txt"))
        except Exception:
            raw["robots_txt"] = False
            issues.append(Issue("warn", "robots.txt niedostępny"))

        sitemap_url = sitemap_from_robots or f"{base}/sitemap.xml"
        try:
            r = await client.get(sitemap_url)
            raw["sitemap"] = r.status_code == 200
            if r.status_code != 200:
                issues.append(Issue("warn", "Brak sitemap.xml"))
        except Exception:
            raw["sitemap"] = False
            issues.append(Issue("warn", "sitemap niedostępny"))

    raw["redirected"] = ctx.url != ctx.final_url
    if raw["redirected"]:
        issues.append(Issue("info", f"Przekierowanie: {ctx.url} → {ctx.final_url}"))

    return CategoryResult("technicals", score_from_issues(issues), issues, raw)
