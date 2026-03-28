---
title: PersistentVolumeClaim Immutability Constraints
domain: infrastructure
severity: medium
status: published
created: 2026-03-25
updated: 2026-03-25
---

## Problem

Kubernetes PersistentVolumeClaims have immutable spec fields after creation. Attempting to modify certain fields (like `storageClassName`) on a bound PVC results in an error:

```
PersistentVolumeClaim 'X' is invalid: spec: Forbidden: spec is immutable after creation
except resources.requests and volumeAttributesClassName for bound claims
```

This can cause ArgoCD to report an application as `OutOfSync` if the manifest tries to change an immutable PVC spec field.

## Root Cause Analysis

When a PVC is first created, it is bound to a PersistentVolume (PV). Once bound, Kubernetes restricts modifications to protect data integrity. Only these fields can be modified on a bound PVC:
- `spec.resources.requests` (storage size increase)
- `spec.volumeAttributesClassName` (in newer Kubernetes versions)

Attempting to change `storageClassName`, `accessModes`, or other spec fields will fail with the immutability error.

## Solution

### Option 1: Prevent the Issue (Recommended)
Design manifests correctly from the start:
- Set the correct `storageClassName` when first creating the PVC
- Use explicit storage classes aligned with your infrastructure (e.g., `local-path`, `mayastor-single-replica`)
- Document storage class choices in comments

### Option 2: Resolve Existing Conflicts
If ArgoCD reports OutOfSync due to PVC immutability violations:

1. **Identify the conflict**: Check ArgoCD operationState or `kubectl diff` to see which field changed
2. **Delete and recreate**: If safe (stateless workloads), delete the PVC and let ArgoCD recreate it
   ```bash
   kubectl delete pvc <name> -n <namespace>
   kubectl apply -f <manifest>  # or let ArgoCD sync
   ```
3. **Accept immutability**: If data is critical, revert the manifest change to match the existing PVC spec
4. **Storage class migration**: For production workloads requiring storage class changes, use:
   - Manual migration (create new PVC with correct class, migrate data)
   - Storage migration tools (depends on provider)

## Case Study: Gatus Monitoring (Incident #224)

**Situation**: Gatus ConfigMap was being updated, and someone attempted to change the PVC `storageClassName` from `local-path` to `mayastor-single-replica` (for MayaStor provisioning).

**Error**:
- Manifest applied to git repository with new storageClassName
- ArgoCD detected mismatch and reported OutOfSync
- Kubernetes rejected the change (immutable field)
- Application remained stuck in OutOfSync state

**Resolution**:
- Recognized that Gatus is stateless (no persistent data required)
- Reverted the manifest back to `storageClassName: local-path`
- Committed fix (307765d): "fix: gatus PVC storageClassName immutable constraint - revert to local-path"
- ArgoCD synced successfully with commit 307765d
- PVC immutability constraint respected; Application reported Synced

**Key Learning**:
For stateless monitoring applications, storage class choice doesn't affect functionality. Respect immutability constraints rather than trying to force updates. If storage migration is truly needed, plan it explicitly rather than attempting in-place modifications.

## Prevention Checklist

- [ ] Set `storageClassName` at PVC creation time (don't change it later)
- [ ] Document why specific storage classes were chosen (in CLAUDE.md or comments)
- [ ] For applications that don't need persistent data, use `emptyDir` instead of PVC
- [ ] For stateless apps with PVCs, remember that changing storageClassName is not safe
- [ ] In ArgoCD, consider adding PVC to `ignoreDifferences` if spec matches intent but live cluster has different class

## References

- Kubernetes: [PersistentVolumeClaims documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- ArgoCD: [Difference customization](https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/#ignore-differences)

## Runbook Metadata

- **Applicable clusters**: All (prod, agentic, monit)
- **Time to resolve**: 5 minutes (once root cause identified)
- **Manual intervention required**: Possible deletion + recreation of PVC
- **Data loss risk**: Medium (depends on whether workload is stateless)
