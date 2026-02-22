# Redis Incident Runbook (ai-platform)

## Overview

Redis runs as a single-replica StatefulSet in the `ai-platform` namespace on the agentic cluster.
It serves as cache/session store for: Kernow Hub (sessions), LangGraph, and other platform services.

**Manifest**: `agentic_lab/kubernetes/applications/redis/statefulset.yaml`
**PVC**: `redis-data-redis-0` (5Gi, local-path)
**NodePort**: 30637

---

## Alert: Redis Pod Restarted (Coroot critical)

### Symptoms
- Coroot fires a critical incident for `redis@ai-platform`
- `kubectl_get_pods` shows `restarts > 0` for `redis-0`
- Services depending on Redis (Kernow Hub, LangGraph) may briefly fail

### Diagnosis

**1. Check pod state**
```
kubectl_get_pods namespace=ai-platform label_selector=app=redis
kubectl_describe resource_type=pod name=redis-0 namespace=ai-platform
```

Look at `Last State → Reason` and `Exit Code`:
- **Exit Code 255 / Reason: Unknown** → node-level event (node crash/reboot). Redis auto-recovered. No Redis fault.
- **Exit Code 1 / Reason: Error** → Redis application crash. Check logs.
- **OOMKilled** → Redis hit memory limit. Check maxmemory config.

**2. Check logs**
```
kubectl_logs pod_name=redis-0 namespace=ai-platform tail_lines=100
kubectl_logs pod_name=redis-0 namespace=ai-platform previous=true tail_lines=100
```

**3. Check current health**
```
kubectl_get_pods namespace=ai-platform label_selector=app=redis
```
If `ready=true`, Redis has recovered and services should be operational.

---

## Exit Code 255 (Node Crash) — Most Common

This is **not a Redis bug**. The node (agentic-01) rebooted or lost power, causing all pods to terminate with code 255.

**Resolution**: No action needed if the pod is `Running` and `ready=true`.
Redis reloads its AOF/RDB on startup — data is preserved via PVC.

**To verify data integrity post-restart**:
```bash
# Via MCP REST bridge or kubectl exec
redis-cli -h 10.20.0.40 -p 30637 INFO keyspace
redis-cli -h 10.20.0.40 -p 30637 DEBUG SLEEP 0  # Just tests connection
```

---

## OOMKilled — Memory Pressure

If `Reason: OOMKilled`:

1. Check current memory usage:
   ```
   redis-cli -h 10.20.0.40 -p 30637 INFO memory
   ```

2. The `maxmemory` is set to 512mb with `allkeys-lru` eviction — Redis should self-regulate.
   If OOM occurs despite this, the process memory overhead is exceeding the 1Gi container limit.

3. **Fix**: Increase memory limit in `statefulset.yaml`:
   ```yaml
   limits:
     memory: "2Gi"
   ```
   Commit → push → ArgoCD sync.

---

## Redis Application Crash (Exit Code 1)

If logs show `FATAL` or config errors:

1. Review args in `statefulset.yaml` — specifically `--appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru`
2. Check PVC is mounted and healthy: `kubectl_describe resource_type=pvc name=redis-data-redis-0`
3. Check for disk space issues on local-path storage

---

## Dependent Services Impact

If Redis is down, these services are affected:
- **Kernow Hub**: Session cookie auth fails → users get 401/redirect loops
- **LangGraph**: May fail to access state store
- **Any caching layer** using Redis

Most services have retry logic and will recover automatically once Redis is up.

---

## False Positive Suppression

Coroot fires critical on any restart, including benign node reboots.
If the cluster node is intentionally rebooted (e.g. Talos upgrades), this alert can be ignored once Redis is confirmed running.

Current restart history (as of 2026-02-22):
- 2 total restarts — both from node-level events (exit code 255), not Redis faults
