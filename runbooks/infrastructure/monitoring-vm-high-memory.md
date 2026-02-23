# Runbook: talos-monitor VM High Memory / OOM

**Alert**: `MonitNodeHighMemoryWarning` / `MonitNodeCriticalMemoryOomRisk` / Pulse "VM memory" alert
**Severity**: Warning at 80%, Critical at 90%
**Node**: `talos-monitor` (VMID 200, Pihanga)

---

## Overview

`talos-monitor` is a **single-node Talos K8s cluster** on Proxmox Pihanga. There is no node to reschedule to — OOM will crash all monitoring workloads simultaneously. This is the highest-priority memory issue in the homelab.

### Hardware Budget
- **Pihanga host total RAM**: ~28 GB
- **pbs VM** (VMID 101): 2 GB
- **talos-monitor max**: 24 GB (balloon up to 24 GB, guaranteed 18 GB minimum)
- **Host overhead**: ~2 GB

### Major Memory Consumers

| Workload | Limit | Notes |
|----------|-------|-------|
| Prometheus | 4 Gi | Grows as scrape targets increase |
| VictoriaMetrics | 4 Gi | Grows with retention |
| VictoriaLogs | 4 Gi | Grows with log volume |
| ClickHouse shard | 3 Gi | Coroot eBPF data (was unlimited before Feb 2026) |
| ClickHouse keepers (x3) | 512 Mi each | Coordination |
| Coroot server | 2 Gi | |
| System + other pods | ~3 Gi | kube-apiserver, cilium, etc. |

**Total max**: ~22 Gi — within the 24 GB VM maximum.

---

## Investigation

### 1. Check host memory
```bash
# From MCP or direct query
mcp__infrastructure__proxmox_list_vms(host="pihanga")
# Look for: mem (actual usage) vs maxmem (allocated max) for VMID 200
```

### 2. Check in-cluster node memory
```bash
KUBECONFIG=/home/monit_homelab/kubeconfig kubectl top nodes
```

### 3. Identify top consumers via VictoriaMetrics
```bash
curl -s "http://victoriametrics.monit.kernow.io/api/v1/query" \
  --data-urlencode 'query=sort_desc(container_memory_working_set_bytes{container!=""})' \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['data']['result'][:20]:
    m = r['metric']
    v = float(r['value'][1])
    if v > 0:
        print(f'{v/1024/1024:.0f}Mi - {m.get(\"namespace\")}/{m.get(\"pod\")}/{m.get(\"container\")}')
"
```

### 4. Check ClickHouse specifically
```bash
curl -s "http://victoriametrics.monit.kernow.io/api/v1/query" \
  --data-urlencode 'query=container_memory_working_set_bytes{pod=~"coroot-clickhouse.*",container!=""}' \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['data']['result']:
    m = r['metric']
    v = float(r['value'][1])
    if v > 0:
        print(f'{v/1024/1024:.0f}Mi - {m.get(\"pod\")}/{m.get(\"container\")}')
"
```

---

## Immediate Relief (if OOM imminent)

### Option A: Restart ClickHouse to free memory
```bash
KUBECONFIG=/home/monit_homelab/kubeconfig kubectl rollout restart statefulset/coroot-clickhouse-shard-0 -n coroot
```
This restarts ClickHouse (frees ~1 GB). Data is on persistent volume and will reload.

### Option B: Scale down non-critical workloads temporarily
```bash
# Grafana image renderer (1 Gi limit, rarely used)
KUBECONFIG=/home/monit_homelab/kubeconfig kubectl scale deploy grafana-image-renderer -n monitoring --replicas=0

# Scale back up when pressure is resolved
KUBECONFIG=/home/monit_homelab/kubeconfig kubectl scale deploy grafana-image-renderer -n monitoring --replicas=1
```

---

## Permanent Fix

### 1. ClickHouse memory limits (GitOps)
Edit `monit_homelab/kubernetes/platform/coroot-config/coroot-cr.yaml`:
- `clickhouse.resources.limits.memory` should be `3Gi`
- `clickhouse.keeper.resources.limits.memory` should be `512Mi`

### 2. VM memory increase (Terraform)
Edit `monit_homelab/terraform/talos-single-node/variables.tf`:
- `memory` (maxmem): should be at least `24576` (24 GB)
- `memory_minimum` (balloon_min): should be at least `18432` (18 GB)

Apply:
```bash
cd /home/monit_homelab/terraform/talos-single-node
terraform plan
terraform apply
```
Note: VM may need a restart for the `maxmem` change to take effect.

### 3. Reduce Prometheus/VictoriaMetrics limits (if above 4 Gi each)
These are set in:
- `monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml` → `prometheus.prometheusSpec.resources`
- `monit_homelab/kubernetes/argocd-apps/platform/victoria-metrics-app.yaml` → `server.resources`
- `monit_homelab/kubernetes/argocd-apps/platform/victoria-logs-app.yaml` → `server.resources`

---

## Root Cause History

| Date | Event |
|------|-------|
| Feb 2026 | ClickHouse deployed with no memory limits, workload growth exceeded 14 GB balloon minimum |
| Feb 2026 (fix) | Added ClickHouse limits (3 Gi shard, 512 Mi keeper), increased VM memory to 24 GB / 18 GB min |

---

## Related

- Proxmox high memory runbook: `infrastructure/proxmox-high-memory-pressure.md`
- Incident #159 (Feb 2026): talos-monitor OOM crash, 96.2% VM memory
