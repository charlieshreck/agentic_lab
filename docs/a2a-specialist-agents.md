# A2A Specialist Agents — Architecture

## Overview

A2A (Agent-to-Agent) specialist agents provide parallel, domain-specific investigation for automated alert triage. Primary path uses Gemini (free API tier); falls back to local qwen when quota exhausted.

| System | Interface | Purpose |
|--------|-----------|---------|
| Claude-Gemini Collab | CLI | Plan reviews (stays separate) |
| A2A Specialists | REST API | Alert triage (Gemini primary) |
| Local LLM Fallback | Internal | Degraded mode when API unavailable |

---

## Architecture

```
Keep Alert
    │
    ▼
A2A Orchestrator (Gemini Pro)
    │
    ├── Success ──► Specialists (Gemini Flash, parallel)
    │                   ├──► DevOps ──► infrastructure-mcp
    │                   ├──► Network ──► infrastructure-mcp, home-mcp
    │                   ├──► Security ──► infrastructure-mcp
    │                   ├──► SRE ──► observability-mcp
    │                   └──► Database ──► knowledge-mcp
    │                   │
    │                   ▼
    │              Synthesis + Evidence
    │
    └── 429/Quota ──► Fallback to qwen (degraded)
    │
    ▼
Matrix (approval with findings)
```

### Fallback Logic

When Gemini API quota exhausted, falls back to local qwen:

```python
async def investigate(alert: Alert) -> Investigation:
    try:
        return await a2a_orchestrator.investigate(alert)
    except (RateLimitError, QuotaExhaustedError):
        logger.warning("Gemini quota exhausted, using qwen fallback")
        return await qwen_fallback.assess(alert)
```

- **Gemini available**: Full parallel investigation with MCP tools
- **Quota exhausted**: Single-model assessment (degraded but functional)

---

## 5-Agent MVP

| Agent | Domain | MCP Access | Alert Types |
|-------|--------|------------|-------------|
| DevOps | K8s, pods, deployments | infrastructure | PodCrashLoop, OOM, ImagePull |
| Network | DNS, routing, firewall | infrastructure, home | DNS failures, connectivity |
| Security | Secrets, auth | infrastructure | Auth failures, cert expiry |
| SRE | Metrics, incidents | observability | Latency, anomalies |
| Database | Qdrant, Neo4j, PG | knowledge | Query failures, sync |

---

## API Endpoints

### Orchestrator Service

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/investigate` | POST | Alert investigation |
| `/v1/agents` | GET | List active agents |
| `/health` | GET | Health check |

### Request Schema

```json
{
  "request_id": "uuid",
  "alert": {
    "name": "PodCrashLooping",
    "labels": {"namespace": "prod", "pod": "my-app"},
    "severity": "critical"
  },
  "context": {
    "source": "langgraph",
    "urgency": "high"
  }
}
```

### Response Schema

```json
{
  "request_id": "uuid",
  "verdict": "ACTIONABLE",
  "confidence": 0.92,
  "findings": [
    {
      "agent": "devops",
      "status": "FAIL",
      "issue": "Pod OOMKilled",
      "evidence": "kubectl logs: OOMKilled, limit=256Mi",
      "recommendation": "Increase memory to 512Mi"
    }
  ],
  "synthesis": "Pod OOMKilled due to insufficient memory.",
  "suggested_action": "kubectl patch deployment..."
}
```

---

## LangGraph Integration

Add investigation node before runbook matching:

```python
async def investigate_with_a2a(state: IncidentState) -> IncidentState:
    """Call A2A orchestrator for specialist investigation."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://a2a-orchestrator.ai-platform.svc.cluster.local:8000/v1/investigate",
            json={
                "request_id": state.incident_id,
                "alert": state.alert,
                "context": {"source": "langgraph", "urgency": state.severity}
            },
            timeout=30.0
        )

        findings = response.json()
        state.a2a_findings = findings.get("findings", [])
        state.a2a_synthesis = findings.get("synthesis", "")
        state.suggested_action = findings.get("suggested_action")

    return state
```

Flow becomes:
```
assess_alert → investigate_with_a2a → match_runbook → generate_solution → ...
```

---

## Deployment

### Namespace

All A2A components deploy to `ai-platform` namespace in agentic cluster.

### Kubernetes Manifests

Location: `kubernetes/applications/a2a/`

```yaml
# orchestrator.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: a2a-orchestrator
  namespace: ai-platform
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: orchestrator
        image: ghcr.io/charlieshreck/a2a-orchestrator:latest
        env:
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: a2a-secrets
              key: OPENROUTER_API_KEY
        - name: INFRASTRUCTURE_MCP_URL
          value: "http://infrastructure-mcp:8000"
        - name: OBSERVABILITY_MCP_URL
          value: "http://observability-mcp:8000"
        - name: KNOWLEDGE_MCP_URL
          value: "http://knowledge-mcp:8000"
        - name: HOME_MCP_URL
          value: "http://home-mcp:8000"
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "500m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: a2a-orchestrator
  namespace: ai-platform
spec:
  selector:
    app: a2a-orchestrator
  ports:
  - port: 8000
    targetPort: 8000
```

### Secrets (Infisical)

Path: `/external/openrouter`
- `API_KEY` - OpenRouter API key for Gemini access

---

## Model Selection

| Component | Model | Reasoning |
|-----------|-------|-----------|
| Orchestrator | Gemini Pro | Synthesis, weighted judgment |
| Specialists | Gemini 2.0 Flash | Fast parallel investigation |
| LangGraph routing | qwen2.5:7b (local) | Simple domain identification |

Cost estimate: ~$0.001 per investigation (5 Flash calls + 1 Pro synthesis)

---

## Relationship to Collaboration Workflow

The CLI-based Claude-Gemini collaboration is **separate**:

| Aspect | Collaboration (CLI) | A2A (API) |
|--------|---------------------|-----------|
| Trigger | Human | Automated |
| Model | Gemini Pro via CLI | Gemini Flash/Pro via API |
| History | Outline | Qdrant |
| Purpose | Plan review | Alert triage |

Gemini CLI now has MCP access (infrastructure, observability, knowledge, home) for plan validation. A2A agents handle the automated reactive path.

---

## Related Documents

- [Outline: A2A Specialist Agents — Unified Architecture](https://outline.kernow.io/doc/8141288b-6a7e-4973-8f40-b37df233a68b)
- [Project 04: LangGraph Incident Flow](../kubernetes/applications/langgraph/README.md)
- [unified-architecture-updated.md](./unified-architecture-updated.md)
