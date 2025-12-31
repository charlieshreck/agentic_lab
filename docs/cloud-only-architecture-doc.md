# Cloud-Native Homelab AI Agent Architecture
## Gemini + Claude with Human-in-the-Loop Autonomy

---

## Executive Summary

This architecture delivers an intelligent, self-improving homelab management system using **cloud LLMs exclusively** (Google Gemini as primary, Anthropic Claude for premium tasks). By eliminating local inference, the system becomes dramatically simpler to deploy and maintain while gaining access to superior reasoning capabilities.

**Design Philosophy**: Start verbose, learn what matters, earn autonomy through demonstrated reliability.

**Key Characteristics:**
- **No local LLM** - all inference via Gemini/Claude APIs
- **Human approval workflow** - Signal/Mattermost notifications with chat-based approval
- **Progressive autonomy** - runbooks graduate from "ask human" to "auto-execute"
- **MCP integration** - custom servers for Home Assistant, *arr suite, infrastructure
- **GitOps-native** - Renovate handles updates, PRs are the approval mechanism
- **Learning system** - every approved fix becomes a documented, reusable pattern

**Target Platform**: Any Linux host with Docker/Kubernetes (Raspberry Pi 5 to full server)

---

## Part I: Infrastructure Layer

### Recommended: Proxmox + K3s VM

With cloud-only inference, the UM690L becomes a general-purpose homelab host rather than a dedicated AI inference node. Proxmox provides flexibility for consolidation.

```
UM690L (32GB RAM, 1.5TB NVMe)
└── Proxmox VE 8.x
    │
    ├── AI Platform VM (Debian 12 + K3s)
    │   ├── CPU: 4 cores
    │   ├── RAM: 8GB (expandable)
    │   ├── Disk: 100GB
    │   └── Contains: LiteLLM, LangGraph, MCP servers, Signal
    │
    ├── Monitoring VM (optional, or in K3s)
    │   ├── CPU: 2 cores
    │   ├── RAM: 4GB
    │   └── Contains: Coroot, Prometheus, Grafana
    │
    └── Available for consolidation: ~20GB RAM
        ├── Home Assistant (if migrating)
        ├── Development/testing
        └── Future expansion
```

### VM Setup

```bash
# Create VM
qm create 100 --name ai-platform --memory 8192 --cores 4 \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci

# Attach Debian 12 ISO and install minimal
qm set 100 --ide2 local:iso/debian-12-netinst.iso,media=cdrom
qm set 100 --boot order=ide2

# After install, add disk
qm set 100 --scsi0 local-lvm:100

# Start and install K3s
qm start 100
```

### K3s Installation (Inside VM)

```bash
# Install K3s (single node, no traefik - use ingress-nginx)
curl -sfL https://get.k3s.io | sh -s - \
  --disable traefik \
  --write-kubeconfig-mode 644

# Get kubeconfig
cat /etc/rancher/k3s/k3s.yaml
```

### Why Not Talos for Cloud-Only?

| Factor | Talos | Proxmox + K3s |
|--------|-------|---------------|
| RAM overhead | 600MB | 2GB + 500MB (negligible with 32GB) |
| Debugging | API only, no shell | Full shell access |
| Flexibility | K8s only | VMs, LXCs, containers |
| Learning curve | Steep | Already known |
| Consolidation | Single purpose | Multi-workload |
| Snapshots | External backup | Native `qm snapshot` |

The original Talos recommendation was for **maximizing inference performance**. Without local inference, Proxmox's flexibility wins.

---

## Part II: Architecture Overview

### What's In vs Out

