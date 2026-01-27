"""Sync TrueNAS storage to Neo4j."""

import logging

from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def _extract_nested(value, default=0):
    """Extract value from nested TrueNAS-style dicts like {"parsed": 123, "rawvalue": "123"}."""
    if isinstance(value, dict):
        return value.get("parsed", value.get("value", default))
    return value if value is not None else default


def sync_truenas_storage(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync TrueNAS storage pools, datasets, and shares to Neo4j."""
    logger.info("Syncing TrueNAS storage...")

    # --- Pools ---
    pools_response = mcp.call_tool(
        "infrastructure", "truenas_list_pools",
        {"params": {"instance": "hdd", "response_format": "json"}},
    )
    pools = extract_list(pools_response, "pools", "result")

    pool_names = []
    for pool in pools:
        name = pool.get("name")
        if not name:
            continue

        pool_size = 0
        pool_used = 0
        topology = pool.get("topology", {})
        for vdev_type in ("data", "cache", "log", "spare", "special", "dedup"):
            for vdev in topology.get(vdev_type, []):
                stats = vdev.get("stats", {})
                pool_size += stats.get("size", 0)
                pool_used += stats.get("allocated", 0)
        if pool_size == 0:
            pool_size = _extract_nested(pool.get("size", 0))
        if pool_used == 0:
            pool_used = _extract_nested(pool.get("used", 0))

        raw_status = pool.get("status", "unknown").lower()
        pool_status = {"online": "healthy", "degraded": "degraded", "faulted": "unhealthy"}.get(raw_status, raw_status)

        neo4j.write("""
        MERGE (p:StoragePool {name: $name})
        SET p.status = $status,
            p.size = $size,
            p.used = $used,
            p.size_gb = $size_gb,
            p.used_gb = $used_gb,
            p.last_seen = datetime(),
            p.source = 'truenas',
            p._sync_status = 'active'
        """, {
            "name": name,
            "status": pool_status,
            "size": pool_size,
            "used": pool_used,
            "size_gb": round(pool_size / (1024**3), 2) if pool_size else 0,
            "used_gb": round(pool_used / (1024**3), 2) if pool_used else 0,
        })
        pool_names.append(name)

    mark_active(neo4j, "StoragePool", pool_names)

    # --- Datasets ---
    datasets_response = mcp.call_tool(
        "infrastructure", "truenas_list_datasets",
        {"params": {"instance": "hdd", "response_format": "json"}},
    )
    datasets = extract_list(datasets_response, "datasets", "result")

    dataset_names = []
    for dataset in datasets:
        name = dataset.get("name", "")
        pool_name = name.split("/")[0] if "/" in name else name

        used = _extract_nested(dataset.get("used", 0))
        available = _extract_nested(dataset.get("available", 0))
        dataset_status = "online" if available > 0 else "full"

        neo4j.write("""
        MERGE (d:Dataset {name: $name})
        SET d.mountpoint = $mountpoint,
            d.used = $used,
            d.available = $available,
            d.used_gb = $used_gb,
            d.available_gb = $available_gb,
            d.status = $status,
            d.last_seen = datetime(),
            d.source = 'truenas',
            d._sync_status = 'active'
        WITH d
        MATCH (p:StoragePool {name: $pool_name})
        MERGE (p)-[:CONTAINS]->(d)
        """, {
            "name": name,
            "pool_name": pool_name,
            "mountpoint": dataset.get("mountpoint", ""),
            "used": used,
            "available": available,
            "used_gb": round(used / (1024**3), 2) if used else 0,
            "available_gb": round(available / (1024**3), 2) if available else 0,
            "status": dataset_status,
        })
        dataset_names.append(name)

    mark_active(neo4j, "Dataset", dataset_names)

    # --- Shares ---
    shares_response = mcp.call_tool(
        "infrastructure", "truenas_list_shares",
        {"params": {"instance": "hdd", "response_format": "json"}},
    )
    if isinstance(shares_response, list):
        shares = shares_response
    elif isinstance(shares_response, dict):
        if "result" in shares_response and isinstance(shares_response["result"], list):
            shares = shares_response["result"]
        else:
            shares = shares_response.get("nfs", []) + shares_response.get("smb", [])
    else:
        shares = []

    share_paths = []
    for share in shares:
        path = share.get("path", "")
        name = share.get("name", path.split("/")[-1] if path else "unknown")
        enabled = share.get("enabled", True)
        share_status = "online" if enabled else "offline"

        neo4j.write("""
        MERGE (s:Share {path: $path})
        SET s.name = $name,
            s.type = $type,
            s.enabled = $enabled,
            s.status = $status,
            s.last_seen = datetime(),
            s.source = 'truenas',
            s._sync_status = 'active'
        """, {
            "path": path,
            "name": name,
            "type": share.get("type", "nfs"),
            "enabled": enabled,
            "status": share_status,
        })
        if path:
            share_paths.append(path)

    mark_active(neo4j, "Share", share_paths, id_field="path")

    logger.info(f"Synced {len(pool_names)} pools, {len(datasets)} datasets, {len(shares)} shares")
    return len(pool_names)
