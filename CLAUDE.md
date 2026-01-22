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

#### 1. AI Architecture
| Role | Model | Responsibility |
|------|-------|----------------|
| **Agent** | Ollama (qwen2.5:7b) via LiteLLM | Alert response, runbook execution, automated operations |
| **Orchestrator** | LangGraph | Graph-based agent routing, state management, tool orchestration |
| **Architect** | Claude Code (with Charlie) | Architecture decisions, planning, context-aware review sessions |

- **Inference**: LiteLLM proxy routing to local Ollama (qwen2.5:7b)
- **Embeddings**: Ollama nomic-embed-text (local embeddings)
- **Manual Interface**: OpenWebUI for direct Ollama chat

#### 2. Vector Knowledge Base
- **Engine**: Qdrant vector database
- **Collections**: runbooks, decisions, validations, documentation, **entities**, **device_types**, capability_gaps, skill_gaps, user_feedback
- **Purpose**: RAG for context-aware decisions, learning from outcomes, **network entity intelligence**
- **Embeddings**: Ollama nomic-embed-text (local, 768 dimensions)

#### 3. Orchestration
- **LangGraph**: Graph-based agent routing and state management
- **State**: PostgreSQL checkpointer for conversation history
- **Cache**: Redis for semantic caching and job queues
- **MCP Servers**: 6 consolidated domain MCPs for infrastructure, observability, knowledge, home, media, external
- **Context Sources**: Full context injection via Qdrant RAG

#### 3a. Domain MCP Servers

6 consolidated domain MCPs provide all tool capabilities:

| Domain | Endpoint | Components |
|--------|----------|------------|
| `observability-mcp` | observability-mcp.agentic.kernow.io | Keep alerts, Coroot metrics, VictoriaMetrics, AlertManager, Grafana, Gatus |
| `infrastructure-mcp` | infrastructure-mcp.agentic.kernow.io | Kubernetes, Proxmox, TrueNAS, Cloudflare, OPNsense, Caddy, Infisical |
| `knowledge-mcp` | knowledge-mcp.agentic.kernow.io | Qdrant (runbooks, entities), Neo4j graph, Outline wiki, Vikunja tasks |
| `home-mcp` | home-mcp.agentic.kernow.io | Home Assistant, Tasmota (26 devices), UniFi network, AdGuard DNS, Homepage |
| `media-mcp` | media-mcp.agentic.kernow.io | Plex, Sonarr, Radarr, Prowlarr, Overseerr, Tautulli, Transmission, SABnzbd |
| `external-mcp` | external-mcp.agentic.kernow.io | SearXNG web search, GitHub, Reddit, Wikipedia, Playwright browser |

**Usage**: MCP servers are configured in `/home/.mcp.json`. Tools are available to both Claude Code sessions and LangGraph agents.

**Access**: All domain MCPs run in the agentic cluster (ai-platform namespace) with DNS-based ingress:

| Domain MCP | Health Check |
|------------|--------------|
| observability-mcp | `curl http://observability-mcp.agentic.kernow.io/health` |
| infrastructure-mcp | `curl http://infrastructure-mcp.agentic.kernow.io/health` |
| knowledge-mcp | `curl http://knowledge-mcp.agentic.kernow.io/health` |
| home-mcp | `curl http://home-mcp.agentic.kernow.io/health` |
| media-mcp | `curl http://media-mcp.agentic.kernow.io/health` |
| external-mcp | `curl http://external-mcp.agentic.kernow.io/health` |

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

#### 3c. Neo4j Knowledge Graph (via knowledge-mcp)

The knowledge-mcp includes Neo4j for **relationship-aware queries** complementing Qdrant's semantic search:

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

#### 3e. Tasmota Device Control (via tasmota-mcp)

Direct HTTP API control of **26 Tasmota smart devices** (lights, switches, plugs) on the prod network.

| Tool | Purpose |
|------|---------|
| `tasmota_list_devices` | List registered devices |
| `tasmota_add_device(ip, name)` | Register a device by IP |
| `tasmota_discover(network)` | Scan network for Tasmota devices |
| `tasmota_power(ip, action)` | Control power: on, off, toggle, blink |
| `tasmota_power_all(action)` | Control all registered devices |
| `tasmota_status(ip)` | Get device status (power, WiFi, uptime) |
| `tasmota_wifi_config(ip, ssid, password)` | Configure WiFi settings |
| `tasmota_mqtt_config(ip, host, topic)` | Configure MQTT settings |
| `tasmota_command(ip, command)` | Execute any raw Tasmota command |
| `tasmota_restart(ip)` | Restart device |
| `tasmota_upgrade(ip, url)` | Trigger OTA firmware upgrade |

**Device Inventory (26 devices on 10.10.0.0/24):**
- Living Room: Sockets (4-relay), Lamp, Main Light
- Kitchen: Pendants, Spots
- Bedrooms: Study Pendant, Bedroom Light, Bedside, Vienna's, Albie's
- Bathrooms: EnSuite Spots, Shower Spots, Loo Lights, Cloakroom Spots
- Other: Hall, Stairs, Dining Room (Pendant + Spots), Laundry, Garage, Patio, Door Lights, Play Room (Pendants + Wall), RF Bridge, Macerator

**API Access:** All devices have HTTP API enabled by default (`WebServer 2`). No authentication required.

**Source:** `/home/agentic_lab/mcp-servers/tasmota/`

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

### Why Local Ollama (not Cloud APIs)?
- **Cost**: Zero per-token costs, unlimited usage
- **Privacy**: All inference runs locally, no data leaves the network
- **Latency**: Direct local inference, no network round-trip
- **Reliability**: No API rate limits or quota issues
- **Model**: qwen2.5:7b provides good balance of capability and speed

### Why LangGraph for Orchestration?
- **Graph-based**: Complex multi-step workflows with conditional routing
- **Stateful**: PostgreSQL checkpointing for conversation history
- **Tool orchestration**: Native MCP integration for tool calling
- **Extensible**: Easy to add new nodes and edges for new capabilities

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
- **MCP auto-generation**: When LangGraph needs a capability, Claude Code builds it
- **Skill auto-generation**: Repeated queries become slash commands
- **Runbook learning**: Patterns become formal procedures
- **Human approval**: All auto-generated code requires approval before deployment

---

## Security Considerations

1. **Network Isolation**: 10.20.0.0/24 isolated from production
2. **Local Inference**: All LLM inference runs locally on Ollama (no data leaves network)
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
├── matrix/
│   └── MATRIX_PASSWORD       # Matrix bot user password
├── mcp/
│   └── (various MCP secrets) # API keys for MCP server backends
└── infisical/
    └── (internal)            # Operator credentials
```

**Note**: Gemini and Claude API keys were retired when migrating to local Ollama.
See `/home/agentic_lab/archive/retired-cloud-llm/README.md` for details.

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
