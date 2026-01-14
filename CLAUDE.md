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
- **GPU**: AMD Radeon 680M (RDNA2) - available for future local inference
- **Storage**: Local path provisioner + future MinIO for backups

### Key Components

#### 1. Split-Role AI Architecture
| Role | Model | Responsibility |
|------|-------|----------------|
| **Workhorse** | Gemini 2.0 Pro (via LiteLLM) | Alert response, runbook execution, code fixes, maintenance |
| **Validator** | Claude (via claude-agent) | Reviews Gemini outputs, auto-corrects minor issues, flags major issues |
| **Architect** | Claude Code (with Charlie) | Architecture decisions, planning, context-aware review sessions |

- **Inference**: LiteLLM proxy routing to Gemini Pro (1M token context)
- **Embeddings**: Gemini text-embedding-004 (768 dimensions)

#### 2. Vector Knowledge Base
- **Engine**: Qdrant vector database
- **Collections**: runbooks, decisions, validations, documentation, **entities**, **device_types**, capability_gaps, skill_gaps, user_feedback
- **Purpose**: RAG for context-aware decisions, learning from outcomes, **network entity intelligence**
- **Embeddings**: Gemini text-embedding-004 (768 dimensions)

#### 3. Orchestration
- **LangGraph**: Graph-based agent routing and state management
- **State**: PostgreSQL checkpointer for conversation history
- **Cache**: Redis for semantic caching and job queues
- **MCP Servers**: Custom servers for infrastructure, search, and automation (see below)
- **Context Sources**: Full context injection via Gemini's 1M token window

#### 3a. Available MCP Servers
| Server | Description | Key Tools |
|--------|-------------|-----------|
| `infrastructure-mcp` | Cluster state, kubectl, talosctl | kubectl_get_pods, kubectl_logs, talosctl_health |
| `coroot-mcp` | Observability, metrics, anomalies | get_service_metrics, get_anomalies, get_alerts |
| `knowledge-mcp` | Qdrant vector DB + **entity intelligence** | search_runbooks, search_entities, get_entity, get_device_type_info |
| `opnsense-mcp` | Firewall/router management | get_dhcp_leases, get_firewall_rules, get_gateway_status |
| `unifi-mcp` | Network infrastructure | list_clients, list_devices, get_health, get_alarms |
| `proxmox-mcp` | Hypervisor management | list_vms, start_vm, stop_vm, get_vm_status |
| `truenas-mcp` | Storage management | list_pools, list_datasets, list_shares, get_disk_status |
| `home-assistant-mcp` | Smart home control | list_lights, turn_on_light, list_climate, get_sensors |
| `web-search-mcp` | Web search via SearXNG | web_search, get_page_content, search_news |
| `browser-automation-mcp` | Headless browser (Playwright) | navigate, screenshot, click, type_text |
| `infisical-mcp` | Secrets management | list_secrets, get_secret (read-only) |

**Usage**: MCP servers are configured in `.mcp.json`. Tools are available to both Claude Code sessions and LangGraph agents.

**Access**: All MCP servers run in the agentic cluster (ai-platform namespace) with NodePort exposure on `10.20.0.40`:

| Server | NodePort | Health Check |
|--------|----------|--------------|
| infisical-mcp | 31080 | `curl http://10.20.0.40:31080/health` |
| coroot-mcp | 31081 | `curl http://10.20.0.40:31081/health` |
| proxmox-mcp | 31082 | `curl http://10.20.0.40:31082/health` |
| infrastructure-mcp | 31083 | `curl http://10.20.0.40:31083/health` |
| knowledge-mcp | 31084 | `curl http://10.20.0.40:31084/health` |
| opnsense-mcp | 31085 | `curl http://10.20.0.40:31085/health` |
| adguard-mcp | 31086 | `curl http://10.20.0.40:31086/health` |
| cloudflare-mcp | 31087 | `curl http://10.20.0.40:31087/health` |
| unifi-mcp | 31088 | `curl http://10.20.0.40:31088/health` |
| truenas-mcp | 31089 | `curl http://10.20.0.40:31089/health` |
| home-assistant-mcp | 31090 | `curl http://10.20.0.40:31090/health` |
| arr-suite-mcp | 31091 | `curl http://10.20.0.40:31091/health` |
| homepage-mcp | 31092 | `curl http://10.20.0.40:31092/health` |
| web-search-mcp | 31093 | `curl http://10.20.0.40:31093/health` |
| browser-automation-mcp | 31094 | `curl http://10.20.0.40:31094/health` |
| plex-mcp | 31096 | `curl http://10.20.0.40:31096/health` |
| vikunja-mcp | 31097 | `curl http://10.20.0.40:31097/health` |
| neo4j-mcp | 31098 | `curl http://10.20.0.40:31098/health` |

