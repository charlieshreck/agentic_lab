# Proxmox Node Memory Pressure

**Alert**: `node_memory_available_percent < 15%` on Proxmox hosts

**Severity**: Warning (15-20% free), Critical (<10% free)

**Description**: Proxmox host has insufficient free memory for workload operations.

## Root Causes

1. **VM Over-Allocation**: Total VM allocated memory exceeds physical host memory
   - Proxmox supports memory overcommit, but balloon drivers + host overhead consume real RAM
   - Each QEMU process adds overhead (~50MB per VM)
   - Kernel buffers and caches further reduce available memory

2. **Memory Leak in Guest OS**: Individual VM consuming more than allocated
   - Use `ssh root@<vm-ip>` and run `free -h` to check guest memory usage
   - Check kernel messages: `dmesg | tail -20` for OOM killer activity
   - **PBS Backup OOM**: PBS (Proxmox Backup Server) needs extra memory during large backups
     - Standard allocation: 2GB (minimum for installation)
     - Recommended for backups: 4GB (Incident #156, #163)

3. **Host Overhead**: Proxmox system services consuming memory
   - Check: `free -h` on Proxmox host
   - Check: `ps aux | sort -k4 -rn | head -10` for top memory consumers

## Investigation Steps

### Step 1: Get Host Memory Status
```bash
# From Synapse LXC, check Proxmox node memory
kubectl get nodes -o custom-columns=NAME:.metadata.name,MEMORY:.status.allocatable.memory

# Or use MCP infrastructure tool:
mcp__infrastructure__proxmox_list_nodes with params={"host": "ruapehu"}
```

### Step 2: List All VMs and Their Memory Usage
```bash
mcp__infrastructure__proxmox_list_vms with params={"host": "ruapehu"}

# Check actual memory (memhost) vs allocated (maxmem) for each VM
# If memhost + (# VMs × 50MB overhead) + host buffer ≈ 62.6GB, then allocation is too high
```

### Step 3: Identify Problem VMs
Look for VMs where:
- **`memhost` > `maxmem`**: Guest OS using more than allocated (balloon deflation issue)
- Sum of all `maxmem` values > host physical memory: Overcommit situation

### Step 4: Check Guest OS Status
```bash
# SSH to problem VM and check memory
ssh root@<vm-ip> "free -h && top -b -n1 | head -20"

# Check for OOM killer activity
ssh root@<vm-ip> "dmesg | grep -i 'oom\|killed' | tail -10"
```

## Permanent Fix

Memory allocations are managed in GitOps (Terraform):
- **File**: `prod_homelab/infrastructure/terraform/variables.tf`
- **Variables**:
  - `var.control_plane.memory` - Control plane allocation
  - `var.workers[*].memory` - Worker allocations
  - `var.plex_vm.memory` - Plex VM allocation
  - `var.unifi_vm.memory` - UniFi VM allocation

### Current Safe Allocations

**Ruapehu Host** (Incident #160 fix - Feb 23, 2026):
```hcl
control_plane.memory = 5120   # 5GB
workers[*].memory    = 9216   # 9GB each (3 × 9GB = 27GB)
plex_vm.memory       = 7168   # 7GB
unifi_vm.memory      = 3072   # 3GB (balloon disabled — see Balloon section below)
truenas.memory       = 16384  # 16GB (TrueNAS VM, separate)

Total = 5 + 27 + 7 + 3 + 16 = 58GB allocated
Available for host overhead = 62.6GB - 58GB = 4.6GB (acceptable)
```

**Pihanga Host** (28GB physical RAM):
```hcl
pbs.memory                   = 4096   # 4GB (increased from 2GB due to OOM during backups)
talos-monitor.memory         = 24576  # 24GB max (balloon min 18GB)
talos-monitor.memory_minimum = 18432  # 18GB min

Total max allocation = 4 + 24 = 28GB
Host overhead = ~3.7GB
OVER-COMMITTED: 28 + 3.7 = 31.7GB on 28GB host
Actual usage at 18-19GB workload: 18.5 + 4 + 3.7 ≈ 26.2GB = 93-94%
```

**NOTE (Feb 26, 2026)**: The talos-monitor comment in variables.tf says "pbs=2GB" but PBS was
increased to 4GB (Incident #156/160). The capacity estimate is therefore stale. Pihanga will
persistently run at ~93% memory usage. **Services are healthy despite this.** This is a capacity
constraint, not a failure. Resolution requires a hardware decision or architectural change.

## Incident #215 Status (Feb 26, 2026 - Ruapehu Memory Pressure)

**Alert**: Ruapehu node memory at 88.2% (85% warning threshold) — sustained 7+ hours (13:33-20:32)

**Investigation Result**:
- **Terraform fix already exists**: `prod_homelab/infrastructure/terraform/variables.tf` has correct allocations
  - Workers: 9GB each (vs 12GB running) ✅ Code ready
  - Control plane: 5GB ✅
  - Plex: 7GB ✅
  - UniFi: 3GB ✅
  - Total allocation would be: 42GB (vs current 49GB running on 62.6GB host)

- **Actual VMs still at old allocations**:
  - talos-cp-01: 4GB allocated, 3.1GB actual
  - talos-worker-01: 12GB allocated, 7.3GB actual
  - talos-worker-02: 12GB allocated, 8.8GB actual
  - talos-worker-03: 12GB allocated, 8.7GB actual
  - plex: 6GB allocated, 4.8GB actual
  - unifi: 3GB allocated, 1.2GB actual
  - **Total configured: 49GB on 62.6GB host = ~78% before TrueNAS**

- **Root cause**: Terraform fix (correct memory values) is committed to git but `terraform apply` has not been executed

**Blockers to Remediation**:
- Terraform state is incomplete (only contains data sources, not VM resources)
- Full `terraform apply` would attempt to recreate resources (23 to add, 1 to destroy)
- Safe execution requires importing existing VMs or careful state management

**Recommended Next Step**:
1. Investigate Terraform state synchronization
2. Either: (a) Import existing VMs into state, or (b) manually adjust via Proxmox UI
3. Once resolved, execute `terraform apply` to synchronize all allocations
4. This should reduce Ruapehu memory pressure from 88% to ~70% (42GB + host overhead)

### To Apply Fix
```bash
cd /home/prod_homelab/infrastructure/terraform

# Requires terraform.tfvars with Proxmox credentials
terraform plan
terraform apply

# Verify nodes have new allocations
mcp__infrastructure__proxmox_list_vms with params={"host": "ruapehu"}
```

## Temporary Mitigation (if Terraform apply blocked)

If you cannot apply Terraform (e.g., waiting for credentials), migrate workloads to other nodes:

1. **Drain worker node**: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`
2. **Reduce VM memory via Proxmox UI**: Proxmox → Ruapehu → VM → Hardware → Memory
3. **Reboot VM**: Changes take effect on next boot

**WARNING**: Manual changes will be overwritten by next Terraform apply.

## Prevention

1. **Monitor regularly**: Set up recurring check via Alert Manager
   - `node_memory_available_percent < 20%` (warning threshold)
   - `node_memory_available_percent < 10%` (critical threshold)

2. **Size nodes correctly**: Calculate memory budget upfront
   - Sum all VM allocations + 10% buffer for host overhead

3. **Right-size VMs**: Monitor actual usage
   - Use Kubernetes resource metrics: `kubectl top nodes` / `kubectl top pods`
   - Adjust `maxmem` if VMs consistently use <50% allocation

4. **Balloon drivers**: Use carefully, disable for memory-sensitive VMs
   - Balloon enabled on workers allows flexible allocation
   - **Disabled on**: control plane (stable memory), Plex (GPU stability), UniFi (Java+MongoDB needs stable RSS)
   - See "Balloon Driver Gotchas" section below

## Balloon Driver Gotchas

**Key lesson (Incident — UniFi VM, Feb 25 2026, 3 occurrences in one day):**

1. **`qm set <vmid> --balloon 0` only changes stored config** — the running VM still has the balloon device loaded from boot. The balloon driver will continue operating.

2. **QMP `balloon` command is temporary** — inflating the balloon via QMP monitor (`info balloon` / `balloon <size>`) provides immediate relief, but the host's KSM/autoballooning will squeeze it back under memory pressure. This is NOT a durable fix.

3. **Only a cold restart applies balloon removal** — you must `qm shutdown <vmid>` then `qm start <vmid>` (or `qm stop` + `qm start`). A guest-level `reboot` may NOT be sufficient since the hypervisor device config isn't reloaded.

4. **Symptoms of balloon squeeze**: Low guest `free_mem` (<100MB), massive `mem_swapped_in`/`mem_swapped_out` (cumulative, hundreds of GB), high `major_page_faults` (millions), guest sees less `MemTotal` than `maxmem`.

### Verification After Restart
```bash
# Should return "Error: No balloon device has been activated"
ssh root@<proxmox-host> "qm monitor <vmid> <<< 'info balloon'"

# Should show full memory allocation
ssh root@<proxmox-host> "qm guest exec <vmid> -- cat /proc/meminfo | head -3"
```

## UniFi VM Memory (VMID 451) — Incidents #265+

The UniFi VM (VMID 451, 3GB RAM) runs UniFi OS with many services:
- **Java (UniFi Network)**: `-Xmx512M -XX:+UseParallelGC` (heap capped)
- **Node.js (UniFi Core)**: `--max-old-space-size=300` (300MB cap)
- **MongoDB x2**: System MongoDB + UniFi MongoDB (`cache_size=256M`)
- **ulp-go, PostgreSQL, unifi-directory, beszel-agent**: ~200MB combined

### Architecture
UniFi OS runs via `uosserver` systemd service (PID 1 = `/sbin/init`). Services run directly
on the VM with user namespacing (UIDs 100xxx). There are NO podman containers despite podman
being installed. The `/var/lib/unifi/` path does NOT exist at the VM host level.

### Alert Pattern: Pulse Memory False Positive

**Same pattern as monitoring cluster** (see `pulse-vm-memory-page-cache.md`):

| Metric | Source | Typical Value | Real? |
|--------|--------|--------------|-------|
| Proxmox `mem/maxmem` | Pulse alert | 85-97% | **NO** — includes page cache |
| Linux `MemAvailable` | Guest OS | ~45-55% of total | **YES** — actual pressure |
| Swap usage | Guest OS | 0 | Confirms no pressure |
| OOM events | `dmesg` | None | Confirms healthy |

The 3GB VM fills its free RAM with filesystem cache (MongoDB, PostgreSQL reads). Proxmox
reports this as "used" memory. Pulse fires at 85% threshold. This is a **false positive**.

### Diagnosis (from Synapse LXC)
```bash
# Check Proxmox-level (what Pulse sees — misleading)
# Use MCP: proxmox_get_vm_status(node="Ruapehu", vmid=451)
# Look at mem/maxmem ratio

# Check OS-level (what actually matters)
ssh root@10.10.0.10 "qm guest exec 451 -- bash -c 'cat /proc/meminfo | grep -E \"MemTotal|MemAvailable|Cached|SwapFree\"'"

# If MemAvailable > 500MB (17% of 3GB): FALSE POSITIVE
# If MemAvailable < 300MB (10% of 3GB): REAL PRESSURE — investigate services

# Check for OOM events
ssh root@10.10.0.10 "qm guest exec 451 -- bash -c 'dmesg | grep -i oom'"

# Check JVM heap cap is working
ssh root@10.10.0.10 "qm guest exec 451 -- bash -c 'ps aux | grep ace.jar'"
# Should show -Xmx512M in the command line
```

### Suppression
Added `["memory", "unifi"]` to `SUPPRESSED_ALERT_KEYWORDS` in LangGraph normalizer
(`agentic_lab/kubernetes/applications/langgraph/langgraph.yaml`). Future pulse/beszel
memory alerts for the UniFi VM are auto-suppressed.

If real memory issues occur, service-down alerts (Gatus, Coroot) will catch them.

### JVM Heap Cap Status
As of Feb 25 2026, the JVM includes `-Xmx512M` by default in the running process.
The previous env-overrides file approach (incident #265 initial fix) does NOT persist —
the path `/var/lib/unifi/env-overrides` doesn't exist at the VM host level. However, the
heap cap is working natively in the current UniFi OS version. Monitor after firmware updates.

## TrueNAS-Media VM (VMID 109) — ZFS ARC False Positive

**Pattern**: Pulse reports TrueNAS VM at 85-97% memory continuously. This is EXPECTED.

ZFS ARC (Adaptive Replacement Cache) is designed to fill all available RAM. TrueNAS will
always show near-100% memory utilization because ZFS aggressively caches disk data in RAM
to accelerate NFS reads. ZFS releases ARC automatically under memory pressure.

**Diagnosis**: Compare Proxmox `mem` (host-view) vs `maxmem`:
- If `mem/maxmem` < 60%: The VM's balloon has reduced allocation → check if this is causing ARC eviction
- If `mem/maxmem` > 85%: ZFS ARC filling available guest RAM → **NORMAL, not an issue**

**Verification** (guest exec via Proxmox SSH):
```bash
# NOTE: Guest agent may not return filesystem info (known issue for TrueNAS)
# Check via TrueNAS web API instead:
curl -s http://10.10.0.100/api/v2.0/reporting/get_data -H "Authorization: Bearer $API_KEY"
```

**Alert on TrueNAS**: Only escalate if:
- NFS mounts are failing (mount-canary-writer job fails)
- Dependent services (sonarr, radarr, transmission) are CrashLooping
- TrueNAS management UI is unreachable

**Note**: The Proxmox guest agent for TrueNAS sometimes returns "no filesystem info". This is a
QEMU guest agent compatibility issue with TrueNAS/FreeBSD, not a sign of VM problems.

## References
- Memory overcommit: https://pve.proxmox.com/wiki/Memory
- Balloon driver: https://pve.proxmox.com/wiki/Balloning
- Incident #160 fix: GitOps commit reducing allocations (Feb 23, 2026)
- Incident #265: UniFi VM memory — page cache false positive, suppression added (Feb 25, 2026)
