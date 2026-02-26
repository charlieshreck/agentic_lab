# Proxmox Host High Memory Utilization

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | Proxmox node memory high utilization |
| **Severity** | Warning |
| **Threshold** | Memory usage > 85% |
| **Source** | Proxmox metrics (VictoriaMetrics) |
| **Clusters Affected** | Prod cluster host (Ruapehu - Pihanga) |

## Description

Proxmox hypervisor memory pressure occurs when total VM allocations + host kernel overhead approach physical RAM limits. High memory utilization on the host can lead to:

- OOMKilled VMs and containers
- VM migration failures
- Degraded I/O performance
- Potential host crash if memory becomes fully exhausted

**Note**: Proxmox systems are typically overcommitted on memory using balloon-based memory reclaim (guest VMs report less available memory, host can reclaim unused pages). A healthy system runs at 75-85% utilization.

## Quick Diagnosis

### 1. Check host memory status

```bash
# From Proxmox UI or MCP tools
infrastructure-mcp proxmox_list_nodes --host ruapehu

# Expected output:
# Memory: 56.7GB / 62.6GB (91%)  ← Alert threshold 85%
```

### 2. List all VMs and container memory allocations

```bash
# List all VMs on the host
infrastructure-mcp proxmox_list_vms --host ruapehu

# List all LXC containers
infrastructure-mcp proxmox_list_containers --host ruapehu
```

### 3. Check actual memory usage vs. allocations

```bash
# Get detailed status for each VM
infrastructure-mcp proxmox_get_vm_status --host ruapehu --node Ruapehu --vmid <vmid>

# Look for:
# - mem: actual memory in use (bytes)
# - maxmem: allocated memory (bytes)
# - memhost: host-visible memory usage (includes overhead)
```

### 4. Calculate memory budget

```
Total RAM = 62.6GB (Ruapehu)
Host overhead = ~13.6GB (Proxmox kernel, caches)
Available for VMs = 49GB

Current allocations by VM:
- Workers (3x): 9GB each = 27GB
- Control plane: 4GB
- Plex: 7GB
- Unifi: 2GB
- TrueNAS: 9GB
- Omada: 2GB
- TOTAL: 51GB allocated

Allocation rate: 51/62.6 = 81% (acceptable, under 85% threshold)
```

## Common Causes

### 1. VMs Over-Allocated (Most Common)

**Symptoms:**
- Total allocated memory > 50GB on a 62.6GB system
- Many VMs allocated more than they actually need
- Memory balloon disabled on VMs, preventing reclamation

**Verification:**
```bash
# Check allocations
infrastructure-mcp proxmox_list_vms --host ruapehu

# Note maxmem field for each VM
# Calculate total: sum of all maxmem / 1024^3
```

**Resolution:**
Reduce memory allocations in Terraform:
1. Edit `/home/prod_homelab/infrastructure/terraform/variables.tf`
2. Reduce overallocated VM memory (workers, plex, unifi)
3. Commit and push changes
4. Apply Terraform to update VM allocations
5. Verify in Proxmox after VMs restart

**Example reductions:**
- Workers: 12GB → 9GB (actual usage: 8.5-9.6GB)
- UniFi: 3GB → 2GB (actual usage: 1.5GB)
- Plex: 6GB → 7GB (actual usage: 6.5GB, was oversubscribed)

### 2. Memory Balloon Disabled

**Symptoms:**
- VMs allocated X GB, all X GB reserved even if unused
- VM maxmem close to memhost value
- Can't reclaim memory from idle VMs

**Verification:**
```bash
# Check VM configuration
proxmox_get_vm_status --host ruapehu --node Ruapehu --vmid <vmid>

# Look in Terraform: floating = 0 means balloon is disabled
# See: infrastructure/terraform/main.tf and modules/
```

**Resolution:**
Memory ballooning should be enabled (controlled by Terraform). Current configuration:
- Control plane: `floating = 0` (balloon disabled intentionally for stability)
- Workers: `balloon_min = 0` (balloon enabled, can reclaim)
- Plex/UniFi: handled by Proxmox

**Don't enable balloon on control plane** — Kubernetes API server needs stable memory.

### 3. Orphaned/Hanging VMs

**Symptoms:**
- VM appears in list but not running
- Memory still allocated in Proxmox
- Can't connect to VM

