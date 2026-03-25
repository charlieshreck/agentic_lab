# Gatus Deployment Provisioning & Infrastructure Setup

## Problem

Gatus health check pod (monit cluster) was not running despite ArgoCD showing "Synced" status. Health checks were timing out for all endpoints, particularly the Homepage check. Root cause: Gatus infrastructure components were defined in git but not actually provisioned on the cluster.

**Incident #504**: Homepage endpoint health check timeout (RESOLVED 2026-03-25)

## Root Causes

Three-layer provisioning failure:

### 1. InfisicalSecret Resources Not Applied
- **Symptom**: ArgoCD showed resources synced, but InfisicalSecret CRD objects didn't exist on cluster
- **Cause**: While Kubernetes manifests were in git and ArgoCD tracked them, the InfisicalSecret resources themselves weren't applied
- **Impact**: Secrets couldn't be provisioned; Gatus pod couldn't start

### 2. PersistentVolumeClaim Without Storage Class
- **Symptom**: PVC created but remained in `Pending` state; no volume binding
- **Cause**: PVC spec lacked `storageClassName: mayastor-single-replica`
- **Impact**: Gatus pod couldn't mount data volume; pod creation blocked

### 3. Kubernetes Secrets Not Provisioned by Infisical Operator
- **Symptom**: Pod creation failed with "secret 'gatus-discord-webhook' not found"
- **Cause**: InfisicalSecret resources existed but Infisical operator hadn't processed them yet to create actual Kubernetes secrets
- **Impact**: Pod lacked required environment variables for Discord and Keep integrations

## Solution

### Step 1: Ensure InfisicalSecret Resources Exist
```bash
# Apply the InfisicalSecret definitions to monit cluster
kubectl apply -f monit_homelab/kubernetes/platform/gatus/infisical-secret.yaml \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster
```

**Expected output**:
```
infisicalsecret.secrets.infisical.com/gatus-keep-apikey created
infisicalsecret.secrets.infisical.com/gatus-discord-webhook created
```

### Step 2: Add Storage Class to PVC Spec
**File**: `monit_homelab/kubernetes/platform/gatus/deployment.yaml` (ConfigMap section, around line 681)

Update the PersistentVolumeClaim:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: gatus-data
  namespace: monitoring
spec:
  storageClassName: mayastor-single-replica  # ← ADD THIS LINE
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

### Step 3: Wait for Infisical Operator or Create Secrets Manually
If Infisical operator doesn't auto-provision after a few minutes, manually create the Kubernetes secrets:

```bash
# Get secret values from Infisical
DISCORD_WEBHOOK=$(infisical secrets get --path=/external/discord WEBHOOK_INFRA_ALERTS --plain)
KEEP_API_KEY=$(infisical secrets get --path=/observability/keep API_KEY --plain)

# Create secrets on monit cluster
kubectl create secret generic gatus-discord-webhook \
  --from-literal=WEBHOOK_INFRA_ALERTS="$DISCORD_WEBHOOK" \
  -n monitoring \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster

kubectl create secret generic gatus-keep-apikey \
  --from-literal=API_KEY="$KEEP_API_KEY" \
  -n monitoring \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster
```

### Step 4: Apply/Re-apply Gatus Deployment
```bash
# Apply the full Gatus deployment (includes ConfigMap, PVC with storageClassName, Deployment)
kubectl apply -f monit_homelab/kubernetes/platform/gatus/deployment.yaml \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster
```

### Step 5: Verify Pod Health
```bash
# Check pod status (should transition to Running within 30-60s)
kubectl get pods -n monitoring -l app=gatus -o wide \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster

# Check recent logs for health check activity
kubectl logs -n monitoring -l app=gatus --tail=30 \
  --kubeconfig=/root/.kube/config \
  --context=admin@monitoring-cluster | grep Homepage
```

Expected log output when healthy:
```
[watchdog.executeEndpoint] Monitored group=Apps; endpoint=Homepage; key=apps_homepage; success=true; errors=0; duration=16ms
```

## Prevention

### Multi-Cluster Synchronization Pattern

Talos clusters (prod, agentic, monit) use ArgoCD for declarative management, BUT:
- **ArgoCD only tracks Kubernetes resources** — it can't ensure CRD instances exist if they're not applied
- **InfisicalSecret CRDs require explicit resource creation** — just having the operator doesn't auto-create the resources

### Best Practice: Check Cluster State

Before relying on ArgoCD sync status:
```bash
# Verify ACTUAL resources exist, not just manifest tracking
kubectl get -n monitoring infisicalsecrets gatus-discord-webhook
kubectl get -n monitoring secret gatus-discord-webhook
kubectl get -n monitoring pvc gatus-data

# If missing, investigate:
# 1. Are manifests in git? (git log --oneline kubernetes/platform/gatus/)
# 2. Are manifests in ArgoCD tracking? (kubectl get application gatus -n argocd)
# 3. Are ACTUAL resources provisioned? (kubectl get <resource-type> -n monitoring)
```

### Storage Class Specification

Always include `storageClassName` for every PVC:
```yaml
spec:
  storageClassName: mayastor-single-replica  # Required on Talos clusters with MayaStor
```

For different storage:
- **Talos prod/agentic/monit**: Use `mayastor-single-replica` (OpenEBS MayaStor)
- **K3s clusters**: May have different storage classes (check via `kubectl get storageclass`)

## Verification Checklist

- [ ] `kubectl get pvc -n monitoring gatus-data` shows `Bound` status
- [ ] `kubectl get pods -n monitoring -l app=gatus` shows pod in `Running` state with 1/1 Ready
- [ ] `kubectl logs -n monitoring -l app=gatus | grep Homepage` shows `success=true`
- [ ] Gatus web UI at `https://gatus.kernow.io/` displays Homepage endpoint as "UP"
- [ ] ArgoCD Application `gatus` (monit cluster context) shows all resources in sync
- [ ] Incident #504 resolved and closed

## References

- **Manifests**: `monit_homelab/kubernetes/platform/gatus/`
- **InfisicalSecret CRD**: Infisical operator in `infisical-operator-system` namespace
- **Storage**: OpenEBS MayaStor single-replica provisioner on Talos
- **Knowledge Base**: Gatus health check pattern, Infisical operator provisioning

## Related

- [Gatus S3 Health Check Configuration](./gatus-s3-health-check.md) — S3 API endpoint condition tuning
- [Infisical Integration Pattern](../infrastructure/infisical-integration.md) — Secret provisioning overview
