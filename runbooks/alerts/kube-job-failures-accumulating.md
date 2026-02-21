# KubeJobFailuresAccumulating

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeJobFailuresAccumulating |
| **Severity** | Warning |
| **Threshold** | >3 failed jobs per namespace/reason over 15 minutes |
| **Source** | PrometheusRule (kube_job_status_failed metric) |
| **Clusters Affected** | Production (media namespace most common) |

## Description

This alert fires when multiple Kubernetes jobs in a namespace have failed with the same reason. The most common causes are:
- **DeadlineExceeded**: Jobs timing out because NFS volumes fail to mount (FailedMount events)
- **BackoffLimitExceeded**: Jobs exhausting retry attempts

In the media namespace, this is most commonly caused by `mount-canary-writer` CronJobs failing because NFS volumes from TrueNAS-HDD (10.10.0.103) are unavailable.

## Quick Diagnosis

### 1. Check failed jobs in the namespace

```
mcp__infrastructure__kubectl_get_jobs(namespace="media")
# Look for jobs with COMPLETIONS 0/1 and non-zero FAILED count
```

### 2. Check pod events for the failed jobs

```
mcp__infrastructure__kubectl_get_events(namespace="media")
# Look for FailedMount, DeadlineExceeded events
```

### 3. Check NFS mount health

```
mcp__infrastructure__kubectl_get_pods(namespace="media")
# Check if any pods are stuck in ContainerCreating
```

### 4. Check TrueNAS NFS availability

```
mcp__observability__gatus_get_endpoint_status()
# Check TrueNAS-HDD NFS endpoint health
```

## Common Causes

### 1. NFS Mount Failures (FailedMount → DeadlineExceeded)

**Symptoms:**
- mount-canary-writer jobs fail with DeadlineExceeded
- FailedMount warning events in the namespace
- Pods stuck in ContainerCreating

**Verification:**
```
mcp__observability__query_metrics_instant(query='kube_job_status_failed{namespace="media",reason="DeadlineExceeded"} > 0')
```

**Resolution:**
1. Verify TrueNAS-HDD NFS service is running:
   - Check TrueNAS via MCP: `mcp__infrastructure__truenas_list_shares()`
   - NFS server IP: 10.40.0.10 (40Gbps network) or 10.10.0.103 (prod network)
2. Check network connectivity from worker nodes to NFS server
3. Verify NFS shares are exported: `/mnt/Taupo/Pleximetry`, `/mnt/Tekapo/*`
4. If NFS is down, restart NFS service on TrueNAS
5. Clean up failed jobs: the CronJob owner will create new ones automatically

### 2. Image Pull Failures

**Symptoms:**
- Jobs fail with BackoffLimitExceeded
- Pod events show ErrImagePull or ImagePullBackOff

**Verification:**
```
mcp__infrastructure__kubectl_get_events(namespace="media")
# Look for ImagePullBackOff events
```

**Resolution:**
- Check GHCR credentials: `ghcr-credentials` secret in the namespace
- Verify image tag exists in the registry
- Check network connectivity to ghcr.io

## Resolution Steps

### Step 1: Identify the failing jobs and reason

```
mcp__infrastructure__kubectl_get_jobs(namespace="media")
```

### Step 2: Check NFS health (most common root cause)

```
mcp__observability__gatus_get_endpoint_status()
```

### Step 3: If NFS is down, restart TrueNAS NFS service

Access TrueNAS management UI or API at 10.10.0.103.

### Step 4: Clean up old failed jobs

Failed CronJob pods are retained by the `failedJobsHistoryLimit` setting. They will be cleaned up automatically. To verify new jobs succeed after fixing the root cause, wait for the next CronJob schedule.

### Step 5: Verify resolution

```
mcp__observability__query_metrics_instant(query='kube_job_status_failed{namespace="media"} > 0')
# Should show no new failures after the fix
```

## Prevention

1. **Monitor NFS health** via Gatus endpoint checks
2. **Set reasonable deadlines** on CronJobs (`activeDeadlineSeconds`)
3. **Use mount-canary** job as an early warning for NFS issues
4. **Keep failedJobsHistoryLimit low** (3-5) to avoid metric bloat

## Related Alerts

- `KubeJobFailed` — Standard kube-prometheus-stack alert for individual job failures
- `KubeContainerStuckWaiting` — Catches containers stuck in waiting state (FailedMount symptom)
- `HomelabPodCrashLooping` — If pods restart after mount eventually succeeds
