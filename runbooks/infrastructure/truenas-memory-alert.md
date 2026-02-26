# TrueNAS Memory Alert Runbook

## Alert: VM Memory Usage > 85%

**Source**: Proxmox pulse monitoring
**Threshold**: 85%
**VM**: truenas (VMID 109)
**Affected Node**: Ruapehu

## Root Cause

TrueNAS/FreeBSD ZFS ARC (Adaptive Replacement Cache) is **designed** to fill all available RAM. This is NOT a memory leak — ZFS ARC maximizes cache hit rates by using every available page. The ARC releases memory immediately when applications request it. At 16GB, ZFS ARC typically fills 95-97% from the OS perspective.

**This is a false positive.** The Proxmox host shows ~58% actual physical page usage (9.3 GiB of 16 GiB). The 97% figure comes from the in-guest FreeBSD kernel reporting ARC-held pages as "used".

### Distinction: Host vs Guest Memory

| Metric | Value | Meaning |
|--------|-------|---------|
| Proxmox `mem` (host view) | 9.3 GiB / 16 GiB = 58% | Actual physical pages used on host |
| Pulse alert value (guest view) | 97% | FreeBSD reports ZFS ARC as "used" memory |
| ZFS ARC memory | ~15 GiB | Reclaimable cache — not real pressure |

### Recommended Fix: Pulse Override (not memory increase)

The correct fix is to raise the pulse alert threshold for this VM, NOT to increase memory further (adding more RAM will just lead to ~97% ZFS ARC usage again).

```bash
TOKEN="<pulse_api_token>"  # from Infisical /observability/pulse API_TOKENS
curl -sk -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"overrides":{"Ruapehu:Ruapehu:109":{"memory":{"trigger":99,"clear":95}}}}' \
  https://pulse.kernow.io/api/alerts/config
```

**Applied**: 2026-02-26 — threshold now 99%/95% for Ruapehu:Ruapehu:109.

---

## Legacy Fix: Increase VM Memory

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
| 2026-02-22 | 92.7% | Increased from 9GB → 16GB | ✅ Reduced host pressure; guest still fills to ~97% (ZFS ARC) |
| 2026-02-26 | 97.2% | Set pulse override threshold 99%/95% for Ruapehu:Ruapehu:109 | ✅ False positive resolved — no more patrol triggers for ZFS ARC |

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
