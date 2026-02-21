# KubeJobFailed Alert Runbook

## Overview

Alert: `KubeJobFailed`
Severity: warning
Source: kube-state-metrics
Namespace: media (typically)

## Symptoms

- Job `huntarr-stop-*`, `huntarr-start-*`, or `configarr-*` fails to complete
- Pods stuck in `Failed` or `ImagePullBackOff` state
- Scheduled CronJobs creating failed Job runs

## Root Causes

### 1. Image Pull Failures (Most Common)
- CronJob template references image that doesn't exist or cannot be pulled
- Examples:
  - `bitnami/kubectl:1.31` (correct: `registry.k8s.io/kubectl:v1.31`)
  - `ghcr.io/raydak-labs/configarr:2.1.0` (correct: `ghcr.io/raydak-labs/configarr:1.20`)
- Usually occurs when manifests are updated in git but ArgoCD sync is pending or failed

### 2. Cluster Out of Sync
- Git manifests have correct image tags
- Live cluster has stale CronJob specs referencing old image tags
- Happens when ArgoCD sync fails or is delayed

### 3. Job Backoff Loop
- Pods continuously fail and retry (backoff limit exhausted)
- historylimit settings keep failed jobs around, triggering repeated alerts

## Investigation Steps

1. **Check CronJob definition in git:**
   ```bash
   cat prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml | grep image:
   cat prod_homelab/kubernetes/applications/media/configarr/cronjob.yaml | grep image:
   ```

2. **Check live CronJob spec:**
   ```bash
   kubectl -n media describe cronjob huntarr-stop
   kubectl -n media describe cronjob configarr
   ```

3. **Check failed Job pods:**
   ```bash
   kubectl -n media get jobs
   kubectl -n media get pods -l job-name=huntarr-stop-29526240  # or specific job
   kubectl -n media describe job huntarr-stop-29526240
   ```

4. **Check events for image pull errors:**
   ```bash
   kubectl -n media get events --sort-by='.lastTimestamp'
   # Look for: "Failed to pull image", "ErrImagePull", "ImagePullBackOff"
   ```

5. **Force ArgoCD sync:**
   ```bash
   argocd app sync huntarr --force
   argocd app sync configarr --force
   ```

## Resolution

### Option A: Clean Up Old Failed Jobs (Preferred)
Failed Jobs are ephemeral and will be recreated by CronJobs on the next schedule with correct images:

```bash
# Delete all failed jobs in media namespace
kubectl -n media delete jobs --field-selector status.failed=1

# Or delete specific failed jobs
kubectl -n media delete job huntarr-stop-29526240 huntarr-start-29509920 configarr-29509920

# Verify cleanup
kubectl -n media get jobs
```

### Option B: Force Immediate CronJob Sync
If you need immediate execution with correct image:

```bash
# Create job from CronJob template (forces new pod with current spec)
kubectl create job --from=cronjob/huntarr-stop huntarr-stop-manual -n media
kubectl create job --from=cronjob/configarr configarr-manual -n media

# Monitor logs
kubectl -n media logs -f job/huntarr-stop-manual
kubectl -n media logs -f job/configarr-manual
```

### Option C: Manual Fix (Last Resort)
If images are truly unavailable, update the CronJob manifest in git:

1. **Update `prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`:**
   ```yaml
   # Ensure correct image tags
   image: registry.k8s.io/kubectl:v1.31
   ```

2. **Update `prod_homelab/kubernetes/applications/media/configarr/cronjob.yaml`:**
   ```yaml
   image: ghcr.io/raydak-labs/configarr:1.20
   ```

3. **Commit and push:**
   ```bash
   git -C /home/prod_homelab add kubernetes/applications/media/huntarr/ kubernetes/applications/media/configarr/
   git -C /home/prod_homelab commit -m "fix: update cronjob image tags to valid versions"
   git -C /home/prod_homelab push origin main
   ```

4. **Force ArgoCD sync:**
   ```bash
   argocd app sync huntarr --force
   argocd app sync configarr --force
   ```

## Prevention

1. **Always verify image tags exist before updating manifests:**
   ```bash
   docker pull registry.k8s.io/kubectl:v1.31
   docker pull ghcr.io/raydak-labs/configarr:1.20
   ```

2. **Enable ArgoCD auto-sync** for critical applications

3. **Set `failedJobsHistoryLimit: 3`** to limit alert spam from old jobs

4. **Monitor image pull failures** in prometheus:
   ```promql
   rate(container_runtime_cri_operations_errors_total{operation_type=~"PullImage"}[5m])
   ```

## References

- Kubernetes Jobs: https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Kubernetes CronJobs: https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- Image Pull Policies: https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy
- ArgoCD Sync Docs: https://argo-cd.readthedocs.io/en/stable/user-guide/application-management/

## Related Alerts

- `KubePodCrashLooping`: Pod continuously fails and restarts
- `KubeDeploymentGenerationMismatch`: Deployment spec out of sync with live state
- `ImagePullBackOff`: Container image cannot be pulled from registry

