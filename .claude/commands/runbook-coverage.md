# Runbook Coverage Analysis

Analyze runbook coverage gaps:

1. Get all entities from Qdrant (network devices and services)
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/entities/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 100, "with_payload": true}'
   ```

2. Get all runbooks from Qdrant
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/runbooks/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 100, "with_payload": true}'
   ```

3. Cross-reference to identify:
   - Entities without any associated runbooks
   - Common alert types (from recent decisions) without runbooks
   - Runbooks with low success rates that need improvement

4. Suggest priorities for new runbooks based on:
   - Entity criticality (infrastructure > compute > storage > endpoint)
   - Alert frequency
   - Mean time to resolution

Format output as:
- **Coverage Summary**: X of Y entities have runbooks
- **Gaps by Priority**: High/Medium/Low priority entities without runbooks
- **Runbook Health**: Runbooks that need attention (high failure rate, stale)
- **Recommendations**: Top 3 runbooks to create next
