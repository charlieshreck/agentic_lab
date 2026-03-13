# Velero Restore Procedure (Kopia File-Level)

**When to use**: Restoring persistent volume data after data loss (Mayastor etcd wipe, PV corruption, accidental deletion).

**Backup system**: Velero with Kopia uploader, Garage S3 backend.

**Schedules**: Daily at 02:00 UTC (7-day retention), Weekly Sundays at 03:00 UTC (30-day retention).

---

## Prerequisites

- `KUBECONFIG=/root/.kube/config` (prod cluster context)
- Velero controller and all 3 node-agents running: `kubectl get pods -n velero -l 'name in (velero, node-agent)'`
- No concurrent backup operations (check: `kubectl get podvolumebackups -n velero | grep InProgress`)
- ArgoCD may need to be paused (see Step 0)

## Quick Reference

| Command | Purpose |
|---------|---------|
| `kubectl get backups -n velero --sort-by=.metadata.creationTimestamp` | List available backups |
| `kubectl get podvolumebackups -n velero -l velero.io/backup-name=<backup>` | List PVBs in a backup |
| `kubectl get restores -n velero` | List restore attempts |
| `kubectl get podvolumerestores -n velero` | List PVR progress |
| `kubectl get podvolumerestores -n velero -o wide` | PVR progress with bytes |

---

## Step 0: Pause ArgoCD (if needed)

ArgoCD self-heal will revert manual changes (pod deletions, deployment modifications). You must pause it during restore operations.

**Option A — Pause specific apps** (preferred):
```bash
kubectl patch application <app-name> -n argocd --type merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
```

**Option B — Scale controller to 0** (stops ALL syncing across ALL clusters):
```bash
kubectl scale statefulset argocd-application-controller -n argocd --replicas=0
```

**IMPORTANT**: If using Option B, remember to scale back to 1 when done:
```bash
kubectl scale statefulset argocd-application-controller -n argocd --replicas=1
```

---

## Step 1: Identify the Backup

```bash
# List recent backups
kubectl get backups -n velero --sort-by=.metadata.creationTimestamp | tail -10

# Check which PVBs exist in a backup (shows pod, volume, size)
kubectl get podvolumebackups -n velero -l velero.io/backup-name=daily-backup-YYYYMMDD \
  -o jsonpath='{range .items[*]}{.spec.pod.namespace}{" "}{.spec.pod.name}{" "}{.spec.volume}{" "}{.status.progress.totalBytes}{"\n"}{end}'
```

Choose the most recent backup BEFORE the data loss event.

---

## Step 2: Prepare for Restore

