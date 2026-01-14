#!/usr/bin/env python3
"""Neo4j MCP server for knowledge graph operations."""
import os
import json
import logging
from typing import List, Optional, Dict, Any
from base64 import b64encode
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
NEO4J_URL = os.environ.get("NEO4J_URL", "http://neo4j:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "").strip()

mcp = FastMCP(
    name="neo4j-mcp",
    instructions="""
    MCP server for Neo4j knowledge graph operations.
    Use this for relationship queries, dependency analysis, and impact assessment.

    KEY TOOLS:
    - query_graph: Execute read-only Cypher queries
    - get_entity_context: Get full context for an entity including all relationships
    - find_dependencies: Find upstream/downstream dependencies for a service
    - get_impact_analysis: What breaks if entity X fails?
    - find_path: Find connection path between two entities
    - get_runbook_for_alert: Find runbooks that resolve an alert
    - get_infrastructure_overview: High-level cluster status

    WHEN TO USE NEO4J vs QDRANT:
    - Neo4j: Relationships, dependencies, "what connects to X?", impact analysis
    - Qdrant: Semantic similarity, "find things like X", text search
    """
)


class Entity(BaseModel):
    """Entity node from the graph."""
    id: str
    type: str
    name: str
    properties: Dict[str, Any] = {}
    relationships: List[Dict[str, Any]] = []


class QueryResult(BaseModel):
    """Result from a Cypher query."""
    columns: List[str]
    data: List[List[Any]]
    summary: str = ""


class DependencyChain(BaseModel):
    """Dependency chain result."""
    entity: str
    upstream: List[str] = []
    downstream: List[str] = []
    depth: int = 1


class ImpactAnalysis(BaseModel):
    """Impact analysis result."""
    entity_type: str
    entity_id: str
    affected_services: List[Dict[str, Any]] = []
    affected_hosts: List[Dict[str, Any]] = []
    severity: str = "unknown"


async def neo4j_query(cypher: str, params: dict = None) -> dict:
    """Execute Cypher query via Neo4j HTTP API."""
    url = f"{NEO4J_URL}/db/neo4j/tx/commit"
    auth = b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()

    body = {
        "statements": [{
            "statement": cypher,
            "parameters": params or {}
        }]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth}"
            }
        )
        return response.json()


def format_query_result(result: dict) -> QueryResult:
    """Format Neo4j HTTP API response."""
    if result.get("errors"):
        return QueryResult(
            columns=[],
            data=[],
            summary=f"Error: {result['errors']}"
        )

    results = result.get("results", [])
    if not results:
        return QueryResult(columns=[], data=[], summary="No results")

    first_result = results[0]
    columns = first_result.get("columns", [])
    data = [row.get("row", []) for row in first_result.get("data", [])]

    return QueryResult(
        columns=columns,
        data=data,
        summary=f"Returned {len(data)} rows"
    )


# ============================================================================
# CORE TOOLS
# ============================================================================

@mcp.tool()
async def query_graph(cypher: str) -> QueryResult:
    """
    Execute a read-only Cypher query against the knowledge graph.

    Args:
        cypher: The Cypher query to execute. Must be read-only (no MERGE, CREATE, DELETE).

    Returns:
        Query results with columns and data rows.

    Example queries:
        "MATCH (h:Host) RETURN h.ip, h.hostname LIMIT 10"
        "MATCH (s:Service)-[:DEPENDS_ON]->(d) RETURN s.name, d.name"
        "MATCH (h:Host {ip: '10.10.0.50'}) RETURN h"
    """
    # Safety check: prevent write operations
    cypher_upper = cypher.upper()
    if any(kw in cypher_upper for kw in ["MERGE", "CREATE", "DELETE", "SET", "REMOVE", "DROP"]):
        return QueryResult(
            columns=[],
            data=[],
            summary="Error: Write operations not allowed. Use read-only queries."
        )

    result = await neo4j_query(cypher)
    return format_query_result(result)


@mcp.tool()
async def get_entity_context(entity_id: str, entity_type: str = "Host") -> Entity:
    """
    Get full context for an entity including all relationships.

    Args:
        entity_id: The entity identifier (IP, hostname, MAC, name, etc.)
        entity_type: Node label (Host, VM, Service, Pod, etc.)

    Returns:
        Entity with all properties and relationships.
    """
    # Try to find the entity by various keys
    cypher = f"""
    MATCH (e:{entity_type})
    WHERE e.ip = $id
       OR e.hostname = $id
       OR e.mac = $id
       OR e.name = $id
       OR e.vmid = $id
    WITH e LIMIT 1
    OPTIONAL MATCH (e)-[r]->(related)
    OPTIONAL MATCH (e)<-[r2]-(related2)
    RETURN e,
           collect(DISTINCT {{type: type(r), target: related.name, target_type: labels(related)[0]}}) as outgoing,
           collect(DISTINCT {{type: type(r2), source: related2.name, source_type: labels(related2)[0]}}) as incoming
    """

    result = await neo4j_query(cypher, {"id": entity_id})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return Entity(id=entity_id, type=entity_type, name="not found")

    data = result["results"][0]["data"][0]["row"]
    entity_props = data[0] if data[0] else {}
    outgoing = [r for r in data[1] if r.get("target")]
    incoming = [r for r in data[2] if r.get("source")]

    return Entity(
        id=entity_id,
        type=entity_type,
        name=entity_props.get("name", entity_props.get("hostname", entity_props.get("ip", entity_id))),
        properties=entity_props,
        relationships=outgoing + [{"type": r["type"], "direction": "incoming", **r} for r in incoming]
    )