| Component | Status | Rationale |
|-----------|--------|-----------|
| Local LLM (Ollama) | ❌ Removed | Gemini subscription covers usage |
| GPU drivers/tuning | ❌ Removed | No inference workload |
| Model management | ❌ Removed | No quantization, no updates |
| Vector database | ❌ Removed | Cloud handles embeddings |
| MCP Servers | ✅ Required | Bridge to homelab applications |
| Human-in-the-loop | ✅ Required | Core approval mechanism |
| Runbook learning | ✅ Required | Path to autonomy |
| Observability | ✅ Required | Coroot anomaly detection |
| GitOps | ✅ Required | Infrastructure management |
| PII filtering | ⚠️ Optional | Local Presidio if needed |

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DETECTION LAYER                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Coroot  │  │Prometheus│  │ Renovate │  │Scheduled │            │
│  │ Anomaly  │  │  Alerts  │  │   PRs    │  │ Queries  │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  LangGraph  │  │   LiteLLM   │  │  Runbook    │                 │
│  │  Workflows  │◄─┤    Proxy    │  │  Database   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          │                ▼                │
          │  ┌─────────────────────────────────────┐
          │  │         CLOUD LLM LAYER             │
          │  │  ┌─────────────────────────────┐   │
          │  │  │    Gemini (Primary)         │   │
          │  │  │  Flash │ Pro │ Thinking     │   │
          │  │  └─────────────────────────────┘   │
          │  │  ┌─────────────────────────────┐   │
          │  │  │    Claude (Premium)         │   │
          │  │  │  Sonnet │ Opus              │   │
          │  │  └─────────────────────────────┘   │
          │  └─────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MCP TOOL LAYER                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │    Home    │ │    Arr     │ │   Infra    │ │    Plex    │       │
│  │  Assistant │ │   Suite    │ │    MCP     │ │    MCP     │       │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘       │
└────────┼──────────────┼──────────────┼──────────────┼───────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
    │   HA    │   │  Sonarr  │   │   K8s    │   │  Plex   │
    │ Tasmota │   │  Radarr  │   │  ArgoCD  │   │Tautulli │
    └─────────┘   └──────────┘   └──────────┘   └─────────┘

                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   HUMAN-IN-THE-LOOP LAYER                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Signal    │  │  Approval   │  │   Weekly    │                 │
│  │   Bridge    │◄─┤   Handler   │  │   Reports   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part II: Cloud LLM Strategy

### Model Selection

| Model | Use Case | When to Use |
|-------|----------|-------------|
| **Gemini Flash** | Triage, simple queries | "Is this a problem?" |
| **Gemini Pro** | Solution research, analysis | "How do I fix this?" |
| **Gemini Thinking** | Complex reasoning | Multi-step planning |
| **Claude Sonnet** | Premium code review | Critical infrastructure code |
| **Claude Opus** | Architecture decisions | Rare, high-stakes choices |

### Routing Logic

```python
"""Simple routing without local triage LLM."""

def route_to_model(query: str, context: dict) -> str:
    """Route based on query characteristics and runbook matching."""
    
    # Priority 1: Check runbooks first (no LLM needed)
    if runbook := match_runbook(query, context):
        if runbook.is_standard_change:
            return "execute_directly"
        return "gemini-flash"  # Quick confirmation
    
    # Priority 2: Keyword-based classification
    query_type = classify_by_keywords(query)
    
    routing_map = {
        "triage": "gemini-flash",
        "solution": "gemini-pro",
        "code": "gemini-pro",  # Default to Gemini
        "code_critical": "claude-sonnet",  # Infra code
        "architecture": "claude-opus",
        "complex": "gemini-thinking",
        "default": "gemini-flash"
    }
    
    return routing_map.get(query_type, "gemini-flash")


def classify_by_keywords(query: str) -> str:
    """Fast keyword matching - no API call needed."""
    q = query.lower()
    
    # Triage patterns
    if any(w in q for w in ["is this", "problem", "issue", "alert", "anomaly"]):
        return "triage"
    
    # Solution patterns
    if any(w in q for w in ["fix", "solve", "resolve", "how to", "help with"]):
        return "solution"
    
    # Code patterns
    if any(w in q for w in ["write", "implement", "create", "code", "script"]):
        if any(w in q for w in ["terraform", "firewall", "network", "security"]):
            return "code_critical"
        return "code"
    
    # Architecture patterns
    if any(w in q for w in ["architect", "design", "restructure", "migrate"]):
        return "architecture"
    
    # Complex reasoning
    if any(w in q for w in ["compare", "trade-off", "evaluate", "analyze deeply"]):
        return "complex"
    
    return "default"
```

### LiteLLM Configuration

