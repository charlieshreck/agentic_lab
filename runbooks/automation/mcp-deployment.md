# MCP Server Deployment Pattern

## Overview
MCP (Model Context Protocol) servers provide tools for AI agents to interact with external services. ALL MCP servers run in the agentic cluster (10.20.0.0/24), ai-platform namespace.

## Location
- Cluster: Agentic (10.20.0.0/24)
- Namespace: `ai-platform`
- Manifests: `/home/agentic_lab/kubernetes/applications/mcp-servers/`

## Pattern: ConfigMap + Deployment + Service

Every MCP server follows the same structure:

### 1. ConfigMap (Server Code)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: <name>-mcp-code
  namespace: ai-platform
data:
  server.py: |
    # Python MCP server implementation
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    # ... server code
```

### 2. Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <name>-mcp
  namespace: ai-platform
  labels:
    app.kubernetes.io/name: <name>-mcp
    app.kubernetes.io/component: mcp-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: <name>-mcp
  template:
    metadata:
      labels:
        app.kubernetes.io/name: <name>-mcp
        app.kubernetes.io/component: mcp-server
    spec:
      containers:
        - name: mcp-server
          image: python:3.11-slim
          command: ["python", "/app/server.py"]
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: code
              mountPath: /app
          env:
            - name: MCP_SERVER_NAME
              value: "<name>-mcp"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
      volumes:
        - name: code
          configMap:
            name: <name>-mcp-code
```

### 3. Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: <name>-mcp
  namespace: ai-platform
  labels:
    app.kubernetes.io/name: <name>-mcp
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: 8080
      protocol: TCP
  selector:
    app.kubernetes.io/name: <name>-mcp
```

## Deployment Steps

### 1. Create MCP Server File
```bash
cat > /home/agentic_lab/kubernetes/applications/mcp-servers/<name>-mcp.yaml << 'EOF'
# ConfigMap with server code
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: <name>-mcp-code
  namespace: ai-platform
data:
  server.py: |
    # Your MCP server code here
---
# Deployment
apiVersion: apps/v1
kind: Deployment
# ... deployment spec
---
# Service
apiVersion: v1
kind: Service
# ... service spec
EOF
```

### 2. Add to Kustomization
Edit `/home/agentic_lab/kubernetes/applications/mcp-servers/kustomization.yaml`:
```yaml
resources:
  - existing-mcp.yaml
  - <name>-mcp.yaml  # Add new MCP
```

### 3. Commit and Push
```bash
cd /home/agentic_lab
git add .
git commit -m "feat: add <name>-mcp server"
git push
```

### 4. Verify Deployment
```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

kubectl get pods -n ai-platform -l app.kubernetes.io/name=<name>-mcp
kubectl logs -n ai-platform -l app.kubernetes.io/name=<name>-mcp
```

## Naming Conventions

| Component | Pattern | Example |
|-----------|---------|---------|
| ConfigMap | `<name>-mcp-code` | `proxmox-mcp-code` |
| Deployment | `<name>-mcp` | `proxmox-mcp` |
| Service | `<name>-mcp` | `proxmox-mcp` |
| File | `<name>-mcp.yaml` | `proxmox-mcp.yaml` |

## Labels

All MCP servers should have:
```yaml
labels:
  app.kubernetes.io/name: <name>-mcp
  app.kubernetes.io/component: mcp-server
```

## Secrets Integration

For MCP servers needing secrets (API keys, credentials):

```yaml
env:
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: <name>-mcp-secrets
        key: api-key
```

Create InfisicalSecret:
```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: <name>-mcp-secrets
  namespace: ai-platform
spec:
  # ... Infisical config
```

## Current MCP Servers

| Server | Purpose | Tools |
|--------|---------|-------|
| infrastructure-mcp | kubectl, talosctl | kubectl_*, talosctl_* |
| knowledge-mcp | Qdrant, entities | search_*, get_entity |
| coroot-mcp | Observability | get_metrics, get_anomalies |
| proxmox-mcp | VM management | list_vms, start_vm |
| opnsense-mcp | Firewall | get_firewall_rules |
| unifi-mcp | Network | list_clients, list_devices |
| adguard-mcp | DNS filtering | add_dns_rewrite |
| cloudflare-mcp | DNS, tunnels | manage_dns |
| truenas-mcp | Storage | list_pools, list_datasets |
| home-assistant-mcp | Smart home | list_*, control_* |
| arr-suite-mcp | Media | manage_sonarr, manage_radarr |
| infisical-mcp | Secrets | get_secret |
| homepage-mcp | Discovery | list_services |
| web-search-mcp | SearXNG | web_search |
| browser-automation-mcp | Playwright | navigate, screenshot |

## Forbidden Actions

- **NEVER** deploy MCP servers to prod cluster
- **NEVER** deploy MCP servers to monit cluster
- **ALWAYS** deploy to agentic cluster, ai-platform namespace

If you find MCP references in other clusters, remove them.

## Testing

After deployment, test via Claude Code:
1. Check MCP is listed in `.mcp.json`
2. Invoke a tool from the MCP
3. Verify expected response

## Troubleshooting

### Pod CrashLoopBackOff
- Check logs: `kubectl logs -n ai-platform <pod>`
- Usually syntax error in server.py

### MCP Not Responding
- Check service exists: `kubectl get svc -n ai-platform`
- Check endpoints: `kubectl get endpoints -n ai-platform`

### Missing Dependencies
- Add pip install in container command or use custom image
