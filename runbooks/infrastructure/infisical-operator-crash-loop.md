# Infisical Operator: Leader Election Crash Loop

## Problem
The Infisical Operator pod crashes periodically with exit code 1 due to failed leader election lease renewal.

**Symptoms:**
- Pod restarts frequently (every few hours)
- Error in logs: `failed to renew lease ... context deadline exceeded`
- API server timeouts when updating leader election lease

**Error Pattern:**
```
E0325 02:26:25.627496 leaderelection.go:429] Failed to update lock optimistically: ... Client.Timeout exceeded
E0325 02:26:30.627606 leaderelection.go:436] error retrieving resource lock ... context deadline exceeded
ERROR setup problem running manager {"error": "leader election lost"}
```

## Root Cause
The Kubernetes operator uses leader election to ensure only one replica manages cluster state. The default probe timeout of 1 second is too aggressive—even minor API server latency causes the liveness probe to fail and trigger a restart.

**Contributing Factors:**
- Liveness/readiness probe `timeoutSeconds: 1` is very tight
- Periodic Kubernetes API server latency (common in multi-cluster setups)
- High number of InfisicalSecret resources requiring periodic sync

## Solution
Increase the liveness and readiness probe timeouts from 1 second to 5 seconds. This allows the operator to tolerate transient API latency without crashing.

### Changes Made
```yaml
# Before
livenessProbe:
  timeoutSeconds: 1      # ← Too aggressive
  failureThreshold: 3
  periodSeconds: 20

readinessProbe:
  timeoutSeconds: 1      # ← Too aggressive
  failureThreshold: 3
  periodSeconds: 10

# After
livenessProbe:
  timeoutSeconds: 5      # ← Forgiving of latency
  failureThreshold: 3
  periodSeconds: 20

readinessProbe:
  timeoutSeconds: 5      # ← Forgiving of latency
  failureThreshold: 3
  periodSeconds: 10
```

The failureThreshold of 3 means:
- Liveness: 3 failures × 20s = 60s before restart (graceful)
- Readiness: 3 failures × 10s = 30s before marking unready

This gives the operator plenty of time to recover from transient latency without crashing.

### Where to Apply
Edit the ArgoCD application in `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`:
- Add Helm values section with `manager.livenessProbe.timeoutSeconds: 5`
- Add `manager.readinessProbe.timeoutSeconds: 5`

ArgoCD will auto-sync and redeploy the operator with the new settings.

## Prevention
- Monitor the operator pod for restarts: `kubectl top pod -n infisical-operator-system`
- If restarts spike again, check API server latency and cluster load
- Consider increasing resource requests if the cluster is under high load

## Verification
After ArgoCD syncs:
1. Check the deployment is updated: `kubectl get deployment -n infisical-operator-system infisical-opera-controller-manager -o yaml`
2. Verify probe timeouts are now 5 seconds in the spec
3. Monitor for stable operation: `kubectl get pod -n infisical-operator-system -w`

## See Also
- [Leader Election (Kubernetes docs)](https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/quotas/)
- Infisical Operator version: v0.10.2
- ArgoCD Application: `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`