**IMPORTANT**: MCP servers are ONLY in the agentic cluster. Do NOT deploy MCPs to prod or monit clusters.

#### 3b. Network Entity Intelligence (via knowledge-mcp)

The knowledge MCP includes **complete visibility into every device on the network**:

| Tool | Purpose |
|------|---------|
| `search_entities(query)` | Semantic search: "find all Chromecast devices", "IoT on guest network" |
| `get_entity(ip/mac/hostname)` | Exact lookup by identifier |
| `get_entities_by_type(type)` | Filter by type: "sonoff", "chromecast", "nas", "printer" |
| `get_entities_by_network(network)` | Filter by network: "prod", "iot-vlan", "guest" |
| `get_device_type_info(type)` | Control methods for device type (API commands, protocols) |
| `update_entity(id, updates)` | Update entity after performing actions |
| `add_entity(...)` | Add newly discovered device |

**Coverage**: Every device on the network - hardware and software, physical and virtual, managed and unmanaged. Entities include IP, MAC, hostname, manufacturer, model, location, capabilities, and control interfaces.

#### 3c. Neo4j Knowledge Graph (via neo4j-mcp)

The neo4j-mcp provides **relationship-aware queries** complementing Qdrant's semantic search:

| Tool | Purpose |
|------|---------|
| `query_graph(cypher)` | Execute read-only Cypher queries |
| `get_entity_context(id)` | Get entity with all relationships |
| `find_dependencies(service, depth)` | Find upstream/downstream dependencies |
| `get_impact_analysis(type, id)` | What breaks if entity X fails? |
| `find_path(from, to)` | Network/dependency path between entities |
| `get_runbook_for_alert(name)` | Find runbooks that resolve an alert |
| `get_infrastructure_overview()` | High-level cluster status |
| `get_hosts_on_network(network)` | List hosts on a network (prod/agentic/monitoring) |
| `find_orphan_entities()` | Find entities with no relationships |

**When to use Neo4j vs Qdrant:**
- **Neo4j**: Relationships, dependencies, "what connects to X?", impact analysis
- **Qdrant**: Semantic similarity, "find things like X", text search

**REST API endpoints:**
- `GET /health` - Health check
- `GET /api/overview` - Infrastructure overview
- `GET /api/query?q=<cypher>` - Execute Cypher query
- `GET /api/entity?id=<id>&type=<type>` - Get entity context

**Data sync:**
- network-discovery (every 15 min) - Hosts, Networks, CONNECTED_TO
- graph-sync (every 5 min) - VMs, Services, Pods, lifecycle management

#### 3d. Kernow Knowledge UI (fumadocs)

Web interface for browsing entities, exploring the knowledge graph, and searching documentation.

| Feature | Description |
|---------|-------------|
| **Entities** | Browse hosts, VMs, services, network devices |
| **Graph** | Explore relationships and dependencies (Neo4j) |
| **Search** | Semantic search across runbooks and docs (Qdrant) |

**Access:**
- Internal: `http://10.20.0.40:31099/`
- External: (not configured yet)

**Tech Stack:** Next.js 14, Tailwind CSS, standalone Docker build

**Source:** `/home/agentic_lab/fumadocs/`

#### 4. Human-in-the-Loop
- **Interface**: Matrix/Element (self-hosted Conduit server)
- **Workflow**: Threaded conversations, reaction-based approvals
- **Learning**: Every approval/rejection updates the knowledge base
- **Progressive Autonomy**: Runbooks graduate from manual → prompted → standard
- **Arr Suite**: Separate notifications via Discord + Notifiarr

#### 5. Self-Evolution
- **Runbooks**: Auto-generated from patterns, Claude Validator reviews
- **MCPs**: Auto-generated when capability gaps detected
- **Skills**: Auto-generated slash commands from usage patterns
- **All changes require human approval before deployment**

#### 6. Observability
- **Monitoring**: Prometheus + Grafana (monit_homelab cluster)
- **Anomaly Detection**: Coroot integration (via coroot-mcp)
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
3. ArgoCD Applications created in prod cluster (ArgoCD manages agentic remotely)
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

## Cluster Access (Claude Code Sessions)

### Kubernetes Clusters

Access clusters via kubectl with explicit kubeconfig:

```bash
# Agentic cluster (10.20.0.0/24)
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
kubectl get nodes

# Production cluster (10.10.0.0/24)
export KUBECONFIG=/home/prod_homelab/kubeconfig
kubectl get nodes

# Monitoring cluster (10.30.0.0/24)
export KUBECONFIG=/home/monit_homelab/kubeconfig
kubectl get nodes
```

### ArgoCD Operations

**IMPORTANT**: ArgoCD runs ONLY in the **prod cluster** (10.10.0.0/24) and manages all three clusters remotely via app-of-apps pattern. The agentic cluster has NO local ArgoCD.

