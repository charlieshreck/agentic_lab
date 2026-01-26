# Validate Skill

This skill provides human-triggered validation of runbook executions against ground truth from the observability stack, powered by the LangGraph validation SubGraph.

## When to Use

Use this skill when:
- Spot-checking if a runbook execution actually succeeded
- Auditing runbook performance before autonomy promotion
- Investigating suspicious success/failure patterns
- Validating historical executions

## Commands

```
/validate <event_id>              # Validate specific execution
/validate --runbook <runbook_id>  # Validate recent executions for runbook
/validate --last <n>              # Validate last N executions
/validate --autonomy-candidates   # Validate all pending promotion candidates
```

## Validation Method

All validation is routed through the LangGraph validation SubGraph, which implements a 4-node workflow:

1. **fetch_context** - Gets event + runbook from knowledge-mcp
2. **gather_truth** - Queries observability-mcp (Keep, Coroot, Gatus) and infrastructure-mcp (kubectl)
3. **compute_verdict** - Deterministic logic first, Ollama/LiteLLM fallback if uncertain
4. **record_validation** - Writes structured validation back to knowledge-mcp

### Single Event Validation

```bash
# POST to LangGraph validation endpoint
curl -X POST http://langgraph:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"event_id": "<event_id>", "triggered_by": "human"}'
```

Human-triggered validations run immediately (no cooling period).

### Batch Validation (Autonomy Candidates)

```bash
# POST to LangGraph validate-candidates endpoint
curl -X POST http://langgraph:8000/validate-candidates \
  -H "Content-Type: application/json" \
  -d '{"max_candidates": 10}'
```

### Check Results

After validation completes, the event will have a `validation` field:

```
knowledge-mcp: get_event(<event_id>)
```

Returns:
```json
{
  "validation": {
    "validated": true,
    "validated_at": "2026-01-26T08:30:00",
    "validated_by": "human",
    "verdict": "confirmed",
    "confidence": 0.95,
    "actual_success": true,
    "signal_count": 3,
    "ground_truth": {
      "alert_state": {"status": "resolved", "resolved": true},
      "service_health": {"status": "OK"},
      "kubernetes": {"total_pods": 2, "running_pods": 2, "healthy": true}
    }
  }
}
```

## Workflow for Each Command

### `/validate <event_id>`

1. Call `POST http://langgraph:8000/validate` with `{"event_id": "<event_id>", "triggered_by": "human"}`
2. Wait a few seconds for processing
3. Call `get_event(<event_id>)` via knowledge-mcp to retrieve the validation result
4. Display the verdict, confidence, and ground truth summary

### `/validate --runbook <runbook_id>`

1. Call `list_recent_events(event_type="runbook.execution", limit=20)` via knowledge-mcp
2. Filter events where `metadata.runbook_id == <runbook_id>`
3. For each unvalidated event, call `POST http://langgraph:8000/validate`
4. Wait for processing, then retrieve and display results in a table

### `/validate --last <n>`

1. Call `list_recent_events(event_type="runbook.execution", limit=<n>)` via knowledge-mcp
2. For each unvalidated event, call `POST http://langgraph:8000/validate`
3. Wait for processing, then retrieve and display results

### `/validate --autonomy-candidates`

1. Call `POST http://langgraph:8000/validate-candidates` with `{"max_candidates": 10}`
2. Wait for processing
3. Call `list_autonomy_candidates()` via knowledge-mcp
4. For each candidate, get recent events and display validation status

## Response Format

### Single Validation
```
## Validation Results

**Event:** `{event_id}`
**Runbook:** {runbook_title}
**Executed:** {timestamp}

### Reported vs Actual
| Aspect | Reported | Ground Truth |
|--------|----------|--------------|
| Success | ✅/❌ | ✅/❌ |
| Alert State | - | {resolved/firing} |
| Service Health | - | {healthy/degraded} |
| Endpoint | - | {up/down} |

### Verdict
{✅ Confirmed | ⚠️ False Positive | ⚠️ False Negative | ❓ Uncertain}

**Confidence:** {0.0-1.0}
**Signals checked:** {signal_count}
```

### Batch Validation (Runbook Audit)
```
## Runbook Validation: {runbook_title}

Last {n} executions:

| Execution | Date | Reported | Validated | Confidence |
|-----------|------|----------|-----------|------------|
| {id_1} | {date} | ✅ | ✅ Confirmed | 0.95 |
| {id_2} | {date} | ✅ | ⚠️ Uncertain | 0.45 |
| {id_3} | {date} | ❌ | ✅ Confirmed | 0.88 |

### Summary
- **Validated:** {n}/{total}
- **False Positives:** {n}
- **False Negatives:** {n}
- **Uncertain:** {n}

### Recommendation
{Ready for promotion | Needs investigation | Block promotion}
```

## Verdict Types

| Verdict | Meaning | Autonomy Impact |
|---------|---------|-----------------|
| confirmed | Reported outcome matches ground truth | Counts toward promotion |
| false_positive | Reported success, actually failed | **Blocks runbook** (downgraded to manual) |
| false_negative | Reported failure, actually succeeded | No impact (conservative) |
| uncertain | Insufficient signals (confidence < 0.7) | Not counted |

## Key Design Decisions

- **Deterministic first**: Pure Python logic evaluates ground truth signals before any LLM call
- **LLM fallback**: Only invoked if deterministic logic returns confidence < 0.7
- **5-minute cooling**: Auto-triggered validations wait 5 minutes for metrics to settle
- **False positive = block**: Runbooks producing false positives are immediately downgraded to manual (Gemini R3)
- **Pydantic enforced**: All validation results pass through ValidationResult schema (Gemini R4)

## Ground Truth Sources by Domain

| Domain | Primary Source | Secondary Source |
|--------|----------------|------------------|
| Kubernetes | kubectl_get_pods | coroot_get_service_metrics |
| DNS | gatus_get_endpoint_status | query_metrics |
| Network | gatus_get_endpoint_status | unifi_list_clients |
| Alerts | keep_get_alert | prometheus alerts |
| Storage | truenas_get_alerts | query_metrics |
| Media | plex_get_active_sessions | gatus |

## Notes

- This skill is **human-triggered only** - automated validation is handled by LangGraph's `record_outcome` function
- Ground truth gathering may fail if observability stack is unavailable (verdict = "uncertain", confidence = 0.3)
- Confidence < 0.7 is marked as "uncertain" and not counted toward autonomy decisions
- False positives are more dangerous than false negatives for autonomy

## Related

- `record_runbook_execution()` - How executions are logged
- `get_autonomy_config()` - Promotion thresholds (70/85/95)
- `list_autonomy_candidates()` - Pending promotions
- `POST /validate` - LangGraph validation endpoint
- `POST /validate-candidates` - Batch validation endpoint
