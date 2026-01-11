# New Application - Agentic Cluster (Internal Only)

## Overview
Deploy a new application to the agentic cluster (10.20.0.0/24) with internal LAN access only via Caddy reverse proxy and AdGuard DNS rewrite.

## Prerequisites
- Agentic cluster accessible (`export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig`)
- Caddy running on Unbound server (10.10.0.1)
- AdGuard Home for DNS rewrites
- MCP access: `adguard-mcp`, `knowledge-mcp`

## Pattern: Caddy + AdGuard

For internal-only apps:
1. **NodePort service** in agentic cluster
2. **AdGuard DNS rewrite** to resolve hostname to Caddy
3. **Caddy reverse proxy** entry to forward to NodePort

```
LAN Client → AdGuard DNS (<app>.kernow.io → 10.10.0.1)
          → Caddy (10.10.0.1) → Agentic NodePort (10.20.0.40:3xxxx)
```

## Steps

### 1. Create Application in Agentic Cluster

#### Deployment
File: `/home/agentic_lab/kubernetes/applications/<namespace>/<app-name>/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
  namespace: <namespace>
  labels:
    app.kubernetes.io/name: <app-name>
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: <app-name>
  template:
    metadata:
      labels:
        app.kubernetes.io/name: <app-name>
    spec:
      containers:
        - name: <app-name>
          image: <image>:<tag>
          ports:
            - containerPort: <port>
```

#### NodePort Service
File: `/home/agentic_lab/kubernetes/applications/<namespace>/<app-name>/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: <namespace>
  labels:
    app.kubernetes.io/name: <app-name>
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: <port>
      nodePort: 3xxxx  # Choose unused port
      protocol: TCP
  selector:
    app.kubernetes.io/name: <app-name>
```

### 2. Configure AdGuard DNS Rewrite

Use `adguard-mcp` to add DNS rewrite:
```
Tool: add_dns_rewrite
Parameters:
  domain: <app-name>.kernow.io
  answer: 10.10.0.1  # Caddy server IP
```

Or manually in AdGuard Home UI:
1. Navigate to Filters → DNS rewrites
2. Add rewrite: `<app-name>.kernow.io` → `10.10.0.1`

### 3. Configure Caddy Reverse Proxy

Add entry to Caddy configuration on 10.10.0.1:

```caddyfile
<app-name>.kernow.io {
    reverse_proxy 10.20.0.40:3xxxx
    tls internal
}
```

Reload Caddy:
```bash
ssh root@10.10.0.1 "systemctl reload caddy"
```

### 4. Commit and Push
```bash
cd /home/agentic_lab
git add .
git commit -m "feat: add <app-name> deployment"
git push
```

### 5. Verify Deployment

#### In Agentic Cluster
```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check pods
kubectl get pods -n <namespace> -l app.kubernetes.io/name=<app-name>

# Check NodePort
kubectl get svc <app-name> -n <namespace>

# Test NodePort directly
curl http://10.20.0.40:3xxxx
```

#### DNS and Access
```bash
# Check DNS resolves to Caddy
dig <app-name>.kernow.io

# Should return 10.10.0.1

# Test access
curl -k https://<app-name>.kernow.io
```

## MCP Tools

### AdGuard DNS Rewrite
```
adguard-mcp:
  - add_dns_rewrite(domain, answer)
  - remove_dns_rewrite(domain)
  - list_dns_rewrites()
```

### Search Existing Runbooks
```
knowledge-mcp:
  - search_runbooks("caddy")
  - search_runbooks("adguard")
```

## Key Notes

- Internal-only apps are NOT accessible from internet
- Caddy handles TLS with internal certificates
- AdGuard DNS rewrite only works for LAN clients
- No Homepage annotations needed (not in prod cluster)

## Troubleshooting

### App not accessible
1. Check DNS resolves: `dig <app-name>.kernow.io`
2. Check Caddy is proxying: `curl -v https://<app-name>.kernow.io`
3. Check NodePort is accessible: `curl http://10.20.0.40:<nodeport>`

### DNS not resolving
1. Check AdGuard rewrite exists
2. Check client is using AdGuard DNS server
3. Clear DNS cache on client

### Certificate warnings
- Expected with Caddy internal TLS
- Add exception or configure Caddy with Let's Encrypt

## When to Use This Pattern

Use internal-only pattern when:
- App is for internal homelab use only
- App contains sensitive data not for internet exposure
- App is for development/testing
- App is an MCP server (only Claude Code needs access)

Use External Bridge pattern instead when:
- Remote access needed
- Mobile app access required
- External collaborators need access
