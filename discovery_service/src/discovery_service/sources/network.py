"""Sync UniFi devices and DNS topology to Neo4j."""

import logging

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
