"""Sync Proxmox VMs to Neo4j."""

import logging

from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_proxmox_vms(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync VMs from Proxmox to Neo4j."""
    logger.info("Syncing Proxmox VMs...")

    vms_response = mcp.call_tool(
        "infrastructure", "proxmox_list_vms",
        {"params": {"response_format": "json"}},
    )
    vms = extract_list(vms_response, "vms")

    if not vms:
        logger.warning("No VMs returned from Proxmox MCP")
        return 0

    rows = []
    for vm in vms:
        vmid = vm.get("vmid")
        name = vm.get("name", f"vm-{vmid}")
        status = vm.get("status", "unknown")
        node = vm.get("node", "unknown")

        cpu_percent = round(vm.get("cpu", 0) * 100, 1)
        cpus = vm.get("maxcpu", vm.get("cpus", 0))
        mem_used = vm.get("mem", 0)
        mem_total = vm.get("maxmem", 0)
        memory_used_gb = round(mem_used / (1024**3), 2) if mem_used else 0
        memory_total_gb = round(mem_total / (1024**3), 2) if mem_total else 0
        memory_percent = round((mem_used / mem_total) * 100, 1) if mem_total else 0
        uptime_days = round(vm.get("uptime", 0) / 86400, 2)
        netin_gb = round(vm.get("netin", 0) / (1024**3), 2)
        netout_gb = round(vm.get("netout", 0) / (1024**3), 2)
        disk_max_gb = round(vm.get("maxdisk", 0) / (1024**3), 2)

        rows.append({
            "vmid": str(vmid),
            "name": name,
            "status": status,
            "node": node,
            "type": vm.get("type", "qemu"),
            "cpu_percent": cpu_percent,
            "cpus": cpus,
            "memory_used_gb": memory_used_gb,
            "memory_total_gb": memory_total_gb,
            "memory_percent": memory_percent,
            "uptime_days": uptime_days,
            "netin_gb": netin_gb,
            "netout_gb": netout_gb,
            "disk_max_gb": disk_max_gb,
        })

    neo4j.batch_merge("""
        MERGE (v:VM {vmid: row.vmid})
        SET v.name = row.name,
            v.status = row.status,
            v.node = row.node,
            v.type = row.type,
            v.cpu_percent = row.cpu_percent,
            v.cpus = row.cpus,
            v.memory_used_gb = row.memory_used_gb,
            v.memory_total_gb = row.memory_total_gb,
            v.memory_percent = row.memory_percent,
            v.uptime_days = row.uptime_days,
            v.netin_gb = row.netin_gb,
            v.netout_gb = row.netout_gb,
            v.disk_max_gb = row.disk_max_gb,
            v.last_seen = datetime(),
            v.source = 'proxmox',
            v._sync_status = 'active'
        WITH v, row
        MERGE (h:Host {hostname: row.node})
        SET h.type = 'hypervisor'
        MERGE (h)-[:HOSTS]->(v)
        WITH v, row
        MERGE (p:ProxmoxNode {name: row.node})
        MERGE (v)-[:RUNS_ON]->(p)
    """, rows)

    mark_active(neo4j, "VM", [r["vmid"] for r in rows], id_field="vmid")

    logger.info(f"Synced {len(rows)} VMs from Proxmox")
    return len(rows)
