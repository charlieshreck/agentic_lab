# Alert Pipeline: Keep → LangGraph → Matrix

## Overview

The alert pipeline provides AI-powered triage and human-in-the-loop approval for infrastructure alerts.

```
AlertManager/Prometheus → Keep (aggregation) → LangGraph (triage) → Matrix (approval) → Execution
```

## Components

### 1. Keep (Alert Aggregation)

| Property | Value |
|----------|-------|
| Namespace | `keep` |
| Service | `keep:8080` (NodePort 31105) |
| Frontend | `keep-frontend:3000` (NodePort 31106) |
| API Key Secret | `mcp-keep` in `ai-platform` namespace |

**Responsibilities:**
- Receives alerts from Prometheus AlertManager
- Deduplicates and correlates related alerts
- Triggers workflows on alert status changes
- Provides UI for alert management

### 2. Keep Workflow

```yaml
workflow:
  id: forward-to-langgraph
  description: Routes firing alerts to LangGraph for AI triage
  triggers:
    - type: alert
      filters:
        - key: status
          value: firing
  actions:
    - name: send-to-langgraph
      provider:
        type: webhook
        config:
          authentication:
            url: "http://langgraph.ai-platform.svc.cluster.local:8000/keep-alert"
            method: POST
      with:
        body: "{{ alert | tojson }}"
```

**Webhook Provider:**
- Name: `langgraph-keep`
- URL: `http://langgraph.ai-platform.svc.cluster.local:8000/keep-alert`

### 3. LangGraph (AI Triage)

| Property | Value |
|----------|-------|
| Namespace | `ai-platform` |
| Service | `langgraph:8000` (NodePort 30800) |
| ConfigMap | `langgraph-code` |

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/keep-alert` | POST | Receive alerts from Keep |
| `/approve` | POST | Process human approvals |
| `/pending/{alert_id}` | GET | Check pending approval status |
| `/runbooks` | GET | List diagnostic runbooks |
| `/health` | GET | Health check |

**Processing Flow:**
1. Receive alert at `/keep-alert`
2. Transform Keep format to internal format
3. Search Qdrant for matching diagnostic runbooks
4. If match found → Execute runbook diagnostics
5. If no match → Escalate to Claude for analysis
6. Generate solutions
7. Send approval request to Matrix
8. Wait for human approval
9. Execute selected solution
10. Record outcome and update runbook stats

**Approval Request Format (to Matrix):**
```json
{
  "alert_id": "keep-20260117135204",
  "room": "#infrastructure",
  "alert": {...},
  "solutions": [
    {"name": "...", "description": "...", "risk": "..."}
  ]
}
```

**Approval Format (from Matrix):**
```json
{
  "alert_id": "keep-20260117135204",
  "solution_index": 1,
  "approved_by": "chaz"
}
```

### 4. Matrix Bot (Human Interface)

| Property | Value |
|----------|-------|
| Namespace | `ai-platform` |
| Service | `matrix-bot:8000` (NodePort 30168) |
| ConfigMap | `matrix-bot-code` |
| Alert Room | `!P3BHXqELzL12n7uDOd:agentic.local` |

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/message` | POST | Send message to room |
| `/approval` | POST | Receive approval request from LangGraph |
| `/alert` | POST | Receive simple alert notification |
| `/health` | GET | Health check |

**Approval Interaction:**
- Bot posts approval request with solutions
- User reacts with ✅ to approve, ❌ to reject
- Bot forwards approval to LangGraph

## Configuration

### Keep API Access
```bash
# Get API key
kubectl get secret mcp-keep -n ai-platform -o jsonpath='{.data.api_key}' | base64 -d

# List workflows
curl -H "x-api-key: $API_KEY" http://10.20.0.40:31105/workflows

# List providers
curl -H "x-api-key: $API_KEY" http://10.20.0.40:31105/providers
```

### Workflow Management
```bash
# Create workflow (from inside cluster)
kubectl exec -n ai-platform deploy/keep-mcp -- python -c "
import httpx, os
workflow_yaml = '''
workflow:
  id: forward-to-langgraph
  ...
'''
files = {'file': ('workflow.yaml', workflow_yaml, 'application/yaml')}
headers = {'x-api-key': os.environ['KEEP_API_KEY']}
r = httpx.post('http://keep.keep.svc.cluster.local:8080/workflows',
               files=files, headers=headers)
print(r.json())
"

# Delete workflow
curl -X DELETE -H "x-api-key: $API_KEY" \
  http://10.20.0.40:31105/workflows/{workflow_id}
```

## Verification

### Check Pipeline Health
```bash
# Keep health
curl http://10.20.0.40:31105/healthcheck

# LangGraph health
curl http://10.20.0.40:30800/health

# Matrix bot health
curl http://10.20.0.40:30168/health
```

### Check Pending Approvals
```bash
curl http://10.20.0.40:30800/pending/{alert_id}
```

### Manual Approval
```bash
curl -X POST http://10.20.0.40:30800/approve \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "keep-20260117135204",
    "solution_index": 1,
    "approved_by": "chaz"
  }'
```

### Send Test Alert
```bash
kubectl exec -n ai-platform deploy/keep-mcp -- python -c "
import httpx
from datetime import datetime

alert = {
    'name': 'TestAlert',
    'status': 'firing',
    'severity': 'warning',
    'lastReceived': datetime.now().isoformat(),
    'description': 'Test alert',
    'source': ['test'],
    'fingerprint': 'test-' + datetime.now().strftime('%H%M%S')
}

r = httpx.post(
    'http://keep.keep.svc.cluster.local:8080/alerts/event/keep',
    json=alert,
    headers={'x-api-key': 'c2056883-65b1-4b78-9b97-c5f468601055'}
)
print(r.status_code, r.text)
"
```

## Known Issues

### 1. Matrix Reaction → Approval Gap
**Status:** Fixed (2026-01-17)

~~The Matrix bot's reaction handler calls the wrong endpoint~~

**Fix Applied:**
1. Added `pending_approvals` dict to track `event_id` → `alert_id` mapping
2. `/approval` endpoint now requires `alert_id` and captures Matrix `event_id`
3. `on_reaction` looks up pending approval by `event_id`
4. `process_approval` calls LangGraph `/approve` with `{alert_id, solution_index, approved_by}`

**Commit:** `dc7c746` in agentic_lab

### 2. Claude Analysis Timeout
**Status:** Known limitation

Some alerts timeout during Claude analysis (300s limit). Solution shows "Error: Task did not complete within 300.0s".

**Mitigation:** Increase timeout or add async notification when complete.

## Troubleshooting

### Alerts Not Reaching LangGraph
1. Check Keep workflow exists: `curl -H "x-api-key: $KEY" http://keep:8080/workflows`
2. Check workflow is enabled: `disabled: false`
3. Check LangGraph is reachable from Keep namespace
4. Check LangGraph logs: `kubectl logs -n ai-platform -l app=langgraph`

### Approvals Not Working
1. Check alert is pending: `curl http://langgraph:8000/pending/{alert_id}`
2. Check Matrix bot received reaction: `kubectl logs -n ai-platform -l app=matrix-bot`
3. Manually approve via API to verify LangGraph works

### Matrix Messages Not Appearing
1. Check bot is logged in: `curl http://matrix-bot:8000/health`
2. Check room ID is correct in `ALERT_ROOM_ID` env var
3. Check Conduit is accessible from matrix-bot pod
