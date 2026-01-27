"""Sync TrueNAS storage to Neo4j via direct API.

Iterates all configured TrueNAS instances, syncing pools, datasets,
shares (NFS + SMB), alerts, and apps.
"""

import logging

from discovery_service.api.truenas import TrueNASClient
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active

logger = logging.getLogger(__name__)


def _extract_nested(value, default=0):
    """Extract value from nested TrueNAS-style dicts like {"parsed": 123, "rawvalue": "123"}."""
    if isinstance(value, dict):
        return value.get("parsed", value.get("value", default))
    return value if value is not None else default


def sync_truenas_storage(neo4j: Neo4jClient, truenas: TrueNASClient) -> int:
    """Sync TrueNAS storage from all instances to Neo4j."""
    logger.info("Syncing TrueNAS storage (multi-instance direct API)...")

    if not truenas.instances:
        logger.warning("No TrueNAS instances configured")
        return 0

    total_pools = 0
    total_datasets = 0
    total_shares = 0
    total_alerts = 0
    total_apps = 0

    for instance in truenas.instances:
        try:
            pools = _sync_instance_pools(neo4j, truenas, instance)
            total_pools += pools
        except Exception as e:
            logger.error(f"  {instance}: pool sync failed: {e}")

        try:
            datasets = _sync_instance_datasets(neo4j, truenas, instance)
            total_datasets += datasets
        except Exception as e:
            logger.error(f"  {instance}: dataset sync failed: {e}")

        try:
            shares = _sync_instance_shares(neo4j, truenas, instance)
            total_shares += shares
        except Exception as e:
            logger.error(f"  {instance}: share sync failed: {e}")

        try:
            alerts = _sync_instance_alerts(neo4j, truenas, instance)
            total_alerts += alerts
        except Exception as e:
            logger.error(f"  {instance}: alert sync failed: {e}")

        try:
            apps = _sync_instance_apps(neo4j, truenas, instance)
            total_apps += apps
        except Exception as e:
            logger.error(f"  {instance}: app sync failed: {e}")

    logger.info(
        f"Synced TrueNAS: {total_pools} pools, {total_datasets} datasets, "
        f"{total_shares} shares, {total_alerts} alerts, {total_apps} apps "
        f"from {len(truenas.instances)} instances"
    )
    return total_pools


def _sync_instance_pools(neo4j: Neo4jClient, truenas: TrueNASClient, instance: str) -> int:
    """Sync storage pools from a TrueNAS instance."""
    pools = truenas.list_pools(instance)
    if not isinstance(pools, list):
        return 0

    rows = []
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

        rows.append({
            "name": name,
            "instance": instance,
            "status": pool_status,
            "size": pool_size,
            "used": pool_used,
            "size_gb": round(pool_size / (1024**3), 2) if pool_size else 0,
            "used_gb": round(pool_used / (1024**3), 2) if pool_used else 0,
        })

    if rows:
        neo4j.batch_merge("""
            MERGE (p:StoragePool {name: row.name, instance: row.instance})
            SET p.status = row.status,
                p.size = row.size,
                p.used = row.used,
                p.size_gb = row.size_gb,
                p.used_gb = row.used_gb,
                p.last_seen = datetime(),
                p.source = 'truenas',
                p._sync_status = 'active'
        """, rows)

        mark_active(neo4j, "StoragePool",
                    [f"{r['name']}|{r['instance']}" for r in rows],
                    id_field="name")

    logger.info(f"  {instance}: {len(rows)} pools")
    return len(rows)


def _sync_instance_datasets(neo4j: Neo4jClient, truenas: TrueNASClient, instance: str) -> int:
    """Sync datasets from a TrueNAS instance."""
    datasets = truenas.list_datasets(instance)
    if not isinstance(datasets, list):
        return 0

    rows = []
    for dataset in datasets:
        name = dataset.get("name", "")
        if not name:
            continue

        pool_name = name.split("/")[0] if "/" in name else name
        used = _extract_nested(dataset.get("used", 0))
        available = _extract_nested(dataset.get("available", 0))
        dataset_status = "online" if available > 0 else "full"

        rows.append({
            "name": name,
            "instance": instance,
            "pool_name": pool_name,
            "mountpoint": dataset.get("mountpoint", ""),
            "used": used,
            "available": available,
            "used_gb": round(used / (1024**3), 2) if used else 0,
            "available_gb": round(available / (1024**3), 2) if available else 0,
            "status": dataset_status,
        })

    if rows:
        neo4j.batch_merge("""
            MERGE (d:Dataset {name: row.name, instance: row.instance})
            SET d.mountpoint = row.mountpoint,
                d.used = row.used,
                d.available = row.available,
                d.used_gb = row.used_gb,
                d.available_gb = row.available_gb,
                d.status = row.status,
                d.last_seen = datetime(),
                d.source = 'truenas',
                d._sync_status = 'active'
            WITH d, row
            MATCH (p:StoragePool {name: row.pool_name, instance: row.instance})
            MERGE (p)-[:CONTAINS]->(d)
        """, rows)

        mark_active(neo4j, "Dataset",
                    [r["name"] for r in rows])

    logger.info(f"  {instance}: {len(rows)} datasets")
    return len(rows)


