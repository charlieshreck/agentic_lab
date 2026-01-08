# Agentic AI Platform

**Cyclical Learning Intelligent Agent for Homelab Management**

---

## Project Overview

This repository contains the infrastructure and application code for a **self-improving AI agent** that manages homelab operations through learning, human-in-the-loop workflows, and progressive autonomy.

**Core Philosophy**: The AI doesn't just execute tasks—it remembers what worked, learns your preferences, and gets smarter over time. Autonomy is earned through demonstrated reliability, not configured upfront.

---

## Architecture Summary

### Infrastructure
- **Platform**: Talos Linux bare metal on UM690L (no Proxmox, no VMs)
- **Hardware**: AMD Ryzen 9 6900HX (8C/16T), 32GB DDR5, 1.5TB NVMe
- **Network**: 10.20.0.0/24 (isolated from production and monitoring networks)
- **Node IP**: 10.20.0.40
- **GPU**: AMD Radeon 680M (RDNA2) for local inference acceleration
- **Storage**: Local path provisioner + future MinIO for backups

### Key Components

#### 1. Hybrid Inference Layer
- **Local**: Ollama (qwen2.5:7b for tool calling, nomic-embed-text for embeddings)
- **Cloud**: Google Gemini (primary), Anthropic Claude (premium tasks)
- **Routing**: LiteLLM with complexity-based model selection
- **Privacy**: Presidio + GLiNER for PII detection before cloud escalation

#### 2. Vector Knowledge Base
- **Engine**: Qdrant vector database
- **Collections**: runbooks, decisions, documentation, research, agent_events
- **Purpose**: RAG for context-aware decisions, learning from outcomes
- **Embeddings**: nomic-embed-text-v1.5 (768 dimensions, 8K context)

#### 3. Orchestration
- **LangGraph**: Graph-based agent routing and state management
- **State**: PostgreSQL checkpointer for conversation history
- **Cache**: Redis for semantic caching and job queues
- **MCP Servers**: Custom servers for Home Assistant, arr suite, infrastructure tools

#### 4. Human-in-the-Loop
- **Interface**: Telegram Bot with Forum Topics
- **Workflow**: Inline keyboard approvals for proposed actions
- **Learning**: Every approval/rejection updates the knowledge base
- **Progressive Autonomy**: Runbooks graduate from manual → prompted → standard

#### 5. Observability
- **Monitoring**: Prometheus + Grafana (potentially in separate cluster)
- **Anomaly Detection**: Coroot integration
- **Metrics**: Inference latency, decision outcomes, runbook success rates
- **Logs**: Structured logging with correlation IDs

---

## Network Architecture

```
10.20.0.0/24 - Agentic Platform Network
├── 10.20.0.1      - Gateway
├── 10.20.0.40    - Talos cluster node (UM690L)
└── 10.20.0.x      - Future expansion nodes

Related Networks:
- 10.10.0.0/24 - Production cluster (prod_homelab)
- 10.30.0.0/24 - Monitoring cluster (monit_homelab)
```

**Network Isolation**: This cluster is separate from production and monitoring to prevent agentic operations from impacting critical services during learning phase.

---

## Deployment Model

### Phase 1: Infrastructure (Current)
**Goal**: Provision Talos cluster and deploy core services

1. Terraform provisions Talos VM on Proxmox (or bare metal)
2. Talos cluster bootstrapped via talosctl
3. ArgoCD deployed for GitOps workflow
4. Infisical deployed for secrets management
5. Storage provisioner configured

### Phase 2-8: Application Layers
See `PHASES.md` for detailed implementation timeline.

---

## GitOps Workflow

**⚠️ CRITICAL**: This repository follows strict GitOps practices. Read [`GITOPS-WORKFLOW.md`](./GITOPS-WORKFLOW.md) before making ANY changes.

**Key Rules**:
- NEVER manual `kubectl apply` or `talosctl apply-config`
- ALWAYS commit → push → ArgoCD sync
- NEVER hardcode secrets (use Infisical or SOPS)
- ALWAYS use Terraform for infrastructure changes

---

## Repository Structure

```
agentic_lab/
├── infrastructure/          # Infrastructure as Code
│   ├── terraform/
│   │   └── talos-cluster/  # Talos OS provisioning
│   ├── ansible/            # Post-Talos configuration (future)
│   └── scripts/            # Utility scripts
├── kubernetes/             # K8s manifests (GitOps)
│   ├── bootstrap/          # ArgoCD installation
│   ├── platform/           # Core services (cert-manager, infisical, storage)
│   └── applications/       # AI workloads (ollama, qdrant, langgraph, etc.)
├── docs/                   # Architecture documentation
│   ├── unified-architecture-updated.md
│   ├── telegram-architecture.md
│   ├── mcp-development-guide.md
│   └── ... (14 design docs total)
├── scripts/                # Operational scripts
├── .claude/                # Claude Code integration
│   └── skills/agentic-ops/ # Context for Claude operations
├── GITOPS-WORKFLOW.md      # Mandatory GitOps rules
├── PHASES.md               # Implementation timeline
└── README.md               # Quick start guide
```

