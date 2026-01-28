"""Mark & Sweep lifecycle management, Network deduplication, and Orphan Lifecycle.

Phase 0.4: Orphan Lifecycle implements aggressive pruning for nodes that remain
orphans after connectivity fixes, with tiered grace periods and protection rules.
"""

import logging
from datetime import timedelta

from discovery_service.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 0.4: Orphan Lifecycle Configuration
# ---------------------------------------------------------------------------

# Labels that should NEVER be pruned as orphans (structural/foundational nodes)
PROTECTED_LABELS = [
    "Network",        # Network topology (prod, agentic, monit)
    "Location",       # Physical locations
    "Cluster",        # Kubernetes clusters
    "ProxmoxNode",    # Hypervisor hosts
    "NAS",            # Storage systems
    "StoragePool",    # ZFS pools
]

# Tiered grace periods for different node types
# Nodes become eligible for pruning after this many days as orphan
ORPHAN_GRACE_DAYS = {
    # Infrastructure nodes - longer grace (may be temporarily disconnected)
    "VM": 30,
    "Host": 30,
    "Device": 30,
    "TasmotaDevice": 30,
    "HAEntity": 14,
    # Kubernetes resources - shorter grace (frequently recreated)
    "Pod": 1,
    "Service": 7,
    "Deployment": 7,
    "StatefulSet": 7,
    "DaemonSet": 7,
    "Ingress": 7,
    "PersistentVolumeClaim": 14,
    # ArgoCD/GitOps - medium grace
    "ArgoApp": 14,
    # Monitoring/observability - short grace
    "Alert": 1,
    "UptimeMonitor": 7,
    "Dashboard": 14,
    # DNS/network - medium grace
    "DNSRecord": 14,
    "ReverseProxy": 14,
    "CloudflareTunnel": 14,
    # Knowledge/documentation - longer grace
    "RunbookDocument": 30,
    # Default for unlisted types
    "default": 14,
}


# ---------------------------------------------------------------------------
# Mark & Sweep
# ---------------------------------------------------------------------------

def mark_all_stale(neo4j: Neo4jClient, node_labels: list[str]):
    """Phase 1: Mark all syncable nodes as stale before sync begins."""
    for label in node_labels:
        neo4j.write(f"MATCH (n:{label}) SET n._sync_status = 'stale'")
    logger.info(f"Marked {len(node_labels)} node types as stale")


def mark_active(neo4j: Neo4jClient, label: str, ids: list, id_field: str = "name"):
    """Phase 2: Called during sync to mark nodes that still exist.

    *ids* is a list of identifier values matching *id_field* on the given label.
    """
    if not ids:
        return
    neo4j.write(
        f"""
        UNWIND $ids AS id
        MATCH (n:{label} {{{id_field}: id}})
        SET n._sync_status = 'active', n.last_seen = datetime()
        """,
        {"ids": ids},
    )


def sweep_stale(neo4j: Neo4jClient, node_labels: list[str]):
    """Phase 3: Delete nodes still marked stale after sync completes."""
    total = 0
    for label in node_labels:
        result = neo4j.query(
            f"""
            MATCH (n:{label} {{_sync_status: 'stale'}})
            DETACH DELETE n
            RETURN count(n) AS deleted
            """
        )
        deleted = result[0]["deleted"] if result else 0
        if deleted:
            logger.info(f"  Swept {deleted} stale {label} nodes")
            total += deleted
    logger.info(f"Sweep complete: {total} nodes removed")
    return total


# ---------------------------------------------------------------------------
# Legacy lifecycle (kept for labels excluded from Mark & Sweep)
# ---------------------------------------------------------------------------

def run_lifecycle_management(neo4j: Neo4jClient):
    """Age-based lifecycle for structural/manual node types excluded from sweep.

    Also runs Phase 0.4 orphan lifecycle management.
    """
    logger.info("Running legacy lifecycle management...")

    # Clean up orphan structural nodes with no relationships
    for label in ("Location",):  # Network handled by dedup
        result = neo4j.query(
            f"""
            MATCH (n:{label})
            WHERE NOT (n)--()
            DELETE n
            RETURN count(n) AS cnt
            """
        )
        cnt = result[0]["cnt"] if result else 0
        if cnt:
            logger.info(f"  Deleted {cnt} orphan {label} nodes")

    # Phase 0.4: Run orphan lifecycle
    mark_orphans(neo4j)
    sweep_aged_orphans(neo4j)


# ---------------------------------------------------------------------------
# Phase 0.4: Orphan Lifecycle Functions
# ---------------------------------------------------------------------------

