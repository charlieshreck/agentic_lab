#!/usr/bin/env python3
"""Browser Automation MCP server using Playwright."""
import os
import base64
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Browser configuration
BROWSER_TYPE = os.environ.get("BROWSER_TYPE", "chromium")  # chromium, firefox, webkit
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
DEFAULT_TIMEOUT = int(os.environ.get("DEFAULT_TIMEOUT", "30000"))
VIEWPORT_WIDTH = int(os.environ.get("VIEWPORT_WIDTH", "1920"))
VIEWPORT_HEIGHT = int(os.environ.get("VIEWPORT_HEIGHT", "1080"))

mcp = FastMCP(
    name="browser-automation-mcp",
    instructions="""MCP server for browser automation using Playwright.
    Provides tools for navigating web pages, taking screenshots, clicking elements,
    typing text, and extracting page content. Use for web automation tasks."""
)


class NavigateResult(BaseModel):
    """Result of navigation."""
    url: str
    title: str
    status: int
    load_time_ms: int


class Screenshot(BaseModel):
    """Screenshot data."""
    data: str  # base64 encoded PNG
    width: int
    height: int
    timestamp: str


class ActionResult(BaseModel):
    """Result of a browser action."""
    success: bool
    message: str
    timestamp: str


class PageContent(BaseModel):
    """Page content."""
    url: str
    title: str
    html: Optional[str] = None
    text: Optional[str] = None
    word_count: int


class ElementInfo(BaseModel):
    """Information about an element."""
    selector: str
    tag_name: str
    text: str
    visible: bool
    bounding_box: Optional[Dict[str, float]] = None


# ============================================================================
# BROWSER MANAGEMENT
# ============================================================================

