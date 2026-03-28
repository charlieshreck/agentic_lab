---
title: cert-manager Troubleshooting & Helm Security Context Overrides
tags: [cert-manager, kubernetes, helm, security]
domain: infrastructure
created: 2026-03-25
---

# cert-manager Troubleshooting & Helm Security Context Overrides

## Symptom: Periodic Pod Crashes After ~52 Minutes

**Cluster**: monit (Talos 1.11.5, K8s 1.34.1)
**Component**: cert-manager v1.20.0
**Behavior**: Pods crash repeatedly ~52 minutes after deployment starts, then restart every ~5 minutes
**Incident**: #615 (2026-03-24)

### Root Cause

Helm chart `cert-manager:v1.20.0` defaults to **`readOnlyRootFilesystem: true`** for all containers:
- `cert-manager` (controller)
- `webhook`
- `cainjector`
- `startupapicheck`

This prevents runtime filesystem writes to:
- Temporary files (`/tmp`)
- Unix socket directories (`/run`)
- Application-specific cache/state locations

When cert-manager attempts to write certificates or create sockets 52 minutes into operation (during initial sync cycle completion), the container crashes with permission denied errors.

### Solution: Override via ArgoCD Helm Values

**DO NOT**:
- Patch the Helm chart directly (lost on upgrades)
- Patch pods/deployments post-deploy (violates GitOps)
- Disable pod security entirely

**DO**: Override via ArgoCD Application manifest `helm.values` section.

#### Implementation

In `kubernetes/argocd-apps/platform/cert-manager-app.yaml`:

```yaml
spec:
  sources:
    - repoURL: https://charts.jetstack.io
      chart: cert-manager
      targetRevision: v1.20.0
      helm:
        releaseName: cert-manager
        parameters:
          - name: crds.enabled
            value: "true"
          - name: crds.keep
            value: "true"
          - name: dns01RecursiveNameservers
            value: "1.1.1.1:53,8.8.8.8:53"
          - name: dns01RecursiveNameserversOnly
            value: "true"
        values: |
          # Override restrictive readOnlyRootFilesystem for all components
          # Root cause: Helm chart v1.20.0 defaults to true, breaking runtime operations

          containerSecurityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
              - ALL
            readOnlyRootFilesystem: false

          webhook:
            containerSecurityContext:
              allowPrivilegeEscalation: false
              capabilities:
                drop:
                - ALL
              readOnlyRootFilesystem: false

          cainjector:
            containerSecurityContext:
              allowPrivilegeEscalation: false
              capabilities:
                drop:
                - ALL
              readOnlyRootFilesystem: false

          startupapicheck:
            containerSecurityContext:
              allowPrivilegeEscalation: false
              capabilities:
                drop:
                - ALL
              readOnlyRootFilesystem: false
```

#### Why This Works

1. **Selective Override**: Relaxes only `readOnlyRootFilesystem` (runtime requirement), keeps other security hardening (nonRoot, capabilities.drop)
2. **GitOps Compliant**: Full history in git, easy revert/adjustment
3. **Upgradeable**: When cert-manager chart releases a fix, update targetRevision and keep the values override only if still needed
4. **Transparent**: Values override is visible in ArgoCD Application manifest, no hidden patch logic

### Verification Steps

After updating the Application manifest and committing to git:

1. **Trigger ArgoCD Sync** (automatic if auto-sync enabled, or manual):
   ```bash
   kubectl patch applications.argoproj.io cert-manager-monit -n argocd \
     --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"normal"}}}'
   ```

2. **Verify Sync Completed**:
   ```bash
   kubectl get applications.argoproj.io cert-manager-monit -n argocd -o jsonpath='{.status}'
   # Should show: "phase":"Succeeded","syncResult":{"revision":"<hash>","resources":[...]}"
   ```

3. **Check Pod Deployments**:
   ```bash
   kubectl get deployment -n cert-manager -o wide
   # All deployments should have Desired=Current=Ready=Available
   # Restart count should be 0 for newly deployed pods
   ```

4. **Verify Security Context Applied**:
   ```bash
   kubectl get deployment -n cert-manager cert-manager -o \
     jsonpath='{.spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem}'
   # Should output: false
   ```

5. **Stability Check** (run every 15-30 seconds for 2-3 minutes):
   ```bash
   kubectl get pods -n cert-manager -o wide --sort-by=.metadata.creationTimestamp
   # All pods should maintain Running status with 0 Restarts
   ```

### Key Learnings

1. **Helm Chart Defaults**: Always review `values.yaml` in Helm charts for security settings that may conflict with runtime requirements
2. **readOnlyRootFilesystem Impact**: This constraint is increasingly common in hardened Helm charts but can break applications that perform legitimate runtime writes
3. **ArgoCD Helm Values**: The cleanest way to override chart defaults while maintaining GitOps principles
4. **Component-Level Overrides**: cert-manager has multiple sub-components (controller, webhook, cainjector, startupapicheck) — ensure all are overridden consistently

### Prevention for Future Charts

When evaluating a new Helm chart:

1. Check `values.yaml` for `securityContext` and `containerSecurityContext` settings
2. Search for `readOnlyRootFilesystem`, `runAsNonRoot`, `allowPrivilegeEscalation`, `capabilities.drop`
3. If using restrictive defaults, plan helm.values overrides in ArgoCD Application manifest from day 1
4. Add override documentation to `CLAUDE.md` or runbooks

### Related Incidents

- **#615**: Original incident (2026-03-24), resolved via Helm values override in commit cfa338a
