# Mayastor Stale VolumeAttachment

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubePodNotReady / HomelabPodStuckPending |
| **Severity** | Critical |
| **Symptom** | Pod stuck in `Pending` or `ContainerCreating` with `Multi-Attach error` |
| **Source** | kube-state-metrics / error-hunter |
| **Clusters Affected** | prod (only cluster using Mayastor) |

## Description

Mayastor RWO (ReadWriteOnce) volumes can retain stale VolumeAttachment references when pods are rescheduled to different nodes. The Kubernetes attach-detach controller blocks the new attachment because it believes the volume is still exclusively attached to the old node.

This results in pods stuck in `ContainerCreating` with the event:
```
Warning  FailedAttachVolume  attachdetach-controller  Multi-Attach error for volume "pvc-xxx" Volume is already exclusively attached to one node and can't be attached to another
```

## Root Cause

When a Mayastor-backed pod moves between nodes (e.g., node eviction, rolling update, pod deletion), the following can happen:

1. Pod is deleted from node A
2. VolumeAttachment for node A should be cleaned up by the CSI driver
3. **Bug**: The CSI driver fails to clean up, OR the kubelet on node A retains stale `volumesAttached` in its node status
4. New pod is scheduled to node B
5. Attach-detach controller sees volume "still attached" to node A → blocks attachment to node B
6. Pod remains in `ContainerCreating` indefinitely

## Quick Diagnosis

### 1. Identify the stuck pod and its PVC

```bash
# MCP tools
kubectl_get_pods(namespace="<ns>", cluster="prod")
kubectl_describe(resource_type="pod", name="<pod>", namespace="<ns>", cluster="prod")
# Look for: "Multi-Attach error for volume" in Events
```

### 2. Find the PVC and PV

```bash
kubectl get pvc -n <namespace> <pvc-name> -o wide
# Note the VOLUME name (pvc-xxx-xxx-xxx)
```

### 3. Find stale VolumeAttachments

```bash
kubectl get volumeattachments -o custom-columns='NAME:.metadata.name,PV:.spec.source.persistentVolumeName,NODE:.spec.nodeName,ATTACHED:.status.attached,AGE:.metadata.creationTimestamp' | grep <pv-name>
```

### 4. Check node status for orphaned references

```bash
kubectl get node <stale-node> -o json | python3 -c "
import json, sys
node = json.load(sys.stdin)
for v in node.get('status', {}).get('volumesAttached', []):
    if '<pv-uuid>' in v.get('name', ''):
        print(f'STALE: {v}')
"
```

## Remediation

### Tier 1: Delete Stale VolumeAttachment (auto-remediated by error-hunter)

```bash
kubectl delete volumeattachment <stale-attachment-name>
```

Wait 30 seconds. If the pod transitions to `Running`, the fix is complete.

### Tier 2: Clear Orphaned Node Status

If Tier 1 doesn't work (VolumeAttachment already gone but node status is stale):

```bash
# Check Mayastor volume publish state
# Port-forward to Mayastor API REST
kubectl port-forward -n mayastor svc/mayastor-api-rest 18081:8081
curl -X DELETE "http://localhost:18081/v0/volumes/<volume-uuid>/target"
```

If Mayastor says "VolumeNotPublished", the stale state is in the kubelet. Fix:

```bash
# Restart kubelet on the stale node (Talos only)
TALOSCONFIG=/home/prod_homelab/infrastructure/terraform/talos-cluster/generated/talosconfig
talosctl -n <stale-node-ip> service kubelet restart
```

Then delete the stuck pod to force fresh scheduling:

```bash
kubectl delete pod -n <namespace> <pod-name>
```

### Tier 3: Escalate

If kubelet restart doesn't clear the stale reference:
1. Check for CSI staging artifacts on the node
2. Consider draining the stale node
3. As last resort, restart the node via `talosctl reboot`

## Verification

```bash
# Pod should be Running and Ready
kubectl get pod -n <namespace> <pod-name>

# No stale VolumeAttachments for the PV
kubectl get volumeattachments | grep <pv-name>

# Node status should not reference the volume
kubectl get node <old-node> -o json | jq '.status.volumesAttached[] | select(.name | contains("<pv-uuid>"))'
```

## Prevention

1. Keep Mayastor components updated (io-engine, csi-node, agent-core)
2. Monitor VolumeAttachment age vs pod age — stale attachments indicate drift
3. Error-hunter auto-remediates Tier 1 (stale attachment deletion) automatically

## Historical Incidents

### March 2026 — TasmoAdmin v5.0.0 Upgrade
- **Affected**: TasmoAdmin pod stuck Pending after image upgrade
- **Cause**: Stale VolumeAttachment to worker-03 from 14 days prior
- **Fix**: Deleted stale VolumeAttachment → pod recovered immediately

### March 2026 — Karakeep + Cleanuparr Down 6+ Hours
- **Affected**: Both pods stuck ContainerCreating
- **Cause**: Stale VolumeAttachments to worker-03 (from Feb 26 and Feb 28)
- **Karakeep**: Fixed by deleting stale VolumeAttachment
- **Cleanuparr**: Required kubelet restart on worker-03 (orphaned node status with no backing artifacts)
- **Root cause of delay**: Error-hunter classified as warning, remediator skipped Pending pods

## Related Alerts

- `KubePodNotReady` — Fires for any non-ready pod after 15 minutes
- `HomelabPodStuckPending` — Custom critical alert for Pending pods (added March 2026)
- `HomelabDeploymentUnavailable` — Fires when deployment has 0 replicas

## Related Runbooks

- `runbooks/alerts/kube-pod-not-ready.md` — General pod troubleshooting
- `runbooks/alerts/deployment-unavailable.md` — Deployment zero replicas
