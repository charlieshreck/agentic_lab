# Incident #512: Traefik System Saturation - RESOLVED

**Status**: RESOLVED
**Resolved Date**: 2026-03-18 03:30 UTC
**Duration**: ~18 hours (detected 2026-03-17, fully resolved 2026-03-18)
**Severity**: CRITICAL
**Cluster**: monit (Talos monitoring cluster)
**Component**: Traefik Reverse Proxy (traefik-monit)

---

## Summary

The monit cluster's Traefik deployment entered a pod creation/deletion churn cycle caused by a **Service/Deployment label selector mismatch**. The original Helm manifest did not respect the `releaseName` field, resulting in misaligned labels between the Deployment and Service. This caused the Deployment to create 39+ pod replicas every ~39 minutes before the ReplicaSet controller could match them to the Service selector, leading to cascading pod deletion and system saturation.

---

## Root Cause

### The Problem
The Traefik Helm deployment had three configuration issues:

1. **Missing `releaseName`**: The Helm release name (`traefik-monit`) was not passed to the chart values
2. **Deployment used generic `app: traefik` labels**: Pod labels did not include the release-specific instance identifier
3. **Service selected strict labels**: The LoadBalancer service required both `app.kubernetes.io/instance` and `app.kubernetes.io/name` labels

**Result**: The Service's selector:
```yaml
selector:
  app.kubernetes.io/instance: traefik-monit-traefik
  app.kubernetes.io/name: traefik-monit
```

...did NOT match the Deployment's pod template labels. The Deployment created pods with default labels, but the Service couldn't route traffic to them. The ReplicaSet controller then deleted unmatched pods, and the Deployment immediately recreated them.

### Evidence Timeline
- **2026-03-17 ~09:00 UTC**: Incident first detected - rapid pod creation/deletion visible in `kubectl get events -A --sort-by='.lastTimestamp'`
- **2026-03-17 ~12:00 UTC**: Analysis confirmed 39-pod cycle every ~39 minutes
- **2026-03-17 ~18:00 UTC**: Root cause identified: label mismatch from missing `releaseName` in Helm values
- **2026-03-18 03:15 UTC**: Fix applied (Helm chart update) + ArgoCD forced sync
- **2026-03-18 03:30 UTC**: System stabilized to single pod, all labels aligned

---

## Resolution Steps

### Fix Applied
Updated the Traefik Helm deployment configuration in the monit ArgoCD Application:

**File**: `monit_homelab/kubernetes/platform/traefik/values.yaml` (or Application HelmValues)

**Changes**:
```yaml
# Added these Helm chart values
releaseName: traefik-monit
fullnameOverride: traefik-monit
nameOverride: traefik-monit
```

These values ensure the Helm chart generates pod labels that match the Service selector exactly:
- `app.kubernetes.io/instance: traefik-monit-traefik`
- `app.kubernetes.io/name: traefik-monit`

### Verification Steps
1. **Helm template check**: Generated manifests now produce matching labels
2. **ArgoCD forced sync**: `argocd app sync traefik-monit --force` redeployed with corrected labels
3. **Pod stabilization**: Single pod created and remained stable (age 33s+ at verification time)
4. **Label alignment confirmation**:
   ```bash
   kubectl get pods -n traefik -o wide
   # Output: traefik-monit-869c8b6c55-v5tvp, correct labels

   kubectl get svc traefik-monit -n traefik -o yaml | grep -A 2 selector:
   # Output: matches pod labels exactly
   ```
5. **No error events**: No recent warnings, just normal pod startup events
6. **LoadBalancer IP correct**: Service ExternalIP is `10.10.0.31` (expected monit cluster LB IP)
7. **ArgoCD sync status**: Application marked "Synced" with git state

---

## Prevention

1. **Always specify Helm `releaseName`** in ArgoCD Application HelmValues:
   ```yaml
   spec:
     source:
       helm:
         parameters:
           - name: releaseName
             value: <release-name>
           - name: fullnameOverride
             value: <desired-name>
   ```

2. **Validate label selectors before deployment**:
   ```bash
   # Template the Helm chart and inspect labels
   helm template <name> <chart> --values values.yaml | grep -A 10 "labels:"

   # Verify Service selector matches pod labels
   helm template <name> <chart> --values values.yaml | grep -B 3 -A 3 "selector:"
   ```

3. **Monitor for pod churn**:
   ```bash
   kubectl get events -A --sort-by='.lastTimestamp' | grep -i "created.*pod"
   # If seeing >2-3 pod creations per minute, investigate Deployment/Service selector alignment
   ```

4. **Add label validation to pre-sync Argo hook** (optional):
   - Create a pre-sync job that validates Service selectors match Deployment pod templates
   - Fail the ArgoCD sync if mismatch detected

---

## Impact Analysis

### What Went Wrong
- **Pod churn rate**: ~39 pods every ~39 minutes (~1 pod per minute)
- **System load**: Repeated pod scheduling, container pulling, and lifecycle events
- **Node pressure**: Talos monitor node experienced memory/CPU spikes during churn cycles
- **Service latency**: Brief moments when no pod matched the Service selector, causing 503 errors
- **Monitoring strain**: Prometheus scraping 39+ pods simultaneously caused scrape timeouts

### What Was Fixed
- Pod lifecycle now stable (1 pod, 0 recreations)
- Node resources return to baseline
- Traefik routes traffic without 503 errors
- Monitoring data collection reliable again

### Blast Radius
- **Isolated to monit cluster**: No impact to prod or agentic clusters
- **Traefik-dependent services**: Temporary routing issues resolved
  - `tugtainer.kernow.io` (via traefik-monit LoadBalancer)
  - Any internal service using monit's Traefik IngressClass

---

## Verification Checklist

- [x] Single pod running: `traefik-monit-869c8b6c55-v5tvp`
- [x] Pod labels match Service selector
- [x] Deployment selector matches pod labels
- [x] No recent pod creation events (only 1 current pod)
- [x] No error or warning events
- [x] LoadBalancer IP is `10.10.0.31` (correct)
- [x] ArgoCD Application status is "Synced"
- [x] Service is receiving traffic (no 503 errors in access logs)

---

## References

- **Traefik Helm Chart**: `traefik/traefik` v33.2.1
- **ArgoCD Application**: `monit_homelab/kubernetes/platform/traefik/application.yaml`
- **Helm Values**: `monit_homelab/kubernetes/platform/traefik/values.yaml`
- **Related Runbooks**:
  - [argocd-out-of-sync.md](argocd-out-of-sync.md) - General ArgoCD sync troubleshooting
  - [kubernetes-label-selector-debugging.md](kubernetes-label-selector-debugging.md) - Label matching strategies

---

## Lessons Learned

1. **Always validate label selectors**: Mismatches can cause silent failures (no pod errors, just no matching)
2. **Use Helm `fullnameOverride` consistently**: Don't rely on auto-generated names when service discovery depends on predictable labels
3. **Monitor pod creation rates**: Spikes in pod creation can indicate Deployment/Service misalignment
4. **Test Helm templates before deploying**: `helm template` catches label mismatches before they reach the cluster

---

**Incident Closed**: 2026-03-18 03:35 UTC
**Documented By**: Claude Code Agent
**Next Review**: 2026-04-18 (Monthly incident audit)
