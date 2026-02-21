# NodeSystemSaturation

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | NodeSystemSaturation |
| **Severity** | Warning |
| **Threshold** | System load per core > 2.0 for 15 minutes |
| **Source** | Prometheus node-exporter (node_load1 metric) |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a Kubernetes node's CPU load per core exceeds 2.0 for more than 15 minutes. High system load indicates CPU saturation and can lead to:

- Degraded application performance
- Slow API responses
- Delayed job execution
- Increased context switching overhead
- Risk of cascading failures under additional load
- Potential node unresponsiveness

**Note:** Load per core = `node_load1 / cpu_count`. A value of 2.0 means the system is oversubscribed — processes are queuing for CPU time.

## Quick Diagnosis

### 1. Identify the affected node

```bash
# Check which node is alerting (from alert labels)
# Example: instance: 10.10.0.43:9100

# Map IP to node name
# 10.10.0.40 = talos-cp-01 (control plane)
# 10.10.0.41 = talos-worker-01
# 10.10.0.42 = talos-worker-02
# 10.10.0.43 = talos-worker-03
# 10.20.0.40 = agentic node
# 10.30.0.20 = monit node
```

### 2. Check current system load

```bash
# For prod cluster (adjust KUBECONFIG for agentic/monit)
export KUBECONFIG=/root/.kube/config
kubectl get nodes -o wide | grep <node-ip>
kubectl top nodes
```

### 3. Check pod density

```bash
# Count pods on the affected node
kubectl get pods -A -o wide | grep <node-name> | wc -l

# Check pod distribution across nodes
kubectl get pods -A -o wide | awk '{print $8}' | sort | uniq -c | sort -rn
```

### 4. Check CPU allocation vs usage

```bash
# Get CPU requests and actual usage
kubectl top pods -A --containers | grep <node-name> | head -20
kubectl describe node <node-name> | grep -A 5 "Non-terminated Pods"
```

## Common Causes

### 1. Pod Overallocation / High Pod Density (Most Common)

**Symptoms:**
- 50+ pods on a 4-core node
- Uneven pod distribution (one node has many more pods than others)
- High context switches (12,000+/sec)
- Many pods with no CPU requests/limits

**Verification:**
```bash
# Count pods per node
kubectl get pods -A -o wide | awk '{print $8}' | sort | uniq -c | sort -rn

# Check context switches and load
# Via metrics: rate(node_context_switches_total[5m])
# Via Prometheus: SELECT node_load1{instance="<ip>:9100"}
```

**Root cause analysis:**
```bash
# List all pods on the node
kubectl get pods -A -o wide --field-selector spec.nodeName=<node-name>

# Check pod age (many completed jobs staying around?)
kubectl get pods -A -o wide --field-selector spec.nodeName=<node-name> | grep -E "Succeeded|Failed|Pending"
```

**Resolution:**

Option A: **Reduce pod density (recommended)**
- Remove completed job pods (cleanup policies)
- Move deployments to other nodes using affinity rules
- Scale down replicas for non-critical deployments

Option B: **Set resource requests on all pods**
```yaml
resources:
  requests:
    cpu: "50m"      # Small value for lightweight pods
    memory: "64Mi"
  limits:
    cpu: "200m"
    memory: "256Mi"
```

Option C: **Add pod anti-affinity rules**
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app
                operator: In
                values:
                  - my-app
          topologyKey: kubernetes.io/hostname
        weight: 50
```

### 2. Runaway Process or Resource Leak

**Symptoms:**
- Load increases gradually over days/weeks
- Single pod consuming 1-2 CPU cores continuously
- Pod hasn't restarted recently

**Verification:**
```bash
# Find top CPU consumers on the node
kubectl top pods -A --sort-by=cpu | head -20

# Check pod age
kubectl describe pod <pod-name> -n <namespace> | grep "Start Time"
```

**Resolution:**
```bash
# Restart the specific deployment
kubectl rollout restart deployment/<name> -n <namespace>

# Or delete the pod (will be recreated)
kubectl delete pod <pod-name> -n <namespace>
```

### 3. Node Hardware Limitation

**Symptoms:**
- Older hardware (2-4 cores)
- Many CPU-intensive workloads
- Load remains high even after moving pods

**Resolution:**
- Add more nodes to the cluster
- Migrate workloads to higher-resource nodes
- Enable horizontal pod autoscaling to spread load

### 4. CI/CD or Batch Jobs

**Symptoms:**
- Load spikes at specific times (build jobs, cron tasks)
- Load returns to normal after job completes
- High load during business hours only

**Resolution:**
```bash
# Check for running jobs
kubectl get jobs -A
kubectl get cronjobs -A -o wide

