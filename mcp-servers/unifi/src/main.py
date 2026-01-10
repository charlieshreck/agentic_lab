#!/usr/bin/env python3
"""UniFi MCP server for network infrastructure management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UNIFI_HOST = os.environ.get("UNIFI_HOST", "https://10.10.0.154:11443")
UNIFI_USER = os.environ.get("UNIFI_USER", "")
UNIFI_PASSWORD = os.environ.get("UNIFI_PASSWORD", "")
UNIFI_SITE = os.environ.get("UNIFI_SITE", "default")

mcp = FastMCP(
    name="unifi-mcp",
    instructions="""
    MCP server for UniFi network management.
    Provides tools to monitor clients, devices, and network health.
    """
)


class UniFiSession:
    def __init__(self):
        self.cookies = None

    async def login(self, client: httpx.AsyncClient) -> bool:
        try:
            response = await client.post(
                f"{UNIFI_HOST}/api/auth/login",
                json={"username": UNIFI_USER, "password": UNIFI_PASSWORD}
            )
            response.raise_for_status()
            self.cookies = response.cookies
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

session = UniFiSession()


async def unifi_api(endpoint: str) -> Any:
    """Make authenticated API call to UniFi."""
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        if not session.cookies:
            await session.login(client)
        response = await client.get(
            f"{UNIFI_HOST}/proxy/network/api/s/{UNIFI_SITE}{endpoint}",
            cookies=session.cookies
        )
        response.raise_for_status()
        return response.json().get("data", [])


@mcp.tool()
async def list_clients() -> List[Dict[str, Any]]:
    """List all connected clients."""
    try:
        return await unifi_api("/stat/sta")
    except Exception as e:
        logger.error(f"Failed to list clients: {e}")
        return []


@mcp.tool()
async def list_devices() -> List[Dict[str, Any]]:
    """List all UniFi devices (APs, switches, gateways)."""
    try:
        return await unifi_api("/stat/device")
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        return []


@mcp.tool()
async def get_health() -> Dict[str, Any]:
    """Get network health status."""
    try:
        return await unifi_api("/stat/health")
    except Exception as e:
        logger.error(f"Failed to get health: {e}")
        return {}


@mcp.tool()
async def get_alarms() -> List[Dict[str, Any]]:
    """Get active alarms."""
    try:
        return await unifi_api("/stat/alarm")
    except Exception as e:
        logger.error(f"Failed to get alarms: {e}")
        return []


# REST API endpoints for direct HTTP access (used by LangGraph)
async def api_devices(request):
    """REST endpoint for listing devices."""
    try:
        data = await list_devices()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_devices error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_clients(request):
    """REST endpoint for listing clients."""
    try:
        data = await list_clients()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_clients error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_health(request):
    """REST endpoint for network health."""
    try:
        data = await get_health()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_health error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_alarms(request):
    """REST endpoint for alarms."""
    try:
        data = await get_alarms()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_alarms error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_index(request):
    """REST endpoint listing available APIs."""
    return JSONResponse({
        "status": "ok",
        "endpoints": [
            "/api/devices - List all UniFi devices",
            "/api/clients - List connected clients",
            "/api/health - Network health status",
            "/api/alarms - Active alarms",
        ]
    })


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))

    # REST routes for direct HTTP access
    rest_routes = [
        Route("/api", api_index),
        Route("/api/devices", api_devices),
        Route("/api/clients", api_clients),
        Route("/api/health", api_health),
        Route("/api/alarms", api_alarms),
    ]

    # Combine REST routes with MCP app
    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
