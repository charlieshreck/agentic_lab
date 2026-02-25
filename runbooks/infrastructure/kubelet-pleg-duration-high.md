# Runbook: KubeletPlegDurationHigh

## Alert Definition

```
KubeletPlegDurationHigh — PLEG (Pod Lifecycle Event Generator) 99th percentile
relist duration > 10 seconds on a node.
```

The PLEG is the kubelet component that polls the container runtime (containerd) to
detect pod state changes. When it takes >10s, the kubelet can't respond quickly to
container events. kubectl commands may also timeout.

## Affected Clusters

This alert fires on the **monit cluster** (single-node: talos-monitor, 10.10.0.30).

---

## Step 1: Verify Current State

```promql
# Current PLEG p99 duration
histogram_quantile(0.99, rate(kubelet_pleg_relist_duration_seconds_bucket{node=~"talos-monitor.*"}[5m]))

# Node CPU saturation
sum(rate(node_cpu_seconds_total{instance="10.10.0.30:9100",mode!="idle"}[5m]))

# Memory available %
node_memory_MemAvailable_bytes{instance=~"10.10.0.30.*"} / node_memory_MemTotal_bytes{instance=~"10.10.0.30.*"} * 100
```

**If PLEG < 1s and CPU < 4/6 cores**: The alert is based on a stale 5-minute window.
Verify in AlertManager that the alert is resolving. Auto-resolve if no longer firing.

**If PLEG = 10 (histogram ceiling) and CPU near 100%**: Active cascade — continue below.

---

## Step 2: Check for Cascade (CPU Saturation Pattern)

The most common cause on `talos-monitor` is a **restart cascade**. When a critical pod
(grafana, kube-state-metrics) enters a crash loop, containerd operations (start/init/mount)
saturate all 6 CPUs, which slows the container runtime, which causes PLEG to spike.

```bash
# Check for pods with high restart counts
kubectl --context admin@monitoring-cluster get pods -n monitoring
# Also check: velero, coroot, backrest namespaces
kubectl --context admin@monitoring-cluster get pods -A
```

**Warning**: kubectl itself may timeout due to PLEG/CPU pressure. If it times out,
wait 2-3 minutes and retry.

**Indicators of cascade**:
- kube-state-metrics or grafana with > 5 restarts
- Events showing liveness probe kills
- Container CPU metrics ~0.1 cores total but node CPU at ~100%

```bash
# Check events for probe failures
kubectl --context admin@monitoring-cluster get events -n monitoring --sort-by=lastTimestamp | tail -30
```

---

## Step 3: Identify Root Cause

### Common Triggers on Monit Cluster

| Time (UTC) | Possible Trigger |
|------------|-----------------|
| 02:30 | Velero daily backup (`30 2 * * *`) |
| 03:30 | Velero weekly backup (Sundays) |
| Any | etcd WAL compaction (every ~3h) |
| Any | containerd image GC |
| Any | Prometheus TSDB compaction (every 2h) |
| Any | VictoriaMetrics background merge |

**Note**: Container CPU metrics (cAdvisor) do NOT capture containerd-level operations.
If node CPU is near saturation but container metrics show only 0.1-0.2 total cores,
the cause is OS/runtime-level (etcd, containerd GC, kernel) — not application code.

### Container CPU During Spike

```promql
# Top CPU users during the incident (check historical data with offset)
topk(10, rate(container_cpu_usage_seconds_total{node="talos-monitor",container!="",container!="POD"}[2m] offset 20m))
```

---

## Step 4: Recovery Actions

### 4a. If Everything is Already Recovering (Self-Resolved)

If CPU < 4 cores and PLEG < 1s and all pods Running+Ready:
- The cascade ended on its own
- Wait for AlertManager to auto-resolve (5min group_interval)
- Document and resolve via webhook

### 4b. If kube-state-metrics is Crash-Looping (Not Recovering)

The kube-state-metrics liveness probe may be too aggressive. On startup, it needs
time to list all Kubernetes objects (configmaps, secrets, pods, etc. — 28 resource types).

**Temporary fix** — delete the pod to get a clean restart with less competition:
```bash
# Only do this if node CPU has dropped below 50% (room to restart)
kubectl --context admin@monitoring-cluster delete pod -n monitoring \
  -l app.kubernetes.io/name=kube-state-metrics
```

**Permanent fix** — increase initialDelaySeconds in Helm values.
In `/home/monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`,
add under `kubeStateMetrics:`:
```yaml
kubeStateMetrics:
  enabled: true
  extraArgs:
    - --custom-resource-state-only=false
  livenessProbe:
    initialDelaySeconds: 120  # default may be 5-10s, too aggressive
  readinessProbe:
    initialDelaySeconds: 60
```

Then commit + push to let ArgoCD apply.

### 4c. If Grafana is Crash-Looping (Not Recovering)

Grafana has `limits.memory: 512Mi`. It may OOM under load with plugins + dashboards.
Check the termination reason:

```bash
kubectl --context admin@monitoring-cluster describe pod -n monitoring \
  $(kubectl --context admin@monitoring-cluster get pod -n monitoring -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')
```

If `OOMKilled`, increase memory limit in kube-prometheus-stack-app.yaml:
```yaml
grafana:
  resources:
    limits:
      memory: 1Gi  # Increase from 512Mi
```

### 4d. If CPU is Still 100% and Nothing is Recovering

The cascade has gone critical. Consider:
1. Cordon the node (no-op on single-node but signals intent)
2. Delete the highest-restart pods to give containerd breathing room
3. If truly stuck, restart the Talos machine via Proxmox:
   - SSH to Pihanga: `ssh root@10.10.0.20`
   - Find the monit VM: `pct list` (or check Proxmox UI)
   - Restart: `qm reboot <vmid>`

---

## Step 5: Verify Recovery

```promql
# Confirm PLEG back to normal (should be < 0.1s)
histogram_quantile(0.99, rate(kubelet_pleg_relist_duration_seconds_bucket{node=~"talos-monitor.*"}[5m]))

# Confirm CPU normalized
sum(rate(node_cpu_seconds_total{instance="10.10.0.30:9100",mode!="idle"}[5m]))
```

Also confirm all pods in Running+Ready state.

---

## Prevention

### Short-Term: AlertManager Silence for Brief Spikes

The monit cluster is a single-node design — any CPU spike affects ALL monitoring services.
If the alert consistently fires during Velero backups (02:30 UTC), add a silence or
route in AlertManager for `KubeletPlegDurationHigh` on the monit node during the
02:30-03:00 window.

### Long-Term: Resource Planning

The monit node runs 114+ pods including heavy workloads:
- Prometheus (2Gi-4Gi memory, 0.5-2 CPU)
- VictoriaMetrics (stateful, I/O intensive)
- Coroot + ClickHouse (3 keeper replicas, 1 shard)
- Grafana, AlertManager, Beszel, Tugtainer, etc.

If cascades become frequent, consider:
1. Upgrading the monit VM CPU allocation (via Proxmox/Terraform)
2. Splitting workloads (e.g., move Coroot to a dedicated VM)
3. Increasing kube-state-metrics + grafana probe tolerances

---

## Resolution History

| Date | Root Cause | Fix | Duration |
|------|-----------|-----|----------|
| 2026-02-25 | Unknown OS-level CPU spike (~02:05 UTC) → grafana×11 + kube-state-metrics×8 restart cascade → containerd CPU saturation | Self-recovered | ~20 min |