@mcp.tool()
async def find_dependencies(service_name: str, depth: int = 2) -> DependencyChain:
    """
    Find upstream and downstream dependencies for a service.

    Args:
        service_name: Name of the service to analyze
        depth: How many hops to traverse (default 2)

    Returns:
        Dependency chain showing what this service depends on and what depends on it.
    """
    # Find upstream dependencies (what this service depends on)
    upstream_cypher = f"""
    MATCH (s:Service {{name: $name}})-[:DEPENDS_ON*1..{depth}]->(dep)
    RETURN DISTINCT dep.name as name, labels(dep)[0] as type
    """

    # Find downstream dependencies (what depends on this service)
    downstream_cypher = f"""
    MATCH (s:Service {{name: $name}})<-[:DEPENDS_ON*1..{depth}]-(dependent)
    RETURN DISTINCT dependent.name as name, labels(dependent)[0] as type
    """

    upstream_result = await neo4j_query(upstream_cypher, {"name": service_name})
    downstream_result = await neo4j_query(downstream_cypher, {"name": service_name})

    upstream = []
    if upstream_result.get("results", [{}])[0].get("data"):
        upstream = [f"{row['row'][1]}:{row['row'][0]}" for row in upstream_result["results"][0]["data"]]

    downstream = []
    if downstream_result.get("results", [{}])[0].get("data"):
        downstream = [f"{row['row'][1]}:{row['row'][0]}" for row in downstream_result["results"][0]["data"]]

    return DependencyChain(
        entity=service_name,
        upstream=upstream,
        downstream=downstream,
        depth=depth
    )


@mcp.tool()
async def get_impact_analysis(entity_type: str, entity_id: str) -> ImpactAnalysis:
    """
    Analyze what would break if an entity fails.

    Args:
        entity_type: Type of entity (Host, VM, Service, StoragePool, etc.)
        entity_id: The entity identifier

    Returns:
        Impact analysis showing affected services and hosts.
    """
    # Find all services that would be affected
    cypher = """
    MATCH (e)
    WHERE labels(e)[0] = $type
      AND (e.ip = $id OR e.hostname = $id OR e.name = $id OR e.vmid = $id)
    CALL {
        WITH e
        OPTIONAL MATCH (e)<-[:SCHEDULED_ON|HOSTS|RUNS*1..3]-(affected)
        RETURN collect(DISTINCT {name: affected.name, type: labels(affected)[0]}) as affected
    }
    CALL {
        WITH e
        OPTIONAL MATCH (e)<-[:DEPENDS_ON*1..3]-(dependent:Service)
        RETURN collect(DISTINCT {name: dependent.name, namespace: dependent.namespace}) as dependent_services
    }
    RETURN affected, dependent_services
    """

    result = await neo4j_query(cypher, {"type": entity_type, "id": entity_id})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return ImpactAnalysis(
            entity_type=entity_type,
            entity_id=entity_id,
            severity="unknown"
        )

    data = result["results"][0]["data"][0]["row"]
    affected = [a for a in data[0] if a.get("name")] if data[0] else []
    dependent_services = [s for s in data[1] if s.get("name")] if data[1] else []

    # Calculate severity based on number of affected components
    total_affected = len(affected) + len(dependent_services)
    if total_affected == 0:
        severity = "low"
    elif total_affected < 5:
        severity = "medium"
    elif total_affected < 15:
        severity = "high"
    else:
        severity = "critical"

    return ImpactAnalysis(
        entity_type=entity_type,
        entity_id=entity_id,
        affected_services=dependent_services,
        affected_hosts=affected,
        severity=severity
    )


