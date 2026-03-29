# TrueNAS Capacity Management

**Last Updated**: 2026-03-29
**Finding Reference**: #1435 (Taupo pool at 85%, escalated to 97.7%)

## Overview

TrueNAS-HDD pools fill naturally due to media downloads and library accumulation. This runbook establishes monitoring thresholds and cleanup procedures to prevent critical outages.

## Known Pools

### Taupo (Media)
- **Capacity**: 14.55TB
- **Primary use**: Plex media library, downloads, backups
- **Growth pattern**: Download spikes to 85-88% (transient), but library grows permanently
- **Datasets**:
  - `Taupo/pbs`: Proxmox backups (~1TB)
  - `Taupo/Pleximetry`: Prometheus metrics (~860GB)
  - `Taupo/Truro`: Media downloads (usually empty after processing)
  - `Taupo/MinIO`: Object storage (usually empty)
  - Root: Media library + miscellaneous (~12.6TB)

### Tekapo (Spare)
- **Capacity**: 2.25TB
- **Usage**: ~1.3%
- Can be used for temporary media staging

## Alert Thresholds

| Threshold | Action | Owner |
|-----------|--------|-------|
| < 80% | Normal operation | — |
| 80-85% | Monitor closely, prepare cleanup | Observability |
| 85-90% | Active cleanup needed, review old media | ops |
| 90%+ | **CRITICAL** — Stop downloads, escalate | ops + SRE |
| 97%+ | Imminent full-disk; immediate action | SRE |

## Cleanup Procedures

### 1. Identify Large Files in Taupo Root
```bash
# SSH to TrueNAS-HDD (10.10.0.103)
ssh root@10.10.0.103

# Find largest directories
du -sh /mnt/Taupo/* | sort -rh | head -20

# Check Truro for incomplete/old downloads
ls -ltr /mnt/Taupo/Truro/ | tail -30
```

### 2. Archive Old Media
Move infrequently accessed media (watched > 6 months ago) to Tekapo or external storage:
```bash
# Example: Move old Season 1-2 to staging
rsync -av /mnt/Taupo/Old-Series/Season-{1,2} /mnt/Tekapo/Archive/

# Verify
du -sh /mnt/Taupo/ /mnt/Tekapo/
```

### 3. Cleanup Download Debris
```bash
# Check for incomplete/failed downloads in Truro
find /mnt/Taupo/Truro -type f -mtime +7 -exec ls -lh {} \;

# Remove old incomplete downloads (> 7 days)
find /mnt/Taupo/Truro -type f -mtime +7 -delete
```

### 4. PBS Backup Rotation
If pbs dataset is > 1.2TB, review backup retention:
```bash
# View PBS snapshots
zfs list -r -t snapshot Taupo/pbs | head -20

# Remove old snapshots (keep last 30 days)
# Done via PBS Web UI or command
```

## Monitoring Integration

### Prometheus Metrics
Track pool capacity in Grafana:
```promql
# Taupo utilization
node_filesystem_avail_bytes{mountpoint="/mnt/Taupo"} / node_filesystem_size_bytes * 100

# Alert rule (AlertManager)
- alert: TrueNASPoolHigh
  expr: (node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes > 0.85
  for: 15m
  labels:
    severity: warning
    pool: taupo
```

### Manual Check
```bash
# From Synapse LXC
mcp__infrastructure__truenas_get_disk_usage({instance: "hdd"})
```

## Capacity Expansion Plan

**When**: Pool reaches 90% for > 1 hour OR 95% any time
**Actions**:
1. Stop media downloads (pause Sonarr/Radarr)
2. Emergency cleanup (old media archive)
3. If still > 90%: Add drives to Taupo pool (requires downtime)

**Current Hardware**:
- 2x 8TB drives (14.55TB usable with RAID1 mirror)
- Expansion: Add 2x 10TB (20TB usable) or 2x 12TB (24TB usable)

## Related Incidents

- **Finding #1435**: Taupo at 97.7% (2026-03-29) — escalated from 85% finding
  - Root cause: Media library growth + backup accumulation
  - Resolution: Document pattern and establish thresholds

## References

- TrueNAS-HDD IP: 10.10.0.103 (Prod network)
- Infisical secrets: `/infrastructure/truenas-hdd/`
- MCP tools: `truenas_list_pools`, `truenas_get_disk_usage`, `truenas_list_datasets`
