# Cyclical Learning Agentic AI Platform
## Talos Bare Metal + Local/Cloud Hybrid + Vector Knowledge Base

---

## Executive Summary

This architecture delivers a **self-improving homelab AI agent** that learns from every interaction, builds institutional knowledge, and progressively earns autonomy. It combines local inference for speed and privacy with cloud escalation for complex reasoning, unified by a vector knowledge base that enables genuine learning.

**Core Capabilities:**
- **Flexible inference**: Local Ollama, Cloud Gemini/Claude, or hybrid - switchable per-request
- **Persistent knowledge**: Vector DB stores decisions, outcomes, and learnings
- **Cyclical learning**: Every action feeds back into the knowledge base
- **Progressive autonomy**: System earns trust through demonstrated reliability
- **Human-in-the-loop**: Telegram Forum with topic-based organization and inline keyboard approvals

**Philosophy**: The AI doesn't just execute tasks—it remembers what worked, learns your preferences, and gets smarter over time.

---

## Part I: The Learning Loop

### The Cyclical Intelligence Model

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         THE LEARNING CYCLE                                │
│                                                                           │
│    ┌──────────┐                                      ┌──────────┐        │
│    │  DETECT  │                                      │  LEARN   │        │
│    │  Event   │                                      │  Update  │        │
│    │  occurs  │                                      │  vectors │        │
│    └────┬─────┘                                      └────▲─────┘        │
│         │                                                 │              │
│         ▼                                                 │              │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐      │              │
│    │ RETRIEVE │      │  REASON  │      │   ACT    │      │              │
│    │ Similar  │─────▶│  Decide  │─────▶│ Execute  │──────┘              │
│    │ contexts │      │  action  │      │  + log   │                     │
│    └──────────┘      └──────────┘      └──────────┘                     │
│         ▲                                                                │
│         │                                                                │
│    ┌────┴─────┐                                                         │
│    │  VECTOR  │  ◄── Runbooks, decisions, outcomes, preferences         │
│    │    DB    │  ◄── System state snapshots, documentation              │
│    │ (Qdrant) │  ◄── Conversation history, human feedback               │
│    └──────────┘                                                         │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### What Gets Learned

| Knowledge Type | Source | How It's Used |
|----------------|--------|---------------|
| **Runbooks** | Approved fixes | "I've seen this before, solution X worked" |
| **Outcomes** | Post-action monitoring | "Last time this fix caused Y" |
| **Preferences** | Human approvals/rejections | "Charlie prefers permanent fixes" |
| **Context** | System state at decision time | "This happened during high load" |
| **Documentation** | Ingested docs, READMEs | "The Sonarr API works like this" |
| **Conversations** | Past interactions | "We discussed this architecture before" |

---

## Part II: Hybrid Inference Layer

### Inference Modes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INFERENCE MODE SELECTION                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│  │ LOCAL_FIRST │     │ CLOUD_ONLY  │     │ LOCAL_ONLY  │                │
│  │  (Default)  │     │  (Bypass)   │     │  (Offline)  │                │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                │
│         │                   │                   │                        │
│         ▼                   ▼                   ▼                        │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│  │   Ollama    │     │   Gemini    │     │   Ollama    │                │
│  │  qwen2.5:7b │     │    Flash    │     │  qwen2.5:7b │                │
│  └──────┬──────┘     └─────────────┘     └─────────────┘                │
│         │                                                                │
│         ▼                                                                │
│  ┌─────────────┐                                                        │
│  │ Confidence  │                                                        │
│  │   < 0.7?    │                                                        │
│  └──────┬──────┘                                                        │
│    Yes  │  No                                                           │
│         ▼                                                                │
│  ┌─────────────┐     ┌─────────────┐                                    │
│  │  Escalate   │     │   Return    │                                    │
│  │  to Cloud   │     │   Result    │                                    │
│  └─────────────┘     └─────────────┘                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Mode Configuration

| Mode | Behavior | Use Case |
|------|----------|----------|
| `local_first` | Try Ollama → escalate if confidence < threshold | Default operation |
| `cloud_only` | Skip local, go directly to Gemini/Claude | Complex tasks, bypass local |
| `local_only` | Never use cloud APIs | Offline, privacy-critical |
| `cloud_first` | Try cloud → fallback to local if API fails | When quality is priority |