```yaml
# litellm-config.yaml
model_list:
  # Gemini - Primary (Subscription - Unlimited)
  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
      
  - model_name: gemini-pro
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GEMINI_API_KEY
      
  - model_name: gemini-thinking
    litellm_params:
      model: gemini/gemini-2.0-flash-thinking-exp
      api_key: os.environ/GEMINI_API_KEY

  # Claude - Premium (Subscription - Quota Limited)
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_budget: 25.00
      
  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_budget: 50.00

router_settings:
  routing_strategy: simple-shuffle
  redis_host: redis
  redis_port: 6379

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

### Claude Quota Management

```yaml
# Track usage in Redis
quota_config:
  claude_sonnet:
    daily_limit: 20
    weekly_limit: 100
    alert_at: 0.7  # Notify at 70%
    
  claude_opus:
    daily_limit: 5
    weekly_limit: 20
    alert_at: 0.5  # Early warning
    
  fallback_chain:
    - gemini-thinking
    - gemini-pro
    - gemini-flash
```

---

## Part III: Human-in-the-Loop Framework

### The Approval Loop

```
Detection (Coroot/Prometheus/Renovate)
         │
         ▼
┌─────────────────────────────────────────┐
│  Signal: "🔔 Issue Detected"            │
│                                         │
│  Radarr memory at 95%                   │
│                                         │
│  Is this a problem?                     │
│  [Yes] [No, expected] [Snooze 1h]       │
└─────────────────────────────────────────┘
         │
         │ "Yes"
         ▼
┌─────────────────────────────────────────┐
│  Gemini Pro researches solutions...     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Signal: "📋 Solutions Found"           │
│                                         │
│  1. Increase memory 1GB → 2GB           │
│     Impact: 30s restart                 │
│     Risk: Low, reversible               │
│                                         │
│  2. Restart pod (temporary fix)         │
│     Impact: 30s restart                 │
│     Risk: Low, will recur               │
│                                         │
│  3. Investigate leak (diagnostic)       │
│     Impact: None                        │
│     Risk: None                          │
│                                         │
│  Reply: 1, 2, 3, ignore, or custom      │
└─────────────────────────────────────────┘
         │
         │ "1"
         ▼
┌─────────────────────────────────────────┐
│  Execute via MCP infrastructure tools   │
│  kubectl patch deployment/radarr ...    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Signal: "✅ Complete"                  │
│                                         │
│  Radarr memory increased to 2GB         │
│  Status: Healthy (15 min)               │
│  Memory: 45% (was 95%)                  │
│                                         │
│  📝 Runbook created                     │
│  Next time: [Auto] [Ask] [Investigate]  │
└─────────────────────────────────────────┘
```

### Signal Message Commands

| Command | Action |
|---------|--------|
| `1`, `2`, `3` | Select numbered solution |
| `approve` | Approve current action/PR |
| `ignore` | Take no action, learn preference |
| `snooze 2h` | Ask again in 2 hours |
| `details` | Request more context |
| `custom: restart all arr` | Execute custom instruction |
| `approve PR 47` | Merge specific Renovate PR |
| `status` | Show pending approvals |
| `weekly` | Trigger weekly report now |

### PR Approval Flow

Renovate creates PRs → AI enriches with context → Signal notification → Chat approval

```
📦 Renovate PR #47: Sonarr 4.0.1 → 4.0.2

Changes:
• Bug fix: RSS sync memory leak
• Bug fix: Custom format scoring
• No breaking changes

AI Assessment:
• Safe to merge (no breaking changes)
• Relevant: Memory leak fix matches your recent restarts
• Previous version: Stable 14 days

[approve] [defer] [details] [reject]

─────────────────────────

You: approve

─────────────────────────

✅ PR #47 merged
ArgoCD syncing... (2 min)

─────────────────────────

✅ Sonarr 4.0.2 deployed
• Health checks: Passing
• RSS sync: Completed
• Memory: 340MB (was 380MB avg)
```

### Runbook Learning

Every approved action becomes a runbook:

```yaml
# runbooks/radarr-memory-pressure.yaml
id: radarr-memory-pressure-001
created: 2025-12-21
trigger:
  metric: container_memory_usage_bytes{pod=~"radarr.*"}
  condition: "> 90%"
  duration: 5m

solutions:
  - id: increase_memory
    action: kubectl_patch
    human_selected: 4  # Times chosen
    success_rate: 1.0  # 4/4
    
  - id: restart_pod
    action: kubectl_rollout_restart
    human_selected: 1
    success_rate: 1.0

automation_level: ask_human  # Will promote after 5 successes

promotion_criteria:
  min_approvals: 5
  min_success_rate: 0.95
  blast_radius: single_pod
