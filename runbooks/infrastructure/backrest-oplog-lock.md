# Backrest OpLog Lock Contention

## Alert

- **Name**: KubePodCrashLooping
- **Pod**: backrest/* (namespace: backrest)
- **Reason**: "oplog is locked by another instance of backrest"

## Root Cause

Backrest uses a file-based oplog (operation log) for managing backup state. The oplog file has an exclusive lock that prevents concurrent access. During rolling deployments with `RollingUpdate` strategy, Kubernetes can start the new pod while the old pod is still terminating, causing both to attempt oplog access simultaneously.

**Error Log**:
```
FATAL    oplog is locked by another instance of backrest    {"data_dir": "/data"}
```

## Solution

Change the deployment strategy from `RollingUpdate` to `Recreate`. This ensures the old pod is fully terminated before the new pod starts, preventing oplog lock contention.

### Fix

Edit the Backrest deployment in `monit_homelab/kubernetes/applications/backrest/deployment.yaml`:

```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate  # ← Change from RollingUpdate to Recreate
  selector:
    matchLabels:
      app: backrest
```

**Why**: Backrest does NOT support concurrent instances on the same PVC due to the oplog lock mechanism. The `Recreate` strategy is the correct pattern for single-replica stateful workloads with exclusive file locks.

## Verification

After ArgoCD syncs the updated manifest:

1. Check pod is running and ready:
   ```bash
   kubectl get pods -n backrest
   ```

2. Verify no crash loops:
   ```bash
   kubectl describe pod -n backrest backrest-*
   ```

3. Check logs for successful startup:
   ```bash
   kubectl logs -n backrest backrest-* | tail -20
   ```

Should see:
```
INFO    backrest starting    {"version": "v1.12.0", ...}
INFO    restic binary "/bin/restic" in $PATH matches required version...
```

## Prevention

- **Review**: Stateful workloads with exclusive file locks should use `Recreate` strategy
- **Test**: Deploy changes during low-traffic windows to validate strategy behavior
- **Monitor**: Watch for CrashLoopBackOff on first deployment update to catch similar issues

## Related Issues

- Single-replica Backrest cannot support RollingUpdate (oplog lock is per-instance)
- ReadWriteOnce PVCs are compatible with multiple pods only if they don't hold exclusive locks
- Kubernetes RollingUpdate with 1 replica allows a window where both old/new pods exist

## Incident

- **ID**: #196
- **Date**: 2026-02-23
- **Fix Commit**: `monit_homelab:d8fbee0`
