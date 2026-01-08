#!/usr/bin/env python3
"""Homepage MCP server for dashboard management."""
import os
import logging
from typing import Dict, Any
from fastmcp import FastMCP
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOMEPAGE_HOST = os.environ.get("HOMEPAGE_HOST", "http://homepage:3000")

mcp = FastMCP(
    name="homepage-mcp",
    instructions="""
    MCP server for Homepage dashboard management.
    Provides tools to query service status shown on the dashboard.
    """
)


@mcp.tool()
async def get_services() -> Dict[str, Any]:
    """Get status of services configured in Homepage."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{HOMEPAGE_HOST}/api/services")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get services: {e}")
        return {}


@mcp.tool()
async def get_widgets() -> Dict[str, Any]:
    """Get widget data from Homepage."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{HOMEPAGE_HOST}/api/widgets")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get widgets: {e}")
        return {}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(mcp.get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
