# kube-state-metrics Restart Loop Resolution

## Problem

kube-state-metrics container in the monitoring cluster (monit_homelab) experienced a persistent restart loop with 45 restarts over 11 days. Root cause: liveness probe returning HTTP 503 during startup, triggering kubelet-enforced container restarts every 5-6 minutes.

## Root Cause Analysis

### Why /livez Returns 503 on Startup

The kube-state-metrics application performs expensive initialization on startup:
1. Connects to Kubernetes API server
2. Discovers and caches 28+ resource types (pods, deployments, services, etc.)
3. Builds internal state for metric generation
4. Only then becomes responsive to health check endpoints

**Memory constraint**: With only 64Mi memory request and 256Mi limit, the container's memory allocation was too tight. During the API discovery phase, memory pressure caused the `/livez` endpoint to return HTTP 503 (Service Unavailable).

**Probe configuration**: The default liveness probe (`initialDelaySeconds: 5`) started probing before the app finished initialization, encountering 503 responses and triggering restarts.

### Evidence

Pod events showed:
```
Liveness probe failed: HTTP probe failed with statuscode: 503
Container kube-state-metrics failed liveness probe, will be restarted
```

Logs showed successful startup and port binding but immediate 503 on first probe after 5s delay.

## Solution

Increased memory allocation to provide sufficient headroom for startup:

**Before:**
```yaml
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

**After:**
```yaml
resources:
  requests:
    cpu: 50m
    memory: 128Mi    # 2x increase
  limits:
    cpu: 200m
    memory: 512Mi    # 2x increase
```

This allows the app to comfortably:
- Allocate memory for API client cache during discovery
- Build internal state without memory pressure
- Return healthy 200 responses to probes within 5s startup delay

## Verification

After updating the manifest and restarting the pod:
- Pod achieved 1/1 Ready status in 30+ seconds
- No liveness probe failures observed
- No container restarts after fix deployment
- Stable running state maintained

## Prevention

For slow-starting monitoring applications:
1. Allocate memory based on API client cache size (especially for clusters with 25+ resource types)
2. Consider using Kubernetes StartupProbe if probe configuration is overridable
3. Monitor pod events for health check failures during initial deployment
4. Scale memory reserves in metric collection workloads proportionally to API object count

## Files Modified

- `monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`
  - Updated kube-state-metrics memory request: 64Mi → 128Mi
  - Updated kube-state-metrics memory limit: 256Mi → 512Mi

## Impact

- **Monitoring**: kube-state-metrics pod now stable and continuously operational
- **Resource usage**: Slightly higher baseline memory usage, but eliminates eviction risk
- **Cluster stability**: Removes cascading restart loop that could trigger cascading failures

## Related Issues

- Incident #611: kube-state-metrics crash loop (RESOLVED)
- Previous fix (commit f4a448c): Addressed BestEffort QoS eviction during I/O storms by adding resource requests — this fix extends that by increasing memory headroom
