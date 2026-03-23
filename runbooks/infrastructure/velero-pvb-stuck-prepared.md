# Velero PodVolumeBackup Stuck in Prepared State

## Alert
`velero_pod_unhealthy` — backup pod in `Pending` or `Running` for >10 minutes with `Prepared` PVB status.

## Symptoms
- Backup pod(s) from prior days still running (`daily-backup-YYYYMMDD-*` or `weekly-backup-*`)
- PodVolumeBackup CR(s) stuck in `phase: Prepared` with empty `repoIdentifier`
- Node-agent log floods with `creating data path routine` every 2–3 seconds — no errors logged
- Current-day backup fails with `PartiallyFailed` after 4h (itemOperationTimeout)
- Multiple backup pods accumulating over days (one per stuck PVB)

## Root Cause
The node-agent's in-memory data path manager accumulates state from stuck PVBs. When a PVB gets stuck in `Prepared` (initial trigger: gRPC handshake failure, pod reschedule, or first-time connectivity issue), the node-agent enters an infinite reconcile loop calling `createDataPathRoutine`. Each retry adds entries to the goroutine pool without cleaning up previous failed attempts.

As the backlog grows (5+ PVBs per node), the data path manager deadlocks internally: subsequent `createDataPathRoutine` calls silently fail (no error logged), preventing any new PVBs on that node from progressing.

Symptoms are **node-specific** — only nodes with accumulated stale PVBs are affected. Other nodes continue working normally.

**Trigger for accumulation**: The original stuck PVB is caused by the node-agent failing to connect to the backup pod's gRPC server on startup. The backup pod waits indefinitely; Velero's parent Backup CR eventually times out and completes as `PartiallyFailed`, but the PVB and its pod are never cleaned up.

## Investigation

```bash
# 1. Check for old backup pods still Running
kubectl get pods -n velero --context admin@homelab-prod | grep -E "daily-backup|weekly-backup"

# 2. Check PVB status — look for phase: Prepared with empty repoIdentifier
kubectl get podvolumebackup -n velero --context admin@homelab-prod
kubectl get podvolumebackup <name> -n velero -o yaml --context admin@homelab-prod | grep -E "phase|repoIdentifier"

# 3. Check node-agent logs — stuck loop signature:
# "PVB is prepared and should be processed by X"
# "Hosting pod is in running state"
# "Exposed PVB is ready and creating data path routine"
# ...repeated every 2-3 seconds with no errors
kubectl logs <node-agent-pod> -n velero --context admin@homelab-prod | tail -50

# 4. Check parent Backup CR status
kubectl get backup <backup-name> -n velero -o yaml --context admin@homelab-prod | grep -E "phase|completionTimestamp"
```

## Fix

### 1. Delete orphaned PVBs (parent Backup already completed)
```bash
# Delete all stuck PVBs — Velero will remove finalizers automatically
kubectl delete podvolumebackup -n velero --context admin@homelab-prod \
  <pvb-name-1> <pvb-name-2> ...

# Or delete all Prepared PVBs whose parent Backup is completed:
kubectl get podvolumebackup -n velero -o json --context admin@homelab-prod | \
  jq -r '.items[] | select(.status.phase=="Prepared") | .metadata.name'
```

### 2. Restart stuck node-agent(s)
```bash
# Identify which nodes are stuck (look for the retry loop in logs)
kubectl get pods -n velero --context admin@homelab-prod | grep node-agent

# Delete the stuck node-agent pods (DaemonSet restarts them automatically)
kubectl delete pod <node-agent-pod-name> -n velero --context admin@homelab-prod
```

### 3. Verify recovery
```bash
# Node-agent should log: "MicroServiceBR is initialized" and "asyncBR is resumed"
kubectl logs <new-node-agent-pod> -n velero --context admin@homelab-prod | grep -E "initialized|resumed|started"

# Backup pod should start logging Kopia progress
kubectl logs <backup-pod-name> -n velero --context admin@homelab-prod | tail -20
```

## Prevention

The accumulation requires an initial stuck PVB. The known trigger is a gRPC connection failure at backup start. To reduce impact:

1. **Monitor for stuck PVBs**: Alert when any PVB stays in `Prepared` for >30 minutes (before the 4h timeout). Current alert fires when the backup POD is in `Pending`, which is too late.

2. **Current Velero version**: v1.17.1. This is a known issue with the micro-service architecture's data path manager. May be fixed in later versions — check release notes.

3. **TTL cleanup**: PVBs are owned by their parent Backup CR. When the Backup CR expires and is garbage-collected, orphaned PVBs should also be cleaned up. Daily backups have 7-day TTL, so stale PVBs eventually auto-clean if the accumulation stops.

## Resolution History

| Date | Finding | Affected Nodes | Stuck PVBs | Root Trigger | Fix Applied |
|------|---------|----------------|------------|--------------|-------------|
| 2026-03-23 | #1319 | worker-01, worker-03 | 7 (5 daily Mar 18-22 + 2 weekly Mar 22) | Mar 18 gRPC handshake failure for filebrowser-data PVC | Deleted 7 PVBs + restarted node-agents on workers 01 and 03 |
