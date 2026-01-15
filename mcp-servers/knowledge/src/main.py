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


# Valid autonomy levels for runbooks
AUTONOMY_LEVELS = {
    "manual": {
        "confidence_threshold": 0.0,
        "requires_approval": True,
        "timeout_auto_approve": None,
        "notify_human": True,
        "description": "Always requires human approval"
    },
    "prompted": {
        "confidence_threshold": 0.7,
        "requires_approval": True,
        "timeout_auto_approve": 300,  # Auto-approve after 5 min
        "notify_human": True,
        "description": "Prompts human, auto-approves if no response"
    },
    "standard": {
        "confidence_threshold": 0.85,
        "requires_approval": False,
        "timeout_auto_approve": None,
        "notify_human": True,
        "description": "Executes automatically, notifies human"
    },
    "autonomous": {
        "confidence_threshold": 0.95,
        "requires_approval": False,
        "timeout_auto_approve": None,
        "notify_human": False,
        "description": "Fully autonomous, logged only"
    }
}


@mcp.tool()
async def get_runbook(runbook_id: str) -> Optional[dict]:
    """
    Get a specific runbook by ID.

    Args:
        runbook_id: UUID of the runbook

    Returns:
        Runbook details or None if not found
    """
    try:
        point = await qdrant_get_by_id("runbooks", runbook_id)
        if not point:
            return None
        payload = point.get("payload", {})
        payload["id"] = runbook_id
        return payload
    except Exception as e:
        logger.error(f"Get runbook failed: {e}")
        return None


