# Alert Runbooks

This directory contains runbooks for responding to alerts in the Kernow Homelab monitoring stack.

## Alert Categories

### Kubernetes Workload Alerts
| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [kube-deployment-rollout-stuck.md](kube-deployment-rollout-stuck.md) | KubeDeploymentRolloutStuck | Warning |
| [kube-pod-not-ready.md](kube-pod-not-ready.md) | KubePodNotReady | Warning |
| [kube-container-waiting.md](kube-container-waiting.md) | KubeContainerWaiting | Warning |
| [kube-job-failed.md](kube-job-failed.md) | KubeJobFailed | Warning |
| [kube-statefulset-replicas-mismatch.md](kube-statefulset-replicas-mismatch.md) | KubeStatefulSetReplicasMismatch | Warning |

### Node Alerts
| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [node-memory-high-utilization.md](node-memory-high-utilization.md) | NodeMemoryHighUtilization | Warning |

### Network/CNI Alerts
| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [cilium-operator-rollout-stuck.md](cilium-operator-rollout-stuck.md) | KubeDeploymentRolloutStuck (cilium-operator) | Warning |

### Prometheus/Monitoring Alerts
| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [target-down.md](target-down.md) | TargetDown | Warning |
| [talos-false-positives.md](talos-false-positives.md) | KubeProxyDown, KubeSchedulerDown, KubeControllerManagerDown | Critical |

### Operational Issues
| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [orphaned-resources.md](orphaned-resources.md) | Various (orphaned workloads) | N/A |

## Quick Reference

### Most Common Alerts

1. **NodeMemoryHighUtilization**
   - Usually: mayastor-alloy memory leak
   - Fix: `kubectl rollout restart daemonset mayastor-alloy -n mayastor`

2. **KubeDeploymentRolloutStuck**
   - Check: `kubectl describe deployment <name> -n <namespace>`
   - Common causes: Missing secrets, image pull errors, resource constraints

3. **KubePodNotReady**
   - Check: `kubectl describe pod <name> -n <namespace>`
   - Common causes: PVC binding, resource constraints, config errors

4. **KubeContainerWaiting (CreateContainerConfigError)**
   - Check: `kubectl describe pod <name> -n <namespace> | grep Events`
   - Common causes: Missing secrets/configmaps

### Talos-Specific False Positives

These alerts are **always false positives** on Talos Linux:
- KubeProxyDown (Cilium replaces kube-proxy)
- KubeSchedulerDown (metrics not exposed)
- KubeControllerManagerDown (metrics not exposed)

**Fix:** Delete corresponding ServiceMonitors. See [talos-false-positives.md](talos-false-positives.md).

### Cluster Architecture Reference

| Cluster | Network | API Server | ArgoCD |
|---------|---------|------------|--------|
| **prod** | 10.10.0.0/24 | 10.10.0.40:6443 | YES (runs here) |
| **agentic** | 10.20.0.0/24 | 10.20.0.40:6443 | Managed by prod |
| **monit** | 10.30.0.0/24 | 10.30.0.20:6443 | Managed by prod |

### Kubeconfig Paths

```bash
# Prod
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig

# Agentic
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Monit
export KUBECONFIG=/home/monit_homelab/kubeconfig
```

## Alert Handling Workflow

1. **Identify** - Check alert labels (cluster, namespace, resource)
2. **Verify** - Is this a real issue or false positive?
3. **Diagnose** - Follow the relevant runbook
4. **Fix** - Apply resolution steps
5. **Verify** - Confirm alert resolves
6. **Document** - Update runbook if new information found

## Adding New Runbooks

When creating new runbooks:

1. Follow the template structure (Alert Details, Description, Quick Diagnosis, Common Causes, Resolution)
2. Include historical incidents if applicable
3. Add to this README index
4. Index to Qdrant via knowledge-mcp:
   ```
   mcp__knowledge__add_runbook(
     title="Alert Name",
     trigger_pattern="alert pattern or keywords",
     solution="brief solution summary",
     path="alerts/filename.md"
   )
   ```

## Related Documentation

- [Prometheus Operator Runbooks](https://runbooks.prometheus-operator.dev/)
- [Talos Linux Documentation](https://www.talos.dev/docs/)
- [Cilium Documentation](https://docs.cilium.io/)
