"""Sync Home Assistant areas and ArgoCD applications to Neo4j."""

import logging

from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_ha_areas(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync area/location data from Home Assistant to Neo4j.

    Graceful degradation: If HA-MCP fails, log warning and continue.
    """
    logger.info("Syncing Home Assistant areas...")

    try:
        entities_response = mcp.call_tool("home", "list_entities")
        if not entities_response:
            logger.warning("Home-MCP unavailable or returned empty response, skipping area sync")
            return 0
    except Exception as e:
        logger.warning(f"Home-MCP unavailable, skipping area sync: {e}")
        return 0

    entities = extract_list(entities_response, "entities", "result")
    if not entities:
        logger.info("No entities returned from HA, skipping area sync")
        return 0

    synced_count = 0
    for entity in entities:
        area = entity.get("area", entity.get("area_id", ""))
        attributes = entity.get("attributes", {})
        ip = attributes.get("ip", attributes.get("ip_address", ""))

        if not area or not ip:
            continue

        try:
            result = neo4j.query("""
            MATCH (h:Host {ip: $ip})
            SET h.location = $area
            WITH h
            MERGE (loc:Location {name: $area})
            MERGE (h)-[:LOCATED_IN]->(loc)
            RETURN h.ip
            """, {"ip": ip, "area": area})

            if result:
                synced_count += 1
                logger.debug(f"Synced location '{area}' for {ip}")
        except Exception as e:
            logger.warning(f"Failed to sync area for {ip}: {e}")

    logger.info(f"HA area sync complete: {synced_count} entities updated")
    return synced_count


def sync_argocd_apps(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync ArgoCD applications from prod cluster to Neo4j (GitOps chain)."""
    logger.info("Syncing ArgoCD applications...")

    apps_response = mcp.call_tool("infrastructure", "argocd_get_applications")
    apps = extract_list(apps_response, "applications", "result")

    count = 0
    app_names = []
    for app in apps:
        name = app.get("name")
        if not name:
            continue

        project = app.get("project", "default")
        sync_status = app.get("sync_status", "unknown")
        health = app.get("health", "unknown")
        repo = app.get("repo", "")
        path = app.get("path", "")

        if health == "Healthy" and sync_status == "Synced":
            app_status = "healthy"
        elif health == "Degraded":
            app_status = "degraded"
        elif sync_status == "OutOfSync":
            app_status = "out-of-sync"
        elif health == "Missing":
            app_status = "unhealthy"
        else:
            app_status = health.lower() if health else "unknown"

        if "agentic" in (path or ""):
            target_cluster = "agentic"
        elif "monit" in (path or ""):
            target_cluster = "monit"
        else:
            target_cluster = "prod"

        neo4j.write("""
        MERGE (a:ArgoApp {name: $name})
        SET a.project = $project,
            a.sync_status = $sync_status,
            a.health = $health,
            a.repo = $repo,
            a.path = $path,
            a.target_cluster = $target_cluster,
            a.status = $status,
            a.last_seen = datetime(),
            a.source = 'argocd',
            a._sync_status = 'active'
        """, {
            "name": name,
            "project": project,
            "sync_status": sync_status,
            "health": health,
            "repo": repo,
            "path": path,
            "target_cluster": target_cluster,
            "status": app_status,
        })
        count += 1
        app_names.append(name)

        # Strategy 1: Link ArgoApp->Service by name match in target cluster
        neo4j.write("""
        MATCH (a:ArgoApp {name: $name})
        MATCH (s:Service {name: $name, cluster: $target_cluster})
        MERGE (a)-[:DEPLOYS]->(s)
        """, {"name": name, "target_cluster": target_cluster})

        # Strategy 2: path-derived name
        if path:
            app_from_path = path.rstrip("/").split("/")[-1]
            if app_from_path and app_from_path != name:
                neo4j.write("""
                MATCH (a:ArgoApp {name: $argo_name})
                WHERE NOT (a)-[:DEPLOYS]->()
                MATCH (s:Service {name: $svc_name})
                WITH a, s LIMIT 1
                MERGE (a)-[:DEPLOYS]->(s)
                """, {"argo_name": name, "svc_name": app_from_path})

        # Strategy 3: match via Deployment of same name
        neo4j.write("""
        MATCH (a:ArgoApp {name: $name})
        WHERE NOT (a)-[:DEPLOYS]->()
        MATCH (d:Deployment {name: $name})
        MATCH (s:Service {name: d.name, namespace: d.namespace, cluster: d.cluster})
        WITH a, s LIMIT 1
        MERGE (a)-[:DEPLOYS]->(s)
        """, {"name": name})

        # Strategy 4: ArgoApp name matches a namespace
        neo4j.write("""
        MATCH (a:ArgoApp {name: $name})
        WHERE NOT (a)-[:DEPLOYS]->()
        MATCH (s:Service {namespace: $name})
        WHERE s.name = $name OR s.name STARTS WITH $name
        WITH a, s LIMIT 1
        MERGE (a)-[:DEPLOYS]->(s)
        """, {"name": name})

    mark_active(neo4j, "ArgoApp", app_names)

    logger.info(f"Synced {count} ArgoCD applications")
    return count
