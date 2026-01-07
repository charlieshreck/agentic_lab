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
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

mcp = FastMCP(
    name="knowledge-mcp",
    instructions="""
    MCP server for knowledge base operations.
    Provides semantic search across runbooks, decisions, and documentation.
    Use these tools to find relevant information and store new knowledge.
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


async def get_embedding(text: str) -> List[float]:
    """Get embedding vector from Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]


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