# Adjust job resource requests/limits
# or schedule heavy jobs during off-peak hours
```

## Resolution Steps

### Immediate (Reduce Load)

For **talos-worker-03** or any affected node:

1. **Identify and count pods:**
   ```bash
   kubectl get pods -A -o wide --field-selector spec.nodeName=talos-worker-03 | wc -l
   ```

2. **Check for completed/failed pods to clean up:**
   ```bash
   # List Succeeded or Failed pods
   kubectl get pods -A -o wide --field-selector spec.nodeName=talos-worker-03 | grep -E "Succeeded|Failed"

   # Delete completed pod pods (they hold resources)
   kubectl delete pods -A --field-selector status.phase=Succeeded
   kubectl delete pods -A --field-selector status.phase=Failed
   ```

3. **Review node taints/cordon status:**
   ```bash
   kubectl describe node talos-worker-03 | grep -A 5 "Taints\|Cordoned"

   # If cordoned, check why and consider uncordoning
   kubectl uncordon talos-worker-03  # only if intentional cordon is resolved
   ```

4. **Identify top CPU consumers:**
   ```bash
   kubectl top pods -A --sort-by=cpu | head -10
   ```

5. **Restart high-load deployments** if they're leaking resources:
   ```bash
   kubectl rollout restart deployment/<name> -n <namespace>
   ```

### Long-term Fixes

1. **Set CPU requests and limits on all deployments:**
   - Review existing deployments: `kubectl get deployments -A -o jsonpath='{.items[*].spec.template.spec.containers[*].resources}'`
   - Add reasonable defaults in manifests (50m CPU, 64-256Mi memory for most apps)

2. **Implement pod disruption budgets:**
   ```yaml
   apiVersion: policy/v1
   kind: PodDisruptionBudget
   metadata:
     name: pdb-example
   spec:
     minAvailable: 1
     selector:
       matchLabels:
         app: example
   ```

3. **Configure HPA for CPU-intensive workloads:**
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: example
     minReplicas: 1
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
   ```

4. **Enable JobBackoffLimit and TTL for batch jobs:**
   ```yaml
   spec:
     backoffLimit: 3
     ttlSecondsAfterFinished: 300  # Delete completed jobs after 5 minutes
   ```

5. **Review Talos machine config:**
   - If consistently overloaded, consider increasing CPU allocation in Terraform
   - Or distribute workloads across more nodes

## Escalation

If load remains high after:
1. Removing completed job pods
2. Restarting resource-leaking workloads
3. Adding CPU requests/limits

Then:
1. Check Talos node health via dashboard: `talosctl -n <node-ip> dashboard`
2. Review kernel logs for CPU-related errors
3. Consider adding more compute resources to the cluster
4. Check for processes running outside Kubernetes (rare on Talos)

## Prevention

1. **Set default resource requests/limits in namespace ResourceQuotas**
2. **Use LimitRanges to enforce minimum/maximum CPU allocations per pod**
3. **Enable audit logging to catch suspicious scheduling**
4. **Regular capacity planning reviews** — maintain 30-40% CPU headroom per node
5. **Implement pod lifecycle hooks** to clean up stale resources

## Related Alerts

- `NodeMemoryHighUtilization` - High memory usage on node
- `KubeCpuOvercommit` - Cluster CPU over-committed
- `KubePodCrashLooping` - Pods crash due to resource contention
- `NodeNotReady` - Node becomes unresponsive due to CPU starvation

## Monitoring & Metrics

**Key metrics to track:**
- `node_load1` — Raw system load (1-minute average)
- `rate(node_context_switches_total[5m])` — Context switch rate (should be <5000/sec normally)
- `kubelet_running_pods` — Pod count per node
- `container_cpu_usage_seconds_total` — CPU usage per container

**Grafana queries:**
```promql
# Load per core
node_load1{job="node-exporter"} / count(count(node_cpu_seconds_total) by (cpu)) by (instance)

# Top pod CPU usage
topk(5, rate(container_cpu_usage_seconds_total{pod!=""}[5m]))

# Context switches (early warning of overload)
rate(node_context_switches_total[5m])
```

## Historical Incidents

### February 2026 - talos-worker-03 High Load

- **Date**: 2026-02-21
- **Duration**: 24+ hours sustained
- **Affected**: talos-worker-03 (10.10.0.43)
- **Load**: 8.0-8.9 on 4-core node (2.0-2.22 per core)
- **Root cause**: 78 pods scheduled on node with only 3.95 cores allocatable
- **Symptoms**:
  - High context switches: 12,052/sec
  - Multiple pods in "Succeeded" status not cleaned up
  - Many pods with high restart counts (ArgoCD repo-server: 12 restarts)
  - Uneven pod distribution (26 actually running, 78 total across cluster)
- **Resolution**: Implemented cleanup policies and resource requests across deployments

## References

- [Kubernetes Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Pod Priority and Preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/)
- [Talos Troubleshooting](https://www.talos.dev/latest/learn-more/troubleshooting/)
