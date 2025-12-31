# Tool Selection Reference - Hybrid AI Architecture

## Deployment Options

### Option 1: Local LLM (Hybrid)
| Component | Choice | Notes |
|-----------|--------|-------|
| **OS** | Talos Linux | Bare metal, GPU extensions |
| **Container** | Kubernetes | Full K8s for GPU scheduling |
| **Inference** | Ollama + Qwen 2.5 3B | Vulkan backend |
| **Cloud** | Gemini + Claude | Escalation targets |

### Option 2: Cloud-Only (Recommended for simplicity)
| Component | Choice | Notes |
|-----------|--------|-------|
| **Hypervisor** | Proxmox VE | Familiar, flexible |
| **AI Platform** | Debian 12 VM + K3s | 8GB RAM, 4 cores |
| **Inference** | None local | All via Gemini/Claude |
| **Cloud** | Gemini (primary) + Claude (premium) | Subscription-based |

### Cloud-Only VM Sizing
```
AI Platform VM:
├── RAM: 8GB (3.5GB used, headroom for growth)
├── CPU: 4 cores
├── Disk: 100GB (plenty for containers + state)
└── Network: Bridge to LAN
```

## Inference Layer

| Tool | Version | Purpose | Config | Notes |
|------|---------|---------|--------|-------|
| **Ollama** | 0.4+ | Model serving | `GGML_VULKAN=1` | Primary runtime |
| **Qwen 2.5 3B** | Q4_K_M | Tool calling/routing | ~2GB VRAM | Best JSON output |
| **Llama 3.2 3B** | Q4_K_M | Fallback router | ~2GB VRAM | Superior instruction follow |
| **nomic-embed-text** | v1.5 | Embeddings | 768d/8K ctx | RAG retrieval |
| **BGE-reranker-v2-m3** | Latest | Reranking | ~1GB | Optional quality boost |

## Storage & State

### NVMe Layout for Talos (1TB + 500GB)

**Note**: Talos is immutable - no ZFS on the host. Use Kubernetes storage provisioners.

```
/dev/nvme0n1 (1TB) - Primary
├── Talos OS (EFI + STATE + EPHEMERAL)
└── Remaining: local-path-provisioner

/dev/nvme1n1 (500GB) - Data Disk
└── Dedicated to OpenEBS LocalPV or Mayastor
```

### Talos Storage Configuration
```yaml
# talconfig.yaml patch for extra disk
machine:
  disks:
    - device: /dev/nvme1n1
      partitions:
        - mountpoint: /var/mnt/data
  kubelet:
    extraMounts:
      - destination: /var/mnt/data
        type: bind
        source: /var/mnt/data
        options: [rbind, rshared, rw]
```

### Kubernetes Storage Options

| Provisioner | Use Case | Complexity | Performance |
|-------------|----------|------------|-------------|
| **local-path-provisioner** | Simple hostPath | Low | Native NVMe |
| **OpenEBS LocalPV** | Single-node, snapshots | Medium | Native NVMe |
| **Mayastor** | Replication (multi-node) | High | ~10% overhead |

**Recommended for single-node**: local-path-provisioner with manual backup scripts

| Tool | Purpose | Storage Class | Backup Strategy |
|------|---------|---------------|-----------------|
| **Ollama models** | LLM weights | local-path (1TB) | Re-download from registry |
| **Qdrant** | Vector database | local-path (500GB) | Snapshot to MinIO |
| **Redis** | Cache + queue | local-path (500GB) | AOF + BGSAVE to MinIO |
| **PostgreSQL** | Agent state | local-path (500GB) | pg_dump CronJob |
| **MinIO** | S3 storage | local-path (500GB) | Offsite sync to Backblaze/Wasabi |

## Orchestration & Routing

| Tool | Purpose | Why This One |
|------|---------|--------------|
| **LangGraph** | Agent orchestration | Graph-based, lowest latency, state persistence |
| **Open WebUI** | Chat interface | Pipeline filters, multi-model, self-hosted |
| **LiteLLM** | API proxy | Unified interface, automatic fallback, cost tracking |
| **Presidio** | PII detection | Rule-based, fast, production-ready |
| **GLiNER** | Zero-shot NER | International names, no fine-tuning needed |

