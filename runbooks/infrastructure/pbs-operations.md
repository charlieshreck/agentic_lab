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

### API Briefly Unreachable During Backup Window (02:00-02:15 UTC)

**Symptom**: `pbs_unreachable` finding fires around 02:03 UTC. Error: `PBS API unreachable: ` (empty message = timeout).

**Root cause**: The PBS proxy (`proxmox-backup-proxy`) logs `ENOTCONN` (os error 107) on the Unix socket to the API backend when multiple backup jobs start simultaneously at 02:00 UTC. This lasts 2-5 minutes while the jobs initialise (ct-100, vm-109, vm-200 all start together).

**Verification**:
```bash
# Check PBS API is actually working now
curl -s --max-time 10 -k -X POST https://10.10.0.151:8007/api2/json/access/ticket \
  -d "username=root@pam&password=H4ckwh1z" 2>&1 | grep -c '"status":200'

# Check proxy journal for ENOTCONN pattern
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 \
  "journalctl -u proxmox-backup-proxy --since '10 minutes ago' --no-pager | grep ENOTCONN"
```

**Expected**: Single `pbs_unreachable` finding at ~02:03, then API recovers by 02:08. Backups complete successfully by ~02:35.

**Resolution**: Transient. Auto-suppressed in error-hunter for 02:00-02:15 UTC window (fix applied Feb 2026, finding #915). If the alert fires outside that window, investigate as a real outage.

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

## Memory Pressure (Incident #163 — Feb 2026, recurring nightly)

### Known Recurring Pattern: Backup Window (02:00–02:35 UTC daily)

**This alert fires every night** at ~02:00 UTC when PBS backup jobs start. This is expected:
- PBS aggressively caches backup data in RAM during `vzdump` jobs
- With 4GB allocation, PBS uses ~97% during active backups
- **Memory pressure is always 0** — no OOM risk, no swapping
- Alert clears by ~02:35 UTC when backups complete

**Auto-resolve if**: Time is 01:45–03:15 UTC AND Proxmox task list shows active `vzdump` AND memory pressure = 0.

**Recommendation**: Add time-based alert suppression for `memory - pbs` between 01:45–03:15 UTC to eliminate this nightly false positive.

### Symptoms
- Pulse/KAO alert: `VM memory at >85%` for `pbs` on Pihanga
- Proxmox API reports ~96-98% memory used for PBS VM (VMID 101)
- `free -h` inside VM shows MemAvailable ~3.4GB — actual usage only ~430MB

### Root Cause: Missing QEMU Guest Agent (Primary)

Without `qemu-guest-agent`, Proxmox reports the QEMU process memory from the host side,
which includes **all Linux page cache**. Linux uses free RAM for disk cache (healthy behavior),
but Proxmox interprets it as used memory → false positive alert.

**Feb 24 2026 (recurrence)**:
- Proxmox-reported memory: 95.9% (3.84 GB / 4 GB) → alert fires
- Actual `MemAvailable`: 3.4 GB / 3.8 GB → **only 11% actually used**
- Active RSS: ~430 MB (proxmox-backup-proxy 55MB, proxmox-backup-api 25MB, system ~350MB)
- Page cache: 3.5 GB (disk I/O cache, reclaimable)
- `qemu-guest-agent`: **not installed**, `agent: enabled=0` in VM config

**Fix applied**: Installed `qemu-guest-agent`, enabled `agent: 1` in Proxmox config, rebooted VM.
After fix, Proxmox correctly reports ~25% memory usage via guest agent.

### Historical Fix (Initial incident)
1. **RAM increased** 2GB → 4GB (Terraform or manual `qm set`)
2. **journald** capped at 128MB runtime / 256MB system
3. **Guest agent** installed and enabled (Feb 24 fix)

### Procedure When Alert Fires

```bash
# 1. SSH to PBS and check real memory pressure
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "free -h"
# MemAvailable > 500MB = safe, just Proxmox cache bloat (likely false positive)

# 2. Verify guest agent is running (prevents false positives)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl status qemu-guest-agent --no-pager"
# If not running: systemctl start qemu-guest-agent

# 3. Check for log flooding
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "journalctl -u proxmox-backup-proxy --since '30 min ago' --no-pager | grep -c 'unable to open'"

# 4. If journald is bloated from log flooding, restart it
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl restart systemd-journald"

# 5. If actual memory pressure (MemAvailable < 200MB), check for a larger process
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "ps aux --sort=-%mem | head -10"

# 6. If NFS error flooding, see stale-NFS section above — restart PBS services
```

### Guest Agent Setup (if missing)

```bash
# Install inside PBS VM
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "apt-get install -y qemu-guest-agent"

# Enable in Proxmox config from Pihanga host
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "qm set 101 --agent enabled=1"

# Reboot VM (virtio-serial device only appears after reboot)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "qm reboot 101"

# Verify after ~30s
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl status qemu-guest-agent --no-pager"
```

**Note**: Plan PBS restart during a maintenance window (avoid 02:00 backup window).

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
