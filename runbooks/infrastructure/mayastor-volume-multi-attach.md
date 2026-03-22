---
title: "Mayastor Volume Multi-Attach Error (ReadWriteOnce PVC)"
description: "Resolve pod pending state when Mayastor volume has stale attachment from previous node"
domain: "infrastructure"
alert_names:
  - "HomelabDeploymentUnavailable"
  - "PodPending"
---

## Problem

Pod stays in `PodInitializing` state with error:

```
FailedAttachVolume: Multi-Attach error for volume "pvc-..." Volume is already exclusively attached to one node and can't be attached to another
```

This occurs when a ReadWriteOnce (RWO) PVC is being reused by a pod on a different node, but the Mayastor CSI driver still has an active volumeattachment from the old pod.

## Root Cause

Mayastor (OpenEBS) enforces exclusive attachment for RWO volumes. When a pod is rescheduled to a different node:

1. Old pod/node is cleaned up
2. New pod is scheduled to a new node
3. kubelet attempts to attach the PVC to the new node
4. Mayastor CSI controller blocks the attachment because a volumeattachment resource still exists for the old node

The stale volumeattachment prevents the PVC from being reattached even though the old pod is gone.

## Solution

### Step 1: Identify the stale volumeattachment

```bash
export KUBECONFIG=/root/.kube/config
kubectl get volumeattachment -o wide | grep <pvc-name>
```

Look for an entry with `ATTACHED=true` but a different NODE than where the pod is trying to run.

### Step 2: Delete the stale volumeattachment

```bash
kubectl delete volumeattachment <attachment-name>
```

### Step 3: Verify recovery

```bash
kubectl get pod -n <namespace> -l app=<app> -o wide
```

Pod should transition to Running within 5-10 seconds.

## Prevention

- Use RWX (ReadWriteMany) storage classes when pods may be rescheduled across nodes
- Ensure pod disruption budgets or topology spread constraints keep pods stable on current nodes
- Monitor volumeattachment resources for long-lived stale entries
- Use RollingUpdate deployment strategy instead of Recreate when using RWO storage

## Related Issues

- Mayastor volumeattachment leak during node failures
- Deployment with Recreate strategy + RWO storage = high risk of stale attachments
- Velero restore with existing PVCs may create stale attachments

## References

- Mayastor CSI: https://mayastor.io/
- Kubernetes volumeattachment: https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistent-volumes
- OpenEBS documentation: https://docs.openebs.io/

## Incident History

- **2026-03-22**: Filebrowser deployment (#562) - stale attachment on talos-worker-01 blocked new pod on talos-worker-03