### Mode Switching

```bash
# Set globally via ConfigMap
kubectl patch configmap ai-config -n ai-platform \
  --patch '{"data": {"INFERENCE_MODE": "local_first"}}'

# Override per-request via header
curl -X POST http://langgraph:8000/invoke \
  -H "X-Inference-Mode: cloud_only" \
  -d '{"query": "complex architecture question"}'

# Telegram command to switch mode
# In any topic, send: /mode cloud_only
```

### LiteLLM Routing Configuration

```yaml
# litellm-config.yaml
model_list:
  # Local Models (Ollama)
  - model_name: local/qwen2.5:7b
    litellm_params:
      model: ollama/qwen2.5:7b
      api_base: http://ollama:11434
      
  - model_name: local/qwen2.5:3b
    litellm_params:
      model: ollama/qwen2.5:3b
      api_base: http://ollama:11434

  # Cloud Models (Gemini - Primary)
  - model_name: cloud/gemini-flash
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
      
  - model_name: cloud/gemini-pro
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GEMINI_API_KEY

  # Cloud Models (Claude - Premium)
  - model_name: cloud/claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY

router_settings:
  routing_strategy: simple-shuffle
  redis_host: redis
  redis_port: 6379
```

### Inference Router Logic

```python
"""Inference router with mode selection and confidence-based escalation."""

from enum import Enum
from dataclasses import dataclass
import litellm

class InferenceMode(Enum):
    LOCAL_FIRST = "local_first"
    CLOUD_ONLY = "cloud_only"
    LOCAL_ONLY = "local_only"
    CLOUD_FIRST = "cloud_first"

@dataclass
class InferenceResult:
    response: str
    model_used: str
    confidence: float
    escalated: bool

class InferenceRouter:
    """Routes inference requests based on mode and confidence."""
    
    def __init__(
        self,
        local_model: str = "local/qwen2.5:7b",
        cloud_model: str = "cloud/gemini-flash",
        escalation_threshold: float = 0.7,
        default_mode: InferenceMode = InferenceMode.LOCAL_FIRST
    ):
        self.local_model = local_model
        self.cloud_model = cloud_model
        self.threshold = escalation_threshold
        self.default_mode = default_mode
    
    async def infer(
        self,
        prompt: str,
        mode: InferenceMode = None,
        force_model: str = None
    ) -> InferenceResult:
        """Execute inference with mode-based routing."""
        
        mode = mode or self.default_mode
        
        # Direct model override
        if force_model:
            return await self._call_model(force_model, prompt)
        
        # Mode-based routing
        if mode == InferenceMode.CLOUD_ONLY:
            return await self._call_model(self.cloud_model, prompt)
        
        if mode == InferenceMode.LOCAL_ONLY:
            return await self._call_model(self.local_model, prompt)
        
        if mode == InferenceMode.CLOUD_FIRST:
            try:
                return await self._call_model(self.cloud_model, prompt)
            except Exception:
                return await self._call_model(self.local_model, prompt)
        
        # LOCAL_FIRST (default): Try local, escalate if needed
        result = await self._call_model(self.local_model, prompt)
        
        if result.confidence < self.threshold:
            cloud_result = await self._call_model(self.cloud_model, prompt)
            cloud_result.escalated = True
            return cloud_result
        
        return result
    
    async def _call_model(self, model: str, prompt: str) -> InferenceResult:
        """Call a specific model via LiteLLM."""
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract confidence from response metadata or estimate
        confidence = self._estimate_confidence(response)
        
        return InferenceResult(
            response=response.choices[0].message.content,
            model_used=model,
            confidence=confidence,
            escalated=False
        )
    
    def _estimate_confidence(self, response) -> float:
        """Estimate confidence based on response characteristics."""
        text = response.choices[0].message.content.lower()
        
        # Low confidence indicators
        uncertain_phrases = [
            "i'm not sure", "i think", "possibly", "might be",
            "i don't know", "unclear", "uncertain"
        ]
        
        if any(phrase in text for phrase in uncertain_phrases):
            return 0.5
        
        # Check for hedging
        if text.count("maybe") > 1 or text.count("perhaps") > 1:
            return 0.6
        
        return 0.85  # Default confidence
```