```

### Progressive Autonomy

```
Month 1-2: VERBOSE MODE
├── Every anomaly → Signal notification
├── Every action → Approval required
├── Daily summary reports
└── Goal: Build baseline, learn patterns

Month 3-4: LEARNING MODE
├── Suggest "this looks like standard change"
├── Batch low-priority notifications
├── Weekly reports replace daily
└── Goal: Identify automation candidates

Month 5-6: SELECTIVE AUTOMATION
├── Promoted runbooks auto-execute
├── Notify post-hoc for standard changes
├── New patterns still need approval
└── Goal: Reduce notification noise

Month 7+: MATURE OPERATION
├── Standard changes: auto + weekly summary
├── Known patterns: auto + immediate notify
├── New patterns: full approval
├── Quarterly trust reviews
└── Goal: Only see what matters
```

---

## Part IV: MCP Server Layer

### Why MCP Servers Still Required

Cloud LLMs can reason about your homelab, but they can't **act** on it without tool access. MCP servers bridge this gap.

```
Gemini: "I recommend restarting Radarr"
         │
         ▼
MCP Server: kubectl rollout restart deployment/radarr
         │
         ▼
Kubernetes: Actually restarts the pod
```

### Server Inventory

| Server | Target Apps | Tools Exposed |
|--------|-------------|---------------|
| `home-assistant-mcp` | HA, Tasmota, Google Home | lights, climate, automations, sensors |
| `arr-suite-mcp` | Sonarr, Radarr, Prowlarr | search, add, queue, status |
| `infrastructure-mcp` | K8s, ArgoCD, MinIO | pods, logs, restart, sync |
| `plex-mcp` | Plex, Tautulli | library, sessions, stats |
| `network-mcp` | OPNsense, Cloudflare | rules, tunnels, DNS |

### Base MCP Server Template

```python
#!/usr/bin/env python3
"""Base MCP server for homelab tools."""
import os
from fastmcp import FastMCP

mcp = FastMCP(
    name="homelab-mcp",
    instructions="Tools for homelab automation."
)

@mcp.resource("health://status")
def health() -> str:
    return "healthy"

def main():
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
```

### Home Assistant MCP

```python
"""Home Assistant tools."""
import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(name="home-assistant-mcp")
HA_URL = os.environ["HA_URL"]
HA_TOKEN = os.environ["HA_TOKEN"]

async def ha_api(method: str, endpoint: str, data: dict = None):
    async with httpx.AsyncClient() as client:
        r = await client.request(
            method, f"{HA_URL}/api/{endpoint}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            json=data, timeout=30
        )
        r.raise_for_status()
        return r.json()

@mcp.tool()
async def list_lights() -> list:
    """List all lights and their state."""
    states = await ha_api("GET", "states")
    return [
        {"entity_id": s["entity_id"], "state": s["state"]}
        for s in states if s["entity_id"].startswith("light.")
    ]

@mcp.tool()
async def turn_on_light(entity_id: str, brightness: int = None) -> str:
    """Turn on a light. Brightness 0-255 optional."""
    data = {"entity_id": entity_id}
    if brightness:
        data["brightness"] = brightness
    await ha_api("POST", "services/light/turn_on", data)
    return f"Turned on {entity_id}"

@mcp.tool()
async def turn_off_light(entity_id: str) -> str:
    """Turn off a light."""
    await ha_api("POST", "services/light/turn_off", {"entity_id": entity_id})
    return f"Turned off {entity_id}"

@mcp.tool()
async def run_automation(automation_id: str) -> str:
    """Trigger a Home Assistant automation."""
    await ha_api("POST", "services/automation/trigger", {"entity_id": automation_id})
    return f"Triggered {automation_id}"
```

### Infrastructure MCP

```python
"""Kubernetes and ArgoCD tools."""
import subprocess
import json
from fastmcp import FastMCP

mcp = FastMCP(name="infrastructure-mcp")

def kubectl(args: list) -> dict:
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True, text=True
    )
    return {
        "success": result.returncode == 0,
        "output": result.stdout or result.stderr
    }

@mcp.tool()
async def get_pods(namespace: str = "default") -> list:
    """List pods in namespace."""
    result = kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    if not result["success"]:
        return {"error": result["output"]}
    
    data = json.loads(result["output"])
    return [
        {
            "name": p["metadata"]["name"],
            "status": p["status"]["phase"],
            "restarts": sum(
                c.get("restartCount", 0)
                for c in p["status"].get("containerStatuses", [])
            )
        }
        for p in data.get("items", [])
    ]

