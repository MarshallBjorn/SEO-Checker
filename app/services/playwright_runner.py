async def scrape_basic(url: str, timeout_ms: int = 30000) -> dict:
    """Proof of concept — page_title, status_code, final_url."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            title = await page.title()
            return {
                "page_title": title,
                "status_code": response.status if response else None,
                "final_url": page.url,
            }
        finally:
            await browser.close()
