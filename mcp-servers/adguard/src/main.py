#!/usr/bin/env python3
"""AdGuard Home MCP server for DNS and ad-blocking management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADGUARD_HOST = os.environ.get("ADGUARD_HOST", "http://10.10.0.1:3000")
ADGUARD_USER = os.environ.get("ADGUARD_USER", "admin")
ADGUARD_PASSWORD = os.environ.get("ADGUARD_PASSWORD", "")

mcp = FastMCP(
    name="adguard-mcp",
    instructions="""
    MCP server for AdGuard Home DNS management.
    Provides tools to view DNS stats, blocked queries, and manage filtering.
    """
)


async def adguard_api(endpoint: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
    """Make authenticated API call to AdGuard Home."""
    auth = (ADGUARD_USER, ADGUARD_PASSWORD)
    url = f"{ADGUARD_HOST}/{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, auth=auth)
        else:
            response = await client.post(url, auth=auth, json=data)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_stats() -> Dict[str, Any]:
    """Get DNS query statistics."""
    try:
        return await adguard_api("control/stats")
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}


@mcp.tool()
async def get_query_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent DNS query log."""
    try:
        result = await adguard_api(f"control/querylog?limit={limit}")
        return result.get("data", [])
    except Exception as e:
        logger.error(f"Failed to get query log: {e}")
        return []


@mcp.tool()
async def get_filtering_status() -> Dict[str, Any]:
    """Get current filtering status and blocklists."""
    try:
        return await adguard_api("control/filtering/status")
    except Exception as e:
        logger.error(f"Failed to get filtering status: {e}")
        return {}


@mcp.tool()
async def get_blocked_services() -> List[str]:
    """Get list of blocked services."""
    try:
        result = await adguard_api("control/blocked_services/list")
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.error(f"Failed to get blocked services: {e}")
        return []


@mcp.tool()
async def get_clients() -> List[Dict[str, Any]]:
    """Get configured clients."""
    try:
        result = await adguard_api("control/clients")
        return result.get("clients", [])
    except Exception as e:
        logger.error(f"Failed to get clients: {e}")
        return []


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting AdGuard MCP server on port {port}")
    uvicorn.run(mcp.get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
