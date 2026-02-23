# PBS (Proxmox Backup Server) Operations Runbook

## Overview

PBS provides VM/LXC snapshot-level backups as a disaster recovery layer, complementing Backrest file-level backups.

### Current Setup (Pihanga)

**PBS Server**: 10.10.0.151 (VM 101 on Pihanga)
**Web UI**: https://10.10.0.151:8007
**Datastore**: `pbs-datastore` → `/mnt/pbs-datastore` (NFS to TrueNAS-HDD)
**NFS Path**: 10.10.0.103:/mnt/Taupo/pbs
**Storage**: 13.3 TB available

### Why Pihanga?

PBS runs on Pihanga (separate from Ruapehu) for proper DR:
- If Ruapehu fails, PBS and backups are still accessible
- Can restore Ruapehu VMs to new hardware
- Backups stored on TrueNAS-HDD (network storage)

## Backup Strategy

All three Proxmox hosts back up daily at 02:00 to PBS on Pihanga.

| Host | VMs/LXCs | Notes |
|------|----------|-------|
| Ruapehu (10.10.0.10) | vm/109, vm/400-403, vm/450, vm/451, ct/200 | Production workloads |
| Pihanga (10.10.0.20) | vm/101, vm/200 | PBS itself + monitoring |
| Hikurangi (10.10.0.178) | ct/100, ct/101, ct/102 | Synapse, Haute Banque, Tamar |

**Retention**: keep-daily=7, keep-monthly=3, keep-yearly=1

**Note**: Talos K8s VMs (400-403) can be rebuilt from IaC. PBS backups are optional DR layer.

## PBS Configuration

### Access PBS
```
URL: https://10.10.0.151:8007
User: root@pam
Password: H4ckwh1z
```

### Backup Schedule
All hosts have identical schedule configuration:
- Schedule: Daily 02:00
- Selection: All VMs/LXCs (`all=1`)
- Storage: `pbs-pihanga`
- Mode: Snapshot
- Compression: ZSTD

## Troubleshooting

### Stale NFS File Handles (Most Common Failure — Feb 2026)

When ALL backups fail with `unable to open chunk store at "/mnt/pbs-datastore/.chunks"`:

```bash
# 1. Restart PBS services (clears stale NFS handles)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl restart proxmox-backup proxmox-backup-proxy"

# 2. Test with a small backup
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump 200 --storage pbs-pihanga --mode snapshot --compress zstd"

# 3. Trigger full backups on all hosts
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.178 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
```

**Root cause**: NFS mount disruptions (e.g., TrueNAS IP change, network blip) leave the PBS process with cached stale file descriptors. Files are visible via `ls` but the running process gets ENOENT.

See also: `/home/agentic_lab/runbooks/alerts/pbs-backup-stale.md`

### Job Errors on vzdump
Common causes:
1. VM paused during backup — Check if QEMU guest agent is installed
2. Storage full — Check datastore space (`df -h /mnt/pbs-datastore`)
3. Lock conflicts — Check for stale locks
4. Stale NFS handles — See above

Check logs:
```bash
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "cat /var/log/vzdump/qemu-<VMID>.log"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "journalctl -u pvedaemon | grep vzdump | tail -50"
```

### Backup Verification Failed
1. Check datastore consistency
2. Run manual verify via PBS UI or API

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
