# Runbook: Taranaki ZFS Pool Saturation

## Alert
- **Alert Name**: `usage - Taranaki` (source: pulse)
- **Threshold**: 85% pool usage
- **Host**: Ruapehu (10.10.0.10)

## What Is Taranaki

**Taranaki** is a local 4TB NVMe ZFS pool on the Ruapehu Proxmox host (`/dev/nvme` CT4000P3PSSD8).
It holds **Mayastor block storage zvols** for the 3 Talos worker nodes:

| ZFS Dataset | VM | Use |
|-------------|-------|-----|
| `Taranaki/vm-401-disk-0` | talos-worker-01 (401) | Mayastor raw block device (scsi1) |
| `Taranaki/vm-402-disk-0` | talos-worker-02 (402) | Mayastor raw block device (scsi1) |
| `Taranaki/vm-403-disk-0` | talos-worker-03 (403) | Mayastor raw block device (scsi1) |

Each zvol is **1100GB** (`volsize=1.07T`). Proxmox automatically sets `refreservation=volsize` at creation, which means the full 1.1TB is pre-reserved in the pool per zvol, regardless of actual data.

**Note**: The Terraform variable `mayastor_disk = 1000` is a dead config — `lifecycle { ignore_changes = [disk] }` prevents Terraform from resizing existing zvols.

## Root Cause (Diagnosed 2026-02-24)

Alert fires because ZFS **thick provisioning** (refreservation) pre-allocates the full volsize:
- 3 zvols × 1.09TB refreservation = 3.27TB consumed
- Pool size: 3.52TB → 93.2% "used" (even with only 364GB actual data)

Actual Mayastor data usage is small: ~111-133GB per zvol (total ~364GB across all 3). This serves ~23 Kubernetes PVs totaling ~53GB (replicated 3×).

## Diagnosis

```bash
# SSH to Ruapehu
ssh root@10.10.0.10

# Check pool status
zfs list -o name,used,avail,refer,volsize,refreservation Taranaki Taranaki/vm-401-disk-0 Taranaki/vm-402-disk-0 Taranaki/vm-403-disk-0

# Check if refreservation is the problem (thick-provisioned):
# - USED >> REFER means refreservation is eating space
# - logicalused shows actual data
zfs get logicalused Taranaki/vm-401-disk-0 Taranaki/vm-402-disk-0 Taranaki/vm-403-disk-0
```

## Fix: Switch to Thin Provisioning

If refreservation is the cause (USED ≈ VOLSIZE but REFER is small):

```bash
ssh root@10.10.0.10

# Remove refreservation (safe: pool contains only these zvols)
zfs set refreservation=none Taranaki/vm-401-disk-0
zfs set refreservation=none Taranaki/vm-402-disk-0
zfs set refreservation=none Taranaki/vm-403-disk-0

# Verify
zfs list -o name,used,avail,refreservation Taranaki Taranaki/vm-401-disk-0 Taranaki/vm-402-disk-0 Taranaki/vm-403-disk-0
```

**Why it's safe**: The pool contains only these 3 zvols. Thin provisioning is safe when no other datasets compete for pool space. The actual data remains fully intact.

**Reversible with**: `zfs set refreservation=1.09T Taranaki/vm-<id>-disk-0`

## Why Refreservation Gets Re-Applied

Proxmox sets `refreservation=volsize` **at zvol creation time only**. It does NOT periodically re-apply it. Once set to `none`, it stays that way until the VM disk is deleted and recreated.

However, if the Talos cluster is ever rebuilt (VMs deleted + recreated), the new zvols will again have refreservation set. After a cluster rebuild, re-run this fix.

## Long-Term Fix (Requires Cluster Rebuild)

The real solution is to use smaller Mayastor zvols (200-300GB each, given ~53GB of PVs):
1. Snapshot all PVs / backup Mayastor data
2. Destroy and recreate the worker VMs with `mayastor_disk = 250` in Terraform
3. Restore Mayastor pools

This is a major maintenance window operation. Not needed until actual Mayastor data approaches the thin-provisioned pool free space.

## Expected State (After Fix)
- Pool usage: ~10-15% (actual data only)
- ZFS free: ~3TB+
- Each zvol: `refreservation=none`, `USED≈REFER≈logicalused`

## Related
- Terraform: `/home/prod_homelab/infrastructure/terraform/storage.tf` (Taranaki pool creation)
- Terraform: `/home/prod_homelab/infrastructure/terraform/variables.tf` (VM disk config)
- Terraform: `/home/prod_homelab/infrastructure/terraform/modules/talos-vm-triple-nic/main.tf` (ignore_changes)