def _sync_instance_shares(neo4j: Neo4jClient, truenas: TrueNASClient, instance: str) -> int:
    """Sync NFS and SMB shares from a TrueNAS instance."""
    count = 0

    # NFS shares
    try:
        nfs_shares = truenas.list_nfs_shares(instance)
        if isinstance(nfs_shares, list):
            nfs_rows = []
            for share in nfs_shares:
                path = share.get("path", "")
                if not path:
                    # TrueNAS SCALE uses 'paths' (list) for NFS
                    paths = share.get("paths", [])
                    path = paths[0] if paths else ""
                if not path:
                    continue

                enabled = share.get("enabled", True)
                nfs_rows.append({
                    "path": path,
                    "instance": instance,
                    "name": path.split("/")[-1] if path else "unknown",
                    "type": "nfs",
                    "enabled": enabled,
                    "status": "online" if enabled else "offline",
                })

            if nfs_rows:
                neo4j.batch_merge("""
                    MERGE (s:Share {path: row.path, instance: row.instance})
                    SET s.name = row.name,
                        s.type = row.type,
                        s.enabled = row.enabled,
                        s.status = row.status,
                        s.last_seen = datetime(),
                        s.source = 'truenas',
                        s._sync_status = 'active'
                """, nfs_rows)
                count += len(nfs_rows)
    except Exception as e:
        logger.warning(f"  {instance}: NFS share sync failed: {e}")

    # SMB shares
    try:
        smb_shares = truenas.list_smb_shares(instance)
        if isinstance(smb_shares, list):
            smb_rows = []
            for share in smb_shares:
                path = share.get("path", "")
                name = share.get("name", path.split("/")[-1] if path else "unknown")
                if not path:
                    continue

                enabled = share.get("enabled", True)
                smb_rows.append({
                    "path": path,
                    "instance": instance,
                    "name": name,
                    "type": "smb",
                    "enabled": enabled,
                    "status": "online" if enabled else "offline",
                })

            if smb_rows:
                neo4j.batch_merge("""
                    MERGE (s:Share {path: row.path, instance: row.instance})
                    SET s.name = row.name,
                        s.type = row.type,
                        s.enabled = row.enabled,
                        s.status = row.status,
                        s.last_seen = datetime(),
                        s.source = 'truenas',
                        s._sync_status = 'active'
                """, smb_rows)
                count += len(smb_rows)
    except Exception as e:
        logger.warning(f"  {instance}: SMB share sync failed: {e}")

    if count:
        mark_active(neo4j, "Share", [], id_field="path")  # Already marked active in batch_merge

    logger.info(f"  {instance}: {count} shares")
    return count


def _sync_instance_alerts(neo4j: Neo4jClient, truenas: TrueNASClient, instance: str) -> int:
    """Sync alerts from a TrueNAS instance."""
    alerts = truenas.list_alerts(instance)
    if not isinstance(alerts, list):
        return 0

    rows = []
    for alert in alerts:
        alert_id = alert.get("id", alert.get("uuid", ""))
        if not alert_id:
            continue

        rows.append({
            "alert_id": str(alert_id),
            "instance": instance,
            "level": alert.get("level", "unknown"),
            "message": alert.get("formatted", alert.get("text", "")),
            "source": alert.get("source", ""),
            "klass": alert.get("klass", ""),
            "dismissed": alert.get("dismissed", False),
        })

    if rows:
        neo4j.batch_merge("""
            MERGE (a:StorageAlert {alert_id: row.alert_id, instance: row.instance})
            SET a.level = row.level,
                a.message = row.message,
                a.source = row.source,
                a.klass = row.klass,
                a.dismissed = row.dismissed,
                a.last_seen = datetime(),
                a._sync_status = 'active'
        """, rows)

        mark_active(neo4j, "StorageAlert",
                    [r["alert_id"] for r in rows],
                    id_field="alert_id")

    logger.info(f"  {instance}: {len(rows)} alerts")
    return len(rows)


def _sync_instance_apps(neo4j: Neo4jClient, truenas: TrueNASClient, instance: str) -> int:
    """Sync TrueNAS Docker/apps (Garage, etc.) from a TrueNAS instance."""
    apps = truenas.list_apps(instance)
    if not isinstance(apps, list):
        return 0

    rows = []
    for app in apps:
        name = app.get("name", app.get("id", ""))
        if not name:
            continue

        state = app.get("state", app.get("status", "unknown"))
        version = app.get("version", app.get("human_version", ""))

        rows.append({
            "name": name,
            "instance": instance,
            "state": state,
            "version": str(version),
        })

    if rows:
        neo4j.batch_merge("""
            MERGE (a:App {name: row.name, instance: row.instance})
            SET a.state = row.state,
                a.version = row.version,
                a.last_seen = datetime(),
                a.source = 'truenas',
                a._sync_status = 'active'
        """, rows)

        mark_active(neo4j, "App",
                    [r["name"] for r in rows])

    logger.info(f"  {instance}: {len(rows)} apps")
    return len(rows)
