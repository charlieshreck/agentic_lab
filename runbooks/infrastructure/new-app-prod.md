# New Application - Production Cluster

## Overview
Deploy a new application to the production cluster (10.10.0.0/24) with dual-ingress pattern for both internal LAN and external internet access.

## Prerequisites
- Production cluster accessible (`export KUBECONFIG=/home/prod_homelab/kubeconfig`)
- ArgoCD configured for the target namespace
- cert-manager and letsencrypt-prod ClusterIssuer deployed
- Cloudflare tunnel controller running

## Pattern: Dual-Ingress

Every prod app requires TWO ingress resources:
1. **Traefik ingress** - Internal LAN access via `*.kernow.io → 10.10.0.90`
2. **Cloudflare-tunnel ingress** - External access via Cloudflare Tunnel

## Steps

### 1. Create Application Directory
```bash
mkdir -p /home/prod_homelab/kubernetes/applications/apps/<app-name>/
```

### 2. Create Deployment
File: `/home/prod_homelab/kubernetes/applications/apps/<app-name>/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
  namespace: apps
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
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
```

### 3. Create Service
File: `/home/prod_homelab/kubernetes/applications/apps/<app-name>/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: apps
  labels:
    app.kubernetes.io/name: <app-name>
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: <port>
      protocol: TCP
  selector:
    app.kubernetes.io/name: <app-name>
```

### 4. Create Traefik Ingress (Internal)
File: `/home/prod_homelab/kubernetes/applications/apps/<app-name>/ingress.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app-name>
  namespace: apps
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    gethomepage.dev/enabled: "true"
    gethomepage.dev/name: "<App Name>"
    gethomepage.dev/group: "Apps"
    gethomepage.dev/icon: "<icon>.png"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - <app-name>.kernow.io
      secretName: <app-name>-tls
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
                  number: 80
```

### 5. Create Cloudflare Tunnel Ingress (External)
File: `/home/prod_homelab/kubernetes/applications/apps/<app-name>/cloudflare-tunnel-ingress.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: <app-name>-cloudflare
  namespace: apps
  labels:
    app: <app-name>
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
                name: <app-name>
                port:
                  number: 80
```

### 6. Create Kustomization
File: `/home/prod_homelab/kubernetes/applications/apps/<app-name>/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - ingress.yaml
  - cloudflare-tunnel-ingress.yaml
```

### 7. Add ArgoCD Application
File: `/home/prod_homelab/kubernetes/argocd-apps/applications/<app-name>.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app-name>
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/homelab-prod.git
    targetRevision: main
    path: kubernetes/applications/apps/<app-name>
  destination:
    server: https://kubernetes.default.svc
    namespace: apps
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 8. Commit and Push
```bash
cd /home/prod_homelab
git add .
git commit -m "feat: add <app-name> application"
git push
```

### 9. Verify Deployment
```bash
export KUBECONFIG=/home/prod_homelab/kubeconfig

# Check ArgoCD sync
kubectl get application <app-name> -n argocd

# Check pods
kubectl get pods -n apps -l app.kubernetes.io/name=<app-name>

# Check ingresses (should see both)
kubectl get ingress -n apps | grep <app-name>

# Check certificate
kubectl get certificate -n apps | grep <app-name>
```

## Key Notes

- **NEVER** use only one ingress type - always create both
- **ALWAYS** use the same hostname for both ingresses
- **ALWAYS** use the `-cloudflare` suffix for tunnel ingress names
- Cloudflare-tunnel ingress does NOT need TLS configuration
- Traefik ingress MUST have TLS configuration for cert-manager
- DNS propagation can take a few minutes after creating cloudflare-tunnel ingress

## Verification

### Internal Access
```bash
# From LAN, should resolve to 10.10.0.90
dig <app-name>.kernow.io
curl -k https://<app-name>.kernow.io
```

### External Access
```bash
# Should resolve to Cloudflare CNAME
dig <app-name>.kernow.io @8.8.8.8
```

## Troubleshooting

### App not accessible externally
1. Check cloudflare-tunnel ingress exists
2. Check cloudflare-tunnel-controller logs
3. Check cloudflared logs

### App not accessible internally
1. Check traefik ingress exists
2. Check Traefik LoadBalancer IP (10.10.0.90)
3. Check Unbound DNS override

## References
- Full documentation: `/home/prod_homelab/docs/DUAL-INGRESS-PATTERN.md`
