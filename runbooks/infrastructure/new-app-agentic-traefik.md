# New Application - Agentic Cluster (Traefik Ingress)

## Overview

Deploy a new application to the agentic cluster (10.20.0.0/24) with internal LAN access via the **Agentic Traefik LoadBalancer** at 10.20.0.90.

This is the **preferred pattern** for agentic cluster services that need internal access, as it's simpler than the Caddy pattern and uses standard Kubernetes Ingress.

## Prerequisites

- Agentic cluster accessible (`export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig`)
- Traefik running in agentic cluster (namespace: traefik)
- AdGuard Home for DNS rewrites
- MCP access: `adguard-mcp`, `infrastructure-mcp`

## Pattern: Agentic Traefik Ingress

For internal apps using Traefik:
1. **Deployment + Service** (ClusterIP or NodePort) in agentic cluster
2. **Traefik Ingress** in agentic cluster
3. **AdGuard DNS rewrite** to resolve hostname to Traefik LB

```
LAN Client → AdGuard DNS (<app>.kernow.io → 10.20.0.90)
          → Agentic Traefik LB (10.20.0.90) → Ingress → Service → Pod
```

## Key IPs

| Service | IP | Purpose |
|---------|-----|---------|
| Agentic Traefik LB | 10.20.0.90 | LoadBalancer via Cilium LB IPAM |
| Agentic Node | 10.20.0.40 | Single node (UM690L baremetal) |
| Caddy (alternative) | 10.10.0.1 | For Caddy pattern (not used here) |

## When to Use This Pattern

**Use Agentic Traefik when:**
- App is for internal homelab use only
- Standard Kubernetes Ingress is sufficient
- TLS termination via Traefik is acceptable
- No Caddy configuration changes desired

**Use Caddy pattern instead when:**
- Need custom reverse proxy features (headers, rewrites)
- App requires specific Caddy middleware
- Legacy compatibility with existing Caddy setup

**Use External Bridge pattern when:**
- External internet access is required
- Cloudflare Tunnel access needed

## Steps

### 1. Create Application in Agentic Cluster

#### Deployment + Service
File: `/home/agentic_lab/kubernetes/applications/<namespace>/<app-name>/deployment.yaml`
```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: <namespace>
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
  namespace: <namespace>
  labels:
    app: <app-name>
spec:
  replicas: 1
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
    spec:
      containers:
        - name: <app-name>
          image: <image>:<tag>
          ports:
            - containerPort: <port>
---
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: <namespace>
spec:
  selector:
    app: <app-name>
  ports:
    - port: <port>
      targetPort: <port>
      nodePort: 3xxxx  # Optional: for fallback direct access
  type: NodePort  # Or ClusterIP if no direct access needed
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app-name>
  namespace: <namespace>
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  rules:
    - host: <app-name>.kernow.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: <app-name>
                port:
                  number: <port>
```

### 2. Configure AdGuard DNS Rewrite

Use `adguard-mcp` to add DNS rewrite:
```
Tool: adguard_add_rewrite
Parameters:
  domain: <app-name>.kernow.io
  answer: 10.20.0.90  # Agentic Traefik LB IP
```

Or manually in AdGuard Home UI:
1. Navigate to Filters → DNS rewrites
2. Add rewrite: `<app-name>.kernow.io` → `10.20.0.90`

### 3. Commit and Push

Using the helper script (recommended):
```bash
/home/scripts/git-commit-submodule.sh agentic_lab "feat: add <app-name> deployment"
```

Or manually:
```bash
cd /home/agentic_lab
git add .
git commit -m "feat: add <app-name> deployment"
git push
```

### 4. Sync ArgoCD

ArgoCD runs in the prod cluster and manages agentic apps:
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'
```

### 5. Verify Deployment

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check pods
kubectl get pods -n <namespace>

# Check service
kubectl get svc <app-name> -n <namespace>

# Check ingress
kubectl get ingress <app-name> -n <namespace>

# Test via Traefik LB
curl -k https://<app-name>.kernow.io

# Test via NodePort (if configured)
curl http://10.20.0.40:<nodeport>
```

## Services Using This Pattern

