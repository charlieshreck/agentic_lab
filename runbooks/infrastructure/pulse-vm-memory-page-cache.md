# Pulse Alert: VM Memory High (talos-monitor / monitoring cluster)

**Alert source**: Pulse (Proxmox monitoring)
**Symptom**: `talos-monitor` VM memory at >85-97% per Pulse dashboard
**Severity pattern**: Usually a **false positive** due to Linux page cache

---

## Root Cause

Pulse monitors Proxmox guest memory via the Proxmox API. Proxmox reports **total physical
pages allocated to the guest**, which includes:

- Actual process RSS (real usage)
- **Linux page cache** (disk I/O cache — reclaimable at any time)
- Kernel buffers

The monitoring cluster runs disk-heavy workloads (VictoriaMetrics TSDB, ClickHouse, Prometheus
WAL), which causes Linux to fill free RAM with file system cache. This is **healthy, expected
behavior** — the kernel aggressively caches disk reads for performance.

**Observed pattern (Incident #159, Feb 23 2026)**:
- Proxmox-reported memory: 97.1% (19.6 GB / 20 GB) → Pulse alert fires
- Linux `MemAvailable`: 11.1 GB / 20 GB = **55% available** → No alert warranted
- Linux page cache: ~10.7 GB (50%+ of RAM)
- Actual process RSS: ~7-8 GB (kube-apiserver 1.2GB, Prometheus 1.1GB, VictoriaMetrics 1.0GB,
  Coroot 0.6GB, ClickHouse 0.45GB, VictoriaLogs 0.25GB, system ~2GB)

---

## Diagnosis Steps

### Step 1: Check Proxmox vs OS memory

```bash
# Proxmox-level (what Pulse sees)
mcp__infrastructure__proxmox_get_vm_status with params={"node": "Pihanga", "vmid": 200, "host": "pihanga"}
# mem / maxmem = Proxmox usage (includes cache)

# OS-level (what actually matters)
mcp__observability__query_metrics_instant("node_memory_MemAvailable_bytes{instance='10.10.0.30:9100'}")
mcp__observability__query_metrics_instant("node_memory_MemTotal_bytes{instance='10.10.0.30:9100'}")
# (1 - MemAvailable/MemTotal) = actual usage excluding reclaimable cache
```

**If MemAvailable > 2 GB (10% of 20 GB)**: FALSE POSITIVE — Linux page cache, system healthy.
**If MemAvailable < 2 GB**: REAL PRESSURE — investigate container RSS and consider action.

### Step 2: Check page cache size

```bash
mcp__observability__query_metrics_instant(
  "node_memory_Cached_bytes{instance='10.10.0.30:9100'} + node_memory_Buffers_bytes{instance='10.10.0.30:9100'}"
)
```

If cache > 5 GB on this 20 GB VM, the Proxmox metric is almost certainly inflated by cache.

### Step 3: Check actual container memory RSS

```bash
mcp__observability__query_metrics_instant("sort_desc(container_memory_rss{namespace!='',container!=''})")
# Look at top consumers — expected top consumers:
#   kube-apiserver ~1-1.5 GB
#   prometheus     ~1-1.5 GB
#   vmsingle       ~1-2 GB
#   coroot         ~0.5-1 GB
#   clickhouse     ~0.3-1 GB
# Total expected: 5-9 GB for a healthy monitoring cluster
```

### Step 4: Check Prometheus alert (authoritative)

The `HomelabNodeHighMemory` PrometheusRule uses `MemAvailable` (correct metric).
If this alert is NOT firing, the system is healthy.

```bash
mcp__observability__list_alerts()
# Look for HomelabNodeHighMemory or HomelabNodeCriticalMemory for talos-monitor
```

---

## When It IS a Real Problem

Act if ANY of these are true:
- Linux `MemAvailable` < 2 GB (< 10% of 20 GB)
- `HomelabNodeHighMemory` PrometheusRule IS firing
- OOMKilled events in the past hour: `mcp__observability__query_metrics_instant("kube_pod_container_status_last_terminated_reason{reason='OOMKilled'} > 0")`
- Pods pending due to insufficient memory

### If real pressure: identify top consumer

```bash
mcp__observability__query_metrics_instant("sort_desc(container_memory_rss{namespace!='',container!=''})")
```

Common culprits on the monit cluster:
- **VictoriaMetrics** — 4 GB limit, check if near limit; reduce retention (`--retentionPeriod`)
- **ClickHouse** — No memory limit (Coroot operator sets `max_server_memory_usage=0`);
  cannot directly limit via CRD; consider reducing ClickHouse data retention in Coroot UI
- **Prometheus** — May grow with more scrape targets; check TSDB stats

### If action needed: increase VM RAM

VM RAM is defined in Terraform:

```
/home/monit_homelab/terraform/talos-single-node/variables.tf
# Find: memory variable for talos-monitor VM
# Current: 20480 MB (20 GB)
# Pihanga has 28 GB total — max safe allocation: ~24 GB (leaving 4 GB for PBS VM + host)
```

```bash
# Edit variables.tf, commit, and apply:
git -C /home/monit_homelab add terraform/talos-single-node/variables.tf
git -C /home/monit_homelab commit -m "infra: increase talos-monitor memory to Xm"
git -C /home/monit_homelab push origin main
# Then: terraform apply in terraform/talos-single-node/
# NOTE: Memory change requires VM reboot
```

---

## Why the Prometheus Alert Is Correct but Pulse Is Misleading

| Metric | Source | What it measures | Correct for alerting? |
|--------|--------|-----------------|----------------------|
| `mem/maxmem` | Proxmox API | Total pages in guest (incl. cache) | **NO** — includes reclaimable cache |
| `(1-MemAvailable/MemTotal)` | node-exporter | Process memory + non-reclaimable | **YES** — reflects real pressure |

The existing `HomelabNodeHighMemory` rule (threshold 85%) and `HomelabNodeCriticalMemory`
(threshold 95%) using `MemAvailable` are the authoritative alerts. Pulse alerts on this VM are
informational only — always verify with the MemAvailable metric before taking action.

---

## References

- Incident #159 (Feb 23 2026): talos-monitor 97.1% Proxmox memory = false positive, 55% actual available
- Proxmox memory accounting: https://pve.proxmox.com/wiki/Memory
- Linux page cache: kernel reclaims automatically when processes need more RAM
- `HomelabNodeHighMemory` rule: `monit_homelab/kubernetes/platform/prometheus-rules/homelab-rules.yaml`
