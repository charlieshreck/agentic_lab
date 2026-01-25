# Neo4j Reasoning Graph Schema

Schema and migration scripts for the agentic knowledge system.

## Overview

This schema transforms Neo4j from an infrastructure topology graph to a **reasoning graph** that captures:
- Problems encountered
- Solutions that worked (or failed)
- Runbook execution history
- Learning from agent operations

## Files

| File | Purpose |
|------|---------|
| `001-reasoning-graph.cypher` | Core schema: constraints, indexes, config, skills, domains |
| `002-migrate-runbooks.py` | Migration script for existing Qdrant runbooks |

## Deployment

### Prerequisites

1. Neo4j 5.17+ running in agentic cluster
2. Qdrant with `runbooks` collection (54 points)
3. Ollama with `nomic-embed-text` model

### Step 1: Deploy Schema

```bash
# Connect to Neo4j
export NEO4J_PASSWORD=$(kubectl get secret neo4j-credentials -n ai-platform -o jsonpath='{.data.NEO4J_PASSWORD}' | base64 -d)

# Run schema via cypher-shell or Neo4j Browser
cat 001-reasoning-graph.cypher | cypher-shell -u neo4j -p $NEO4J_PASSWORD
```

### Step 2: Migrate Runbooks

```bash
# Set environment
export QDRANT_URL=http://qdrant.ai-platform.svc:6333
export NEO4J_URL=http://neo4j.ai-platform.svc:7474
export NEO4J_PASSWORD=<password>
export OLLAMA_URL=http://ollama.ai-platform.svc:11434

# Dry run first
python 002-migrate-runbooks.py --dry-run

# Run migration
python 002-migrate-runbooks.py
```

### Step 3: Verify

```cypher
// Count nodes
MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count ORDER BY count DESC;

// Check relationships
MATCH (r:Runbook)-[:SOLVES]->(p:Problem) RETURN count(*) AS runbook_problem_links;

// Test retrieval
MATCH (p:Problem)-[r:SOLVED_BY]->(s:Solution)
WHERE p.domain = 'dns'
RETURN p.description, s.approach, r.success_rate
ORDER BY r.success_rate DESC LIMIT 5;
```

## Schema Design

### Node Types

- **Problem**: Issues encountered (dual-indexed in Qdrant)
- **Solution**: Approaches that address problems
- **Runbook**: Executable procedures (mutable)
- **RunbookVersion**: Immutable execution snapshots
- **Execution**: Historical execution records
- **Skill**: Capability bundles (MCP groupings)
- **Config**: System-wide thresholds

### Key Relationships

```
(Runbook)-[:SOLVES]->(Problem)
(Problem)-[:SOLVED_BY {success_rate, attempts}]->(Solution)
(Runbook)-[:HAS_VERSION]->(RunbookVersion)
(Execution)-[:USED_VERSION]->(RunbookVersion)
```

### Dual-Indexing

Problems and Runbooks are indexed in both:
- **Neo4j**: For graph traversal and relationship queries
- **Qdrant** (`knowledge_nodes`): For semantic search

This allows retrieval even when domain classification is uncertain.

## Configuration

All thresholds stored in `(:Config {id: "global"})`:

```yaml
confidence_thresholds:
  autonomous_execution: 0.85
  prompted_execution: 0.60

time_decay:
  half_life_days: 90

pruning:
  min_attempts_to_archive: 5
  archive_threshold: 0.20
  stale_days: 90

automation_promotion:
  manual_to_prompted:
    min_executions: 5
    min_success_rate: 0.90
  # ... etc
```

## Review Status

| Reviewer | Date | Verdict |
|----------|------|---------|
| Claude | 2026-01-25 | Ready for Gemini review |
| Gemini | Pending | - |

See `/reviews/neo4j-schema-2026-01-25` in SilverBullet for detailed review notes.
