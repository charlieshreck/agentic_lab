"""Sync media app operational state onto existing Service nodes in Neo4j."""

import logging

from discovery_service.graph.client import Neo4jClient
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_media_state(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Enrich existing Service nodes with media app operational properties.

    No new node types — sets app_status, queue_count, monitored_count,
    active_sessions, and active_downloads on matched Service nodes.
    Each media app is independently try/excepted so one failure doesn't
    block others.
    """
    logger.info("Syncing media app state...")
    updated = 0

    # --- Sonarr ---
    try:
        queue_resp = mcp.call_tool("media", "sonarr_get_queue")
        queue = extract_list(queue_resp, "records", "result", "queue")
        queue_count = len(queue) if queue else 0

        series_resp = mcp.call_tool("media", "sonarr_list_series")
        series = extract_list(series_resp, "series", "result")
        monitored = sum(1 for s in series if s.get("monitored")) if series else 0

        _set_service_state(neo4j, "sonarr", {
            "app_status": "running",
            "queue_count": queue_count,
            "monitored_count": monitored,
        })
        updated += 1
        logger.debug(f"Sonarr: queue={queue_count}, monitored={monitored}")
    except Exception as e:
        logger.warning(f"Sonarr state sync failed: {e}")

    # --- Radarr ---
    try:
        queue_resp = mcp.call_tool("media", "radarr_get_queue")
        queue = extract_list(queue_resp, "records", "result", "queue")
        queue_count = len(queue) if queue else 0

        movies_resp = mcp.call_tool("media", "radarr_list_movies")
        movies = extract_list(movies_resp, "movies", "result")
        monitored = sum(1 for m in movies if m.get("monitored")) if movies else 0

        _set_service_state(neo4j, "radarr", {
            "app_status": "running",
            "queue_count": queue_count,
            "monitored_count": monitored,
        })
        updated += 1
        logger.debug(f"Radarr: queue={queue_count}, monitored={monitored}")
    except Exception as e:
        logger.warning(f"Radarr state sync failed: {e}")

    # --- Plex ---
    try:
        sessions_resp = mcp.call_tool("media", "plex_get_active_sessions")
        sessions = extract_list(sessions_resp, "sessions", "result")
        active_sessions = len(sessions) if sessions else 0

        libraries_resp = mcp.call_tool("media", "plex_list_libraries")
        libraries = extract_list(libraries_resp, "libraries", "result")
        library_count = len(libraries) if libraries else 0

        _set_service_state(neo4j, "plex", {
            "app_status": "running",
            "active_sessions": active_sessions,
            "library_count": library_count,
        })
        updated += 1
        logger.debug(f"Plex: sessions={active_sessions}, libraries={library_count}")
    except Exception as e:
        logger.warning(f"Plex state sync failed: {e}")

    # --- Transmission ---
    try:
        torrents_resp = mcp.call_tool("media", "transmission_list_torrents")
        torrents = extract_list(torrents_resp, "torrents", "result")
        active_downloads = (
            sum(1 for t in torrents if t.get("status") in ("downloading", 4))
            if torrents else 0
        )

        _set_service_state(neo4j, "transmission", {
            "app_status": "running",
            "active_downloads": active_downloads,
            "total_torrents": len(torrents) if torrents else 0,
        })
        updated += 1
        logger.debug(f"Transmission: active={active_downloads}")
    except Exception as e:
        logger.warning(f"Transmission state sync failed: {e}")

    # --- SABnzbd ---
    try:
        # SABnzbd may return a flat response (not wrapped in "result")
        queue_resp = mcp.call_tool("media", "sabnzbd_get_queue")
        if isinstance(queue_resp, dict):
            queue_data = queue_resp.get("result", queue_resp)
            slots = queue_data.get("slots", queue_data.get("queue", {}).get("slots", []))
        else:
            slots = []
        active_downloads = len(slots) if slots else 0

        _set_service_state(neo4j, "sabnzbd", {
            "app_status": "running",
            "active_downloads": active_downloads,
        })
        updated += 1
        logger.debug(f"SABnzbd: queue={active_downloads}")
    except Exception as e:
        logger.warning(f"SABnzbd state sync failed: {e}")

    logger.info(f"Media state sync complete: {updated} services updated")
    return updated


def _set_service_state(neo4j: Neo4jClient, service_name: str, props: dict):
    """Set operational properties on an existing Service node by name match."""
    set_clauses = ", ".join(f"s.{k} = ${k}" for k in props)
    neo4j.write(
        f"""
        MATCH (s:Service)
        WHERE toLower(s.name) CONTAINS $name
        SET {set_clauses}, s.media_sync_at = datetime()
        """,
        {"name": service_name, **props},
    )
