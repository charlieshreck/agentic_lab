"""Sync Proxmox VMs and LXC containers to Neo4j via direct API.

Iterates all configured Proxmox hosts, syncing QEMU VMs and LXC containers
with IP address extraction for graph linking.
"""

import logging

from discovery_service.api.proxmox import ProxmoxClient, extract_lxc_ip, extract_vm_ip
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active

logger = logging.getLogger(__name__)


def sync_proxmox_vms(neo4j: Neo4jClient, proxmox: ProxmoxClient) -> int:
    """Sync VMs and LXC containers from all Proxmox hosts."""
    logger.info("Syncing Proxmox VMs and containers (multi-host direct API)...")

    if not proxmox.hosts:
        logger.warning("No Proxmox hosts configured")
        return 0

    all_rows = []
    node_rows = []

    for host_name in proxmox.hosts:
        try:
            nodes = proxmox.list_nodes(host_name)
        except Exception as e:
            logger.error(f"  {host_name}: failed to list nodes: {e}")
            continue

        for node_info in nodes:
            node = node_info.get("node", "unknown")

            node_rows.append({
                "name": node,
                "host": host_name,
                "status": node_info.get("status", "unknown"),
                "cpu": round(node_info.get("cpu", 0) * 100, 1),
                "maxcpu": node_info.get("maxcpu", 0),
                "mem_used_gb": round(node_info.get("mem", 0) / (1024**3), 2),
                "mem_total_gb": round(node_info.get("maxmem", 0) / (1024**3), 2),
                "uptime_days": round(node_info.get("uptime", 0) / 86400, 2),
            })

            # QEMU VMs
            try:
                vms = proxmox.list_vms(host_name, node)
            except Exception as e:
                logger.error(f"  {host_name}/{node}: failed to list VMs: {e}")
                vms = []

            for vm in vms:
                row = _build_vm_row(vm, node, host_name, "qemu")

                # Try to get IP via QEMU guest agent
                vmid = vm.get("vmid")
                if vmid and vm.get("status") == "running":
                    try:
                        ifaces = proxmox.get_vm_interfaces(host_name, node, vmid)
                        ip = extract_vm_ip(ifaces)
                        if ip:
                            row["ip"] = ip
                    except Exception:
                        pass  # Guest agent may not be running

                all_rows.append(row)

            # LXC containers
            try:
                containers = proxmox.list_containers(host_name, node)
            except Exception as e:
                logger.error(f"  {host_name}/{node}: failed to list containers: {e}")
                containers = []

            for ct in containers:
                row = _build_vm_row(ct, node, host_name, "lxc")

                # Get IP from LXC config
                vmid = ct.get("vmid")
                if vmid:
                    try:
                        config = proxmox.get_container_config(host_name, node, vmid)
                        ip = extract_lxc_ip(config)
                        if ip:
                            row["ip"] = ip
                    except Exception:
                        pass

                all_rows.append(row)

        logger.info(f"  {host_name}: {sum(1 for r in all_rows if r['host'] == host_name)} VMs/containers")

    if not all_rows:
        logger.warning("No VMs or containers found across Proxmox hosts")
        return 0

    # Merge ProxmoxNode nodes
    if node_rows:
        neo4j.batch_merge("""
            MERGE (p:ProxmoxNode {name: row.name})
            SET p.host = row.host,
                p.status = row.status,
                p.cpu_percent = row.cpu,
                p.maxcpu = row.maxcpu,
                p.mem_used_gb = row.mem_used_gb,
                p.mem_total_gb = row.mem_total_gb,
                p.uptime_days = row.uptime_days,
                p.last_seen = datetime(),
                p.source = 'proxmox',
                p._sync_status = 'active'
        """, node_rows)

    # Merge VM/LXC nodes
    neo4j.batch_merge("""
        MERGE (v:VM {vmid: row.vmid})
        SET v.name = row.name,
            v.status = row.status,
            v.node = row.node,
            v.host = row.host,
            v.type = row.type,
            v.ip = row.ip,
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
        MERGE (p:ProxmoxNode {name: row.node})
        MERGE (v)-[:RUNS_ON]->(p)
    """, all_rows)

    mark_active(neo4j, "VM", [r["vmid"] for r in all_rows], id_field="vmid")

    # Link VMs with IPs to Host nodes (K8s nodes)
    vms_with_ip = [r for r in all_rows if r.get("ip")]
    if vms_with_ip:
        neo4j.batch_merge("""
            MATCH (v:VM {vmid: row.vmid})
            WHERE v.ip IS NOT NULL
            MATCH (h:Host {internal_ip: v.ip})
            MERGE (v)-[:MAPS_TO]->(h)
        """, vms_with_ip)
        logger.info(f"  Linked {len(vms_with_ip)} VMs with IPs to Host nodes")

    qemu_count = sum(1 for r in all_rows if r["type"] == "qemu")
    lxc_count = sum(1 for r in all_rows if r["type"] == "lxc")
    logger.info(f"Synced {len(all_rows)} Proxmox entities ({qemu_count} VMs, {lxc_count} LXC) from {len(proxmox.hosts)} hosts")
    return len(all_rows)


def _build_vm_row(vm: dict, node: str, host: str, vm_type: str) -> dict:
    """Build a standardised row dict from a Proxmox VM/container response."""
    vmid = vm.get("vmid")
    mem_used = vm.get("mem", 0)
    mem_total = vm.get("maxmem", 0)

    return {
        "vmid": str(vmid),
        "name": vm.get("name", f"{vm_type}-{vmid}"),
        "status": vm.get("status", "unknown"),
        "node": node,
        "host": host,
        "type": vm_type,
        "ip": "",
        "cpu_percent": round(vm.get("cpu", 0) * 100, 1),
        "cpus": vm.get("maxcpu", vm.get("cpus", 0)),
        "memory_used_gb": round(mem_used / (1024**3), 2) if mem_used else 0,
        "memory_total_gb": round(mem_total / (1024**3), 2) if mem_total else 0,
        "memory_percent": round((mem_used / mem_total) * 100, 1) if mem_total else 0,
        "uptime_days": round(vm.get("uptime", 0) / 86400, 2),
        "netin_gb": round(vm.get("netin", 0) / (1024**3), 2),
        "netout_gb": round(vm.get("netout", 0) / (1024**3), 2),
        "disk_max_gb": round(vm.get("maxdisk", 0) / (1024**3), 2),
    }
