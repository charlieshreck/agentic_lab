#!/usr/bin/env python3
"""Cloudflare MCP server for DNS and tunnel management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CF_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID", "")

mcp = FastMCP(
    name="cloudflare-mcp",
    instructions="""
    MCP server for Cloudflare management.
    Provides tools to manage DNS records, tunnels, and access policies.
    """
)


async def cf_api(endpoint: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
    """Make authenticated API call to Cloudflare."""
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    url = f"https://api.cloudflare.com/client/v4{endpoint}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, headers=headers)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = await client.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            response = await client.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_dns_records(zone_id: str = None) -> List[Dict[str, Any]]:
    """List DNS records for a zone."""
    try:
        zone = zone_id or CF_ZONE_ID
        result = await cf_api(f"/zones/{zone}/dns_records")
        return result.get("result", [])
    except Exception as e:
        logger.error(f"Failed to list DNS records: {e}")
        return []


@mcp.tool()
async def list_tunnels() -> List[Dict[str, Any]]:
    """List Cloudflare tunnels."""
    try:
        result = await cf_api(f"/accounts/{CF_ACCOUNT_ID}/cfd_tunnel")
        return result.get("result", [])
    except Exception as e:
        logger.error(f"Failed to list tunnels: {e}")
        return []


@mcp.tool()
async def get_tunnel_status(tunnel_id: str) -> Dict[str, Any]:
    """Get detailed tunnel status."""
    try:
        result = await cf_api(f"/accounts/{CF_ACCOUNT_ID}/cfd_tunnel/{tunnel_id}")
        return result.get("result", {})
    except Exception as e:
        logger.error(f"Failed to get tunnel status: {e}")
        return {}


@mcp.tool()
async def create_dns_record(
    name: str,
    record_type: str,
    content: str,
    proxied: bool = True,
    zone_id: str = None
) -> Dict[str, Any]:
    """Create a new DNS record."""
    try:
        zone = zone_id or CF_ZONE_ID
        data = {
            "name": name,
            "type": record_type,
            "content": content,
            "proxied": proxied
        }
        result = await cf_api(f"/zones/{zone}/dns_records", "POST", data)
        return result.get("result", {})
    except Exception as e:
        logger.error(f"Failed to create DNS record: {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_zone_analytics(zone_id: str = None) -> Dict[str, Any]:
    """Get zone analytics/traffic data."""
    try:
        zone = zone_id or CF_ZONE_ID
        result = await cf_api(f"/zones/{zone}/analytics/dashboard")
        return result.get("result", {})
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return {}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting Cloudflare MCP server on port {port}")
    uvicorn.run(mcp.get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
