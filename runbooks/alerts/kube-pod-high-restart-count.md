# HomelabPodHighRestartCount

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | HomelabPodHighRestartCount |
| **Severity** | Warning |
| **Threshold** | Container restart count > 100 |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a container has accumulated a high number of restarts, indicating chronic instability or a restart loop. Exit code 137 (SIGKILL) often indicates liveness/readiness probe failures or resource exhaustion.

## Quick Diagnosis

### 1. Identify the affected pod

```bash
kubectl get pods -n <namespace> -l <selector>
kubectl describe pod <pod-name> -n <namespace>
```

### 2. Check restart count and exit code

```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].restartCount}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.exitCode}'
```

**Common exit codes:**
- **137**: SIGKILL - liveness probe failure, OOM kill, or pod eviction
- **1**: Application crash
- **2**: Misuse of shell built-in
- **124**: Timeout
- **127**: Command not found

## Common Causes

### 1. DNS/Service Discovery Failure (Most Common)

**Symptoms:**
- Exit code: 137
- Logs show connection timeouts to services
- Pod uses `hostNetwork: true` but tries to access Kubernetes service names

**Root cause:**
When `hostNetwork: true`, pod uses the host's network namespace and cannot resolve Kubernetes service DNS names like `myapp.namespace.svc.cluster.local`. Service discovery fails, application crashes, liveness probe fails, pod restarts.

**Verification:**
```bash
# Check deployment spec for hostNetwork
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.hostNetwork}'

# Check pod logs for DNS/connection errors
kubectl logs <pod-name> -n <namespace> --previous | grep -iE "connection refused|getaddrinfo|enetunreach"
```

**Resolution:**
```yaml
# Option 1: Remove hostNetwork (preferred)
spec:
  template:
    spec:
      hostNetwork: false  # Remove or set to false
      dnsPolicy: ClusterFirst

# Option 2: Use pod IP or NodePort instead of service name
# (less preferred - fragile and requires pod IP discovery)
```

**Example Fix for Matter Hub:**
- Issue: `hostNetwork: true` + trying to connect to `homeassistant.apps.svc.cluster.local:8123`
- Fix: Remove `hostNetwork: true`, update `dnsPolicy` to `ClusterFirst`
- Commit and push to trigger ArgoCD sync

### 2. Insufficient Memory (OOM Kill)

**Symptoms:**
- Exit code: 137
- Logs show memory spikes or garbage collection
- Pod memory usage near limit

**Verification:**
```bash
kubectl top pod <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Limits:"
```

**Resolution:**
```yaml
# Increase memory limits in deployment
resources:
  limits:
    memory: 1Gi  # Increase from 512Mi
  requests:
    memory: 256Mi
```

### 3. Failing Readiness/Liveness Probe

**Symptoms:**
- Exit code: 137
- Pod restarts every 30-60 seconds
- Logs show the application is running but probe fails

**Verification:**
```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].livenessProbe}'
kubectl logs <pod-name> -n <namespace> --previous | tail -20
```

**Resolution:**
```yaml
# Increase probe timeouts or failure thresholds
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 60  # Increase from 30
  periodSeconds: 10
  timeoutSeconds: 5        # Increase from 1
  failureThreshold: 5      # Increase from 3
```

### 4. Dependency Not Ready

**Symptoms:**
- Exit code: 1
- Logs show errors like "Unable to connect to upstream service"
- Pod starts but can't reach a dependency

**Verification:**
```bash
kubectl logs <pod-name> -n <namespace> --tail=50
# Look for connection errors, timeouts, "service not found"
```

**Resolution:**
- Check if dependency is running: `kubectl get pods -n <dep-namespace> -l app=<dep-name>`
- Check service exists: `kubectl get svc -n <dep-namespace> <dep-name>`
- Increase initial delay in probes to give dependencies time to start
- Add init containers to wait for dependencies

### 5. Resource Request/Limit Mismatch

**Symptoms:**
- Pod scheduled to a node, then immediately evicted
- Exit code: 137
- No restarts in logs

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
```

**Resolution:**
- Reduce resource requests
- Increase node capacity
- Update node affinity/selectors

## Resolution Steps

### Step 1: Gather Information

```bash
# Pod status
kubectl get pod <pod-name> -n <namespace> -o wide

# Container status with exit code
kubectl describe pod <pod-name> -n <namespace> | grep -A 20 "Container"

# Recent logs (current run)
kubectl logs <pod-name> -n <namespace> --tail=100

# Previous run logs (if crashed)
kubectl logs <pod-name> -n <namespace> --previous --tail=100
```

### Step 2: Identify the Pattern

1. **Exit code 137 + DNS/connection errors** → DNS/service discovery issue
2. **Exit code 137 + memory spikes** → OOM or memory leak
3. **Exit code 1 + dependency errors** → Dependency not ready
4. **Quick restart cycle (30-60s)** → Probe failure

### Step 3: Update Deployment

Edit the deployment manifest in your GitOps repo:

```bash
# Example: Fix hostNetwork issue
cd /home/prod_homelab
git edit kubernetes/applications/apps/matter-hub/deployment.yaml
```

Make changes according to the cause identified in Step 2.

### Step 4: Commit and Push

```bash
git -C /home/<repo> add kubernetes/.../deployment.yaml
git -C /home/<repo> commit -m "fix: resolve pod restart loop

- Root cause: [DNS issue|OOM|probe failure|etc]
- Fix: [change made]
- Example: removed hostNetwork to enable service DNS resolution"
git -C /home/<repo> push origin main
```

ArgoCD will auto-sync within 3 minutes.

### Step 5: Verify Resolution

```bash
# Monitor pod restart count
kubectl get pod <pod-name> -n <namespace> -w

# Check logs for normal operation
kubectl logs <pod-name> -n <namespace> -f
```

**Success criteria:**
- Restart count stops increasing
- Logs show normal operation, no errors
- Pod shows `Ready 1/1`

## Prevention

1. **Test service discovery** - Always verify services are reachable from pods
2. **Use appropriate network modes** - Only use `hostNetwork: true` if absolutely necessary
3. **Monitor memory usage** - Set requests/limits based on observed usage, not guesses
4. **Graceful startup** - Use init containers or probe delays for dependencies
5. **Alerting** - This alert is designed to catch issues early

## Related Alerts

- `KubePodNotReady` - Pod not becoming ready (complementary alert)
- `KubeContainerWaiting` - Container stuck in waiting state
- `KubePodCrashLooping` - Similar but specifically for crash loops

## Historical Incidents

### February 2026 - Matter Hub Service Discovery Failure
- **Affected**: matter-hub pod in apps namespace
- **Symptom**: 133 restarts, unable to connect to homeassistant.apps.svc.cluster.local
- **Root cause**: `hostNetwork: true` prevented Kubernetes service DNS resolution
- **Exit code**: 137 (liveness probe kill)
- **Resolution**: Removed hostNetwork, updated dnsPolicy, increased memory limits
- **Lesson**: hostNetwork breaks service discovery; modern Matter doesn't require it

## References

- [Kubernetes Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Network Policies and hostNetwork](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Container Exit Codes](https://tldp.org/LDP/abs/html/exitcodes.html)
