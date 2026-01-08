# Investigate Alert Pattern

You are investigating an infrastructure alert. Follow this structured approach:

## Context
- Alert: {alertname}
- Severity: {severity}
- Namespace: {namespace}
- Description: {description}

## Investigation Steps

1. **Identify the affected component**
   - What service/pod/node is affected?
   - What is the current state?

2. **Gather diagnostic information**
   - Check pod logs: `kubectl logs -n {namespace} <pod>`
   - Check events: `kubectl get events -n {namespace} --sort-by='.lastTimestamp'`
   - Check resource status: `kubectl get pods -n {namespace}`

3. **Determine root cause**
   - Is this a resource issue (CPU/memory)?
   - Is this a configuration issue?
   - Is this a dependency issue (database, external service)?
   - Is this a network issue?

4. **Review similar past incidents**
   - Search the decisions collection for similar alerts
   - Check if there's an existing runbook

## Output Format

Respond with JSON:
```json
{
  "affected_component": "description",
  "current_state": "description",
  "root_cause": "description",
  "recommended_actions": ["action1", "action2"],
  "risk_level": "low|medium|high",
  "requires_human_approval": true|false
}
```
