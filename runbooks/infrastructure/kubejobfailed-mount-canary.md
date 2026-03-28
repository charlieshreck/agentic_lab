# KubeJobFailed: mount-canary-writer

## Alert Description

Alert: **KubeJobFailed** with severity **warning**
- Namespace: `media`
- Job: `mount-canary-writer-*`
- Cluster: `production`

## What This Canary Does

The `mount-canary-writer` CronJob runs every 5 minutes and writes sentinel files to two NFS-mounted directories to verify NFS connectivity is healthy:

- `/media/downloads` → `10.40.0.10:/mnt/Taranaki/Tarriance/hopuhopu_katoa`
- `/media/plexopathy` → `10.40.0.10:/mnt/Tongariro/Plexopathy`

It uses `busybox:1.37`, runs as UID/GID 3000, with a 120-second `activeDeadlineSeconds`.

## Failure Modes

### 1. Transient NFS Timeout (most common)

**Symptoms**: Job fails with `DeadlineExceeded` reason. Subsequent runs succeed.

**Cause**: Brief NFS unresponsiveness from TrueNAS-Media (10.40.0.10) — e.g., disk I/O spike, reboot, network blip.

**Fix**: Delete the failed job to clear the alert. No other action needed.

```bash
kubectl --context admin@homelab-prod delete job <job-name> -n media
# e.g.: kubectl --context admin@homelab-prod delete job mount-canary-writer-29571990 -n media
```

**Confirm recovery**: Check the next job succeeded:
```bash
kubectl --context admin@homelab-prod get jobs -n media | grep mount-canary
```

### 2. Persistent NFS Failure

**Symptoms**: Multiple consecutive jobs fail. No recent successful runs.

**Cause**: TrueNAS-Media offline, NFS export removed, network partition, or dataset deleted.

**Investigation**:
```bash
# Check TrueNAS-Media alerts
mcp: truenas_get_alerts(instance="media")

# Check recent events
kubectl --context admin@homelab-prod get events -n media | grep mount-canary

# Check if NFS is reachable
ssh root@10.10.0.178 "showmount -e 10.40.0.10"
```

**Fix**: Restore NFS service on TrueNAS-Media or fix network connectivity.

### 3. Wrong NFS Paths (historical, fixed 2026-03)

**Symptoms**: Job fails with `OOMKilled` or pod stuck in `ContainerCreating` (NFS mount hang).

**Cause**: CronJob configured with non-existent NFS paths.

**Current valid paths** (as of 2026-03-24):
- `/mnt/Taranaki/Tarriance/hopuhopu_katoa` ✓
- `/mnt/Tongariro/Plexopathy` ✓

If paths change, update manifest:
```
prod_homelab/kubernetes/applications/media/mount-canary/cronjob.yaml
```

## Standard Resolution (Transient)

```bash
# 1. Confirm it's transient (latest job succeeded)
kubectl --context admin@homelab-prod get jobs -n media | grep mount-canary

# 2. Delete the failed job to clear the alert
kubectl --context admin@homelab-prod delete job <failed-job-name> -n media

# 3. Confirm no more failed jobs
kubectl --context admin@homelab-prod get jobs -n media | grep mount-canary
```

## Alert Configuration

CronJob schedule: `*/5 * * * *` (every 5 minutes)
- `backoffLimit: 1` — 1 retry before marking failed
- `activeDeadlineSeconds: 120` — 2-minute timeout
- `failedJobsHistoryLimit: 1` — keeps only the most recent failed job

## Related Resources

- CronJob manifest: `prod_homelab/kubernetes/applications/media/mount-canary/cronjob.yaml`
- NFS server: 10.40.0.10 (TrueNAS-Media NFS, vmbr3 10.40.0.0/24)
- TrueNAS-Media management: 10.10.0.100

## Incident History

| Date | Job | Failure Reason | Resolution |
|------|-----|---------------|------------|
| 2026-03-24T02:30Z | mount-canary-writer-29571990 | DeadlineExceeded (transient NFS timeout) | Deleted failed job; subsequent runs OK |
| 2026-03 (earlier) | multiple | Wrong NFS paths (datasets didn't exist) | Updated cronjob.yaml to correct paths |
