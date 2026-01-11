# New Application - Agentic Cluster (External Access)

## Overview
Deploy a new application to the agentic cluster (10.20.0.0/24) with external internet access via the External Service Bridge pattern.

## Prerequisites
- Agentic cluster accessible (`export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig`)
- Production cluster accessible (for bridge resources)
- Cloudflare tunnel controller running in prod cluster

## Pattern: External Service Bridge

Since Cloudflare Tunnel only runs in prod cluster, agentic apps needing external access require:
1. **NodePort service** in agentic cluster
2. **Bridge Service + Endpoints** in prod cluster pointing to agentic NodePort
3. **Cloudflare-tunnel ingress** in prod cluster

```
Internet → Cloudflare Tunnel → Prod Cluster (Service+Endpoints)
         → Agentic Cluster (NodePort 10.20.0.40:3xxxx) → App
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
      nodePort: 3xxxx  # Choose unused port in 30000-32767 range
      protocol: TCP
  selector:
    app.kubernetes.io/name: <app-name>
```

### 2. Create Bridge Resources in Prod Cluster

#### Bridge Service (no selector)
File: `/home/prod_homelab/kubernetes/applications/apps/agentic-external/services.yaml`
Add to existing file:
```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: <app-name>-external
  namespace: apps
  labels:
    app.kubernetes.io/name: <app-name>-external
spec:
  type: ClusterIP
  ports:
    - name: http
      port: 80
      protocol: TCP
```

#### Bridge Endpoints
File: `/home/prod_homelab/kubernetes/applications/apps/agentic-external/endpoints.yaml`
Add to existing file:
```yaml
---
apiVersion: v1
kind: Endpoints
metadata:
  name: <app-name>-external
  namespace: apps
subsets:
  - addresses:
      - ip: 10.20.0.40  # Agentic cluster node IP
    ports:
      - name: http
        port: 3xxxx  # NodePort from agentic service
        protocol: TCP
```

#### Cloudflare Tunnel Ingress
File: `/home/prod_homelab/kubernetes/applications/apps/agentic-external/cloudflare-tunnel-ingresses.yaml`
Add to existing file:
```yaml
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app-name>-cloudflare
  namespace: apps
  annotations:
    gethomepage.dev/enabled: "true"
    gethomepage.dev/name: "<App Name>"
    gethomepage.dev/group: "Agentic"
    gethomepage.dev/icon: "<icon>.png"
    gethomepage.dev/description: "<description>"
    gethomepage.dev/pod-selector: ""
spec:
  ingressClassName: cloudflare-tunnel
  rules:
    - host: <app-name>.kernow.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: <app-name>-external
                port:
                  number: 80
```

### 3. Commit and Push Both Repos
```bash
# Agentic cluster changes
cd /home/agentic_lab
git add .
git commit -m "feat: add <app-name> deployment"
git push

# Prod cluster bridge
cd /home/prod_homelab
git add .
git commit -m "feat: add external bridge for <app-name>"
git push
```

### 4. Verify Deployment

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

#### In Prod Cluster
```bash
export KUBECONFIG=/home/prod_homelab/kubeconfig

# Check bridge service
kubectl get svc <app-name>-external -n apps

# Check endpoints
kubectl get endpoints <app-name>-external -n apps

# Check ingress
kubectl get ingress <app-name>-cloudflare -n apps
```

## NodePort Allocation

Current allocations in agentic cluster:
| Port | Service |
|------|---------|
| 30080 | netbox |
| 30167 | matrix/conduit |
| 30800 | langgraph |

Choose next available port for new services.

## Key Notes

- Service name in prod MUST match Endpoints name
- Endpoints name MUST match the Service it backs
- NodePort must be in range 30000-32767
- Homepage annotations go on the cloudflare ingress in prod
- The `-external` suffix distinguishes bridge services

## Troubleshooting

### 502 Bad Gateway
1. Check agentic pod is running
2. Check NodePort is accessible: `curl http://10.20.0.40:<nodeport>`
3. Check Endpoints have correct IP and port

### DNS not resolving
1. Check cloudflare-tunnel-controller logs in prod
2. Check ingress has correct hostname

### Homepage not showing app
1. Check homepage annotations on cloudflare ingress
2. Empty `pod-selector` is required for external services

## References
- Example: `/home/prod_homelab/kubernetes/applications/apps/agentic-external/`
