#!/usr/bin/env python3
"""
Migrate existing Qdrant runbooks to Neo4j reasoning graph.

This script:
1. Reads all runbooks from Qdrant 'runbooks' collection
2. Creates Problem nodes for each unique trigger_pattern
3. Creates Runbook nodes with initial RunbookVersion
4. Creates SOLVES relationships
5. Dual-indexes Problems in 'knowledge_nodes' collection

Run with: python 002-migrate-runbooks.py [--dry-run]
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from uuid import uuid4

import httpx

# Configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant.ai-platform.svc:6333")
NEO4J_URL = os.environ.get("NEO4J_URL", "http://neo4j.ai-platform.svc:7474")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama.ai-platform.svc:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Domain classification keywords
DOMAIN_KEYWORDS = {
    "infra": ["kubernetes", "k8s", "pod", "node", "terraform", "proxmox", "storage", "vm", "container", "deployment", "helm"],
    "security": ["cert", "ssl", "tls", "auth", "vault", "secret", "firewall", "cve", "credential"],
    "obs": ["alert", "metric", "prometheus", "grafana", "log", "monitor", "trace", "coroot", "keep"],
    "dns": ["dns", "domain", "adguard", "unbound", "resolve", "record", "wpad"],
    "network": ["network", "vlan", "ip", "dhcp", "route", "switch", "wifi", "opnsense"],
    "data": ["database", "postgres", "qdrant", "neo4j", "backup", "redis", "migration"],
}


@dataclass
class RunbookData:
    id: str
    title: str
    trigger_pattern: str
    solution: str
    path: Optional[str]
    automation_level: str
    execution_count: int
    success_count: int
    success_rate: float
    created_at: str


def classify_domain(text: str) -> str:
    """Classify text into a problem domain based on keywords."""
    text_lower = text.lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)

    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return "general"


def content_hash(data: dict) -> str:
    """Generate SHA256 hash of content for change detection."""
    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def get_embedding(text: str) -> List[float]:
    """Generate embedding using Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text}
        )
        response.raise_for_status()
        return response.json().get("embedding", [])


async def qdrant_request(endpoint: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
    """Make request to Qdrant API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{QDRANT_URL}{endpoint}"
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        elif method == "PUT":
            response = await client.put(url, json=data)
        response.raise_for_status()
        return response.json()


async def neo4j_query(cypher: str, params: dict = None) -> List[Dict]:
    """Execute Cypher query against Neo4j."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{NEO4J_URL}/db/neo4j/tx/commit",
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            json={
                "statements": [{
                    "statement": cypher,
                    "parameters": params or {}
                }]
            }
        )
        response.raise_for_status()
        result = response.json()

        if result.get("errors"):
            raise Exception(f"Neo4j error: {result['errors']}")

        return result.get("results", [{}])[0].get("data", [])


async def ensure_knowledge_nodes_collection():
    """Create knowledge_nodes collection in Qdrant if it doesn't exist."""
    try:
        await qdrant_request("/collections/knowledge_nodes")
        logger.info("knowledge_nodes collection already exists")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("Creating knowledge_nodes collection...")
            await qdrant_request("/collections/knowledge_nodes", "PUT", {
                "vectors": {
                    "size": 768,  # nomic-embed-text dimension
                    "distance": "Cosine"
                }
            })
            logger.info("knowledge_nodes collection created")
        else:
            raise


async def fetch_all_runbooks() -> List[RunbookData]:
    """Fetch all runbooks from Qdrant."""
    result = await qdrant_request("/collections/runbooks/points/scroll", "POST", {
        "limit": 100,
        "with_payload": True
    })

    runbooks = []
    for point in result.get("result", {}).get("points", []):
        payload = point.get("payload", {})
        runbooks.append(RunbookData(
            id=str(point.get("id")),
            title=payload.get("title", "Untitled"),
            trigger_pattern=payload.get("trigger_pattern", ""),
            solution=payload.get("solution", ""),
            path=payload.get("path"),
            automation_level=payload.get("automation_level", "manual"),
            execution_count=payload.get("execution_count", 0),
            success_count=payload.get("success_count", 0),
            success_rate=payload.get("success_rate", 0.0),
            created_at=payload.get("created_at", datetime.utcnow().isoformat())
        ))

    return runbooks