@mcp.tool()
async def get_logs(pod: str, namespace: str = "default", lines: int = 50) -> str:
    """Get pod logs."""
    result = kubectl(["logs", pod, "-n", namespace, f"--tail={lines}"])
    return result["output"]

@mcp.tool()
async def restart_deployment(name: str, namespace: str = "default") -> str:
    """Restart a deployment."""
    result = kubectl(["rollout", "restart", "deployment", name, "-n", namespace])
    return result["output"]

@mcp.tool()
async def argocd_sync(app: str) -> str:
    """Sync ArgoCD application."""
    result = subprocess.run(
        ["argocd", "app", "sync", app, "--prune"],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: home-assistant-mcp
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: home-assistant-mcp
  template:
    metadata:
      labels:
        app: home-assistant-mcp
    spec:
      containers:
        - name: mcp
          image: ghcr.io/yourrepo/home-assistant-mcp:latest
          ports:
            - containerPort: 8000
          env:
            - name: HA_URL
              value: "http://home-assistant:8123"
            - name: HA_TOKEN
              valueFrom:
                secretKeyRef:
                  name: mcp-secrets
                  key: ha-token
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "200m"
```

---

## Part V: Observability

### Stack

| Tool | Purpose | Resource Usage |
|------|---------|----------------|
| **Coroot** | Anomaly detection (eBPF) | ~500MB |
| **Prometheus** | Metrics collection | ~500MB |
| **Grafana** | Dashboards (optional) | ~200MB |
| **Langfuse** | LLM tracing (optional) | ~300MB |

### Coroot Configuration

Coroot provides automatic anomaly detection without manual threshold configuration:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coroot
  namespace: monitoring
spec:
  template:
    spec:
      containers:
        - name: coroot
          image: ghcr.io/coroot/coroot:latest
          ports:
            - containerPort: 8080
          env:
            - name: BOOTSTRAP_PROMETHEUS_URL
              value: "http://prometheus:9090"
          resources:
            requests:
              memory: "256Mi"
            limits:
              memory: "512Mi"
```

### Alert → LLM Pipeline

```yaml
# alertmanager-config.yaml
receivers:
  - name: ai-triage
    webhook_configs:
      - url: http://langgraph:8000/webhook/alert
        send_resolved: true

route:
  receiver: ai-triage
  group_wait: 30s
  group_interval: 5m
```

```python
# langgraph webhook handler
@app.post("/webhook/alert")
async def handle_alert(alert: dict):
    """Receive Prometheus alert, triage with Gemini."""
    
    # Format alert for LLM
    prompt = f"""
    Alert received:
    - Name: {alert['labels']['alertname']}
    - Severity: {alert['labels']['severity']}
    - Description: {alert['annotations']['description']}
    
    Recent metrics context:
    {get_recent_metrics(alert['labels'])}
    
    Is this a real problem requiring action?
    If yes, what are the likely causes and solutions?
    """
    
    # Check runbooks first
    if runbook := match_runbook(alert):
        if runbook.is_standard_change:
            await execute_runbook(runbook)
            await notify_signal(f"✅ Auto-fixed: {alert['labels']['alertname']}")
            return
    
    # Otherwise, ask Gemini
    response = await litellm.completion(
        model="gemini-flash",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Send to human for approval
    await request_approval(alert, response)
```

---

## Part VI: GitOps Integration

### Renovate + ArgoCD + Signal

```
Renovate Bot
     │
     │ Detects: sonarr:4.0.1 → 4.0.2
     ▼
┌─────────────────────────────────┐
│  Creates PR #47                 │
│  - Updates image tag            │
│  - Includes changelog link      │
└─────────────────────────────────┘
     │
     │ Webhook triggers LangGraph
     ▼
┌─────────────────────────────────┐
│  Gemini enriches PR:            │
│  - Summarizes changes           │
│  - Checks for breaking changes  │
│  - Notes relevant fixes         │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Signal notification:           │
│  📦 PR #47: Sonarr update       │
│  [approve] [defer] [reject]     │
└─────────────────────────────────┘
     │
     │ Human: "approve"
     ▼
┌─────────────────────────────────┐
│  GitHub API: Merge PR           │
└─────────────────────────────────┘
     │
     │ ArgoCD detects change
     ▼
┌─────────────────────────────────┐
│  ArgoCD syncs deployment        │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Signal: ✅ Deployed & healthy  │
└─────────────────────────────────┘
```

### Renovate Configuration

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:base"],
  "kubernetes": {
    "fileMatch": ["apps/.+\\.yaml$"]
  },
  "packageRules": [
    {
      "matchPackagePatterns": ["*"],
      "automerge": false,
      "labels": ["renovate", "dependencies"]
    },
    {
      "matchPackagePatterns": ["ghcr.io/linuxserver/*"],
      "groupName": "linuxserver images"
    }
  ],
  "prHourlyLimit": 2,
  "prConcurrentLimit": 5
}
```

### Repository Structure

```
homelab-gitops/
├── apps/
│   ├── home-assistant/
│   │   ├── deployment.yaml
│   │   └── kustomization.yaml
│   ├── sonarr/
│   ├── radarr/
│   ├── plex/
│   └── ai-platform/
│       ├── litellm/
│       ├── langgraph/
│       ├── signal-cli/
│       └── mcp-servers/
├── infrastructure/
│   ├── argocd/
│   ├── monitoring/
│   └── storage/
├── terraform/
│   └── talos/
├── secrets/
│   └── .sops.yaml
└── renovate.json
```

---

## Part VII: Scheduled Intelligence

### Proactive Queries

```yaml
# scheduled-queries.yaml
queries:
  - id: unifi-features
    schedule: "0 9 1 * *"  # Monthly
    prompt: |
      Check UniFi controller for new features:
      - Recent firmware updates
      - New settings available
      - Security recommendations
      Format as actionable items with effort ratings.
    delivery: signal

  - id: security-review
    schedule: "0 10 * * 1"  # Weekly Monday
    prompt: |
      Security posture review:
      - Containers running as root
      - Services without authentication
      - Certificates expiring soon
      - Failed login attempts
    delivery: signal

  - id: resource-optimization
    schedule: "0 9 15 * *"  # 15th monthly
    prompt: |
      Resource usage analysis:
      - Over-provisioned containers
      - Under-utilized storage
      - Bandwidth patterns
    delivery: signal

  - id: dependency-health
    schedule: "0 8 * * 0"  # Weekly Sunday
    prompt: |
      Dependency health check:
      - EOL software versions
      - Security vulnerabilities
      - Upcoming breaking changes
    delivery: signal