```bash
# Set kubeconfig for PROD cluster (where ArgoCD lives)
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig

# List all ArgoCD applications (includes agentic cluster apps)
kubectl get applications -n argocd

# Get application status
kubectl get application <app-name> -n argocd -o jsonpath='{.status.sync.status}'

# Force sync an application (via patch)
kubectl patch application <app-name> -n argocd --type merge -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'

# Watch application sync status
kubectl get application <app-name> -n argocd -w

# Get sync details
kubectl describe application <app-name> -n argocd

# Check ArgoCD server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=50
```

### Deploying to Agentic Cluster

1. Create manifests in `/home/agentic_lab/kubernetes/applications/<app>/`
2. Create ArgoCD Application in `/home/agentic_lab/kubernetes/argocd-apps/<app>.yaml`:
   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: <app>
     namespace: argocd
   spec:
     project: default
     source:
       repoURL: https://github.com/charlieshreck/agentic_lab.git
       targetRevision: main
       path: kubernetes/applications/<app>
     destination:
       server: https://10.20.0.40:6443  # Agentic cluster API
       namespace: ai-platform
     syncPolicy:
       automated:
         prune: true
         selfHeal: true
   ```
3. Commit and push to git
4. Apply ArgoCD Application to **PROD cluster**:
   ```bash
   KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
     kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/<app>.yaml
   ```

### Common Operations

```bash
# Watch pods in ai-platform namespace
kubectl get pods -n ai-platform -w

# Check job status
kubectl get jobs -n ai-platform

# View logs from latest job
kubectl logs -n ai-platform job/<job-name>

# Restart a deployment
kubectl rollout restart deployment/<name> -n ai-platform

# Run a one-off job from CronJob
kubectl create job --from=cronjob/<cronjob-name> <job-name> -n ai-platform
```

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
│   ├── argocd-apps/        # ArgoCD Application manifests (applied to prod cluster)
│   ├── platform/           # Core services (cert-manager, infisical, storage)
│   └── applications/       # AI workloads (matrix, qdrant, langgraph, etc.)
├── mcp-servers/            # Custom MCP server implementations
├── docs/                   # Architecture documentation
│   ├── unified-architecture-updated.md
│   ├── mcp-development-guide.md
│   └── ... (14 design docs total)
├── scripts/                # Operational scripts
├── .claude/                # Claude Code integration
│   ├── commands/           # Slash commands (bootstrap + auto-generated)
│   ├── context/            # Ambient context files (latest.md)
│   └── skills/agentic-ops/ # Context for Claude operations
├── .gemini/                # Gemini agent configuration
│   └── SYSTEM.md           # Gemini system prompt and guidelines
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

5. **Create ArgoCD Applications** in prod cluster (see `kubernetes/argocd-apps/README.md`)

---

## Related Repositories

- **prod_homelab**: Production Talos cluster (10.10.0.0/24) - Production applications
- **monit_homelab**: Monitoring Talos cluster (10.30.0.0/24) - Observability stack

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

### Why Gemini as Workhorse?
- **1M token context window**: Comprehensive context injection, no need for complex RAG chunking
- **Cost effective**: Lower cost than Claude for high-volume operational tasks
- **Fast**: Good latency for real-time alert response
- **Embeddings**: Built-in text-embedding-004 model

### Why Claude as Validator?
- **Superior reasoning**: Better at catching edge cases and subtle issues
- **Security focus**: Excellent at identifying security vulnerabilities
- **Architectural thinking**: Good at suggesting improvements
- **Batch processing**: Cost-effective for daily validation runs

### Why Matrix/Element (not Telegram)?
- **Self-hosted**: Full control with Conduit server (~128MB RAM)
- **Conversational threads**: Full back-and-forth in incident threads
- **Reaction-based approvals**: Quick approve/reject with emojis
- **Cross-platform**: Element app on Android, Web, Desktop
- **No rate limits**: Internal server, no API restrictions

### Why Qdrant for Knowledge?
- True vector database (not just indexed Postgres)
- Fast semantic search (<10ms for 100K vectors)
- Payload filtering (combine vector + metadata queries)
- Snapshots for backup/restore

### Why Auto-Evolution?
- **MCP auto-generation**: When Gemini needs a capability, Claude builds it
- **Skill auto-generation**: Repeated queries become slash commands
- **Runbook learning**: Patterns become formal procedures
- **Human approval**: All auto-generated code requires approval before deployment

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
│   └── GEMINI_API_KEY        # LiteLLM uses for Gemini Pro/Flash/Embeddings
├── claude/
│   └── (OAuth tokens)        # Claude Agent service credentials
├── matrix/
│   └── MATRIX_PASSWORD       # Matrix bot user password
└── infisical/
    └── (internal)            # Operator credentials
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