**Verification:**
```bash
proxmox_list_vms --host ruapehu
# Look for status != "running"

# Or in Proxmox:
qm list  # Shows all VMs
```

**Resolution:**
```bash
# Remove zombie VM
proxmox_delete_vm --host ruapehu --node Ruapehu --vmid <vmid>
```

## Resolution Steps

### Immediate (Reduce Allocations)

**Step 1: Edit Terraform variables**
```bash
# File: /home/prod_homelab/infrastructure/terraform/variables.tf

# Reduce workers
memory = 9216  # from 12288 (12GB → 9GB)

# Reduce UniFi
memory = 2048  # from 3072 (3GB → 2GB)

# Increase Plex (was oversubscribed)
memory = 7168  # from 6144 (6GB → 7GB)
```

**Step 2: Commit and push**
```bash
git add infrastructure/terraform/variables.tf
git commit -m "fix: reduce VM memory allocations to ease host pressure"
git push origin main
```

**Step 3: Apply Terraform**
```bash
cd /home/prod_homelab/infrastructure/terraform
terraform plan
terraform apply
```

**Note**: VMs will restart with new allocations. This may take 5-10 minutes.

**Step 4: Verify memory recovers**
```bash
# Wait for VMs to restart (2-3 minutes)
infrastructure-mcp proxmox_list_nodes --host ruapehu

# Expected: Memory < 85% (target 75-80%)
```

### Long-term Monitoring

1. **Set lower alert threshold**: 80% (early warning before 85% critical)
2. **Monitor actual vs. allocated**: Check MCP tools monthly
3. **Review Kubernetes workload growth**: May need to add more worker nodes if cluster capacity increases
4. **Plan future upgrades**: If additional VMs needed, budget RAM accordingly

## Prevention

1. **Monitor memory monthly**: Use MCP `proxmox_list_nodes` to track trends
2. **Plan allocations carefully**: Keep host overhead + VM allocations < 62.6GB
3. **Size by actual usage**: Not worst-case. Most workloads don't use peak allocation.
4. **Use memory balloons**: Enable on non-critical VMs to allow reclamation
5. **Capacity planning**: Ruapehu with 62.6GB can handle:
   - 1x 4GB control plane
   - 3x 9GB workers = 27GB
   - 1x 6GB Plex
   - 1x 2GB UniFi
   - 1x 9GB TrueNAS (standalone)
   - 1x 2GB Omada (LXC)
   - **Total: 51GB allocations + 13.6GB overhead ≈ 64.6GB (slightly overcommitted)**

## Per-Host Reference

### Ruapehu (62.6GB - Production VMs)
- **Terraform**: `prod_homelab/infrastructure/terraform/variables.tf`
- **VMs**: talos-cp-01 (4GB), talos-worker-01..03 (9GB each), plex (7GB), unifi (2GB)
- **Safe total**: 51GB allocated (~81%)

