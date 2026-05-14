from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues


async def collect(ctx: PageContext) -> CategoryResult:
    soup = ctx.soup
    issues: list[Issue] = []

    tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    headings = [{"level": int(t.name[1]), "text": t.get_text(strip=True)[:120]} for t in tags]
    h1_count = sum(1 for h in headings if h["level"] == 1)

    if h1_count == 0:
        issues.append(Issue("error", "Brak nagłówka H1"))
    elif h1_count > 1:
        issues.append(Issue("warn", f"Wiele nagłówków H1 ({h1_count})"))

    prev = 0
    for h in headings:
        if prev and h["level"] > prev + 1:
            issues.append(Issue("warn", f"Skok poziomów: H{prev} → H{h['level']}"))
        prev = h["level"]

    if not headings:
        issues.append(Issue("error", "Strona nie ma żadnych nagłówków"))

    raw = {"headings": headings, "h1_count": h1_count, "total": len(headings)}
    return CategoryResult("headings", score_from_issues(issues), issues, raw)