```

### Weekly Report

```
📊 Weekly Homelab Report (Dec 15-21)

Actions Taken:
├── Auto-executed: 8
│   └── Pod restarts (3), cache clears (5)
├── With approval: 3
│   └── Memory increase, PR merge, config change
└── Declined: 1
    └── Suggested library removal (you said keep)

Anomalies:
├── Detected: 12
├── True positives: 9
└── False positives: 3 (learned)

Runbooks:
├── New: 2
├── Promoted to standard: 1
└── Total: 24

Patterns Learned:
• You approve restarts within 5 min avg
• You prefer permanent fixes over temporary
• Plex transcoding alerts can be batched

Pending:
• 3 PRs awaiting review
• Monthly UniFi check (tomorrow)

Next Week:
• SSL renewal due Dec 24
• Quarterly storage review Dec 28
```

---

## Part VIII: Deployment

### Minimal Stack (10 containers)

```yaml
# docker-compose.yaml or Helm chart
services:
  # Core orchestration
  litellm:
    image: ghcr.io/berriai/litellm:main
    ports: ["4000:4000"]
    
  langgraph:
    image: ghcr.io/yourrepo/langgraph-homelab:latest
    
  redis:
    image: redis:7-alpine
    
  postgresql:
    image: postgres:16-alpine
    
  # Notifications
  signal-cli:
    image: bbernhard/signal-cli-rest-api:latest
    
  # Observability
  coroot:
    image: ghcr.io/coroot/coroot:latest
    
  prometheus:
    image: prom/prometheus:latest
    
  # MCP Servers
  mcp-home-assistant:
    image: ghcr.io/yourrepo/mcp-home-assistant:latest
    
  mcp-arr-suite:
    image: ghcr.io/yourrepo/mcp-arr-suite:latest
    
  mcp-infrastructure:
    image: ghcr.io/yourrepo/mcp-infrastructure:latest
