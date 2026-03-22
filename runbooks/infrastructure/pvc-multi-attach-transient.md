# PersistentVolume Multi-Attach Errors (Transient)

## Alert Pattern
- **Alert**: `HomelabDeploymentUnavailable` or `KubePodCrashLooping`
- **Root cause**: Multi-Attach error during pod rollout
- **Severity**: Warning (transient, self-resolving)
- **Duration**: 5-15 minutes (resolves when old pod fully terminates)

## What Happens
During a deployment rollout (image update, config change), Kubernetes:
1. Creates a new pod to use the PersistentVolumeClaim (PVC)
2. Old pod is still terminating and holding a lock on the PVC
3. Kubernetes detects PVC is attached to multiple nodes simultaneously
4. Temporary "Multi-Attach error" appears in pod events

This is **expected behavior** and resolves automatically when the old pod fully terminates.

## Diagnosis

### Step 1: Verify Current State
```bash
kubectl -n <namespace> get deployment <name>
kubectl -n <namespace> get pods -o wide | grep <deployment>
kubectl -n <namespace> describe pod <pod-name> | grep -A5 Events
```

Check for:
- New pod is `Running` and ready? → **Self-healed**, auto-resolve
- Old pod still exists and terminating? → Wait 1-2 minutes, recheck
- Repeated Multi-Attach errors after 15+ minutes? → **Investigate deeper**

### Step 2: Check What Triggered the Rollout
```bash
git -C /home/<cluster> log --oneline -n 10 -- kubernetes/applications/*/deployment.yaml
git -C /home/<cluster> show <commit> | grep -A5 image
```

Look for:
- Image version change (Update Patrol automation)
- ConfigMap/Secret update
- Resource limit change

If it's an **image version update** from Update Patrol, this is **expected behavior**. Auto-resolve.

### Step 3: Verify PVC Status (If Still Failing)
```bash
kubectl -n <namespace> get pvc
kubectl -n <namespace> describe pvc <pvc-name> | grep -A10 Events
```

Look for:
- PVC is `Bound` → Normal, pod should start
- PVC stuck in `Pending` → Storage issue, needs investigation

## Auto-Resolve Criteria
✅ **Auto-resolve if ALL of these are true:**
1. Current pod is `Running` and `Ready`
2. Deployment has desired replicas available
3. Multi-Attach error was > 2 minutes ago and has not recurred
4. No other issues in pod events (OOM, ImagePullBackOff, etc.)
5. Rollout was triggered by Update Patrol (image version change)

## Manual Investigation Required If
❌ **Escalate if ANY of these are true:**
1. Multi-Attach error persists > 15 minutes
2. Pod enters `CrashLoopBackOff` after rollout
3. PVC stuck in `Pending` or `Failed` state
4. Rollout was NOT triggered by an image change (config change may have side effects)
5. Multiple pods failing simultaneously with multi-attach

## Example Resolution
**Incident #563 - filebrowser deployment:**
- Rollout triggered by Update Patrol (1.2.2 → 1.2.3)
- Multi-Attach error: 2026-03-22 03:05:23Z to 03:18:02Z (13 min)
- Pod healthy at 03:18:08Z, running cleanly
- Resolved: Auto-healed during normal termination of old pod
- Action: None required, expected transient behavior

## References
- [Kubernetes PVC Multi-Attach Issues](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes)
- [Update Patrol](../../../scripts/update-patrol/README.md) — nightly image version automation