### Pihanga (28.2GB - Monitoring + Backup)
- **Terraform**: `monit_homelab/terraform/talos-single-node/variables.tf`
- **VMs**: talos-monitor (24GB max, 18GB min with balloon), pbs (4GB)
- **Memory budget** (current as of 2026-02-26):
  - talos-monitor: 24GB max, 18GB balloon min (monitoring stack grew to need 18GB baseline)
  - pbs: 4GB (increased from 2GB in incident #163 to prevent OOM during backup)
  - Proxmox host overhead: ~3.8GB
  - Total at balloon minimum: 18 + 4 + 3.8 = ~25.8GB / 28.2GB = ~91-93% ← **this is expected and documented in Terraform**
- **Key**: Pihanga WILL run at 91-93% host memory with current config. Services are healthy. The Terraform variables.tf comment explicitly acknowledges this: `# → node runs ~93% memory (expected, services healthy)`
- **Inside VM**: talos-monitor reports ~50% (node_exporter) — services not under memory pressure
- **IO pressure**: ~2.5% PSI on talos-monitor (write-heavy monitoring workloads: VictoriaMetrics, Coroot, Prometheus)
- **Pulse override**: Set threshold 96%/91% for Pihanga-Pihanga to prevent false patrol triggers (2026-02-26)
- **Real fix would be**: Hardware RAM upgrade on Pihanga (architectural change, not quick fix)
- **Terraform file to edit**: `monit_homelab/terraform/talos-single-node/variables.tf` (memory_minimum field)

## Alert Rules

The Proxmox node memory alert should trigger at:
- **Warning (85%)**: Take action to reduce allocations within 24 hours
- **Critical (92%)**: Immediate action required to prevent OOM

**Current alert configuration**:
- Alert: `node_memory_high_utilization` or similar in Coroot/Keep
- Threshold: 85% for warning, 92% for critical
- Duration: Fire after 15 minutes sustained high usage

## Related Alerts

- `ProxmoxNodeNotResponding` - Host unreachable or rebooting
- `KubernetesNodeNotReady` - K8s node down due to host memory pressure
- `VMCrashLooping` - VM repeatedly restarting due to OOM

## Historical Incidents

### Incident #156 - February 2026 (Pihanga - talos-monitor)
- **Host**: Pihanga - 28GB RAM
- **Alert**: Memory at 97% (critical, threshold 85%)
- **Cause**: talos-monitor VM had 20GB dedicated with balloon **disabled** (`floating = 0`)
  - Linux fills all available RAM with page cache (disk I/O caching for monitoring data)
  - Pod working set is only ~7.2GB (VictoriaMetrics 1.4GB, Prometheus 1.2GB, kube-apiserver 1.0GB, etc.)
  - Remaining ~12GB was page cache — unnecessarily held by guest
- **Fix**: Enabled memory balloon in Terraform (`floating = 14336` = 14GB minimum)
  - virtio_balloon module was already loaded in Talos kernel config
  - No VM restart required — balloon device activated in-place
  - Host reclaims up to 6GB from talos-monitor guest's page cache
  - Result: ~77% utilization (well below 85% threshold)
- **Time to fix**: ~15 minutes (blocked by PBS backup lock, then terraform apply)
- **Root cause**: Balloon disabled when VM was created; page cache naturally fills all available RAM

### Incident #160 - February 2026 (Ruapehu)
- **Host**: Ruapehu - 62.6GB RAM
- **Alert**: Memory at 91% (warning level)
- **Cause**: VM allocations overcommitted (65GB allocated + host overhead)
- **Fix**: Reduced allocations via Terraform:
  - Workers: 12GB → 9GB (saves 9GB)
  - UniFi: 3GB → 2GB (saves 1GB)
  - Result: 51GB allocated (81% utilization, under 85% threshold)
- **Time to fix**: 10 minutes (commit → push → Terraform apply + VM restart)
- **Root cause**: No periodic memory review during VM allocation planning

### 2026-02-26 (Pihanga) — Recurring, Accepted State
- **Host**: Pihanga - 28.2GB RAM
- **Alert**: 92.8% (warning, firing since 2026-02-25)
- **Cause**: talos-monitor (24GB max, 18GB min) + PBS (4GB) = 28GB allocated. Host overhead ~3.8GB. System runs at 91-93% by design.
- **Fix**: Set pulse alert threshold override to 96%/91% for `Pihanga-Pihanga`. Terraform already documents this as expected: `# → node runs ~93% memory (expected, services healthy)`
- **Not fixed**: Root over-allocation constraint unchanged. Real fix = RAM upgrade.
- **Note**: Terraform state mismatch observed — code has 9GiB workers/5GiB CP but Proxmox shows 12GiB/4GiB. Pending terraform apply, but worker-02 currently at 8.11GiB (reducing to 9GiB = 90% usage). Needs human review.

## Implementation Notes

**Terraform VM memory field names:**
- Control plane: `var.control_plane.memory` (in MB)
- Workers: `var.workers["worker-0X"].memory`
- Plex: `var.plex_vm.memory`
- UniFi: `var.unifi_vm.memory`
- All values in **MB** (multiply by 1024 for GB conversion)

**Proxmox memory limits:**
- Available: 62.6GB (8 × 8GB DDR4 modules)
- Host overhead: ~13.6GB (kernel, caches, services)
- Usable for VMs: ~49GB hard limit
- Safe allocation: 45-50GB (allows 12-17GB breathing room)

**VM restart order** (Terraform apply):
1. Workers restart one at a time (Kubernetes reschedules pods)
2. Other VMs restart as Terraform moves through config
3. Control plane restarts last (wait for it to rejoin cluster)

## See Also

- `/home/prod_homelab/infrastructure/terraform/variables.tf` - VM allocation config
- `/home/prod_homelab/CLAUDE.md` - Proxmox architecture details
- `~/.claude/CLAUDE.md` - Infrastructure rules and git workflow
