#!/usr/bin/env python3
"""Knowledge MCP server for Qdrant vector database operations."""
import os
import logging
import httpx
from typing import List, Optional
from datetime import datetime, timezone
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embeddings")

mcp = FastMCP(
    name="knowledge-mcp",
    instructions="""
    MCP server for knowledge base operations.
    Provides semantic search across runbooks, decisions, documentation, and network entities.

    ENTITY TOOLS (Network Intelligence):
    - search_entities: Semantic search for any device/resource on the network
    - get_entity: Lookup by IP, MAC, or hostname
    - get_entities_by_type: Filter by device type (sonoff, chromecast, nas, etc.)
    - get_entities_by_network: Filter by network/VLAN
    - get_device_type_info: Get control methods for a device type
    - update_entity: Update entity metadata after actions

    KNOWLEDGE TOOLS:
    - search_runbooks, search_decisions, search_documentation: Find relevant information
    - add_runbook, add_decision: Store new knowledge
    - get_similar_events: Pattern matching for events
    """
)


class SearchResult(BaseModel):
    id: str
    score: float
    title: str
    content: str
    metadata: dict


class RunbookInfo(BaseModel):
    id: str
    title: str
    trigger_pattern: str
    solution: str
    success_rate: float
    automation_level: str


class EntityResult(BaseModel):
    """Network entity with full details."""
    id: str
    score: float = 0.0
    ip: str
    mac: str = ""
    hostname: str = ""
    category: str = ""  # infrastructure, compute, storage, endpoint, iot, media, peripheral
    type: str = ""  # router, vm, nas, switch, chromecast, sonoff, printer, etc.
    manufacturer: str = ""
    model: str = ""
    location: str = ""
    function: str = ""
    network: str = ""
    status: str = "unknown"
    interfaces: List[dict] = []  # Control methods
    capabilities: List[str] = []
    discovered_via: List[str] = []
    last_seen: str = ""


class DeviceTypeInfo(BaseModel):
    """Device type knowledge - how to control a type of device."""
    id: str
    name: str
    description: str
    category: str = ""
    manufacturers: List[str] = []
    protocols: List[str] = []
    discovery_methods: List[str] = []
    control_api: dict = {}  # Command templates
    default_credentials_path: str = ""


async def get_embedding(text: str) -> List[float]:
    """Get embedding vector from LiteLLM (Gemini text-embedding-004)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{LITELLM_URL}/v1/embeddings",
            json={"model": EMBEDDING_MODEL, "input": text}
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


async def qdrant_search(
    collection: str,
    vector: List[float],
    limit: int = 5,
    filter_conditions: dict = None
) -> List[dict]:
    """Search Qdrant collection."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "vector": vector,
            "limit": limit,
            "with_payload": True
        }
        if filter_conditions:
            payload["filter"] = filter_conditions

        response = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/search",
            json=payload
        )
        response.raise_for_status()
        return response.json().get("result", [])


async def qdrant_upsert(collection: str, points: List[dict]) -> bool:
    """Upsert points to Qdrant collection."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(
            f"{QDRANT_URL}/collections/{collection}/points",
            json={"points": points}
        )
        return response.status_code == 200


async def qdrant_scroll(
    collection: str,
    filter_conditions: dict = None,
    limit: int = 100
) -> List[dict]:
    """Scroll through Qdrant collection with optional filter."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "limit": limit,
            "with_payload": True,
            "with_vector": False
        }
        if filter_conditions:
            payload["filter"] = filter_conditions

        response = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            json=payload
        )
        response.raise_for_status()
        return response.json().get("result", {}).get("points", [])


async def qdrant_get_by_id(collection: str, point_id: str) -> Optional[dict]:
    """Get a single point by ID."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{QDRANT_URL}/collections/{collection}/points/{point_id}"
        )
        if response.status_code == 200:
            return response.json().get("result")
        return None


async def qdrant_delete_points(collection: str, point_ids: List[str]) -> bool:
    """Delete points by IDs from a Qdrant collection."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/delete",
            json={"points": point_ids}
        )
        return response.status_code == 200


def payload_to_entity(point: dict) -> EntityResult:
    """Convert Qdrant point to EntityResult."""
    payload = point.get("payload", {})
    return EntityResult(
        id=str(point.get("id", "")),
        score=point.get("score", 0.0),
        ip=payload.get("ip", ""),
        mac=payload.get("mac", ""),
        hostname=payload.get("hostname", ""),
        category=payload.get("category", ""),
        type=payload.get("type", ""),
        manufacturer=payload.get("manufacturer", ""),
        model=payload.get("model", ""),
        location=payload.get("location", ""),
        function=payload.get("function", ""),
        network=payload.get("network", ""),
        status=payload.get("status", "unknown"),
        interfaces=payload.get("interfaces", []),
        capabilities=payload.get("capabilities", []),
        discovered_via=payload.get("discovered_via", []),
        last_seen=payload.get("last_seen", "")
    )


