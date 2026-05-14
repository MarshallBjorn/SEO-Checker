from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues


async def collect(ctx: PageContext) -> CategoryResult:
    soup = ctx.soup
    issues = list[Issue] = []
    raw: dict = {}

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    raw["title"] = title
    if not title:
        issues.append(Issue("error", "Brak tagu <title>"))
    elif len(title) < 30:
        issues.append(Issue("warn", f"Title za krótki ({len(title)} zn., zalecane 30-60)"))
    elif len(title) > 60:
        issues.append(Issue("warn", f"Title za długi ({len(title)} zn., zalecane 30-60)"))

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag.get("content", "").strip() if desc_tag else None
    raw["description"] = desc
    if not desc:
        issues.append(Issue("error", "Brak meta description"))
    elif len(desc) < 120:
        issues.append(Issue("warn", f"Description za krótki ({len(desc)} zn., zalecane 120-160)"))
    elif len(desc) > 160:
        issues.append(Issue("warn", f"Description za długi ({len(desc)} zn., zalecane 120-160)"))

    canonical = soup.find("link", rel="canonical")
    raw["canonical"] = canonical.get("href") if canonical else None
    if not canonical:
        issues.append(Issue("warn", "Brak linku canonical"))

    for og in ("og:title", "og:description", "og:image"):
        tag = soup.find("meta", attrs={"property": og})
        raw[og] = tag.get("content") if tag else None
        if not tag:
            issues.append(Issue("info", f"Brak {og}"))

    viewport = soup.find("meta", attrs={"name": "viewport"})
    raw["viewport"] = viewport.get("content") if viewport else None
    if not viewport:
        issues.append(Issue("error", "Brak meta viewport"))

    return CategoryResult("meta", score_from_issues(issues), issues, raw)
