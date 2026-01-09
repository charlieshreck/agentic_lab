# Runbook Coverage Analysis

Analyze runbook coverage gaps:

1. Get all services from NetBox MCP
   ```bash
   curl -s -X POST "http://netbox-mcp:8000/mcp" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "netbox_list_services", "arguments": {}}}'
   ```

2. Get all runbooks from Qdrant
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/runbooks/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 100, "with_payload": true}'
   ```

3. Cross-reference to identify:
   - Services without any associated runbooks
   - Common alert types (from recent decisions) without runbooks
   - Runbooks with low success rates that need improvement

4. Suggest priorities for new runbooks based on:
   - Service criticality
   - Alert frequency
   - Mean time to resolution

Format output as:
- **Coverage Summary**: X of Y services have runbooks
- **Gaps by Priority**: High/Medium/Low priority services without runbooks
- **Runbook Health**: Runbooks that need attention (high failure rate, stale)
- **Recommendations**: Top 3 runbooks to create next
