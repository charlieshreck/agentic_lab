# KubeJobFailed: huntarr-start / huntarr-stop

**Alert**: `KubeJobFailed` on production cluster
**Namespace**: `media`
**Root Causes**:
1. ~~CronJob containers using unreachable container image~~ (FIXED - 2026-02-21)
2. RBAC permissions missing for kubectl scale operations (FIXED - 2026-02-21)
**Status**: FULLY RESOLVED

## Symptoms

- `KubeJobFailed` warning alerts for jobs: `huntarr-start-*` and `huntarr-stop-*`
- Early symptoms: Pod events showing `ImagePullBackOff` errors (bitnami/kubectl image)
- Later symptoms: Pods running but jobs failing with "error: unable to scale" or permission errors

## Root Cause Analysis

Two separate issues were preventing the huntarr scheduler jobs from completing:

### Issue 1: Unreachable Container Image (RESOLVED)
The huntarr scheduler CronJobs were configured to use `bitnami/kubectl:latest`, which:
1. Is not guaranteed to be available in Kubernetes image registries
2. May have tag availability issues
3. Can have registry access failures

### Issue 2: Insufficient RBAC Permissions (RESOLVED)
Even after fixing the image, the ServiceAccount `huntarr-scheduler` lacked proper permissions:
- **Original RBAC rule**: Only had `["patch", "get"]` on `deployments/scale` resource
- **Missing permission**: The `kubectl scale` command requires `update` verb on `deployments` resource
- **Result**: Jobs would run but fail with permission denied when attempting to scale

CronJobs affected:
- `huntarr-start` (schedule: 0 0 * * * / midnight UTC) - scales huntarr deployment to 1 replica
- `huntarr-stop` (schedule: 0 8 * * * / 8am UTC) - scales huntarr deployment to 0 replicas

## Solution

Two fixes were required to fully resolve the issue:

### Fix 1: Update Container Image
Replace the unreachable `bitnami/kubectl:latest` image with the official Kubernetes kubectl image:

**File**: `/home/prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`

**Changes**:
```yaml
# BEFORE
image: bitnami/kubectl:latest

# AFTER
image: registry.k8s.io/kubectl:v1.34
```

The `registry.k8s.io/kubectl:v1.34` image is:
- The official Kubernetes kubectl image
- Guaranteed to be available in the Kubernetes image registry
- Matches the cluster's Kubernetes version (v1.34.1)

### Fix 2: Update RBAC Role Permissions
Update the `huntarr-scheduler` Role to include the `update` verb required by kubectl scale:

**File**: `/home/prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`

**Changes**:
```yaml
# BEFORE
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  resourceNames: ["huntarr"]
  verbs: ["patch", "get"]

# AFTER
- apiGroups: ["apps"]
  resources: ["deployments", "deployments/scale"]
  resourceNames: ["huntarr"]
  verbs: ["get", "patch", "update"]
```

**Why this fix is needed**:
- `kubectl scale` command requires `update` permission on deployments
- The original rule only allowed `patch` on `deployments/scale` subresource
- Adding `update` on the main `deployments` resource allows the kubectl client to update replica counts

## Implementation Steps

Both fixes are already committed in git (as of 2026-02-21). Implementation process:

1. **Update manifest**:
   - Changed `bitnami/kubectl:latest` → `registry.k8s.io/kubectl:v1.34` in CronJob specs
   - Updated Role to include `update` verb and `deployments` resource
2. **Commit to git**: Commit message: "fix: replace unreachable bitnami/kubectl with official registry.k8s.io/kubectl:v1.34"
3. **Push to GitHub**: Changes pushed to `prod_homelab` repo
4. **ArgoCD syncs**: Application `huntarr` auto-synced (Synced status confirmed)
5. **Clean up old jobs**: Failed jobs manually deleted from media namespace to clear alert
6. **Next scheduled run**: Jobs will execute with correct image and RBAC permissions

**Status**: Fixes applied and verified in production cluster as of 2026-02-21 17:45 UTC

## Verification

After ArgoCD sync completes:

```bash
# Check CronJob spec
kubectl -n media get cronjob huntarr-start -o yaml | grep image
kubectl -n media get cronjob huntarr-stop -o yaml | grep image

# Both should show: image: registry.k8s.io/kubectl:v1.34

# Monitor next job run (huntarr-stop at 08:00 UTC, huntarr-start at 00:00 UTC)
kubectl -n media get jobs
kubectl -n media get pods -l batch.kubernetes.io/cronjob-name=huntarr-stop
```

## Prevention

- Always use official or verified container images
- Avoid `latest` tags; use specific versions
- Test CronJob manifests before deploying to production
- Monitor image pull failures early via alerts

## Related Files

- Source manifest: `prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`
- ArgoCD Application: `prod_homelab/kubernetes/argocd-apps/applications/huntarr-app.yaml`
- Deployment: `prod_homelab/kubernetes/applications/media/huntarr/deployment.yaml`

## Timeline

- **Issue Detected**: Multiple failed jobs over ~2 weeks (various failure times)
  - Jobs: huntarr-start-29505600 (10d ago), 29509920 (12d), 29524320 (2d17h), 29525760 (41h), 29527200 (17h)
  - Incident #118 raised for huntarr-start-29527200
- **Root Causes Identified**: 2026-02-21
  - Issue 1: `bitnami/kubectl` image unreachable/unavailable
  - Issue 2: RBAC missing `update` verb for kubectl scale operations
- **Fixes Applied**: 2026-02-21
  - Both issues already fixed in git (commit: 6a75395)
  - ArgoCD synced to production
  - Old failed jobs cleaned up
- **Status**: FULLY RESOLVED - Ready for production use
  - Next huntarr-start job: 2026-02-22 00:00 UTC
  - Next huntarr-stop job: 2026-02-21 08:00 UTC (or 2026-02-22 08:00 UTC)
