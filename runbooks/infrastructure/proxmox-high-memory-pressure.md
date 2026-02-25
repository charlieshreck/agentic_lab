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

**Pihanga Host** (Incident #156 fix - Feb 23, 2026):
```hcl
pbs.memory           = 4096   # 4GB (increased from 2GB due to OOM during backups)
talos-monitor.memory = 20480  # 20GB (K8s control plane, single-node monit cluster)

Total = 4 + 20 = 24GB allocated
Available for host overhead = 30.27GB - 24GB = 6.27GB (acceptable)
```

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

## UniFi VM Memory Tuning (Incident #265, Feb 25 2026)

The UniFi VM (VMID 451) runs UniFi OS inside a Podman container. The container runs multiple services:
- **Java (UniFi Network)**: Largest consumer. Default JVM max heap = 1/4 of VM RAM.
- **Node.js (UniFi Core)**: `--max-old-space-size=300` (300MB cap)
- **MongoDB x2**: System MongoDB + UniFi MongoDB (256M WiredTiger cache)
- **ulp-go, PostgreSQL, unifi-directory**: ~200MB combined

### Root Cause: Missing JVM Heap Limit

The systemd service unit (`/lib/systemd/system/unifi.service`) sets:
```
Environment="UNIFI_JVM_OPTS=-Xmx512M -XX:+UseParallelGC"
```

But `/etc/default/unifi` (loaded via `EnvironmentFile`) overrides it to:
```
UNIFI_JVM_OPTS="-Dunifi-os.server=true -Dorg.xerial.snappy.tempdir=/usr/lib/unifi/run"
```

This **removes** the `-Xmx512M` flag. The JVM then uses its ergonomic default of ~730MB max heap (1/4 of 3GB VM). Combined with all other services, the VM naturally grows past 90%.

### Fix: env-overrides File

The systemd service loads EnvironmentFiles in order — the last one wins:
1. `/etc/default/unifi` (image-managed, overrides service unit)
2. `/var/lib/unifi/env-overrides` (persistent volume, our override)

Create/edit the env-overrides file via the persistent volume:
```bash
# SSH to UniFi VM
sshpass -p '<password>' ssh root@10.10.0.51

# Write env-overrides inside the container
su - uosserver -c 'podman exec uosserver bash -c "cat > /var/lib/unifi/env-overrides << EOF
UNIFI_JVM_OPTS=\"-Dunifi-os.server=true -Dorg.xerial.snappy.tempdir=/usr/lib/unifi/run -Xmx512M -XX:+UseParallelGC\"
EOF"'

# Restart UniFi Network Application service
su - uosserver -c 'podman exec uosserver systemctl restart unifi'
```

### Verification
```bash
# Check JVM flags — should show -Xmx512M
su - uosserver -c 'podman exec uosserver bash -c "ps aux | grep ace.jar"'

# Check VM memory — should be under 80%
free -m
```

### Notes
- The env-overrides file is in the `/var/lib/unifi` persistent podman volume — survives container restarts
- After UniFi OS firmware updates, verify the file still exists and the -Xmx flag is active
- With -Xmx512M: estimated steady-state ~75% of 3GB VM (was 97%+ without it)

## References
- Memory overcommit: https://pve.proxmox.com/wiki/Memory
- Balloon driver: https://pve.proxmox.com/wiki/Balloning
- Incident #160 fix: GitOps commit reducing allocations (Feb 23, 2026)
- Incident #265 fix: UniFi JVM heap limit restored (Feb 25, 2026)
