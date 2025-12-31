# Agentic AI Platform

> **Cyclical Learning Intelligent Agent for Homelab Management**

A self-improving AI platform that learns from every interaction, builds institutional knowledge, and progressively earns autonomy through demonstrated reliability.

---

## Quick Overview

This is a **hybrid local/cloud AI agent** deployed on dedicated infrastructure (Talos Linux on UM690L) that:

- 🧠 **Learns**: Vector knowledge base (Qdrant) stores every decision, outcome, and your feedback
- 🤝 **Collaborates**: Human-in-the-loop via Telegram Forum with inline keyboard approvals
- 🚀 **Improves**: Runbooks graduate from manual → prompted → fully automated based on success rate
- ⚡ **Adapts**: Local inference (Ollama) for speed, cloud (Gemini/Claude) for complex reasoning
- 🔒 **Protects**: PII detection before cloud escalation, network isolation, secrets management

**Philosophy**: Autonomy is earned, not configured. The system starts by asking permission for everything, then gradually proves it can be trusted with more independence.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│  Detection          Triage           Approval        Execution   │
│  (Coroot,     →    (LangGraph    →  (Telegram   →   (MCP        │
│   Prometheus)       + Qdrant)        Forum)           Tools)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │   Vector Knowledge    │
                  │   (Learning Layer)    │
                  │   Runbooks, Decisions │
                  └──────────────────────┘
```

**Components**:
- **Ollama**: Local LLM (qwen2.5:7b, nomic-embed-text)
- **Qdrant**: Vector database for learning and RAG
- **LangGraph**: Agent orchestration and state management
- **Telegram**: Human-in-the-loop approval interface
- **LiteLLM**: Unified API for local + cloud models
- **MCP Servers**: Tool integrations (Home Assistant, arr suite, infrastructure)

---

## Prerequisites

- **Hardware**: Proxmox host or bare metal with 8+ cores, 16GB+ RAM
  - This project targets UM690L (Ryzen 9 6900HX, 32GB RAM, 1.5TB NVMe)
- **Software**:
  - Terraform >= 1.5.0
  - kubectl >= 1.28
  - talosctl >= 1.6.0
- **Accounts**:
  - GitHub (for GitOps repository)
  - Infisical (for secrets management) or SOPS + age keys
  - Google Gemini API key (optional, for cloud inference)
  - Anthropic Claude API key (optional, for premium tasks)
  - Telegram account (for bot creation via @BotFather)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/charlieshreck/agentic_lab.git
cd agentic_lab
```

### 2. Configure Terraform

```bash
cd infrastructure/terraform/talos-cluster

# Copy example vars
cp terraform.tfvars.example terraform.tfvars

# Edit with your Proxmox credentials
vim terraform.tfvars
```

**Required variables**:
- `proxmox_api_url`: Proxmox API endpoint
- `proxmox_api_token_id`: API token ID
- `proxmox_api_token_secret`: API token secret
- `vm_ip`: Static IP for Talos node (default: 10.20.0.109)

### 3. Provision Infrastructure

```bash
terraform init
terraform plan -out=agentic.plan
terraform apply agentic.plan
```

This creates:
- Talos VM on Proxmox (or provisions bare metal if using Talos metal provider)
- Single-node Kubernetes cluster
- Kubeconfig and Talosconfig in `generated/` directory

### 4. Access Cluster

```bash
export KUBECONFIG=$(terraform output -raw kubeconfig_path)
export TALOSCONFIG=$(terraform output -raw talosconfig_path)

# Verify nodes
kubectl get nodes

# Check Talos health
talosctl health --nodes 10.20.0.109
```

### 5. Deploy Platform (ArgoCD Bootstrap)

```bash
cd ../../..  # Back to repo root
kubectl apply -k kubernetes/bootstrap/
```

### 6. Access ArgoCD

```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port forward
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser: https://localhost:8080
# Username: admin
# Password: (from command above)
```

### 7. Configure Secrets

Add secrets to Infisical UI (or use SOPS):
- `/agentic-platform/llm-apis`: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`
- `/agentic-platform/telegram`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_FORUM_CHAT_ID`
- `/agentic-platform/proxmox`: Proxmox credentials for MCP server

### 8. Sync Applications

ArgoCD will automatically deploy platform services and applications. Monitor progress:

```bash
argocd app list
argocd app get platform/ollama
```

---

## Documentation

- **[CLAUDE.md](./CLAUDE.md)**: Complete project overview and architecture
- **[GITOPS-WORKFLOW.md](./GITOPS-WORKFLOW.md)**: Mandatory workflow for all changes
- **[PHASES.md](./PHASES.md)**: Implementation timeline and roadmap
- **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)**: Required secrets documentation
- **[docs/](./docs/)**: Architecture deep-dives (14 detailed design documents)

---

## Project Status

**Current Phase**: Phase 1 - Infrastructure provisioning

See [PHASES.md](./PHASES.md) for detailed roadmap.

---

## Network Architecture

```
10.20.0.0/24 - Agentic Platform Network (Isolated)
├── 10.20.0.1      - Gateway
├── 10.20.0.109    - Talos cluster node (UM690L)
└── 10.20.0.x      - Future expansion

Related Networks:
- 10.10.0.0/24 - Production cluster (prod_homelab)
- 10.30.0.0/24 - Monitoring cluster (monit_homelab)
```

**Isolation**: This network is separate from production and monitoring to allow safe learning and experimentation.

---

## Key Design Decisions

### Why Talos Linux?
- Immutable, API-driven OS designed for Kubernetes
- No SSH, no shell by default (minimal attack surface)
- GitOps-native configuration
- Perfect for infrastructure as code

### Why Hybrid Inference?
- **Local (Ollama)**: Fast (50ms), private, no API costs, offline capable
- **Cloud (Gemini/Claude)**: Superior reasoning for complex tasks
- **PII Detection**: Automatic filtering before cloud escalation
- **Cost Optimization**: 80% of queries handled locally

### Why Qdrant?
- True vector database (not just indexed Postgres)
- Fast semantic search (<10ms for 100K vectors)
- Payload filtering (combine vector + metadata queries)
- Snapshots for backup/restore

### Why Telegram?
- Native Bot API with inline keyboards (better UX than Signal)
- Forum Topics for scalable organization
- Webhook-based (no polling overhead)
- Declarative deployment (token-based)

---

## Related Projects

- **[prod_homelab](https://github.com/charlieshreck/prod_homelab)**: Production Talos cluster
- **[monit_homelab](https://github.com/charlieshreck/monit_homelab)**: Monitoring K3s cluster

---

## Contributing

This is a personal homelab project. The repository is public for transparency and knowledge sharing, but contributions are not expected.

---

## License

MIT (see LICENSE file)

---

## Contact

Charlie Shreck

For detailed architecture, see [CLAUDE.md](./CLAUDE.md).
For operational workflows, see [GITOPS-WORKFLOW.md](./GITOPS-WORKFLOW.md).