@mcp.tool()
async def find_path(from_entity: str, to_entity: str, max_depth: int = 5) -> Dict[str, Any]:
    """
    Find connection path between two entities.

    Args:
        from_entity: Starting entity (IP, hostname, or name)
        to_entity: Target entity (IP, hostname, or name)
        max_depth: Maximum path length (default 5)

    Returns:
        Path showing how entities are connected.
    """
    cypher = f"""
    MATCH (from), (to)
    WHERE (from.ip = $from OR from.hostname = $from OR from.name = $from)
      AND (to.ip = $to OR to.hostname = $to OR to.name = $to)
    MATCH path = shortestPath((from)-[*1..{max_depth}]-(to))
    RETURN [n IN nodes(path) | {{name: n.name, type: labels(n)[0]}}] as nodes,
           [r IN relationships(path) | type(r)] as relationships
    LIMIT 1
    """

    result = await neo4j_query(cypher, {"from": from_entity, "to": to_entity})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return {
            "found": False,
            "from": from_entity,
            "to": to_entity,
            "path": []
        }

    data = result["results"][0]["data"][0]["row"]

    return {
        "found": True,
        "from": from_entity,
        "to": to_entity,
        "nodes": data[0],
        "relationships": data[1]
    }


@mcp.tool()
async def get_runbook_for_alert(alert_name: str) -> List[Dict[str, Any]]:
    """
    Find runbooks that can resolve a specific alert.

    Args:
        alert_name: Name or pattern of the alert (e.g., "HighCPU", "DiskSpace")

    Returns:
        List of runbooks that can help resolve this alert type.
    """
    cypher = """
    MATCH (r:RunbookDocument)-[:RESOLVES]->(a:Alert)
    WHERE a.name =~ ('(?i).*' + $pattern + '.*')
    RETURN r.title as title,
           r.path as path,
           r.automation_level as automation_level,
           a.name as alert_name
    ORDER BY r.automation_level DESC
    LIMIT 10
    """

    result = await neo4j_query(cypher, {"pattern": alert_name})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return []

    return [
        {
            "title": row["row"][0],
            "path": row["row"][1],
            "automation_level": row["row"][2],
            "alert": row["row"][3]
        }
        for row in result["results"][0]["data"]
    ]


@mcp.tool()
async def get_infrastructure_overview() -> Dict[str, Any]:
    """
    Get high-level infrastructure overview from the knowledge graph.

    Returns:
        Summary of hosts, VMs, services, and their health status.
    """
    cypher = """
    CALL {
        MATCH (h:Host)
        RETURN 'hosts' as label, count(h) as total,
               sum(CASE WHEN h.status = 'online' THEN 1 ELSE 0 END) as online
    }
    UNION ALL
    CALL {
        MATCH (v:VM)
        RETURN 'vms' as label, count(v) as total,
               sum(CASE WHEN v.status = 'running' THEN 1 ELSE 0 END) as online
    }
    UNION ALL
    CALL {
        MATCH (s:Service)
        RETURN 'services' as label, count(s) as total, count(s) as online
    }
    UNION ALL
    CALL {
        MATCH (p:Pod)
        RETURN 'pods' as label, count(p) as total,
               sum(CASE WHEN p.phase = 'Running' THEN 1 ELSE 0 END) as online
    }
    UNION ALL
    CALL {
        MATCH (n:Network)
        RETURN 'networks' as label, count(n) as total, count(n) as online
    }
    UNION ALL
    CALL {
        MATCH (ap:AccessPoint)
        RETURN 'access_points' as label, count(ap) as total, count(ap) as online
    }
    UNION ALL
    CALL {
        MATCH (sp:StoragePool)
        RETURN 'storage_pools' as label, count(sp) as total, count(sp) as online
    }
    """

    result = await neo4j_query(cypher)

    if result.get("errors"):
        return {"error": str(result["errors"])}

    overview = {}
    if result.get("results", [{}])[0].get("data"):
        for row in result["results"][0]["data"]:
            label = row["row"][0]
            overview[label] = {
                "total": row["row"][1],
                "online": row["row"][2]
            }

    return overview


@mcp.tool()
async def get_hosts_on_network(network: str) -> List[Dict[str, Any]]:
    """
    Get all hosts connected to a specific network.

    Args:
        network: Network name (e.g., "prod", "agentic", "monitoring", "iot")

    Returns:
        List of hosts on that network with their details.
    """
    cypher = """
    MATCH (h:Host)-[:CONNECTED_TO]->(n:Network {name: $network})
    RETURN h.ip as ip,
           h.hostname as hostname,
           h.mac as mac,
           h.status as status,
           h.type as type,
           h.vendor as vendor
    ORDER BY h.ip
    """

    result = await neo4j_query(cypher, {"network": network})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return []

    return [
        {
            "ip": row["row"][0],
            "hostname": row["row"][1],
            "mac": row["row"][2],
            "status": row["row"][3],
            "type": row["row"][4],
            "vendor": row["row"][5]
        }
        for row in result["results"][0]["data"]
    ]


