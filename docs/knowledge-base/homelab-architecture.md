# Homelab Architecture

## Overview
Three-cluster Kubernetes homelab running on Proxmox and bare metal, following GitOps principles.

## Clusters

### Production Cluster (prod)
- **Network**: 10.10.0.0/24
- **Platform**: Talos Linux on Proxmox VMs
- **Hardware**: Ruapehu host (i9-12900K, 62GB RAM)
- **Purpose**: Production applications, media services
- **ArgoCD**: YES (manages all prod deployments)
- **MCP Servers**: NO

**Nodes:**
- Control plane: 10.10.0.30
- Worker 1: 10.10.0.41
- Worker 2: 10.10.0.42
- Worker 3: 10.10.0.43

**Key Components:**
- Traefik (LoadBalancer IP: 10.10.0.90)
- cert-manager (Let's Encrypt)
- Cloudflare Tunnel
- Mayastor (block storage)
- Infisical Operator

### Agentic Cluster (agentic)
- **Network**: 10.20.0.0/24
- **Platform**: Talos Linux on bare metal UM690L
- **Hardware**: AMD Ryzen 9 6900HX, 32GB DDR5, 1.5TB NVMe
- **Purpose**: AI platform, Claude agents, MCP servers
- **ArgoCD**: NO (uses different GitOps approach)
- **MCP Servers**: ALL HERE

**Node:**
- 10.20.0.40 (single node cluster)

**Key Components:**
- LiteLLM (Gemini proxy)
- Qdrant (vector database)
- LangGraph (agent orchestration)
- Matrix/Conduit (human-in-the-loop)
- All MCP servers

### Monitoring Cluster (monit)
- **Network**: 10.30.0.0/24
- **Platform**: Talos Linux on VM
- **Purpose**: Observability stack only
- **ArgoCD**: NO
- **MCP Servers**: NO (migrate any found to agentic)

**Components:**
- Prometheus
- Grafana
- Coroot

## Network Architecture

### Network Bridges (Proxmox)
| Bridge | Network | MTU | Purpose |
|--------|---------|-----|---------|
| vmbr0 | 10.10.0.0/24 | 1500 | Management/external |
| vmbr3 | 10.40.0.0/24 | 9000 | TrueNAS NFS traffic |
| vmbr4 | 10.50.0.0/24 | 1500 | Mayastor replication |

### Storage
- **TrueNAS**: 10.10.0.100 (mgmt), 10.40.0.10 (NFS)
- **Mayastor**: Replicated block storage on vmbr4

## External Services

### DNS
- **Cloudflare**: kernow.io domain
- **Unbound**: Local DNS server, wildcard *.kernow.io → 10.10.0.90
- **AdGuard Home**: DNS filtering and rewrites

### Secrets
- **Infisical**: Cloud-hosted, accessed via operator and CLI

### Code
- **GitHub**: All repos hosted at github.com/charlieshreck

## Repository Locations

| Repo | Path | Purpose |
|------|------|---------|
| prod_homelab | /home/prod_homelab | Production cluster |
| agentic_lab | /home/agentic_lab | Agentic platform |
| monit_homelab | /home/monit_homelab | Monitoring |

## Tags for Indexing
`architecture`, `clusters`, `network`, `homelab`, `kubernetes`, `talos`
