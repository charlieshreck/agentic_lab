# Mayastor Upgrade Procedure

**Risk Level**: HIGH — Mayastor upgrades can wipe the etcd metadata store, orphaning ALL persistent volumes.

**Last incident**: 2026-03-13 — Mayastor 2.8.0 → 2.10.0 wiped etcd, lost all 21 PVs, 5+ hour recovery. See `/home/prod_homelab/docs/LESSONS-LEARNED-MAYASTOR-TRAEFIK-UPGRADE.md`.

---

## Pre-Upgrade Checklist

### 1. Read Release Notes
```bash
# Check for breaking changes, migration hooks, etcd changes
# https://github.com/openebs/mayastor-extensions/releases
```

Key things to look for:
- etcd schema changes or migration hooks
- Helm hook changes (pre-upgrade, post-upgrade)
- CSI driver changes
- Storage class changes

### 2. Verify Backups

```bash
# Check most recent backup
kubectl get backups -n velero --sort-by=.metadata.creationTimestamp | tail -3

# Verify PVBs exist for all apps
kubectl get podvolumebackups -n velero -l velero.io/backup-name=<latest-backup> \
  -o jsonpath='{range .items[*]}{.spec.pod.namespace}/{.spec.pod.name} {.status.progress.totalBytes}B{"\n"}{end}'

# Trigger a manual backup if the latest is > 24h old
kubectl apply -f - <<EOF
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: pre-mayastor-upgrade-$(date +%Y%m%d)
  namespace: velero
spec:
  storageLocation: garage
  includedNamespaces: ["*"]
  excludedNamespaces: ["kube-system", "mayastor"]
  defaultVolumesToFsBackup: true
  ttl: 720h
EOF
```

### 3. Snapshot Mayastor etcd

```bash
# Get etcd pod
kubectl get pods -n mayastor -l app=etcd

# Create etcd snapshot
kubectl exec -n mayastor mayastor-etcd-0 -- etcdctl snapshot save /tmp/etcd-pre-upgrade.db

# Copy snapshot locally
kubectl cp mayastor/mayastor-etcd-0:/tmp/etcd-pre-upgrade.db ./etcd-pre-upgrade.db
```

### 4. Document Current State

```bash
# Record current disk pools
kubectl get diskpool -n mayastor -o yaml > diskpools-backup.yaml

# Record current volumes
kubectl get pv -o yaml > pv-backup.yaml

# Record PVC bindings
kubectl get pvc -A -o yaml > pvc-backup.yaml
```

---

## Upgrade Procedure

### NEVER DO

- **NEVER add `SkipHooks=true`** to the ArgoCD sync options without understanding what each hook does
- **NEVER force-sync** with `Replace=true` on StatefulSets (especially etcd)
- **NEVER delete the etcd StatefulSet** manually

### Step 1: Review the ArgoCD Application

```bash
# Check current Mayastor app config
kubectl get application mayastor-operator -n argocd -o yaml | grep -A 5 targetRevision
```

File: `/home/prod_homelab/kubernetes/argocd-apps/platform/mayastor-app.yaml`

### Step 2: Update Version in Git

Edit `mayastor-app.yaml`, change `targetRevision` to new version. **Do NOT change syncOptions**.

### Step 3: Check Helm Hook Compatibility

```bash
# Before pushing, check what hooks the new chart has
helm template mayastor openebs/mayastor --version <new-version> | grep -B5 "helm.sh/hook"
```

If pre-upgrade hooks exist:
- Check if they can schedule (anti-affinity requirements, resource limits)
- If hooks can't schedule, **fix the scheduling issue** — do NOT skip hooks

### Step 4: Push and Monitor

```bash
git -C /home/prod_homelab add kubernetes/argocd-apps/platform/mayastor-app.yaml
git -C /home/prod_homelab commit -m "chore: upgrade mayastor to <version>"
git -C /home/prod_homelab push origin main
```

Monitor ArgoCD sync:
```bash
# Watch the sync
kubectl get application mayastor-operator -n argocd -w

# Watch Mayastor pods
watch 'kubectl get pods -n mayastor'

# Watch etcd specifically
kubectl logs -f -n mayastor mayastor-etcd-0

# Watch disk pools (should stay Online)
watch 'kubectl get diskpool -n mayastor'
```

### Step 5: Post-Upgrade Verification

```bash
# All Mayastor pods running
kubectl get pods -n mayastor

# Disk pools online
kubectl get diskpool -n mayastor

# All PVCs still bound
kubectl get pvc -n apps
kubectl get pvc -n media

# All app pods running
kubectl get pods -n apps --no-headers | grep -v "1/1"
kubectl get pods -n media --no-headers | grep -v "1/1"

# Test a volume write (create temp pod with PVC on each worker)
# See velero-restore-procedure.md for the CSI test pattern
```

---

## Rollback

If upgrade fails and data is intact:
1. Revert the version in git
2. Push and let ArgoCD sync
3. Monitor etcd and disk pools

If upgrade fails and data is lost:
1. Follow the Velero restore procedure: `velero-restore-procedure.md`
2. Scale ArgoCD to 0 first
3. Restore from the pre-upgrade backup

---

## Current Configuration

| Setting | Value | Why |
|---------|-------|-----|
| `SkipHooks=true` | YES (in mayastor-app.yaml) | etcd pre-upgrade hook can't schedule on 3-node cluster |
| `ignoreDifferences` on etcd StatefulSet | `/spec/template` | Helm render vs live state drift |
| `ignoreDifferences` on etcd JWT secret | `/data` | Auto-generated on each Helm release |

**WARNING**: The `SkipHooks=true` is a known risk. The etcd pre-upgrade hook exists to migrate data safely between versions. Skipping it means etcd data migration must happen automatically or not at all. Any version that requires an explicit data migration **will break** with this setting.

**TODO**: Fix the anti-affinity scheduling issue so hooks can run, then remove `SkipHooks=true`.