| Service | Namespace | DNS | NodePort (fallback) |
|---------|-----------|-----|---------------------|
| Backrest | backrest | backrest.kernow.io | 31115 |
| Keep | keep | keep.kernow.io | 31105 |
| Keep Frontend | keep | keep.kernow.io (via path) | 31106 |
| Vikunja | vikunja | vikunja.kernow.io | 31095 |
| Matrix | ai-platform | matrix.kernow.io | 30167 |
| Outline | ai-platform | outline.kernow.io | 31113 |
| Fumadocs | ai-platform | fumadocs.kernow.io | 31099 |
| LangGraph | ai-platform | langgraph.kernow.io | 30800 |
| Claude Refresh | ai-platform | claude-refresh.kernow.io | 31110 |

## Agentic Traefik Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │     AGENTIC CLUSTER (10.20.0.0/24)  │
                                    │                                     │
  LAN Client                        │  ┌─────────────────────────────┐   │
      │                             │  │      Traefik LoadBalancer    │   │
      │ DNS: app.kernow.io          │  │         10.20.0.90           │   │
      ▼                             │  │   (Cilium LB IPAM assigned)  │   │
┌───────────────┐                   │  └──────────────┬──────────────┘   │
│  AdGuard DNS  │                   │                 │                   │
│   10.10.0.1   │──────────────────►│                 ▼                   │
│               │   10.20.0.90      │  ┌─────────────────────────────┐   │
└───────────────┘                   │  │    Traefik Pod (traefik ns) │   │
                                    │  │    Ingress Controller        │   │
                                    │  └──────────────┬──────────────┘   │
                                    │                 │                   │
                                    │    ┌────────────┼────────────┐     │
                                    │    ▼            ▼            ▼     │
                                    │ ┌──────┐   ┌──────┐    ┌──────┐   │
                                    │ │ keep │   │backup│    │vikunj│   │
                                    │ │  ns  │   │ rest │    │ a ns │   │
                                    │ └──────┘   └──────┘    └──────┘   │
                                    └─────────────────────────────────────┘
```

## Traefik Service Details

```yaml
# In namespace: traefik
Name:                     traefik
Type:                     LoadBalancer
Desired LoadBalancer IP:  10.20.0.90  # Via annotation
LoadBalancer Ingress:     10.20.0.90 (VIP)
Ports:
  - web:       80/TCP   (NodePort: 31734)
  - websecure: 443/TCP  (NodePort: 30662)
  - admin:     8080/TCP (NodePort: 30203)
```

The LoadBalancer IP is assigned via **Cilium LB IPAM** with the label:
```yaml
labels:
  io.cilium/lb-ipam-ips: traefik
```

## Troubleshooting

### App not accessible via domain
1. Check DNS resolves to 10.20.0.90: `dig <app-name>.kernow.io`
2. Check Ingress exists: `kubectl get ingress -n <namespace>`
3. Check Traefik pod is running: `kubectl get pods -n traefik`
4. Test via NodePort: `curl http://10.20.0.40:<nodeport>`

### 404 from Traefik
1. Check Ingress host matches DNS
2. Check Ingress service name matches Service name
3. Check Ingress port matches Service port

### 502 Bad Gateway
1. Check backend pod is running
2. Check Service selector matches Pod labels
3. Check Service targetPort matches container port

### TLS Certificate Errors
- Traefik uses self-signed certs by default
- For valid certs, configure cert-manager with Traefik

## Comparison with Other Patterns

| Pattern | DNS Target | Proxy | Use Case |
|---------|-----------|-------|----------|
| **Agentic Traefik** | 10.20.0.90 | Traefik | Internal services, K8s Ingress |
| Caddy + AdGuard | 10.10.0.1 | Caddy | Custom proxy needs, legacy |
| External Bridge | (via Cloudflare) | CF Tunnel | External internet access |

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-internal.md` - Caddy pattern
- `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-external.md` - External Bridge pattern
- `/home/agentic_lab/runbooks/infrastructure/new-app-prod.md` - Production dual-ingress
- `/home/agentic_lab/docs/knowledge-base/domain-routing.md` - Overall routing strategy
