from app.auditor.collectors.base import CategoryResult, Issue, PageContext, score_from_issues


async def collect(ctx: PageContext) -> CategoryResult:
    soup = ctx.soup
    issues: list[Issue] = []

    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    if not lang:
        issues.append(Issue("error", "Element <html> bez atrybutu lang"))

    imgs = soup.find_all("img")
    with_alt = sum(1 for i in imgs if i.get("alt") is not None)
    coverage = round(with_alt / len(imgs) * 100) if imgs else 100
    if coverage < 100:
        issues.append(Issue("error" if coverage < 50 else "warn", f"Pokrycie alt: {coverage}%"))

    unlabeled = 0
    for el in soup.find_all(["button", "a"]):
        if (
            not el.get_text(strip=True)
            and not el.get("aria-label")
            and not el.get("aria-labelledby")
            and not el.get("title")
        ):
            unlabeled += 1
    if unlabeled:
        issues.append(Issue("warn", f"{unlabeled} interaktywnych elementów bez etykiety"))

    raw = {"lang": lang, "alt_coverage_pct": coverage, "unlabeled_interactive": unlabeled}
    return CategoryResult("accessibility", score_from_issues(issues), issues, raw)
