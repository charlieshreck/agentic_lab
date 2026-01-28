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
    """Sync ArgoCD applications from prod cluster to Neo4j (GitOps chain).

    Phase 0.2: Improved connectivity with namespace derivation and umbrella detection.
    """
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
        # Phase 0.2 fix: Use actual destination namespace from ArgoCD spec
        destination_namespace = app.get("destination_namespace", "")
        destination_server = app.get("destination_server", "")

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

        # Determine target cluster from destination_server or path/repo fallback
        if destination_server:
            if "10.20.0" in destination_server or "agentic" in destination_server:
                target_cluster = "agentic"
            elif "10.30.0" in destination_server or "monit" in destination_server:
                target_cluster = "monit"
            else:
                target_cluster = "prod"
        elif "agentic" in (path or "") or "agentic_lab" in (repo or ""):
            target_cluster = "agentic"
        elif "monit" in (path or "") or "monit_homelab" in (repo or ""):
            target_cluster = "monit"
        else:
            target_cluster = "prod"

        # Phase 0.2 fix: Use actual destination namespace, fall back to path derivation
        if destination_namespace:
            derived_namespace = destination_namespace
        else:
            # Fallback: derive from path structure
            derived_namespace = _derive_namespace_from_path(path, name, project, target_cluster)

        # Phase 0.2: Detect umbrella apps (app-of-apps pattern)
        is_umbrella = _is_umbrella_app(name, path)

        neo4j.write("""
        MERGE (a:ArgoApp {name: $name})
        SET a.project = $project,
            a.sync_status = $sync_status,
            a.health = $health,
            a.repo = $repo,
            a.path = $path,
            a.target_cluster = $target_cluster,
            a.destination_namespace = $destination_namespace,
            a.destination_server = $destination_server,
            a.derived_namespace = $derived_namespace,
            a.is_umbrella = $is_umbrella,
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
            "destination_namespace": destination_namespace,
            "destination_server": destination_server,
            "derived_namespace": derived_namespace,
            "is_umbrella": is_umbrella,
            "status": app_status,
        })
        count += 1
        app_names.append(name)

    mark_active(neo4j, "ArgoApp", app_names)

    # Phase 0.2: Run connectivity pass after all apps are synced
    _link_argocd_to_services(neo4j)

    logger.info(f"Synced {count} ArgoCD applications")
    return count


def _derive_namespace_from_path(path: str, name: str, project: str, cluster: str) -> str:
    """Derive the likely target namespace from ArgoCD app path.

    Patterns observed:
    - kubernetes/applications/media/sonarr -> 'media'
    - kubernetes/applications/apps/homepage -> 'apps'
    - kubernetes/platform/traefik -> 'traefik' or cluster default
    - kubernetes/argocd-apps/* -> 'argocd' (meta apps)
    """
    if not path:
        # Fallback: use project name for monitoring apps
        if project == "monitoring":
            return "monitoring"
        # Fallback: agentic cluster usually uses ai-platform
        if cluster == "agentic":
            return "ai-platform"
        return ""

    parts = path.rstrip("/").split("/")

    # Pattern: kubernetes/applications/<namespace>/<app>
    if len(parts) >= 4 and parts[1] == "applications":
        namespace_candidate = parts[2]
        # Known namespace mappings
        if namespace_candidate in ["media", "apps", "platform", "public"]:
            return namespace_candidate
        # App name as namespace (e.g., kubernetes/applications/keep)
        if len(parts) == 3:
            return "ai-platform" if cluster == "agentic" else namespace_candidate

    # Pattern: kubernetes/platform/<app> -> often uses app name as namespace
    if len(parts) >= 3 and parts[1] == "platform":
        app_name = parts[-1]
        # Common platform namespaces
        if app_name in ["traefik", "cert-manager", "velero", "coroot"]:
            return app_name
        return ""

    # Pattern: kubernetes/argocd-apps/* -> argocd namespace
    if "argocd-apps" in path:
        return "argocd"

    return ""


def _is_umbrella_app(name: str, path: str) -> bool:
    """Detect umbrella apps (app-of-apps pattern).

    These apps deploy other ArgoCD apps, not direct workloads.
    """
    umbrella_indicators = [
        "-applications",  # e.g., agentic-applications
        "-apps",          # e.g., cluster-apps
        "argocd-apps",    # meta app directories
        "platform",       # often contains multiple apps
    ]

    name_lower = name.lower()
    path_lower = (path or "").lower()

    # Check name patterns
    if any(ind in name_lower for ind in ["-applications", "-apps"]):
        return True

    # Check path patterns
    if path_lower.endswith("/argocd-apps") or "/argocd-apps/" in path_lower:
        return True

    # Specific known umbrella apps
    known_umbrellas = [
        "agentic-applications", "monitoring-platform", "domain-mcps",
        "external-bridges", "agentic-external", "monitoring-external",
    ]
    if name_lower in known_umbrellas:
        return True

    return False


def _link_argocd_to_services(neo4j: Neo4jClient):
    """Multi-strategy ArgoApp -> Service linking with confidence scores.

    Phase 0.2: Runs after all apps are synced for better cross-referencing.
    """
    # Strategy 1: Exact name match in target cluster (highest confidence)
    neo4j.write("""
    MATCH (a:ArgoApp)
    WHERE a._sync_status = 'active' AND NOT a.is_umbrella
    MATCH (s:Service {name: a.name, cluster: a.target_cluster})
    WHERE s._sync_status = 'active'
    MERGE (a)-[r:DEPLOYS]->(s)
    SET r.strategy = 'exact_name', r.confidence = 1.0
    """)

    # Strategy 2: Derived namespace match (high confidence)
    neo4j.write("""
    MATCH (a:ArgoApp)
    WHERE a._sync_status = 'active' AND NOT a.is_umbrella
      AND a.derived_namespace <> '' AND NOT (a)-[:DEPLOYS]->()
    MATCH (s:Service {namespace: a.derived_namespace, cluster: a.target_cluster})
    WHERE s._sync_status = 'active'
      AND (s.name = a.name OR s.name STARTS WITH a.name OR a.name STARTS WITH s.name)
    WITH a, s
    ORDER BY CASE WHEN s.name = a.name THEN 0 ELSE 1 END
    WITH a, collect(s)[0] AS best_svc
    WHERE best_svc IS NOT NULL
    MERGE (a)-[r:DEPLOYS]->(best_svc)
    SET r.strategy = 'derived_namespace', r.confidence = 0.9
    """)

    # Strategy 3: Path-derived service name
    neo4j.write("""
    MATCH (a:ArgoApp)
    WHERE a._sync_status = 'active' AND NOT a.is_umbrella
      AND a.path IS NOT NULL AND NOT (a)-[:DEPLOYS]->()
    WITH a, split(a.path, '/')[-1] AS path_name
    WHERE path_name <> a.name
    MATCH (s:Service {name: path_name, cluster: a.target_cluster})
    WHERE s._sync_status = 'active'
    MERGE (a)-[r:DEPLOYS]->(s)
    SET r.strategy = 'path_derived', r.confidence = 0.85
    """)

    # Strategy 4: Deployment label match (medium confidence)
    neo4j.write("""
    MATCH (a:ArgoApp)
    WHERE a._sync_status = 'active' AND NOT a.is_umbrella AND NOT (a)-[:DEPLOYS]->()
    MATCH (d:Deployment {cluster: a.target_cluster})
    WHERE d._sync_status = 'active'
      AND (d.name = a.name OR d.labels CONTAINS a.name)
    MATCH (s:Service {name: d.name, namespace: d.namespace, cluster: d.cluster})
    WHERE s._sync_status = 'active'
    WITH a, s LIMIT 1
    MERGE (a)-[r:DEPLOYS]->(s)
    SET r.strategy = 'deployment_match', r.confidence = 0.8
    """)

    # Strategy 5: Namespace-only match for known namespace patterns
    neo4j.write("""
    MATCH (a:ArgoApp)
    WHERE a._sync_status = 'active' AND NOT a.is_umbrella AND NOT (a)-[:DEPLOYS]->()
      AND a.derived_namespace IN ['media', 'apps', 'monitoring', 'ai-platform']
    MATCH (s:Service {namespace: a.derived_namespace, cluster: a.target_cluster})
    WHERE s._sync_status = 'active'
    WITH a, collect(s) AS services
    WHERE size(services) > 0 AND size(services) < 5
    UNWIND services AS svc
    MERGE (a)-[r:DEPLOYS]->(svc)
    SET r.strategy = 'namespace_broad', r.confidence = 0.6
    """)
