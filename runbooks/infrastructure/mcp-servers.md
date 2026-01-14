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
| neo4j-mcp | 31099 | Neo4j knowledge graph (relationships, dependencies) |

## Health Checks

```bash
# Check all MCP servers
for port in 31080 31081 31082 31083 31084 31085 31086 31087 31088 31089 31090 31091 31092 31093 31094; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://10.20.0.40:$port/health)
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
- **ALWAYS use NodePort in range 31080-31099**
- **ALWAYS update `.mcp.json` after adding new MCP**
- **ALWAYS update this runbook after changes**
