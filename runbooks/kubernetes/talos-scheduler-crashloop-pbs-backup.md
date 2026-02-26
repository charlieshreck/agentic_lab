# Talos Scheduler CrashLoop — PBS Backup IO/Memory Pressure

## Alert Pattern
- **Alert**: `HomelabPodCrashLooping` on `kube-scheduler-talos-monitor` or `kube-scheduler-talos-cp-01`
- **Time window**: 02:00–04:00 AM daily (coincides with PBS backup schedule)
- **Clusters affected**: All three clusters (monit worst, prod moderate, agentic least)

## Root Cause

Nightly PBS backup (Pihanga receives, Ruapehu sends VM snapshots) causes simultaneous IO and memory pressure on both Proxmox hosts:

1. **02:00 AM** — PBS backup starts
2. **Ruapehu** — Live VM snapshot IO during backup causes disk/CPU contention. The `talos-cp-01` VM's KubePrism (port 7445) becomes slow.
3. **Pihanga** — Both PBS VM (4GB) and talos-monitor VM (24GB max, 18GB min) are memory-competing. The balloon driver may reclaim memory from talos-monitor. Storage IO is also shared on Pihanga's single NVMe.
4. **API server slowness** → kube-scheduler can't renew its leader election lease within `renewDeadline` (10s default)
5. **Scheduler exits with** `"Leaderelection lost"` and is restarted by kubelet

### Evidence
- Prod cluster (Ruapehu): crash at 02:23 AM on 2026-02-26
- Monit cluster (Pihanga): crash at 03:01 AM on 2026-02-26
- kube-scheduler logs: `context deadline exceeded` on `https://127.0.0.1:7445/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-scheduler?timeout=5s`
- kube-apiserver shows WARNING-level `lookup localhost: operation was canceled` for etcd gRPC channels (background noise, not the direct cause)

### Restart Counts (as of 2026-02-26)
- `kube-scheduler-talos-monitor`: 18 restarts
- `kube-controller-manager-talos-monitor`: 16 restarts
- `kube-scheduler-talos-cp-01`: 9 restarts
- `kube-controller-manager-talos-cp-01`: 8 restarts
- `kube-scheduler-agentic-01`: 4 restarts

## Immediate Assessment

**Self-healing**: Yes — scheduler recovers within 3–5 minutes after API server stabilises.

### Verify Current State
```bash
kubectl --context admin@monitoring-cluster get pod -n kube-system kube-scheduler-talos-monitor
kubectl --context admin@homelab-prod get pod -n kube-system kube-scheduler-talos-cp-01
```

If `Running` with no recent crashes → alert is stale, cluster is healthy. Resolve as "transient - self-healed, recurring pattern documented."

### Check Time of Last Crash
```bash
kubectl --context admin@monitoring-cluster logs -n kube-system kube-scheduler-talos-monitor -c kube-scheduler --previous 2>&1 | tail -5
```
If crash time is 02:00–04:00 AM → PBS backup triggered it.

## Permanent Fix Options (Require Human Decision)

### Option 1: Increase Scheduler Lease Tolerance (Recommended — No Hardware)
Add `schedulerConfig` to Talos machineconfig to increase lease durations:
```yaml
# In monit_homelab/terraform/talos-single-node/main.tf machine patches:
cluster:
  schedulerConfig:
    leaderElection:
      leaseDuration: 30s   # default: 15s
      renewDeadline: 20s   # default: 10s
      retryPeriod: 5s      # default: 2s
```
Apply via `terraform apply` in `monit_homelab/terraform/talos-single-node/`.
Do the same for prod cluster in `prod_homelab/infrastructure/terraform/`.

### Option 2: PBS IO Throttling
On PBS VM (`ssh root@10.10.0.20 "pct exec 101 -- ..."` or `ssh root@10.10.0.151`):
- Configure backup job with bandwidth limit / IO throttling in the PBS UI
- Reduces impact on Pihanga NVMe and Ruapehu disk IO during snapshot

### Option 3: Stagger Backup Schedule
Move PBS backup to 04:00 AM instead of 02:00 AM, or schedule per-VM with offsets to avoid simultaneous snapshots.

### Option 4: Hardware — Separate Disks
Add a dedicated NVMe to Pihanga for the PBS datastore, eliminating IO contention with the talos-monitor boot/data disks.

## Related Issues
- Ruapehu memory over-allocation: Incident #160 (pending Terraform apply to reduce workers from 12GB → 9GB)
- Pihanga memory: 28GB total, 24GB talos-monitor + 4GB PBS = 100% nominal allocation

## Etcd `lookup localhost` Warnings (Background Noise)
The kube-apiserver logs `W ... grpc: addrConn.createTransport failed ... lookup localhost: operation was canceled` every 30 seconds. This is **not** the cause of the scheduler crashes — it's gRPC background reconnect context cancellation for idle etcd channels. The API server remains functional. These warnings appear on all Talos clusters regardless of load.
