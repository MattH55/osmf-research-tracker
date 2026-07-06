"""Browser manager — Playwright when available, aiohttp fallback."""
from __future__ import annotations

import logging

import aiohttp

from ...config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ..natural_products.web_fetch import fetch_html as aio_fetch
from .rate_limiter import semaphore_for, throttle

log = logging.getLogger(__name__)

_PLAYWRIGHT_OK: bool | None = None


def _playwright_available() -> bool:
    global _PLAYWRIGHT_OK
    if _PLAYWRIGHT_OK is not None:
        return _PLAYWRIGHT_OK
    try:
        import playwright  # noqa: F401
        _PLAYWRIGHT_OK = True
    except ImportError:
        _PLAYWRIGHT_OK = False
    return _PLAYWRIGHT_OK


class BrowserManager:
    """Fetch rendered HTML for GMI / Examine; falls back to aiohttp."""

    def __init__(self, *, use_playwright: bool = True, use_cache: bool = True):
        self.use_playwright = use_playwright and _playwright_available()
        self.use_cache = use_cache
        self._pw = None
        self._browser = None

    async def __aenter__(self) -> BrowserManager:
        if self.use_playwright:
            try:
                from playwright.async_api import async_playwright
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=True)
            except Exception as e:
                log.warning("[Browser] Playwright unavailable: %s — using aiohttp", e)
                self.use_playwright = False
        return self

    async def __aexit__(self, *_) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    def _host(self, url: str) -> str:
        if "greenmedinfo" in url:
            return "greenmedinfo"
        if "examine.com" in url:
            return "examine"
        return "default"

    async def fetch_html(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        namespace: str,
        cache_key: str,
    ) -> str | None:
        if self.use_playwright and self._browser:
            host = self._host(url)
            sem = semaphore_for(host, default=1)
            try:
                async with sem:
                    await throttle(host)
                    page = await self._browser.new_page(
                        user_agent=BROWSER_USER_AGENT,
                    )
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=int(HTTP_TIMEOUT * 1000))
                        html = await page.content()
                    finally:
                        await page.close()
                if html and self.use_cache:
                    from .cache import cache_set
                    cache_set(namespace, cache_key, html)
                return html
            except Exception as e:
                log.warning("[Browser] Playwright fetch failed %s: %s", url, e)

        return await aio_fetch(
            session,
            url,
            namespace=namespace,
            cache_key=cache_key,
            use_cache=self.use_cache,
            ttl_days=30,
        )