#!/usr/bin/env python3
"""OPNsense MCP server for firewall and router management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPNSENSE_HOST = os.environ.get("OPNSENSE_HOST", "https://10.10.0.1")
OPNSENSE_KEY = os.environ.get("OPNSENSE_KEY", "")
OPNSENSE_SECRET = os.environ.get("OPNSENSE_SECRET", "")

mcp = FastMCP(
    name="opnsense-mcp",
    instructions="""
    MCP server for OPNsense firewall management.
    Provides tools to view firewall rules, interfaces, DHCP leases, and VPN status.
    Modifications require careful consideration - incorrect rules can lock you out.
    """
)


async def opnsense_api(endpoint: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
    """Make authenticated API call to OPNsense."""
    auth = (OPNSENSE_KEY, OPNSENSE_SECRET)
    url = f"{OPNSENSE_HOST}/api{endpoint}"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, auth=auth)
        else:
            response = await client.post(url, auth=auth, json=data)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_interfaces() -> List[Dict[str, Any]]:
    """List all network interfaces with status."""
    try:
        return await opnsense_api("/diagnostics/interface/getInterfaceStatistics")
    except Exception as e:
        logger.error(f"Failed to get interfaces: {e}")
        return []


@mcp.tool()
async def get_firewall_rules() -> List[Dict[str, Any]]:
    """List firewall rules."""
    try:
        return await opnsense_api("/firewall/filter/searchRule")
    except Exception as e:
        logger.error(f"Failed to get firewall rules: {e}")
        return []


@mcp.tool()
async def get_dhcp_leases() -> List[Dict[str, Any]]:
    """List active DHCP leases."""
    try:
        return await opnsense_api("/dhcpv4/leases/searchLease")
    except Exception as e:
        logger.error(f"Failed to get DHCP leases: {e}")
        return []


@mcp.tool()
async def get_gateway_status() -> Dict[str, Any]:
    """Get gateway status and latency."""
    try:
        return await opnsense_api("/routes/gateway/status")
    except Exception as e:
        logger.error(f"Failed to get gateway status: {e}")
        return {}


@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """Get overall system status."""
    try:
        return await opnsense_api("/core/system/status")
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting OPNsense MCP server on port {port}")
    uvicorn.run(mcp.get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
