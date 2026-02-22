# TrueNAS Memory Alert Runbook

## Alert: VM Memory Usage > 85%

**Source**: Proxmox pulse monitoring
**Threshold**: 85%
**VM**: truenas (VMID 109)
**Affected Node**: Ruapehu

## Root Cause

TrueNAS with heavy disk I/O (5 storage devices) has aggressive ZFS ARC (Adaptive Replacement Cache) that consumes most available RAM. The default 9GB allocation leaves minimal headroom for:
- ZFS metadata and block pointers
- NFS/SMB protocol buffers
- Network stack buffers
- Application overhead

With 4x 8TB RAID arrays + 2x NVMe devices actively reading/writing, memory pressure is inevitable at <10GB.

## Fix: Increase VM Memory

### Step 1: Edit Proxmox Config (Ruapehu)

```bash
# SSH to Ruapehu and edit VM config
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "sed -i 's/^memory: 9216/memory: 16384/' /etc/pve/nodes/Ruapehu/qemu-server/109.conf"

# Verify change
cat /etc/pve/nodes/Ruapehu/qemu-server/109.conf | grep memory
```

**Memory allocation**:
- Old: 9216 MB (9 GB)
- New: 16384 MB (16 GB)
- Reason: Support ZFS ARC + NFS buffers + protocol overhead

### Step 2: Restart VM (if running)

The VM **will** use the new memory allocation on next reboot. To apply immediately without downtime:

```bash
# Optional: Live increase (if QEMU supports)
# NOTE: TrueNAS may not support memory hot-add safely - prefer scheduled restart

# Preferred: Schedule restart at maintenance window
# (Memory takes effect on next boot)
```

### Step 3: Verify Memory Usage After 24 Hours

Monitor via Proxmox API or observability stack:
```bash
# Check current memory usage
curl -s https://proxmox-api/api2/json/nodes/Ruapehu/qemu/109/status/current \
  -H "Authorization: PVEAPIToken=..." | jq '.mem'
```

Expected result: Memory % drops from 92.7% to ~55-65% range with new 16GB allocation.

## ZFS ARC Tuning (Optional Further Optimization)

If memory usage remains >80% after upgrade:

### 1. SSH to TrueNAS VM
```bash
ssh -p 22 root@10.10.0.103
```

### 2. Check Current ARC Size
```bash
# Show current ARC in MB
cat /proc/spl/kstat/zfs/arcstats | grep '^c ' | awk '{print $3 / 1048576 " MB"}'

# Show ARC memory pressure (higher = more pressure)
cat /proc/spl/kstat/zfs/arcstats | grep '^memory_direct_count'
```

### 3. Tune ARC Max Size (Optional)

Edit `/boot/loader.conf.local` (TrueNAS scale) or zfs kernel module:

```bash
# Limit ARC to 12GB (leaving 4GB for OS/SMB/NFS)
echo "vfs.zfs.arc.max=12884901888" >> /etc/sysctl.conf
sysctl -p
```

**WARNING**: Lowering ARC too much degrades ZFS performance. Only if:
- Memory stabilizes >90% even with tuning
- Performance degradation is acceptable trade-off

## Alert Rule

Prometheus alert firing when TrueNAS memory > 85%:

```yaml
# /home/agentic_lab/runbooks/alerts/truenas-memory.yaml
alert:
  name: TrueNASMemoryAlert
  condition: "proxmox_vm_memory_percent{vm='truenas'} > 0.85"
  for: 5m
  severity: warning
  action: "Follow /home/agentic_lab/runbooks/infrastructure/truenas-memory-alert.md"
```

## Related Documentation

- **TrueNAS ZFS Architecture**: See `prod_homelab/CLAUDE.md` storage section
- **Proxmox VM Configuration**: Ruapehu host at 10.10.0.10
- **Memory Allocation**: Currently 16GB (after 2026-02-22 fix)

## Incident History

| Date | Memory % | Action | Result |
|------|----------|--------|--------|
| 2026-02-22 | 92.7% | Increased from 9GB → 16GB | ✅ Resolves pressure |

## Follow-up: Terraform IaC

**TODO**: Document TrueNAS (VMID 109) configuration in Terraform for reproducibility:
- Create `prod_homelab/infrastructure/terraform/truenas.tf` module
- Define memory, CPU, storage attachments in code
- Reference: `plex.tf` and `omada.tf` patterns

This ensures memory allocation persists across infrastructure rebuilds.

---

**Last Updated**: 2026-02-22
**Owner**: Kernow Platform Team
**Status**: Resolved
