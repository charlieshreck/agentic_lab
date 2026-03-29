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
Two contributing factors combine to cause this crash loop:

### Factor 1: Probe timeout too tight (initial fix)
The liveness/readiness probe `timeoutSeconds: 1` was too aggressive. Even minor API server latency causes the probe to fail.

### Factor 2: Memory limit too low (recurrence cause)
With **46+ InfisicalSecrets** each reconciled every 1 minute, the 128Mi memory limit causes Go GC (garbage collection) pressure. GC pauses interrupt the leader election lease renewal goroutine, causing the 5s API request timeout to be exceeded. The crash pattern: bulk reconciliation completes → GC runs → lease renewal goroutine stalls → timeout → leader election lost.

This is the dominant factor — the probe fix alone did not prevent recurrence.

## Solution

### Step 1: Increase probe timeouts (applied 2026-03-25)
```yaml
livenessProbe:
  timeoutSeconds: 5      # was: 1
  failureThreshold: 3
  periodSeconds: 20
readinessProbe:
  timeoutSeconds: 5      # was: 1
  failureThreshold: 3
  periodSeconds: 10
```

### Step 2: Increase resource limits (applied 2026-03-29)
```yaml
resources:
  requests:
    cpu: 10m
    memory: 128Mi    # was: 64Mi
  limits:
    cpu: 1000m       # was: 500m
    memory: 256Mi    # was: 128Mi
```

The memory increase from 128Mi → 256Mi reduces Go GC frequency, allowing the leader election renewal goroutine to complete within the 5s timeout even during peak reconciliation.

### Where to Apply
Edit the ArgoCD application in `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`
under the `manager.resources` Helm values section.

ArgoCD will auto-sync and redeploy the operator with the new settings.

## Scaling Rule
As more InfisicalSecrets are added to the cluster, memory pressure will grow. Rough guidance:
- < 20 InfisicalSecrets: 128Mi is sufficient
- 20-50 InfisicalSecrets: 256Mi
- 50+ InfisicalSecrets: 512Mi or consider increasing `resyncInterval` to 5m

## Prevention
- Monitor restart count: `kubectl get pod -n infisical-operator-system`
- If restarts resume, check current InfisicalSecret count: `kubectl get infisicalsecrets -A | wc -l`
- Scale memory limits proactively as secrets grow

## Verification
After ArgoCD syncs:
1. Check deployment updated: `kubectl get deployment -n infisical-operator-system infisical-opera-controller-manager -o yaml | grep -A4 resources`
2. Verify memory limit is 256Mi
3. Monitor stability: `kubectl get pod -n infisical-operator-system -w`
4. Restart count should stop incrementing after a few hours

## See Also
- Infisical Operator version: v0.10.2
- ArgoCD Application: `prod_homelab/kubernetes/argocd-apps/platform/infisical-operator-app.yaml`
- Finding #1428 (2026-03-29): 51 restarts, root cause confirmed as GC pressure with 46 secrets