@mcp.tool()
async def get_services_on_host(host_id: str) -> List[Dict[str, Any]]:
    """
    Get all services/pods running on a specific host.

    Args:
        host_id: Host identifier (IP or hostname)

    Returns:
        List of services/pods running on this host.
    """
    cypher = """
    MATCH (h:Host)
    WHERE h.ip = $id OR h.hostname = $id
    OPTIONAL MATCH (p:Pod)-[:SCHEDULED_ON]->(h)
    OPTIONAL MATCH (s:Service)-[:EXPOSES]->(p)
    RETURN p.name as pod,
           p.namespace as namespace,
           p.phase as phase,
           collect(DISTINCT s.name) as services
    """

    result = await neo4j_query(cypher, {"id": host_id})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return []

    return [
        {
            "pod": row["row"][0],
            "namespace": row["row"][1],
            "phase": row["row"][2],
            "services": row["row"][3]
        }
        for row in result["results"][0]["data"]
        if row["row"][0]  # Filter out null pods
    ]


# ============================================================================
# CLEANUP/ADMIN TOOLS
# ============================================================================

@mcp.tool()
async def find_orphan_entities(entity_type: str = None) -> List[Dict[str, Any]]:
    """
    Find entities with no relationships (likely stale or incorrect).

    Args:
        entity_type: Optional type filter (Host, VM, Service, etc.)

    Returns:
        List of orphan entities.
    """
    type_filter = f":{entity_type}" if entity_type else ""
    cypher = f"""
    MATCH (e{type_filter})
    WHERE NOT (e)--()
    RETURN e.ip as ip,
           e.name as name,
           labels(e)[0] as type,
           e.last_seen as last_seen,
           e.source as source
    ORDER BY e.last_seen ASC
    LIMIT 50
    """

    result = await neo4j_query(cypher)

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return []

    return [
        {
            "ip": row["row"][0],
            "name": row["row"][1],
            "type": row["row"][2],
            "last_seen": row["row"][3],
            "source": row["row"][4]
        }
        for row in result["results"][0]["data"]
    ]


@mcp.tool()
async def get_stale_entities(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Find entities that haven't been seen in a specified time period.

    Args:
        hours: Hours since last seen (default 24)

    Returns:
        List of stale entities.
    """
    cypher = """
    MATCH (h:Host)
    WHERE h.last_seen < datetime() - duration({hours: $hours})
    RETURN h.ip as ip,
           h.hostname as hostname,
           h.status as status,
           h.last_seen as last_seen,
           h.source as source
    ORDER BY h.last_seen ASC
    LIMIT 50
    """

    result = await neo4j_query(cypher, {"hours": hours})

    if result.get("errors") or not result.get("results", [{}])[0].get("data"):
        return []

    return [
        {
            "ip": row["row"][0],
            "hostname": row["row"][1],
            "status": row["row"][2],
            "last_seen": row["row"][3],
            "source": row["row"][4]
        }
        for row in result["results"][0]["data"]
    ]


# ============================================================================
# REST API Endpoints
# ============================================================================

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount


async def api_health(request):
    """Health check endpoint with Neo4j connectivity test."""
    try:
        result = await neo4j_query("RETURN 1 as test")
        if result.get("errors"):
            return JSONResponse({"status": "unhealthy", "neo4j": "error", "error": str(result["errors"])})
        return JSONResponse({"status": "healthy", "neo4j": "connected"})
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "neo4j": "disconnected", "error": str(e)})


async def api_overview(request):
    """REST endpoint for infrastructure overview."""
    try:
        data = await get_infrastructure_overview()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_overview error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_query(request):
    """REST endpoint for Cypher queries."""
    try:
        q = request.query_params.get("q", "")
        if not q:
            return JSONResponse({"status": "error", "error": "Missing 'q' parameter"}, status_code=400)
        data = await query_graph(q)
        return JSONResponse({"status": "ok", "data": data.model_dump()})
    except Exception as e:
        logger.error(f"REST api_query error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_entity(request):
    """REST endpoint for entity context."""
    try:
        entity_id = request.query_params.get("id", "")
        entity_type = request.query_params.get("type", "Host")
        if not entity_id:
            return JSONResponse({"status": "error", "error": "Missing 'id' parameter"}, status_code=400)
        data = await get_entity_context(entity_id, entity_type)
        return JSONResponse({"status": "ok", "data": data.model_dump()})
    except Exception as e:
        logger.error(f"REST api_entity error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# ============================================================================
# MAIN
# ============================================================================

def main():
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting neo4j MCP server on port {port}")

    # REST routes
    rest_routes = [
        Route("/health", api_health),
        Route("/api/overview", api_overview),
        Route("/api/query", api_query),
        Route("/api/entity", api_entity),
    ]

    # Combine REST routes with MCP app using http_app() for proper HTTP transport
    # FastMCP's http_app() internally handles /mcp path, so mount at root
    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/", app=mcp_app)])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
