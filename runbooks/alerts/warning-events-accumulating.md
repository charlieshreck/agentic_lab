# WarningEventsAccumulating

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | WarningEventsAccumulating |
| **Severity** | Warning |
| **Threshold** | >10 combined waiting pods + failed jobs per namespace over 10 minutes |
| **Source** | PrometheusRule (kube_pod_container_status_waiting + kube_job_status_failed) |
| **Clusters Affected** | All (most common in production media namespace) |

## Description

This alert fires when a namespace accumulates a high number of warning-level symptoms: pods stuck in waiting state (typically due to FailedMount) combined with failed jobs (typically DeadlineExceeded). This is a composite signal indicating systemic issues in a namespace rather than isolated failures.

The most common trigger is the media namespace when NFS volumes from TrueNAS-HDD become unavailable, causing mount-canary CronJobs to fail with DeadlineExceeded and media pods to get stuck with FailedMount events.

## Quick Diagnosis

### 1. Check warning events in the namespace

```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod")
# Look for FailedMount, DeadlineExceeded, BackOff events
```

### 2. Check pods in waiting state

```
mcp__infrastructure__kubectl_get_pods(namespace="media", cluster="prod")
# Look for pods in ContainerCreating or Init:0/1 state
```

### 3. Check failed jobs

```
mcp__infrastructure__kubectl_get_jobs(namespace="media", cluster="prod")
# Look for jobs with 0/1 completions
```

### 4. Check NFS availability (if media namespace)

```
mcp__infrastructure__truenas_list_shares()
mcp__observability__gatus_get_endpoint_status()
```

## Common Causes

### 1. NFS Mount Failures (FailedMount events)

**Symptoms:**
- Multiple pods stuck in ContainerCreating
- Events show "Unable to attach or mount volumes" or "timeout expired waiting for volumes"
- mount-canary-writer jobs fail with DeadlineExceeded

**Verification:**
```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod")
# Count FailedMount events
```

**Resolution:**
1. Check TrueNAS-HDD NFS service status
2. Verify network path: worker nodes -> 10.40.0.10 (40Gbps) or 10.10.0.103 (prod)
3. Restart NFS service on TrueNAS if needed
4. Wait for automatic recovery (mount-canary runs every 5 minutes)

### 2. Job Deadline Exceeded

**Symptoms:**
- Jobs show DeadlineExceeded in failure reason
- Jobs created but never complete before timeout
- Often correlates with FailedMount (NFS timeout causes job deadline to expire)

**Verification:**
```
mcp__infrastructure__kubectl_get_jobs(namespace="media", cluster="prod")
# Check activeDeadlineSeconds vs actual runtime
```

**Resolution:**
- If caused by NFS: fix the underlying mount issue first
- If caused by slow operations: increase activeDeadlineSeconds in the CronJob spec
- Clean up old failed jobs: they accumulate and keep firing the alert

### 3. Image Pull Failures

**Symptoms:**
- Pods stuck in ContainerCreating with ImagePullBackOff
- Events show "Failed to pull image"

**Verification:**
```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod")
# Look for ErrImagePull or ImagePullBackOff
```

**Resolution:**
- Check container registry connectivity
- Verify image tag exists
- Check imagePullSecrets are configured

## Resolution Steps

### Step 1: Identify the dominant event type

```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod")
```

Categorize: FailedMount vs DeadlineExceeded vs ImagePull vs other.

### Step 2: Address root cause

- **FailedMount**: See NfsMountFailuresAccumulating runbook
- **DeadlineExceeded**: See KubeJobFailuresAccumulating runbook
- **ImagePull**: Check registry and image tags

### Step 3: Clean up failed resources

Old failed jobs keep the alert firing. After fixing the root cause:
- Wait for successful job runs to confirm recovery
- Failed jobs auto-cleanup based on `failedJobsHistoryLimit` in CronJob spec

### Step 4: Verify recovery

```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod")
# Confirm no new warning events
mcp__infrastructure__kubectl_get_pods(namespace="media", cluster="prod")
# Confirm all pods running
```

## Prevention

1. **Gatus monitoring** for TrueNAS NFS endpoints
2. **mount-canary CronJob** as early warning for NFS issues
3. **Appropriate job deadlines** — not too short for NFS-dependent jobs
4. **failedJobsHistoryLimit** set to avoid accumulation of old failed jobs
5. **Resource requests/limits** to prevent resource-based scheduling failures

## Related Alerts

- `NfsMountFailuresAccumulating` — Focused on NFS mount pattern in media namespace
- `KubeJobFailuresAccumulating` — Focused on job failure counts by reason
- `KubeContainerStuckWaiting` — Individual containers stuck waiting >15 minutes
- `HomelabPodCrashLooping` — Pods restarting frequently (different failure mode)
