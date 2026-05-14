from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues


async def collect(ctx: PageContext) -> CategoryResult:
    v = ctx.web_vitals
    issues: list[Issue] = []

    lcp = v.get("lcp_ms")
    if lcp is not None:
        if lcp > 4000:
            issues.append(Issue("error", f"LCP {lcp:.0f}ms (cel <2500ms)"))
        elif lcp > 2500:
            issues.append(Issue("warn", f"LCP {lcp:.0f}ms (cel <2500ms)"))

    cls = v.get("cls")
    if cls is not None:
        if cls > 0.25:
            issues.append(Issue("error", f"CLS {cls:.3f} (cel <0.1)"))
        elif cls > 0.1:
            issues.append(Issue("warn", f"CLS {cls:.3f} (cel <0.1)"))

    load = v.get("load_time_ms")
    if load is not None and load > 5000:
        issues.append(Issue("warn", f"Czas ładowania {load:.0f}ms (>5s)"))

    size = v.get("document_size_bytes")
    if size is not None and size > 1_000_000:
        issues.append(Issue("info", f"Duży dokument HTML ({size // 1024} KB)"))

    return CategoryResult("performance", score_from_issues(issues), issues, dict(v))
