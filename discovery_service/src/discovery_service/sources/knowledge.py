"""Sync runbooks to Neo4j with relationship enrichment."""

import logging

from discovery_service.config import MCP_SERVERS
from discovery_service.graph.client import Neo4jClient
from discovery_service.mcp.client import McpClient

logger = logging.getLogger(__name__)


def sync_runbooks(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync runbooks to Neo4j with rich relationship enrichment."""
    logger.info("Syncing runbook relationships...")

    # Pre-fetch known entities from graph for text matching
    svc_rows = neo4j.query("MATCH (s:Service) RETURN s.name AS name, s.namespace AS ns")
    known_services: dict[str, str] = {}
    for row in svc_rows:
        svc_name = row.get("name")
        if svc_name and len(svc_name) > 3:
            known_services[svc_name.lower()] = svc_name

    host_rows = neo4j.query("MATCH (h:Host) RETURN h.hostname AS hostname")
    known_hosts: set[str] = set()
    for row in host_rows:
        hostname = row.get("hostname")
        if hostname and len(hostname) > 3:
            known_hosts.add(hostname.lower())

    alert_rows = neo4j.query("MATCH (a:Alert) RETURN a.name AS name")
    known_alerts: set[str] = set()
    for row in alert_rows:
        alert_name = row.get("name")
        if alert_name:
            known_alerts.add(alert_name)

    logger.info(f"  Pre-fetched {len(known_services)} services, {len(known_hosts)} hosts, {len(known_alerts)} alerts for matching")

    # Get runbooks from knowledge MCP REST API
    runbooks_response = mcp.call_rest(MCP_SERVERS["knowledge"], "/api/runbooks?limit=100")
    runbooks = runbooks_response.get("runbooks", []) if isinstance(runbooks_response, dict) else []

    count = 0
    rel_count = 0
    for runbook_entry in runbooks:
        qdrant_id = runbook_entry.get("id", "")
        title = runbook_entry.get("title", "")
        trigger_pattern = runbook_entry.get("trigger_pattern", "")

        if not title:
            continue

        path = runbook_entry.get("path", "")
        domain = runbook_entry.get("domain", "")
        if not domain and path:
            path_parts = path.replace("\\", "/").split("/")
            try:
                rb_idx = path_parts.index("runbooks")
                if rb_idx + 1 < len(path_parts) - 1:
                    domain = path_parts[rb_idx + 1]
            except ValueError:
                domain = path_parts[0] if len(path_parts) > 1 else ""

        solution = runbook_entry.get("solution", "")
        solution_preview = solution[:200] if solution else ""
        has_content = bool(solution)

        result = neo4j.write("""
        MERGE (r:RunbookDocument {qdrant_id: $qdrant_id})
        SET r.title = $title,
            r.path = $path,
            r.domain = $domain,
            r.automation_level = $automation_level,
            r.trigger_pattern = $trigger_pattern,
            r.solution_preview = $solution_preview,
            r.has_content = $has_content,
            r.last_seen = datetime(),
            r.source = 'knowledge'
        RETURN r.title
        """, {
            "qdrant_id": qdrant_id,
            "title": title,
            "path": path,
            "domain": domain,
            "automation_level": runbook_entry.get("automation_level", "manual"),
            "trigger_pattern": trigger_pattern,
            "solution_preview": solution_preview,
            "has_content": has_content,
        })

        if result:
            count += 1

        # --- Relationship enrichment ---
        solution_lower = (solution + " " + title).lower()

        # A. RESOLVES->Alert: trigger_pattern match + fuzzy title match
        if trigger_pattern and not trigger_pattern.startswith("*"):
            neo4j.write("""
            MATCH (r:RunbookDocument {qdrant_id: $qdrant_id})
            MERGE (a:Alert {name: $alert_name})
            MERGE (r)-[:RESOLVES]->(a)
            """, {"qdrant_id": qdrant_id, "alert_name": trigger_pattern})
            rel_count += 1

        # Fuzzy title->alert match
        title_normalized = title.lower().replace(" ", "").replace("-", "").replace("_", "")
        for alert_name in known_alerts:
            alert_normalized = alert_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            if title_normalized == alert_normalized or alert_name.lower() in solution_lower:
                neo4j.write("""
                MATCH (r:RunbookDocument {qdrant_id: $qdrant_id})
                MATCH (a:Alert {name: $alert_name})
                MERGE (r)-[:RESOLVES]->(a)
                """, {"qdrant_id": qdrant_id, "alert_name": alert_name})
                rel_count += 1

        # B. TROUBLESHOOTS->Service: text match service names in solution
        for svc_lower, svc_name in known_services.items():
            if svc_lower in solution_lower:
                neo4j.write("""
                MATCH (r:RunbookDocument {qdrant_id: $qdrant_id})
                MATCH (s:Service {name: $svc_name})
                MERGE (r)-[:TROUBLESHOOTS]->(s)
                """, {"qdrant_id": qdrant_id, "svc_name": svc_name})
                rel_count += 1

        # C. APPLIES_TO->Host: text match hostnames in solution
        for hostname_lower in known_hosts:
            if hostname_lower in solution_lower:
                neo4j.write("""
                MATCH (r:RunbookDocument {qdrant_id: $qdrant_id})
                MATCH (h:Host {hostname: $hostname})
                MERGE (r)-[:APPLIES_TO]->(h)
                """, {"qdrant_id": qdrant_id, "hostname": hostname_lower})
                rel_count += 1

    logger.info(f"Synced {count} runbooks, {rel_count} relationships created")
    return count
