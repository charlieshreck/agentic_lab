# MCP Server Deployment Pattern

## Overview
MCP (Model Context Protocol) servers provide tools for AI agents to interact with external services. All MCP servers MUST run in the agentic cluster.

## Location Requirements

| Cluster | MCP Servers Allowed |
|---------|---------------------|
| **agentic** (10.20.0.0/24) | YES - ALL HERE |
| prod (10.10.0.0/24) | NO |
| monit (10.30.0.0/24) | NO |

**Namespace**: ai-platform
**Manifests**: /home/agentic_lab/kubernetes/applications/mcp-servers/

## Deployment Patterns

There are two patterns for deploying MCP servers:

1. **Pre-built Image Pattern** (Preferred) - Use existing Docker images from GHCR/Docker Hub
2. **ConfigMap Pattern** - Custom server code in ConfigMap

### Pattern Selection
| Scenario | Pattern |
|----------|---------|
| Community-maintained MCP exists | Pre-built Image |
| Custom integration needed | ConfigMap |
| Quick prototyping | ConfigMap |
| Production, low maintenance | Pre-built Image |

---

## Pre-built Image Pattern (Recommended)

For MCP servers with maintained Docker images:

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
          image: ghcr.io/<maintainer>/<image>:latest
          ports:
            - containerPort: 3000
          env:
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: mcp-<name>
                  key: API_KEY
            - name: API_URL
              value: "http://<service>/api"  # Internal K8s DNS
            - name: MCP_TRANSPORT
              value: "streamable-http"
            - name: MCP_HOST
              value: "0.0.0.0"
            - name: MCP_PORT
              value: "3000"
          resources:
            requests:
              memory: "128Mi"
              cpu: "50m"
            limits:
              memory: "256Mi"
              cpu: "250m"
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: <name>-mcp
  namespace: ai-platform
spec:
  type: NodePort
  selector:
    app: <name>-mcp
  ports:
    - port: 3000
      targetPort: 3000
      nodePort: 311XX  # Check /root/.claude-ref/mcp-ports.txt
```

**Example**: outline-mcp uses `ghcr.io/vortiago/mcp-outline:latest`

**Benefits:**
- Maintained by community
- Regular security updates
- Less code to maintain
- Well-documented tool interfaces

---

## ConfigMap Pattern (Custom Code)

Every MCP server consists of three Kubernetes resources in a single YAML file:

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
spec:
  type: ClusterIP  # or NodePort if external access needed
  ports:
    - port: 8080
      targetPort: 8080
  selector:
    app.kubernetes.io/name: <name>-mcp
```

## Naming Conventions

| Component | Pattern | Example |
|-----------|---------|---------|
| ConfigMap | `<name>-mcp-code` | `proxmox-mcp-code` |
| Deployment | `<name>-mcp` | `proxmox-mcp` |
| Service | `<name>-mcp` | `proxmox-mcp` |
| File | `<name>-mcp.yaml` | `proxmox-mcp.yaml` |

## Labels

All MCP servers must have:
```yaml
labels:
  app.kubernetes.io/name: <name>-mcp
  app.kubernetes.io/component: mcp-server
```

## Service Types

### ClusterIP (Default)
For MCP servers accessed only from within cluster:
```yaml
spec:
  type: ClusterIP
```

### NodePort
For MCP servers accessed from Claude Code outside cluster:
```yaml
spec:
  type: NodePort
  ports:
    - port: 8080
      targetPort: 8080
      nodePort: 31xxx
```

## Secrets Integration

For MCP servers requiring credentials:

### Using InfisicalSecret
```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: <name>-mcp-secrets
  namespace: ai-platform
spec:
  # ... Infisical configuration
```

### Referencing in Deployment
```yaml
env:
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: <name>-mcp-secrets
        key: api-key
```

## MCP.json Configuration

After deploying MCP server, add to .mcp.json:

### For ClusterIP Services (in-cluster access)
```json
{
  "<name>": {
    "url": "http://<name>-mcp.ai-platform.svc.cluster.local:8080",
    "description": "Description of MCP server"
  }
}
```

### For NodePort Services (external access)
```json
{
  "<name>": {
    "url": "http://10.20.0.40:31xxx/mcp",
    "description": "Description of MCP server"
  }
}
```

**IMPORTANT**: URLs must include `/mcp` path. FastMCP 2.x serves the protocol at this endpoint.

### FastMCP Starlette Pattern (REQUIRED)
```python
mcp_app = mcp.http_app()
app = Starlette(
    routes=rest_routes + [Mount("/", app=mcp_app)],
    lifespan=mcp_app.lifespan  # REQUIRED for FastMCP 2.x
)
```

## Current MCP Servers

(Keep agnostic - this list will grow)

Core servers include:
- infrastructure-mcp: kubectl, talosctl operations
- knowledge-mcp: Qdrant vector DB access
- coroot-mcp: Observability metrics
- proxmox-mcp: VM management
- And many more...

## Deployment Workflow

1. Create YAML file in mcp-servers directory
2. Add to kustomization.yaml
3. Commit and push
4. Verify pod is running
5. Add to .mcp.json if external access needed
6. Test MCP tool invocation

## Migration Notes

If MCP servers found in wrong clusters:
- monit cluster (10.30.0.0/24): REMOVE
- prod cluster (10.10.0.0/24): REMOVE
- Move all to agentic cluster

## Tags for Indexing
`mcp`, `model-context-protocol`, `deployment`, `kubernetes`, `ai-platform`