def mark_orphans(neo4j: Neo4jClient) -> int:
    """Mark unconnected nodes with orphan_since timestamp.

    Nodes are marked as orphans if:
    - They have no relationships
    - They are not protected labels
    - They are not manually enriched (have description/notes/owner)
    - They are active (_sync_status = 'active')

    Returns number of newly marked orphans.
    """
    # First, protect nodes that have manual enrichment
    neo4j.write("""
    MATCH (n)
    WHERE (n.description IS NOT NULL AND n.description <> '')
       OR (n.notes IS NOT NULL AND n.notes <> '')
       OR (n.owner IS NOT NULL AND n.owner <> '')
    SET n._protected = true
    """)

    # Mark new orphans (nodes with no relationships and no orphan_since)
    protected_labels_clause = " AND ".join([f"NOT n:{label}" for label in PROTECTED_LABELS])

    result = neo4j.query(f"""
    MATCH (n)
    WHERE NOT (n)-[]-()
      AND n._sync_status = 'active'
      AND n.orphan_since IS NULL
      AND NOT coalesce(n._protected, false)
      AND {protected_labels_clause}
    SET n.orphan_since = datetime()
    RETURN count(n) AS marked
    """)

    marked = result[0]["marked"] if result else 0
    if marked:
        logger.info(f"  Marked {marked} new orphan nodes")

    # Clear orphan status for nodes that now have relationships
    result = neo4j.query("""
    MATCH (n)
    WHERE n.orphan_since IS NOT NULL
      AND (n)-[]-()
    SET n.orphan_since = NULL
    RETURN count(n) AS cleared
    """)

    cleared = result[0]["cleared"] if result else 0
    if cleared:
        logger.info(f"  Cleared orphan status for {cleared} reconnected nodes")

    return marked


def sweep_aged_orphans(neo4j: Neo4jClient) -> int:
    """Delete orphan nodes that have exceeded their grace period.

    Uses tiered grace periods from ORPHAN_GRACE_DAYS config.
    Returns total number of pruned nodes.
    """
    total_pruned = 0

    # Get all labels with orphan nodes
    result = neo4j.query("""
    MATCH (n)
    WHERE n.orphan_since IS NOT NULL
    RETURN DISTINCT labels(n)[0] AS label, count(n) AS count
    """)

    if not result:
        return 0

    for row in result:
        label = row["label"]
        if not label or label in PROTECTED_LABELS:
            continue

        grace_days = ORPHAN_GRACE_DAYS.get(label, ORPHAN_GRACE_DAYS["default"])

        # Delete orphans older than grace period
        delete_result = neo4j.query(f"""
        MATCH (n:{label})
        WHERE n.orphan_since IS NOT NULL
          AND n.orphan_since < datetime() - duration({{days: {grace_days}}})
          AND NOT coalesce(n._protected, false)
        DETACH DELETE n
        RETURN count(n) AS pruned
        """)

        pruned = delete_result[0]["pruned"] if delete_result else 0
        if pruned:
            logger.info(f"  Pruned {pruned} aged {label} orphans (>{grace_days} days)")
            total_pruned += pruned

    if total_pruned:
        logger.info(f"Orphan lifecycle: pruned {total_pruned} aged orphan nodes")

    return total_pruned


def get_orphan_stats(neo4j: Neo4jClient) -> dict:
    """Get statistics on orphan nodes by label and age.

    Returns dict with counts by label and age buckets.
    """
    result = neo4j.query("""
    MATCH (n)
    WHERE n.orphan_since IS NOT NULL
    WITH labels(n)[0] AS label,
         CASE
           WHEN n.orphan_since > datetime() - duration({days: 1}) THEN '<1d'
           WHEN n.orphan_since > datetime() - duration({days: 7}) THEN '1-7d'
           WHEN n.orphan_since > datetime() - duration({days: 14}) THEN '7-14d'
           WHEN n.orphan_since > datetime() - duration({days: 30}) THEN '14-30d'
           ELSE '>30d'
         END AS age_bucket,
         count(*) AS count
    RETURN label, age_bucket, count
    ORDER BY label, age_bucket
    """)

    stats = {}
    for row in result or []:
        label = row["label"]
        if label not in stats:
            stats[label] = {}
        stats[label][row["age_bucket"]] = row["count"]

    return stats


# ---------------------------------------------------------------------------
# Network node deduplication
# ---------------------------------------------------------------------------

def dedup_network_nodes(neo4j: Neo4jClient) -> int:
    """Merge duplicate Network nodes: bare (no cidr) -> enriched (has cidr).

    network-discovery creates enriched Network nodes with cidr/purpose.
    graph-sync creates bare ones via MERGE {name: $name}.
    This dedup moves relationships to the enriched node and deletes the bare one.
    """
    logger.info("Deduplicating Network nodes...")

    # Move incoming CONNECTED_TO from bare to enriched
    neo4j.write("""
    MATCH (bare:Network), (enriched:Network)
    WHERE bare.name = enriched.name
      AND enriched.cidr IS NOT NULL
      AND bare.cidr IS NULL
    WITH bare, enriched
    MATCH (source)-[r:CONNECTED_TO]->(bare)
    MERGE (source)-[:CONNECTED_TO]->(enriched)
    DELETE r
    """)

    # Move outgoing CONNECTED_TO from bare to enriched
    neo4j.write("""
    MATCH (bare:Network), (enriched:Network)
    WHERE bare.name = enriched.name
      AND enriched.cidr IS NOT NULL
      AND bare.cidr IS NULL
    WITH bare, enriched
    MATCH (bare)-[r:CONNECTED_TO]->(target)
    MERGE (enriched)-[:CONNECTED_TO]->(target)
    DELETE r
    """)

    # Delete now-orphaned bare Network nodes
    result = neo4j.query("""
    MATCH (bare:Network)
    WHERE bare.cidr IS NULL
      AND NOT (bare)-[]-()
    DETACH DELETE bare
    RETURN count(bare) AS deleted
    """)

    deleted = result[0]["deleted"] if result else 0
    logger.info(f"Deduplicated {deleted} bare Network nodes")
    return deleted
