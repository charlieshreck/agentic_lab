"""Sync UniFi devices, DNS topology, Caddy proxies, DHCP devices, and Cloudflare to Neo4j."""

import logging

from discovery_service.config import DHCP_NETWORK_MAP, DNS_NOISE_PATTERNS, MANUFACTURER_DEVICE_TYPE
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_unifi_devices(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync UniFi network devices to Neo4j."""
    logger.info("Syncing UniFi devices...")

    devices_response = mcp.call_tool("home", "unifi_list_devices")
    devices = extract_list(devices_response, "devices", "result")

    device_macs = []
    for device in devices:
        mac = device.get("mac", "").lower()
        if not mac:
            continue

        name = device.get("name", device.get("hostname", f"device-{mac}"))
        device_type = device.get("type", "unknown")
        model = device.get("model", "unknown")
        ip = device.get("ip", "")

        label = (
            "AccessPoint" if device_type in ("uap", "ap")
            else "Switch" if device_type in ("usw", "sw")
            else "NetworkDevice"
        )

        neo4j.write(f"""
        MERGE (d:{label} {{mac: $mac}})
        SET d.name = $name,
            d.model = $model,
            d.ip = $ip,
            d.status = $status,
            d.last_seen = datetime(),
            d.source = 'unifi',
            d._sync_status = 'active'
        WITH d
        MERGE (n:Network {{name: 'prod'}})
        MERGE (d)-[:CONNECTED_TO]->(n)
        """, {
            "mac": mac,
            "name": name,
            "model": model,
            "ip": ip,
            "status": device.get("state", "unknown"),
        })
        device_macs.append(mac)

    # Mark active for each label type that might have been created
    for lbl in ("AccessPoint", "Switch", "NetworkDevice"):
        mark_active(neo4j, lbl, device_macs, id_field="mac")

    # Client-to-AP connections
    clients_response = mcp.call_tool("home", "unifi_list_clients")
    clients = extract_list(clients_response, "clients", "result")

    for client in clients:
        mac = client.get("mac", "").lower()
        ap_mac = client.get("ap_mac", "").lower()
        if mac and ap_mac:
            neo4j.write("""
            MATCH (h:Host {mac: $mac})
            MATCH (ap:AccessPoint {mac: $ap_mac})
            MERGE (h)-[r:CONNECTED_VIA]->(ap)
            SET r.signal = $signal,
                r.channel = $channel,
                r.last_seen = datetime()
            """, {
                "mac": mac,
                "ap_mac": ap_mac,
                "signal": client.get("signal", 0),
                "channel": client.get("channel", 0),
            })

    logger.info(f"Synced {len(device_macs)} UniFi devices, processed {len(clients)} client connections")
    return len(device_macs)


def sync_dns_topology(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync DNS topology from AdGuard rewrites and Unbound overrides."""
    logger.info("Syncing DNS topology...")

    count = 0
    dns_domains = []

    # --- AdGuard rewrites ---
    try:
        rewrites_response = mcp.call_tool("infrastructure", "get_adguard_rewrites")
        rewrites = extract_list(rewrites_response, "rewrites", "result")

        for rewrite in rewrites:
            domain = rewrite.get("domain", "")
            answer = rewrite.get("answer", "")
            if not domain:
                continue

            neo4j.write("""
            MERGE (d:DNSRecord {domain: $domain})
            SET d.hostname = $domain,
                d.answer = $answer,
                d.record_type = 'rewrite',
                d.source = 'adguard',
                d.status = 'active',
                d.last_seen = datetime(),
                d._sync_status = 'active'
            """, {"domain": domain, "answer": answer})
            count += 1
            dns_domains.append(domain)

            # Link to Host if answer is an IP
            if answer and answer[0].isdigit():
                neo4j.write("""
                MATCH (d:DNSRecord {domain: $domain})
                MATCH (h:Host {ip: $ip})
                MERGE (d)-[:RESOLVES_TO]->(h)
                """, {"domain": domain, "ip": answer})

            # Link to Service by subdomain match
            subdomain = domain.split(".")[0] if "." in domain else domain
            if len(subdomain) > 3:
                neo4j.write("""
                MATCH (d:DNSRecord {domain: $domain})
                MATCH (s:Service)
                WHERE toLower(s.name) = toLower($subdomain)
                MERGE (d)-[:RESOLVES_TO]->(s)
                """, {"domain": domain, "subdomain": subdomain})

        logger.info(f"  AdGuard: {count} DNS rewrites")
    except Exception as e:
        logger.error(f"  AdGuard DNS sync failed: {e}")

    # --- Unbound overrides ---
    unbound_count = 0
    try:
        overrides_response = mcp.call_tool("infrastructure", "get_unbound_overrides")
        overrides = extract_list(overrides_response, "overrides", "result")

        for override in overrides:
            domain = override.get("domain", override.get("host", ""))
            target = override.get("server", override.get("ip", override.get("target", "")))
            if not domain:
                continue

            neo4j.write("""
            MERGE (d:DNSRecord {domain: $domain})
            SET d.hostname = $domain,
                d.answer = $target,
                d.record_type = 'override',
                d.source = 'unbound',
                d.status = 'active',
                d.last_seen = datetime(),
                d._sync_status = 'active'
            """, {"domain": domain, "target": target})
            unbound_count += 1
            dns_domains.append(domain)

            if target and target[0].isdigit():
                neo4j.write("""
                MATCH (d:DNSRecord {domain: $domain})
                MATCH (h:Host {ip: $ip})
                MERGE (d)-[:RESOLVES_TO]->(h)
                """, {"domain": domain, "ip": target})

        logger.info(f"  Unbound: {unbound_count} DNS overrides")
    except Exception as e:
        logger.error(f"  Unbound DNS sync failed: {e}")

    mark_active(neo4j, "DNSRecord", dns_domains, id_field="domain")

    total = count + unbound_count
    logger.info(f"Synced {total} DNS records total")
    return total


def sync_caddy_proxies(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Caddy reverse proxy entries to Neo4j.

    Joins proxy definitions (FromDomain) with handles (ToDomain/ToPort)
    via UUID: handle.reverse == proxy.uuid.
    """
    logger.info("Syncing Caddy reverse proxies...")

    proxies_response = mcp.call_tool("infrastructure", "list_caddy_reverse_proxies")
    proxies = extract_list(proxies_response, "proxies", "result")

    handles_response = mcp.call_tool("infrastructure", "list_caddy_handles")
    handles = extract_list(handles_response, "handles", "result")

    if not proxies:
        logger.warning("No Caddy proxies returned")
        return 0

    # Build handle lookup by proxy UUID
    handle_map: dict[str, dict] = {}
    for handle in handles:
        reverse_uuid = handle.get("reverse", "")
        if reverse_uuid:
            handle_map[reverse_uuid] = handle

    rows = []
    proxy_domains = []
    for proxy in proxies:
        uuid = proxy.get("uuid", "")
        domain = proxy.get("FromDomain", "")
        if not domain:
            continue

        enabled = proxy.get("enabled", "1") == "1"
        description = proxy.get("description", "")

        # Join with handle for upstream info
        handle = handle_map.get(uuid, {})
        upstream_ip = handle.get("ToDomain", "")
        raw_port = handle.get("ToPort", "")
        upstream_port = int(raw_port) if raw_port and raw_port.isdigit() else 0
        upstream_tls = handle.get("HttpTls", "0") == "1"

        rows.append({
            "domain": domain,
            "upstream_ip": upstream_ip,
            "upstream_port": upstream_port,
            "upstream_tls": upstream_tls,
            "description": description,
            "enabled": enabled,
        })
        proxy_domains.append(domain)

    if rows:
        neo4j.batch_merge("""
            MERGE (rp:ReverseProxy {domain: row.domain})
            SET rp.upstream_ip = row.upstream_ip,
                rp.upstream_port = row.upstream_port,
                rp.upstream_tls = row.upstream_tls,
                rp.description = row.description,
                rp.enabled = row.enabled,
                rp.last_seen = datetime(),
                rp.source = 'caddy',
                rp._sync_status = 'active'
        """, rows)

        # Link: DNSRecord -[:ROUTES_THROUGH]-> ReverseProxy (domain match)
        neo4j.write("""
        MATCH (rp:ReverseProxy)
        WHERE rp._sync_status = 'active'
        MATCH (dns:DNSRecord {domain: rp.domain})
        MERGE (dns)-[:ROUTES_THROUGH]->(rp)
        """)

        # Link: ReverseProxy -[:PROXIES_TO]-> target (upstream IP match)
        # Match any node type with matching IP — Host, VM, NAS, ProxmoxNode, Device
        # Priority: Host > VM > NAS > ProxmoxNode > Device (pick best per proxy)
        neo4j.write("""
        MATCH (rp:ReverseProxy)
        WHERE rp._sync_status = 'active' AND rp.upstream_ip <> ''
        WITH rp
        MATCH (target)
        WHERE (target:Host OR target:VM OR target:NAS OR target:ProxmoxNode OR target:Device)
          AND (target.ip = rp.upstream_ip OR target.internal_ip = rp.upstream_ip)
        WITH rp, target
        ORDER BY CASE
          WHEN target:Host THEN 0
          WHEN target:VM THEN 1
          WHEN target:NAS THEN 2
          WHEN target:ProxmoxNode THEN 3
          ELSE 4
        END
        WITH rp, collect(target)[0] AS best
        MERGE (rp)-[:PROXIES_TO]->(best)
        """)

    mark_active(neo4j, "ReverseProxy", proxy_domains, id_field="domain")

    logger.info(f"Synced {len(rows)} Caddy reverse proxies")
    return len(rows)


def sync_dhcp_devices(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync DHCP leases to Neo4j, enriching Hosts and creating Device nodes.

    Phase A: Enrich existing Host nodes with MAC + manufacturer.
    Phase B: Create Device nodes for all leases with classification.
    Gemini ruling: keep both Host and Device; link via NETWORK_INTERFACE_FOR.
    """
    logger.info("Syncing DHCP devices...")

    response = mcp.call_tool("infrastructure", "get_dhcp_leases")
    leases = extract_list(response, "leases", "result")

    if not leases:
        logger.warning("No DHCP leases returned")
        return 0

    # Phase A: Enrich existing Host nodes
    enrich_count = 0
    for lease in leases:
        mac = lease.get("mac", "").lower()
        ip = lease.get("address", "")
        if not mac or not ip:
            continue

        manufacturer = lease.get("man", "")
        result = neo4j.query("""
        MATCH (h:Host)
        WHERE h.ip = $ip OR h.internal_ip = $ip
        SET h.mac = $mac, h.manufacturer = $manufacturer
        RETURN h.ip
        """, {"ip": ip, "mac": mac, "manufacturer": manufacturer})

        if result:
            enrich_count += 1

    logger.info(f"  Enriched {enrich_count} existing Host nodes with DHCP data")

    # Phase B: Create Device nodes for all leases
    device_rows = []
    device_macs = []
    for lease in leases:
        mac = lease.get("mac", "").lower()
        if not mac:
            continue

        ip = lease.get("address", "")
        hostname = lease.get("hostname", lease.get("client-hostname", ""))
        manufacturer = lease.get("man", "")
        status = lease.get("status", "")
        if_descr = lease.get("if_descr", "")

        # Classify device type by manufacturer
        device_type = "unknown"
        if manufacturer:
            manufacturer_lower = manufacturer.lower()
            for keyword, dtype in MANUFACTURER_DEVICE_TYPE.items():
                if keyword in manufacturer_lower:
                    device_type = dtype
                    break

        network_name = DHCP_NETWORK_MAP.get(if_descr, if_descr.lower() if if_descr else "unknown")

        device_rows.append({
            "mac": mac,
            "ip": ip,
            "hostname": hostname,
            "manufacturer": manufacturer,
            "device_type": device_type,
            "status": status,
            "network_name": network_name,
        })
        device_macs.append(mac)

    if device_rows:
        neo4j.batch_merge("""
            MERGE (d:Device {mac: row.mac})
            SET d.ip = row.ip,
                d.hostname = row.hostname,
                d.manufacturer = row.manufacturer,
                d.device_type = row.device_type,
                d.status = row.status,
                d.network_name = row.network_name,
                d.last_seen = datetime(),
                d.source = 'dhcp',
                d._sync_status = 'active'
        """, device_rows)

        # Link: Device -[:ON_NETWORK]-> Network
        neo4j.write("""
        MATCH (d:Device)
        WHERE d._sync_status = 'active' AND d.network_name <> 'unknown'
        MATCH (n:Network {name: d.network_name})
        MERGE (d)-[:ON_NETWORK]->(n)
        """)

        # Link: Device -[:NETWORK_INTERFACE_FOR]-> Host (Gemini ruling)
        neo4j.write("""
        MATCH (d:Device)
        WHERE d._sync_status = 'active' AND d.ip IS NOT NULL
        MATCH (h:Host)
        WHERE h.ip = d.ip OR h.internal_ip = d.ip
        MERGE (d)-[:NETWORK_INTERFACE_FOR]->(h)
        """)

    mark_active(neo4j, "Device", device_macs, id_field="mac")

    logger.info(f"Synced {len(device_rows)} DHCP devices ({enrich_count} Host enrichments)")
    return len(device_rows)


def sync_cloudflare_dns(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Cloudflare DNS records and tunnels to Neo4j.

    Designed for graceful failure — early-exits if zones returns empty
    (indicates broken auth). Will produce warning logs until API token is fixed.
    """
    logger.info("Syncing Cloudflare DNS + Tunnels...")

    try:
        zones_response = mcp.call_tool("infrastructure", "cloudflare_list_zones",
                                        {"params": {"response_format": "json"}})
        zones = extract_list(zones_response, "zones", "result")
    except Exception as e:
        logger.warning(f"  Cloudflare zones unavailable (auth broken?): {e}")
        return 0

    if not zones:
        logger.warning("  Cloudflare returned no zones (auth likely broken), skipping")
        return 0

    count = 0
    dns_domains: list[str] = []

    for zone in zones:
        zone_id = zone.get("id", "")
        zone_name = zone.get("name", "")
        if not zone_id:
            continue

        try:
            records_response = mcp.call_tool("infrastructure", "cloudflare_list_dns_records",
                                              {"params": {"zone_id": zone_id, "response_format": "json"}})
            records = extract_list(records_response, "records", "result")
        except Exception as e:
            logger.warning(f"  Cloudflare DNS records for {zone_name} failed: {e}")
            continue

        for record in records:
            name = record.get("name", "")
            if not name:
                continue

            # Phase 0: Filter DNS noise patterns
            name_lower = name.lower()
            if any(pattern in name_lower for pattern in DNS_NOISE_PATTERNS):
                logger.debug(f"  Filtering DNS noise: {name}")
                continue

            record_type = record.get("type", "")
            content = record.get("content", "")
            proxied = record.get("proxied", False)

            neo4j.write("""
            MERGE (d:DNSRecord {domain: $name})
            SET d.hostname = $name,
                d.record_type = $record_type,
                d.answer = $content,
                d.proxied = $proxied,
                d.source = 'cloudflare',
                d.zone = $zone_name,
                d.last_seen = datetime(),
                d._sync_status = 'active'
            """, {
                "name": name,
                "record_type": record_type,
                "content": content,
                "proxied": proxied,
                "zone_name": zone_name,
            })
            count += 1
            dns_domains.append(name)

    # --- Tunnels ---
    tunnel_count = 0
    tunnel_ids: list[str] = []
    try:
        tunnels_response = mcp.call_tool("infrastructure", "cloudflare_list_tunnels",
                                          {"params": {"response_format": "json"}})
        tunnels = extract_list(tunnels_response, "tunnels", "result")

        for tunnel in tunnels:
            tunnel_id = tunnel.get("id", "")
            tunnel_name = tunnel.get("name", "")
            status = tunnel.get("status", "unknown")
            if not tunnel_id:
                continue

            neo4j.write("""
            MERGE (t:CloudflareTunnel {tunnel_id: $tunnel_id})
            SET t.name = $name,
                t.status = $status,
                t.last_seen = datetime(),
                t.source = 'cloudflare',
                t._sync_status = 'active'
            """, {"tunnel_id": tunnel_id, "name": tunnel_name, "status": status})
            tunnel_count += 1
            tunnel_ids.append(tunnel_id)

        # Link: DNSRecord (CNAME) -[:POINTS_TO]-> CloudflareTunnel
        if tunnel_ids:
            neo4j.write("""
            MATCH (d:DNSRecord {source: 'cloudflare'})
            WHERE d.record_type = 'CNAME' AND d.answer CONTAINS '.cfargotunnel.com'
            MATCH (t:CloudflareTunnel)
            WHERE d.answer CONTAINS t.tunnel_id
            MERGE (d)-[:POINTS_TO]->(t)
            """)

    except Exception as e:
        logger.warning(f"  Cloudflare tunnels unavailable: {e}")

    if dns_domains:
        mark_active(neo4j, "DNSRecord", dns_domains, id_field="domain")
    if tunnel_ids:
        mark_active(neo4j, "CloudflareTunnel", tunnel_ids, id_field="tunnel_id")

    # Phase 0: CNAME chain resolution
    # Link CNAMEs to their target DNS records (enables tracing resolution chains)
    try:
        neo4j.write("""
        MATCH (dns:DNSRecord {source: 'cloudflare'})
        WHERE dns.record_type = 'CNAME' AND dns._sync_status = 'active'
        MATCH (target:DNSRecord {domain: dns.answer})
        WHERE NOT (dns)-[:RESOLVES_TO]->(target)
        MERGE (dns)-[:RESOLVES_TO]->(target)
        """)
        logger.debug("  CNAME chain resolution complete")
    except Exception as e:
        logger.warning(f"  CNAME chain resolution failed: {e}")

    # Phase 0: DNS -> Ingress -> Service linking
    # Link A/CNAME records to Ingress resources by hostname match
    # Note: i.hosts is stored as a string (not array) in our schema
    try:
        neo4j.write("""
        MATCH (dns:DNSRecord)
        WHERE dns._sync_status = 'active' AND dns.record_type IN ['A', 'CNAME']
        MATCH (i:Ingress)
        WHERE i._sync_status = 'active'
          AND (dns.hostname = i.hosts OR dns.hostname = i.host)
        MERGE (dns)-[:ROUTES_TO]->(i)
        """)

        # Ensure Ingress -> Service links exist (belt and suspenders)
        neo4j.write("""
        MATCH (i:Ingress)
        WHERE i._sync_status = 'active' AND NOT (i)-[:BACKENDS_TO]->()
        MATCH (s:Service {name: i.service_name, namespace: i.namespace, cluster: i.cluster})
        WHERE s._sync_status = 'active'
        MERGE (i)-[:BACKENDS_TO]->(s)
        """)
        logger.debug("  DNS -> Ingress -> Service linking complete")
    except Exception as e:
        logger.warning(f"  DNS -> Ingress linking failed: {e}")

    logger.info(f"Synced {count} Cloudflare DNS records, {tunnel_count} tunnels")
    return count + tunnel_count
