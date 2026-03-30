# Velero Kopia Repository Re-initialization

## Alert
- **Name**: KubeJobFailed (kopia-maintain jobs)
- **Domain**: Storage / Kubernetes
- **Severity**: Warning (escalates to Critical if backups missing >48h)

## Symptoms
- `*-garage-kopia-maintain-job-*` pods showing Error status across clusters
- Error: `repository not initialized in the provided storage`
- BackupRepository CRDs show `Ready` (misleading)
- Backups show `PartiallyFailed` with errors on PodVolumeBackup operations

## Root Cause
Garage S3 buckets were recreated (intentionally or due to Garage restart/migration), wiping all kopia repository metadata inside them. The Velero BackupRepository CRDs still report `Ready` because they check the BackupStorageLocation (S3 endpoint availability), not the actual kopia repo state inside the bucket.

Prod cluster may auto-recover if its scheduled backup runs before the maintain jobs, because the backup process initializes the repo. Agentic and monit may not auto-recover if their stale CRDs prevent re-initialization.

## Detection
Check for kopia-maintain job failures:
```bash
kubectl get pods -n velero | grep kopia | grep Error
```

Check the error:
```bash
kubectl logs -n velero <failed-kopia-pod>
# Look for: "repository not initialized in the provided storage"
```

Verify bucket creation dates (requires Garage admin token):
```bash
curl -s -H "Authorization: Bearer $GARAGE_TOKEN" http://10.10.0.103:30190/v1/bucket | python3 -m json.tool
# If created dates are recent, buckets were recreated
```

## Fix

### 1. Delete stale BackupRepository CRDs
```bash
# On each affected cluster:
kubectl get backuprepository -n velero -o name | while read repo; do
    echo "Deleting $repo"
    kubectl delete "$repo" -n velero
done
```

### 2. Trigger manual backup to re-initialize repos
```bash
cat <<EOF | kubectl apply -f -
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: manual-reinit-<cluster>
  namespace: velero
spec:
  storageLocation: garage
  ttl: 72h0m0s
EOF
```

### 3. Verify
```bash
# Wait 2-5 minutes, then:
kubectl get backup manual-reinit-<cluster> -n velero -o jsonpath='{.status.phase}'
# Should be: Completed

kubectl get backuprepository -n velero -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'
# All should show: Ready
```

## Validation
- Backup phase: `Completed` (0 errors acceptable, warnings OK)
- All BackupRepository CRDs: `Ready` with recent `lastMaintenanceTime`
- Subsequent kopia-maintain jobs: `Completed` (not Error)

## Automation Potential
- **Could automate**: Yes
- **Tools needed**: `kubectl delete backuprepository`, `kubectl apply` for Backup resources, Garage admin API access
- **Blocker**: `kubectl delete backuprepository` is a destructive operation not currently in the estate patrol allowed tools. `kubectl apply` is blocked by GitOps guardrails.

## Lessons Learned
- BackupRepository CRDs report Ready based on BSL availability, not actual kopia repo state
- When Garage buckets are recreated, stale CRDs must be deleted to trigger re-initialization
- Prod may auto-recover because its backup runs first (02:00 UTC vs 02:30 UTC for agentic/monit)
- Monitor for bucket recreation events in Garage to catch this proactively
- The 274 warnings on monit are expected (skipped PVCs, node-agent issues) — not related to this problem

---
*Created by Estate Patrol v2 from human resolution on 2026-03-30*
