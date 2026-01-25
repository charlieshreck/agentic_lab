# Validate Skill

This skill provides human-triggered validation of runbook executions against ground truth from the observability stack.

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

## Validation Process

### Step 1: Retrieve Execution Event

Use knowledge-mcp to get the execution event:
```
get_event(event_id)
```

This returns:
- `runbook_id`: Which runbook was executed
- `timestamp`: When it ran
- `success`: Reported success/failure
- `output`: Execution output/logs
- `alert_fingerprint`: Related alert (if any)
- `service_name`: Affected service (if any)

### Step 2: Retrieve Runbook Definition

Use knowledge-mcp to get the runbook:
```
get_runbook(runbook_id)
```

This returns:
- `title`: Runbook name
- `steps`: What it does
- `expected_outcome`: What success looks like
- `success_criteria`: How to verify success

### Step 3: Gather Ground Truth

Query observability sources to determine what actually happened:

#### Keep (Alert State)
If the execution was for an alert:
```
keep_get_alert(alert_fingerprint)
```
Check: Is the alert resolved? When did it resolve?

#### Prometheus/VictoriaMetrics (Metrics)
If success criteria includes metrics:
```
query_metrics(query, start_time, end_time)
```
Check: Did the metric improve after execution?

#### Coroot (Service Health)
If a service was involved:
```
coroot_get_service_metrics(service_name)
```
Check: Is the service healthy now?

#### Gatus (Endpoint Status)
If an endpoint was involved:
```
gatus_get_endpoint_status(endpoint)
```
Check: Is the endpoint responding?

#### Kubernetes (Pod/Deployment State)
If Kubernetes resources were involved:
```
kubectl_get_pods(namespace, label_selector)
kubectl_get_deployments(namespace)
```
Check: Are pods running? Is deployment healthy?

### Step 4: Compare and Evaluate

Compare the reported outcome against ground truth:

| Reported | Ground Truth | Verdict |
|----------|--------------|---------|
| Success  | Confirmed    | ✅ Validated |
| Success  | Not confirmed| ⚠️ False positive |
| Failure  | Confirmed    | ✅ Validated |
| Failure  | Success seen | ⚠️ False negative |

### Step 5: Record Validation

Update the event with validation results:
```
update_event(
  event_id=event_id,
  validation={
    "validated": true,
    "validated_at": "ISO timestamp",
    "validated_by": "human-triggered",
    "verdict": "confirmed|false_positive|false_negative|uncertain",
    "confidence": 0.0-1.0,
    "ground_truth": {...}
  }
)
```

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
**Evidence:** {brief summary}
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

- This skill is **human-triggered only** - not automated
- Use LiteLLM for LLM calls (routes to configured backend)
- Ground truth gathering may fail if observability is unavailable
- Confidence < 0.7 should be marked as "uncertain"
- False positives are more dangerous than false negatives for autonomy

## Related

- `record_runbook_execution()` - How executions are logged
- `get_autonomy_config()` - Promotion thresholds
- `list_autonomy_candidates()` - Pending promotions
