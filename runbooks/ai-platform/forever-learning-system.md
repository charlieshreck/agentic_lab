# Forever Learning System - Operational Runbook

## Overview

| Attribute | Value |
|-----------|-------|
| **System** | Forever Learning System |
| **Cluster** | Agentic (10.20.0.0/24) |
| **Namespace** | ai-platform |
| **Components** | claude-agent, claude-validator, knowledge-mcp, pattern-detector |
| **Dependencies** | Qdrant, Redis |

---

## Quick Health Check

```bash
# Set kubeconfig
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check all components
echo "=== Claude Agent ===" && kubectl get pods -n ai-platform -l app=claude-agent
echo "=== Knowledge MCP ===" && curl -s http://10.20.0.40:31084/health | jq
echo "=== Claude Validator ===" && curl -s http://10.20.0.40:30201/health | jq
echo "=== Pattern Detector ===" && kubectl get cronjob pattern-detector -n ai-platform
echo "=== Qdrant ===" && kubectl get pods -n ai-platform -l app=qdrant
echo "=== Event Count (7d) ===" && curl -s "http://10.20.0.40:31084/api/events?days=7&limit=1" | jq '.count'
```

---

## Component Details

### 1. claude-agent

**Purpose**: Executes tasks and logs events to Qdrant

| Resource | Value |
|----------|-------|
| Replicas | 3 |
| Port | 8000 (HTTP) |
| NodePort | 30200 |
| Health | `/health` |
| Metrics | `/metrics` |

**Key Files**:
- ConfigMap: `/home/agentic_lab/kubernetes/applications/claude-agent/configmap.yaml`
- Deployment: `/home/agentic_lab/kubernetes/applications/claude-agent/deployment.yaml`

### 2. claude-validator

**Purpose**: Validates outputs, collects feedback, analyzes skill gaps

| Resource | Value |
|----------|-------|
| Replicas | 1 |
| Port | 8000 (HTTP) |
| NodePort | 30201 |
| Health | `/health` |
| Metrics | `/metrics` |

**Key Endpoints**:
- `POST /feedback` - Submit feedback for an event
- `POST /analyze-skill-gaps` - Run skill gap analysis
- `POST /self-improve` - Trigger self-improvement

**Key Files**:
- ConfigMap: `/home/agentic_lab/kubernetes/applications/claude-validator/configmap.yaml`

### 3. knowledge-mcp

**Purpose**: MCP server providing access to Qdrant knowledge base

| Resource | Value |
|----------|-------|
| Replicas | 1 |
| Port | 8000 (HTTP) |
| NodePort | 31084 |
| Health | `/health` |

**Key REST Endpoints**:
- `GET /api/events` - Query agent_events
- `POST /api/find_similar_prompts` - Find patterns
- `POST /api/log_event` - Log new event
- `POST /api/update_event` - Update event with feedback

**Key MCP Tools**:
- `log_event()`, `update_event()`, `search_runbooks()`, `update_runbook()`

**Key Files**:
- ConfigMap: `/home/agentic_lab/kubernetes/applications/mcp-servers/knowledge-mcp.yaml`

### 4. pattern-detector

**Purpose**: Daily CronJob analyzing patterns and suggesting improvements

| Resource | Value |
|----------|-------|
| Schedule | `0 3 * * *` (3am UTC daily) |
| Timeout | 600s (10 min) |
| Memory | 256Mi limit |

**Key Files**:
- CronJob: `/home/agentic_lab/kubernetes/applications/pattern-detector/cronjob.yaml`

---

## Common Operations

### View Recent Events

```bash
# Last 7 days, all events
curl "http://10.20.0.40:31084/api/events?days=7&limit=50" | jq

# Only errors
curl "http://10.20.0.40:31084/api/events?event_types=agent.error&limit=20" | jq

# Low-scoring events
curl "http://10.20.0.40:31084/api/events?max_score=0.5&limit=20" | jq

# Pattern analysis events
curl "http://10.20.0.40:31084/api/events?event_types=pattern.analysis&limit=5" | jq
```

### Submit Feedback

```bash
curl -X POST http://10.20.0.40:30201/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "EVENT_UUID_HERE",
    "score": 0.85,
    "feedback": "Response was accurate and helpful",
    "outcome": "resolved"
  }'
```

### Run Skill Gap Analysis