```

### Resource Requirements

| Service | Memory | CPU |
|---------|--------|-----|
| LiteLLM | 256MB | 0.2 |
| LangGraph | 512MB | 0.3 |
| Redis | 128MB | 0.1 |
| PostgreSQL | 256MB | 0.2 |
| Signal CLI | 256MB | 0.1 |
| Coroot | 512MB | 0.3 |
| Prometheus | 512MB | 0.2 |
| MCP Servers (×3) | 384MB | 0.3 |
| **K3s overhead** | **~500MB** | **0.2** |
| **Total** | **~3.5GB** | **~2 cores** |

Allocate **8GB to the VM** for headroom. This leaves **~22GB** in Proxmox for other workloads.

---

## Part IX: Implementation Timeline

### Phase 1: Infrastructure (Week 1)
- [ ] Install Proxmox VE on UM690L (if not already)
- [ ] Create AI Platform VM (Debian 12, 8GB RAM, 4 cores)
- [ ] Install K3s single-node
- [ ] Set up ArgoCD + SOPS
- [ ] Configure Renovate on your GitOps repo
- [ ] Deploy Redis + PostgreSQL

### Phase 2: Cloud Integration (Week 2)
- [ ] Deploy LiteLLM with Gemini + Claude config
- [ ] Test API connectivity and routing
- [ ] Set up quota tracking in Redis
- [ ] Configure fallback chain

### Phase 3: MCP Servers (Week 2-3)
- [ ] Build home-assistant-mcp
- [ ] Build infrastructure-mcp
- [ ] Build arr-suite-mcp
- [ ] Test tool execution
- [ ] Deploy to cluster

### Phase 4: Observability (Week 3)
- [ ] Deploy Coroot
- [ ] Deploy Prometheus
- [ ] Configure AlertManager → webhook pipeline
- [ ] Test alert → LLM → notification flow

### Phase 5: Human-in-the-Loop (Week 4)
- [ ] Deploy Signal CLI (register number)
- [ ] Build notification service
- [ ] Build approval handler
- [ ] Configure message parsing
- [ ] Set up weekly report generation

### Phase 6: Go Live (Week 5)
- [ ] **Snapshot VM before enabling** (`qm snapshot 100 pre-golive`)
- [ ] Enable VERBOSE MODE
- [ ] Monitor all notifications for 1 week
- [ ] Create initial runbooks from approvals
- [ ] Tune false positive filters

### Phase 7: Learning (Month 2-3)
- [ ] Track approval patterns
- [ ] Identify promotion candidates
- [ ] Reduce notification frequency
- [ ] First standard change promotions
- [ ] Weekly review of auto-actions

### Phase 8: Mature Operation (Month 4+)
- [ ] Standard changes auto-execute
- [ ] Weekly reports replace daily
- [ ] Quarterly trust reviews
- [ ] Expand MCP server coverage

---

## Part X: Backup & Recovery

### Proxmox Native Backups

```bash
# Schedule daily VM backup
pvesh create /cluster/backup \
  --dow mon,tue,wed,thu,fri,sat,sun \
  --starttime 03:00 \
  --storage local \
  --vmid 100 \
  --mode snapshot \
  --compress zstd \
  --retention-daily 7 \
  --retention-weekly 4
```

### Pre-Change Snapshots

Before any significant change:
```bash
# Create snapshot
qm snapshot 100 pre-upgrade --description "Before ArgoCD upgrade"

# If it breaks
qm rollback 100 pre-upgrade

# If it works, clean up
qm delsnapshot 100 pre-upgrade
```

### Application-Level Backups

| Component | Strategy | Frequency |
|-----------|----------|-----------|
| PostgreSQL | pg_dump to MinIO | Every 6h |
| Redis | BGSAVE + copy to MinIO | Daily |
| Runbook YAML files | Git repository | On change |
| ArgoCD state | Git repository | On change |
| Coroot data | Prometheus snapshots | Daily |

### Disaster Recovery Plan

```
Level 1: Pod failure
└── K3s auto-restarts, ArgoCD self-heals

Level 2: Application state corruption  
└── Restore PostgreSQL from MinIO backup

Level 3: VM corruption
└── Rollback to Proxmox snapshot

Level 4: Host failure
└── Restore VM backup to new Proxmox host
└── Re-apply GitOps (ArgoCD rebuilds everything)