---

## Part III: Human-in-the-Loop Layer

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
│  Agent Capabilities:                                                     │
│  • Create/close/reopen topics dynamically                                │
│  • Route messages to appropriate topics based on domain                  │
│  • Present inline keyboard buttons for approvals                         │
│  • Track conversation context per topic                                  │
│  • Learn routing patterns from human corrections                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Approval Workflow

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
│      │ Model: local/qwen2.5:7b (confidence: 0.82)              ││
│      │                                                          ││
│      │ Solutions:                                               ││
│      │ 1. Increase memory 1GB → 2GB                            ││
│      │ 2. Restart pod (temporary)                              ││
│      │ 3. Investigate leak (diagnostic)                        ││
│      │                                                          ││
│      │ [1️⃣ Increase] [2️⃣ Restart] [3️⃣ Investigate]            ││
│      │ [❌ Ignore]   [🔍 Details] [☁️ Re-analyze]              ││
│      └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │
         │ Button: [1️⃣ Increase]
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Execute via MCP infrastructure tools                            │
│  kubectl patch deployment/radarr ...                             │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  🟡 Arr Suite                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ✅ Radarr memory increased to 2GB                           ││
│  │                                                              ││
│  │ Status: Healthy (15 min)                                    ││
│  │ Memory: 45% (was 95%)                                       ││
│  │                                                              ││
│  │ 📚 Runbook updated: runbook-mem-001                         ││
│  │ Next occurrence: [🔄 Auto] [❓ Ask] [🔍 Investigate]         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Telegram Commands

| Input | Action |
|-------|--------|
| Button: `1️⃣`, `2️⃣`, `3️⃣` | Select numbered solution |
| Button: `Approve` | Approve current action/PR |
| Button: `Ignore` | Take no action, record preference |
| Button: `Details` | Show extended diagnostics |
| Button: `☁️ Re-analyze` | Bypass local, re-run with cloud model |
| Text: `status` | Show pending approvals |
| Text: `weekly` | Trigger weekly report now |
| Text: `/mode cloud_only` | Switch inference mode |
| Text: `custom: restart all arr` | Execute custom instruction |

### Topic Routing Rules

```yaml
# config/telegram-topics.yaml
standing_topics:
  - key: critical
    name: "🔴 Critical Alerts"
    route_when:
      - severity: critical
      - alertname: ".*OOM.*|.*Crash.*|.*Down.*"
      
  - key: arr_suite
    name: "🟡 Arr Suite"
    domains: ["sonarr", "radarr", "prowlarr", "sabnzbd", "plex"]
    
  - key: infrastructure
    name: "🔵 Infrastructure"
    domains: ["k8s", "argocd", "storage", "network", "proxmox", "talos"]
    
  - key: home_assistant
    name: "🏠 Home Assistant"
    domains: ["homeassistant", "tasmota", "mqtt", "zigbee"]
    
  - key: weekly_reports
    name: "📊 Weekly Reports"
    
  - key: resolved
    name: "✅ Resolved"

dynamic_topics:
  incident:
    name_template: "🔧 {title} #{id}"
    create_when:
      - severity: critical
      - estimated_complexity: high
    auto_close_after_hours: 168
    archive_to: resolved
```

---

## Part IV: Vector Knowledge Base

### Qdrant Collections

```python
# Collection schemas for learning system

collections = {
    "runbooks": {
        "vector_size": 768,  # nomic-embed-text
        "distance": "Cosine",
        "payload_schema": {
            "id": "keyword",
            "trigger_pattern": "text",
            "solution": "text",
            "success_rate": "float",
            "approval_count": "integer",
            "automation_level": "keyword",  # manual, prompted, standard
            "last_used": "datetime"
        }
    },
    
    "decisions": {
        "vector_size": 768,
        "distance": "Cosine", 
        "payload_schema": {
            "trigger": "text",
            "context": "text",
            "action_taken": "text",
            "outcome": "keyword",  # success, failure, partial
            "human_feedback": "keyword",  # approved, rejected, modified
            "model_used": "keyword",
            "confidence": "float",
            "timestamp": "datetime"
        }
    },
    
    "documentation": {
        "vector_size": 768,
        "distance": "Cosine",
        "payload_schema": {
            "source": "keyword",
            "title": "text",
            "content": "text",
            "doc_type": "keyword",  # readme, api, config, runbook
            "last_updated": "datetime"
        }
    }
}
```

