# ArgoCD Patterns

## Overview
ArgoCD provides GitOps continuous deployment for the production cluster. All application deployments follow the app-of-apps pattern.

## Location
- **Cluster**: Production (10.10.0.0/24) only
- **Namespace**: argocd
- **Repo**: /home/prod_homelab

## App-of-Apps Pattern

### Structure
```
kubernetes/
├── argocd-apps/           # ArgoCD Application manifests
│   ├── bootstrap.yaml     # Root application (deploys all others)
│   ├── platform/          # Core infrastructure apps
│   │   ├── cert-manager.yaml
│   │   ├── traefik.yaml
│   │   └── infisical.yaml
│   └── applications/      # User-facing apps
│       ├── filebrowser.yaml
│       ├── homeassistant.yaml
│       └── media-apps.yaml
├── platform/              # Platform component configs
│   ├── cert-manager/
│   ├── traefik/
│   └── infisical/
└── applications/          # Application configs
    ├── apps/
    │   ├── filebrowser/
    │   └── homeassistant/
    └── media/
        ├── sonarr/
        └── radarr/
```

### Bootstrap App
The root application that deploys all other applications:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bootstrap
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/homelab-prod.git
    targetRevision: main
    path: kubernetes/argocd-apps
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Application Template
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
    path: kubernetes/applications/<category>/<app-name>
  destination:
    server: https://kubernetes.default.svc
    namespace: <target-namespace>
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Kustomize Pattern

Each application directory uses Kustomize:
```
<app-name>/
├── kustomization.yaml
├── deployment.yaml
├── service.yaml
├── ingress.yaml
├── cloudflare-tunnel-ingress.yaml
└── secrets.yaml (InfisicalSecret)
```

### kustomization.yaml
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - ingress.yaml
  - cloudflare-tunnel-ingress.yaml
```

## Sync Policies

### Automated Sync
Most apps use automated sync with pruning:
```yaml
syncPolicy:
  automated:
    prune: true      # Remove resources not in git
    selfHeal: true   # Revert manual changes
```

### Manual Sync
For sensitive apps, use manual sync:
```yaml
syncPolicy: {}  # Empty = manual sync only
```

## Common Operations

### Check Application Status
```bash
export KUBECONFIG=/home/prod_homelab/kubeconfig
kubectl get applications -n argocd
```

### Force Sync
```bash
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'
```

### View Sync Details
```bash
kubectl describe application <app-name> -n argocd
```

### Check Logs
```bash
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=50
```

## Namespaces

| Namespace | Purpose | Apps |
|-----------|---------|------|
| apps | General applications | filebrowser, homeassistant, vaultwarden |
| media | Media services | sonarr, radarr, prowlarr, transmission |
| argocd | ArgoCD itself | argocd-server, argocd-repo-server |
| traefik | Ingress controller | traefik |
| cert-manager | Certificate management | cert-manager |
| cloudflared | Cloudflare tunnel | cloudflared |

## GitOps Workflow

1. Make changes to manifests in /home/prod_homelab
2. Commit and push to GitHub
3. ArgoCD detects changes (webhook or poll)
4. ArgoCD syncs changes to cluster
5. Verify deployment succeeded

**NEVER**: `kubectl apply` directly
**ALWAYS**: Commit → Push → ArgoCD sync

## Tags for Indexing
`argocd`, `gitops`, `deployment`, `kubernetes`, `app-of-apps`, `kustomize`