@mcp.tool()
async def update_runbook(
    runbook_id: str,
    automation_level: Optional[str] = None,
    success_rate: Optional[float] = None,
    execution_count: Optional[int] = None,
    success_count: Optional[int] = None,
    avg_resolution_time: Optional[int] = None
) -> dict:
    """
    Update runbook metadata including autonomy level and execution stats.

    Used by the autonomy system to track runbook performance and
    automatically upgrade/downgrade autonomy levels based on success rates.

    Args:
        runbook_id: UUID of the runbook to update
        automation_level: New autonomy level (manual, prompted, standard, autonomous)
        success_rate: Updated success rate (0.0-1.0)
        execution_count: Total number of executions
        success_count: Number of successful executions
        avg_resolution_time: Average resolution time in seconds

    Returns:
        Status of the update operation
    """
    try:
        # Validate autonomy level if provided
        if automation_level and automation_level not in AUTONOMY_LEVELS:
            return {
                "success": False,
                "error": f"Invalid autonomy level: {automation_level}. "
                         f"Valid levels: {list(AUTONOMY_LEVELS.keys())}"
            }

        # Get existing runbook
        point = await qdrant_get_by_id("runbooks", runbook_id)
        if not point:
            return {"success": False, "error": f"Runbook not found: {runbook_id}"}

        payload = point.get("payload", {})

        # Update fields if provided
        if automation_level is not None:
            old_level = payload.get("automation_level", "manual")
            payload["automation_level"] = automation_level
            # Log autonomy change
            if old_level != automation_level:
                logger.info(f"Runbook {runbook_id} autonomy: {old_level} -> {automation_level}")

        if success_rate is not None:
            if not 0.0 <= success_rate <= 1.0:
                return {"success": False, "error": "success_rate must be between 0.0 and 1.0"}
            payload["success_rate"] = success_rate

        if execution_count is not None:
            payload["execution_count"] = execution_count

        if success_count is not None:
            payload["success_count"] = success_count

        if avg_resolution_time is not None:
            payload["avg_resolution_time"] = avg_resolution_time

        payload["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Regenerate embedding if title/solution changed (not in this case, but future-proof)
        combined_text = f"{payload.get('title', '')}\n{payload.get('trigger_pattern', '')}\n{payload.get('solution', '')}"
        vector = await get_embedding(combined_text)

        updated_point = {
            "id": runbook_id,
            "vector": vector,
            "payload": payload
        }

        success = await qdrant_upsert("runbooks", [updated_point])
        return {"success": success, "id": runbook_id}
    except Exception as e:
        logger.error(f"Update runbook failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def record_runbook_execution(
    runbook_id: str,
    success: bool,
    resolution_time: Optional[int] = None
) -> dict:
    """
    Record a runbook execution and update statistics.

    Convenience method that updates execution_count, success_count, and success_rate
    in a single call. Used after executing a runbook to track its effectiveness.

    Args:
        runbook_id: UUID of the executed runbook
        success: Whether the execution was successful
        resolution_time: Time to resolution in seconds (optional)

    Returns:
        Updated runbook stats and any autonomy level changes
    """
    try:
        # Get existing runbook
        point = await qdrant_get_by_id("runbooks", runbook_id)
        if not point:
            return {"success": False, "error": f"Runbook not found: {runbook_id}"}

        payload = point.get("payload", {})

        # Update counts
        execution_count = payload.get("execution_count", 0) + 1
        success_count = payload.get("success_count", 0) + (1 if success else 0)
        success_rate = success_count / execution_count if execution_count > 0 else 0.0

        # Update average resolution time
        avg_resolution_time = payload.get("avg_resolution_time", 0)
        if resolution_time is not None:
            old_total = avg_resolution_time * (execution_count - 1)
            avg_resolution_time = int((old_total + resolution_time) / execution_count)

        payload["execution_count"] = execution_count
        payload["success_count"] = success_count
        payload["success_rate"] = success_rate
        payload["avg_resolution_time"] = avg_resolution_time
        payload["last_executed"] = datetime.now(timezone.utc).isoformat()

        # Check for autonomy level upgrade eligibility
        current_level = payload.get("automation_level", "manual")
        suggested_upgrade = None

        if execution_count >= 10:  # Minimum executions for upgrade consideration
            for level_name, level_config in AUTONOMY_LEVELS.items():
                if success_rate >= level_config["confidence_threshold"]:
                    if level_name != current_level:
                        # Check if this is actually an upgrade
                        level_order = ["manual", "prompted", "standard", "autonomous"]
                        if level_order.index(level_name) > level_order.index(current_level):
                            suggested_upgrade = level_name

        # Regenerate embedding
        combined_text = f"{payload.get('title', '')}\n{payload.get('trigger_pattern', '')}\n{payload.get('solution', '')}"
        vector = await get_embedding(combined_text)

        updated_point = {
            "id": runbook_id,
            "vector": vector,
            "payload": payload
        }

        upsert_success = await qdrant_upsert("runbooks", [updated_point])

        result = {
            "success": upsert_success,
            "id": runbook_id,
            "execution_count": execution_count,
            "success_count": success_count,
            "success_rate": success_rate,
            "current_level": current_level
        }

        if suggested_upgrade:
            result["suggested_upgrade"] = suggested_upgrade
            result["upgrade_reason"] = f"Success rate {success_rate:.0%} exceeds threshold for {suggested_upgrade}"

        return result
    except Exception as e:
        logger.error(f"Record runbook execution failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_autonomy_config(level: str) -> Optional[dict]:
    """
    Get the configuration for an autonomy level.

    Args:
        level: Autonomy level name (manual, prompted, standard, autonomous)

    Returns:
        Level configuration including thresholds and approval requirements
    """
    if level not in AUTONOMY_LEVELS:
        return None
    return {"level": level, **AUTONOMY_LEVELS[level]}


@mcp.tool()
async def list_autonomy_candidates(
    min_executions: int = 10,
    min_success_rate: float = 0.9
) -> List[dict]:
    """
    List runbooks eligible for autonomy upgrade.

    Finds runbooks that meet the criteria for upgrading to a higher autonomy level
    based on their execution history and success rate.

    Args:
        min_executions: Minimum number of executions required (default: 10)
        min_success_rate: Minimum success rate required (default: 0.9)

    Returns:
        List of runbooks with upgrade suggestions
    """
    try:
        results = await qdrant_scroll("runbooks", limit=200)

        candidates = []
        level_order = ["manual", "prompted", "standard", "autonomous"]

        for point in results:
            payload = point.get("payload", {})
            execution_count = payload.get("execution_count", 0)
            success_rate = payload.get("success_rate", 0.0)
            current_level = payload.get("automation_level", "manual")

            if execution_count < min_executions or success_rate < min_success_rate:
                continue

            # Find the highest eligible level
            eligible_level = current_level
            for level_name, level_config in AUTONOMY_LEVELS.items():
                if success_rate >= level_config["confidence_threshold"]:
                    if level_order.index(level_name) > level_order.index(eligible_level):
                        eligible_level = level_name

            if eligible_level != current_level:
                candidates.append({
                    "id": str(point.get("id", "")),
                    "title": payload.get("title", ""),
                    "current_level": current_level,
                    "suggested_level": eligible_level,
                    "success_rate": success_rate,
                    "execution_count": execution_count,
                    "threshold": AUTONOMY_LEVELS[eligible_level]["confidence_threshold"]
                })

        return candidates
    except Exception as e:
        logger.error(f"List autonomy candidates failed: {e}")
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
        automation_level: One of: manual, prompted, standard, autonomous

    Returns:
        Status of the operation
    """
    try:
        import uuid

        # Validate autonomy level
        if automation_level not in AUTONOMY_LEVELS:
            return {
                "success": False,
                "error": f"Invalid autonomy level: {automation_level}. "
                         f"Valid levels: {list(AUTONOMY_LEVELS.keys())}"
            }

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
                "success_count": 0,
                "execution_count": 0,
                "avg_resolution_time": 0,
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
# EVENT LOGGING TOOLS - Forever Learning System
# ============================================================

# Valid event types for the learning system
EVENT_TYPES = {
    "agent.chat.start",      # Conversation initiated
    "agent.chat.complete",   # Conversation finished
    "agent.tool.call",       # Tool executed
    "agent.error",           # Error occurred
    "validation.complete",   # Validator reviewed item
    "runbook.executed",      # Runbook was run
    "feedback.received",     # Human provided feedback
    "pattern.detected",      # Pattern detector found something
    "autonomy.upgrade",      # Runbook autonomy level changed
}


@mcp.tool()
async def log_event(
    event_type: str,
    description: str,
    source_agent: str = "claude-agent",
    metadata: Optional[dict] = None,
    resolution: Optional[str] = None
) -> dict:
    """
    Log an event to the agent_events collection for learning.

    This is the foundation of the Forever Learning System - every interaction
    is logged here for pattern detection, feedback tracking, and autonomy progression.

    Args:
        event_type: Type of event. Valid types:
            - agent.chat.start: Conversation initiated
            - agent.chat.complete: Conversation finished
            - agent.tool.call: Tool executed
            - agent.error: Error occurred
            - validation.complete: Validator reviewed item
            - runbook.executed: Runbook was run
            - feedback.received: Human provided feedback
            - pattern.detected: Pattern detector found something
            - autonomy.upgrade: Runbook autonomy level changed
        description: Natural language description of the event
        source_agent: Source of the event (default: claude-agent)
        metadata: Additional context (task_id, model, latency_ms, tools_used, etc.)
        resolution: What happened / outcome (completed, failed, pending)

    Returns:
        Status with event ID for later feedback
    """
    try:
        import uuid

        # Validate event type
        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}. Logging anyway.")

        point_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build combined text for embedding (description + event type for semantic search)
        combined_text = f"{event_type}: {description}"
        if resolution:
            combined_text += f" - {resolution}"
        vector = await get_embedding(combined_text)

        payload = {
            "event_type": event_type,
            "description": description,
            "source_agent": source_agent,
            "timestamp": timestamp,
            "metadata": metadata or {},
            "resolution": resolution or "",
            "score": None,  # Will be set by feedback
            "feedback": None  # Will be set by feedback
        }

        point = {
            "id": point_id,
            "vector": vector,
            "payload": payload
        }

        success = await qdrant_upsert("agent_events", [point])

        if success:
            logger.info(f"Logged event {event_type} with ID {point_id}")

        return {"success": success, "id": point_id, "timestamp": timestamp}
    except Exception as e:
        logger.error(f"Log event failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_event(
    event_id: str,
    score: Optional[float] = None,
    feedback: Optional[str] = None,
    resolution: Optional[str] = None
) -> dict:
    """
    Update an existing event with feedback or outcome.

    Used by the feedback loop to record human feedback on agent actions,
    enabling the system to learn from successes and failures.

    Args:
        event_id: UUID of the event to update
        score: Feedback score 0.0-1.0 (0=failed, 0.5=partial, 1.0=perfect)
        feedback: Human feedback text explaining the score
        resolution: Updated resolution status (resolved, partial, failed, escalated)

    Returns:
        Status of the update operation
    """
    try:
        # Get the existing event
        point = await qdrant_get_by_id("agent_events", event_id)
        if not point:
            return {"success": False, "error": f"Event not found: {event_id}"}

        payload = point.get("payload", {})

        # Update fields if provided
        if score is not None:
            if not 0.0 <= score <= 1.0:
                return {"success": False, "error": "Score must be between 0.0 and 1.0"}
            payload["score"] = score

        if feedback is not None:
            payload["feedback"] = feedback

        if resolution is not None:
            payload["resolution"] = resolution

        # Add feedback timestamp
        payload["feedback_at"] = datetime.now(timezone.utc).isoformat()

        # Regenerate embedding with feedback context for better similarity matching
        combined_text = f"{payload.get('event_type', '')}: {payload.get('description', '')}"
        if payload.get("resolution"):
            combined_text += f" - {payload['resolution']}"
        if payload.get("feedback"):
            combined_text += f" (feedback: {payload['feedback']})"

        vector = await get_embedding(combined_text)

        updated_point = {
            "id": event_id,
            "vector": vector,
            "payload": payload
        }

        success = await qdrant_upsert("agent_events", [updated_point])

        if success:
            logger.info(f"Updated event {event_id} with score={score}, resolution={resolution}")

        return {"success": success, "id": event_id}
    except Exception as e:
        logger.error(f"Update event failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_event(event_id: str) -> Optional[dict]:
    """
    Get a specific event by ID.

    Args:
        event_id: UUID of the event

    Returns:
        Event details or None if not found
    """
    try:
        point = await qdrant_get_by_id("agent_events", event_id)
        if not point:
            return None
        return point.get("payload", {})
    except Exception as e:
        logger.error(f"Get event failed: {e}")
        return None


@mcp.tool()
async def list_recent_events(
    event_type: Optional[str] = None,
    source_agent: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    List recent events, optionally filtered by type or source.

    Args:
        event_type: Filter by event type (optional)
        source_agent: Filter by source agent (optional)
        limit: Maximum events to return (default: 50)

    Returns:
        List of recent events (most recent first)
    """
    try:
        filter_conditions = None
        must_conditions = []

        if event_type:
            must_conditions.append({"key": "event_type", "match": {"value": event_type}})
        if source_agent:
            must_conditions.append({"key": "source_agent", "match": {"value": source_agent}})

        if must_conditions:
            filter_conditions = {"must": must_conditions}

        results = await qdrant_scroll("agent_events", filter_conditions, limit=limit)

        # Extract payloads and sort by timestamp (descending)
        events = []
        for r in results:
            payload = r.get("payload", {})
            payload["id"] = str(r.get("id", ""))
            events.append(payload)

        # Sort by timestamp descending
        events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return events
    except Exception as e:
        logger.error(f"List recent events failed: {e}")
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
