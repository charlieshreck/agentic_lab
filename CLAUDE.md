# Agentic Lab — AI Platform Cluster

## Overview

Single-node Talos Linux cluster on UM690L (AMD Ryzen 9 6900HX, 64GB RAM).
Network: 10.20.0.0/24 (AI network), node IP: 10.20.0.40.
Cilium CNI with L2 LoadBalancer (10.20.0.90-99).

ArgoCD managed remotely from **prod cluster** — no local ArgoCD instance here.
All changes: commit → push → ArgoCD auto-sync.

---

## Deployed Workloads (ai-platform namespace)

| App | Notes |
|-----|-------|
| observability-mcp | Domain MCP — Keep, Coroot, VictoriaMetrics, AlertManager, Grafana, Gatus, ntopng |
| infrastructure-mcp | Domain MCP — K8s, ArgoCD, Proxmox, TrueNAS, Cloudflare, OPNsense, Caddy, Infisical, Omada |
| knowledge-mcp | Domain MCP — Qdrant, Neo4j, Outline, SilverBullet, Vikunja |
| home-mcp | Domain MCP — Home Assistant, Tasmota, UniFi, AdGuard, Homepage |
| media-mcp | Domain MCP — Plex, Sonarr, Radarr, Prowlarr, Overseerr, Tautulli, Transmission, SABnzbd, etc. |
| external-mcp | Domain MCP — SearXNG, GitHub, Reddit, Wikipedia, Playwright browser |
| kernow-hub | Unified PWA (Incidents, Terminal, Chat) — NodePort 30456 |
| langgraph | KAO incident broker — NodePort 30800, /ingest endpoint |
| a2a-orchestrator | A2A REST bridge for MCP tool calls (/api/call) |
| alerting-pipeline | Polls infra/home/media MCPs, forwards alerts to LangGraph |
| litellm | LLM proxy — routes to cloud APIs |
| openwebui | OpenWebUI chat interface |
| outline | Wiki (knowledge base) |
| silverbullet | SilverBullet note-taking |
| searxng | SearXNG search engine (backend for external-mcp) |
| neodash | Neo4j dashboard UI |
| mcp-config-sync | Syncs MCP config to Synapse screen sessions |
| investmentology-api | Investmentology API (0 replicas — inactive) |

**Supporting infrastructure**: qdrant, neo4j, postgresql, redis, ollama (local inference)

---

## MCP Servers

All 6 domain MCP servers run in this cluster. Source code: `/home/mcp-servers/`.
Docker images: `ghcr.io/charlieshreck/mcp-<domain>:latest`
K8s manifests: `/home/mcp-servers/kubernetes/domains/<domain>.yaml`

| Domain | Endpoint |
|--------|----------|
| observability | observability-mcp.agentic.kernow.io |
| infrastructure | infrastructure-mcp.agentic.kernow.io |
| knowledge | knowledge-mcp.agentic.kernow.io |
| home | home-mcp.agentic.kernow.io |
| media | media-mcp.agentic.kernow.io |
| external | external-mcp.agentic.kernow.io |

**Rule**: MCP servers are ONLY deployed here (ai-platform namespace). Never prod or monit.

---

## KAO — Kernow Autonomous Operations

Alert sources → LangGraph → Kernow Hub → Claude screen sessions.

- **LangGraph**: NodePort 30800, `/ingest?source=<type>` with 7 normalizers
  (alertmanager, gatus, coroot, pulse, pbs, beszel, alerting-pipeline)
- **Graph**: ingest → suppress filter → FP check → assess → create_screen → record_outcome
- **Max concurrent incidents**: 3
- **Kernow Hub**: PWA at kernow.kernow.io — Incidents tab shows live incident state

Alert wiring:
- AlertManager → `http://10.20.0.40:30800/ingest?source=alertmanager`
- alerting-pipeline → LangGraph internal (polls MCP tools)
- alert-forwarder CronJob → LangGraph (TrueNAS/PBS alerts)

See `~/.claude/projects/-home/memory/MEMORY.md` for full KAO architecture details.

---

## Storage

NFS from TrueNAS-HDD (10.10.0.103) via cross-network mount.
No local persistent storage — Talos is ephemeral.
NFS PVs mounted for: qdrant, neo4j, postgresql, outline, victoria-metrics.

---

## Access

- **kubectl**: Use `infrastructure-mcp kubectl_*` tools — kubeconfig managed internally by MCP.
  Or: `KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig`
- **ArgoCD**: Runs on prod cluster — use `argocd_*` MCP tools or prod KUBECONFIG.
- **App discovery**: All apps auto-discovered by `agentic-applications` app-of-apps in ArgoCD.

---

## Repository Structure

```
agentic_lab/
├── infrastructure/
│   └── terraform/talos-cluster/    # Talos machine configs + generated kubeconfig
├── kubernetes/
│   ├── applications/               # App manifests (ArgoCD auto-sync)
│   │   ├── kernow-hub/
│   │   ├── langgraph/
│   │   ├── a2a/
│   │   ├── alerting-pipeline/
│   │   ├── litellm/
│   │   ├── openwebui/
│   │   ├── outline/
│   │   ├── silverbullet/
│   │   ├── mcp-servers/            # searxng + reconcile cronjob (MCPs from /home/mcp-servers/)
│   │   ├── qdrant/
│   │   ├── neo4j/
│   │   ├── postgresql/
│   │   ├── redis/
│   │   └── ...
│   └── platform/                   # cert-manager, infisical-operator, storage
├── runbooks/                       # Operational runbooks (synced to knowledge-mcp)
├── docs/                           # Architecture documentation
└── .gemini/SYSTEM.md               # Gemini reviewer system prompt
```

Note: MCP server source code lives at `/home/mcp-servers/` (not in this repo).

---

## Rules

- **MCP servers deploy HERE** (ai-platform namespace) — never prod or monit
- **GitOps only** — commit → push → ArgoCD sync. No manual `kubectl apply`
- **Infisical for all secrets** — use InfisicalSecret CRD or MCP tools
- See global `~/.claude/CLAUDE.md` for full GitOps rules, secret patterns, and git workflow