## Cloud APIs (Escalation Targets)

### Gemini (Primary Cloud Target - Subscription, Unrestricted)
| Model | Use Case | Strengths |
|-------|----------|-----------|
| **Gemini Flash** | Default cloud escalation | Fast, large context, cost-effective |
| **Gemini Pro** | Complex analysis, coding | Balanced reasoning/speed |
| **Gemini Thinking** | Deep reasoning, planning | Extended chain-of-thought |

### Claude (Secondary Target - Subscription with Quotas)
| Model | Use Case | Reserve For |
|-------|----------|-------------|
| **Claude 4.5 Haiku** | Quick structured output | Fallback when Gemini unavailable |
| **Claude 4.5 Sonnet** | Complex coding, analysis | Tasks requiring superior code quality |
| **Claude 4.5 Opus** | Highest reasoning tasks | Critical decisions, architecture review |

⚠️ **Claude quota management required** - implement request counting and daily/weekly limits

## Observability

| Tool | Purpose | Deployment |
|------|---------|------------|
| **Prometheus** | Metrics collection | + ollama-exporter sidecar |
| **Grafana** | Dashboards/alerting | Pre-built LLM dashboards |
| **Langfuse** | LLM tracing | Self-hosted, LangChain integration |
| **Jaeger** | Distributed tracing | OpenTelemetry export |
| **Coroot** | Anomaly detection | eBPF-based, auto-instrumentation |

### Coroot Configuration
```yaml
# Detects anomalies without manual threshold configuration
# Uses eBPF for zero-instrumentation observability
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coroot
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
```

## GitOps & DevOps

| Tool | Purpose | Integration |
|------|---------|-------------|
| **ArgoCD** | Continuous deployment | App-of-apps pattern |
| **SOPS + Age** | Secret encryption | Native Flux/ArgoCD support |
| **Talhelper** | Talos config generation | Declarative machine configs |
| **Renovate** | Dependency updates | Helm chart + image tags |

## Scheduling & Workflows

| Tool | Use Case | Complexity |
|------|----------|------------|
| **K8s CronJob** | Simple scheduled tasks | Low |
| **n8n** | Visual workflows | Medium |
| **Temporal.io** | Durable long-running workflows | High |

---

## Environment Variables Reference

```bash
# Ollama AMD APU Configuration
export HSA_OVERRIDE_GFX_VERSION=10.3.0
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_KEEP_ALIVE=5m
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export GGML_VULKAN=1

# Open WebUI Security
export WEBUI_AUTH=true
export ENABLE_SIGNUP=false
export JWT_EXPIRES_IN=3600

# LiteLLM - Model Routing
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...
export LITELLM_MASTER_KEY=sk-...

# Claude Quota Management (daily limits)
export CLAUDE_HAIKU_DAILY_LIMIT=50
export CLAUDE_SONNET_DAILY_LIMIT=20
export CLAUDE_OPUS_DAILY_LIMIT=5
```

## Claude Quota Management Strategy

```yaml
# Redis-based quota tracking
quota_config:
  claude_haiku:
    daily_limit: 50
    weekly_limit: 200
    alert_threshold: 0.8  # Alert at 80% usage
  claude_sonnet:
    daily_limit: 20
    weekly_limit: 100
    alert_threshold: 0.7
  claude_opus:
    daily_limit: 5
    weekly_limit: 20
    alert_threshold: 0.5  # Early warning for premium tier
  
  # Fallback chain when quota exhausted
  fallback_order:
    - gemini_flash
    - gemini_pro
    - local_qwen
```

