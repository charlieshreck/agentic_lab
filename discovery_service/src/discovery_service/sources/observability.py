"""Sync observability data (Coroot, Gatus, Keep alerts, Grafana dashboards) to Neo4j."""

import json
import logging
import re

from discovery_service.config import GATUS_URL
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_coroot_services(neo4j: Neo4jClient, mcp: McpClient) -> tuple[int, list[str]]:
    """Sync service health from Coroot to Neo4j.

    Returns (count, anomalous_service_ids).
    """
    logger.info("Syncing Coroot service health...")

    overview_response = mcp.call_tool("observability", "coroot_get_infrastructure_overview")

    if not overview_response or not isinstance(overview_response, dict) or "error" in overview_response:
        msg = overview_response.get("error", "no data") if isinstance(overview_response, dict) else "unexpected format"
        logger.warning(f"Coroot overview unavailable: {msg}")
        return 0, []

    COROOT_CLUSTER_IDS = {"jd756uxv", "qorspfs5", "loka6zue"}

    count = 0
    anomalous_services: list[str] = []
    services = overview_response.get("services", {})

    for service_key, service_data in services.items():
        coroot_id = service_data.get("id", service_key)
        parts = coroot_id.split(":")
        if len(parts) == 4:
            _, namespace, kind, name = parts
            if namespace == "_" or kind == "Unknown":
                continue
        elif len(parts) == 2:
            namespace = parts[0]
            name = parts[1]
        elif "/" in service_key:
            sparts = service_key.split("/", 1)
            namespace = sparts[0]
            name = sparts[1]
        else:
            namespace = "unknown"
            name = service_key

        if name.isdigit() or "." in name:
            continue
        if namespace in COROOT_CLUSTER_IDS:
            continue

        health = service_data.get("health", "unknown")
        anomaly_count = service_data.get("anomalies", 0)

        status = {"ok": "healthy", "warning": "warning", "critical": "critical", "error": "critical"}.get(health, "unknown")

        if anomaly_count > 0:
            anomalous_services.append(coroot_id)

        result = neo4j.query("""
        MATCH (s:Service {name: $name, namespace: $namespace})
        SET s.health = $health,
            s.coroot_id = $coroot_id,
            s.anomaly_count = $anomaly_count,
            s.last_health_check = datetime()
        RETURN s.name
        """, {
            "name": name,
            "namespace": namespace,
            "health": health,
            "coroot_id": coroot_id,
            "anomaly_count": anomaly_count,
        })
        if result:
            count += 1

    # Coroot alerts
    alerts_response = mcp.call_tool("observability", "coroot_get_alerts")
    alerts = extract_list(alerts_response, "alerts", "result")

    for alert in alerts:
        alert_name = alert.get("name", alert.get("alertname", "unknown"))
        service = alert.get("service", "")
        status = alert.get("status", "unknown")
        severity = alert.get("severity", alert.get("labels", {}).get("severity", "info"))

        neo4j.write("""
        MERGE (a:Alert {name: $alert_name})
        SET a.status = $status,
            a.severity = $severity,
            a.service = $service,
            a.last_seen = datetime(),
            a.source = 'coroot',
            a._sync_status = 'active'
        """, {
            "alert_name": alert_name,
            "status": status,
            "severity": severity,
            "service": service,
        })

    logger.info(f"Synced {count} services from Coroot, {len(alerts)} alerts")
    return count, anomalous_services


