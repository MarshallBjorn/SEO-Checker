import asyncio
from urllib.parse import urljoin

import httpx

from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues

_MAX_CHECK = 30
_SIZE_LIMIT = 100_000


async def collect(ctx: PageContext) -> CategoryResult:
    soup = ctx.soup
    issues: list[Issue] = []
    imgs = soup.find_all("img")

    missing_alt = [img.get("src") or "(brak src)" for img in imgs if not img.get("alt")]
    not_lazy = [img.get("src") for img in imgs if img.get("src") and img.get("loading") != "lazy"]

    urls = [urljoin(ctx.final_url, img["src"]) for img in imgs if img.get("src")]
    large: list[dict] = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:

        async def head(u: str) -> dict | None:
            try:
                r = await client.head(u)
                cl = int(r.headers.get("content-length", 0))
                ct = r.headers.get("content-type", "")
                if cl > _SIZE_LIMIT and any(x in ct for x in ("jpeg", "jpg", "png")):
                    return {"url": u, "bytes": cl, "type": ct}
            except Exception:
                return None
            return None

        results = await asyncio.gather(*[head(u) for u in urls[:_MAX_CHECK]])
    large = [r for r in results if r]

    if missing_alt:
        issues.append(Issue("error", f"{len(missing_alt)} obrazów bez atrybutu alt"))
    if large:
        issues.append(Issue("warn", f"{len(large)} nieoptymalnych obrazów (>100KB)"))
    if len(not_lazy) > 3:
        issues.append(Issue("info", f'{len(not_lazy)} obrazów bez loading="lazy"'))

    raw = {
        "total": len(imgs),
        "missing_alt": missing_alt,
        "large_images": large,
        "not_lazy_count": len(not_lazy),
    }
    return CategoryResult("images", score_from_issues(issues), issues, raw)
