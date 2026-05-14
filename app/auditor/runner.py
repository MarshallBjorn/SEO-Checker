import base64

from app.auditor.collectors import (
    accessibility,
    headings,
    images,
    links,
    meta,
    performance,
    technicals,
)
from app.auditor.collectors.base import PageContext
from app.auditor.scoring import final_score
from app.schemas.audit import AuditSettings

USER_AGENTS = {
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "chrome_desktop": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "mobile_safari": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
}

VIEWPORTS = {
    "desktop": {"width": 1366, "height": 768},
    "mobile": {"width": 390, "height": 844},
}

# (collector_module, enable_flag_field)
COLLECTORS = [
    ("meta", meta.collect, "enable_meta"),
    ("headings", headings.collect, "enable_headings"),
    ("images", images.collect, "enable_images"),
    ("links", links.collect, "enable_links"),
    ("performance", performance.collect, "enable_performance"),
    ("technicals", technicals.collect, "enable_technicals"),
    ("accessibility", accessibility.collect, "enable_accessibility"),
]

_WEB_VITALS_JS = """
() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  let lcp = null;
  try {
    const e = performance.getEntriesByType('largest-contentful-paint');
    if (e.length) lcp = e[e.length - 1].renderTime || e[e.length - 1].loadTime || null;
  } catch (_) {}
  let cls = 0;
  try {
    for (const e of performance.getEntriesByType('layout-shift')) {
      if (!e.hadRecentInput) cls += e.value;
    }
  } catch (_) { cls = null; }
  return {
    lcp_ms: lcp,
    cls: cls,
    load_time_ms: nav.loadEventEnd ? nav.loadEventEnd - nav.startTime : null,
    dom_content_loaded_ms: nav.domContentLoadedEventEnd
      ? nav.domContentLoadedEventEnd - nav.startTime : null,
  };
}
"""


async def _capture_screenshots(page) -> dict[str, str]:
    shots: dict[str, str] = {}
    for name, vp in VIEWPORTS.items():
        await page.set_viewport_size(vp)
        png = await page.screenshot(full_page=False)
        shots[name] = base64.b64encode(png).decode("ascii")
    return shots


async def run_full_audit(url: str, settings: AuditSettings) -> dict:
    """Orkiestruje wszystkie kolektory: render Playwright + Web Vitals + scoring."""
    import asyncio

    from bs4 import BeautifulSoup
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=USER_AGENTS[settings.user_agent],
                viewport=VIEWPORTS[settings.viewport],
            )
            page = await context.new_page()
            response = await page.goto(url, timeout=settings.timeout_ms, wait_until="load")
            html = await page.content()
            final_url = page.url
            status_code = response.status if response else None

            web_vitals = await page.evaluate(_WEB_VITALS_JS)
            web_vitals["document_size_bytes"] = len(html.encode("utf-8"))

            screenshots = await _capture_screenshots(page)
        finally:
            await browser.close()

    ctx = PageContext(
        url=url,
        final_url=final_url,
        status_code=status_code,
        html=html,
        soup=BeautifulSoup(html, "lxml"),
        settings=settings,
        web_vitals=web_vitals,
    )

    enabled = [(name, fn) for name, fn, flag in COLLECTORS if getattr(settings, flag)]
    results = await asyncio.gather(*[fn(ctx) for _, fn in enabled])

    score = final_score(results, settings)
    return {
        "url": url,
        "final_url": final_url,
        "status_code": status_code,
        "score": score,
        "categories": {r.category: r.as_dict() for r in results},
        "category_scores": {r.category: r.score for r in results},
        "screenshots": screenshots,
    }
