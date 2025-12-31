# Cloud-Native Homelab AI Agent Architecture
## Gemini + Claude with Human-in-the-Loop Autonomy

> **Note**: This is the cloud-only variant. For the recommended hybrid approach (local-first with cloud escalation), see `unified-architecture.md`.

---

## Executive Summary

This architecture delivers an intelligent, self-improving homelab management system using **cloud LLMs exclusively** (Google Gemini as primary, Anthropic Claude for premium tasks). By eliminating local inference, the system becomes dramatically simpler to deploy and maintain while gaining access to superior reasoning capabilities.

**Design Philosophy**: Start verbose, learn what matters, earn autonomy through demonstrated reliability.

**Key Characteristics:**
- **No local LLM** - all inference via Gemini/Claude APIs
- **Human approval workflow** - Telegram Forum with topic-based organization and inline keyboard approvals
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
    │   └── Contains: LiteLLM, LangGraph, MCP servers, Telegram service
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

---

## Part II: LLM Routing

### Model Selection

```python
"""Route queries to appropriate cloud model."""

def select_model(query: str, context: dict) -> str:
    """Select cloud model based on query type."""
    q = query.lower()
    
    # Triage patterns - use fast model
    if any(w in q for w in ["is this", "problem", "issue", "alert"]):
        return "gemini-flash"
    
    # Architecture/complex reasoning - use premium
    if any(w in q for w in ["architect", "design", "compare", "trade-off"]):
        return "claude-sonnet"
    
    # Code with security implications - use premium
    if any(w in q for w in ["terraform", "firewall", "security"]):
        return "claude-sonnet"
    
    # Default to fast model
    return "gemini-flash"
```

### LiteLLM Configuration

```yaml
# litellm-config.yaml
model_list:
  # Gemini - Primary
  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
      
  - model_name: gemini-pro
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GEMINI_API_KEY

  # Claude - Premium
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
```

---

## Part III: Human-in-the-Loop Framework

### Telegram Forum Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      TELEGRAM FORUM STRUCTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  🏠 Homelab Ops (Forum Supergroup)                                       │
│  ├── 📌 General                    # Default topic                       │
│  ├── 🔴 Critical Alerts            # Standing - high priority            │
│  ├── 🟡 Arr Suite                  # Standing - *arr domain              │
│  ├── 🔵 Infrastructure             # Standing - K8s/storage/network      │
│  ├── 🏠 Home Assistant             # Standing - HA domain                │
│  ├── 📊 Weekly Reports             # Standing - scheduled digests        │
│  ├── 🔧 Incident #47               # Dynamic - agent-created             │
│  └── ✅ Resolved                    # Standing - archive                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Approval Loop

```
Detection (Coroot/Prometheus/Renovate)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  🏠 Homelab Ops Forum                                            │
│  └── 🟡 Arr Suite                                                │
│      ┌─────────────────────────────────────────────────────────┐│
│      │ 🔔 Radarr memory at 95%                                 ││
│      │                                                          ││
│      │ Similar to: runbook-mem-001 (89%)                       ││
│      │ Last time: memory increase worked                        ││
│      │                                                          ││
│      │ [1️⃣ Increase] [2️⃣ Restart] [3️⃣ Investigate]            ││
│      │ [❌ Ignore]   [🔍 Details]                               ││
│      └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │
         │ Button: [1️⃣ Increase]
         ▼
    Execute via MCP → Document → Learn
```

### Telegram Commands

| Input | Action |
|-------|--------|
| Button: `1️⃣`, `2️⃣`, `3️⃣` | Select numbered solution |
| Button: `Approve` | Approve current action/PR |
| Button: `Ignore` | Take no action, record preference |
| Button: `Details` | Show extended diagnostics |
| Text: `status` | Show pending approvals |
| Text: `weekly` | Trigger weekly report now |
| Text: `custom: restart all arr` | Execute custom instruction |

### PR Approval Flow

```
📦 Renovate PR #47: Sonarr 4.0.1 → 4.0.2

Changes:
• Bug fix: RSS sync memory leak
• Bug fix: Custom format scoring
• No breaking changes

AI Assessment:
• Safe to merge (no breaking changes)
• Relevant: Memory leak fix matches recent restarts
• Previous version: Stable 14 days

[✅ Approve] [⏸️ Defer] [🔍 Details] [❌ Reject]

─────────────────────────────

You: [✅ Approve]

─────────────────────────────

✅ PR #47 merged
ArgoCD syncing... (2 min)

─────────────────────────────

✅ Sonarr 4.0.2 deployed
• Health checks: Passing
• RSS sync: Completed
• Memory: 340MB (was 380MB avg)
```

---

## Part IV: GitOps Integration

