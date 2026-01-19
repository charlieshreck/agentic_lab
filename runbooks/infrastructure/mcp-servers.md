# MCP Servers - Access and Management

## Overview

All MCP (Model Context Protocol) servers run exclusively in the **agentic cluster** (10.20.0.0/24) in the `ai-platform` namespace. They are exposed via NodePort for external access.

## Architecture

```
Claude Code / Agents
        │
        ▼
   10.20.0.40:NodePort
        │
        ▼
   Kubernetes Service (NodePort)
        │
        ▼
   MCP Server Pod (ai-platform namespace)
        │
        ▼
   External API (Proxmox, UniFi, etc.)
```

## NodePort Allocation

**Range**: 31080-31199 reserved for MCP servers

| MCP Server | NodePort | Purpose |
|------------|----------|---------|
| infisical-mcp | 31080 | Secrets management (read-only) |
| coroot-mcp | 31081 | Observability, metrics, anomalies |
| proxmox-mcp | 31082 | VM/container management |
| infrastructure-mcp | 31083 | kubectl, talosctl operations |
| knowledge-mcp | 31084 | Qdrant vector DB, runbooks |
| opnsense-mcp | 31085 | Firewall, DHCP, DNS |
| adguard-mcp | 31086 | DNS filtering, rewrites |
| cloudflare-mcp | 31087 | DNS records, tunnels |
| unifi-mcp | 31088 | Network clients, devices, WLANs |
| truenas-mcp | 31089 | Storage pools, datasets, shares |
| home-assistant-mcp | 31090 | Smart home control |
| arr-suite-mcp | 31091 | Sonarr, Radarr, Prowlarr |
| homepage-mcp | 31092 | Service discovery |
| web-search-mcp | 31093 | SearXNG web search |
| browser-automation-mcp | 31094 | Playwright browser automation |
| plex-mcp | 31096 | Plex Media Server (31095 reserved) |
| vikunja-mcp | 31097 | Vikunja task management |
| neo4j-mcp | 31098 | Neo4j knowledge graph |
| tasmota-mcp | 31100 | Tasmota smart device control |
| monitoring-mcp | 31101 | VictoriaMetrics, Grafana, Gatus |
| reddit-mcp | 31104 | Reddit browsing, discussions |
| keep-mcp | 31107 | Alert aggregation, correlation |
| github-mcp | 31111 | GitHub repos, issues, PRs |
| wikipedia-mcp | 31112 | Wikipedia articles, knowledge |
| outline-mcp | 31114 | Outline wiki document management |

### Reserved Ports (Non-MCP)
| Service | NodePort | Purpose |
|---------|----------|---------|
| alerting-pipeline | 31102 | Alert webhook receiver |
| mcp-config-sync | 31103 | MCP configuration sync |
| keep | 31105 | Keep alert platform |
| keep-frontend | 31106 | Keep UI |
| claude-refresh | 31110 | Claude token refresh |
| outline | 31113 | Outline wiki application |

## Health Checks

```bash
# Check all MCP servers
MCP_PORTS="31080 31081 31082 31083 31084 31085 31086 31087 31088 31089 31090 31091 31092 31093 31094 31096 31097 31098 31100 31101 31104 31107 31111 31112 31114"
for port in $MCP_PORTS; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://10.20.0.40:$port/health 2>/dev/null || echo "ERR")
  echo "Port $port: $status"
done
```

## Configuration

MCP servers are configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "proxmox": {
      "url": "http://10.20.0.40:31082/mcp",
      "description": "Proxmox VE - VMs, containers, storage"
    }
  }
}
```

**IMPORTANT**: All MCP URLs must include the `/mcp` path suffix. FastMCP 2.x serves the MCP protocol at the `/mcp` endpoint.

## Troubleshooting

### MCP Not Responding

1. Check pod status:
   ```bash
   KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
     kubectl get pods -n ai-platform -l app=<mcp-name>
   ```

2. Check logs:
   ```bash
   KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
     kubectl logs -n ai-platform deployment/<mcp-name> --tail=50
   ```

3. Check service:
   ```bash
   KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
     kubectl get svc -n ai-platform <mcp-name>
   ```

### API Authentication Errors

MCP servers use secrets from Infisical. Check:
1. InfisicalSecret exists: `kubectl get infisicalsecret -n ai-platform`
2. Secret synced: `kubectl get secret mcp-<service> -n ai-platform`
3. Correct secret path in Infisical

### Adding New MCP Server

1. Create manifest in `/home/agentic_lab/kubernetes/applications/mcp-servers/<name>-mcp.yaml`
2. Include: ConfigMap (code), Deployment, Service (NodePort)
3. Add InfisicalSecret if API credentials needed
4. Add to kustomization.yaml
5. Update `.mcp.json` with new endpoint
6. Commit, push, ArgoCD syncs automatically

## Important Rules

- **ALL MCP servers belong in agentic cluster ONLY**
- **NEVER deploy MCPs to prod or monit clusters**
- **ALWAYS use NodePort in range 31080-31199** (check existing allocations first!)
- **ALWAYS update `.mcp.json` after adding new MCP**
- **ALWAYS update this runbook after changes**
- **ALWAYS update `/root/.claude-ref/mcp-ports.txt` after port allocation**

## NodePort Allocation Checklist

Before allocating a new NodePort:
```bash
# Check all services in 311xx range
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get svc -A -o custom-columns="NAME:.metadata.name,NODEPORT:.spec.ports[*].nodePort" | grep "311" | sort -t: -k2

# Check reference file
cat /root/.claude-ref/mcp-ports.txt
```

## Pre-built Image Pattern

For MCP servers with maintained Docker images (preferred when available):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <name>-mcp
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: <name>-mcp
  template:
    metadata:
      labels:
        app: <name>-mcp
        component: mcp
    spec:
      containers:
        - name: mcp-server
          image: ghcr.io/<maintainer>/<name>:latest
          ports:
            - containerPort: 3000
          env:
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: mcp-<name>
                  key: API_KEY
            - name: MCP_TRANSPORT
              value: "streamable-http"
```

**Benefits of pre-built images:**
- Maintained by community
- Regular security updates
- Less code to maintain
- Documented tool interfaces
