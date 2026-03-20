# Reflector OOM Prevention Runbook

## Overview
Kubernetes Reflector (emberstack/kubernetes-reflector) is used to mirror Secrets and ConfigMaps across namespaces. It requires explicit memory limits to prevent OOM kills.

## Issue History
- **Incident #538 / Finding #1277** (2026-03-20): Reflector pod OOM killed on **monit cluster** after running for ~2 days
- **Root cause**: .NET runtime slow memory leak — gradual accumulation over time, not a spike. 128Mi limit was insufficient for multi-day operation.
- **Fix**: Memory limit raised to 192Mi across all three clusters (2026-03-20)

## Cluster Configuration

### Prod Cluster (Helm-managed)
**File**: `kubernetes/argocd-apps/platform/reflector-app.yaml`

Reflector deployed via Helm chart with explicit resource limits:
```yaml
helm:
  values: |
    resources:
      requests:
        cpu: 10m
        memory: 64Mi
      limits:
        cpu: 100m
        memory: 192Mi
```

### Agentic & Monit Clusters (Manifest-managed)
**Files**:
- `agentic_lab/kubernetes/platform/reflector/deployment.yaml`
- `monit_homelab/kubernetes/platform/reflector/deployment.yaml`

Direct Kubernetes manifests with resource limits:
```yaml
resources:
  requests:
    cpu: 10m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 192Mi
```

## QoS Class Implications

| QoS Class | Resource Limits | Behavior | Risk |
|-----------|----------------|----------|------|
| **Guaranteed** | Requests = Limits | Reserved capacity | Low |
| **Burstable** | Request < Limit | Can burst, then throttled | Medium |
| **BestEffort** | No limits | Compete for node resources | **HIGH - OOM Kill risk** |

**BestEffort pods are the first to be evicted when node memory is needed.**

## Standard Resource Allocation
- **CPU request**: 10m (0.01 core)
- **CPU limit**: 100m (0.1 core)
- **Memory request**: 64Mi
- **Memory limit**: 192Mi

This allocation is:
- Sufficient for multi-day continuous operation (tested: 2+ days without OOM)
- 50% headroom over previous 128Mi limit to account for .NET GC slow leak
- Applied consistently across all three clusters

## Verification

After ArgoCD sync, verify the prod reflector pod has correct limits:

```bash
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig
kubectl get pod -n kube-system -l app=reflector -o yaml | grep -A 10 resources:
```

Expected output:
```yaml
resources:
  limits:
    cpu: 100m
    memory: 192Mi
  requests:
    cpu: 10m
    memory: 64Mi
```

Verify QoS class is `Burstable`:
```bash
kubectl get pod -n kube-system -l app=reflector -o jsonpath='{.items[0].status.qosClass}'
# Output: Burstable
```

## Monitoring

- **Metric**: `container_memory_usage_bytes` for reflector pod
- **Alert**: If memory approaches 100Mi, investigate namespace mirroring load
- **Dashboard**: Coroot service metrics (infrastructure-mcp tool: `coroot_get_service_metrics`)

## Related Resources
- Kubernetes QoS docs: https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/
- Reflector project: https://github.com/emberstack/kubernetes-reflector
- Incident #538: HomelabPodOOMKilled (2026-03-20)
