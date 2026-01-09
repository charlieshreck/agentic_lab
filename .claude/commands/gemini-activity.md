# Gemini Activity Summary

Summarize recent Gemini activity:

1. Query Qdrant `decisions` collection for last 24 hours
   ```bash
   curl -s -X POST "http://qdrant:6333/collections/decisions/points/scroll" \
     -H "Content-Type: application/json" \
     -d '{"limit": 50, "with_payload": true}'
   ```

2. Group decisions by outcome:
   - **Success**: Fix applied and validated
   - **Pending**: Awaiting approval
   - **Failed**: Fix failed or rolled back
   - **Escalated**: Sent to Claude for review

3. Identify patterns:
   - Most common alert types
   - Services with most incidents
   - Time-of-day patterns

4. Show learning metrics:
   - New runbooks created
   - Runbooks updated (success/failure stats)
   - Capability gaps identified
   - Skill gaps identified

Format as a dashboard-style report:
```
=== GEMINI ACTIVITY (Last 24h) ===

Decisions: 12 total
  ✅ Success: 8 (67%)
  ⏳ Pending: 2
  ❌ Failed: 1
  ⬆️ Escalated: 1

Top Alert Types:
  1. PodCrashLoopBackOff (4)
  2. HighMemoryUsage (3)
  3. CertificateExpiring (2)

Learning:
  📚 New runbooks: 1
  📈 Runbook updates: 3
  🔧 Capability gaps: 0
  💡 Skill gaps: 1
```
