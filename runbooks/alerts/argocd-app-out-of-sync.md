# ArgoCDAppOutOfSync

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | ArgoCDAppOutOfSync |
| **Severity** | Warning |
| **Threshold** | App not Synced for 15 minutes |
| **Source** | ArgoCD metrics / error-hunter / alerting-pipeline |
| **Clusters Affected** | All (prod ArgoCD manages prod, agentic, monit) |

## Description

This alert fires when an ArgoCD application has been in a non-Synced state (typically OutOfSync) for more than 15 minutes. OutOfSync means the live cluster state differs from the desired state defined in Git.

ArgoCD runs on the **prod cluster only** and manages all three clusters (prod, agentic, monit). All applications are defined in Git repositories and synced via ArgoCD.

## Quick Diagnosis

### 1. Check current sync status

```
# Via MCP tool (preferred)
mcp__infrastructure__argocd_get_applications()

# Look for apps with sync_status != "Synced"
```

### 2. Check specific app details

```bash
# Via ArgoCD CLI (if available)
argocd app get <app-name> --server argocd.kernow.io

# Via kubectl on prod cluster
kubectl get application <app-name> -n argocd -o yaml
```

### 3. Check ArgoCD UI

Navigate to `https://argocd.kernow.io` and inspect the application for sync errors.

## Common Causes

### 1. Manual Changes on Cluster (Drift)

**Symptoms:**
- App shows OutOfSync but no recent Git commits
- Diff shows fields that were manually changed

**Verification:**
```
# Check app diff in ArgoCD UI or CLI
argocd app diff <app-name>
```

**Resolution:**
- Sync the app to restore Git state: `argocd app sync <app-name>`
- Or revert the manual change and commit to Git
- Avoid manual `kubectl apply/patch/edit` — use GitOps

### 2. Git Repository Changes Not Auto-Synced

**Symptoms:**
- Recent commits in the Git repo
- App configured with manual sync policy

**Verification:**
```
# Check sync policy
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.syncPolicy}'
```

**Resolution:**
- Manually trigger sync: `argocd app sync <app-name>`
- Or enable auto-sync in the Application spec:
```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 3. App-of-Apps Drift

**Symptoms:**
- `app-of-apps` or `agentic-applications` or `monitoring-platform` is OutOfSync
- Child Application resources don't match what's in Git

**Verification:**
```
# Check the parent app-of-apps
mcp__infrastructure__argocd_get_applications()
# Look for app-of-apps, agentic-applications, monitoring-platform
```

**Resolution:**
- Sync the parent app: `argocd app sync app-of-apps`
- Check if new Application manifests were added to `kubernetes/argocd-apps/`
- Verify the bootstrap app-of-apps manifest exists:
  - Prod: `prod_homelab/kubernetes/bootstrap/app-of-apps.yaml`
  - Agentic: via `agentic-applications` app
  - Monit: via `monitoring-platform` app

### 4. Helm Values Changed

**Symptoms:**
- Helm-based apps show OutOfSync
- Values in Git differ from what's deployed

**Verification:**
```bash
# Check helm release values
kubectl get application <app-name> -n argocd -o yaml | grep -A 20 helm
```

**Resolution:**
- Sync the app to apply new Helm values
- Check for Helm chart version bumps via Renovate

### 5. Persistent Sync Loop (Default-Value Fields)

**Symptoms:**
- App is OutOfSync but sync operation shows "successfully synced"
- `status.operationState.operation.sync.autoHealAttemptsCount` is high (> 3)
- The same 1-2 resources keep getting re-synced every cycle
- `app-of-apps` or another parent app keeps cycling on specific child Application resources

**Root cause:**
YAML fields that are Kubernetes defaults get **stripped** when stored in etcd. If these fields exist in Git, ArgoCD will always detect a diff because live state never has them.

Common culprits in ArgoCD Application specs:
- `spec.source.directory.recurse: false` — default, stripped on store
- `spec.source.directory.jsonnet: {}` — empty default
- Any field with zero-value (`false`, `""`, `0`, `{}`) that isn't stored

**Verification:**
```bash
# Check the specific resource that keeps cycling
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.source}' | python3 -m json.tool

# Compare against git manifest — look for fields missing from live spec
diff <(cat kubernetes/argocd-apps/.../app.yaml | yq .spec.source) \
     <(kubectl get application <app-name> -n argocd -o jsonpath='{.spec.source}' | python3 -m json.tool)
```

**Resolution:**
Remove the default-value field from the Git manifest so it matches what Kubernetes stores.

Example: `prod_homelab/kubernetes/argocd-apps/platform/homepage-rbac-agentic.yaml` (2026-02-24)
```yaml
# BEFORE (caused persistent loop)
source:
  repoURL: ...
  targetRevision: main
  path: kubernetes/platform/homepage-rbac
  directory:
    recurse: false   # <-- default, gets stripped

# AFTER (fixed)
source:
  repoURL: ...
  targetRevision: main
  path: kubernetes/platform/homepage-rbac
