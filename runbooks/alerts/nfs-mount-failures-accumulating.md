# NfsMountFailuresAccumulating

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | NfsMountFailuresAccumulating |
| **Severity** | Warning |
| **Threshold** | >5 failed jobs in media namespace over 10 minutes |
| **Source** | PrometheusRule (kube_job_status_failed metric) |
| **Clusters Affected** | Production (media namespace) |

## Description

This alert fires when NFS-related job failures accumulate in the media namespace. The most common trigger is `mount-canary-writer` CronJobs failing because NFS volumes from TrueNAS-HDD cannot be mounted. This is a more specific variant of `KubeJobFailuresAccumulating` focused on the NFS mount failure pattern.

Key infrastructure:
- **NFS Server**: TrueNAS-HDD at 10.40.0.10 (40Gbps network) / 10.10.0.103 (prod network)
- **NFS Shares**: `/mnt/Taupo/Pleximetry` (media data — movies, TV, downloads)
- **CronJob**: `mount-canary-writer` runs every 5 minutes to verify NFS mount health

## Quick Diagnosis

### 1. Check warning events in media namespace

```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod", warning_only=True)
# Look for FailedMount, DeadlineExceeded events
```

### 2. Check failed jobs

```
mcp__infrastructure__kubectl_get_jobs(namespace="media", cluster="prod")
# Look for mount-canary-writer jobs with 0/1 completions
```

### 3. Check TrueNAS NFS health

```
mcp__infrastructure__truenas_list_shares()
mcp__observability__gatus_get_endpoint_status()
# Check TrueNAS-HDD NFS endpoint
```

### 4. Check if other media pods are affected

```
mcp__infrastructure__kubectl_get_pods(namespace="media", cluster="prod")
# Look for pods stuck in ContainerCreating
```

## Common Causes

### 1. TrueNAS-HDD NFS Service Down

**Symptoms:**
- All NFS-dependent pods in media namespace fail to mount
- mount-canary-writer jobs consistently fail with FailedMount
- Other media apps (Sonarr, Radarr, Plex) may also be affected

**Verification:**
```
mcp__infrastructure__truenas_list_shares()
# If this fails, TrueNAS NFS is likely down
```

**Resolution:**
1. Check TrueNAS management UI at https://10.10.0.103
2. Restart NFS service if needed
3. Verify NFS exports are present for `/mnt/Taupo/Pleximetry`
4. Wait for next mount-canary-writer run to verify recovery

### 2. Network Connectivity Issue

**Symptoms:**
- NFS mounts fail from some worker nodes but not others
- Intermittent mount failures

**Verification:**
- Check if the 40Gbps network (10.40.0.0/24) is up
- Verify worker node connectivity to 10.40.0.10

**Resolution:**
- Check switch port status for NFS network
- Verify LACP/LAG status if applicable
- Fall back to prod network path (10.10.0.103) if 40Gbps is down

### 3. UID Mismatch on TrueNAS-Media NFS

**Symptoms:**
- mount-canary-writer jobs fail with permission denied or mount timeout
- Failures accumulate but resolve after Kubernetes Job objects are cleaned up
- Root cause: pod UID (1000) doesn't match NFS export requirements (UID 3000)

**Verification:**
- Check TrueNAS-Media NFS ACLs at 10.40.0.10 — verify required UID is 3000, not 1000
- Check mount-canary-writer pod security context: `spec.securityContext.runAsUser`

**Resolution:**
- Verify fix is deployed: `git -C /home/prod_homelab log --oneline kubernetes/applications/media/mount-canary/`
- Deployment should have `runAsUser: 3000` in pod spec (commit 6bf63d0 and later)
- If deployed but alert persists: delete stale failed Job objects
  - `kubectl delete job -n media -l app=mount-canary-writer --field-selector status.successful=0`
  - `kubectl delete job -n media -l app=huntarr --field-selector status.successful=0`
- Wait for next mount-canary-writer run to verify recovery

### 4. Transient NFS Timeout

**Symptoms:**
- A few failures followed by recovery
- mount-canary-writer fails for 1-2 runs then succeeds

**Verification:**
- Check event timestamps — are failures clustered or continuous?
- If failures stop within 15 minutes, this is transient

**Resolution:**
- Transient failures are normal during TrueNAS maintenance or heavy I/O
- No action needed if failures self-resolve
- Consider increasing `activeDeadlineSeconds` on the CronJob if timeouts are too aggressive

## Resolution Steps

### Step 1: Confirm the failure pattern

```
mcp__infrastructure__kubectl_get_events(namespace="media", cluster="prod", warning_only=True)
```

### Step 2: Check NFS availability

```
mcp__infrastructure__truenas_list_shares()
```

### Step 3: If NFS is down, investigate TrueNAS

Access TrueNAS at 10.10.0.103 and check:
- ZFS pool status (Taupo pool)
- NFS service status
- System alerts

### Step 4: Verify recovery

Wait for the next mount-canary-writer CronJob run (every 5 minutes) and confirm success.

## Prevention

1. **Gatus monitoring** for TrueNAS NFS endpoint
2. **mount-canary CronJob** as early warning system
3. **Dual-path NFS** (40Gbps + prod network fallback)
4. **TrueNAS alerts** forwarded via alert-forwarder to LangGraph

## Related Alerts

- `KubeJobFailuresAccumulating` — General job failure alert (parent pattern)
- `KubeContainerStuckWaiting` — Containers stuck in waiting state due to FailedMount
- `VeleroBackupFailed` — Backups may also fail if NFS is unavailable
