# Pulse Deployment Issues - PVC Lifecycle & Pod Recovery

**Runbook for investigating and resolving Pulse server pod failures due to PersistentVolumeClaim (PVC) lifecycle issues.**

---

## Overview

Pulse is a monitoring aggregation server running in the `monit` cluster (Talos single-node at 10.10.0.30). The Pulse pod frequently experiences temporary Not Ready states during PVC initialization cycles, caused by storage class attachment delays. These are typically self-resolving but can trigger false positive alerts.

---

## Symptoms

- Pod status: `Running` but `Not Ready (0/1 containers ready)` for 30-120 seconds
- Events show: `FailedScheduling` → `Scheduled` → `SuccessfulAttachVolume` → `Ready`
- Readiness probe failures: HTTP GET `/api/health` timing out (initialDelaySeconds: 10, periodSeconds: 10)
- Pulse agents (DaemonSet on prod cluster) may report connection failures during recovery window
- Alert: "Pod not ready" or "Container failed to start"

---

## Root Cause

**Storage Class Resolution Delay:**
The `pulse-data` PVC references `mayastor-single-replica` storage class, which may be slow to mount during cluster recovery or shortly after deployment. The pod is scheduled before the PVC is fully attached, causing:

1. Pod starts but PVC not mounted → readiness probe fails (app can't initialize)
2. PVC attachment completes (typically within 30-120 seconds)
3. Pod's storage becomes available → app initializes → readiness probe succeeds
4. Pod transitions to Ready

**Why It Happens:**
- Monit cluster uses Mayastor for block storage (same as prod)
- Single-node Talos cluster has minimal redundancy
- Pulse pod requires `/data` mount before health check can pass

---

## Quick Diagnosis

### Check Pod Status
```bash
export KUBECONFIG=/home/monit_homelab/kubeconfig
kubectl -n monitoring get pod -l app=pulse -w
# Watch for Ready state change from 0/1 to 1/1
```

### View Events
```bash
kubectl -n monitoring describe pod -l app=pulse
# Look for: FailedScheduling, Scheduled, SuccessfulAttachVolume, Created, Started, Ready
```

### Check PVC Status
```bash
kubectl -n monitoring get pvc pulse-data
# Should show: Bound, size 5Gi, storage class mayastor-single-replica
```

### Tail Logs
```bash
kubectl -n monitoring logs -l app=pulse -f
# Watch for: startup errors, data mount warnings, health check messages
```

---

## Resolution Steps

### If Pod Is Recovering (1-3 minutes since event start)
**No action needed.** The issue is self-resolving. Monitor for:
```bash
# Wait for Ready → 1/1
kubectl -n monitoring get pod -l app=pulse
# Expected: After 30-120 seconds, pod should show READY 1/1
```

### If Pod Stuck in NotReady (> 3 minutes)
1. **Check Mayastor pool status:**
   ```bash
   kubectl -n mayastor get diskpool
   # All pools should show "online", not "degraded" or "offline"
   ```

2. **Check node disks:**
   ```bash
   # From agentic cluster - monit runs on Pihanga (10.10.0.20)
   talosctl -n 10.10.0.30 disks
   # Should show: /dev/vda (Mayastor pool disk)
   ```

3. **Force pod restart (GitOps workflow):**
   - Edit `/home/monit_homelab/kubernetes/platform/pulse/deployment.yaml`
   - Add or update `.spec.template.metadata.annotations.restartedAt` with current timestamp
   - Commit and push (ArgoCD will sync within 3 minutes)
   ```bash
   # Example annotation:
   restartedAt: "2026-03-19T14:30:00Z"
   ```

4. **If PVC remains unbound:**
   - Check storage class exists: `kubectl get storageclass mayastor-single-replica`
   - If missing, ArgoCD will recreate on next sync
   - Verify Mayastor operator is running: `kubectl -n mayastor get deployment`

---

## Prevention

### Configuration Review (Already Implemented)
Git commit `fdac417` fixed:
- Storage class name: `mayastor-single-replica` (correct)
- PVC request: `5Gi` (adequate for monitoring data)
- Webhook rate limit: increased to 60 req/sec (prevents agent disconnects during recovery)

### Monitoring for Recurrence
Alert on:
- Pod NotReady > 2 minutes
- PVC Pending > 1 minute
- Mayastor pool degraded

Current readiness probe settings are appropriate:
- `initialDelaySeconds: 10` (allows app startup)
- `periodSeconds: 10` (responsive to recovery)
- `failureThreshold: 3` (tolerates 30 seconds of transient failures)

---

## Related Components

**Pulse Agent (prod cluster):**
- DaemonSet runs on all prod cluster nodes
- Sends heartbeats to Pulse server (https://pulse.kernow.io)
- Will report connection timeouts if Pulse pod is NotReady
- These are transient and do NOT indicate a problem once Pulse recovers

**ArgoCD Application:**
- App name: `pulse` (monit cluster)
- Namespace: `monitoring`
- Source: `monit_homelab/kubernetes/platform/pulse/`
- Sync policy: automated with pruning enabled
- If deployment manifest changes, ArgoCD will trigger a rolling update

---

## Verification After Recovery

```bash
# Pod is Ready
kubectl -n monitoring get pod -l app=pulse
# Expected: 1/1 Running, Ready

# PVC is Bound
kubectl -n monitoring get pvc pulse-data
# Expected: Bound

# Health endpoint responds
kubectl -n monitoring port-forward svc/pulse 7655:7655 &
curl -s http://localhost:7655/api/health | jq .
# Expected: {"status":"ok"} or similar success response

# Pulse agent can reach server
kubectl -n prod get pod -l app=pulse-agent -o wide
# All pods should show Running, Ready
```

---

## Escalation

If issue persists after pod recovery completes:
1. Check Mayastor pool: `kubectl -n mayastor get diskpool -o wide`
2. Check monit cluster control plane: `kubectl get nodes` (should show Ready)
3. Check pihanga host: `ssh root@10.10.0.20 uptime` (hypervisor health)
4. Review Pulse app logs: `kubectl -n monitoring logs deployment/pulse --tail=100`

**Contact:** Check infrastructure alerts in Grafana (coroot.kernow.io)

---

## Files Modified
- `/home/monit_homelab/kubernetes/platform/pulse/deployment.yaml` — PVC storage class configuration
- ArgoCD Application: `pulse` (monit cluster, namespace monitoring)

## Reference
- Monit cluster CLAUDE.md: `/home/monit_homelab/CLAUDE.md`
- Talos cluster operations: talosctl commands documented in prod_homelab CLAUDE.md
- Mayastor storage: `prod_homelab/kubernetes/platform/mayastor/`