---

## Prerequisites

- Terraform >= 1.5.0
- kubectl >= 1.28
- talosctl >= 1.8.0
- UM690L bare metal hardware (no Proxmox required)
- USB drive (8GB+) for Talos ISO
- GitHub account (for GitOps repository)
- Infisical project for secrets (or SOPS + age keys)

**Installation Guide**: See [BARE_METAL_INSTALL.md](./BARE_METAL_INSTALL.md) for complete bare metal setup instructions.

---

## Quick Start

1. **Clone repository**:
   ```bash
   git clone https://github.com/charlieshreck/agentic_lab.git
   cd agentic_lab
   ```

2. **Configure Terraform**:
   ```bash
   cd infrastructure/terraform/talos-cluster
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your Proxmox credentials
   ```

3. **Provision infrastructure**:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

4. **Bootstrap cluster**:
   ```bash
   export KUBECONFIG=$(terraform output -raw kubeconfig_path)
   kubectl get nodes
   ```

5. **Deploy ArgoCD** (see `kubernetes/bootstrap/README.md`)

---

## Related Repositories

- **prod_homelab**: Production Talos cluster (10.10.0.0/24) - Production applications
- **monit_homelab**: Monitoring K3s cluster (10.30.0.0/24) - Observability stack

---

## Architecture Documentation

Comprehensive architecture documentation is available in the `docs/` directory:

- **[Unified Architecture (Updated)](./docs/unified-architecture-updated.md)** - Complete system design with hybrid inference
- **[Telegram Architecture](./docs/telegram-architecture.md)** - Human-in-the-loop Telegram Forum workflow
- **[MCP Development Guide](./docs/mcp-development-guide.md)** - Building custom MCP servers
- **[Qdrant Agent Communication](./docs/qdrant-agent-communication.md)** - Inter-agent knowledge sharing
- **[Cloud-Only Architecture](./docs/cloud-only-updated.md)** - Alternative cloud-only design

---

## Key Design Decisions

### Why Talos Linux?
- Immutable, API-driven OS designed for Kubernetes
- Minimal attack surface (no SSH, no shell by default)
- GitOps-native configuration
- Perfect for infrastructure as code

### Why Hybrid Local/Cloud Inference?
- **Local**: Fast (50ms), private, no API costs, offline capable
- **Cloud**: Superior reasoning for complex tasks, latest models
- **PII Detection**: Automatic filtering before cloud escalation
- **Cost Optimization**: 80% of queries handled locally

### Why Telegram?
- Native Bot API with inline keyboards (better UX than Signal CLI)
- Forum Topics for scalable organization (critical/arr/infrastructure/etc.)
- Webhook-based (no polling overhead)
- Declarative deployment (token-based, no phone registration)

### Why Qdrant for Knowledge?
- True vector database (not just indexed Postgres)
- Fast semantic search (<10ms for 100K vectors)
- Payload filtering (combine vector + metadata queries)
- Snapshots for backup/restore

---

## Security Considerations

1. **Network Isolation**: 10.20.0.0/24 isolated from production
2. **PII Detection**: Presidio + GLiNER scan before cloud API calls
3. **Secrets Management**: Infisical (never hardcoded)
4. **RBAC**: Kubernetes RBAC for service accounts
5. **Audit**: All agent decisions logged to Qdrant with human feedback

---

## Infisical Access (Claude Sessions)

Machine Identity credentials are stored securely for programmatic access to Infisical secrets.

### Location
```
/root/.config/infisical/
├── machine-identity.json   # Client ID & Secret (chmod 600)
├── get-token.sh            # Fetches short-lived access token
└── secrets.sh              # Helper for CRUD operations
```

### Usage
```bash
# Get a secret
/root/.config/infisical/secrets.sh get /agentic-platform/telegram BOT_TOKEN

# Set a secret
/root/.config/infisical/secrets.sh set /agentic-platform/llm API_KEY "value"

# List secrets at path
/root/.config/infisical/secrets.sh list /agentic-platform

# List folders
/root/.config/infisical/secrets.sh folders /agentic-platform

# Create folder
/root/.config/infisical/secrets.sh mkdir /agentic-platform newservice
```

### Current Secret Paths
```
/agentic-platform/
├── Gemini/
│   └── GEMINI_API_KEY
└── telegram/
    ├── BOT_TOKEN
    └── CHAT_ID
```

### Machine Identity Details
- **Workspace ID**: 9383e039-68ca-4bab-bc3c-aa06fdb82627
- **Environment**: prod
- **Permissions**: Full CRUD on secrets and folders
- **Token TTL**: 30 days (auto-refreshed on each call)

---

## Contributing

This is a personal homelab project. The repository is public for transparency and knowledge sharing, but contributions are not expected.

---

## License

MIT (see LICENSE file)

---

## Contact

Charlie Shreck - charlie@example.com (update with actual contact)

For questions about architecture decisions, see the detailed docs in `docs/`.
For operational workflows, see `GITOPS-WORKFLOW.md`.
For implementation timeline, see `PHASES.md`.
