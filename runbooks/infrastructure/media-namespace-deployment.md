# Media Namespace Deployment — Fix for Tautulli and Media Apps Unavailability

## Problem

Media applications (tautulli, sonarr, radarr, etc.) failed to start with "0 available replicas" because the **media namespace was never created**.

## Root Cause

Each media application's ArgoCD app definition (e.g., `tautulli-app.yaml`) includes `CreateNamespace=true` to auto-create the namespace. However:

1. **Individual media apps were pointed at subdirectories**: Each app's `path` was set to `kubernetes/applications/media/<app-name>` (e.g., `kubernetes/applications/media/tautulli`)
2. **Namespace manifest was in the parent directory**: The `namespace.yaml` file existed at `kubernetes/applications/media/namespace.yaml`
3. **Namespace wasn't synced**: Because each app only looked at its subdirectory, the namespace.yaml manifest was never included in any ArgoCD sync
4. **CreateNamespace=true created a namespace, but didn't sync the manifest**: ArgoCD's `CreateNamespace=true` only creates the namespace object itself; it doesn't manage the namespace.yaml manifest. Once the namespace was created by the first app, subsequent apps didn't need the flag, but the namespace.yaml was still never synced.

## Solution

Create a dedicated **media-namespace** ArgoCD Application that manages the namespace manifest:

**File**: `/home/prod_homelab/kubernetes/argocd-apps/applications/media-namespace-app.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: media-namespace
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/prod_homelab.git
    targetRevision: main
    path: kubernetes/applications/media
    directory:
      include: 'namespace.yaml'
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

This app ensures:
- The namespace manifest is explicitly synced via ArgoCD
- The namespace is always created before other media apps attempt to deploy
- Namespace configuration (labels, pod-security policies) are managed as code

## Verification

After the fix is deployed:

```bash
# 1. Verify namespace exists
kubectl get namespace media

# 2. Verify all media apps are synced
kubectl get app -n argocd | grep -E 'media|tautulli|sonarr'

# 3. Verify media pods are running
kubectl get pods -n media
```

## Prevention

- Always create a dedicated namespace app for application groups (e.g., media, apps, monitoring)
- Don't rely solely on individual app's `CreateNamespace=true`
- Use directory includes to explicitly sync namespace manifests

---

**Fixed in commit**: `78944d5` (prod_homelab)
**Created**: 2026-02-26
**Tags**: ArgoCD, namespace, media-apps, deployment
