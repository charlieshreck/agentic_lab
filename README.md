# Agentic AI Platform

> **Cyclical Learning Intelligent Agent for Homelab Management**

A self-improving AI platform that learns from every interaction, builds institutional knowledge, and progressively earns autonomy through demonstrated reliability.

---

## Quick Overview

This is a **hybrid local/cloud AI agent** deployed on dedicated infrastructure (Talos Linux on UM690L) that:

- 🧠 **Learns**: Vector knowledge base (Qdrant) stores every decision, outcome, and your feedback
- 🤝 **Collaborates**: Human-in-the-loop via Telegram Forum with inline keyboard approvals
- 🚀 **Improves**: Runbooks graduate from manual → prompted → fully automated based on success rate
- ⚡ **Adapts**: Cloud inference via LiteLLM routing to Gemini (embeddings + chat)
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
- **LiteLLM**: Unified API routing to Gemini (chat + embeddings)
- **Qdrant**: Vector database for learning and RAG
- **LangGraph**: Agent orchestration and state management
- **Telegram**: Human-in-the-loop approval interface
- **MCP Servers**: Tool integrations (Home Assistant, arr suite, infrastructure)

---

## Prerequisites

- **Hardware**: UM690L bare metal (Ryzen 9 6900HX, 32GB RAM, 1.5TB NVMe)
  - USB drive (8GB+) for Talos ISO
  - Monitor + keyboard for initial setup (or remote console)
  - Network connectivity
- **Software**:
  - Terraform >= 1.5.0
  - kubectl >= 1.28
  - talosctl >= 1.8.0
- **Accounts**:
  - GitHub (for GitOps repository)
  - Infisical (for secrets management) or SOPS + age keys
  - Google Gemini API key (optional, for cloud inference)
  - Anthropic Claude API key (optional, for premium tasks)
  - Telegram account (for bot creation via @BotFather)

---

## Quick Start

⚠️ **Important**: This is a bare metal Talos installation. See **[BARE_METAL_INSTALL.md](./BARE_METAL_INSTALL.md)** for the complete step-by-step guide.

### Quick Summary:

1. **Download Talos ISO** and flash to USB drive
2. **Boot UM690L** from USB (enters maintenance mode)
3. **Configure Terraform** with network details
4. **Run `terraform apply`** to provision cluster
5. **Remove USB** and reboot (boots from NVMe)
6. **Deploy platform** via ArgoCD

**Full guide**: [BARE_METAL_INSTALL.md](./BARE_METAL_INSTALL.md)

### 4. Access Cluster

```bash
export KUBECONFIG=$(terraform output -raw kubeconfig_path)
export TALOSCONFIG=$(terraform output -raw talosconfig_path)

# Verify nodes
kubectl get nodes

# Check Talos health
talosctl health --nodes 10.20.0.40
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
argocd app get platform/litellm
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
├── 10.20.0.40    - Talos cluster node (UM690L)
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

### Why Gemini via LiteLLM?
- **1M Token Context**: Comprehensive context injection without complex RAG chunking
- **Cost Effective**: Lower cost than Claude for high-volume operational tasks
- **Fast Embeddings**: text-embedding-004 (768 dimensions) for semantic search
- **Unified API**: LiteLLM provides OpenAI-compatible interface for all models

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
- **[monit_homelab](https://github.com/charlieshreck/monit_homelab)**: Monitoring Talos cluster

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
