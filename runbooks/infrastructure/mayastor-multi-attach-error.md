# Mayastor Multi-Attach Error (Pod Stuck Pending)

## Symptoms

- Pod stuck in `Pending` state with `ContainerCreating` reason
- Warning event: `Multi-Attach error for volume "pvc-XXXX" Volume is already exclusively attached to one node and can't be attached to another`
- Pod was rescheduled to a different node (e.g., after ArgoCD rolling update or node eviction)
- `kubectl get volumeattachment` shows the PVC attached to a different node than the pod's target node

## Root Cause

Mayastor uses ReadWriteOnce (RWO) volumes. When a pod moves from one node to another (due to rolling update, node eviction, or manual rescheduling), the Kubernetes VolumeAttachment object for the old node may not be released.

The CSI controller detects the conflict and reports a Multi-Attach error — it cannot publish the volume to two nodes simultaneously.

**Common trigger**: ArgoCD rolling update changes the deployment (e.g., image update via Renovate), scheduler picks a new node for the replacement pod, but the old VolumeAttachment from the previous node persists.

## Diagnosis

```bash
# 1. Identify the affected PVC name from pod description
kubectl --context admin@homelab-prod describe pod <pod-name> -n <namespace>
# Look for: "Multi-Attach error for volume pvc-XXXXX"

# 2. Find which node the volume is attached to vs. where the pod is scheduled
kubectl --context admin@homelab-prod get pod <pod-name> -n <namespace> -o wide
# Note: NODE column shows where the pod is scheduled

# 3. Find the stale VolumeAttachment
kubectl --context admin@homelab-prod get volumeattachment -o wide | grep <pvc-volume-name>
# Look for the attachment on the OLD node (not the pod's target node)
```

## Fix

Delete the stale VolumeAttachment object. Kubernetes/CSI will immediately re-process the attachment and publish the volume to the correct node.

```bash
# Find VolumeAttachment name for the stale attachment
VA_NAME=$(kubectl --context admin@homelab-prod get volumeattachment -o json | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
pvc_id = 'PASTE-PVC-VOLUME-ID-HERE'  # e.g. pvc-40b33f89-d2f2-423a-a774-293b9a96cfec
for item in data['items']:
    if item['spec']['source']['persistentVolumeName'] == pvc_id:
        node = item['spec']['nodeName']
        name = item['metadata']['name']
        print(f'{name} (node: {node})')
")

# Delete the stale attachment
kubectl --context admin@homelab-prod delete volumeattachment <VA-NAME>
```

The pod should move to `ContainerCreating` within a few seconds and then `Running` within ~30 seconds.

## Verification

```bash
kubectl --context admin@homelab-prod get pods -n <namespace> -l app=<app-name>
# Should show: 1/1 Running
```

## Notes

- This is safe to do even if you're not sure which attachment is stale — Kubernetes will re-create the correct attachment automatically
- Mayastor 3-replica volumes have their nexus (primary path) published to one node at a time; deleting the attachment forces a re-publish to the correct node
- If multiple pods are affected (e.g., batch rolling update), you can delete multiple VolumeAttachments in one command
- This issue commonly occurs after Renovate triggers ArgoCD syncs with image updates, especially if the new pods land on different nodes than before

## Related

- `mayastor-node-saturation.md` — if Mayastor io-engine is consuming high CPU after reattachment
- ArgoCD rolling updates can trigger this whenever pods change nodes
