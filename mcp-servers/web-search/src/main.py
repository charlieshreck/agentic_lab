#!/usr/bin/env python3
"""Web Search MCP server using self-hosted SearXNG."""
import os
import re
import logging
from typing import List, Optional
from datetime import datetime
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng.ai-platform.svc.cluster.local:8080")

mcp = FastMCP(
    name="web-search-mcp",
    instructions="""MCP server for web search using self-hosted SearXNG.
    Provides tools for searching the web, fetching page content, and searching news/images.
    Use web_search for general queries, get_page_content to fetch full page text."""
)


class SearchResult(BaseModel):
    """A single search result."""
    title: str
    url: str
    snippet: str
    engine: Optional[str] = None
    published_date: Optional[str] = None


class PageContent(BaseModel):
    """Fetched page content."""
    url: str
    title: str
    content: str
    content_type: str
    word_count: int
    fetched_at: str


class NewsResult(BaseModel):
    """A news search result."""
    title: str
    url: str
    snippet: str
    source: Optional[str] = None
    published_date: Optional[str] = None


class ImageResult(BaseModel):
    """An image search result."""
    title: str
    url: str
    thumbnail_url: Optional[str] = None
    source: Optional[str] = None


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

async def _searxng_search(
    query: str,
    categories: str = "general",
    engines: Optional[str] = None,
    num_results: int = 10,
    time_range: Optional[str] = None
) -> List[dict]:
    """Execute search against SearXNG."""
    params = {
        "q": query,
        "format": "json",
        "categories": categories,
    }
    if engines:
        params["engines"] = engines
    if time_range:
        params["time_range"] = time_range

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])[:num_results]
            return results
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            return []


async def _fetch_page_content(url: str, max_length: int = 50000) -> dict:
    """Fetch and extract text content from a URL."""
    try:
        # Import here to avoid startup issues if not installed
        from bs4 import BeautifulSoup
        import html2text

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AgenticBot/1.0; +http://localhost)"
            }
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove scripts, styles, nav, footer
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                # Get title
                title = soup.title.string if soup.title else ""

                # Convert to markdown
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = True
                h.body_width = 0
                content = h.handle(str(soup))

                # Truncate if needed
                if len(content) > max_length:
                    content = content[:max_length] + "\n\n[Content truncated...]"

                return {
                    "title": title.strip() if title else "",
                    "content": content.strip(),
                    "content_type": "markdown",
                    "word_count": len(content.split())
                }
            else:
                # Plain text or other
                text = response.text[:max_length]
                return {
                    "title": "",
                    "content": text,
                    "content_type": "text",
                    "word_count": len(text.split())
                }
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {
            "title": "",
            "content": f"Error fetching page: {str(e)}",
            "content_type": "error",
            "word_count": 0
        }


