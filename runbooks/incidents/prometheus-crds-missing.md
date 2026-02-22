# Prometheus CRD Missing - TargetDown Alert

**Status**: Resolved
**Date**: 2026-02-22
**Alert**: TargetDown (argocd-metrics)
**Root Cause**: Prometheus CRD resource deleted from monitoring cluster

## Incident Summary

When the Prometheus CRD resource (`monitoring.coreos.com/v1`) is deleted from the monitoring cluster, **all Prometheus scrape targets are reported as down**, including argocd-metrics, talos-kubelets, node-exporter, etc. This causes a cascade of TargetDown warnings.

ArgoCD incorrectly reports the Prometheus resource as "Synced" even though the actual CRD is missing. The Prometheus Operator continues to run normally, but with no Prometheus instance, no metrics are scraped.

## Root Cause Analysis

1. **Missing Prometheus CRD**: The `kube-prometheus-stack-prometheus` resource was deleted (manually or via misconfiguration)
2. **ArgoCD State Mismatch**: ArgoCD Application still tracked the Prometheus resource as "Synced" but didn't notice it was missing
3. **No Alerts on CRD Deletion**: The monitoring stack had no alert to catch this condition (see Mitigation)

## Symptoms

- Alert: `TargetDown` for multiple jobs (argocd-metrics, talos-kubelets, etc.)
- Severity: warning (or critical if all targets down)
- Prometheus service exists but has no pods
- ArgoCD Application status: "Healthy" (misleading!)

## Resolution

### Quick Fix
Force ArgoCD to re-sync the kube-prometheus-stack Application:

```bash
# Patch the app to trigger a sync
kubectl --kubeconfig=/root/.kube/config -n argocd \
  patch app kube-prometheus-stack --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/sync":""}}}'

# Verify Prometheus is recreated
kubectl --kubeconfig=/home/monit_homelab/kubeconfig -n monitoring \
  get prometheus kube-prometheus-stack-prometheus
```

### Verification

```bash
# Check Prometheus pod is running
kubectl --kubeconfig=/home/monit_homelab/kubeconfig -n monitoring \
  get pod -l app.kubernetes.io/name=prometheus

# Verify service endpoints
kubectl --kubeconfig=/home/monit_homelab/kubeconfig -n monitoring \
  get endpoints kube-prometheus-stack-prometheus

# Check TargetDown alert is resolved
argocd app get kube-prometheus-stack --refresh
```

## Permanent Prevention

### 1. Protect Prometheus CRD from Accidental Deletion
Add a finalizer or kubectl plugin to prevent accidental deletion:

```bash
# Add deletion protection via annotation
kubectl --kubeconfig=/home/monit_homelab/kubeconfig -n monitoring \
  annotate prometheus kube-prometheus-stack-prometheus \
  "argocd.argoproj.io/sync-wave=1" \
  --overwrite
```

### 2. Create Alert Rule for Missing Prometheus CRD
Add to `/home/monit_homelab/kubernetes/platform/prometheus-rules/homelab-rules.yaml`:

```yaml
- alert: PrometheusDown
  expr: |
    absent(up{job="prometheus"}) or
    absent(kube_prometheus_stack_prometheus_up)
  for: 5m
  labels:
    severity: critical
    cluster: monitoring
  annotations:
    summary: "Prometheus is not available"
    description: "The Prometheus instance in monitoring cluster is down or missing."
    runbook_url: "https://github.com/charlieshreck/kernow-homelab/blob/main/agentic_lab/runbooks/incidents/prometheus-crds-missing.md"
```

### 3. Document in Runbook Database
Register this runbook pattern in the knowledge base so future incidents can be auto-matched.

## Related Incidents

- Incident #114: TargetDown (argocd-metrics) - Feb 22 2026

## Lessons Learned

1. **ArgoCD Health != Actual Health**: ArgoCD's "Synced" status doesn't verify resources actually exist; it only verifies Git ↔ ArgoCD agreement
2. **Service Without Endpoints**: A Service can exist with 0 endpoints (scrape target = down)
3. **CRD Operator Separation**: Prometheus Operator (running fine) ≠ Prometheus (CRD needed)

## References

- [Prometheus Operator Docs](https://prometheus-operator.dev/)
- [ArgoCD Application Health Assessment](https://argo-cd.readthedocs.io/en/stable/operator-manual/health-assessment/)
- Monitoring Cluster: `/home/monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`
