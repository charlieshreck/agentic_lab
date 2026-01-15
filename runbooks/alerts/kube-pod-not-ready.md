# KubePodNotReady

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubePodNotReady |
| **Severity** | Warning |
| **Threshold** | Pod non-ready for 15+ minutes |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a Kubernetes Pod has been in a non-ready state (Pending, Unknown, or Failed) for longer than 15 minutes. This excludes Jobs which are expected to complete.

## Quick Diagnosis

### 1. Identify the affected pod

```bash
# From alert labels
# Example: namespace=monitoring, pod=gatus-5bb8844f68-ls52q

kubectl get pod <pod-name> -n <namespace> -o wide
kubectl describe pod <pod-name> -n <namespace>
```

### 2. Check pod phase and conditions

```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.phase}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.conditions[*]}'
```

## Common Causes

### 1. Pending - PVC Not Bound (Most Common)

**Symptoms:**
- Pod phase: `Pending`
- Event: "pod has unbound immediate PersistentVolumeClaims"

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
kubectl get pvc -n <namespace>
```

**Resolution Options:**

**Option A: Fix storage provisioner**
```bash
# Check Mayastor status
kubectl get pods -n mayastor
kubectl get diskpool -n mayastor

# Check storage class
kubectl get storageclass
```

**Option B: Create manual PV (for NFS)**
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: <pv-name>
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  nfs:
    server: 10.40.0.10
    path: /mnt/tank/<path>
  storageClassName: nfs-<name>
```

**Option C: Delete if not needed**
```bash
# If the workload is orphaned or redundant
kubectl delete deployment <deployment-name> -n <namespace>
kubectl delete pvc <pvc-name> -n <namespace>
```

### 2. Pending - Insufficient Resources

**Symptoms:**
- Pod phase: `Pending`
- Event: "Insufficient cpu/memory"

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
kubectl top nodes
```

**Resolution:**
```bash
# Option 1: Scale down other workloads
kubectl scale deployment <other-deployment> --replicas=0 -n <namespace>

# Option 2: Reduce resource requests
kubectl edit deployment <deployment-name> -n <namespace>

# Option 3: Add nodes (long-term)
```

### 3. Pending - Node Selector/Affinity Mismatch

**Symptoms:**
- Pod phase: `Pending`
- Event: "didn't match node selector" or "node(s) didn't match Pod's node affinity"

**Verification:**
```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeSelector}'
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.affinity}'
kubectl get nodes --show-labels
```

**Resolution:**
- Update node labels or pod selectors

### 4. CrashLoopBackOff

**Symptoms:**
- Pod phase: `Running` but not ready
- Status: `CrashLoopBackOff`
- Multiple restarts

**Verification:**
```bash
kubectl get pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

**Resolution:**
- Fix application issues based on logs
- Check environment variables, secrets, configs
- Verify dependencies are available

### 5. Failing Readiness Probe

**Symptoms:**
- Pod phase: `Running`
- Ready: `0/1`
- No restarts (liveness passing, readiness failing)

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Readiness:"
kubectl logs <pod-name> -n <namespace>
```

**Resolution:**
- Fix application health endpoint
- Increase probe timeout/threshold
- Check dependencies the health check validates

### 6. Orphaned/Stale Pod

**Symptoms:**
- Pod from old ReplicaSet
- Status: `Completed`, `Error`, or `Evicted`
- Parent workload has newer pods running

**Verification:**
```bash
# Check if there are newer pods from same deployment
kubectl get pods -n <namespace> -l app=<app-label>

# Check replicasets
kubectl get replicaset -n <namespace>
```

**Resolution:**
```bash
# Delete stale pod
kubectl delete pod <pod-name> -n <namespace>
```

## Resolution Steps

### Step 1: Determine pod phase

```bash
kubectl get pod <pod-name> -n <namespace> -o wide
```

### Step 2: Get detailed status

```bash
kubectl describe pod <pod-name> -n <namespace>
```

### Step 3: Check events

```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>
```

### Step 4: Fix based on cause

See "Common Causes" section above for specific fixes.

### Step 5: Verify resolution

```bash
kubectl get pod <pod-name> -n <namespace>
# Should show Running and Ready
```

## Special Cases

### Orphaned Monitoring Components in Prod Cluster

The prod cluster may have orphaned monitoring pods (prometheus, alertmanager, grafana, gatus) from old kube-prometheus-stack deployments. The real monitoring stack runs in the monit cluster.

**Verification:**
```bash
# Check if ArgoCD app points to monit cluster, not prod
kubectl get application kube-prometheus-stack -n argocd -o jsonpath='{.spec.destination.server}'
# Should show: https://10.30.0.20:6443 (monit cluster)
```

**Resolution:**
```bash
# Delete orphaned CRs and workloads in prod
kubectl delete prometheus kube-prometheus-stack-prometheus -n monitoring
kubectl delete alertmanager kube-prometheus-stack-alertmanager -n monitoring
kubectl delete deployment gatus kube-prometheus-stack-grafana beszel -n monitoring
kubectl delete pvc -l app.kubernetes.io/instance=kube-prometheus-stack -n monitoring
```

## Escalation

If pod remains not ready:

1. Check controller logs (deployment controller, statefulset controller)
2. Check node status where pod is scheduled
3. Review cluster-wide events: `kubectl get events -A --sort-by='.lastTimestamp'`
4. Check if node has disk pressure or memory pressure

## Prevention

1. **Resource planning:** Ensure adequate cluster capacity
2. **Storage provisioning:** Verify storage classes are working
3. **Health checks:** Configure appropriate probes
4. **Monitoring:** Alert on pending pods earlier (5 min)

## Related Alerts

- `KubeDeploymentRolloutStuck` - Deployment not progressing
- `KubeContainerWaiting` - Container in waiting state
- `KubePodCrashLooping` - Pod repeatedly crashing

## Historical Incidents

### January 2026 - Orphaned Monitoring Pods in Prod
- **Affected:** prometheus, alertmanager, grafana, gatus, beszel
- **Cause:** Old kube-prometheus-stack deployment in prod cluster with unbound PVCs
- **Symptom:** Pods pending for 31 days, PVCs with no storageClassName
- **Resolution:** Deleted orphaned Prometheus/Alertmanager CRs, deployments, and PVCs
- **Lesson:** Monitoring stack should only exist in monit cluster, not prod

### January 2026 - Coroot Cluster Agent Error
- **Affected:** coroot-cluster-agent in monit cluster
- **Cause:** Stale Error pod not cleaned up after new pod started
- **Resolution:** Deleted stale Error pod manually
- **Lesson:** Kubernetes doesn't always clean up failed pods from deployments
