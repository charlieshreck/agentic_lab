# KubeContainerWaiting

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeContainerWaiting |
| **Severity** | Warning |
| **Threshold** | Container waiting for 1+ hour |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a container has been stuck in a waiting state for more than 1 hour. The waiting reason is typically included in the alert (e.g., `CreateContainerConfigError`, `ImagePullBackOff`).

## Quick Diagnosis

### 1. Identify the affected container

```bash
# From alert labels
# Example: container=claude-validator, pod=claude-validator-55bd4dfcc8-9q9rf, reason=CreateContainerConfigError

kubectl get pod <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```

### 2. Check the waiting reason

```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].state.waiting}'
```

## Waiting Reasons and Resolutions

### CreateContainerConfigError

**Description:** Container can't start due to missing configuration (secrets, configmaps, service accounts).

**Common Causes:**
- Referenced Secret doesn't exist
- Referenced ConfigMap doesn't exist
- Secret/ConfigMap exists but missing required key
- ServiceAccount doesn't exist

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
# Look for: "couldn't find key X in Secret/ConfigMap Y"
```

**Resolution for Missing Secret:**
```bash
# Check if secret exists
kubectl get secret <secret-name> -n <namespace>

# If using Infisical, check sync status
kubectl get infisicalsecret -n <namespace>
kubectl describe infisicalsecret <name> -n <namespace>

# Check Infisical operator logs
kubectl logs -n infisical-operator-system -l app.kubernetes.io/name=infisical-operator --tail=50
```

**Resolution for Missing Key:**
```bash
# Check what keys exist in the secret
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data}' | jq 'keys'

# Compare with what the deployment expects
kubectl get deployment <name> -n <namespace> -o yaml | grep -A 10 "secretKeyRef"
```

**Resolution for Missing ConfigMap:**
```bash
# Check if configmap exists
kubectl get configmap <configmap-name> -n <namespace>

# If managed by ArgoCD, force sync
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"operation": {"sync": {"prune": true}}}'
```

### ImagePullBackOff / ErrImagePull

**Description:** Container image cannot be pulled from registry.

**Common Causes:**
- Image doesn't exist (typo in tag)
- Private registry requires authentication
- Registry is temporarily unavailable
- Image was deleted from registry

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Events:"
# Look for: "Failed to pull image"

# Check image name
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].image}'
```

**Resolution:**
```bash
# Verify image exists (for public images)
docker manifest inspect <image:tag>

# Check if imagePullSecrets are configured
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'

# If wrong image, update deployment
kubectl set image deployment/<name> <container>=<correct-image> -n <namespace>
```

### ContainerCreating (Stuck)

**Description:** Container is being created but not starting.

**Common Causes:**
- Volume mount issues
- Network plugin issues
- Node resource exhaustion

**Verification:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
```

**Resolution:**
```bash
# Check node status
kubectl describe node <node-name>

# Check CNI (Cilium) status
kubectl get pods -n kube-system -l k8s-app=cilium

# Delete and let scheduler try different node
kubectl delete pod <pod-name> -n <namespace>
```

### CrashLoopBackOff

**Description:** Container starts but crashes repeatedly.

**Note:** This alert (KubeContainerWaiting) excludes CrashLoopBackOff. See `KubePodCrashLooping` runbook instead.

### PodInitializing (Stuck)

**Description:** Init containers not completing.

**Verification:**
```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.initContainerStatuses}'
kubectl logs <pod-name> -n <namespace> -c <init-container-name>
```

**Resolution:**
- Fix init container issues
- Check init container dependencies

## Resolution Steps

### Step 1: Get detailed pod status

```bash
kubectl describe pod <pod-name> -n <namespace>
```

### Step 2: Identify the waiting reason

```bash
# Look at the Events section and Container State
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A 20 "containerStatuses"
```

### Step 3: Fix based on reason

See "Waiting Reasons and Resolutions" above.

### Step 4: Force pod recreation if needed

```bash
kubectl delete pod <pod-name> -n <namespace>
```

### Step 5: Verify resolution

```bash
kubectl get pod <pod-name> -n <namespace>
# Should show Running and Ready
```

## Special Case: Wrong Cluster Deployment

If the pod is in a cluster where it shouldn't be (e.g., agentic workload in prod):

**Verification:**
```bash
# Check ArgoCD app destination
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.destination.server}'
# Example: https://10.20.0.40:6443 = agentic cluster
# If pod is in prod but app points to agentic, it's orphaned
```

**Resolution:**
```bash
# Delete orphaned workload
kubectl delete deployment <name> -n <namespace>
```

## Escalation

If container remains waiting:

1. Check node kubelet logs: `talosctl -n <node-ip> logs kubelet`
2. Check if this affects multiple pods (cluster-wide issue)
3. Verify cluster networking is healthy
4. Check storage provisioner status

## Prevention

1. **GitOps validation:** Use `kustomize build` before committing
2. **Secret management:** Ensure Infisical paths match deployment expectations
3. **Image tagging:** Use specific tags, not `latest`
4. **Dependency ordering:** Use sync-waves in ArgoCD

## Related Alerts

- `KubeDeploymentRolloutStuck` - Deployment not progressing
- `KubePodNotReady` - Pod in non-ready state
- `KubePodCrashLooping` - Container crashing

## Historical Incidents

### January 2026 - claude-validator CreateContainerConfigError
- **Affected:** claude-validator pod in prod cluster (orphaned)
- **Reason:** `CreateContainerConfigError`
- **Cause:** Missing `ANTHROPIC_API_KEY` in secret - pod was orphaned in wrong cluster
- **Resolution:** Deleted orphaned deployment from prod cluster
- **Lesson:** ArgoCD app destination must match where workload should run

### Common Pattern - Infisical Secret Sync Delay
- **Symptom:** Pod starts before InfisicalSecret creates the actual Secret
- **Cause:** No dependency ordering between InfisicalSecret and Deployment
- **Resolution:** Add ArgoCD sync-wave annotations (InfisicalSecret before Deployment)
