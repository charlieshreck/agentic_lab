# Infisical Operator: Leader Election Crash Loop

## Problem
The Infisical Operator pod crashes periodically with exit code 1 due to failed leader election lease renewal.

**Symptoms:**
- Pod restarts frequently (dozens of times over weeks)
- Error in logs: `failed to renew lease ... context deadline exceeded`
- API server timeouts when updating leader election lease
- Crash occurs after bulk reconciliation of many InfisicalSecrets

**Error Pattern:**
```
E leaderelection.go:429] Failed to update lock optimistically: ... Client.Timeout exceeded while awaiting headers
E leaderelection.go:436] error retrieving resource lock ... context deadline exceeded
I leaderelection.go:297] failed to renew lease ... context deadline exceeded
ERROR setup problem running manager {"error": "leader election lost"}
```

## Root Cause
**Leader election is enabled on a single-replica deployment.** When there is a transient K8s API server connectivity blip (even 5 seconds), the lease renewal times out and the operator treats this as "leader election lost" and exits with code 1.

With a single replica, leader election provides no benefit (it exists to coordinate multi-replica deployments where only one instance should act as leader). Enabling it on a single replica means any API blip causes a crash-restart cycle.

**Contributing factor**: 46+ InfisicalSecrets each reconciled every 1 minute generates significant API traffic. During peak reconciliation, any momentary latency spike triggers the 5s lease renewal timeout.

## Definitive Fix (applied 2026-03-29, finding #1439)

Updated `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`:

1. **Disabled leader election** (`--leader-elect=false`) — eliminates crash-loop on any API blip
2. **Upgraded chart 0.10.2 → 0.10.28** (latest, was 26 patch versions behind)
3. **Fixed Helm values key** — previous values used wrong path `manager.*`; chart requires `controllerManager.manager.*`, causing all overrides to be silently ignored

```yaml
controllerManager:
  manager:
    # Disable leader election: single replica only, avoids crash-loop on transient API blips
    args:
      - --metrics-bind-address=:8443
      - --leader-elect=false
      - --health-probe-bind-address=:8081
    resources:
      requests:
        cpu: 10m
        memory: 64Mi
      limits:
        cpu: 500m
        memory: 128Mi
```

## History of Attempts

### Attempt 1 (2026-03-25): Probe timeout increase — did not fix it
Added probe timeout overrides in Helm values under `manager.livenessProbe` — but the chart uses `controllerManager.manager.*` so these were silently ignored. Probe timeouts remained at `timeoutSeconds: 1` (chart default).

### Attempt 2 (2026-03-29 AM): Resource limit increase — did not fix it
Added `manager.resources` with 256Mi memory limit — but again wrong key path, chart defaults of 128Mi were used. Did not reduce GC pressure.

### Attempt 3 (2026-03-29): **Definitive fix**
Corrected the key path, upgraded to latest chart, disabled leader election.

## Why Previous Fixes Failed
The Helm chart `secrets-operator` uses `controllerManager.manager.*` not `manager.*` for all manager container configuration. Any values placed under `manager.*` were silently ignored by Helm as unknown fields.

Verify the chart's correct values structure:
```bash
curl -sL "https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/secrets-operator-0.10.28.tgz" | \
  tar xzO secrets-operator/values.yaml
```

## Verification

After ArgoCD syncs (usually within 3 minutes of push):
```bash
# Check operator args — should show --leader-elect=false
kubectl get deployment -n infisical-operator-system infisical-opera-controller-manager \
  -o jsonpath='{.spec.template.spec.containers[0].args}' --kubeconfig /root/.kube/config

# Verify restart count stops incrementing
kubectl get pod -n infisical-operator-system -w --kubeconfig /root/.kube/config

# Check image version is v0.10.28
kubectl get pod -n infisical-operator-system -o jsonpath='{.items[0].spec.containers[0].image}' \
  --kubeconfig /root/.kube/config
```

## Future Upgrades
Check for new versions at: https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/index.yaml

The Helm chart version matches the operator image version (e.g., chart `0.10.28` = image `v0.10.28`).

## See Also
- Infisical Operator version: v0.10.28 (upgraded from v0.10.2)
- ArgoCD Application: `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`
- Finding #1439 (2026-03-29): 51 restarts — root cause: leader election + wrong Helm values key path