Level 5: Total loss
└── Fresh Proxmox + VM install
└── Clone GitOps repo
└── ArgoCD bootstraps everything
└── Restore state from offsite backup
```

---

## Part XI: Privacy Considerations

### Option A: Accept Cloud Processing
All queries go to Gemini. Google sees your homelab context.

**Acceptable if:**
- Homelab data isn't sensitive
- You trust Google's data handling
- Simplicity is priority

### Option B: Local PII Filter

Add Presidio (no LLM needed) to scrub sensitive data:

```yaml
presidio:
  image: mcr.microsoft.com/presidio-analyzer:latest
  resources:
    memory: "256Mi"
```

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def scrub_pii(text: str) -> str:
    results = analyzer.analyze(
        text, language='en',
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", 
                  "IP_ADDRESS", "CREDIT_CARD"]
    )
    return anonymizer.anonymize(text, results).text
```

### Option C: Sensitive Query Bypass

Flag certain query types to never send to cloud:

```python
NEVER_SEND_PATTERNS = [
    r"password", r"secret", r"api.key", r"token",
    r"192\.168\.", r"10\.\d+\.", r"172\.(1[6-9]|2\d|3[01])\."
]

def is_sensitive(query: str) -> bool:
    return any(re.search(p, query, re.I) for p in NEVER_SEND_PATTERNS)
```

---

## Appendix A: Proxmox Networking

### Bridge Configuration

```bash
# /etc/network/interfaces on Proxmox host
auto vmbr0
iface vmbr0 inet static
    address 192.168.1.10/24
    gateway 192.168.1.1
    bridge-ports enp1s0
    bridge-stp off
    bridge-fd 0
```

### VM Network

The AI Platform VM gets a static IP on your LAN:
```yaml
# Inside VM: /etc/netplan/00-installer-config.yaml
network:
  version: 2
  ethernets:
    ens18:
      addresses:
        - 192.168.1.20/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 192.168.1.1
```

### Service Access

MCP servers need to reach your homelab apps:
```
AI Platform VM (192.168.1.20)
├── → Home Assistant (192.168.1.30:8123)
├── → Sonarr (192.168.1.40:8989)
├── → Radarr (192.168.1.40:7878)
├── → OPNsense (192.168.1.1)
└── → Kubernetes API (localhost:6443)
```

Ensure firewall rules allow these connections (OPNsense or Proxmox firewall).

---

## Appendix B: Port Reference

| Service | Port |
|---------|------|
| LiteLLM | 4000 |
| LangGraph | 8000 |
| Signal CLI | 8080 |
| Coroot | 8081 |
| Prometheus | 9090 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MCP Servers | 8001-8010 |
| ArgoCD | 8443 |

---

## Appendix C: Environment Variables

```bash
# Cloud APIs
GEMINI_API_KEY=your-gemini-key
ANTHROPIC_API_KEY=your-claude-key
LITELLM_MASTER_KEY=sk-your-master-key

# GitHub (for PR approval)
GITHUB_TOKEN=ghp_your-token

# Signal
SIGNAL_NUMBER=+44XXXXXXXXXX

# MCP Secrets (via SOPS)
HA_TOKEN=your-ha-long-lived-token
SONARR_API_KEY=your-sonarr-key
RADARR_API_KEY=your-radarr-key
```

---

## Conclusion

The cloud-only architecture trades local inference for operational simplicity while gaining superior reasoning from Gemini Pro and Claude. Running on **Proxmox + K3s** provides the flexibility and debuggability appropriate for a homelab environment.

**What you get:**
- 90% simpler than local LLM deployment
- Better reasoning quality (Gemini Pro >> any 3B local model)
- Familiar Proxmox management
- Room to consolidate other workloads
- Easy VM snapshots for recovery
- Shell access when debugging

**What you accept:**
- API dependency (no offline operation)
- Data transits cloud providers
- ~500ms latency per query (irrelevant for approval workflow)

**Resource utilisation:**
```
UM690L (32GB)
├── Proxmox overhead     2GB
├── AI Platform VM       8GB
└── Available           22GB ← consolidation opportunity
```

**The core insight remains**: Start verbose, learn what matters, let the system earn autonomy through demonstrated reliability. The infrastructure choice (Proxmox vs Talos, cloud vs local) doesn't change the philosophy—pick what you'll actually maintain.