def _is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch (no internal IPs)."""
    # Block internal/private IPs
    internal_patterns = [
        r"^https?://10\.",
        r"^https?://192\.168\.",
        r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.",
        r"^https?://127\.",
        r"^https?://localhost",
        r"\.svc\.cluster\.local",
        r"\.internal",
    ]
    for pattern in internal_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    return url.startswith("http://") or url.startswith("https://")


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
async def web_search(
    query: str,
    num_results: int = 10,
    engines: Optional[str] = None,
    time_range: Optional[str] = None
) -> List[SearchResult]:
    """
    Search the web using SearXNG (aggregates Google, Bing, DuckDuckGo, etc.).

    Args:
        query: Search query string
        num_results: Maximum number of results (default: 10, max: 50)
        engines: Comma-separated engine names (e.g., "google,bing"). Leave empty for auto.
        time_range: Filter by time - "day", "week", "month", "year", or None for all time

    Returns:
        List of search results with title, URL, and snippet
    """
    num_results = min(num_results, 50)
    results = await _searxng_search(query, "general", engines, num_results, time_range)

    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            engine=r.get("engine", None),
            published_date=r.get("publishedDate", None)
        )
        for r in results
    ]


@mcp.tool()
async def get_page_content(
    url: str,
    max_length: int = 50000
) -> PageContent:
    """
    Fetch and extract text content from a web page.

    Args:
        url: The URL to fetch (must be http/https, no internal IPs)
        max_length: Maximum content length in characters (default: 50000)

    Returns:
        Page content converted to markdown with title and word count
    """
    if not _is_safe_url(url):
        return PageContent(
            url=url,
            title="",
            content="Error: URL blocked - internal/private addresses not allowed",
            content_type="error",
            word_count=0,
            fetched_at=datetime.utcnow().isoformat()
        )

    result = await _fetch_page_content(url, max_length)

    return PageContent(
        url=url,
        title=result["title"],
        content=result["content"],
        content_type=result["content_type"],
        word_count=result["word_count"],
        fetched_at=datetime.utcnow().isoformat()
    )


@mcp.tool()
async def search_news(
    query: str,
    num_results: int = 10,
    time_range: str = "week"
) -> List[NewsResult]:
    """
    Search for recent news articles.

    Args:
        query: Search query string
        num_results: Maximum number of results (default: 10)
        time_range: Filter by time - "day", "week", "month" (default: week)

    Returns:
        List of news results with title, URL, snippet, and publication date
    """
    num_results = min(num_results, 50)
    results = await _searxng_search(query, "news", None, num_results, time_range)

    return [
        NewsResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", ""),
            source=r.get("engine", None),
            published_date=r.get("publishedDate", None)
        )
        for r in results
    ]


@mcp.tool()
async def search_images(
    query: str,
    num_results: int = 10
) -> List[ImageResult]:
    """
    Search for images.

    Args:
        query: Search query string
        num_results: Maximum number of results (default: 10)

    Returns:
        List of image results with title, URL, and thumbnail URL
    """
    num_results = min(num_results, 50)
    results = await _searxng_search(query, "images", None, num_results, None)

    return [
        ImageResult(
            title=r.get("title", ""),
            url=r.get("img_src", r.get("url", "")),
            thumbnail_url=r.get("thumbnail_src", None),
            source=r.get("engine", None)
        )
        for r in results
    ]


@mcp.tool()
async def search_and_fetch(
    query: str,
    num_results: int = 3
) -> dict:
    """
    Search and automatically fetch content from top results.

    Args:
        query: Search query string
        num_results: Number of top results to fetch (default: 3, max: 5)

    Returns:
        Search results with full page content for each
    """
    num_results = min(num_results, 5)
    search_results = await _searxng_search(query, "general", None, num_results, None)

    fetched = []
    for r in search_results:
        url = r.get("url", "")
        if url and _is_safe_url(url):
            content = await _fetch_page_content(url, 20000)
            fetched.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("content", ""),
                "full_content": content["content"],
                "word_count": content["word_count"]
            })

    return {
        "query": query,
        "results_fetched": len(fetched),
        "results": fetched
    }


# ============================================================================
# REST API (for langgraph context building)
# ============================================================================

async def rest_health(request: Request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})


async def rest_api_search(request: Request):
    """Search endpoint for langgraph context."""
    try:
        query = request.query_params.get("q", "")
        if not query:
            return JSONResponse({"status": "error", "error": "Missing query parameter 'q'"}, status_code=400)

        num_results = int(request.query_params.get("limit", "10"))
        engines = request.query_params.get("engines")
        time_range = request.query_params.get("time_range")

        results = await _searxng_search(query, "general", engines, num_results, time_range)
        return JSONResponse({
            "status": "ok",
            "query": query,
            "count": len(results),
            "results": results
        })
    except Exception as e:
        logger.error(f"REST search error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def rest_api_fetch(request: Request):
    """Fetch page content endpoint."""
    try:
        url = request.query_params.get("url", "")
        if not url:
            return JSONResponse({"status": "error", "error": "Missing query parameter 'url'"}, status_code=400)

        if not _is_safe_url(url):
            return JSONResponse({"status": "error", "error": "URL blocked"}, status_code=403)

        content = await _fetch_page_content(url)
        return JSONResponse({
            "status": "ok",
            "url": url,
            "data": content
        })
    except Exception as e:
        logger.error(f"REST fetch error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# ============================================================================
# MAIN
# ============================================================================

def main():
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting Web Search MCP on port {port}")

    rest_routes = [
        Route("/health", rest_health, methods=["GET"]),
        Route("/api/search", rest_api_search, methods=["GET"]),
        Route("/api/fetch", rest_api_fetch, methods=["GET"]),
    ]

    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