```bash
# Basic analysis
curl -X POST http://10.20.0.40:30201/analyze-skill-gaps \
  -H "Content-Type: application/json" \
  -d '{"days": 7, "min_pattern_count": 3}'

# Extended analysis (30 days)
curl -X POST http://10.20.0.40:30201/analyze-skill-gaps \
  -H "Content-Type: application/json" \
  -d '{"days": 30, "min_pattern_count": 5, "similarity_threshold": 0.9}'
```

### Trigger Pattern Detector Manually

```bash
kubectl create job --from=cronjob/pattern-detector pattern-detector-manual-$(date +%s) -n ai-platform

# Watch job
kubectl get jobs -n ai-platform | grep pattern-detector

# View logs
kubectl logs -n ai-platform -l job-name=pattern-detector-manual-TIMESTAMP
```

### Find Similar Prompts

```bash
curl -X POST http://10.20.0.40:31084/api/find_similar_prompts \
  -H "Content-Type: application/json" \
  -d '{"threshold": 0.85, "min_count": 3, "days": 14}'
```

---

## Troubleshooting

### Events Not Being Logged

**Symptoms**: `agent_events` collection not growing

**Diagnosis**:
```bash
# Check claude-agent pods
kubectl get pods -n ai-platform -l app=claude-agent

# Check for logging errors in agent logs
kubectl logs -n ai-platform -l app=claude-agent --tail=100 | grep -i "log_event\|error\|knowledge"

# Test knowledge-mcp directly
curl http://10.20.0.40:31084/health

# Test event logging
curl -X POST http://10.20.0.40:31084/api/log_event \
  -H "Content-Type: application/json" \
  -d '{"event_type": "test.event", "description": "Test", "source_agent": "manual"}'
```

**Resolution**:
1. If knowledge-mcp unhealthy: `kubectl rollout restart deployment/knowledge-mcp -n ai-platform`
2. If claude-agent not logging: Check configmap for `log_to_knowledge()` function
3. If Qdrant issue: Check Qdrant pod logs

### Feedback Not Updating Events

**Symptoms**: Score stays null after feedback submission

**Diagnosis**:
```bash
# Test feedback endpoint
curl -X POST http://10.20.0.40:30201/feedback \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test-uuid", "score": 0.5, "feedback": "test", "outcome": "partial"}'

# Check validator logs
kubectl logs -n ai-platform -l app=claude-validator --tail=100 | grep -i feedback

# Verify update_event in knowledge-mcp
curl http://10.20.0.40:31084/health
```

**Resolution**:
1. Check event_id exists in agent_events collection
2. Restart validator: `kubectl rollout restart deployment/claude-validator -n ai-platform`
3. Check knowledge-mcp for update_event errors

### Pattern Detector Not Running

**Symptoms**: No `pattern.analysis` events, no job runs

**Diagnosis**:
```bash
# Check CronJob
kubectl get cronjob pattern-detector -n ai-platform

# Check job history
kubectl get jobs -n ai-platform | grep pattern-detector

# Check last job logs
kubectl logs -n ai-platform job/pattern-detector-XXXXX
```

**Resolution**:
1. Verify CronJob schedule: `schedule: "0 3 * * *"`
2. Run manual job to test: `kubectl create job --from=cronjob/pattern-detector test-$(date +%s) -n ai-platform`
3. Check ConfigMap for Python errors

### Skill Gap Analysis Returns Empty

**Symptoms**: `/analyze-skill-gaps` returns `patterns_found: []`

**Diagnosis**:
```bash
# Check if events exist
curl "http://10.20.0.40:31084/api/events?days=30&limit=1" | jq '.count'

# Check find_similar_prompts
curl -X POST http://10.20.0.40:31084/api/find_similar_prompts \
  -H "Content-Type: application/json" \
  -d '{"threshold": 0.7, "min_count": 2, "days": 30}'
```

**Resolution**:
1. Lower threshold: Try `similarity_threshold: 0.7`
2. Extend time range: Try `days: 30`
3. Lower min count: Try `min_pattern_count: 2`
4. Check for events with proper `description` field (needed for similarity)

### Qdrant Connection Issues

**Symptoms**: 500 errors from knowledge-mcp

**Diagnosis**:
```bash
# Check Qdrant pod
kubectl get pods -n ai-platform -l app=qdrant

# Check Qdrant health
kubectl exec -n ai-platform -it deploy/qdrant -- curl localhost:6333/healthz

# Check collections exist
curl http://10.20.0.40:31084/api/collections | jq
```

