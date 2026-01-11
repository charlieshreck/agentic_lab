# ArgoCD Applications for Agentic Cluster

## Architecture

**ArgoCD runs ONLY in the prod cluster (10.10.0.0/24)** and manages the agentic cluster remotely.

These Application manifests define what ArgoCD should deploy to the agentic cluster.

## How It Works

1. Application manifests in this directory define:
   - Source: Git path in this repo (`kubernetes/applications/<app>/`)
   - Destination: Agentic cluster API (`https://10.20.0.40:6443`)

2. These manifests are applied to the **prod cluster** (not agentic)

3. ArgoCD in prod watches this repo and deploys to agentic remotely

## Creating a New Application

```bash
# 1. Create application manifests
mkdir -p ../applications/my-app
# Add deployment.yaml, service.yaml, etc.

# 2. Create ArgoCD Application
cat > my-app.yaml << 'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/agentic_lab.git
    targetRevision: main
    path: kubernetes/applications/my-app
  destination:
    server: https://10.20.0.40:6443
    namespace: ai-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

# 3. Commit and push
git add . && git commit -m "Add my-app" && git push

# 4. Apply to PROD cluster (one-time)
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl apply -f my-app.yaml
```

## Checking Status

```bash
# List all applications (from prod cluster)
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl get applications -n argocd

# Check specific app
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl describe application mcp-servers -n argocd
```

## Current Applications

| Application | Path | Namespace |
|-------------|------|-----------|
| mcp-servers | kubernetes/applications/mcp-servers | ai-platform |
| litellm | kubernetes/applications/litellm | ai-platform |
| qdrant | kubernetes/applications/qdrant | ai-platform |
| postgresql | kubernetes/applications/postgresql | ai-platform |
| redis | kubernetes/applications/redis | ai-platform |
| langgraph | kubernetes/applications/langgraph | ai-platform |
| cert-manager | kubernetes/platform/cert-manager | cert-manager |
| infisical-operator | kubernetes/platform/infisical | infisical-operator-system |
