"""Sync Home Assistant areas/entities, Tasmota devices, and ArgoCD applications to Neo4j."""

import logging

from discovery_service.config import HA_SYNC_DOMAINS, SENSOR_DEVICE_CLASSES
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


def sync_ha_entities(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Home Assistant entities to Neo4j as HAEntity nodes.

    Filters by HA_SYNC_DOMAINS.  For 'sensor' domain, further filters by
    SENSOR_DEVICE_CLASSES (Gemini ruling: battery, power, temperature, energy only).
    Links HAEntity -[:CONTROLLED_BY]-> Service (home-assistant).
    """
    logger.info("Syncing Home Assistant entities...")

    try:
        response = mcp.call_tool("home", "list_entities")
        if not response:
            logger.warning("Home-MCP unavailable, skipping HA entity sync")
            return 0
    except Exception as e:
        logger.warning(f"Home-MCP unavailable, skipping HA entity sync: {e}")
        return 0

    entities = extract_list(response, "entities", "result")
    if not entities:
        logger.info("No entities returned from HA")
        return 0

    rows = []
    for entity in entities:
        entity_id = entity.get("entity_id", "")
        if not entity_id:
            continue

        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if domain not in HA_SYNC_DOMAINS:
            continue

        # Gemini ruling: filter sensors aggressively by device_class
        attributes = entity.get("attributes", {})
        if domain == "sensor":
            device_class = attributes.get("device_class", "")
            if device_class not in SENSOR_DEVICE_CLASSES:
                continue

        state = entity.get("state", "unknown")
        friendly_name = attributes.get("friendly_name", entity_id)

        rows.append({
            "entity_id": entity_id,
            "domain": domain,
            "friendly_name": friendly_name,
            "state": state,
            "device_class": attributes.get("device_class", ""),
            "unit": attributes.get("unit_of_measurement", ""),
        })

    if not rows:
        logger.info("No matching HA entities after filtering")
        return 0

    # Batch create HAEntity nodes
    neo4j.batch_merge("""
    MERGE (e:HAEntity {entity_id: row.entity_id})
    SET e.domain = row.domain,
        e.friendly_name = row.friendly_name,
        e.state = row.state,
        e.device_class = row.device_class,
        e.unit = row.unit,
        e.source = 'home_assistant',
        e.last_seen = datetime(),
        e._sync_status = 'active'
    """, rows)

    # Link all HAEntities to the Home Assistant service
    neo4j.write("""
    MATCH (s:Service)
    WHERE s.name = 'home-assistant' OR s.name = 'homeassistant'
    WITH s LIMIT 1
    MATCH (e:HAEntity)
    WHERE e._sync_status = 'active'
    MERGE (e)-[:CONTROLLED_BY]->(s)
    """)

    entity_ids = [r["entity_id"] for r in rows]
    mark_active(neo4j, "HAEntity", entity_ids, id_field="entity_id")

    logger.info(f"Synced {len(rows)} HA entities")
    return len(rows)


def sync_tasmota_devices(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Tasmota smart devices to Neo4j as TasmotaDevice nodes.

    Uses tasmota_status_all to get all 26 devices in a single call.
    Links TasmotaDevice -[:ON_NETWORK]-> Network(prod).
    Links TasmotaDevice -[:EXPOSES]-> HAEntity (MAC-first, name fallback with confidence:low).
    """
    logger.info("Syncing Tasmota devices...")

    try:
        response = mcp.call_tool("home", "tasmota_status_all")
        if not response:
            logger.warning("Home-MCP unavailable, skipping Tasmota sync")
            return 0
    except Exception as e:
        logger.warning(f"Home-MCP unavailable, skipping Tasmota sync: {e}")
        return 0

    devices = extract_list(response, "devices", "result")
    if not devices:
        logger.info("No Tasmota devices returned")
        return 0

    rows = []
    for device in devices:
        ip = device.get("ip", "")
        if not ip:
            continue

        # Navigate nested Tasmota status structure
        # Response format: {ip, name, status: {Status: {...}, StatusPRM: {...}, ...}}
        raw_status = device.get("status", {})
        status = raw_status.get("Status", device.get("Status", {}))
        status_prm = raw_status.get("StatusPRM", device.get("StatusPRM", {}))
        status_fwr = raw_status.get("StatusFWR", device.get("StatusFWR", {}))
        status_net = raw_status.get("StatusNET", device.get("StatusNET", {}))

        # Extract device name from nested structure
        name = device.get("name") or ""
        if not name:
            name = status.get("DeviceName", "")
        if not name:
            friendly = status.get("FriendlyName", [])
            if isinstance(friendly, list) and friendly:
                name = friendly[0]
            elif isinstance(friendly, str):
                name = friendly
        if not name:
            name = f"tasmota-{ip}"

        mac = (
            status_net.get("Mac", "")
            or device.get("mac", "")
            or ""
        ).lower()

        firmware = status_fwr.get("Version", device.get("firmware", ""))
        hardware = status_fwr.get("Hardware", device.get("hardware", ""))
        uptime = status_prm.get("Uptime", device.get("uptime", ""))
        power = device.get("power", status.get("Power", ""))

        rows.append({
            "ip": ip,
            "name": name,
            "mac": mac,
            "firmware": firmware,
            "hardware": hardware,
            "uptime": uptime,
            "power": str(power),
        })

    if not rows:
        logger.info("No valid Tasmota devices after parsing")
        return 0

    # Batch create TasmotaDevice nodes
    neo4j.batch_merge("""
    MERGE (t:TasmotaDevice {ip: row.ip})
    SET t.name = row.name,
        t.mac = row.mac,
        t.firmware = row.firmware,
        t.hardware = row.hardware,
        t.uptime = row.uptime,
        t.power = row.power,
        t.source = 'tasmota',
        t.last_seen = datetime(),
        t._sync_status = 'active'
    """, rows)

    # Link all TasmotaDevices to the prod network (all on 10.10.0.x)
    neo4j.write("""
    MATCH (t:TasmotaDevice)
    WHERE t._sync_status = 'active'
    MATCH (n:Network {name: 'prod'})
    MERGE (t)-[:ON_NETWORK]->(n)
    """)

    # Gemini ruling: MAC-first matching for EXPOSES relationship
    neo4j.write("""
    MATCH (t:TasmotaDevice)
    WHERE t._sync_status = 'active' AND t.mac <> ''
    MATCH (e:HAEntity)
    WHERE e.entity_id CONTAINS replace(t.mac, ':', '')
       OR e.entity_id CONTAINS replace(t.mac, ':', '_')
    MERGE (t)-[:EXPOSES]->(e)
    """)

    # Gemini ruling: fuzzy name fallback with confidence:"low"
    neo4j.write("""
    MATCH (t:TasmotaDevice)
    WHERE t._sync_status = 'active'
      AND NOT (t)-[:EXPOSES]->()
      AND t.name <> ''
    WITH t, toLower(replace(replace(t.name, ' ', '_'), '-', '_')) AS norm_name
    MATCH (e:HAEntity)
    WHERE toLower(e.entity_id) CONTAINS norm_name
       OR toLower(e.friendly_name) CONTAINS toLower(t.name)
    WITH t, e LIMIT 3
    MERGE (t)-[r:EXPOSES]->(e)
    SET r.confidence = 'low', r.match_type = 'name_fuzzy'
    """)

    device_ips = [r["ip"] for r in rows]
    mark_active(neo4j, "TasmotaDevice", device_ips, id_field="ip")

    logger.info(f"Synced {len(rows)} Tasmota devices")
    return len(rows)


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
