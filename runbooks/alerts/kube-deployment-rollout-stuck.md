# KubeDeploymentRolloutStuck

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeDeploymentRolloutStuck |
| **Severity** | Warning |
| **Threshold** | Deployment not progressing for 15+ minutes |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a Kubernetes Deployment's rollout is not making progress. This typically indicates:
- New pods can't start (image pull, config errors)
- New pods are failing health checks
- Insufficient cluster resources
- PVC binding issues

## Quick Diagnosis

### 1. Identify the stuck deployment

```bash
# From alert labels, get deployment name and namespace
# Example: deployment=my-app, namespace=ai-platform

# Check deployment status
kubectl get deployment <deployment-name> -n <namespace> -o wide
kubectl describe deployment <deployment-name> -n <namespace>
```

### 2. Check rollout status

```bash
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

### 3. Check pod status

```bash
kubectl get pods -n <namespace> -l app=<deployment-name>
kubectl describe pods -n <namespace> -l app=<deployment-name>
```

## Common Causes

### 1. CreateContainerConfigError (Most Common)

**Symptoms:**
- Pod status: `CreateContainerConfigError`
- Missing secrets, configmaps, or environment variables

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
# Look for: "couldn't find key X in Secret/ConfigMap"
```

**Resolution:**
```bash
# Check if required secret exists
kubectl get secret <secret-name> -n <namespace>

# Check secret contents (keys only)
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data}' | jq 'keys'

# If secret is missing, check Infisical sync
kubectl get infisicalsecret -n <namespace>
kubectl describe infisicalsecret <name> -n <namespace>
```

### 2. ImagePullBackOff

**Symptoms:**
- Pod status: `ImagePullBackOff` or `ErrImagePull`
- Image doesn't exist or registry auth failed

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
# Look for: "Failed to pull image"
```

**Resolution:**
```bash
# Check image name in deployment
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[*].image}'

# Verify image exists (for public images)
docker manifest inspect <image:tag>

# Check image pull secrets
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.imagePullSecrets}'
```

### 3. Insufficient Resources

**Symptoms:**
- Pod status: `Pending`
- No node has sufficient CPU/memory

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
# Look for: "Insufficient cpu" or "Insufficient memory"

# Check node resources
kubectl top nodes
kubectl describe nodes | grep -A 5 "Allocated resources"
```

**Resolution:**
- Reduce resource requests in deployment
- Scale down other workloads
- Add more nodes

### 4. PVC Binding Issues

**Symptoms:**
- Pod status: `Pending`
- PVC can't be bound

**Verification:**
```bash
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>
# Look for: "waiting for a volume to be created"
```

**Resolution:**
```bash
# Check storage classes
kubectl get storageclass

# Check if storage provisioner is healthy
kubectl get pods -n mayastor
kubectl get pods -n openebs
```

### 5. Failed Liveness/Readiness Probes

**Symptoms:**
- Pod starts but gets killed repeatedly
- Pod shows `Running` but `0/1 Ready`

**Verification:**
```bash
kubectl logs <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A 20 "Liveness:"
```

**Resolution:**
- Fix application startup issues
- Increase `initialDelaySeconds` in probes
- Fix probe endpoints

## Resolution Steps

### Step 1: Identify the root cause

```bash
# Get deployment status
kubectl describe deployment <name> -n <namespace>

# Get pod events
kubectl get pods -n <namespace> -l app=<name>
kubectl describe pods -n <namespace> -l app=<name> | tail -30
```

### Step 2: Fix based on cause

**For CreateContainerConfigError:**
```bash
# Create missing secret/configmap or fix reference
kubectl get secret,configmap -n <namespace>
```

**For ImagePullBackOff:**
```bash
# Fix image tag or add pull secret
kubectl set image deployment/<name> <container>=<correct-image> -n <namespace>
```

**For resource issues:**
```bash
# Scale down or adjust resources
kubectl scale deployment/<name> --replicas=0 -n <namespace>
kubectl edit deployment/<name> -n <namespace>  # Reduce requests
kubectl scale deployment/<name> --replicas=1 -n <namespace>
```

### Step 3: Restart rollout if needed

```bash
# Cancel current rollout
kubectl rollout undo deployment/<name> -n <namespace>

# Or restart fresh
kubectl rollout restart deployment/<name> -n <namespace>
```

### Step 4: Verify resolution

```bash
kubectl rollout status deployment/<name> -n <namespace>
kubectl get pods -n <namespace> -l app=<name>
```

## Special Cases

### Orphaned Deployments in Wrong Cluster

Sometimes deployments get created in the wrong cluster (e.g., agentic workloads appearing in prod).

**Verification:**
```bash
# Check if ArgoCD manages this deployment
kubectl get applications -n argocd | grep <deployment-name>

# Check ArgoCD app destination
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.destination.server}'
```

**Resolution:**
```bash
# If orphaned (not managed by ArgoCD pointing to this cluster)
kubectl delete deployment <name> -n <namespace>
```

### YAML Syntax Errors in ConfigMaps

**Symptoms:**
- ArgoCD shows "Unknown" status
- Application won't sync

**Verification:**
```bash
# Check ArgoCD app status
kubectl get application <name> -n argocd -o yaml | grep -A 10 "status:"

# Look for YAML parsing errors
```

**Resolution:**
- Fix YAML syntax in source repository
- Common issues: incorrect indentation, missing quotes, invalid characters

## Escalation

If deployment remains stuck after troubleshooting:

1. Check ArgoCD application sync status
2. Review recent git commits to the deployment
3. Check cluster events: `kubectl get events -n <namespace> --sort-by='.lastTimestamp'`
4. Review application logs if pod starts: `kubectl logs <pod-name> -n <namespace>`

## Prevention

1. **Test configs locally:** Validate YAML before committing
2. **Use kustomize build:** `kustomize build . | kubectl apply --dry-run=client -f -`
3. **Staged rollouts:** Use canary or blue-green deployments
4. **Resource quotas:** Prevent over-scheduling

## Related Alerts

- `KubeDeploymentReplicasMismatch` - Replicas don't match spec
- `KubeContainerWaiting` - Container stuck waiting
- `KubePodNotReady` - Pod not passing readiness checks

## Historical Incidents

(No historical incidents documented)
