# KubeJobFailed: CronJob Timeout Investigation

**Alert**: `KubeJobFailed`
**Severity**: warning
**Affected Component**: Kubernetes Job resources created by CronJobs
**Date Created**: 2026-02-22

---

## Problem Description

The `KubeJobFailed` alert fires when a Kubernetes Job fails to complete successfully. Common causes for CronJob-based Jobs:

1. **Timeout exceeded** (`DeadlineExceeded`) - Job exceeded `activeDeadlineSeconds`
2. **Pod eviction** - Resource constraints or node pressure
3. **Image pull failures** - Cannot pull container image
4. **RBAC/Permission denied** - Service account lacks necessary permissions
5. **API server connectivity** - Pod cannot reach Kubernetes API server

---

## Investigation Steps

### 1. Get Job Details
```bash
# Find the failed job
kubectl get jobs -n <namespace> --sort-by=.metadata.creationTimestamp | grep -i failed

# Get full job manifest
kubectl get job -n <namespace> <job-name> -o yaml

# Check job status
kubectl describe job -n <namespace> <job-name>
```

### 2. Check Job Events
Look for `DeadlineExceeded` in the `Status.Conditions` and `Events` section:

```yaml
Events:
  Type     Reason            Age   From            Message
  ----     ------            ----  ----            -------
  Normal   SuccessfulCreate  23m   job-controller  Created pod: ...
  Warning  DeadlineExceeded  18m   job-controller  Job was active longer than specified deadline
```

### 3. Identify Root Cause by Job Type

#### For CronJobs that use `kubectl` container:
- Check `activeDeadlineSeconds` - is it realistic for the operation?
- Check `imagePullPolicy` - is it `Always` (re-pulls every time) or `IfNotPresent`?
- Verify `image` is accessible from pod network
- Check if API server connectivity exists from pod namespace

**Example**: `huntarr-start-29528640` (Incident #128)
- Timeout: 300s (5 minutes)
- Image: `registry.k8s.io/kubectl:v1.34`
- Issue: `imagePullPolicy: Always` caused image pull to exceed 5-minute deadline

---

## Huntarr CronJob Pattern

The `huntarr-start` and `huntarr-stop` CronJobs scale the huntarr deployment up/down:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: huntarr-start
  namespace: media
spec:
  schedule: "0 0 * * *"  # Daily at midnight
  jobTemplate:
    spec:
      activeDeadlineSeconds: 600  # 10 minutes
      template:
        spec:
          serviceAccountName: huntarr-scheduler
          containers:
          - name: kubectl
            image: registry.k8s.io/kubectl:v1.34
            imagePullPolicy: IfNotPresent  # Key: don't re-pull every run
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment/huntarr --replicas=1 -n media
```

**Fixed issues** (as of 2026-02-22):
- ✅ `activeDeadlineSeconds: 300` → `600` (5min → 10min)
- ✅ Added `imagePullPolicy: IfNotPresent` (was missing)

---

## Fix for CronJob Timeouts

### Quick Fix
For immediate resolution of a failed job:

```bash
# Delete the failed job (alert will clear)
kubectl delete job -n <namespace> <job-name>

# CronJob will create a new instance at next scheduled time
```

### Permanent Fix
If jobs are consistently timing out:

1. **Increase timeout**:
   ```yaml
   activeDeadlineSeconds: 600  # or higher if needed
   ```

2. **Optimize image pulls**:
   ```yaml
   imagePullPolicy: IfNotPresent  # Don't re-pull every time
   ```

3. **Pre-pull image** (optional):
   ```bash
   # Ensure image is cached on all nodes
   kubectl set image -n kube-system daemonset/... image=...
   ```

4. **Verify RBAC** (if using kubectl/API calls):
   ```bash
   # Test service account permissions
   kubectl auth can-i get deployments --as=system:serviceaccount:<ns>:<sa> -n <ns>
   kubectl auth can-i patch deployments --as=system:serviceaccount:<ns>:<sa> -n <ns>
   ```

---

## Monitoring

To prevent future occurrences:

1. **Monitor CronJob success rates**:
   ```bash
   kubectl get cronjob -n <namespace> <name> --watch
   ```

2. **Check Job history**:
   ```bash
   kubectl get jobs -n <namespace> -l batch.kubernetes.io/cronjob-name=<name> --sort-by=.metadata.creationTimestamp
   ```

3. **Set up PrometheusRule** for failing CronJobs:
   ```yaml
   - alert: CronjobSuspendedOrFailing
     expr: changes(kube_cronjob_status_last_schedule_time[6h]) == 0
   ```

---

## Resolution for Incident #128

**Job**: `media/huntarr-start-29528640`
**Cause**: `activeDeadlineSeconds: 300` too short for image pull + startup
**Fix**:
- Increased deadline to 600s
- Added `imagePullPolicy: IfNotPresent`
- Deleted failed job

**Commit**: `prod_homelab/c818137` - "fix: increase huntarr CronJob timeout"

**Next occurrence**: Next CronJob run (midnight UTC) will use new 10-minute deadline

---

## Related Links
- [Kubernetes Job Timeout](https://kubernetes.io/docs/concepts/workloads/controllers/job/#job-termination-and-cleanup)
- [Image Pull Policy](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy)
- [CronJob Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)

