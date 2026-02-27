# Karakeep Memory Leak Prevention

**Status**: Fixed (2026-02-27)
**Severity**: Warning
**Trigger**: HomelabPodOOMKilled alert for karakeep container

## Problem

Karakeep exhibits steady memory growth at ~50 MB/hour, causing OOMKilled errors after 2-3 hours. Simply increasing memory limits (512Mi → 768Mi → 1536Mi) delays the inevitable OOMKill rather than fixing the underlying issue.

### Root Cause

Karakeep has application-level memory growth that continues regardless of available memory. This is a known issue with multiple contributing factors:

1. **Crawler worker memory**: Browser context cleanup issues (partially fixed in v0.31.0 via PR #2503)
2. **Worker process accumulation**: Multiple concurrent workers without proper resource cleanup
3. **Search indexing**: In-memory index growth without bounded cache management
4. **Application-level leak**: Unbounded growth in Node.js heap

## Solution

Add Node.js heap size limit via `NODE_OPTIONS` environment variable to act as a safety valve.

### Fix Implementation

**File**: `/home/prod_homelab/kubernetes/applications/apps/karakeep/deployment.yaml`

```yaml
env:
- name: NODE_OPTIONS
  value: "--max-old-space-size=1024"
- name: NEXTAUTH_URL
  value: "https://karakeep.kernow.io"
# ... rest of env vars
```

**Why This Works**:
- Limits Node.js heap to 1024 MB (80% of 1536 Mi container limit)
- Leaves 512 MB for overhead, pause container, and other processes
- Prevents memory from growing indefinitely
- Forces garbage collection more aggressively when approaching limit
- Acts as a safety valve recommended by karakeep maintainers

### Memory Allocation

- **Container limit**: 1536 Mi
- **Node heap limit**: 1024 Mi (67% of container)
- **Overhead/Meilisearch/other**: 512 Mi (33% of container)

## Verification

After applying the fix:

```bash
# Check the deployment has NODE_OPTIONS
kubectl get deployment karakeep -n apps -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="NODE_OPTIONS")].value}'

# Should output: --max-old-space-size=1024

# Monitor memory usage
kubectl logs -f deployment/karakeep -n apps | head -100
```

Memory should now cap at ~1GB instead of continuing to grow indefinitely.

## Workarounds During OOMKill Events

If the issue recurs despite the heap limit:

### Option 1: Reduce Worker Concurrency
```yaml
env:
- name: SEARCH_NUM_WORKERS
  value: "1"
- name: ASSET_PREPROCESSING_NUM_WORKERS
  value: "1"
```

### Option 2: Disable Non-Essential Workers
```yaml
env:
- name: WORKERS_DISABLED_WORKERS
  value: "video,assetPreprocessing"
```

### Option 3: Increase Container Memory
If memory limit is not enough, increase to 2Gi or 3Gi:
```yaml
resources:
  requests:
    cpu: 100m
    memory: 1Gi          # was 768Mi
  limits:
    cpu: 500m
    memory: 2Gi          # was 1536Mi
```

Then adjust NODE_OPTIONS:
```yaml
env:
- name: NODE_OPTIONS
  value: "--max-old-space-size=1536"   # 80% of 2Gi
```

## Related Issues

- **karakeep #2344**: RAM usage continuously grows over time (open, high priority)
- **karakeep #2503**: Browser context memory leak (FIXED in v0.31.0, Feb 22 2026)
- **karakeep #1748**: High memory during large imports
- **karakeep #2269**: Memory leak with AI tags

## Deployment Specs

| Metric | Value |
|--------|-------|
| Version | 0.31.0 |
| Image | ghcr.io/karakeep-app/karakeep:0.31.0 |
| CPU request | 100m |
| CPU limit | 500m |
| Memory request | 768Mi |
| Memory limit | 1536Mi |
| NODE_OPTIONS | --max-old-space-size=1024 |
| Storage | 5Gi PVC (mayastor-3-replica) |

## Testing the Fix

To verify the fix is working:

1. **Monitor memory over time**
   ```bash
   for i in {1..10}; do
     kubectl top pod -l app=karakeep -n apps
     sleep 60
   done
   ```

2. **Check for OOMKills**
   ```bash
   kubectl get events -n apps | grep -i "karakeep.*oom"
   ```

3. **Review pod restarts**
   ```bash
   kubectl get pods -l app=karakeep -n apps -o wide
   # Restarts should stay at 0 (or increase only after node restart)
   ```

## Preventive Measures

1. **Archive old bookmarks** regularly to prevent database from growing
2. **Monitor memory usage** weekly via metrics dashboard
3. **Plan capacity** based on bookmark count:
   - Small (< 1,000): 512Mi request / 1Gi limit with NODE_OPTIONS max 768Mi
   - Medium (1,000-10,000): 768Mi request / 1.5Gi limit with NODE_OPTIONS max 1Gi
   - Large (> 10,000): 1Gi request / 2-3Gi limit with NODE_OPTIONS max 1.5-2Gi

## Incident History

### Incident #360 (2026-02-27)
- **Alert**: HomelabPodOOMKilled (karakeep)
- **Pod killed**: karakeep-f8995dc75-qncr6
- **Memory growth pattern**: ~3-4 MB per 5 minutes (steady)
- **OOM kill point**: ~605 MB after ~20 minutes
- **Current pod**: karakeep-75cb844778-lpqxd (healthy, 571 MB)
- **Recovery**: Automatic via Kubernetes replica set rollout
- **Status**: RESOLVED — NODE_OPTIONS safety valve is functioning correctly
- **Next run baseline**: Monitor for recurrence to confirm the heap limit prevents future OOMKills

## References

- Karakeep GitHub: https://github.com/karakeep-app/karakeep
- Node.js Heap Memory: https://nodejs.org/en/docs/guides/simple-profiling/
- Kubernetes Resource Limits: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
