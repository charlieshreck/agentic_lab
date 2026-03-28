# Mount-Canary Transient Failures

## Problem
The NFS mount canary job occasionally exceeds its 120-second `activeDeadlineSeconds` limit when NFS initialization is slow due to concurrent I/O from SABnzbd post-processing or PBS backups (typically 02:25-03:45 UTC).

**Affected Job**: `mount-canary-writer` CronJob in `media` namespace
**Current Deadline**: 120 seconds (increased from 60s on 2026-03-01)
**Schedule**: Every 5 minutes
**Recent Failure**: Job `mount-canary-writer-29573435` (2026-03-25 02:35:00 UTC)

## Root Cause
The cronjob must:
1. Mount two NFS volumes (`downloads` and `plexopathy`) from TrueNAS-Media (10.40.0.10)
2. Write sentinel files (`.mount_ok`) to each mount
3. Complete within 120 seconds

During peak load (SABnzbd post-processing + PBS backups), NFS mount initialization can exceed 120 seconds due to:
- Network latency to TrueNAS-Media
- I/O queue saturation on NFS server
- Concurrent large file transfers

## Why This Is Not Critical

1. **Self-Healing**: CronJob runs every 5 minutes. Transient delays recover automatically
2. **No Data Risk**: Subsequent jobs succeed (confirmed: job `mount-canary-writer-29573500` at 03:40 UTC completed in 5s)
3. **No Service Impact**: Failed job doesn't affect running applications or NFS mounts
4. **Rare**: Occurs during predictable peak windows (02:25-03:45 UTC) when bulk operations run

## Recovery
**Automatic**: No manual action required. The next CronJob execution (5 minutes later) succeeds.

**If Alert Persists**:
1. Check recent jobs: `kubectl get jobs -n media -l app=mount-canary`
2. Review logs of successful job: `kubectl logs -n media <job-pod>`
3. Confirm NFS health: `kubectl describe pvc -n media` or check TrueNAS dashboard
4. Delete failed job: `kubectl delete job mount-canary-writer-<failed-id> -n media`

## Permanent Solution Options

### Option A: Increase Deadline Further
```yaml
activeDeadlineSeconds: 180  # 3 minutes instead of 2
```
**Pros**: Accommodates occasional slow NFS initialization
**Cons**: Delays failure detection by 1 minute; hides underlying NFS performance issues

### Option B: Accept as Known Issue
Document as expected behavior during peak load windows. Alert is informational only.
**Pros**: No changes needed; reflects reality of occasional NFS latency
**Cons**: False alerts clutter incident tracking

### Option C: Optimize NFS Initialization
- Reduce concurrent I/O from SABnzbd/PBS during 02:00-03:00 UTC
- Add connection pooling/pre-warming to NFS mounts
- Upgrade TrueNAS Media to improve performance under load

**Current Status**: Recommended Option B - document as known behavior with self-recovery

## Related Configuration
- **NFS Mounts**: TrueNAS-Media (10.40.0.10) exports `/mnt/Taranaki/Tarriance/hopuhopu_katoa` and `/mnt/Tongariro/Plexopathy`
- **Mount Points**: `/media/downloads` and `/media/plexopathy` in pod
- **Security Context**: UID/GID 3000 (matches media app ownership)
- **Resource Requests**: 10m CPU, 16Mi memory (minimal overhead)

## See Also
- `kubernetes/applications/media/mount-canary/cronjob.yaml` - Job definition
- Git commits: `e467383` (deadline increase), `6bf63d0` (UID/GID fix)
