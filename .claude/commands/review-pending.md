# Review Pending Items

Show all items pending my approval:

1. Query Qdrant `validations` collection for items with status="pending"
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/validations/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 20, "with_payload": true, "filter": {"must": [{"key": "status", "match": {"value": "pending"}}]}}'
   ```

2. Query Qdrant `capability_gaps` collection for status="awaiting_approval"
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/capability_gaps/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 20, "with_payload": true, "filter": {"must": [{"key": "status", "match": {"value": "awaiting_approval"}}]}}'
   ```

3. Query Qdrant `skill_gaps` collection for status="awaiting_approval"
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/skill_gaps/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 20, "with_payload": true, "filter": {"must": [{"key": "status", "match": {"value": "awaiting_approval"}}]}}'
   ```

4. Check for new runbooks pending review

Format as an actionable list with:
- Item type (validation, capability gap, skill gap, runbook)
- Brief description
- Created timestamp
- Priority level
- Suggested action (approve/reject/review)
