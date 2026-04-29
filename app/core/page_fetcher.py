import asyncio
from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup

VIZ_HOSTS = (
    "flo.uri.sh",
    "flourish.studio",
    "datawrapper.dwcdn.net",
    "public.tableau.com",
    "infogram.com",
    "e.infogram.com",
    "charts.ap.org",
    "graphics.reuters.com",
    "ig.ft.com",
)

VIZ_TITLES = ("interactive", "visual content", "chart", "graph", "data")


def _is_viz_iframe(tag) -> bool:
    src = tag.get("src") or ""
    title = (tag.get("title") or "").lower()
    return any(host in src for host in VIZ_HOSTS) or any(t in title for t in VIZ_TITLES)


async def _fetch_page(browser: Browser, url: str, timeout_ms: int) -> str:
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = await context.new_page()
    await page.goto(url, wait_until="load", timeout=timeout_ms)
    await page.wait_for_timeout(3000)
    html = await page.content()
    await context.close()
    return html


async def fetch_rendered_html(url: str, timeout_ms: int = 30000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        main_html = await _fetch_page(browser, url, timeout_ms)

        soup = BeautifulSoup(main_html, "html.parser")
        viz_urls = [
            tag["src"] for tag in soup.find_all("iframe")
            if _is_viz_iframe(tag) and tag.get("src")
        ]

        if viz_urls:
            iframe_htmls = await asyncio.gather(*[
                _fetch_page(browser, str(viz_url), timeout_ms)
                for viz_url in viz_urls
            ])
        else:
            iframe_htmls = []

        await browser.close()

    return main_html + "\n".join(iframe_htmls)
