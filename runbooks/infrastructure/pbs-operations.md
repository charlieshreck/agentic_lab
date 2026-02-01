# PBS (Proxmox Backup Server) Operations Runbook

## Overview

PBS provides VM/LXC snapshot-level backups as a disaster recovery layer, complementing Backrest file-level backups.

### Current Setup (Pihanga)

**PBS Server**: 10.10.0.151 (LXC 101 on Pihanga)
**Web UI**: https://10.10.0.151:8007
**Datastore**: `pbs-datastore` → `/mnt/pbs-datastore` (NFS to TrueNAS-HDD)
**NFS Path**: 10.20.0.103:/mnt/Taupo/pbs
**Storage**: 13.3 TB available

### Why Pihanga?

PBS runs on Pihanga (separate from Ruapehu) for proper DR:
- If Ruapehu fails, PBS and backups are still accessible
- Can restore Ruapehu VMs to new hardware
- Backups stored on TrueNAS-HDD (network storage)

### Legacy Setup (Deprecated)

Old PBS on Ruapehu (10.10.0.150, VM 101) should be decommissioned after migration.

## Backup Strategy

| Source | Backup Method | Priority | Retention |
|--------|--------------|----------|-----------|
| IAC LXC (100) | PBS Weekly + Backrest Daily | CRITICAL | 4 weekly |
| Plex VM (450) | PBS Weekly + Backrest Daily | HIGH | 4 weekly |
| UniFi VM (451) | PBS Weekly | MEDIUM | 4 weekly |
| Talos VMs (400-403) | PBS Monthly (optional) | LOW | 1 monthly |

**Note**: Talos K8s VMs can be rebuilt from IaC. PBS backups are optional DR layer.

## Recommended Retention Policy

Replace `keep-all=1` with:
```
keep-daily=0
keep-weekly=4
keep-monthly=1
keep-yearly=0
```

## PBS Configuration via UI

### 1. Access PBS
```
URL: https://10.10.0.150:8007
User: root@pam
```

### 2. Configure Retention (Datastore → pbs-ruapehu → Prune)
- Set retention policy per backup group
- Enable automatic prune job

### 3. Verify Backups (Datastore → Verify)
- Enable automatic verification
- Schedule: Weekly after backups complete

### 4. Create Backup Schedule in Proxmox

On Ruapehu (https://10.10.0.10:8006):
- Datacenter → Backup → Add
- Schedule: Sunday 02:00
- Selection Mode: Include selected VMs
- VMs: 100 (IAC), 450 (Plex), 451 (UniFi)
- Storage: pbs-ruapehu
- Mode: Snapshot
- Compression: ZSTD
- Email notification: Enable

## Troubleshooting

### Job Errors on vzdump
Common causes:
1. VM paused during backup - Check if QEMU guest agent is installed
2. Storage full - Check datastore space
3. Lock conflicts - Check for stale locks

Check logs:
```bash
ssh root@10.10.0.10 "journalctl -u pvedaemon | grep vzdump | tail -50"
```

### Backup Verification Failed
1. Check datastore consistency
2. Run manual verify:
```bash
ssh root@10.10.0.150 "proxmox-backup-client verify <backup-id>"
```

## Monitoring

### PBS Health
- Datastore → Status shows health
- Check Grafana dashboard (if configured)

### Integration with Keep
PBS can send notifications to Keep via webhook for alert aggregation.

## Recovery Procedures

### Restore VM from PBS
1. Proxmox UI → Datacenter → pbs-ruapehu
2. Select backup snapshot
3. Right-click → Restore
4. Choose target node and storage

### Restore Files from PBS (without full VM restore)
```bash
# Mount backup for file-level recovery
proxmox-backup-client mount <datastore> <backup-id> /mnt/restore --repository <user>@<server>
```

## Related Runbooks
- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md`
