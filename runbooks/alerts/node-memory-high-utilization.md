# NodeMemoryHighUtilization

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | NodeMemoryHighUtilization |
| **Severity** | Warning |
| **Threshold** | Memory usage > 90% for 15 minutes |
| **Source** | Prometheus node-exporter |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a Kubernetes node's memory utilization exceeds 90% for more than 15 minutes. High memory usage can lead to:
- OOMKilled pods
- Node instability
- Degraded application performance
- Potential node crashes

## Quick Diagnosis

### 1. Identify the affected node

```bash
# Check which node is alerting (from alert labels)
# Example: instance: 10.10.0.42:9100

# Map IP to node name
# 10.10.0.40 = talos-cp-01 (control plane)
# 10.10.0.41 = talos-worker-01
# 10.10.0.42 = talos-worker-02
# 10.10.0.43 = talos-worker-03
# 10.20.0.40 = agentic node
# 10.30.0.20 = monit node
```

### 2. Check current memory usage

```bash
# For prod cluster
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig kubectl top nodes

# For agentic cluster
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig kubectl top nodes

# For monit cluster
KUBECONFIG=/home/monit_homelab/kubeconfig kubectl top nodes
```

### 3. Identify top memory consumers

```bash
# Replace KUBECONFIG as needed
kubectl top pods -A --sort-by=memory | head -20
```

## Common Causes

### 1. Mayastor-Alloy Memory Leak (Most Common)

**Symptoms:**
- `mayastor-alloy` pods consuming 4-6GB each
- Memory increases over time (days/weeks)
- Pod hasn't restarted recently

**Verification:**
```bash
kubectl top pods -n mayastor -l app.kubernetes.io/name=alloy
kubectl get pods -n mayastor -l app.kubernetes.io/name=alloy -o wide
```

**Resolution:**
```bash
# Restart the alloy daemonset to free memory
kubectl rollout restart daemonset mayastor-alloy -n mayastor

# Verify memory drops after restart (wait 1-2 minutes)
kubectl top nodes
```

**Expected Memory Recovery:** ~4-5GB per node

### 2. Application Memory Leak

**Symptoms:**
- Single application pod consuming excessive memory
- Memory grows over time without releases

**Verification:**
```bash
# Find the culprit
kubectl top pods -A --sort-by=memory | head -10

# Check pod age (long-running pods more likely to leak)
kubectl get pods -A -o wide | grep <pod-name>
```

**Resolution:**
```bash
# Restart the specific deployment
kubectl rollout restart deployment/<deployment-name> -n <namespace>

# Or delete the specific pod (will be recreated)
kubectl delete pod <pod-name> -n <namespace>
```

### 3. Too Many Pods Scheduled

**Symptoms:**
- Many pods on one node
- Uneven distribution across nodes

**Verification:**
```bash
# Check pod distribution
kubectl get pods -A -o wide | awk '{print $8}' | sort | uniq -c | sort -rn
```

**Resolution:**
- Review pod resource requests
- Add pod anti-affinity rules
- Consider adding more nodes

### 4. Resource Requests Too Low

**Symptoms:**
- Pods using more memory than requested
- Scheduler over-commits nodes

**Verification:**
```bash
# Compare requests vs actual usage
kubectl top pods -A --containers
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.containers[*].resources.requests.memory}{"\n"}{end}'
```

**Resolution:**
- Increase memory requests in deployments
- Set appropriate memory limits

## Resolution Steps

### Immediate (Stop the Bleeding)

1. **Identify top memory consumers:**
   ```bash
   kubectl top pods -A --sort-by=memory | head -10
   ```

2. **Restart memory-hogging workloads:**
   ```bash
   # For mayastor-alloy (most common)
   kubectl rollout restart daemonset mayastor-alloy -n mayastor

   # For other deployments
   kubectl rollout restart deployment/<name> -n <namespace>
   ```

3. **Verify memory drops:**
   ```bash
   # Wait 1-2 minutes then check
   kubectl top nodes
   ```

### Long-term Fixes

1. **Set memory limits on pods without them:**
   ```yaml
   resources:
     requests:
       memory: "256Mi"
     limits:
       memory: "512Mi"
   ```

2. **Configure memory-based HPA:**
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   spec:
     metrics:
     - type: Resource
       resource:
         name: memory
         target:
           type: Utilization
           averageUtilization: 80
   ```

3. **Add pod disruption budgets for graceful restarts**

## Escalation

If memory remains high after restarting workloads:

1. Check for memory leaks in custom applications
2. Review Talos node configuration
3. Consider increasing node memory allocation in Terraform
4. Check for runaway processes via Talos dashboard:
   ```bash
   talosctl -n <node-ip> dashboard
   ```

## Prevention

1. **Regular restarts:** Consider periodic rolling restarts of known leaky workloads
2. **Monitoring:** Set up Grafana alerts at 80% as early warning
3. **Capacity planning:** Ensure 20% memory headroom on each node
4. **Resource quotas:** Implement namespace resource quotas

## Related Alerts

- `KubeMemoryOvercommit` - Cluster memory over-committed
- `KubePodCrashLooping` - Pods OOMKilled repeatedly
- `NodeNotReady` - Node becomes unresponsive due to memory pressure

## Historical Incidents

### January 2026 - Mayastor-Alloy Memory Leak
- **Affected:** talos-worker-01 (81%), talos-worker-02 (84%)
- **Cause:** mayastor-alloy pods running 36 days accumulated 5GB+ each
- **Resolution:** Restarted mayastor-alloy daemonset
- **Memory recovered:** ~9GB total across both nodes
- **Lesson:** Consider scheduled restarts for alloy pods
