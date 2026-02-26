# Velero PartiallyFailed — emptyDir Volume Backup Hang

**Alert**: Velero backup `PartiallyFailed` with exactly 1 error on prod cluster

**Root Cause**: With `defaultVolumesToFsBackup: true` on the Velero Schedule, Velero
tries to back up ALL pod volumes including `emptyDir` types via Kopia. Kopia starts a
data path process for the emptyDir but it hangs indefinitely (never errors, never completes)
until the backup times out. This shows as exactly `1 error` per backup.

**First Identified**: 2026-02-26, affecting prod daily/weekly backups since ~2026-02-08.

---

## Verification

Check if this is the emptyDir pattern:

```bash
# Find the stuck PVB
kubectl -n velero get podvolumebackup | grep -v Completed

# Check which pod/volume it's for
kubectl -n velero get podvolumebackup <pvb-name> -o jsonpath='{.spec.pod.name} {.spec.volume}'

# Check if the volume is emptyDir
kubectl -n <namespace> get pod <pod-name> -o json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for v in d['spec']['volumes']:
    print(v.get('name'), '->', list(v.keys()))
"

# Watch node-agent logs — emptyDir hang shows as 5-second "creating data path routine" loop
kubectl -n velero logs <node-agent-pod-on-affected-node> | grep <pvb-name> | tail -20
```

---

## Fix

Add a Velero exclude annotation to the pod template of the affected deployment:

```yaml
# In deployment.yaml spec.template.metadata.annotations:
annotations:
  backup.velero.io/backup-volumes-excludes: <volume1>,<volume2>
```

**Example** (homepage): `backup.velero.io/backup-volumes-excludes: homepage-config,logs`

Apply via GitOps — commit to the relevant cluster repo and let ArgoCD sync.

The fix takes effect after ArgoCD syncs AND the pod is restarted (the annotation lives
on the running pod, not just the deployment spec). The next backup after pod restart
will no longer include the excluded volumes.

---

## Why emptyDir Can't Be Backed Up

`emptyDir` volumes are ephemeral — they are created empty on pod start. There is no
persistent data to preserve. Common patterns that use emptyDir:

- **Init container copy pattern**: ConfigMap → emptyDir → main container (e.g., homepage)
- **Scratch space / logs**: Temporary writes not worth preserving
- **Shared memory / tmpfs**: Never needs backup

These volumes should always be excluded from Velero backup.

---

## Known Affected Deployments

| Deployment | Namespace | Volumes to Exclude | Fixed |
|------------|-----------|-------------------|-------|
| homepage   | apps      | homepage-config, logs | 2026-02-26 (commit 58cb0d7) |

---

## Prevention

When adding new deployments with emptyDir volumes, always add the exclude annotation
if `defaultVolumesToFsBackup: true` is set on the cluster's Velero schedules.

Check current schedule config:
```bash
kubectl -n velero get schedule -o yaml | grep defaultVolumesToFsBackup
```