def payload_to_device_type(point: dict) -> DeviceTypeInfo:
    """Convert Qdrant point to DeviceTypeInfo."""
    payload = point.get("payload", {})
    return DeviceTypeInfo(
        id=str(point.get("id", "")),
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        category=payload.get("category", ""),
        manufacturers=payload.get("manufacturers", []),
        protocols=payload.get("protocols", []),
        discovery_methods=payload.get("discovery_methods", []),
        control_api=payload.get("control_api", {}),
        default_credentials_path=payload.get("default_credentials_path", "")
    )


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


@mcp.tool()
async def search_runbooks(
    query: str,
    limit: int = 5,
    min_score: float = 0.7
) -> List[SearchResult]:
    """
    Search runbooks for solutions to issues.

    Args:
        query: Natural language search query
        limit: Maximum results to return (default: 5)
        min_score: Minimum similarity score (default: 0.7)

    Returns:
        List of matching runbooks with similarity scores
    """
    try:
        vector = await get_embedding(query)
        results = await qdrant_search("runbooks", vector, limit=limit)

        matches = []
        for result in results:
            if result.get("score", 0) >= min_score:
                payload = result.get("payload", {})
                matches.append(SearchResult(
                    id=str(result.get("id", "")),
                    score=result.get("score", 0),
                    title=payload.get("title", "Untitled"),
                    content=payload.get("solution", ""),
                    metadata={
                        "trigger_pattern": payload.get("trigger_pattern", ""),
                        "automation_level": payload.get("automation_level", "manual"),
                        "success_rate": payload.get("success_rate", 0)
                    }
                ))
        return matches
    except Exception as e:
        logger.error(f"Runbook search failed: {e}")
        return []


@mcp.tool()
async def search_decisions(
    query: str,
    limit: int = 5,
    decision_type: Optional[str] = None
) -> List[SearchResult]:
    """
    Search historical decisions and their outcomes.

    Args:
        query: Natural language search query
        limit: Maximum results to return (default: 5)
        decision_type: Filter by type (approved, rejected, modified)

    Returns:
        List of matching decisions with context
    """
    try:
        vector = await get_embedding(query)
        filter_conditions = None
        if decision_type:
            filter_conditions = {
                "must": [{"key": "decision_type", "match": {"value": decision_type}}]
            }

        results = await qdrant_search("decisions", vector, limit=limit, filter_conditions=filter_conditions)

        matches = []
        for result in results:
            payload = result.get("payload", {})
            matches.append(SearchResult(
                id=str(result.get("id", "")),
                score=result.get("score", 0),
                title=payload.get("title", "Untitled"),
                content=payload.get("description", ""),
                metadata={
                    "decision_type": payload.get("decision_type", "unknown"),
                    "timestamp": payload.get("timestamp", ""),
                    "outcome": payload.get("outcome", "")
                }
            ))
        return matches
    except Exception as e:
        logger.error(f"Decision search failed: {e}")
        return []


@mcp.tool()
async def search_documentation(
    query: str,
    limit: int = 5,
    doc_type: Optional[str] = None
) -> List[SearchResult]:
    """
    Search documentation for information.

    Args:
        query: Natural language search query
        limit: Maximum results to return (default: 5)
        doc_type: Filter by type (architecture, guide, reference)

    Returns:
        List of matching documentation sections
    """
    try:
        vector = await get_embedding(query)
        filter_conditions = None
        if doc_type:
            filter_conditions = {
                "must": [{"key": "doc_type", "match": {"value": doc_type}}]
            }

        results = await qdrant_search("documentation", vector, limit=limit, filter_conditions=filter_conditions)

        matches = []
        for result in results:
            payload = result.get("payload", {})
            matches.append(SearchResult(
                id=str(result.get("id", "")),
                score=result.get("score", 0),
                title=payload.get("title", "Untitled"),
                content=payload.get("content", ""),
                metadata={
                    "doc_type": payload.get("doc_type", "general"),
                    "source": payload.get("source", ""),
                    "last_updated": payload.get("last_updated", "")
                }
            ))
        return matches
    except Exception as e:
        logger.error(f"Documentation search failed: {e}")
        return []


