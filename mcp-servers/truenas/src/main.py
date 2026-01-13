#!/usr/bin/env python3
"""TrueNAS MCP server for storage management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRUENAS_HOST = os.environ.get("TRUENAS_HOST", "https://10.10.0.100")
TRUENAS_API_KEY = os.environ.get("TRUENAS_API_KEY", "")

mcp = FastMCP(
    name="truenas-mcp",
    instructions="""
    MCP server for TrueNAS storage management.
    Provides tools to monitor pools, datasets, shares, and snapshots.
    """
)


async def truenas_api(endpoint: str, method: str = "GET", data: dict = None) -> Any:
    """Make authenticated API call to TrueNAS."""
    headers = {"Authorization": f"Bearer {TRUENAS_API_KEY}"}
    url = f"{TRUENAS_HOST}/api/v2.0{endpoint}"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, headers=headers)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        else:
            response = await client.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_pools() -> List[Dict[str, Any]]:
    """List ZFS pools with health status."""
    try:
        return await truenas_api("/pool")
    except Exception as e:
        logger.error(f"Failed to list pools: {e}")
        return []


@mcp.tool()
async def get_pool_status(pool_id: int) -> Dict[str, Any]:
    """Get detailed pool status including disk health."""
    try:
        return await truenas_api(f"/pool/id/{pool_id}")
    except Exception as e:
        logger.error(f"Failed to get pool status: {e}")
        return {}


@mcp.tool()
async def list_datasets(pool_name: str = None) -> List[Dict[str, Any]]:
    """List datasets. Optionally filter by pool."""
    try:
        datasets = await truenas_api("/pool/dataset")
        if pool_name:
            return [d for d in datasets if d.get("pool") == pool_name]
        return datasets
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        return []


@mcp.tool()
async def list_shares() -> Dict[str, List[Dict[str, Any]]]:
    """List all shares (NFS, SMB)."""
    try:
        nfs = await truenas_api("/sharing/nfs")
        smb = await truenas_api("/sharing/smb")
        return {"nfs": nfs, "smb": smb}
    except Exception as e:
        logger.error(f"Failed to list shares: {e}")
        return {"nfs": [], "smb": []}


@mcp.tool()
async def list_snapshots(dataset: str = None) -> List[Dict[str, Any]]:
    """List snapshots. Optionally filter by dataset."""
    try:
        snapshots = await truenas_api("/zfs/snapshot")
        if dataset:
            return [s for s in snapshots if dataset in s.get("name", "")]
        return snapshots
    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        return []


@mcp.tool()
async def get_disk_status() -> List[Dict[str, Any]]:
    """Get status of all disks."""
    try:
        return await truenas_api("/disk")
    except Exception as e:
        logger.error(f"Failed to get disk status: {e}")
        return []


@mcp.tool()
async def get_alerts() -> List[Dict[str, Any]]:
    """Get active alerts."""
    try:
        return await truenas_api("/alert/list")
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return []


# =============================================================================
# REST API Endpoints (for CronJobs - bypass MCP session protocol)
# =============================================================================

app = mcp.get_app()


@app.get("/api/pools")
async def rest_list_pools():
    """REST endpoint for ZFS pools - used by graph-sync CronJob."""
    try:
        pools = await list_pools()
        return {"pools": pools}
    except Exception as e:
        logger.error(f"REST list_pools error: {e}")
        return {"error": str(e), "pools": []}


@app.get("/api/datasets")
async def rest_list_datasets():
    """REST endpoint for datasets - used by graph-sync CronJob."""
    try:
        datasets = await list_datasets()
        return {"datasets": datasets}
    except Exception as e:
        logger.error(f"REST list_datasets error: {e}")
        return {"error": str(e), "datasets": []}


@app.get("/api/shares")
async def rest_list_shares():
    """REST endpoint for shares - used by graph-sync CronJob."""
    try:
        return await list_shares()
    except Exception as e:
        logger.error(f"REST list_shares error: {e}")
        return {"error": str(e), "nfs": [], "smb": []}


@app.get("/api/disks")
async def rest_disk_status():
    """REST endpoint for disk status."""
    try:
        disks = await get_disk_status()
        return {"disks": disks}
    except Exception as e:
        logger.error(f"REST disk_status error: {e}")
        return {"error": str(e), "disks": []}


@app.get("/api/alerts")
async def rest_alerts():
    """REST endpoint for alerts."""
    try:
        alerts = await get_alerts()
        return {"alerts": alerts}
    except Exception as e:
        logger.error(f"REST alerts error: {e}")
        return {"error": str(e), "alerts": []}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting TrueNAS MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
