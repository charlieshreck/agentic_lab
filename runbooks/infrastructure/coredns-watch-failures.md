# CoreDNS Kubernetes Plugin Watch Failures

## Problem

CoreDNS experiences intermittent "Failed to watch" errors in Kubernetes plugin logs, preventing proper service endpoint synchronization. This causes DNS resolution failures for Kubernetes services (e.g., `backrest.backrest.svc`), resulting in downstream health check failures.

**Symptom**: `dial tcp: lookup <service>.<namespace>.svc on <kube-dns-ip>:53: no such host`

## Root Cause

CoreDNS's Kubernetes plugin uses a watch mechanism to monitor service and endpoint updates. When this watch connection fails (often after transient API server hiccups, restart cycles, or quota exhaustion), the plugin cannot refresh its internal cache of services.

Unlike a single failure, persistent watch failures accumulate: the plugin continues serving stale or empty service data until the watch is re-established.

## Detection

Check CoreDNS logs for "Failed to watch" errors:

```bash
kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "failed to watch"
```

Example output:
```
[WARNING] plugin/kubernetes: Failed to watch *v1.Endpoints: unknown
[WARNING] plugin/kubernetes: Failed to watch *v1.Service: unknown (retrying in 1s)
```

Verify the issue affects DNS resolution:
```bash
# From a pod or node in the cluster
nslookup <service>.<namespace>.svc.cluster.local
# Should fail with "no such host" if watch is broken
```

## Resolution

### Step 1: Restart CoreDNS Pods

Restart CoreDNS to force a fresh connection to the Kubernetes API:

```bash
# Set correct cluster context (e.g., monitoring, prod, agentic)
export KUBECONFIG=/path/to/kubeconfig
kubectl --context=<cluster-context> -n kube-system delete pod -l k8s-app=kube-dns
```

Wait for new pods to come up (typically 10-20 seconds):
```bash
kubectl --context=<cluster-context> -n kube-system get pods -l k8s-app=kube-dns
# Should show 1/1 Running with very recent AGE
```

### Step 2: Verify DNS Resolution

Test that DNS is working again:
```bash
# Port-forward to a CoreDNS pod
kubectl port-forward -n kube-system svc/kube-dns 5353:53 &

# Test resolution (from another terminal)
dig @localhost -p 5353 <service>.<namespace>.svc.cluster.local

# Should return the ClusterIP of the service
```

Or check the application logs that was failing:
```bash
# Example: Gatus should show successful health checks again
kubectl logs -n <namespace> -l <app-label> | grep "success=true"
```

### Step 3: Verify No "Failed to watch" Errors

```bash
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100 | grep -i "failed to watch"
# Should return nothing or only old errors
```

## Why This Works

When CoreDNS restarts:
1. New pod instances re-initialize the Kubernetes plugin
2. Fresh connections to the Kubernetes API re-establish the watch mechanism
3. Service and endpoint data is re-synced into the in-memory DNS cache
4. Subsequent queries resolve correctly

The restart is safe because:
- CoreDNS is stateless (no persistent data)
- New instances inherit the same configuration via ConfigMap
- Kubernetes automatically routes DNS requests to healthy pods
- Transient failures during the few seconds of restart are absorbed by client-side DNS caching

## Prevention

Watch failures often indicate transient API server issues. Prevention strategies:

1. **Monitor CoreDNS Logs**: Alert on repeated "Failed to watch" messages
2. **Check API Server Health**: Verify the Kubernetes API server has sufficient resources
3. **Review Quota Limits**: Ensure API rate limits aren't causing watch rejections
4. **Cluster Upgrades**: Update CoreDNS to latest patch version (watch improvements are ongoing)

## Related Issues

- **Incident #509** (2026-03-18): Missing `force_tcp` in CoreDNS caused high KubeAPITerminatedRequests. CoreDNS now forces TCP for all upstream forwarders to avoid UDP fragmentation.
- **Incident #504** (2026-03-29): CoreDNS watch failures prevented Backrest service discovery in monitoring cluster. Fixed by pod restart.

## Files Modified

- None (pod restart only — no manifest changes required)

## Testing

After applying the fix, verify:
1. All CoreDNS pods are Running
2. No "Failed to watch" errors in logs
3. Service DNS queries resolve correctly
4. Dependent applications (Gatus, etc.) resume normal operation

---

**Last Updated**: 2026-03-29
**Verified On**: Monitoring cluster (Talos single-node VM 10.10.0.30)