### RAG Pipeline

```python
"""Retrieval-Augmented Generation for context-aware decisions."""

class KnowledgeRetriever:
    """Retrieves relevant context from vector DB."""
    
    async def get_context(self, query: str, alert: dict) -> dict:
        """Retrieve all relevant context for a decision."""
        
        # Embed the query
        query_vector = await self.embed(query)
        
        # Search each collection
        runbooks = await self.qdrant.search(
            collection_name="runbooks",
            query_vector=query_vector,
            limit=3,
            query_filter=Filter(
                must=[FieldCondition(
                    key="automation_level",
                    match=MatchAny(any=["manual", "prompted"])
                )]
            )
        )
        
        past_decisions = await self.qdrant.search(
            collection_name="decisions",
            query_vector=query_vector,
            limit=5,
            query_filter=Filter(
                must=[FieldCondition(
                    key="outcome",
                    match=MatchValue(value="success")
                )]
            )
        )
        
        documentation = await self.qdrant.search(
            collection_name="documentation",
            query_vector=query_vector,
            limit=3
        )
        
        return {
            "runbooks": [r.payload for r in runbooks],
            "past_decisions": [d.payload for d in past_decisions],
            "documentation": [d.payload for d in documentation],
            "query": query
        }
```

---

## Part V: MCP Server Layer

### Server Architecture

```
LangGraph Orchestrator
         │
         ├──▶ home-assistant-mcp ──▶ Home Assistant API
         │                           ├── Lights (Tasmota)
         │                           ├── Climate
         │                           └── Automations
         │
         ├──▶ arr-suite-mcp ──▶ *arr APIs
         │                      ├── Sonarr
         │                      ├── Radarr
         │                      ├── Prowlarr
         │                      └── SABnzbd
         │
         ├──▶ infrastructure-mcp ──▶ K8s / System
         │                           ├── kubectl
         │                           ├── ArgoCD
         │                           └── Proxmox
         │
         ├──▶ network-mcp ──▶ Network Infra
         │                    ├── OPNsense
         │                    ├── Cloudflare
         │                    └── UniFi
         │
         └──▶ knowledge-mcp ──▶ Knowledge Base
                               ├── Qdrant search
                               ├── Runbook lookup
                               └── Documentation
```

---

## Part VI: Observability & Learning Dashboard

### Key Metrics

```yaml
metrics:
  # Inference metrics
  - inference_requests_total{model, mode, escalated}
  - inference_latency_seconds{model}
  - inference_confidence_histogram{model}
  
  # Decision metrics  
  - decisions_total{outcome, human_feedback}
  - decision_response_time_seconds
  
  # Learning metrics
  - runbooks_total{automation_level}
  - runbook_promotions_total
  - knowledge_base_size{collection}
  
  # Telegram metrics
  - telegram_messages_sent{topic}
  - telegram_callbacks_received{action}
  - telegram_response_time_seconds
```

### Weekly Report (Telegram 📊 Topic)

```
📊 Weekly Homelab Report (Dec 23-30)

═══════════════════════════════════════

📈 INFERENCE SUMMARY
├── Local (qwen2.5:7b): 142 calls (78%)
├── Cloud escalations: 28 calls (15%)
├── Cloud bypass: 12 calls (7%)
└── Avg local confidence: 0.81

⚡ ACTIONS TAKEN
├── Auto-executed (standard): 8
│   └── Pod restarts (3), cache clears (5)
├── With approval: 12
│   └── Memory increases (4), PR merges (6), config (2)
└── Declined: 2
    └── Suggested changes you said no to

🎓 LEARNING
├── New runbooks: 3
├── Promoted to standard: 1
├── Patterns learned: 5
└── Total knowledge items: 247

📱 TELEGRAM ACTIVITY
├── Messages sent: 89
├── Topics created: 2
├── Avg response time: 4.2 min
└── Most active: 🟡 Arr Suite (34 msgs)

🔮 NEXT WEEK
├── SSL renewal due Dec 31
├── Monthly UniFi check Jan 1
└── 2 PRs awaiting review

═══════════════════════════════════════
```