class BrowserManager:
    """Manages a persistent browser instance."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._lock = asyncio.Lock()

    async def ensure_browser(self):
        """Ensure browser is running."""
        async with self._lock:
            if self.page is None or self.page.is_closed():
                await self._start_browser()
            return self.page

    async def _start_browser(self):
        """Start the browser."""
        from playwright.async_api import async_playwright

        if self.playwright is None:
            self.playwright = await async_playwright().start()

        browser_launcher = getattr(self.playwright, BROWSER_TYPE)
        self.browser = await browser_launcher.launch(headless=HEADLESS)

        self.context = await self.browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)
        logger.info(f"Browser started: {BROWSER_TYPE}, headless={HEADLESS}")

    async def close(self):
        """Close browser."""
        async with self._lock:
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None


# Global browser manager
browser_manager = BrowserManager()


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
async def navigate(url: str, wait_until: str = "networkidle") -> NavigateResult:
    """
    Navigate the browser to a URL.

    Args:
        url: The URL to navigate to
        wait_until: When to consider navigation complete - "load", "domcontentloaded", "networkidle"

    Returns:
        Navigation result with URL, title, status code, and load time
    """
    page = await browser_manager.ensure_browser()
    start_time = datetime.utcnow()

    try:
        response = await page.goto(url, wait_until=wait_until)
        load_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return NavigateResult(
            url=page.url,
            title=await page.title(),
            status=response.status if response else 0,
            load_time_ms=load_time
        )
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return NavigateResult(
            url=url,
            title="",
            status=0,
            load_time_ms=0
        )


@mcp.tool()
async def screenshot(full_page: bool = False) -> Screenshot:
    """
    Take a screenshot of the current page.

    Args:
        full_page: If True, capture the entire scrollable page. If False, capture viewport only.

    Returns:
        Screenshot with base64-encoded PNG data
    """
    page = await browser_manager.ensure_browser()

    try:
        screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
        data = base64.b64encode(screenshot_bytes).decode("utf-8")

        viewport = page.viewport_size
        return Screenshot(
            data=data,
            width=viewport["width"] if viewport else VIEWPORT_WIDTH,
            height=viewport["height"] if viewport else VIEWPORT_HEIGHT,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return Screenshot(
            data="",
            width=0,
            height=0,
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def click(selector: str) -> ActionResult:
    """
    Click on an element by CSS selector.

    Args:
        selector: CSS selector for the element to click

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        await page.click(selector)
        return ActionResult(
            success=True,
            message=f"Clicked element: {selector}",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return ActionResult(
            success=False,
            message=f"Click failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def click_coordinates(x: int, y: int) -> ActionResult:
    """
    Click at specific screen coordinates.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        await page.mouse.click(x, y)
        return ActionResult(
            success=True,
            message=f"Clicked at ({x}, {y})",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Click coordinates failed: {e}")
        return ActionResult(
            success=False,
            message=f"Click failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def type_text(selector: str, text: str, clear_first: bool = True) -> ActionResult:
    """
    Type text into an input element.

    Args:
        selector: CSS selector for the input element
        text: Text to type
        clear_first: If True, clear the input before typing

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        if clear_first:
            await page.fill(selector, text)
        else:
            await page.type(selector, text)

        return ActionResult(
            success=True,
            message=f"Typed text into: {selector}",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Type text failed: {e}")
        return ActionResult(
            success=False,
            message=f"Type failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def press_key(key: str) -> ActionResult:
    """
    Press a keyboard key.

    Args:
        key: Key to press - "Enter", "Tab", "Escape", "Backspace", "ArrowDown", etc.
             For combinations use "+" like "Control+a", "Shift+Tab"

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        await page.keyboard.press(key)
        return ActionResult(
            success=True,
            message=f"Pressed key: {key}",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Press key failed: {e}")
        return ActionResult(
            success=False,
            message=f"Key press failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def scroll(direction: str = "down", amount: int = 500) -> ActionResult:
    """
    Scroll the page.

    Args:
        direction: "up", "down", "left", "right"
        amount: Pixels to scroll (default: 500)

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = amount
        elif direction == "up":
            delta_y = -amount
        elif direction == "right":
            delta_x = amount
        elif direction == "left":
            delta_x = -amount

        await page.mouse.wheel(delta_x, delta_y)

        return ActionResult(
            success=True,
            message=f"Scrolled {direction} by {amount}px",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Scroll failed: {e}")
        return ActionResult(
            success=False,
            message=f"Scroll failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def get_page_content(include_html: bool = False) -> PageContent:
    """
    Get the current page content.

    Args:
        include_html: If True, include raw HTML in response

    Returns:
        Page content with URL, title, text, and optionally HTML
    """
    page = await browser_manager.ensure_browser()

    try:
        text = await page.inner_text("body")
        html = await page.content() if include_html else None

        return PageContent(
            url=page.url,
            title=await page.title(),
            html=html,
            text=text,
            word_count=len(text.split())
        )
    except Exception as e:
        logger.error(f"Get page content failed: {e}")
        return PageContent(
            url=page.url if page else "",
            title="",
            text=f"Error: {str(e)}",
            word_count=0
        )


@mcp.tool()
async def evaluate_js(script: str) -> dict:
    """
    Execute JavaScript on the page.

    Args:
        script: JavaScript code to execute

    Returns:
        Result of the JavaScript execution
    """
    page = await browser_manager.ensure_browser()

    try:
        result = await page.evaluate(script)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Evaluate JS failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def wait_for_selector(selector: str, timeout: int = 30000, state: str = "visible") -> ActionResult:
    """
    Wait for an element to appear.

    Args:
        selector: CSS selector for the element
        timeout: Maximum wait time in milliseconds (default: 30000)
        state: Expected state - "attached", "detached", "visible", "hidden"

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
        return ActionResult(
            success=True,
            message=f"Element found: {selector}",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Wait for selector failed: {e}")
        return ActionResult(
            success=False,
            message=f"Wait failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def fill_form(fields: Dict[str, str]) -> ActionResult:
    """
    Fill multiple form fields at once.

    Args:
        fields: Dictionary of selector -> value pairs

    Returns:
        Action result with success status
    """
    page = await browser_manager.ensure_browser()

    try:
        filled = []
        for selector, value in fields.items():
            await page.fill(selector, value)
            filled.append(selector)

        return ActionResult(
            success=True,
            message=f"Filled {len(filled)} fields",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Fill form failed: {e}")
        return ActionResult(
            success=False,
            message=f"Fill form failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def get_element_text(selector: str) -> str:
    """
    Get text content of an element.

    Args:
        selector: CSS selector for the element

    Returns:
        Text content of the element
    """
    page = await browser_manager.ensure_browser()

    try:
        return await page.inner_text(selector)
    except Exception as e:
        logger.error(f"Get element text failed: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def get_element_attribute(selector: str, attribute: str) -> Optional[str]:
    """
    Get an attribute value of an element.

    Args:
        selector: CSS selector for the element
        attribute: Attribute name (e.g., "href", "src", "class")

    Returns:
        Attribute value or None if not found
    """
    page = await browser_manager.ensure_browser()

    try:
        return await page.get_attribute(selector, attribute)
    except Exception as e:
        logger.error(f"Get attribute failed: {e}")
        return None


@mcp.tool()
async def get_all_links() -> List[Dict[str, str]]:
    """
    Get all links on the current page.

    Returns:
        List of links with href and text
    """
    page = await browser_manager.ensure_browser()

    try:
        links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                href: a.href,
                text: a.innerText.trim().substring(0, 100)
            }))
        """)
        return links
    except Exception as e:
        logger.error(f"Get all links failed: {e}")
        return []


@mcp.tool()
async def go_back() -> ActionResult:
    """Navigate back in browser history."""
    page = await browser_manager.ensure_browser()

    try:
        await page.go_back()
        return ActionResult(
            success=True,
            message="Navigated back",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Go back failed: {e}")
        return ActionResult(
            success=False,
            message=f"Go back failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def go_forward() -> ActionResult:
    """Navigate forward in browser history."""
    page = await browser_manager.ensure_browser()

    try:
        await page.go_forward()
        return ActionResult(
            success=True,
            message="Navigated forward",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Go forward failed: {e}")
        return ActionResult(
            success=False,
            message=f"Go forward failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


@mcp.tool()
async def reload_page() -> ActionResult:
    """Reload the current page."""
    page = await browser_manager.ensure_browser()

    try:
        await page.reload()
        return ActionResult(
            success=True,
            message="Page reloaded",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        return ActionResult(
            success=False,
            message=f"Reload failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat()
        )


# ============================================================================
# REST API
# ============================================================================

async def rest_health(request: Request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})


async def rest_api_screenshot(request: Request):
    """Get current screenshot."""
    try:
        page = await browser_manager.ensure_browser()
        screenshot_bytes = await page.screenshot(type="png")
        return Response(content=screenshot_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"REST screenshot error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def rest_api_page_info(request: Request):
    """Get current page info."""
    try:
        page = await browser_manager.ensure_browser()
        return JSONResponse({
            "status": "ok",
            "url": page.url,
            "title": await page.title(),
            "viewport": page.viewport_size
        })
    except Exception as e:
        logger.error(f"REST page info error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# ============================================================================
# MAIN
# ============================================================================

@asynccontextmanager
async def lifespan(app):
    """Manage browser lifecycle."""
    yield
    await browser_manager.close()


def main():
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting Browser Automation MCP on port {port}")

    rest_routes = [
        Route("/health", rest_health, methods=["GET"]),
        Route("/api/screenshot", rest_api_screenshot, methods=["GET"]),
        Route("/api/page", rest_api_page_info, methods=["GET"]),
    ]

    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)], lifespan=lifespan)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