```

Commit the fix and wait for the next ArgoCD reconcile (~3 min).

**Prevention:**
- In `app-of-apps` ignoreDifferences, only ignoring `/metadata/*` and `/status` is NOT enough — spec diffs also trigger OutOfSync
- Either: add problematic jsonPointers to app-of-apps ignoreDifferences, OR remove default fields from git manifests (preferred)

### 6. Target Cluster Unreachable

**Symptoms:**
- Multiple apps targeting the same cluster are OutOfSync
- Sync attempts fail with connection errors

**Verification:**
```
# Check cluster connectivity from prod ArgoCD
# Agentic: 10.20.0.40:6443
# Monit: 10.10.0.30:6443
```

**Resolution:**
- Verify target cluster is running (check Proxmox VM status)
- Check network connectivity between clusters
- Verify ArgoCD cluster secrets haven't expired

## Resolution Steps

### Step 1: Identify the out-of-sync app

```
mcp__infrastructure__argocd_get_applications()
```

### Step 2: Check the app diff

Review what's different between Git and the live cluster state.

### Step 3: Sync the app

```
mcp__infrastructure__argocd_sync_application(name="<app-name>")
```

### Step 4: Verify sync succeeded

```
mcp__infrastructure__argocd_get_applications()
# Confirm app shows sync_status: "Synced", health: "Healthy"
```

### Step 5: Investigate root cause

If the app keeps going OutOfSync, identify what's causing drift:
- Manual kubectl changes
- External controllers modifying resources
- Missing pruning policy

## Prevention

1. **Never use manual kubectl apply/patch** — all changes via Git commits
2. **Enable auto-sync with self-heal** on all applications
3. **Use pruning** to remove resources deleted from Git
4. **Monitor app-of-apps** — if the parent drifts, child apps may not update
5. **Keep bootstrap manifests in Git** — `app-of-apps.yaml` must exist

## Related Alerts

- `ArgoCDAppUnhealthy` — App health is Degraded/Missing/Unknown
- `KubeDeploymentRolloutStuck` — Deployment not progressing (may cause Unhealthy)

## Incident History

### Incident #224 — Second occurrence (2026-02-24 ~20:22 UTC)

**Alert**: ArgoCDOutOfSync on cloudflare-tunnel-controller (health: Missing)
**Status**: RESOLVED
**Root Cause**: `secret-transformer` Job had `ttlSecondsAfterFinished: 300`. K8s TTL controller deletes completed jobs after 5 minutes. ArgoCD tracked the Job as a managed resource, saw it missing, set health=Missing, and re-synced to recreate it — infinite loop.

**Fix**: Converted Job to ArgoCD PostSync hook:
```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
```
Removed `ttlSecondsAfterFinished: 300`. ArgoCD now runs the Job after each sync as a hook (not a tracked resource), so its deletion does not affect app health.

**Commit**: `8bbe3df` in `prod_homelab`

**Pattern**: Any Job with `ttlSecondsAfterFinished` that ArgoCD manages will create a sync loop. Fix = PostSync hook. See "Cause 7" below.

---

### Common Cause 7: Job with TTL Causing Sync Loop

**Symptoms:**
- App health shows `Missing` despite pods being `Running`
- Sync reports "successfully synced (all tasks run)" but SyncError condition persists
- No jobs exist in the namespace (`kubectl_get_jobs` returns empty)
- Sync loop triggers every 5–10 minutes

**Root Cause:**
A Job in the app has `ttlSecondsAfterFinished` set. When the Job completes, K8s deletes it after the TTL. ArgoCD then sees its managed resource is gone → sets health=Missing → re-syncs → Job runs again → completes → gets deleted → repeat.

**Verification:**
```bash
# Check if any jobs exist (empty = already auto-deleted)
kubectl get jobs -n <namespace> --context=admin@homelab-prod

# Look for ttlSecondsAfterFinished in manifests
grep -r "ttlSecondsAfterFinished" prod_homelab/kubernetes/platform/<app>/
```

**Resolution:**
Convert the Job to an ArgoCD PostSync hook. The hook runs after each sync but is NOT tracked as a managed resource:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: <job-name>
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  # Remove ttlSecondsAfterFinished entirely
  template: ...
```

**Alternative**: Remove `ttlSecondsAfterFinished` and let the Job persist in Completed state (ArgoCD treats Succeeded jobs as Healthy).

---

### Incident #224 — First occurrence (2026-02-24)

**Alert**: ArgoCDAppOutOfSync on app-of-apps
**Status**: RESOLVED (self-healed after fixes applied)
**Root Cause**: Persistent sync loop from `directory.recurse: false` in homepage-rbac-agentic.yaml

**Timeline**:
- **09:47 AM**: Fixed cloudflare-tunnel-controller ignoreDifferences (commit f3cf47d)
- **10:48 AM**: Added ArgoCD finalizer to app-of-apps (commit 84d8f0c)
- **13:12 PM**: Removed `directory.recurse: false` from homepage-rbac-agentic (commit 485d1ff)
- **13:14 PM**: App-of-apps transitioned to Synced; all 127 child apps healthy

**Learning**: Default-value fields in ArgoCD Application specs need either:
1. Removal from Git (preferred) — let Kubernetes defaults apply
2. Explicit addition to app-of-apps ignoreDifferences if they must be present

Never include `recurse: false` or empty `jsonnet: {}` unless absolutely necessary.

## Detection Methods

| Method | Status |
|--------|--------|
| PrometheusRule (argocd_app_info metric) | Active — scrapes via API server proxy from monit Prometheus |
| error-hunter sweep | Active — polls ArgoCD API periodically |
| alerting-pipeline | Active — polls infrastructure MCP tools |

ArgoCD metrics are scraped from the prod cluster via the Kubernetes API server proxy pattern. The `argocd-metrics` service (port 8082) exposes `argocd_app_info` which powers both the `ArgoCDAppOutOfSync` and `ArgoCDAppUnhealthy` PrometheusRules. Scrape config is in the kube-prometheus-stack Helm values (`monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`).
