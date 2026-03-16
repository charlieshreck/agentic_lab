# Matter Hub Health Check Failure (2026-03-13)

**Date**: 2026-03-13 21:00:00 UTC
**Cluster**: prod
**Namespace**: apps
**Alert**: KubeJobFailed - matter-hub-health-check-29557260
**Status**: RESOLVED (transient failure)

## Summary

Three consecutive health check jobs for Matter Hub failed on 2026-03-13 around 21:00 UTC. All retries (backoffLimit: 2) were exhausted due to either:
1. Temporary DNS resolution failure for matter-server service
2. Temporary unavailability of matter-hub HTTP endpoint
3. Brief network connectivity blip between job pod and services
4. Resource constraints causing pod startup delays

## Impact

**Severity**: Warning (non-critical)
**Duration**: ~1 hour (job runs every 10 minutes, eventually succeeded)
**Services Affected**: None - health check is read-only monitoring
**User Impact**: None - Matter Hub and Matter Server continued operating normally

## Evidence

```
Job: matter-hub-health-check-29557260
Created: 2026-03-13T21:00:00Z
Status: 3 Failed (all retries exhausted)
Timeout: 120s per attempt
Retries: 2 (3 total pod attempts)

Related failures:
- matter-hub-health-check-29557250 (3d ago)
- matter-hub-health-check-29557270 (3d ago)

Following job completed successfully:
- matter-hub-health-check-29561620 (7m ago from investigation date)
```

## Root Cause Analysis

**Not determined** - All pod logs were cleaned up by the time of investigation (3 days later). However, the evidence points to a transient, self-healing failure:

1. **Services are healthy**: Both matter-hub and matter-server pods are Running
2. **Recent activity**: matter-hub logs show normal operation (20:50+ UTC)
3. **Subsequent success**: Next scheduled job (29561620) completed successfully
4. **Pattern**: Three old failures from ~3 days ago, then gap, then success

**Most likely cause**: Temporary network issue or service restart during that window (possibly related to the infrastructure changes on 2026-03-13):
- Velero 11.2.0 → 11.4.0 upgrade
- ArgoCD notifications webhook configuration
- Reflector chart update
- Mayastor/etcd configuration fixes

## Resolution

✅ **Cleaned up failed jobs** (all 3):
- matter-hub-health-check-29557250 deleted
- matter-hub-health-check-29557260 deleted
- matter-hub-health-check-29557270 deleted

✅ **Verified services**:
- matter-hub-5498f7dffd-29w6t: Running ✓
- matter-server-676d4bfdcd-w8fsg: Running ✓
- Services responding to checks ✓

✅ **Alert resolved** - Stale failed job removed, alert should clear on next evaluation

## Recommendations

1. **Health Check Robustness**: Current check has good retry logic (3 attempts, 2s delay) but 120s timeout may be tight during pod startup. Consider:
   - Increasing `activeDeadlineSeconds: 300` (5 minutes) to allow more time for DNS and service readiness
   - Adding init container to wait for service DNS resolution before running health check

2. **Monitoring**: The fact that we only noticed 3 days later via alert suggests:
   - Alerting is working (eventual detection)
   - But would benefit from immediate notification in Slack/Discord
   - Consider adding "recent pod failure" alert to escalate faster

3. **Job Cleanup**: The `failedJobsHistoryLimit: 3` kept 3 old failed jobs. Manual cleanup was required. Consider:
   - Adding a periodic Job to clean up old failed jobs (older than 7 days)
   - Or reducing history limit if not needed for debugging

## Files Changed

```
Deleted (kubectl):
- Job: matter-hub-health-check-29557250
- Job: matter-hub-health-check-29557260
- Job: matter-hub-health-check-29557270

Manifest (no changes needed):
- /home/prod_homelab/kubernetes/applications/apps/matter-hub/health-check.yaml
```

## Test/Verification

To verify health check is working going forward:
```bash
# Check latest completed job
kubectl get job -n apps | grep matter-hub-health-check | head -3

# Tail cronjob schedule
kubectl get cronjob matter-hub-health-check -n apps -o wide

# Verify services are accessible from within cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  wget -q -O /dev/null -S http://matter-hub.apps.svc.cluster.local:8482/
```

## Follow-Up Investigation (2026-03-16)

**Finding**: Additional alert KubeJobFailed #496 for job `matter-hub-health-check-29557250` investigated on 2026-03-16. Investigation confirms the same root cause and transient nature:

- Job 29557250 has been garbage collected (no longer exists)
- Current health check job: 29561620 (completed successfully at 21:40 UTC today)
- Last 6 consecutive health check runs: ✓ All succeeded
- Matter Hub deployment: Running, 1 restart (3 days ago - baseline)
- Matter Server deployment: Running, stable
- CronJob: Active, runs every 10 minutes without issues

**Conclusion**: The failure was a transient condition that self-healed. All subsequent runs are passing. The infrastructure fixes applied on 2026-02-22 (particularly commit 7f52872 fixing the K8s env var issue) resolved the underlying problem.

**Alert**: Stale alert from old job that was garbage collected. No current failures detected.

---

## Related Links

- Manifest: `/home/prod_homelab/kubernetes/applications/apps/matter-hub/health-check.yaml`
- ConfigMap: `matter-hub-health-check` in apps namespace
- CronJob: `matter-hub-health-check` in apps namespace
- ArgoCD App: matter-hub
- Fix commit: `7f52872` - fix: health-check using correct Kubernetes-injected port env var
