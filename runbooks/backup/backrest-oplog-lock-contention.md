# Backrest oplog Lock Contention Recovery

## Alert
`backrest_unreachable` — Backrest API becomes unreachable due to simultaneous backup instances corrupting the restic repository oplog.

## Root Cause
Backrest uses the restic backup tool, which stores operation metadata in an `oplog` (operation log) within the S3 repository. When multiple Backrest instances run concurrently (due to `RollingUpdate` strategy), they compete for oplog writes:
- Pod A and Pod B both attempt to write to the same oplog
- Locking conflicts occur
- API becomes unstable or unreachable
- Pod health checks fail

## Prevention (IMPLEMENTED)
**Deployment strategy**: Changed from `RollingUpdate` to `Recreate`
- **RollingUpdate** (WRONG): Starts new pod → waits for readiness → then kills old pod = CONCURRENT instances
- **Recreate** (CORRECT): Kills old pod → waits for termination → then starts new pod = NO concurrent instances

**File**: `monit_homelab/kubernetes/applications/backrest/deployment.yaml` (line 40-41)
```yaml
spec:
  strategy:
    type: Recreate  # NOT RollingUpdate
```

## Detection
Readiness probe detects pod becoming not-ready:
- HTTP GET `/` on port 9898
- Initial delay: 10s, period: 15s, failure threshold: 3
- When health checks fail, pod is removed from service endpoints

Monitoring detects API unreachable when readiness probe fails.

## Recovery
No manual action needed. The `Recreate` strategy ensures:
1. Old pod is terminated completely
2. New pod starts fresh with clean oplog access
3. Single instance rule prevents lock contention
4. Pod becomes ready within 30s typically
5. API automatically accessible again

## Verification
- Pod status: `Running` and `Ready`
- Service endpoints show pod IP
- Liveness probe passing (interval: 30s, 3 failures to kill)
- Backup schedules are active and scheduled

## If Issue Persists
1. Check backup job logs for S3 connectivity issues:
   ```
   kubectl -n backrest logs -f backrest-* --tail=50
   ```
2. Verify Garage S3 endpoint is reachable from pod:
   ```
   kubectl -n backrest exec -it backrest-* -- curl -I https://garage-s3-endpoint:30188
   ```
3. Check if restic repository is corrupted:
   ```
   kubectl -n backrest exec -it backrest-* -- restic -r s3://... check
   ```
4. If corrupted, escalate to human operator for repository recovery

## Links
- **Deployment**: `monit_homelab/kubernetes/applications/backrest/deployment.yaml`
- **Monitoring**: Readiness probe at lines 117-123
- **Ticket**: Incident #886 (backrest_unreachable)