@mcp.tool()
async def add_runbook(
    title: str,
    trigger_pattern: str,
    solution: str,
    automation_level: str = "manual"
) -> dict:
    """
    Add a new runbook to the knowledge base.

    Args:
        title: Runbook title
        trigger_pattern: Regex pattern that triggers this runbook
        solution: Step-by-step solution
        automation_level: One of: manual, prompted, standard

    Returns:
        Status of the operation
    """
    try:
        import uuid
        point_id = str(uuid.uuid4())

        # Create combined text for embedding
        combined_text = f"{title}\n{trigger_pattern}\n{solution}"
        vector = await get_embedding(combined_text)

        point = {
            "id": point_id,
            "vector": vector,
            "payload": {
                "title": title,
                "trigger_pattern": trigger_pattern,
                "solution": solution,
                "automation_level": automation_level,
                "success_rate": 0.0,
                "execution_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        }

        success = await qdrant_upsert("runbooks", [point])
        return {"success": success, "id": point_id}
    except Exception as e:
        logger.error(f"Add runbook failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def add_decision(
    title: str,
    description: str,
    decision_type: str,
    outcome: Optional[str] = None,
    context: Optional[dict] = None
) -> dict:
    """
    Record a decision for learning.

    Args:
        title: Decision title
        description: What was decided
        decision_type: One of: approved, rejected, modified
        outcome: Result of the decision (if known)
        context: Additional context metadata

    Returns:
        Status of the operation
    """
    try:
        import uuid
        point_id = str(uuid.uuid4())

        combined_text = f"{title}\n{description}\n{decision_type}"
        if outcome:
            combined_text += f"\n{outcome}"
        vector = await get_embedding(combined_text)

        point = {
            "id": point_id,
            "vector": vector,
            "payload": {
                "title": title,
                "description": description,
                "decision_type": decision_type,
                "outcome": outcome or "",
                "context": context or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

        success = await qdrant_upsert("decisions", [point])
        return {"success": success, "id": point_id}
    except Exception as e:
        logger.error(f"Add decision failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_similar_events(
    event_description: str,
    limit: int = 5,
    min_score: float = 0.75
) -> List[SearchResult]:
    """
    Find similar historical events for pattern matching.

    Args:
        event_description: Description of the current event
        limit: Maximum results to return (default: 5)
        min_score: Minimum similarity score (default: 0.75)

    Returns:
        List of similar past events
    """
    try:
        vector = await get_embedding(event_description)
        results = await qdrant_search("agent_events", vector, limit=limit)

        matches = []
        for result in results:
            if result.get("score", 0) >= min_score:
                payload = result.get("payload", {})
                matches.append(SearchResult(
                    id=str(result.get("id", "")),
                    score=result.get("score", 0),
                    title=payload.get("event_type", "Unknown Event"),
                    content=payload.get("description", ""),
                    metadata={
                        "source": payload.get("source", ""),
                        "resolution": payload.get("resolution", ""),
                        "timestamp": payload.get("timestamp", "")
                    }
                ))
        return matches
    except Exception as e:
        logger.error(f"Similar events search failed: {e}")
        return []


# ============================================================
# ENTITY TOOLS - Network Device Intelligence
# ============================================================

@mcp.tool()
async def search_entities(
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
    network: Optional[str] = None
) -> List[EntityResult]:
    """
    Semantic search for network entities (devices, VMs, services, etc.).

    Args:
        query: Natural language search query (e.g., "all Chromecast devices",
               "IoT devices on guest WiFi", "storage servers")
        limit: Maximum results to return (default: 10)
        category: Optional filter by category (infrastructure, compute, storage,
                  endpoint, iot, media, peripheral)
        network: Optional filter by network (e.g., "prod", "iot-vlan")

    Returns:
        List of matching entities with full details
    """
    try:
        vector = await get_embedding(query)

        filter_conditions = None
        must_conditions = []
        if category:
            must_conditions.append({"key": "category", "match": {"value": category}})
        if network:
            must_conditions.append({"key": "network", "match": {"value": network}})
        if must_conditions:
            filter_conditions = {"must": must_conditions}

        results = await qdrant_search("entities", vector, limit=limit, filter_conditions=filter_conditions)

        return [payload_to_entity(r) for r in results]
    except Exception as e:
        logger.error(f"Entity search failed: {e}")
        return []


@mcp.tool()
async def get_entity(identifier: str) -> Optional[EntityResult]:
    """
    Get a specific entity by IP address, MAC address, or hostname.

    Args:
        identifier: IP address, MAC address, or hostname

    Returns:
        Entity details or None if not found
    """
    try:
        # Normalize identifier
        identifier = identifier.strip().lower()

        # Try each field type
        for field in ["ip", "mac", "hostname"]:
            filter_conditions = {
                "must": [{"key": field, "match": {"value": identifier}}]
            }
            results = await qdrant_scroll("entities", filter_conditions, limit=1)
            if results:
                return payload_to_entity(results[0])

        # Also try case-insensitive MAC (with colons normalized)
        if ":" in identifier or "-" in identifier:
            mac_normalized = identifier.replace("-", ":").upper()
            filter_conditions = {
                "must": [{"key": "mac", "match": {"value": mac_normalized}}]
            }
            results = await qdrant_scroll("entities", filter_conditions, limit=1)
            if results:
                return payload_to_entity(results[0])

        return None
    except Exception as e:
        logger.error(f"Get entity failed: {e}")
        return None


@mcp.tool()
async def get_entities_by_type(
    entity_type: str,
    limit: int = 100
) -> List[EntityResult]:
    """
    Get all entities of a specific type.

    Args:
        entity_type: Device type (e.g., "sonoff", "chromecast", "nas", "printer",
                     "vm", "router", "switch", "access_point")
        limit: Maximum results (default: 100)

    Returns:
        List of entities of that type
    """
    try:
        filter_conditions = {
            "must": [{"key": "type", "match": {"value": entity_type.lower()}}]
        }
        results = await qdrant_scroll("entities", filter_conditions, limit=limit)
        return [payload_to_entity(r) for r in results]
    except Exception as e:
        logger.error(f"Get entities by type failed: {e}")
        return []


@mcp.tool()
async def get_entities_by_network(
    network: str,
    limit: int = 100
) -> List[EntityResult]:
    """
    Get all entities on a specific network or VLAN.

    Args:
        network: Network name (e.g., "prod", "agentic", "monit", "iot-vlan", "guest")
        limit: Maximum results (default: 100)

    Returns:
        List of entities on that network
    """
    try:
        filter_conditions = {
            "must": [{"key": "network", "match": {"value": network.lower()}}]
        }
        results = await qdrant_scroll("entities", filter_conditions, limit=limit)
        return [payload_to_entity(r) for r in results]
    except Exception as e:
        logger.error(f"Get entities by network failed: {e}")
        return []


@mcp.tool()
async def get_device_type_info(device_type: str) -> Optional[DeviceTypeInfo]:
    """
    Get control methods and API information for a device type.

    Args:
        device_type: Type name (e.g., "tasmota", "shelly", "chromecast",
                     "synology", "proxmox", "unifi_ap")

    Returns:
        Device type info including control API commands, protocols, and credentials path
    """
    try:
        # First try exact match
        filter_conditions = {
            "must": [{"key": "name", "match": {"value": device_type.lower()}}]
        }
        results = await qdrant_scroll("device_types", filter_conditions, limit=1)
        if results:
            return payload_to_device_type(results[0])

        # Try semantic search as fallback
        vector = await get_embedding(f"device type: {device_type}")
        results = await qdrant_search("device_types", vector, limit=1)
        if results and results[0].get("score", 0) > 0.75:
            return payload_to_device_type(results[0])

        return None
    except Exception as e:
        logger.error(f"Get device type info failed: {e}")
        return None


@mcp.tool()
async def update_entity(
    identifier: str,
    updates: dict
) -> dict:
    """
    Update entity metadata after performing actions or learning new info.

    Args:
        identifier: IP address, MAC address, or hostname
        updates: Dictionary of fields to update (e.g., {"status": "offline",
                 "location": "living_room", "function": "media streaming"})

    Returns:
        Status of the operation
    """
    try:
        # Find the entity first
        entity = await get_entity(identifier)
        if not entity:
            return {"success": False, "error": f"Entity not found: {identifier}"}

        # Get current point
        point = await qdrant_get_by_id("entities", entity.id)
        if not point:
            return {"success": False, "error": f"Could not retrieve entity point"}

        # Merge updates into payload
        payload = point.get("payload", {})
        for key, value in updates.items():
            payload[key] = value

        # Regenerate description and embedding
        description_parts = []
        if payload.get("manufacturer"):
            description_parts.append(payload["manufacturer"])
        if payload.get("model"):
            description_parts.append(payload["model"])
        if payload.get("type"):
            description_parts.append(payload["type"])
        if payload.get("location"):
            description_parts.append(f"in {payload['location']}")
        if payload.get("function"):
            description_parts.append(payload["function"])
        if payload.get("network"):
            description_parts.append(f"on {payload['network']} network")
        if payload.get("ip"):
            description_parts.append(f"at {payload['ip']}")

        description = " ".join(description_parts)
        vector = await get_embedding(description)

        # Update point
        updated_point = {
            "id": entity.id,
            "vector": vector,
            "payload": payload
        }

        success = await qdrant_upsert("entities", [updated_point])
        return {"success": success, "id": entity.id}
    except Exception as e:
        logger.error(f"Update entity failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def add_entity(
    ip: str,
    entity_type: str,
    category: str,
    hostname: str = "",
    mac: str = "",
    manufacturer: str = "",
    model: str = "",
    location: str = "",
    function: str = "",
    network: str = "",
    interfaces: List[dict] = None,
    capabilities: List[str] = None
) -> dict:
    """
    Add a new entity to the knowledge base.

    Args:
        ip: IP address (required)
        entity_type: Type (e.g., "sonoff", "chromecast", "vm", "nas")
        category: Category (infrastructure, compute, storage, endpoint, iot, media, peripheral)
        hostname: Hostname
        mac: MAC address
        manufacturer: Manufacturer name
        model: Model name
        location: Physical location (e.g., "living_room", "rack1")
        function: What it does (e.g., "media streaming", "network storage")
        network: Network name (e.g., "prod", "iot-vlan")
        interfaces: List of control interfaces (e.g., [{"type": "http", "port": 80}])
        capabilities: List of capabilities (e.g., ["power_control", "dimming"])

    Returns:
        Status and entity ID
    """
    try:
        import uuid
        point_id = str(uuid.uuid4())

        # Build description for embedding
        description_parts = [manufacturer, model, entity_type]
        if location:
            description_parts.append(f"in {location}")
        if function:
            description_parts.append(function)
        if network:
            description_parts.append(f"on {network} network")
        description_parts.append(f"at {ip}")

        description = " ".join(filter(None, description_parts))
        vector = await get_embedding(description)

        payload = {
            "ip": ip,
            "mac": mac.upper() if mac else "",
            "hostname": hostname,
            "category": category,
            "type": entity_type.lower(),
            "manufacturer": manufacturer,
            "model": model,
            "location": location,
            "function": function,
            "network": network,
            "status": "online",
            "interfaces": interfaces or [],
            "capabilities": capabilities or [],
            "discovered_via": ["manual"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat()
        }

        point = {
            "id": point_id,
            "vector": vector,
            "payload": payload
        }

        success = await qdrant_upsert("entities", [point])
        return {"success": success, "id": point_id}
    except Exception as e:
        logger.error(f"Add entity failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_entity(entity_id: str) -> dict:
    """
    Delete an entity by its ID.

    Args:
        entity_id: The UUID of the entity to delete

    Returns:
        Status of the operation
    """
    try:
        success = await qdrant_delete_points("entities", [entity_id])
        return {"success": success, "id": entity_id}
    except Exception as e:
        logger.error(f"Delete entity failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_entities_by_ip(ip: str) -> dict:
    """
    Delete all entities matching an IP address. Useful for cleaning up duplicates.

    Args:
        ip: IP address to match

    Returns:
        Status with count of deleted entities
    """
    try:
        # Find all entities with this IP
        filter_conditions = {
            "must": [{"key": "ip", "match": {"value": ip}}]
        }
        results = await qdrant_scroll("entities", filter_conditions, limit=100)

        if not results:
            return {"success": True, "deleted": 0, "message": f"No entities found with IP {ip}"}

        # Get all IDs
        entity_ids = [str(r.get("id", "")) for r in results if r.get("id")]

        if entity_ids:
            success = await qdrant_delete_points("entities", entity_ids)
            return {"success": success, "deleted": len(entity_ids), "ids": entity_ids}

        return {"success": True, "deleted": 0}
    except Exception as e:
        logger.error(f"Delete entities by IP failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def list_entity_types() -> List[dict]:
    """
    List all unique entity types with their counts.

    Returns:
        List of {type: str, count: int} entries
    """
    try:
        # Scroll through all entities and count types
        all_points = await qdrant_scroll("entities", limit=1000)

        type_counts = {}
        for point in all_points:
            entity_type = point.get("payload", {}).get("type", "unknown")
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

        # Sort by count descending
        result = [{"type": t, "count": c} for t, c in sorted(type_counts.items(), key=lambda x: -x[1])]
        return result
    except Exception as e:
        logger.error(f"List entity types failed: {e}")
        return []


def main():
    port = int(os.environ.get("PORT", "8000"))
    transport = os.environ.get("MCP_TRANSPORT", "sse")

    logger.info(f"Starting knowledge MCP server on port {port} with {transport} transport")

    if transport == "http":
        from starlette.middleware.cors import CORSMiddleware
        app = mcp.streamable_http_app()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
