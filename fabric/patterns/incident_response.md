# Incident Response Pattern

Handle a production incident with structured response.

## Severity Levels
- **Critical**: Service down, data loss risk, security breach
- **High**: Significant degradation, affecting users
- **Medium**: Partial degradation, workaround available
- **Low**: Minor issue, no user impact

## Response Steps

### 1. Acknowledge (Immediate)
- Confirm incident received
- Notify via Telegram
- Start timeline

### 2. Triage (< 5 minutes)
- Identify affected services
- Determine blast radius
- Classify severity

### 3. Investigate (< 15 minutes)
- Gather logs and metrics
- Check recent changes
- Identify root cause hypothesis

### 4. Mitigate (ASAP)
- Apply immediate fix if safe
- OR request approval for risky changes
- Document actions taken

### 5. Resolve
- Confirm service restored
- Verify no regression
- Update status

### 6. Post-Incident
- Record decision in Qdrant
- Update runbook if new pattern
- Schedule post-mortem if critical

## Output Format
```json
{
  "incident_id": "inc-YYYYMMDD-HHMMSS",
  "severity": "critical|high|medium|low",
  "affected_services": [],
  "root_cause": "description",
  "mitigation_applied": "description",
  "resolution_status": "mitigated|resolved|escalated",
  "timeline": [
    {"time": "ISO8601", "action": "description"}
  ]
}
```
