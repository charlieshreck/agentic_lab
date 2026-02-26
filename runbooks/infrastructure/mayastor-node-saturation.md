# Runbook: Mayastor Node System Saturation (False Positive)

## Alert
`NodeSystemSaturation` — System load per core above 2.0 on a node running the Mayastor io-engine.

## Root Cause

Mayastor io-engine uses [SPDK](https://spdk.io/) for high-performance NVMe-oF storage. SPDK runs in **busy-polling mode**: its reactor threads never sleep and are always present in the Linux run queue.

With `-l1,2` (the default config in this cluster), two SPDK reactor threads are pinned to CPU cores 1 and 2. These threads contribute a constant **~2.0 baseline** to the node's load average, regardless of actual I/O activity. The `NodeSystemSaturation` alert fires when `node_load1 / cpu_count > 2.0` — which is always true for these nodes at idle.

This is **expected behavior** for SPDK-based storage, NOT a sign the node is unresponsive.

## Affected Nodes (as of 2026-02-24)

| Node | IP | io-engine pod | load_1min | load/core | Status |
|------|-----|--------------|-----------|-----------|--------|
| talos-worker-03 | 10.10.0.43 | mayastor-io-engine-clct7 | ~8.0 | ~2.0 | Alert suppressed in AlertManager |
| talos-worker-01 | 10.10.0.41 | mayastor-io-engine-vfhw7 | ~2.4 | ~0.6 | Below threshold |
| talos-worker-02 | 10.10.0.42 | mayastor-io-engine-2gqwf | ~2.4 | ~0.6 | Below threshold |

Worker-03 has significantly higher load than workers 01/02 despite identical io-engine config (`-l1,2`). Root cause:
1. Worker-03 is the **nexus host** for most PVC volumes — it coordinates I/O across all replica nodes
2. Each NVMe connection to replica nodes spawns additional SPDK pollers (admin queue threads, etc.)
3. These pollers all compete for CPUs 1 and 2, creating a run queue depth of ~8 threads on those 2 cores
4. Load average of ~8.0 is the stable baseline for worker-03 when hosting multiple active nexuses

All three nodes show CPUs 1 and 2 at 100% (SPDK busy-poll), but worker-03 has more threads competing for those CPUs.

Worker-03 was the sole storage node before Feb 19 2026, so all PVC nexuses were initially placed there. Nexuses don't automatically rebalance.

## AlertManager Fix

A null-route is configured in `monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`:

```yaml
- match:
    alertname: 'NodeSystemSaturation'
    instance: '10.10.0.43:9100'
  receiver: 'null'
```

## How to Verify It's Not a Real Problem

1. Check node conditions — must all be `False` (no pressure):
   ```bash
   kubectl get node talos-worker-03 --context admin@homelab-prod
   ```

2. Check actual CPU utilization (not load average):
   ```promql
   1 - rate(node_cpu_seconds_total{instance="10.10.0.43:9100", mode="idle"}[5m])
   ```
   Expected: ~50% (2 of 4 CPUs busy — the SPDK reactor cores)

3. Check that the load average is stable at its expected baseline, not spiking:
   ```promql
   node_load1{instance="10.10.0.43:9100"} / 4
   ```
   - **Expected baseline for worker-03**: ~2.0/core (absolute load ~8.0) — stable, not growing
   - **Workers 01 and 02**: ~0.6/core (absolute load ~2.4)
   - Spikes above 3.0/core OR sustained upward trend warrants investigation.

4. Verify io-engine is not logging errors:
   ```bash
   kubectl logs -n mayastor mayastor-io-engine-clct7 -c io-engine --tail=50 --context admin@homelab-prod
   ```

## When It IS a Real Problem

Investigate if:
- Load/core spikes above 3.0 (not just 2.0-2.3 baseline)
- Node conditions show `MemoryPressure`, `DiskPressure`, or `PIDPressure = True`
- Mayastor io-engine logs show errors (nexus degraded, NVMe disconnects)
- Application pods are unable to write to PVCs (I/O errors)
- Other nodes in the cluster also show high load

## Related Alert: Pulse VM CPU High (> 80%)

**Pattern** (confirmed 2026-02-25 and 5× on 2026-02-26): Pulse fires `cpu - talos-worker-XX` at 80% threshold during Renovate runs.

**Breakdown on 4-vCPU worker VMs (pre-fix):**
- Mayastor io-engine SPDK busy-polling: **~2 vCPUs constant** = ~50% VM CPU floor on 4 vCPUs
- General K8s overhead (Cilium, ArgoCD, coroot, cert-manager, etc.): **~9%** additional
- Total baseline: **~59%** (observed on worker-01 without Renovate)
- Renovate (`schedule: "0 */6 * * *"`, runs every 6h, limit: 1 vCPU): **~21%** additional
- Combined peak: **~80%** → crosses threshold

**Structural fix applied 2026-02-26**: Workers increased from 4→6 vCPUs via Terraform + VM rolling restart.

**Expected baseline on 6-vCPU workers (post-fix):**
- Mayastor SPDK: 2/6 = 33%
- K8s overhead: ~9%
- Total baseline: ~42%
- With Renovate peak: ~42% + 17% = **~59%** — well below 80% threshold

**NOTE**: Alert continued to fire 5× on 2026-02-26 despite 6-vCPU fix. Actual observed peaks hit 80.6% (above predicted 59%). Likely cause: short post-restart CPU spikes + actual Renovate overhead higher than modelled.

**Additional trigger — Velero daily backup (02:00 UTC)**: Velero `daily-backup` pods start at 02:00:51 UTC and push talos-worker-02 CPU to ~80.6% briefly (confirmed 2026-02-26 02:05). CPU drops to ~47% within a few minutes as backup IO normalizes. This is expected transient behavior during the nightly backup window.

**Threshold fix applied 2026-02-26** *(permanent resolution)*: Raised Pulse CPU alert threshold for all three Talos workers from 80% → 90% via Pulse UI. This matches the actual safe operating range — at 90%+ on a storage node, the workloads themselves would be impacted.

**⚠️ THRESHOLD DISCREPANCY DETECTED 2026-02-26 ~02:05 UTC**: Alert fired at 80.6% with `threshold: 80` in the alert payload — meaning Pulse is still alerting at 80%, not 90%. The threshold change may not have persisted in the Pulse backend, or it requires re-application. **Action required**: Re-verify threshold via `http://pulse.kernow.io` → Alerts → Thresholds → VMs table → talos-worker-01/02/03 → confirm set to 90%. If already showing 90%, check whether Pulse caches thresholds in memory and restart the service.

**How to set threshold** (pulse.kernow.io → Alerts → Thresholds → Proxmox):
1. Navigate to `http://pulse.kernow.io/alerts/thresholds/proxmox`
2. In the "VMs & Containers" table, click the edit (pencil/blue) icon on the right of each worker row
3. Change the CPU % number input from 80 to 90 (type the value, press Tab to commit)
4. Repeat for talos-worker-01, 02, 03
5. Click **"Save Changes"** button at the top of the page
- Current setting: **90%** (changed 2026-02-26)

**To verify Renovate is running** (explain a CPU spike):
```bash
kubectl get pods -n renovate --context admin@homelab-prod
# Renovate status "Running" = spike in progress, will self-heal in ~30 min
# Renovate status "Succeeded" = completed, CPU should already be dropping
```

**If alert fires again (above 90%)**: Investigate — that would be abnormal even with Renovate + Mayastor.

## Long-Term Improvements

1. **Nexus rebalancing**: Delete and recreate PVCs to redistribute nexuses across all three worker nodes. This is disruptive and requires application downtime.

2. **More io-engine CPU cores**: Change the SPDK reactor CPU list from `-l1,2` to `-l0,1,2,3` to use all 4 cores. This halves the per-core contribution to load average. Requires Mayastor Helm chart customization (not a simple values change).

3. **Increase worker vCPUs from 4→6** *(applied in Terraform 2026-02-26)*: Gives more scheduling headroom for workloads like Renovate. The io-engine would still only use CPUs 1-2 but kernel and other pods have more room. Requires `terraform apply` + VM restart cycle. Change is in `prod_homelab/infrastructure/terraform/variables.tf`.

4. **Extend null-route to all Mayastor nodes**: If workers 01/02 ever cross the NodeSystemSaturation 2.0 threshold, update the AlertManager route to use `alertname: NodeSystemSaturation` without an instance filter (and rely on the `cluster: production` label instead).
