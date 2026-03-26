# Cilium ArgoCD Migration & Leader Election Stability

## Problem
When a Cilium cluster is bootstrapped via Terraform but not properly migrated to ArgoCD management, the CNI ends up in an orphaned state. This causes:

- **Repeated pod restarts** — cilium-operator loses leader election approximately every 52-60 minutes
- **No configuration drift correction** — Changes to Cilium Helm values are not enforced or rolled back
- **No declarative management** — Cluster cannot version-control or audit CNI changes
- **Restart accumulation** — Over time, restart counts climb into the hundreds

### Root Cause (Layer 1 — API Server Connectivity)
The cilium-operator connects to the kube-apiserver to maintain its leader election lease
(`kube-system/cilium-operator-resource-lock`). On Talos single-node clusters, the operator
is bootstrapped with `KUBERNETES_SERVICE_HOST=<node-IP>` (e.g. `10.10.0.30:6443`) rather
than `localhost:7445` (the Talos local kube-apiserver proxy). When the kube-apiserver has
brief connection refused periods (during etcd operations, memory pressure, etc.), the operator
fails to renew its lease and exits with `level=fatal msg="Leader election lost"` → restart.

Symptom in logs (previous container):
```
error retrieving resource lock kube-system/cilium-operator-resource-lock:
  dial tcp 10.10.0.30:6443: connect: connection refused
...
level=fatal msg="Leader election lost"
```

### Root Cause (Layer 2 — ArgoCD Naming Conflict Blocks Fix)
The `cilium-app.yaml` ArgoCD Application manifest may exist in git but never take effect
because of an **application name collision**. ArgoCD application names are globally unique
across all projects in an instance. If a `cilium` Application already exists (e.g. targeting
the agentic cluster), a second `cilium` application for the monit cluster will fail to create,
causing the parent `monitoring-platform` app-of-apps to show `sync_status: Unknown`.

**Diagnosis**: Check if `monitoring-platform` is Unknown AND the expected cluster's Cilium
Application is absent from `argocd app list`:
```bash
# No cilium app targeting the monit cluster?
argocd app list | grep cilium
# → only shows cilium targeting 10.20.0.40 (agentic), not 10.10.0.30 (monit)

# monitoring-platform is Unknown?
argocd app get monitoring-platform
```

## Solution: ArgoCD Migration

### Steps

1. **Create (or fix) ArgoCD Application Manifest**
   - File: `kubernetes/argocd-apps/platform/cilium-app.yaml`
   - **Critical naming rule**: Use a cluster-specific name, e.g. `cilium-monit`, NOT `cilium`
     (avoids collision with the agentic cluster's `cilium` Application)
   - Use project `monitoring` (not `default`) for monit cluster apps
   - Adapt for target cluster infrastructure:
     - **Network device**: Match the physical interface for L2 announcements
       - Agentic cluster: `eno1`
       - Monit cluster: `ens18` (vmbr0 bridge interface)
     - **Destination**: Use cluster's Kubernetes API endpoint
       - Agentic: `https://10.20.0.40:6443`
       - Monit: `https://10.10.0.30:6443`
     - **k8sServiceHost/Port**: `localhost` / `7445` — use Talos local proxy, NOT node IP
       (this is the critical setting that prevents operator leader election failures)
     - **targetRevision**: Pin to currently running version first; upgrade separately
   - Keep Talos-specific settings (cgroup, security context, capabilities)
   - Keep L2 announcement timings (leaseDuration: 3s, leaseRenewDeadline: 1s, leaseRetryPeriod: 200ms)

   Example minimal correct values section:
   ```yaml
   k8sServiceHost: localhost
   k8sServicePort: 7445
   ```

2. **Commit via GitOps Workflow**
   ```bash
   /home/scripts/git-commit-submodule.sh monit_homelab "fix: rename cilium ArgoCD app to cilium-monit"
   ```

3. **Verify ArgoCD Sync**
   - `monitoring-platform` app-of-apps should transition from Unknown → Synced
   - A new `cilium-monit` Application should appear in ArgoCD app list
   - `cilium-monit` should sync → Healthy within a few minutes

4. **Monitor Cilium Operator**
   - Pod will restart once as deployment is updated (KUBERNETES_SERVICE_HOST changes to localhost)
   - Verify: `kubectl -n kube-system get pod -l app.kubernetes.io/name=cilium-operator`
   - Restart count should stabilize — no further chronic restarts
   - Check logs: `kubectl -n kube-system logs -l app.kubernetes.io/name=cilium-operator --tail=50`

### Incident Resolution

**Incident #617 (HomelabPodHighRestartCount — finding #1389)**
- **Root cause**: `cilium-app.yaml` used `name: cilium` conflicting with the agentic cluster's
  ArgoCD Application of the same name. This prevented `monitoring-platform` from syncing
  (status: Unknown), leaving monit cluster Cilium orphaned at bootstrap config (v1.18.4 with
  `KUBERNETES_SERVICE_HOST=10.10.0.30`). The operator periodically lost leader election when
  kube-apiserver at 10.10.0.30:6443 briefly refused connections → 106 restarts over 35 days.
- **Resolution (2026-03-26)**: Renamed to `cilium-monit`, moved to `monitoring` project, pinned
  at v1.18.4. ArgoCD will sync `k8sServiceHost=localhost` to the operator deployment.
- **Expected outcome**: Leader election stability, restart counter resets on next pod cycle
- **Verification**: Monitor restart count for 1-2 hours after ArgoCD sync; should remain ≤ 1-2

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
