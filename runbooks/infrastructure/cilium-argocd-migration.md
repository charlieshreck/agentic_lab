# Cilium ArgoCD Migration & Leader Election Stability

## Problem
When a Cilium cluster is bootstrapped via Terraform but not properly migrated to ArgoCD management, the CNI ends up in an orphaned state. This causes:

- **Repeated pod restarts** — cilium-operator loses leader election approximately every 52-60 minutes
- **No configuration drift correction** — Changes to Cilium Helm values are not enforced or rolled back
- **No declarative management** — Cluster cannot version-control or audit CNI changes
- **Restart accumulation** — Over time, restart counts climb into the hundreds

### Root Cause
The Terraform bootstrap file (`infrastructure/terraform/talos-single-node/cilium.tf`) was dormant but never replaced with an ArgoCD Application manifest. Without ArgoCD management:
- The cilium-operator pod runs with only the bootstrap-time Helm release config
- No active reconciliation of the Helm chart version or values
- Leader election timings are not guaranteed to remain stable across pod lifecycle events

## Solution: ArgoCD Migration

### Steps

1. **Create ArgoCD Application Manifest**
   - File: `kubernetes/argocd-apps/platform/cilium-app.yaml`
   - Based on template from agentic cluster (`agentic_lab/kubernetes/argocd-apps/cilium-app.yaml`)
   - Adapt for target cluster infrastructure:
     - **Network device**: Match the physical interface used for L2 announcements
       - Agentic cluster: `eno1` (high-speed nic)
       - Monit cluster: `ens18` (vmbr0 bridge interface)
     - **API server**: Use cluster's Kubernetes API endpoint
       - Agentic: `https://10.20.0.40:6443`
       - Monit: `https://10.10.0.30:6443`
     - **Helm chart version**: Choose consistently with other clusters (recommend same as prod for stability)
   - Keep all Talos-specific settings identical (cgroup, security context, capabilities)
   - Preserve L2 announcement timings (leaseDuration: 3s, leaseRenewDeadline: 1s, leaseRetryPeriod: 200ms)

2. **Commit via GitOps Workflow**
   ```bash
   /commit-submodule <cluster> "Add Cilium ArgoCD Application for <cluster> cluster"
   ```

3. **Verify ArgoCD Sync**
   - Prod cluster's ArgoCD watches git repo and detects new Application
   - ArgoCD automatically syncs the manifest to the target cluster's kube-system namespace
   - Monitor: `kubectl get application cilium -n argocd` on prod cluster (should show `Synced` status)

4. **Monitor Cilium Operator**
   - Pod will likely restart once during upgrade transition
   - Verify using: `kubectl get pod -n kube-system -l app.kubernetes.io/name=cilium-operator`
   - Restart count should stabilize at a low number (0-1 after migration completes)
   - Check logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=cilium-operator --tail=50`

### Incident Resolution

**Incident #617 (HomelabPodHighRestartCount)**
- **Root cause**: Cilium operator orphaned on monit cluster (Terraform bootstrap, no ArgoCD management)
- **Resolution**: Created `cilium-app.yaml` for ArgoCD-based Helm deployment
- **Expected outcome**: Leader election stability, restart count resets, no further chronic restarts
- **Verification**: Monitor restart count for 1-2 hours after sync; should remain ≤ 1-2

## Prevention

1. **Always migrate Terraform bootstrap to ArgoCD** — No manual Helm releases in production clusters
2. **Apply the monitoring-platform app-of-apps pattern** — All platform services must be in argocd-apps/ with proper Application resources
3. **Verify in bootstrap** — After Terraform provisions a cluster, immediately create corresponding ArgoCD manifests before promoting to production
4. **Use diff tools** — `argocd app diff <app-name>` to verify no drift between git and cluster state

## Related Resources
- Cilium Helm values: https://helm.cilium.io/
- ArgoCD Application CRD: Kubernetes v1alpha1
- L2 announcements: Cilium 1.13+ feature, leader election critical for single-node clusters with multiple interfaces
- Talos + Cilium: Requires cgroup autoMount: false, privileged securityContext, specific NET_ADMIN capabilities
