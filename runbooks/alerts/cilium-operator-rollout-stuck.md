# Cilium Operator RolloutStuck

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeDeploymentRolloutStuck (cilium-operator) |
| **Severity** | Warning |
| **Threshold** | Deployment not progressing for 15+ minutes |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (especially single-node clusters) |

## Description

This alert fires when the Cilium Operator deployment is stuck and not making progress. Cilium is the CNI (Container Network Interface) plugin used in Talos clusters for:
- Pod networking
- Network policies
- Kube-proxy replacement
- Load balancing

## Quick Diagnosis

### 1. Check cilium-operator status

```bash
kubectl get deployment cilium-operator -n kube-system
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-operator
```

### 2. Check pod details

```bash
kubectl describe pods -n kube-system -l app.kubernetes.io/name=cilium-operator
```

### 3. Check events

```bash
kubectl get events -n kube-system --sort-by='.lastTimestamp' | grep cilium
```

## Common Causes

### 1. Multiple Replicas on Single-Node Cluster (Most Common)

**Symptoms:**
- Deployment shows 1/2 ready
- Second pod stuck in `Pending`
- Event: "didn't have free ports for the requested pod ports"

**Verification:**
```bash
# Check replica count
kubectl get deployment cilium-operator -n kube-system -o jsonpath='{.spec.replicas}'

# Check node count
kubectl get nodes

# If replicas > nodes, this is the issue
```

**Explanation:**
Cilium operator uses hostPort for high availability. On single-node clusters, only one replica can run because both would need the same host ports.

**Resolution:**
```bash
# Scale to 1 replica for single-node clusters
kubectl scale deployment cilium-operator -n kube-system --replicas=1

# Verify
kubectl get deployment cilium-operator -n kube-system
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-operator
```

### 2. Node Resource Exhaustion

**Symptoms:**
- Pod in `Pending`
- Event: "Insufficient cpu/memory"

**Verification:**
```bash
kubectl describe pod <cilium-operator-pod> -n kube-system | grep -A 10 "Events:"
kubectl top nodes
```

**Resolution:**
- Free up node resources
- Reduce cilium-operator resource requests (not recommended)

### 3. Image Pull Issues

**Symptoms:**
- Pod in `ImagePullBackOff`

**Verification:**
```bash
kubectl describe pod <cilium-operator-pod> -n kube-system | grep -A 5 "Events:"
```

**Resolution:**
- Check network connectivity
- Verify image registry is accessible

### 4. Cilium Agent Issues

**Symptoms:**
- Operator pods running but not ready
- Cilium agents (daemonset) unhealthy

**Verification:**
```bash
kubectl get pods -n kube-system -l k8s-app=cilium
kubectl logs -n kube-system -l k8s-app=cilium --tail=50
```

**Resolution:**
- Fix cilium agent issues first
- Restart cilium daemonset if needed

## Resolution Steps

### For Single-Node Clusters

```bash
# Step 1: Check current state
kubectl get deployment cilium-operator -n kube-system

# Step 2: Scale to 1 replica
kubectl scale deployment cilium-operator -n kube-system --replicas=1

# Step 3: Verify resolution
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-operator
```

### For Multi-Node Clusters

```bash
# Step 1: Identify stuck pod
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-operator -o wide

# Step 2: Check why pod is stuck
kubectl describe pod <stuck-pod-name> -n kube-system

# Step 3: Fix based on cause (see Common Causes)

# Step 4: If needed, restart the deployment
kubectl rollout restart deployment cilium-operator -n kube-system
```

## Cluster-Specific Configurations

### Monit Cluster (Single Node)
- **Node count:** 1 (10.30.0.20)
- **Recommended replicas:** 1
- **Note:** Multi-replica won't work due to hostPort conflicts

### Prod Cluster (Multi Node)
- **Node count:** 4 (1 CP + 3 workers)
- **Recommended replicas:** 2 (for HA)
- **Note:** Pods should schedule on different nodes

### Agentic Cluster (Single Node)
- **Node count:** 1 (10.20.0.40)
- **Recommended replicas:** 1
- **Note:** Same as monit cluster

## Impact Assessment

**If cilium-operator is unhealthy:**
- New pods may not get IP addresses
- Network policies may not be enforced
- Service load balancing may be affected
- **Existing pods continue to work** (control plane issue, not data plane)

## Escalation

If cilium-operator remains stuck:

1. Check cilium agent daemonset health
2. Review cilium operator logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=cilium-operator`
3. Check node networking: `talosctl -n <node-ip> get addresses`
4. Consult Cilium documentation for specific errors

## Prevention

1. **Match replicas to cluster size:** Single-node = 1 replica
2. **Monitor cluster capacity:** Ensure resources for CNI
3. **Test before upgrades:** Verify cilium works after Talos upgrades

## Related Alerts

- `KubeDeploymentReplicasMismatch` - General deployment mismatch
- `CiliumAgentNotReady` - Cilium agent issues
- `NodeNetworkUnavailable` - Network plugin issues

## Historical Incidents

### January 2026 - Monit Cluster Cilium Operator
- **Affected:** cilium-operator in monit cluster (10.30.0.0/24)
- **Cause:** Deployment configured for 2 replicas on single-node cluster
- **Symptom:** 1/2 pods ready, second pod stuck in Pending
- **Resolution:** Scaled deployment to 1 replica
- **Lesson:** Single-node clusters need replicas=1 for operators using hostPort