**Resolution**:
1. Restart Qdrant: `kubectl rollout restart deployment/qdrant -n ai-platform`
2. Check PVC storage: `kubectl get pvc -n ai-platform | grep qdrant`
3. Check Qdrant logs: `kubectl logs -n ai-platform -l app=qdrant`

---

## Monitoring

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `claude_agent_tasks_total` | Counter | Total tasks by status/model |
| `claude_agent_task_duration_seconds` | Histogram | Task execution time |
| `claude_validator_feedback_total` | Counter | Feedback submissions |
| `claude_validator_feedback_score` | Histogram | Score distribution |
| `claude_validator_skill_gaps_detected_total` | Counter | Skill gaps found |

### Alerts

```yaml
# Learning system health
- alert: LearningSystemStale
  expr: time() - max(claude_agent_last_event_timestamp) > 86400
  annotations:
    summary: "No events logged in 24 hours"

- alert: FeedbackLoopBroken
  expr: increase(claude_validator_feedback_total[7d]) == 0
  annotations:
    summary: "No feedback in 7 days"

- alert: LowFeedbackScore
  expr: avg(claude_validator_feedback_score) < 0.6
  annotations:
    summary: "Average feedback below 60%"
```

### Dashboard

Access: `https://grafana.kernow.io/d/ai-learning` (when deployed)

Key panels:
- Event volume trend
- Feedback score distribution
- Skill gaps over time
- Autonomy level progression

---

## Data Management

### Event Retention

Events older than 90 days are archived by the pattern-detector job:

```python
# In pattern_detector.py
async def cleanup_old_events():
    cutoff = datetime.now() - timedelta(days=90)
    # Archive to cold storage, delete from Qdrant
```

### Backup

```bash
# Qdrant snapshot
kubectl exec -n ai-platform deploy/qdrant -- curl -X POST localhost:6333/collections/agent_events/snapshots

# Download snapshot
kubectl cp ai-platform/qdrant-0:/qdrant/snapshots ./qdrant-backup/
```

### Collection Stats

```bash
# Get collection info
curl http://10.20.0.40:31084/api/collections/agent_events | jq

# Expected growth: ~100 events/day = ~36,500/year
# Storage: ~1-2KB per event = ~50-70MB/year
```

---

## Restart Procedures

### Full System Restart

```bash
# Restart all learning system components
kubectl rollout restart deployment/claude-agent -n ai-platform
kubectl rollout restart deployment/claude-validator -n ai-platform
kubectl rollout restart deployment/knowledge-mcp -n ai-platform

# Wait for rollout
kubectl rollout status deployment/claude-agent -n ai-platform
kubectl rollout status deployment/claude-validator -n ai-platform
kubectl rollout status deployment/knowledge-mcp -n ai-platform

# Verify health
curl http://10.20.0.40:31084/health
curl http://10.20.0.40:30200/health
curl http://10.20.0.40:30201/health
```

### ConfigMap Update Deployment

After editing a ConfigMap:

```bash
# knowledge-mcp
kubectl rollout restart deployment/knowledge-mcp -n ai-platform

# claude-validator
kubectl rollout restart deployment/claude-validator -n ai-platform

# claude-agent
kubectl rollout restart deployment/claude-agent -n ai-platform
```

---

## Escalation

| Issue | First Response | Escalate To |
|-------|---------------|-------------|
| Events not logging | Restart claude-agent | Check Qdrant |
| Feedback broken | Restart validator | Check knowledge-mcp |
| Pattern detector fails | Run manual job | Check Python code |
| Qdrant down | Restart Qdrant pod | Check storage/PVC |
| High latency | Check pod resources | Scale replicas |

---

## Related Documentation

- Architecture: `/home/agentic_lab/docs/FOREVER-LEARNING-SYSTEM.md`
- Plan: `/root/.claude/plans/steady-foraging-kite.md`
- knowledge-mcp: `/home/agentic_lab/kubernetes/applications/mcp-servers/knowledge-mcp.yaml`
- claude-validator: `/home/agentic_lab/kubernetes/applications/claude-validator/configmap.yaml`

---

*Runbook Version: 1.0*
*Last Updated: 2026-01-15*
*Author: Forever Learning System*