def sync_coroot_service_map(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync global service dependency map from Coroot."""
    logger.info("Syncing Coroot service dependency map...")

    COROOT_CLUSTER_MAP = {"jd756uxv": "prod", "qorspfs5": "agentic", "loka6zue": "monit"}

    def parse_coroot_id(app_id):
        parts = app_id.split(":")
        if len(parts) == 4:
            cluster_id, namespace, kind, name = parts
            return COROOT_CLUSTER_MAP.get(cluster_id, cluster_id), namespace, kind, name
        elif len(parts) == 2:
            return "unknown", parts[0], "Service", parts[1]
        return None, None, None, None

    map_response = mcp.call_tool("observability", "coroot_get_service_map")
    if not map_response or isinstance(map_response, dict) and "error" in map_response:
        logger.warning(f"Coroot service map unavailable: {map_response}")
        return 0

    if isinstance(map_response, str):
        try:
            map_response = json.loads(map_response)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Coroot service map returned non-JSON: {str(map_response)[:200]}")
            return 0

    if not isinstance(map_response, dict):
        logger.warning(f"Coroot service map unexpected type: {type(map_response)}")
        return 0

    data = map_response.get("data", map_response)
    if not isinstance(data, dict):
        data = map_response
    nodes = data.get("nodes", data.get("map", []))
    if nodes is None:
        nodes = []
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    logger.info(
        f"  Coroot map: {len(nodes)} nodes, type={type(nodes).__name__}, "
        f"sample keys={list(nodes[0].keys()) if nodes and isinstance(nodes[0], dict) else 'N/A'}"
    )

    dep_count = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        app_id = node.get("id", node.get("app_id", ""))
        if not app_id:
            continue

        src_cluster, src_ns, src_kind, src_name = parse_coroot_id(app_id)
        if not src_name:
            continue

        for upstream in (node.get("upstreams") or []):
            up_id = upstream if isinstance(upstream, str) else upstream.get("id", "")
            up_cluster, up_ns, up_kind, up_name = parse_coroot_id(up_id)
            if not up_name:
                continue

            result = neo4j.write("""
            MERGE (s1:Service {name: $src_name, namespace: $src_ns})
            MERGE (s2:Service {name: $up_name, namespace: $up_ns})
            MERGE (s1)-[r:DEPENDS_ON]->(s2)
            SET r.last_seen = datetime(), r.source = 'coroot'
            RETURN s2.name
            """, {"src_name": src_name, "src_ns": src_ns, "up_name": up_name, "up_ns": up_ns})
            if result:
                dep_count += 1

        for downstream in (node.get("downstreams") or []):
            down_id = downstream if isinstance(downstream, str) else downstream.get("id", "")
            down_cluster, down_ns, down_kind, down_name = parse_coroot_id(down_id)
            if not down_name:
                continue

            result = neo4j.write("""
            MERGE (s1:Service {name: $down_name, namespace: $down_ns})
            MERGE (s2:Service {name: $src_name, namespace: $src_ns})
            MERGE (s1)-[r:DEPENDS_ON]->(s2)
            SET r.last_seen = datetime(), r.source = 'coroot'
            RETURN s1.name
            """, {"src_name": src_name, "src_ns": src_ns, "down_name": down_name, "down_ns": down_ns})
            if result:
                dep_count += 1

    logger.info(f"Synced {dep_count} service dependencies from Coroot service map")
    return dep_count


def sync_gatus_health(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync endpoint health from Gatus to Neo4j."""
    logger.info("Syncing Gatus endpoint health...")

    response = mcp.call_rest(GATUS_URL, "/api/v1/endpoints/statuses")

    if not response or isinstance(response, dict) and "error" in response:
        logger.warning(f"Gatus unavailable: {response}")
        return 0

    endpoints = response if isinstance(response, list) else []

    count = 0
    linked = 0
    monitor_keys = []

    for endpoint in endpoints:
        name = endpoint.get("name", "unknown")
        group = endpoint.get("group", "default")
        key = endpoint.get("key", f"{group}_{name}")

        results = endpoint.get("results", [])
        latest = results[-1] if results else {}
        success = latest.get("success", False)
        status_code = latest.get("status", 0)
        response_time = latest.get("duration", 0) / 1000000  # ns -> ms

        uptime = 0
        if results:
            successful = sum(1 for r in results if r.get("success", False))
            uptime = round((successful / len(results)) * 100, 2)

        if success and uptime >= 99:
            monitor_status = "healthy"
        elif success:
            monitor_status = "degraded"
        else:
            monitor_status = "unhealthy"

        neo4j.write("""
        MERGE (e:UptimeMonitor {key: $key})
        SET e.name = $name,
            e.group = $group,
            e.healthy = $healthy,
            e.status_code = $status_code,
            e.response_time_ms = $response_time,
            e.uptime_percent = $uptime,
            e.status = $status,
            e.last_check = datetime(),
            e.source = 'gatus',
            e._sync_status = 'active'
        """, {
            "key": key,
            "name": name,
            "group": group,
            "healthy": success,
            "status_code": status_code,
            "response_time": response_time,
            "uptime": uptime,
            "status": monitor_status,
        })
        count += 1
        monitor_keys.append(key)

        # Link UptimeMonitor to Services / Hosts / VMs
        clean_name = re.sub(r"\(.*?\)", "", name).lower().strip().replace(" ", "-").rstrip("-")
        if len(clean_name) > 3 and not clean_name.endswith("-mcp"):
            # Strategy 1: Exact service name match
            match_result = neo4j.query("""
            MATCH (e:UptimeMonitor {key: $key})
            MATCH (s:Service)
            WHERE toLower(s.name) = $clean_name
              AND NOT toLower(s.name) ENDS WITH '-mcp'
            MERGE (e)-[:MONITORS]->(s)
            RETURN s.name AS matched
            """, {"key": key, "clean_name": clean_name})

            if not match_result:
                # Strategy 2: Fuzzy service match
                match_result = neo4j.query("""
                MATCH (e:UptimeMonitor {key: $key})
                MATCH (s:Service)
                WHERE (toLower(s.name) CONTAINS $clean_name OR $clean_name CONTAINS toLower(s.name))
                  AND size(s.name) > 3
                  AND NOT toLower(s.name) ENDS WITH '-mcp'
                  AND toFloat(size(s.name)) / toFloat(size($clean_name)) > 0.5
                  AND toFloat(size(s.name)) / toFloat(size($clean_name)) < 2.0
                WITH e, s LIMIT 1
                MERGE (e)-[:MONITORS]->(s)
                RETURN s.name AS matched
                """, {"key": key, "clean_name": clean_name})

            if not match_result:
                # Strategy 3: Match to VM/Host/NAS by name
                match_result = neo4j.query("""
                MATCH (e:UptimeMonitor {key: $key})
                MATCH (target)
                WHERE (target:VM OR target:NAS OR target:Host)
                  AND (toLower(target.name) CONTAINS $clean_name
                    OR $clean_name CONTAINS toLower(target.name))
                  AND size(target.name) > 2
                WITH e, target LIMIT 1
                MERGE (e)-[:MONITORS]->(target)
                RETURN target.name AS matched
                """, {"key": key, "clean_name": clean_name})

            if match_result:
                linked += 1

    mark_active(neo4j, "UptimeMonitor", monitor_keys, id_field="key")

    logger.info(f"Synced {count} endpoints from Gatus, {linked} linked to targets")
    return count


def sync_keep_alerts(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Keep alert aggregation to Neo4j."""
    logger.info("Syncing Keep alerts...")

    alerts_response = mcp.call_tool("observability", "keep_list_alerts")
    if not alerts_response or isinstance(alerts_response, dict) and "error" in alerts_response:
        logger.warning(f"Keep unavailable: {alerts_response}")
        return 0

    alerts = extract_list(alerts_response, "alerts", "result")

    count = 0
    alert_names = []
    for alert in alerts:
        name = alert.get("name", alert.get("fingerprint", "unknown"))
        status = alert.get("status", "unknown")
        severity = alert.get("severity", "info")
        source = alert.get("source", [])
        source_str = ", ".join(source) if isinstance(source, list) else str(source)
        description = alert.get("description", "")

        alert_status = {"firing": "firing", "resolved": "resolved", "acknowledged": "acknowledged"}.get(status, status)

        neo4j.write("""
        MERGE (a:Alert {name: $name})
        SET a.status = $alert_status,
            a.severity = $severity,
            a.alert_source = $source,
            a.description = $description,
            a.keep_status = $keep_status,
            a.last_seen = datetime(),
            a._sync_status = 'active'
        """, {
            "name": name,
            "alert_status": alert_status,
            "severity": severity,
            "source": source_str,
            "description": description[:500] if description else "",
            "keep_status": status,
        })
        count += 1
        alert_names.append(name)

        # Link Alert->Service if alert has service label
        svc = alert.get("service", "")
        if not svc and isinstance(alert.get("labels"), dict):
            svc = alert["labels"].get("service", "")
        if svc:
            neo4j.write("""
            MATCH (a:Alert {name: $name})
            MATCH (s:Service {name: $svc})
            MERGE (a)-[:AFFECTS]->(s)
            """, {"name": name, "svc": svc})

    mark_active(neo4j, "Alert", alert_names)

    logger.info(f"Synced {count} alerts from Keep")
    return count


def sync_grafana_dashboards(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Grafana dashboards to Neo4j."""
    logger.info("Syncing Grafana dashboards...")

    dashboards_response = mcp.call_tool("observability", "grafana_list_dashboards")
    if not dashboards_response or isinstance(dashboards_response, dict) and "error" in dashboards_response:
        logger.warning(f"Grafana unavailable: {dashboards_response}")
        return 0

    dashboards = extract_list(dashboards_response, "dashboards", "result")

    count = 0
    dashboard_uids = []
    for dash in dashboards:
        title = dash.get("title", "")
        uid = dash.get("uid", "")
        if not title or not uid:
            continue

        folder = dash.get("folderTitle", dash.get("folder", ""))
        tags = dash.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        url = dash.get("url", "")

        neo4j.write("""
        MERGE (d:Dashboard {uid: $uid})
        SET d.title = $title,
            d.folder = $folder,
            d.tags = $tags,
            d.url = $url,
            d.status = 'active',
            d.last_seen = datetime(),
            d.source = 'grafana',
            d._sync_status = 'active'
        """, {
            "uid": uid,
            "title": title,
            "folder": folder,
            "tags": tags_str,
            "url": url,
        })
        count += 1
        dashboard_uids.append(uid)

        # Link Dashboard->Service by tag matching
        for tag in (tags if isinstance(tags, list) else []):
            if len(tag) > 3:
                neo4j.write("""
                MATCH (d:Dashboard {uid: $uid})
                MATCH (s:Service)
                WHERE toLower(s.name) = toLower($tag)
                MERGE (d)-[:VISUALIZES]->(s)
                """, {"uid": uid, "tag": tag})

    mark_active(neo4j, "Dashboard", dashboard_uids, id_field="uid")

    logger.info(f"Synced {count} Grafana dashboards")
    return count