Velero Kopia file-level restore requires:
1. **Pods included** — Velero injects a `restore-wait` init container to hold the pod while data is restored
2. **PVCs included** — Velero matches PVBs to PVCs
3. **PVs included** — Required for the PVC-PV binding
4. **Deployments deleted** — Velero must create pods from scratch (can't inject init containers into existing pods)

### Delete target deployments

```bash
# For bulk restore (all apps in a namespace):
kubectl delete deployments -n apps --all
kubectl delete deployments -n media --all

# For targeted restore (specific apps):
kubectl delete deployment <app-name> -n <namespace>
```

### Clean up stale resources

```bash
# Delete stale PodVolumeRestores from previous attempts
kubectl delete podvolumerestores -n velero --all

# Delete stale VolumeAttachments (RWO volumes from deleted pods)
kubectl get volumeattachments | grep <pv-name>
kubectl delete volumeattachment <name> --force --grace-period=0
```

---

## Step 3: Create the Restore

### Bulk Restore (all apps)

```yaml
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: bulk-restore
  namespace: velero
spec:
  backupName: daily-backup-YYYYMMDDHHMMSS
  includedNamespaces:
    - apps
    - media
  includedResources:
    - deployments
    - replicasets
    - pods
    - persistentvolumeclaims
    - persistentvolumes
  existingResourcePolicy: update
```

### Targeted Restore (specific app)

```yaml
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: restore-<app-name>
  namespace: velero
spec:
  backupName: daily-backup-YYYYMMDDHHMMSS
  includedNamespaces:
    - <namespace>
  includedResources:
    - deployments
    - replicasets
    - pods
    - persistentvolumeclaims
    - persistentvolumes
  labelSelector:
    matchLabels:
      app: <app-name>
  existingResourcePolicy: update
```

Apply: `kubectl apply -f restore.yaml`

---

## Step 4: Monitor Progress

```bash
# Watch restore phase
kubectl get restore <restore-name> -n velero -w

# Watch PVR progress (bytes restored)
watch 'kubectl get podvolumerestores -n velero -o wide'

# Check pod status (should show Init:0/1 during restore, then Running)
kubectl get pods -n <namespace> -l app=<app-name> -o wide
```

**Expected flow**:
1. Restore creates pods with `restore-wait` init container
2. PVRs created — node-agents start Kopia restore
3. PVR completes — init container exits, main container starts
4. Pod becomes 1/1 Running

---

## Step 5: Re-enable ArgoCD

```bash
# If you used Option B (scaled to 0):
kubectl scale statefulset argocd-application-controller -n argocd --replicas=1

# Verify sync
kubectl get applications -n argocd --no-headers | awk '{print $1, $2, $3}' | grep -v "Synced.*Healthy"
```

ArgoCD will recreate pods from the git spec (which may differ from the backup spec). This is fine — the data is on the PVC, not in the pod spec. Old Velero-restored pods will be replaced by ArgoCD's pods via rolling update.

**If rolling update deadlocks** (Multi-Attach error on RWO volumes):
```bash
# Delete the OLD pod to free the volume for the new pod
kubectl delete pod <old-velero-pod> -n <namespace> --force --grace-period=0
```

---

## Troubleshooting

### PVR stuck with empty progress / `<none>` phase

**Cause**: Stale PVRs from previous restore attempts blocking node-agent processing.

**Fix**:
```bash
kubectl delete podvolumerestores -n velero --all
kubectl rollout restart deployment/velero -n velero
```

### PVR references deleted pod (orphaned PVR)

**Cause**: Pod was deleted during restore. PVR references the specific pod UID and can't find the replacement pod.

**Fix**: Create a new restore — the old PVR is unrecoverable.

### Pod scheduled on broken CSI node

**Cause**: Worker node has stale NVMe-oF transport state. `AttachVolume.Attach failed: transport error`.

**Fix**:
```bash
# Option A: Cordon the node and delete the pod
kubectl cordon <node>
kubectl delete pod <pod> -n <namespace> --force --grace-period=0
# ... wait for pod to reschedule, then uncordon
kubectl uncordon <node>

# Option B: Fix the CSI (restarts io-engine + csi-node DaemonSet pods)
kubectl delete pod <io-engine-pod> -n mayastor     # DaemonSet recreates
kubectl delete pod <csi-node-pod> -n mayastor       # DaemonSet recreates
```

### PVC stuck in Pending (WaitForFirstConsumer)

**Cause**: Pod uses `nodeName` which bypasses scheduler — PVC never gets `selected-node` annotation.

**Fix**:
```bash
kubectl annotate pvc <pvc-name> -n <namespace> volume.kubernetes.io/selected-node=<node-name>
```

### PVC stuck in Terminating

**Cause**: `kubernetes.io/pvc-protection` finalizer blocks deletion while pod still references it.

**Fix**:
```bash
kubectl patch pvc <pvc-name> -n <namespace> -p '{"metadata":{"finalizers":null}}' --type=merge
```

### Velero controller restart marks InProgress restore as Failed

**Cause**: Known behavior — Velero marks InProgress restores as Failed on startup.

**Fix**: Don't restart Velero during a restore. If already restarted, create a new restore.

### Stale backup helper pods consuming node-agent concurrency

**Cause**: Old backup pods stuck in Running state for days.

**Fix**:
```bash
kubectl get pods -n velero | grep "backup.*Running" | grep -v node-agent | grep -v velero-
kubectl delete pod <stale-backup-pods> -n velero --force --grace-period=0
```

### Multi-Attach error (RWO volume)

**Cause**: Volume still attached to old/deleted pod.

**Fix**:
```bash
# Find the stale VolumeAttachment
kubectl get volumeattachments | grep <pv-name>

# Delete it
kubectl delete volumeattachment <va-name> --force --grace-period=0
```

---

## Key Rules

1. **Always include pods + PVCs + PVs** in `includedResources` — missing any one causes 0 PVRs
2. **Delete deployments before restore** — Velero needs to create pods from scratch to inject init containers
3. **Use `existingResourcePolicy: update`** for existing resources
4. **Clean up stale PVRs** before each new restore attempt
5. **Don't restart Velero during a restore** — it marks InProgress as Failed
6. **ArgoCD will drift** — Velero-restored pod specs differ from git. Let ArgoCD reconcile after restore.
7. **RWO volumes**: Delete stale VolumeAttachments before new pods can mount
