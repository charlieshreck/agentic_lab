# Talos Linux - False Positive Alerts

## Overview

Talos Linux is an immutable, API-driven operating system designed for Kubernetes. Due to its unique architecture, several standard Kubernetes monitoring alerts are **false positives** because Talos doesn't expose certain metrics that traditional Linux distributions do.

This runbook documents these false positives and how to handle them.

---

## KubeProxyDown

### Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeProxyDown |
| **Severity** | Critical |
| **Is False Positive** | YES - Always on Talos |

### Why It's a False Positive

**Talos uses Cilium as kube-proxy replacement.** There is no kube-proxy component running.

Cilium provides:
- Service load balancing (replaces kube-proxy iptables/ipvs)
- Network policy enforcement
- Pod networking

### Verification

```bash
# Confirm no kube-proxy exists
kubectl get pods -n kube-system | grep kube-proxy
# Should return nothing

# Confirm Cilium is handling proxy functions
kubectl get pods -n kube-system -l k8s-app=cilium
# Should show running cilium agents

# Check Cilium status
kubectl exec -n kube-system -l k8s-app=cilium -- cilium status
```

### Permanent Resolution

**Delete the ServiceMonitor that creates this false target:**

```bash
kubectl delete servicemonitor kube-prometheus-stack-kube-proxy -n monitoring
```

**Or silence the alert permanently:**

```bash
# Create silence via AlertManager API or monitoring-mcp
mcp__monitoring__create_silence alertname=KubeProxyDown comment="Talos uses Cilium - no kube-proxy" duration_hours=8760
```

---

## KubeSchedulerDown

### Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeSchedulerDown |
| **Severity** | Critical |
| **Is False Positive** | YES - Talos doesn't expose scheduler metrics |

### Why It's a False Positive

**Talos runs kube-scheduler but doesn't expose its metrics endpoint** in a way that Prometheus can scrape via the standard ServiceMonitor.

The scheduler IS running and functioning correctly.

### Verification

```bash
# Check scheduler is running on control plane
talosctl -n <control-plane-ip> services | grep scheduler

# Check pods are being scheduled
kubectl get pods -A | grep -v Running  # Should be minimal
kubectl get events -A --field-selector reason=Scheduled | tail -5
```

### Permanent Resolution

**Delete the ServiceMonitor:**

```bash
kubectl delete servicemonitor kube-prometheus-stack-kube-scheduler -n monitoring
```

---

## KubeControllerManagerDown

### Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeControllerManagerDown |
| **Severity** | Critical |
| **Is False Positive** | YES - Talos doesn't expose controller-manager metrics |

### Why It's a False Positive

**Talos runs kube-controller-manager but doesn't expose its metrics endpoint** to Prometheus.

The controller-manager IS running and functioning correctly.

### Verification

```bash
# Check controller-manager is running on control plane
talosctl -n <control-plane-ip> services | grep controller

# Check controllers are working (deployments scaling, etc.)
kubectl get deployments -A
kubectl get events -A --field-selector reason=ScalingReplicaSet | tail -5
```

### Permanent Resolution

**Delete the ServiceMonitor:**

```bash
kubectl delete servicemonitor kube-prometheus-stack-kube-controller-manager -n monitoring
```

---

## TargetDown (kube-scheduler, kube-controller-manager)

### Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | TargetDown |
| **Severity** | Warning |
| **Is False Positive** | YES - When targeting kube-scheduler or kube-controller-manager on Talos |

### Why It's a False Positive

Related to the above alerts - the ServiceMonitors create scrape targets that don't exist on Talos.

### Permanent Resolution

Delete the associated ServiceMonitors (see above).

---

## Bulk Fix: Delete All False Positive ServiceMonitors

```bash
# Delete all Talos-incompatible ServiceMonitors at once
kubectl delete servicemonitor -n monitoring \
  kube-prometheus-stack-kube-proxy \
  kube-prometheus-stack-kube-scheduler \
  kube-prometheus-stack-kube-controller-manager

# Verify they're gone
kubectl get servicemonitor -n monitoring | grep -E "proxy|scheduler|controller"
```

## GitOps Fix (Recommended)

For a proper GitOps approach, disable these in the kube-prometheus-stack Helm values:

```yaml
# In kube-prometheus-stack values
kubeProxy:
  enabled: false

kubeScheduler:
  enabled: false

kubeControllerManager:
  enabled: false

# Keep these enabled (they work on Talos)
kubeApiserver:
  enabled: true

kubelet:
  enabled: true

kubeStateMetrics:
  enabled: true

nodeExporter:
  enabled: true
```

## Talos Metrics That DO Work

These components expose metrics normally on Talos:

| Component | Status | ServiceMonitor |
|-----------|--------|----------------|
| kube-apiserver | Works | Keep enabled |
| kubelet | Works | Keep enabled |
| node-exporter | Works | Keep enabled |
| kube-state-metrics | Works | Keep enabled |
| etcd | Works (if configured) | Optional |

## Summary Table

| Alert | False Positive | Reason | Fix |
|-------|---------------|--------|-----|
| KubeProxyDown | YES | Cilium replaces kube-proxy | Delete ServiceMonitor |
| KubeSchedulerDown | YES | Metrics not exposed | Delete ServiceMonitor |
| KubeControllerManagerDown | YES | Metrics not exposed | Delete ServiceMonitor |
| TargetDown (scheduler) | YES | No target exists | Delete ServiceMonitor |
| TargetDown (controller-manager) | YES | No target exists | Delete ServiceMonitor |
| TargetDown (kube-proxy) | YES | No target exists | Delete ServiceMonitor |

## Related Documentation

- [Talos Linux Documentation](https://www.talos.dev/docs/)
- [Cilium kube-proxy Replacement](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
- [kube-prometheus-stack Talos Configuration](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
