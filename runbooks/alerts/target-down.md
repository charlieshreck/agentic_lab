# TargetDown

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | TargetDown |
| **Severity** | Warning |
| **Threshold** | >10% of targets down |
| **Source** | Prometheus |
| **Clusters Affected** | All |

## Description

This alert fires when Prometheus cannot scrape one or more targets. This can indicate:
- Service is down
- Network connectivity issues
- Authentication/authorization failures
- Misconfigured scrape target
- False positive (target doesn't exist)

## Quick Diagnosis

### 1. Identify the affected target

```bash
# From alert labels
# Example: job=proxmox-carrick, service=kube-prometheus-stack-kube-scheduler

# Check Prometheus targets UI (if available)
# Or query via API
```

### 2. Check target health in Prometheus

```bash
# Port-forward to Prometheus
kubectl port-forward svc/kube-prometheus-stack-prometheus -n monitoring 9090:9090

# Visit http://localhost:9090/targets
# Or use the Service Discovery page
```

## Common Causes by Target Type

### 1. Proxmox Targets (proxmox-ruapehu, proxmox-carrick)

**Symptoms:**
- TargetDown for proxmox-* job
- Proxmox host is reachable but metrics fail

**Verification:**
```bash
# Test connectivity
curl -sk https://10.10.0.10:8006  # Ruapehu
curl -sk https://10.30.0.10:8006  # Carrick

# Test metrics endpoint (requires auth)
curl -sk -u "root@pam:password" \
  "https://10.10.0.10:8006/api2/prometheus?format=prometheus"
```

**Common Issues:**
- Wrong password in scrape config
- Proxmox API not responding
- Firewall blocking access
- TLS certificate issues

**Resolution:**
```bash
# Check the scrape config password matches Proxmox credentials
kubectl get secret prometheus-kube-prometheus-stack-prometheus -n monitoring -o yaml

# If password is wrong, update Helm values and redeploy
```

### 2. Kubernetes Component Targets (False Positives)

**Affected Targets:**
- kube-proxy
- kube-scheduler
- kube-controller-manager

**Resolution:**
See `talos-false-positives.md` runbook. These are false positives on Talos Linux.

```bash
# Delete the ServiceMonitors
kubectl delete servicemonitor -n monitoring \
  kube-prometheus-stack-kube-proxy \
  kube-prometheus-stack-kube-scheduler \
  kube-prometheus-stack-kube-controller-manager
```

### 3. Application Targets

**Symptoms:**
- TargetDown for specific application
- Application pod may not be running
- Service exists but has no ServiceMonitor

**Verification:**
```bash
# Check if the target pod is running
kubectl get pods -n <namespace> -l <selector>

# Check if service exists and has endpoints
kubectl get endpoints <service-name> -n <namespace>

# Check if ServiceMonitor is correct
kubectl get servicemonitor <name> -n <namespace> -o yaml

# Check if ServiceMonitor exists at all
kubectl get servicemonitor -n <namespace>
```

**Resolution:**
- If pod is running but no ServiceMonitor: Create the ServiceMonitor
- Fix the application if it's down
- Correct the ServiceMonitor selector if misconfigured
- Delete ServiceMonitor if target shouldn't exist

**ArgoCD Metrics (argocd-metrics job) - Confirmed Root Cause (Feb 2026):**

The scrape config used the Kubernetes API server proxy path:
```
https://10.10.0.40:6443/api/v1/namespaces/argocd/services/argocd-metrics:8082/proxy/metrics
```
This returns `503 ServiceUnavailable: error trying to reach service: dial tcp <pod-ip>:8082: i/o timeout`
because the prod API server cannot reach pod IPs cross-node (CNI routing constraint).
Note: `kubectl port-forward` DOES work (uses kubelet tunnel, not direct pod IP routing).

Additional blocker: `argocd-application-controller-network-policy` only allows ingress from
pods via `namespaceSelector: {}`, blocking all external traffic including NodePort.

**Fix applied:**
1. `prod_homelab/kubernetes/platform/argocd/resources/argocd-metrics-nodeport.yaml`:
   - NodePort service `argocd-metrics-nodeport` (port 30082 → 8082)
   - NodePort service `argocd-server-metrics-nodeport` (port 30083 → 8083)
   - NetworkPolicy `argocd-application-controller-metrics-external` allowing all-source ingress on 8082
2. `monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`:
   - Changed scrape targets from API proxy to `10.10.0.40:30082` and `10.10.0.40:30083`

**Pattern:** For cross-cluster scraping of ArgoCD/similar apps, use NodePort + check NetworkPolicies.
Never use the API server proxy for metrics — it times out due to CNI constraints.

### 4. Node Exporter Targets

**Symptoms:**
- TargetDown for node-exporter on specific node
- Node may be unhealthy

**Verification:**
```bash
# Check node status
kubectl get nodes

# Check node-exporter pods
kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus-node-exporter -o wide

# Test node-exporter directly
curl http://<node-ip>:9100/metrics | head
```

**Resolution:**
- Restart node-exporter pod on affected node
- Check node health
- Verify network connectivity

### 5. External Targets (Static Configs)

**Symptoms:**
- TargetDown for external services scraped via static_configs
- Service may be unreachable from monitoring cluster

**Verification:**
```bash
# From a pod in the monitoring cluster, test connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://<target-ip>:<port>/metrics
```

**Resolution:**
- Fix network connectivity
- Update firewall rules
- Correct target address in scrape config

## Resolution Steps

### Step 1: Identify the target type

```bash
# Check the job label in the alert
# Job names indicate what's being scraped
```

### Step 2: Verify if target should exist

For Talos clusters, some targets are expected to be missing:
- kube-proxy (Cilium replacement)
- kube-scheduler (metrics not exposed)
- kube-controller-manager (metrics not exposed)

### Step 3: Fix or remove based on type

**If target should exist:**
- Troubleshoot connectivity
- Fix authentication
- Restart the target service

**If target shouldn't exist:**
- Delete the ServiceMonitor
- Remove from static_configs

### Step 4: Silence while investigating

```bash
# If investigation will take time, silence to reduce noise
# Using monitoring-mcp
mcp__monitoring__create_silence alertname=TargetDown comment="Investigating" duration_hours=4
```

## Target Inventory

### Prod Cluster Targets
| Job | Target | Expected |
|-----|--------|----------|
| proxmox-ruapehu | 10.10.0.10:8006 | YES |
| talos-kubelets | 10.10.0.40-43 | YES |
| talos-node-exporter | 10.10.0.40-43:9100 | YES |
| kube-state-metrics | 10.10.0.40:30081 | YES |
| argocd-metrics | 10.10.0.40:30082 | YES |
| argocd-server-metrics | 10.10.0.40:30083 | YES |
| kube-proxy | N/A | NO (Cilium) |
| kube-scheduler | N/A | NO (Talos) |
| kube-controller-manager | N/A | NO (Talos) |

### Monit Cluster Targets
| Job | Target | Expected |
|-----|--------|----------|
| proxmox-carrick | 10.30.0.10:8006 | YES |
| talos-monitor | 10.10.0.30 | YES |

### Agentic Cluster Targets
| Job | Target | Expected |
|-----|--------|----------|
| claude-agent | 10.20.0.40:30200 | YES |

## Escalation

If target remains down:

1. Verify the service is actually healthy
2. Check network path (firewalls, routing)
3. Review scrape config for errors
4. Check Prometheus logs for scrape errors:
   ```bash
   kubectl logs -n monitoring -l app.kubernetes.io/name=prometheus --tail=100 | grep <target>
   ```

## Prevention

1. **Test scrape configs:** Verify connectivity before adding targets
2. **Use ServiceMonitors:** They auto-discover services vs. static configs
3. **Label targets:** Add cluster/environment labels for easier filtering
4. **Remove unused targets:** Delete ServiceMonitors for unused services

## Related Alerts

- `PrometheusTargetMissing` - Specific target completely gone
- `PrometheusScrapeFailed` - Scrape failures
- Service-specific down alerts

## Historical Incidents

### January 2026 - proxmox-carrick TargetDown
- **Target:** 10.30.0.10:8006 (Carrick Proxmox)
- **Cause:** Under investigation (host is reachable)
- **Status:** Silenced pending investigation
- **Next Steps:** Verify Proxmox API credentials, check firewall

### February 2026 - argocd-metrics TargetDown
- **Target:** `argocd-metrics/` job in AlertManager
- **Cause (multi-layer):**
  1. Scrape config used API server proxy — times out because prod API server can't reach pod IPs across nodes (CNI constraint)
  2. `argocd-application-controller-network-policy` blocked external traffic (only allowed pods via `namespaceSelector: {}`)
- **Resolution:**
  1. Added NodePort services (30082, 30083) in `prod_homelab/kubernetes/platform/argocd/resources/argocd-metrics-nodeport.yaml`
  2. Added supplemental NetworkPolicy allowing all-source ingress on 8082
  3. Updated Prometheus scrape config to use NodePort targets instead of API proxy
- **Lesson:** API server proxy is unreliable for cross-cluster metrics scraping on Talos+Cilium. Use NodePort pattern (same as kube-state-metrics:30081). Always check NetworkPolicies when NodePort is unreachable.

### January 2026 - kube-scheduler/controller-manager TargetDown
- **Cause:** False positive - Talos doesn't expose these metrics
- **Resolution:** Deleted ServiceMonitors
- **Lesson:** Document Talos-specific monitoring requirements
