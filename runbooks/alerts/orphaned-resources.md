# Orphaned Resources in Wrong Cluster

## Overview

This runbook covers the detection and cleanup of Kubernetes resources that exist in the wrong cluster. This commonly happens when:
- ArgoCD app destination changed but old resources remain
- Manual deployments weren't cleaned up
- Multi-cluster setup confusion
- Copy-paste errors in manifests

## Symptoms

Alerts that may indicate orphaned resources:
- `KubePodNotReady` - Pods pending due to missing dependencies
- `KubeContainerWaiting` - Containers waiting for missing secrets
- `KubeDeploymentRolloutStuck` - Deployments stuck
- `KubeStatefulSetReplicasMismatch` - StatefulSets stuck

**Key Indicator:** Resources exist but their ArgoCD application points to a different cluster.

## Diagnosis

### Step 1: Identify the resource's expected location

```bash
# Find the ArgoCD application managing this resource
kubectl get applications -n argocd | grep <resource-name>

# Check destination cluster
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.destination.server}'
```

**Cluster API Endpoints:**
| Cluster | API Server | Network |
|---------|------------|---------|
| Prod | https://10.10.0.40:6443 or https://kubernetes.default.svc | 10.10.0.0/24 |
| Agentic | https://10.20.0.40:6443 | 10.20.0.0/24 |
| Monit | https://10.30.0.20:6443 | 10.30.0.0/24 |

### Step 2: Check where resource actually exists

```bash
# Prod cluster
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl get <resource-type> <name> -n <namespace>

# Agentic cluster
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get <resource-type> <name> -n <namespace>

# Monit cluster
KUBECONFIG=/home/monit_homelab/kubeconfig \
  kubectl get <resource-type> <name> -n <namespace>
```

### Step 3: Determine if orphaned

If the resource exists in a different cluster than its ArgoCD app destination, it's orphaned.

## Common Orphaned Resource Types

### 1. Agentic Workloads in Prod Cluster

**Examples:**
- claude-validator deployment in prod
- AI platform components in prod

**Why it happens:**
- ArgoCD apps point to agentic cluster (10.20.0.40)
- But old resources exist in prod from previous deployments

**Verification:**
```bash
# Check if ai-platform namespace exists in prod
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl get pods -n ai-platform
```

**Resolution:**
```bash
# Delete orphaned workloads from prod
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl delete deployment <name> -n ai-platform
```

### 2. Monitoring Stack in Prod Cluster

**What Should Exist Where:**
| Component | Prod | Monit |
|-----------|------|-------|
| kube-prometheus-stack | Only agents (node-exporter, kube-state-metrics) | Full stack |
| Prometheus | NO | YES |
| AlertManager | NO | YES |
| Grafana | NO | YES |
| Gatus | NO | YES |
| Victoria Metrics | NO | YES |

**Verification:**
```bash
# These should NOT exist in prod
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl get statefulset,deployment -n monitoring | grep -E "prometheus-kube|alertmanager|grafana|gatus"
```

**Resolution:**
```bash
# Delete orphaned monitoring components from prod
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig kubectl delete prometheus kube-prometheus-stack-prometheus -n monitoring
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig kubectl delete alertmanager kube-prometheus-stack-alertmanager -n monitoring
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig kubectl delete deployment gatus kube-prometheus-stack-grafana -n monitoring
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig kubectl delete pvc -l app.kubernetes.io/instance=kube-prometheus-stack -n monitoring
```

### 3. Stale ReplicaSets and Pods

**Symptoms:**
- Old pods in `Completed` or `Error` state
- ReplicaSets with 0 desired replicas still existing

**Verification:**
```bash
kubectl get pods -A | grep -E "Completed|Error" | grep -v "job"
kubectl get rs -A | awk '$2==0 && $3==0 && $4==0'
```

**Resolution:**
```bash
# Delete completed/errored pods
kubectl delete pods -A --field-selector=status.phase=Succeeded
kubectl delete pods -A --field-selector=status.phase=Failed

# Delete empty replicasets (be careful - verify they're truly orphaned)
```

## Cleanup Procedure

### Full Orphaned Resource Cleanup

```bash
# Set the cluster to clean
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig

# Step 1: List potentially orphaned resources
kubectl get pods -A | grep -E "Pending|Error|CreateContainer"
kubectl get deployments -A | awk '$3==0'
kubectl get statefulsets -A | awk '$2=="0/1" || $2=="0/2"'

# Step 2: For each, verify if ArgoCD manages it and where
kubectl get applications -n argocd | grep <name>

# Step 3: Delete confirmed orphans
kubectl delete <resource-type> <name> -n <namespace>
```

## Prevention

### 1. Clear Cluster Targeting
Always verify ArgoCD app destination before creating:
```yaml
spec:
  destination:
    server: https://10.20.0.40:6443  # Be explicit about cluster
    namespace: ai-platform
```

### 2. Namespace Strategy
Use cluster-specific namespaces when possible:
- `ai-platform` - Only in agentic cluster
- `monitoring` - Different contents per cluster

### 3. Regular Audits
Periodically check for orphaned resources:
```bash
# Quick audit script
for cluster in prod agentic monit; do
  echo "=== $cluster ==="
  case $cluster in
    prod) export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig ;;
    agentic) export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig ;;
    monit) export KUBECONFIG=/home/monit_homelab/kubeconfig ;;
  esac
  kubectl get pods -A | grep -E "Pending|Error|CreateContainer" | wc -l
done
```

### 4. Labeling Convention
Label resources with their intended cluster:
```yaml
metadata:
  labels:
    cluster: agentic
```

## Checklist: Is This Resource Orphaned?

- [ ] Does an ArgoCD application manage it?
- [ ] If yes, what cluster does the app target?
- [ ] Does the resource exist in that target cluster?
- [ ] If resource is in wrong cluster, is there a running version in the correct cluster?
- [ ] Are there any dependencies on this orphaned resource?

If all checks pass, the resource can be safely deleted.

## Historical Incidents

### January 2026 - claude-validator in Prod Cluster
- **Issue:** claude-validator deployment existed in prod cluster
- **Root Cause:** ArgoCD app targets agentic, but old deployment remained in prod
- **Symptom:** CreateContainerConfigError (missing ANTHROPIC_API_KEY secret)
- **Resolution:** Deleted deployment from prod cluster

### January 2026 - Monitoring Stack in Prod Cluster
- **Issue:** Full kube-prometheus-stack in prod (prometheus, alertmanager, grafana, gatus)
- **Root Cause:** Old deployment, ArgoCD app now targets monit cluster
- **Symptom:** StatefulSets stuck pending (PVCs without storage class)
- **Resolution:** Deleted prometheus/alertmanager CRs, deployments, PVCs from prod

## Related Runbooks

- `kube-pod-not-ready.md` - Often caused by orphaned resources
- `kube-container-waiting.md` - Missing secrets in wrong cluster
- `kube-statefulset-replicas-mismatch.md` - Storage issues in wrong cluster
