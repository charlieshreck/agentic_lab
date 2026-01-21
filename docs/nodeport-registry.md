# Agentic Cluster NodePort Registry

All services exposed via NodePort on the agentic cluster (10.20.0.40).

## Port Allocation Ranges

| Range | Purpose |
|-------|---------|
| 30000-30299 | Core Infrastructure & Agents |
| 30300-30699 | Databases & Data Services |
| 30700-30999 | Application Services |
| 31080-31199 | MCP Servers (reserved block) |
| 31200-31399 | Future MCP expansion |
| 31400-31499 | LLM/AI Services |
| 31500-31999 | General Services |

---

## Core Infrastructure & Agents (30000-30299)

| Port | Service | Description |
|------|---------|-------------|
| 30167 | conduit | Matrix/Conduit server |
| 30168 | matrix-bot | Matrix bot webhook |
| 30200 | claude-agent | Claude agent service |
| 30201 | claude-validator | Claude validation service |
| 30202 | gemini-agent | Gemini agent service |
| 30203 | traefik-https | Traefik HTTPS (LoadBalancer) |

---

## Databases & Data Services (30300-30699)

| Port | Service | Description |
|------|---------|-------------|
| 30400 | litellm-alt | LiteLLM alternate port |
| 30633 | qdrant-http | Qdrant REST API |
| 30634 | qdrant-grpc | Qdrant gRPC API |
| 30662 | traefik-http | Traefik HTTP (LoadBalancer) |

---

## Application Services (30700-30999)

| Port | Service | Description |
|------|---------|-------------|
| 30800 | langgraph | LangGraph orchestration |

---

## MCP Servers (31080-31199)

**Reserved block for all MCP servers.** All expose `/health` endpoint.

| Port | Service | Description | Health Check |
|------|---------|-------------|--------------|
| 31080 | infisical-mcp | Secrets management (read-only) | `curl http://10.20.0.40:31080/health` |
| 31081 | coroot-mcp | Observability, metrics, anomalies | `curl http://10.20.0.40:31081/health` |
| 31082 | proxmox-mcp | VM management | `curl http://10.20.0.40:31082/health` |
| 31083 | infrastructure-mcp | Kubernetes/Talos operations | `curl http://10.20.0.40:31083/health` |
| 31084 | knowledge-mcp | Qdrant knowledge base, runbooks | `curl http://10.20.0.40:31084/health` |
| 31085 | opnsense-mcp | Firewall, DHCP, DNS | `curl http://10.20.0.40:31085/health` |
| 31086 | adguard-mcp | DNS rewrites, filtering | `curl http://10.20.0.40:31086/health` |
| 31087 | cloudflare-mcp | DNS records, tunnels | `curl http://10.20.0.40:31087/health` |
| 31088 | unifi-mcp | Network clients, devices | `curl http://10.20.0.40:31088/health` |
| 31089 | truenas-mcp | Storage management | `curl http://10.20.0.40:31089/health` |
| 31090 | home-assistant-mcp | Smart home control | `curl http://10.20.0.40:31090/health` |
| 31091 | arr-suite-mcp | Media management | `curl http://10.20.0.40:31091/health` |
| 31092 | homepage-mcp | Dashboard widgets | `curl http://10.20.0.40:31092/health` |
| 31093 | web-search-mcp | SearXNG web search | `curl http://10.20.0.40:31093/health` |
| 31094 | browser-automation-mcp | Playwright browser | `curl http://10.20.0.40:31094/health` |
| 31095 | **AVAILABLE** | - | - |
| 31096 | plex-mcp | Plex media server | `curl http://10.20.0.40:31096/health` |
| 31097 | vikunja-mcp | Task/project management | `curl http://10.20.0.40:31097/health` |
| 31098 | neo4j-mcp | Knowledge graph queries | `curl http://10.20.0.40:31098/health` |
| 31099 | fumadocs | Knowledge UI (Next.js) | `curl http://10.20.0.40:31099/` |
| 31100 | tasmota-mcp | Tasmota smart devices | `curl http://10.20.0.40:31100/health` |
| 31101 | monitoring-mcp | VictoriaMetrics, Grafana, Gatus | `curl http://10.20.0.40:31101/health` |
| 31102 | alerting-pipeline | Alert processing | - |
| 31103 | mcp-config-sync | MCP config sync | - |
| 31104 | reddit-mcp | Reddit browsing | `curl http://10.20.0.40:31104/health` |
| 31105 | keep | Keep API (internal) | - |
| 31106 | keep-frontend | Keep UI | - |
| 31107 | keep-mcp | Keep alert aggregation | `curl http://10.20.0.40:31107/health` |
| 31108 | **AVAILABLE** | - | - |
| 31109 | **AVAILABLE** | - | - |
| 31110 | claude-refresh | Claude token refresh | - |
| 31111 | github-mcp | GitHub repos, issues, PRs | `curl http://10.20.0.40:31111/health` |
| 31112 | wikipedia-mcp | Wikipedia articles | `curl http://10.20.0.40:31112/health` |
| 31113 | outline | Outline wiki (internal) | - |
| 31114 | outline-mcp | Outline wiki MCP | `curl http://10.20.0.40:31114/health` |
| 31115 | backrest | Backrest backup UI | - |

---

## LLM/AI Services (31400-31499)

| Port | Service | Description |
|------|---------|-------------|
| 31400 | litellm | LiteLLM proxy (primary) |
| 31434 | ollama | Ollama inference server |

---

## Other Namespaces

| Port | Service | Namespace | Description |
|------|---------|-----------|-------------|
| 31095 | vikunja | vikunja | Vikunja app |
| 31115 | backrest | backrest | Backrest backup UI |
| 31105 | keep | keep | Keep API |
| 31106 | keep-frontend | keep | Keep UI |

---

## Next Available Ports

### MCP Block (31080-31199)
- 31095
- 31108-31109
- 31116-31199

### General Use
- 30204-30299 (Infrastructure)
- 30301-30399 (Databases)
- 30401-30632 (Databases)
- 30635-30661 (Databases)
- 30801-30999 (Applications)
- 31500-31733 (General)
- 31735-31999 (General)

---

## Adding a New Service

1. **Check this registry** for available ports in the appropriate range
2. **Reserve the port** by updating this document BEFORE deploying
3. **Update `/root/.claude-ref/nodeport-registry.txt`** for quick local reference
4. **Commit changes** to both files

### Example Service Definition

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-new-mcp
  namespace: ai-platform
spec:
  type: NodePort
  ports:
  - port: 8000
    targetPort: 8000
    nodePort: 31108  # From available MCP ports
  selector:
    app: my-new-mcp
```

---

## Verification Commands

```bash
# List all NodePort services
kubectl get svc -A -o wide | grep NodePort

# Check specific port availability
kubectl get svc -A -o json | jq '.items[].spec.ports[]?.nodePort' | grep 31108

# Test MCP health endpoints
for port in 31080 31081 31082 31083 31084; do
  echo -n "Port $port: "
  curl -s -o /dev/null -w "%{http_code}" http://10.20.0.40:$port/health
  echo
done
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-21 | Initial registry created from cluster audit |
