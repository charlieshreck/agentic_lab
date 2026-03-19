# ArgoCD OutOfSync: PersistentVolumeClaim Immutability Conflict

**Incident**: #522 (ArgoCDAppOutOfSync - pulse project monitoring)
**Date**: 2026-03-19
**Status**: RESOLVED
**Root Cause**: PVC immutability constraint + submodule pointer drift

## Problem

ArgoCD application `pulse` remained **OutOfSync** for >15 minutes despite being **Healthy** in Kubernetes.

**Root Cause**:
1. On 2026-03-19 02:22 UTC, someone attempted to change pulse's PVC storage class from `mayastor-single-replica` → `local-path`
2. Kubernetes rejected this (PVCs are immutable after binding)
3. The change was reverted at 02:24 UTC back to `mayastor-single-replica`
4. **BUT** the parent repo's submodule pointer was never updated to the revert commit
5. ArgoCD saw git: `local-path` (stale pointer) vs Kubernetes: `mayastor-single-replica` (immutable, unchanged)
6. The immutable PVC spec prevented any sync operation from succeeding

## Impact

- ArgoCD application stuck OutOfSync (but pod remained Healthy due to immutable binding)
- No service degradation (PVC already correctly bound)
- Pure GitOps drift issue, not a runtime failure

## Resolution

Updated the parent repo's submodule pointer to the correct commit:

```bash
git -C /home add monit_homelab
git -C /home commit -m "chore: update monit_homelab submodule (fix pulse PVC immutability conflict)"
git -C /home push origin main
```

**Commits involved**:
- Parent repo: `e01e1a7` (updated pointer)
- monit_homelab: `5778337` (reverted, correct config with mayastor-single-replica)

## Key Learning: PVC Immutability

Kubernetes **permanently locks** PVC specs at binding time. Once a PVC is bound:
- ✅ Can modify: `resources.requests` (storage size), `volumeAttributesClassName`
- ❌ Cannot modify: `storageClassName`, `accessModes`, `volumeMode`, etc.

**Implication**: If a PVC is created with the wrong storage class, the only fix is to:
1. Delete the PVC (which deletes the data)
2. Recreate it with correct config

Changing storage classes after binding is impossible.

## Prevention

1. **GitOps discipline**: Always update parent repo after submodule changes
2. **Immutability awareness**: Test PVC storage class selection carefully before first deployment
3. **Test rollback procedures**: Verify that git reverts actually update the parent pointer
4. **ArgoCD health vs sync**: "Healthy" ≠ "Synced" — monitor both independently

## References

- Kubernetes PersistentVolumeClaim API: https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolumeclaim
- ArgoCD sync process: https://argocd-docs.readthedocs.io/en/stable/
