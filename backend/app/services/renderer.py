"""Module 4: turn generated HTML into a PNG screenshot.

The refine loop (module 5) compares this PNG with the original screenshot,
so the render must use the SAME width and height as the original.
"""
import asyncio
import logging
import sys
from urllib.parse import urlparse

# playwright: controls a real Chromium browser from Python. We use the *sync*
# API inside a worker thread (see render_html) instead of the async API.
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

log = logging.getLogger(__name__)

# Windows + `uvicorn --reload` switches asyncio to a loop type that cannot start
# subprocesses, and Playwright starts its browser driver as a subprocess.
# Asking for the Proactor loop policy makes the loops Playwright creates later
# (in our worker thread) work again. This does nothing on Linux/macOS.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

MAX_DIM = 4000          # px, largest width/height we will render
TIMEOUT_MS = 15_000     # hard limit so one broken page cannot hang the server
MAX_CONCURRENT = 2      # Chromium is heavy; render at most 2 pages at once

# The HTML is written by a model, so treat it as untrusted. It may only load
# from these hosts (Tailwind, fonts, placeholder images). Anything else,
# like file:// paths or http://localhost:8000, is blocked.
ALLOWED_HOSTS = {
    "cdn.tailwindcss.com",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "placehold.co",
    "unpkg.com",  # React, MUI and Babel for the React screenshot page
}

_slots = asyncio.Semaphore(MAX_CONCURRENT)


class RenderError(Exception):
    """Raised with a message that is safe to show to the user."""


def _is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in ("data", "about", "blob"):
        return True  # inline content, nothing is fetched from outside
    if parsed.scheme in ("http", "https"):
        return (parsed.hostname or "") in ALLOWED_HOSTS
    return False  # file:, ftp:, chrome:, ...


def _render_sync(
    html: str,
    width: int,
    height: int,
    wait_for: str | None = None,
    timeout_ms: int | None = None,
) -> bytes:
    timeout = TIMEOUT_MS if timeout_ms is None else timeout_ms
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            # A fresh context per render: no cookies or storage shared between renders.
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.set_default_timeout(timeout)

            def guard(route):
                if _is_allowed(route.request.url):
                    route.continue_()
                else:
                    log.warning("Blocked request from generated page: %s", route.request.url)
                    route.abort()

            page.route("**/*", guard)

            # networkidle: wait until Tailwind's script (and any fonts) finished loading.
            # A React page also waits for window.__ready, because Babel runs after the scripts.
            page.set_content(html, wait_until="networkidle", timeout=timeout)
            if wait_for:
                page.wait_for_function(wait_for, timeout=timeout)
            page.evaluate("document.fonts.ready")  # web fonts applied before the shot

            # full_page=False keeps the PNG exactly width x height, the same
            # frame as the original screenshot, which is what the comparison needs.
            return page.screenshot(full_page=False)
        finally:
            browser.close()


async def render_html(
    html: str,
    width: int,
    height: int,
    wait_for: str | None = None,
    timeout_ms: int | None = None,
) -> bytes:
    """Render `html` in a width x height viewport and return PNG bytes."""
    if not (1 <= width <= MAX_DIM and 1 <= height <= MAX_DIM):
        raise ValueError(f"width and height must be between 1 and {MAX_DIM}")
    async with _slots:
        try:
            # to_thread: the sync Playwright call blocks, so run it off the event
            # loop. Otherwise streaming for every other request would freeze.
            return await asyncio.to_thread(_render_sync, html, width, height, wait_for, timeout_ms)
        except PlaywrightTimeout as exc:
            raise RenderError("The page took too long to render") from exc
        except PlaywrightError as exc:
            log.exception("Playwright failed")
            raise RenderError("The page could not be rendered") from exc