### Renovate + ArgoCD + Telegram

```
Renovate Bot
     │
     │ Detects: sonarr:4.0.1 → 4.0.2
     ▼
┌─────────────────────────────────────┐
│  Creates PR #47                      │
│  - Updates image tag                 │
│  - Includes changelog link           │
└─────────────────────────────────────┘
     │
     │ Webhook triggers LangGraph
     ▼
┌─────────────────────────────────────┐
│  Gemini enriches PR:                 │
│  - Summarizes changes                │
│  - Checks for breaking changes       │
│  - Notes relevant fixes              │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│  Telegram: 🔵 Infrastructure         │
│  📦 PR #47: Sonarr update            │
│  [✅ Approve] [⏸️ Defer] [❌ Reject] │
└─────────────────────────────────────┘
     │
     │ Button: [✅ Approve]
     ▼
┌─────────────────────────────────────┐
│  GitHub API: Merge PR                │
└─────────────────────────────────────┘
     │
     │ ArgoCD detects change
     ▼
┌─────────────────────────────────────┐
│  ArgoCD syncs deployment             │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│  Telegram: ✅ Deployed & healthy     │
└─────────────────────────────────────┘
```

### Repository Structure

```
homelab-gitops/
├── apps/
│   ├── home-assistant/
│   ├── sonarr/
│   ├── radarr/
│   ├── plex/
│   └── ai-platform/
│       ├── litellm/
│       ├── langgraph/
│       ├── telegram-service/
│       └── mcp-servers/
├── infrastructure/
│   ├── argocd/
│   ├── monitoring/
│   └── storage/
├── terraform/
├── secrets/
│   └── .sops.yaml
└── renovate.json
```

---

## Part V: Scheduled Intelligence

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
    delivery: telegram/infrastructure

  - id: security-review
    schedule: "0 10 * * 1"  # Weekly Monday
    prompt: |
      Security posture review:
      - Containers running as root
      - Services without authentication
      - Certificates expiring soon
    delivery: telegram/critical

  - id: dependency-health
    schedule: "0 8 * * 0"  # Weekly Sunday
    prompt: |
      Dependency health check:
      - EOL software versions
      - Security vulnerabilities
      - Upcoming breaking changes
    delivery: telegram/infrastructure
```

---

## Part VI: Implementation Timeline

### Phase 1: Infrastructure (Week 1)
- [ ] Install Proxmox VE on UM690L
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
- [ ] Create Telegram bot via @BotFather
- [ ] Create Forum supergroup
- [ ] Add bot as admin with can_manage_topics
- [ ] Deploy telegram-service
- [ ] Initialize standing topics
- [ ] Register webhook URL
- [ ] Test approval workflow with inline keyboards

### Phase 6: Go Live (Week 5)
- [ ] **Snapshot VM before enabling**
- [ ] Enable VERBOSE MODE
- [ ] Monitor all notifications for 1 week
- [ ] Create initial runbooks from approvals
- [ ] Tune false positive filters

### Phase 7: Learning (Month 2-3)
- [ ] Track approval patterns
- [ ] Identify promotion candidates
- [ ] First standard change promotions

---

## Appendix: Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| LiteLLM | 4000 | HTTP |
| LangGraph | 8000 | HTTP |
| Telegram Service | 8080 | HTTP |
| MCP Servers | 8001-8010 | HTTP/SSE |
| Prometheus | 9090 | HTTP |
| Grafana | 3000 | HTTP |
| Coroot | 8081 | HTTP |
| ArgoCD | 8443 | HTTPS |

## Appendix: Environment Variables

```bash
# Cloud APIs
GEMINI_API_KEY=your-gemini-key
ANTHROPIC_API_KEY=your-claude-key
LITELLM_MASTER_KEY=sk-your-master-key

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_FORUM_CHAT_ID=-100xxxxxxxxxx
TELEGRAM_WEBHOOK_URL=https://telegram-webhook.yourdomain.com/webhook

# GitHub (for PR approval)
GITHUB_TOKEN=ghp_your-token

# MCP Secrets (via SOPS)
HA_TOKEN=your-ha-long-lived-token
SONARR_API_KEY=your-sonarr-key
RADARR_API_KEY=your-radarr-key
```

---

## Conclusion

The cloud-only architecture trades local inference for operational simplicity while gaining superior reasoning from Gemini and Claude.

**What you get:**
- 90% simpler than local LLM deployment
- Better reasoning quality
- No GPU requirements
- Telegram Forum for organized, scalable notifications

**What you accept:**
- API dependency (no offline operation)
- Data transits cloud providers
- ~500ms latency per query

> **Consider the hybrid approach** in `unified-architecture.md` if you want local-first with cloud escalation capability.
