# Incident #523: ArgoCD OutOfSync - Pulse Storage Class Mismatch

**Incident ID**: #523
**Date**: 2026-03-19
**Status**: RESOLVED
**Root Cause**: PVC storageClassName mismatch between cluster state and git manifest
**Time to Resolution**: ~30 minutes from investigation to verification

---

## Problem Statement

ArgoCD application `pulse` on the monitoring cluster (monit) remained **OutOfSync** with git, despite the deployment being **Healthy** and running. The application manifests in git specified a storage class that was incompatible with the actual PersistentVolumeClaim bound in the cluster.

---

## Root Cause Analysis

### The Mismatch

The pulse application's PersistentVolumeClaim had a conflict:

| Component | Storage Class | Notes |
|-----------|---------------|-------|
| **Actual PVC in cluster** | `local-path` | Immutably bound to this storage class |
| **Git manifest** | `mayastor-single-replica` | Specified in deployment.yaml |

### Why This Happened

1. **2026-03-19 02:00 UTC**: Someone attempted to fix a previous issue by changing the PVC storage class from `mayastor-single-replica` → `local-path`
2. **2026-03-19 02:22 UTC**: The change was reverted back to `mayastor-single-replica` (likely due to perceived breaking changes)
3. **Result**: The git manifest reverted to `mayastor-single-replica`, but the cluster's PVC remained immutably bound to `local-path`
4. **Consequence**: ArgoCD saw a mismatch — git said one thing, the cluster had another (immutable) state

### Why This Is a Problem

Kubernetes PersistentVolumeClaim specs are **immutable after binding**. Once a PVC is created and bound to actual storage:
- ✅ Modifiable: `resources.requests` (storage size), `volumeAttributesClassName`
- ❌ Immutable: `storageClassName`, `accessModes`, `volumeMode`, and all other spec fields

This immutability is by design — it prevents accidental data loss. But it means if you need to change the storage class, the only way is to:
1. Delete the PVC (which deletes the data)
2. Recreate it with the correct config

### The Real Root Cause

**The monit cluster is a single-node Talos cluster with only local-path storage available.** It does not have:
- Mayastor storage class (that's on prod/agentic clusters with Taranaki/Taupo pools)
- Any external storage backend
- Only local SSD storage on the Talos VM

Therefore, the PVC **must** use `local-path` on the monit cluster. There is no other option.

---

## Resolution

### Fix Applied

Updated `/home/monit_homelab/kubernetes/platform/pulse/deployment.yaml` to match cluster reality:

```yaml
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pulse-data
  namespace: monitoring
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path  # ← Corrected from mayastor-single-replica
  resources:
    requests:
      storage: 5Gi
```

### Commits

```
commit c92fbc76e1adee50b6ff7fe4c15dbcbe120cbbb0
Author: Claude Code
Date:   2026-03-19 14:35:00 UTC

    fix: use local-path storage for pulse PVC on monit cluster

    Root cause: Monitoring cluster is single-node Talos with only
    local-path storage available. Mayastor is not deployed.

    PVC was immutably bound to local-path in the cluster, but git
    manifest specified mayastor-single-replica, causing OutOfSync.

    Updated manifest to match actual cluster capabilities.
```

### Verification

```
✅ Sync Status: SYNCED (was OutOfSync)
✅ Health Status: Healthy
✅ Revision: c92fbc76 (correct commit)
✅ Pod: pulse-c65845d76-qmt2c is Running
✅ Replica: 1/1 Ready
```

---

## Prevention

### For Future Pulse Deployments

1. **Document cluster storage capabilities**:
   - Prod/Agentic: Use `mayastor-single-replica` (Taranaki/Taupo available)
   - Monit: Use `local-path` (single-node only)
   - Always verify available storage classes before PVC creation

2. **PVC initialization strategy**:
   - Create PVCs with the **correct** storage class from day 1
   - Test storage class selection in a staging environment
   - Never iterate on PVC storage class — it's immutable

3. **Cluster documentation**:
   - Update CLAUDE.md for each cluster with available storage classes
   - Include storage architecture in cluster bootstrap runbooks

### For ArgoCD Drift Detection

1. **Monitor both Sync AND Health status**:
   - "Healthy" ≠ "Synced" — pod can be running while git is out of sync
   - Set up alerts for `OutOfSync` status regardless of health

2. **Immutability awareness in code review**:
   - Flag storage class changes in PVC specs
   - Require data deletion/migration planning for storage class changes
   - Use ArgoCD pruning policy to prevent orphaned resources

---

## Key Learnings

### PVC Immutability Is Intentional

Kubernetes locks PVC specs at binding time to prevent accidental data loss. This is correct behavior. The lesson: **get the storage class right the first time**.

### Cluster-Specific Configurations Matter

Different clusters have different storage backends:
- **Prod**: Taranaki RAIDZ2 (mayastor available)
- **Agentic**: Taupo RAIDZ2 (mayastor available)
- **Monit**: Single-node SSD only (local-path only)

Manifests must account for these differences. Use:
- Cluster-specific overlays in Kustomize
- Storage class abstractions in Helm values
- Documentation in CLAUDE.md per cluster

### GitOps + Immutable Infrastructure

When git and reality diverge (due to immutability), the resolution is to:
1. Accept cluster reality as the source of truth (PVC binding is immutable)
2. Update git to match (change manifest to use correct storage class)
3. Let ArgoCD sync to make them consistent again

---

## References

- Kubernetes PersistentVolumeClaim: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- ArgoCD OutOfSync Status: https://argocd-docs.readthedocs.io/
- Monitoring Cluster Docs: `/home/monit_homelab/CLAUDE.md`
- Storage Architecture: `/home/agentic_lab/docs/storage-architecture.md`
