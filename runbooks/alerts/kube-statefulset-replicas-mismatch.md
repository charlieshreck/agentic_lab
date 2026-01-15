# KubeStatefulSetReplicasMismatch

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeStatefulSetReplicasMismatch |
| **Severity** | Warning |
| **Threshold** | Mismatch for 15+ minutes with no updates |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a StatefulSet's ready replicas don't match the desired replicas for more than 15 minutes, and no updates have been made. StatefulSets are typically used for:
- Databases (PostgreSQL, ClickHouse)
- Message queues (Redis, RabbitMQ)
- Monitoring (Prometheus, AlertManager)
- Storage systems (Mayastor)

## Quick Diagnosis

### 1. Identify the affected StatefulSet

```bash
# From alert labels
# Example: statefulset=alertmanager-kube-prometheus-stack-alertmanager, namespace=monitoring

kubectl get statefulset <name> -n <namespace>
kubectl describe statefulset <name> -n <namespace>
```

### 2. Check pod status

```bash
kubectl get pods -n <namespace> -l app.kubernetes.io/name=<statefulset-name>
# Or use the selector from the StatefulSet
kubectl get pods -n <namespace> -l <selector-from-describe>
```

### 3. Check events

```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <statefulset-name>
```

## Common Causes

### 1. PVC Not Binding (Most Common)

**Symptoms:**
- Pod stuck in `Pending`
- Event: "pod has unbound immediate PersistentVolumeClaims"

**Verification:**
```bash
kubectl get pvc -n <namespace> | grep <statefulset-name>
kubectl describe pvc <pvc-name> -n <namespace>
```

**Resolution Options:**

**Option A: Fix storage provisioner**
```bash
# Check Mayastor status
kubectl get pods -n mayastor
kubectl get diskpool -n mayastor

# Check if storage class exists
kubectl get storageclass
```

**Option B: Create manual PV**
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: <pv-name>
spec:
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteOnce
  nfs:
    server: 10.40.0.10
    path: /mnt/tank/<path>
  storageClassName: <matching-class>
```

**Option C: Delete if orphaned**
```bash
# If StatefulSet shouldn't exist in this cluster
kubectl delete statefulset <name> -n <namespace>
kubectl delete pvc -l app.kubernetes.io/name=<name> -n <namespace>
```

### 2. Insufficient Resources

**Symptoms:**
- Pod stuck in `Pending`
- Event: "Insufficient cpu/memory"

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
kubectl top nodes
```

**Resolution:**
- Scale down other workloads
- Reduce StatefulSet resource requests
- Add cluster capacity

### 3. Image Pull Issues

**Symptoms:**
- Pod in `ImagePullBackOff` or `ErrImagePull`

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
```

**Resolution:**
- Fix image reference
- Add image pull secrets

### 4. Pod Security / RBAC Issues

**Symptoms:**
- Pod fails to start
- Permission denied errors in logs

**Verification:**
```bash
kubectl logs <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```

**Resolution:**
- Fix SecurityContext settings
- Create required ServiceAccount
- Add necessary RBAC permissions

### 5. Orphaned StatefulSet in Wrong Cluster

**Symptoms:**
- StatefulSet exists but shouldn't be in this cluster
- ArgoCD app points to different cluster

**Verification:**
```bash
# Check ArgoCD app destination
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.destination.server}'
# Compare with current cluster API
```

**Resolution:**
```bash
# Delete orphaned resources
kubectl delete statefulset <name> -n <namespace>
kubectl delete pvc -l app.kubernetes.io/name=<name> -n <namespace>

# For Prometheus/AlertManager, delete the CR first
kubectl delete prometheus <name> -n <namespace>
kubectl delete alertmanager <name> -n <namespace>
```

## Resolution Steps

### Step 1: Identify the issue

```bash
kubectl describe statefulset <name> -n <namespace>
kubectl get pods -n <namespace> -l <selector>
```

### Step 2: Check why pods aren't ready

```bash
kubectl describe pod <pod-name> -n <namespace>
```

### Step 3: Fix based on cause

See "Common Causes" above.

### Step 4: Verify resolution

```bash
kubectl get statefulset <name> -n <namespace>
# READY should match REPLICAS
```

## Special Case: Monitoring Stack in Prod Cluster

The prod cluster should NOT have Prometheus/AlertManager StatefulSets. The monitoring stack runs in the monit cluster.

**Verification:**
```bash
# These shouldn't exist in prod
kubectl get statefulset -n monitoring
# prometheus-kube-prometheus-stack-prometheus - SHOULD NOT EXIST
# alertmanager-kube-prometheus-stack-alertmanager - SHOULD NOT EXIST

# The ArgoCD app points to monit cluster
kubectl get application kube-prometheus-stack -n argocd -o jsonpath='{.spec.destination.server}'
# Should show: https://10.30.0.20:6443
```

**Resolution:**
```bash
# Delete orphaned CRs (this removes StatefulSets automatically)
kubectl delete prometheus kube-prometheus-stack-prometheus -n monitoring
kubectl delete alertmanager kube-prometheus-stack-alertmanager -n monitoring

# Clean up PVCs
kubectl delete pvc -n monitoring -l app.kubernetes.io/instance=kube-prometheus-stack
```

## Escalation

If StatefulSet remains mismatched:

1. Check operator status (if StatefulSet is managed by an operator)
2. Review StatefulSet update strategy
3. Check node availability for pod scheduling
4. Verify storage backend health

## Prevention

1. **Proper cluster targeting:** Ensure ArgoCD apps deploy to correct cluster
2. **Storage planning:** Verify storage classes work before deploying StatefulSets
3. **Resource quotas:** Prevent over-scheduling
4. **Regular cleanup:** Remove orphaned resources

## Related Alerts

- `KubePodNotReady` - Pods not ready
- `KubeDeploymentReplicasMismatch` - Similar for Deployments
- `KubeContainerWaiting` - Containers stuck waiting

## Historical Incidents

### January 2026 - AlertManager StatefulSet in Prod
- **Affected:** alertmanager-kube-prometheus-stack-alertmanager in prod cluster
- **Cause:** Orphaned StatefulSet from old deployment, PVC had no storageClassName
- **Symptom:** StatefulSet showing 0/1 ready for 31 days
- **Resolution:** Deleted AlertManager CR and associated resources
- **Lesson:** Monitoring stack belongs in monit cluster only

### January 2026 - Prometheus StatefulSet in Prod
- **Affected:** prometheus-kube-prometheus-stack-prometheus in prod cluster
- **Same root cause and resolution as AlertManager above**