### LiteLLM Router Config (config.yaml)
```yaml
model_list:
  # Gemini - Primary (no budget limits)
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
  
  # Claude - Secondary (budget-limited)
  - model_name: claude-haiku
    litellm_params:
      model: anthropic/claude-3-5-haiku-latest
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_budget: 10.00  # Daily spend cap
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

  # Local fallback
  - model_name: local-qwen
    litellm_params:
      model: ollama/qwen2.5:3b
      api_base: http://ollama:11434

router_settings:
  routing_strategy: usage-based-routing-v2
  redis_host: redis
  redis_port: 6379
```

## Port Mapping

| Service | Port | Protocol |
|---------|------|----------|
| Open WebUI | 3000 | HTTP |
| Ollama API | 11434 | HTTP |
| Ollama Metrics | 11435 | HTTP |
| Qdrant | 6333/6334 | HTTP/gRPC |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |
| MinIO | 9000/9001 | HTTP |
| Grafana | 3001 | HTTP |
| Langfuse | 3002 | HTTP |
| LiteLLM | 4000 | HTTP |
| ArgoCD | 8080 | HTTPS |
| **MCP Servers** | 8000-8010 | HTTP/SSE |
| **Coroot** | 8081 | HTTP |
| **Signal CLI** | 8082 | HTTP |
| **Notification Service** | 8083 | HTTP |

---

## MCP Server Build Stack

| Tool | Purpose | Notes |
|------|---------|-------|
| **FastMCP** | Python MCP framework | v2.7+, decorator-based tools |
| **uv** | Fast Python package manager | Replaces pip in containers |
| **httpx** | Async HTTP client | For API calls to homelab apps |
| **GHCR** | Container registry | ghcr.io/yourrepo/mcp-* |

### MCP Servers to Build

| Server | Target Apps | Priority |
|--------|-------------|----------|
| `home-assistant-mcp` | HA, Tasmota, Google Home | High |
| `arr-suite-mcp` | Sonarr, Radarr, Prowlarr, SABnzbd | High |
| `infrastructure-mcp` | kubectl, ArgoCD, MinIO | High |
| `plex-mcp` | Plex, Tautulli | Medium |
| `truenas-mcp` | TrueNAS API, ZFS | Medium |

### Community MCP Servers (Evaluate First)

Check these before building custom:
- **pulsemcp.com** - Community MCP registry
- **smithery.ai** - MCP marketplace
- **berrykuipers/radarr-sonarr** - *arr integration
- **mcp-server-docker** - Docker management
- **mcp-server-kubernetes** - K8s operations

---

## Decision Matrix: When to Use What

| Scenario | Local Model | Cloud Target | Rationale |
|----------|-------------|--------------|-----------|
| Simple Q&A | Qwen 2.5 3B | — | Fast, free, no quota |
| Code completion | Qwen 2.5 3B | — | Good enough locally |
| General cloud escalation | — | **Gemini Flash** | Unrestricted, fast |
| Complex analysis | — | **Gemini Pro** | No quota concerns |
| Deep reasoning tasks | — | **Gemini Thinking** | Extended CoT, unrestricted |
| Long document analysis | — | **Gemini Flash/Pro** | 1M+ token context |
| PII-sensitive queries | Qwen 2.5 3B | — | Never leaves device |
| Multi-step planning | Qwen 2.5 3B → | **Gemini Thinking** | Route after initial parse |
| Creative writing | — | **Gemini Pro** | Save Claude quota |
| Data extraction | Qwen 2.5 3B | — | Structured output strength |
| **Premium code review** | — | **Claude Sonnet** | Worth quota for quality |
| **Architecture decisions** | — | **Claude Opus** | Reserve for critical tasks |
| **Gemini API failure** | — | **Claude Haiku** | Fallback only |

### Routing Priority (Cost/Quota Optimised)
```
1. Local (Qwen 2.5 3B)     → Free, instant, PII-safe
2. Gemini Flash            → Unrestricted, fast
3. Gemini Pro              → Unrestricted, capable
4. Gemini Thinking         → Unrestricted, deep reasoning
5. Claude Haiku            → Quota-limited, fallback
6. Claude Sonnet           → Quota-limited, premium code
7. Claude Opus             → Quota-limited, critical only
```
