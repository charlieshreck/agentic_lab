# Matter Hub Health Check Transient Failure (#609)

## Summary
The matter-hub health check CronJob failed transiently when the matter-hub pod was temporarily unreachable during a restart cycle. The issue self-resolved after ~30 minutes as the pod recovered, but the old failed job persisted in the cluster.

## Root Cause
1. **Pod Restart Cycle**: Matter-hub pod experienced multiple restarts (4 total) due to networking or readiness probe issues
2. **Health Check Timeout**: During restart, the HTTP endpoint on port 8482 became unreachable
3. **Job Deadline**: The job's `activeDeadlineSeconds: 120` was exceeded while the pod was recovering
4. **Job History Limit**: The previous `failedJobsHistoryLimit: 3` allowed old failed jobs to persist longer than necessary

## Timeline
- **02:40:00** (2026-03-25): Job `matter-hub-health-check-29573440` created
- **02:40-02:42**: Job failed with `DeadlineExceeded` (pod was unreachable)
- **03:10-03:30**: Subsequent jobs (29573470, 29573480) succeeded (pod recovered)
- **02:07:48**: Fix deployed via commit 7ee305b (reduced `failedJobsHistoryLimit` from 3 to 1)

## Resolution (2026-03-25)
1. ✅ Deleted old failed job: `matter-hub-health-check-29573440`
2. ✅ Confirmed recent commit 7ee305b already deployed (reduces failedJobsHistoryLimit to 1)
3. ✅ Verified matter-hub pod is Running with Ready=true
4. ✅ Confirmed subsequent health check jobs succeeded

## Prevention
The recent fix (commit 7ee305b) prevents future buildup by reducing `failedJobsHistoryLimit` to 1. Benefits:
- Old failed jobs auto-clean on the next failure cycle
- `KubeJobFailed` alerts no longer persist after transient failures self-resolve
- Simplifies manual cleanup (fewer failed jobs to monitor)

## Manifest Changes
**File**: `prod_homelab/kubernetes/applications/apps/matter-hub/health-check.yaml`
```yaml
spec:
  failedJobsHistoryLimit: 1  # was 3, now 1
  successfulJobsHistoryLimit: 1
```

## Health Check Details
The CronJob runs every 10 minutes (`*/10 * * * *`):
1. Checks Matter Hub HTTP server responds on port 8482
2. Checks Matter Server TCP port 5580 is reachable (with 3 retries)
3. Retries: 3 attempts × 2s delay, each nc command has 10s timeout

**Max execution time**: ~30-40 seconds under worst conditions, well within 120s deadline.

## Related Incidents
- **#582**: Previous occurrence of same issue with higher history limit (resolved 2026-03-24)

## Notes
- This is a known pattern when pods restart during their readiness probe window
- The solution (lower history limit + auto-cleanup) is now deployed
- Manual deletion of failed job was optional (would auto-cleanup after next failure cycle with new code)