async def migrate_runbook(runbook: RunbookData, dry_run: bool = False) -> Dict[str, Any]:
    """Migrate a single runbook to Neo4j with dual-indexing."""

    # Classify domain
    domain = classify_domain(f"{runbook.title} {runbook.trigger_pattern}")

    # Generate IDs
    problem_id = str(uuid4())
    runbook_id = runbook.id  # Keep original ID for reference
    version_id = str(uuid4())

    # Create content hash for version
    version_content = {
        "solution": runbook.solution,
        "automation_level": runbook.automation_level
    }
    version_hash = content_hash(version_content)

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate: {runbook.title}")
        logger.info(f"  - Domain: {domain}")
        logger.info(f"  - Problem ID: {problem_id}")
        logger.info(f"  - Runbook ID: {runbook_id}")
        return {"status": "dry_run", "runbook_id": runbook_id}

    # Create Problem node
    await neo4j_query("""
        CREATE (p:Problem {
            id: $problem_id,
            description: $trigger_pattern,
            domain: $domain,
            created_at: datetime($created_at),
            last_referenced: datetime(),
            weight: 1.0
        })
    """, {
        "problem_id": problem_id,
        "trigger_pattern": runbook.trigger_pattern,
        "domain": domain,
        "created_at": runbook.created_at
    })

    # Create Runbook node
    await neo4j_query("""
        CREATE (r:Runbook {
            id: $runbook_id,
            name: $title,
            problem_class: $trigger_pattern,
            skills_required: $skills,
            automation_level: $automation_level,
            current_version: $version,
            created_at: datetime($created_at),
            last_used: datetime()
        })
    """, {
        "runbook_id": runbook_id,
        "title": runbook.title,
        "trigger_pattern": runbook.trigger_pattern,
        "skills": [domain] if domain != "general" else ["infra"],
        "automation_level": runbook.automation_level,
        "version": "1.0.0",
        "created_at": runbook.created_at
    })

    # Create RunbookVersion node
    # Note: steps and ground_truth_probes stored as JSON strings for Neo4j Community Edition compatibility
    await neo4j_query("""
        CREATE (rv:RunbookVersion {
            id: $version_id,
            runbook_id: $runbook_id,
            version: "1.0.0",
            steps_json: $steps_json,
            ground_truth_probes_json: "[]",
            content_hash: $content_hash,
            created_at: datetime(),
            created_by: "migration"
        })
    """, {
        "version_id": version_id,
        "runbook_id": runbook_id,
        "steps_json": json.dumps([{"action": "Execute solution", "description": runbook.solution[:500]}]),
        "content_hash": version_hash
    })

    # Create relationships
    await neo4j_query("""
        MATCH (r:Runbook {id: $runbook_id})
        MATCH (p:Problem {id: $problem_id})
        MATCH (rv:RunbookVersion {id: $version_id})
        CREATE (r)-[:SOLVES]->(p)
        CREATE (r)-[:HAS_VERSION {current: true}]->(rv)
    """, {
        "runbook_id": runbook_id,
        "problem_id": problem_id,
        "version_id": version_id
    })

    # If we have execution history, create a synthetic SOLVED_BY relationship
    if runbook.execution_count > 0:
        await neo4j_query("""
            MATCH (p:Problem {id: $problem_id})
            CREATE (s:Solution {
                id: randomUUID(),
                approach: $solution,
                outcome_summary: "Migrated from Qdrant runbooks",
                confidence: $success_rate,
                created_at: datetime()
            })
            CREATE (p)-[:SOLVED_BY {
                success_rate: $success_rate,
                attempts: $attempts,
                successes: $successes,
                last_used: datetime()
            }]->(s)
        """, {
            "problem_id": problem_id,
            "solution": runbook.solution[:500],
            "success_rate": runbook.success_rate,
            "attempts": runbook.execution_count,
            "successes": runbook.success_count
        })

    # Dual-index Problem in Qdrant
    embedding = await get_embedding(runbook.trigger_pattern)
    await qdrant_request("/collections/knowledge_nodes/points", "PUT", {
        "points": [{
            "id": problem_id,
            "vector": embedding,
            "payload": {
                "type": "problem",
                "neo4j_id": problem_id,
                "domain": domain,
                "content_hash": content_hash({"description": runbook.trigger_pattern}),
                "indexed_at": datetime.utcnow().isoformat()
            }
        }]
    })

    logger.info(f"Migrated: {runbook.title} -> Problem({problem_id}), Runbook({runbook_id})")

    return {
        "status": "migrated",
        "runbook_id": runbook_id,
        "problem_id": problem_id,
        "domain": domain
    }


async def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=== DRY RUN MODE ===")

    # Ensure knowledge_nodes collection exists
    await ensure_knowledge_nodes_collection()

    # Fetch all runbooks
    logger.info("Fetching runbooks from Qdrant...")
    runbooks = await fetch_all_runbooks()
    logger.info(f"Found {len(runbooks)} runbooks to migrate")

    # Migrate each runbook
    results = {
        "total": len(runbooks),
        "migrated": 0,
        "failed": 0,
        "domains": {}
    }

    for runbook in runbooks:
        try:
            result = await migrate_runbook(runbook, dry_run)
            results["migrated"] += 1

            domain = result.get("domain", "unknown")
            results["domains"][domain] = results["domains"].get(domain, 0) + 1

        except Exception as e:
            logger.error(f"Failed to migrate {runbook.title}: {e}")
            results["failed"] += 1

    # Print summary
    logger.info("=== Migration Summary ===")
    logger.info(f"Total:    {results['total']}")
    logger.info(f"Migrated: {results['migrated']}")
    logger.info(f"Failed:   {results['failed']}")
    logger.info("Domains:")
    for domain, count in sorted(results["domains"].items()):
        logger.info(f"  - {domain}: {count}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