---

## Part VII: Implementation Timeline

### Phase 1: Infrastructure (Week 1)
- [ ] Talos cluster provisioned via Terraform
- [ ] Storage configured (Mayastor/local-path)
- [ ] ArgoCD + SOPS deployed
- [ ] Renovate configured on GitOps repo

### Phase 2: Inference Layer (Week 2)
- [ ] Deploy Ollama with qwen2.5:7b
- [ ] Deploy LiteLLM with hybrid routing config
- [ ] Test local inference
- [ ] Configure cloud API keys (Gemini, Claude)
- [ ] Test escalation logic

### Phase 3: Knowledge Base (Week 3)
- [ ] Deploy Qdrant
- [ ] Create collection schemas
- [ ] Deploy nomic-embed-text model
- [ ] Build embedding pipeline
- [ ] Ingest initial documentation

### Phase 4: MCP Servers (Week 4)
- [ ] Build home-assistant-mcp
- [ ] Build infrastructure-mcp
- [ ] Build arr-suite-mcp
- [ ] Build knowledge-mcp
- [ ] Test tool execution

### Phase 5: Human-in-the-Loop (Week 5)
- [ ] Create Telegram bot via @BotFather
- [ ] Create Forum supergroup
- [ ] Deploy telegram-service
- [ ] Initialize standing topics
- [ ] Register webhook
- [ ] Test approval workflow with inline keyboards

### Phase 6: Observability (Week 6)
- [ ] Deploy Prometheus + Grafana
- [ ] Deploy Coroot
- [ ] Build learning dashboard
- [ ] Configure alert → AI pipeline

### Phase 7: Go Live (Week 7)
- [ ] Enable VERBOSE MODE (ask everything)
- [ ] Monitor all decisions
- [ ] Tune confidence thresholds
- [ ] Create initial runbooks from approvals

### Phase 8: Progressive Autonomy (Month 2+)
- [ ] Track approval patterns
- [ ] Promote high-success runbooks to standard
- [ ] Reduce notification frequency
- [ ] Quarterly trust reviews

---

## Appendix: Configuration Reference

### Environment Variables

```bash
# Ollama (Local)
OLLAMA_HOST=http://ollama:11434
OLLAMA_KEEP_ALIVE=10m

# Cloud APIs
GEMINI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# Inference Routing
INFERENCE_MODE=local_first          # local_first, cloud_only, local_only, cloud_first
LOCAL_CONFIDENCE_THRESHOLD=0.7
CLOUD_ESCALATION_MODEL=cloud/gemini-flash

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_FORUM_CHAT_ID=-100xxxxxxxxxx
TELEGRAM_WEBHOOK_URL=https://telegram-webhook.yourdomain.com/webhook

# Learning
PROMOTION_MIN_APPROVALS=5
PROMOTION_MIN_SUCCESS_RATE=0.95
```

### Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| Ollama | 11434 | HTTP |
| Qdrant REST | 6333 | HTTP |
| Qdrant gRPC | 6334 | gRPC |
| LiteLLM | 4000 | HTTP |
| LangGraph | 8000 | HTTP |
| Telegram Service | 8080 | HTTP |
| MCP Servers | 8001-8010 | HTTP/SSE |
| Prometheus | 9090 | HTTP |
| Grafana | 3000 | HTTP |
| Coroot | 8081 | HTTP |
| ArgoCD | 8443 | HTTPS |

---

## Conclusion

This architecture creates a **genuinely learning system** that:

1. **Remembers** every decision, outcome, and your feedback
2. **Retrieves** relevant context before acting via RAG
3. **Reasons** using local models first, cloud when needed
4. **Acts** through MCP tools with human approval via Telegram
5. **Learns** from outcomes and updates its knowledge

**The key insight**: Autonomy is earned, not configured. The system starts by asking permission for everything, then gradually proves it can be trusted with more independence.

**Flexibility built-in**: Switch between local-only, cloud-only, or hybrid inference based on your needs—privacy, offline operation, or maximum quality. Override per-request when needed.

**The learning loop is the differentiator**: Every interaction makes the system smarter. In six months, it will know your homelab better than any generic AI ever could.
