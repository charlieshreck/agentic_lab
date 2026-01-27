"""Mark & Sweep lifecycle management and Network node deduplication."""

import logging

from discovery_service.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


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
    """Age-based lifecycle for structural/manual node types excluded from sweep."""
    logger.info("Running legacy lifecycle management...")

    # Clean up orphan structural nodes with no relationships
    for label in ("Location", "Network"):
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
