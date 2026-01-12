# Knowledge-MCP Test Suite

Automated tests for verifying the knowledge-mcp server functionality in the Kernow homelab unified knowledge system.

## Prerequisites

- Python 3.11+
- knowledge-mcp server running in agentic cluster
- Qdrant with indexed documentation and runbooks

## Installation

```bash
cd /home/agentic_lab/tests/knowledge-mcp
pip install -r requirements.txt
```

## Running Tests

### All Tests
```bash
pytest -v
```

### Integration Tests Only (requires running MCP)
```bash
pytest -v -m integration
```

### Unit Tests Only
```bash
pytest -v -m unit
```

### Specific Test File
```bash
pytest -v test_connectivity.py
pytest -v test_semantic_search.py
pytest -v test_runbooks.py
pytest -v test_entities.py
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWLEDGE_MCP_URL` | `http://knowledge-mcp.ai-platform.svc.cluster.local:8080` | MCP server URL |

### For External Access (NodePort)
```bash
export KNOWLEDGE_MCP_URL="http://10.20.0.40:31090"
pytest -v
```

### For In-Cluster Access
```bash
export KNOWLEDGE_MCP_URL="http://knowledge-mcp.ai-platform.svc.cluster.local:8080"
pytest -v
```

## Test Categories

### test_connectivity.py
- Server reachability
- Tool endpoint availability
- Qdrant connection health
- Collection existence

### test_semantic_search.py
- Documentation search quality
- Runbook search quality
- Query relevance
- Empty query handling

### test_runbooks.py
- Runbook retrieval
- Content quality checks
- Git integration (commit refs)
- Category coverage

### test_entities.py
- Entity search by type, network, capability
- Entity retrieval by IP, hostname, MAC
- Scope coverage (local, cloud, virtual)
- Device type information

## Expected Results

When knowledge-mcp is properly configured with indexed content:
- All connectivity tests should pass
- Semantic search should return relevant results
- Runbooks should be retrievable by path
- Entities should be searchable by various criteria

## Troubleshooting

### Connection Refused
- Check knowledge-mcp pod is running: `kubectl get pods -n ai-platform`
- Check service exists: `kubectl get svc -n ai-platform`
- Verify URL is correct for your access method

### Empty Search Results
- Verify Qdrant collections are populated
- Check if runbooks have been indexed
- Verify documentation files are in knowledge base

### Test Timeouts
- Increase client timeout in conftest.py
- Check Qdrant performance
- Verify network connectivity

## Adding New Tests

1. Create new test file `test_<feature>.py`
2. Use fixtures from `conftest.py`
3. Mark tests appropriately (`@pytest.mark.integration` or `@pytest.mark.unit`)
4. Run locally before committing
