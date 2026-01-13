#!/usr/bin/env python3
"""Proxmox VE MCP server for hypervisor management."""
import os
import logging
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROXMOX_HOST = os.environ.get("PROXMOX_HOST", "https://10.10.0.10:8006")
PROXMOX_USER = os.environ.get("PROXMOX_USER", "root@pam")
PROXMOX_TOKEN_ID = os.environ.get("PROXMOX_TOKEN_ID", "")
PROXMOX_TOKEN_SECRET = os.environ.get("PROXMOX_TOKEN_SECRET", "")

mcp = FastMCP(
    name="proxmox-mcp",
    instructions="""
    MCP server for Proxmox VE hypervisor management.
    Provides tools to list VMs, check status, manage resources.
    Use with caution - some operations can affect running VMs.
    """
)


class VMInfo(BaseModel):
    vmid: int
    name: str
    status: str
    node: str
    cpus: int
    maxmem: int
    maxdisk: int


class NodeInfo(BaseModel):
    node: str
    status: str
    cpu: float
    maxcpu: int
    mem: int
    maxmem: int
    uptime: int


async def proxmox_api(endpoint: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
    """Make authenticated API call to Proxmox."""
    headers = {
        "Authorization": f"PVEAPIToken={PROXMOX_USER}!{PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"
    }
    url = f"{PROXMOX_HOST}/api2/json{endpoint}"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url, headers=headers)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        else:
            response = await client.request(method, url, headers=headers, json=data)

        response.raise_for_status()
        return response.json().get("data", {})


@mcp.tool()
async def list_nodes() -> List[NodeInfo]:
    """List all Proxmox cluster nodes with status and resource usage."""
    try:
        data = await proxmox_api("/nodes")
        return [NodeInfo(
            node=n["node"],
            status=n.get("status", "unknown"),
            cpu=n.get("cpu", 0),
            maxcpu=n.get("maxcpu", 0),
            mem=n.get("mem", 0),
            maxmem=n.get("maxmem", 0),
            uptime=n.get("uptime", 0)
        ) for n in data]
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}")
        return []


@mcp.tool()
async def list_vms(node: str = None) -> List[VMInfo]:
    """List all VMs. Optionally filter by node."""
    try:
        if node:
            data = await proxmox_api(f"/nodes/{node}/qemu")
            return [VMInfo(
                vmid=vm["vmid"],
                name=vm.get("name", f"VM-{vm['vmid']}"),
                status=vm.get("status", "unknown"),
                node=node,
                cpus=vm.get("cpus", 0),
                maxmem=vm.get("maxmem", 0),
                maxdisk=vm.get("maxdisk", 0)
            ) for vm in data]
        else:
            # Get VMs from all nodes
            nodes = await proxmox_api("/nodes")
            all_vms = []
            for n in nodes:
                vms = await proxmox_api(f"/nodes/{n['node']}/qemu")
                for vm in vms:
                    all_vms.append(VMInfo(
                        vmid=vm["vmid"],
                        name=vm.get("name", f"VM-{vm['vmid']}"),
                        status=vm.get("status", "unknown"),
                        node=n["node"],
                        cpus=vm.get("cpus", 0),
                        maxmem=vm.get("maxmem", 0),
                        maxdisk=vm.get("maxdisk", 0)
                    ))
            return all_vms
    except Exception as e:
        logger.error(f"Failed to list VMs: {e}")
        return []


@mcp.tool()
async def get_vm_status(node: str, vmid: int) -> Dict[str, Any]:
    """Get detailed status of a specific VM."""
    try:
        return await proxmox_api(f"/nodes/{node}/qemu/{vmid}/status/current")
    except Exception as e:
        logger.error(f"Failed to get VM status: {e}")
        return {"error": str(e)}


@mcp.tool()
async def start_vm(node: str, vmid: int) -> Dict[str, Any]:
    """Start a VM. Returns task ID for tracking."""
    try:
        return await proxmox_api(f"/nodes/{node}/qemu/{vmid}/status/start", "POST")
    except Exception as e:
        logger.error(f"Failed to start VM: {e}")
        return {"error": str(e)}


@mcp.tool()
async def stop_vm(node: str, vmid: int, force: bool = False) -> Dict[str, Any]:
    """Stop a VM. Use force=True for hard stop."""
    try:
        endpoint = f"/nodes/{node}/qemu/{vmid}/status/stop"
        data = {"forceStop": 1} if force else {}
        return await proxmox_api(endpoint, "POST", data)
    except Exception as e:
        logger.error(f"Failed to stop VM: {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_cluster_status() -> Dict[str, Any]:
    """Get overall cluster status and health."""
    try:
        return await proxmox_api("/cluster/status")
    except Exception as e:
        logger.error(f"Failed to get cluster status: {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_storage(node: str = None) -> List[Dict[str, Any]]:
    """List storage pools. Optionally filter by node."""
    try:
        if node:
            return await proxmox_api(f"/nodes/{node}/storage")
        else:
            return await proxmox_api("/storage")
    except Exception as e:
        logger.error(f"Failed to get storage: {e}")
        return []


# =============================================================================
# REST API Endpoints (for CronJobs - bypass MCP session protocol)
# =============================================================================

app = mcp.get_app()


@app.get("/api/vms")
async def rest_list_vms():
    """REST endpoint for listing all VMs - used by graph-sync CronJob."""
    try:
        vms = await list_vms()
        return {"vms": [vm.model_dump() for vm in vms]}
    except Exception as e:
        logger.error(f"REST list_vms error: {e}")
        return {"error": str(e), "vms": []}


@app.get("/api/nodes")
async def rest_list_nodes():
    """REST endpoint for listing all nodes - used by graph-sync CronJob."""
    try:
        nodes = await list_nodes()
        return {"nodes": [n.model_dump() for n in nodes]}
    except Exception as e:
        logger.error(f"REST list_nodes error: {e}")
        return {"error": str(e), "nodes": []}


@app.get("/api/cluster")
async def rest_cluster_status():
    """REST endpoint for cluster status."""
    try:
        return await get_cluster_status()
    except Exception as e:
        logger.error(f"REST cluster_status error: {e}")
        return {"error": str(e)}


@app.get("/api/storage")
async def rest_list_storage():
    """REST endpoint for storage pools."""
    try:
        storage = await get_storage()
        return {"storage": storage}
    except Exception as e:
        logger.error(f"REST list_storage error: {e}")
        return {"error": str(e), "storage": []}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting Proxmox MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
