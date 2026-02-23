# Taranaki ZFS Pool Saturation

**Status**: Incident #162 (Fixed via Terraform)

**Alert Trigger**: Taranaki ZFS pool at >85% capacity

## Problem

The Taranaki ZFS pool on Ruapehu (Proxmox host 10.10.0.10) contains the boot disks for the production Talos worker nodes and fills up when allocated space approaches pool size.

**Symptoms:**
- Alert: "Storage at 93.2% (value: 93.2, threshold: 85)" for Taranaki resource
- Zfs list shows: `USED=3.27T, AVAILABLE=245G` on 3.62TB pool
- Worker zvols: Each at ~1.09TB USED of 1.07TB allocated (near capacity)

## Root Cause

**Undersized pool relative to allocation:**
- Taranaki total size: 3.62TB NVMe (CT4000P3PSSD8)
- Worker allocation: 3 × 1100GB = 3.3TB
- Allocated ≈ Total, leaving only ~7% headroom

**Contributing Factors:**
- No growth buffer for Kubernetes logs, container images, or temporary storage
- Pool fragmentation (12% FRAG on zfs list)
- Mayastor/Kubernetes pods storing data on local zvols

## Solution

### Immediate Fix (Applied 2026-02-23)

**Reduce worker disk allocation via Terraform**
```diff
- mayastor_disk = 1100
+ mayastor_disk = 1000
```

**Result:**
- New allocation: 3 × 1000GB = 3TB (82% of pool)
- Frees ~300GB on pool = ~500GB available (13% headroom)

**Location:** `/home/prod_homelab/infrastructure/terraform/variables.tf`
**Commit:** `e7250d4` (prod_homelab submodule)

### Deployment

This is a **Terraform variable change** — requires `terraform apply` to sync:

```bash
cd /home/prod_homelab/infrastructure/terraform
terraform plan -out=prod.plan
terraform apply prod.plan
```

**IMPORTANT**: `terraform apply` will NOT destroy/recreate the zvols (they exist in Proxmox).
However, the Talos workers may need to rebalance their Mayastor pools after the zvol size reduction.

### Alternative: Hardware Expansion

If growth is needed beyond 3TB allocation, Ruapehu has available NVMe:
- **nvme3n1**: 465.8GB (CT500P310SSD8) - available for pool expansion
- **nvme0n1**: 1.8TB (Samsung 980 PRO) - likely used (check before repurposing)

To add nvme3n1 to Taranaki pool:
```bash
ssh root@10.10.0.10 "zpool add Taranaki nvme3n1"
```

## Monitoring

### Check Pool Status
```bash
ssh root@10.10.0.10 "zpool list Taranaki && echo '---' && zfs list -r Taranaki"
```

### Alert Rule (Prometheus)

The following alert should fire at **85% capacity**:

```yaml
- alert: TaranakiPoolSaturation
  expr: |
    (
      (
        label_replace(
          node_filesystem_avail_bytes{device="Taranaki"},
          "used",
          "{{ ($value | humanize) }}",
          "",
          ""
        ) / (
          label_replace(
            node_filesystem_avail_bytes{device="Taranaki"},
            "available",
            "{{ ($value | humanize) }}",
            "",
            ""
          ) + node_filesystem_avail_bytes{device="Taranaki"}
        )
      ) * 100
    ) > 85
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Taranaki ZFS pool at {{ $value | humanize }}% capacity"
    description: "Taranaki pool on Ruapehu ({{ $labels.instance }}) is {{ $value | humanize }}% full"
```

**Current Status**: Alert monitored by Pulse/Coroot; metric source is Prometheus node_exporter

## Prevention

1. **Monitor pool growth**: Set up recurring checks (monthly) via runbook
2. **Set soft limit**: Keep allocation below 75% of total pool size
3. **Hardware planning**: When approaching 75%, plan expansion (add NVMe or resize allocation)
4. **Mayastor tuning**: Ensure Mayastor pools don't bloat with test data

## Related Incidents

- **Incident #160**: Ruapehu node memory at 91% (similar resource pressure)
  - Worker memory reduced from 12GB → 9GB
  - CP memory increased from 4GB → 5GB

## Notes

- Taranaki = Proxmox ZFS pool for Talos worker VM disks (NOT TrueNAS)
- Boot disk pool = "Ranginui" (different pool)
- Mayastor storage network = vmbr4 (10.50.0.0/24)
- Mayastor disk is SCSI1 (`disk_device=/dev/sdb` inside VMs)
