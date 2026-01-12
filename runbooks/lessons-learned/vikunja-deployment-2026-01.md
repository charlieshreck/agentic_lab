# Lessons Learned: Vikunja Deployment (January 2026)

## Summary

Deployed Vikunja (kanban/todo app) and vikunja-mcp to the agentic cluster with both external (Cloudflare tunnel) and internal (Caddy + AdGuard) access.

## What Went Well

1. **External Service Bridge Pattern** - Successfully bridged agentic cluster NodePort to prod cluster for Cloudflare tunnel access
2. **AdGuard DNS API** - Direct API calls worked reliably for DNS rewrite management
3. **OPNsense Caddy API** - Successfully configured reverse proxy via REST API
4. **Plain K8s Deployment** - Simpler and more reliable than Helm chart approach

## Issues Encountered

### 1. Missing ArgoCD Application Manifest

**Problem**: Vikunja pod didn't exist because no ArgoCD Application was created.

**Root Cause**: Created the deployment manifests but forgot to create the ArgoCD Application that tells ArgoCD to deploy them.

**Fix**: Created `/home/agentic_lab/kubernetes/argocd-apps/vikunja-app.yaml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vikunja
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/agentic_lab.git
    targetRevision: main
    path: kubernetes/applications/vikunja
  destination:
    server: https://10.20.0.40:6443
    namespace: vikunja
```

**Lesson**: Always create BOTH the application manifests AND the ArgoCD Application that deploys them.

---

### 2. Kustomize helmCharts Requires --enable-helm

**Problem**: ArgoCD sync failed with error:
```
must specify --enable-helm
```

**Root Cause**: Using `helmCharts` in kustomization.yaml requires ArgoCD to have `--enable-helm` flag enabled, which it doesn't by default.

**Attempted Solution**: Tried ArgoCD multi-source application with Helm chart type.

**Final Solution**: Abandoned Helm entirely and used plain Kubernetes manifests.

**Lesson**: Kustomize `helmCharts` is NOT supported by ArgoCD without additional configuration. Prefer plain K8s manifests or native ArgoCD Helm sources.

---

### 3. OCI Helm Chart Not Found

**Problem**: When attempting multi-source ArgoCD application:
```
oci://ghcr.io/go-vikunja/helm-chart/vikunja:0.2.6: not found
```

**Root Cause**: The Vikunja OCI Helm chart URL was incorrect or requires authentication.

**Solution**: Switched to plain Kubernetes deployment using the official `vikunja/vikunja:0.24.6` Docker image directly.

**Lesson**: Official Helm charts may have issues (wrong URLs, auth requirements). Plain K8s deployments are often simpler and more reliable.

---

### 4. SSH to OPNsense Failed

**Problem**: Attempting to SSH to OPNsense to configure Caddy failed:
```
Too many authentication failures
```

**Solution**: Used OPNsense REST API directly with credentials from Infisical.

**Lesson**: OPNsense plugins (including Caddy) expose REST APIs. Use API access over SSH when possible.

---

## Final Architecture

```
┌─────────────────── Agentic Cluster (10.20.0.0/24) ───────────────────┐
│                                                                       │
│  ┌─────────────────────┐         ┌─────────────────────────────┐     │
│  │   vikunja           │         │      vikunja-mcp            │     │
│  │   (Plain K8s)       │◄───────►│   (FastMCP + REST API)      │     │
│  │   namespace:vikunja │  k8s    │   namespace: ai-platform    │     │
│  │                     │  svc    │                             │     │
│  │   NodePort: 31095   │         │   NodePort: 31097           │     │
│  └─────────────────────┘         └─────────────────────────────┘     │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
    ┌─────────────┐                    Claude Code / Agents
    │ Prod Cluster │                    (MCP tools)
    │ External     │
    │ Bridge       │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐
    │ Cloudflare      │◄── vikunja.kernow.io (external)
    │ Tunnel          │
    └─────────────────┘

    ┌─────────────────┐
    │ Caddy (OPNsense)│◄── vikunja.kernow.io (internal)
    │ + AdGuard DNS   │
    └─────────────────┘
```

## Files Created/Modified

### Agentic Cluster (agentic_lab)
| File | Purpose |
|------|---------|
| `kubernetes/applications/vikunja/namespace.yaml` | Namespace definition |
| `kubernetes/applications/vikunja/deployment.yaml` | Deployment + PVCs + Service |
| `kubernetes/applications/vikunja/infisical-secret.yaml` | InfisicalSecret CRD |
| `kubernetes/applications/vikunja/kustomization.yaml` | Kustomize configuration |
| `kubernetes/argocd-apps/vikunja-app.yaml` | ArgoCD Application |
| `kubernetes/applications/mcp-servers/vikunja-mcp.yaml` | MCP server (14 tools) |

### Prod Cluster (prod_homelab)
| File | Purpose |
|------|---------|
| `kubernetes/applications/apps/agentic-external/services.yaml` | External bridge service |
| `kubernetes/applications/apps/agentic-external/endpoints.yaml` | Endpoint to agentic NodePort |
| `kubernetes/applications/apps/agentic-external/cloudflare-tunnel-ingresses.yaml` | Cloudflare tunnel ingress |

### Infisical Secrets
| Path | Keys |
|------|------|
| `/apps/vikunja` | `API_TOKEN` (placeholder - generate after first login) |

### Infrastructure Configuration
| System | Change |
|--------|--------|
| AdGuard | DNS rewrite: `vikunja.kernow.io → 10.10.0.1` |
| Caddy (OPNsense) | Reverse proxy: `vikunja.kernow.io → 10.20.0.40:31095` |

## Key Decisions

1. **SQLite over PostgreSQL**: Simpler deployment, adequate for single-user workload
2. **Plain K8s over Helm**: Avoided Helm chart issues, more control over configuration
3. **NodePort over LoadBalancer**: Consistent with other agentic cluster services
4. **External bridge pattern**: Reused existing pattern for Cloudflare tunnel access

## Post-Deployment Tasks

1. Access Vikunja at https://vikunja.kernow.io
2. Create user account
3. Generate API token in Settings → API Tokens
4. Update Infisical: `/apps/vikunja/API_TOKEN`
5. Restart vikunja-mcp to pick up the token

## Verification Commands

```bash
# Check Vikunja pod
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n vikunja

# Check MCP pod
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n ai-platform -l app=vikunja-mcp

# Test internal access
curl -k https://vikunja.kernow.io

# Test MCP health
curl http://10.20.0.40:31097/health
```

## Recommendations for Future Deployments

1. **Checklist**: Create ArgoCD Application alongside manifests
2. **Prefer Plain K8s**: Unless Helm chart is well-tested and documented
3. **API over SSH**: Use REST APIs for OPNsense, AdGuard, and similar services
4. **Test Locally First**: Verify Docker image works before creating full deployment
5. **Document Early**: Create runbook entries as you discover issues
