---
title: TrueNAS Boot Pool Space Management
description: Investigate and resolve boot-pool space usage warnings (85%+)
tags: [truenas, storage, space-management, boot-pool]
---

# TrueNAS Boot Pool Space Management Runbook

## Alert: Space usage for pool 'boot-pool' is 85%

**Source**: TrueNAS system pool monitoring
**Severity**: INFO (warning, not critical)
**Instances**: TrueNAS-Media (VMID 109, 10.10.0.100)
**Pool**: `boot-pool` (system/OS pool, ~32GB total capacity)

---

## What's boot-pool?

The `boot-pool` is TrueNAS's internal **system pool**, separate from user data pools (Tongariro, Taranaki):

- **Purpose**: TrueNAS OS, system files, configurations, snapshots
- **Size**: ~32GB (VM disk scsi0 on Proxmox VMID 109)
- **Current Usage**: ~27GB at 85% capacity
- **Growth Drivers**:
  - TrueNAS system snapshots
  - Container/Docker images
  - System logs
  - Temporary files from maintenance tasks

---

## Investigation Steps

### 1. Verify Alert Status

```bash
# Check if alert is still active
mcp__infrastructure__truenas_get_alerts(instance="media")

# Expected output: Shows "Space usage for pool 'boot-pool' is 85%"
```

### 2. Check System Pool Health

The boot-pool is **not exposed** via TrueNAS REST API (only data pools are: Tongariro, Taranaki).
You need **direct SSH access** to investigate:

```bash
# SSH into TrueNAS-media (10.10.0.100)
ssh root@10.10.0.100

# Check boot-pool status (requires TrueNAS credentials from Infisical)
zfs list -h boot-pool

# Expected output example:
# NAME       SIZE  ALLOC  FREE  CKPOINT  EXPANDSZ  FRAGMENTATION  CAP  DEDUP  HEALTH
# boot-pool   32G   27G  5.1G        -         -              8%  85%  1.00x  ONLINE

# Check what's consuming space
zfs get used,available boot-pool
du -sh /mnt/boot-pool/* 2>/dev/null | sort -h

# Check snapshots
zfs list -t snapshot -r boot-pool
```

### 3. Identify Large Consumers

Common space consumers in boot-pool:

| Item | Typical Size | How to Check |
|------|-------------|--------------|
| **Snapshots** | 1-5GB | `zfs list -t snapshot` |
| **System logs** | 0.5-2GB | `du -sh /var/log/` |
| **Container images** | 1-3GB | (depends on Docker) |
| **TrueNAS database** | 0.5-1GB | `/var/db/*` |
| **Temporary files** | varies | `/tmp/`, `/var/tmp/` |

---

## Remediation (in Priority Order)

### ✅ Step 1: Clean Old Snapshots (SAFE)

Old snapshots are the most common cause. Clean automatically-created snapshots:

```bash
ssh root@10.10.0.100

# List all snapshots sorted by size
zfs list -t snapshot -r boot-pool -S used -h

# Delete old automated snapshots (keep recent ones)
# Example: Remove snapshots older than 7 days
zfs list -t snapshot -r boot-pool -o name,creation -s creation | \
  awk 'NR>1 {cmd="date -d \"$(stat -c %y "$2" | cut -d. -f1)\" +%s"; \
  cmd | getline timestamp; close(cmd); \
  now=strftime("%s", systime()); \
  if (now - timestamp > 604800) print $1}' | \
  xargs -r zfs destroy

# Or manually: zfs destroy boot-pool@<snapshot-name>
```

### ✅ Step 2: Rotate System Logs (SAFE)

Compress or remove old system logs:

```bash
ssh root@10.10.0.100

# Check log directory size
du -sh /var/log/

# Force log rotation and cleanup
/usr/sbin/logrotate -f /etc/logrotate.conf

# Remove old rotated logs (> 30 days)
find /var/log -name "*.gz" -mtime +30 -delete
```

### ⚠️ Step 3: Clean Temporary Files (CAREFUL)

Only if Steps 1-2 don't free enough space:

```bash
ssh root@10.10.0.100

# Check temp directories
du -sh /tmp /var/tmp

# Remove old temporary files (> 7 days)
find /tmp /var/tmp -type f -mtime +7 -delete

# Note: Do NOT delete files currently in use
```

### 🚨 Step 4: Expand Virtual Disk (IF NEEDED)

If Steps 1-3 don't solve it, the system disk needs expansion.

**Prerequisites**: Proxmox credentials, comfortable with VM disk operations

```bash
# On Proxmox host (Ruapehu - 10.10.0.10)
# Backup current disk first (use Proxmox Backup)

# Resize disk from 32GB to 64GB
# Via Proxmox UI: Agentic → VMID 109 → Hardware → scsi0 → Resize Disk
# Or CLI: pvesm alloc local 109 vm-109-disk-0 +32G

# Inside TrueNAS VM: Grow the boot-pool
# (Requires TrueNAS web UI or zpool expand command)
```

---

## Expected Outcomes

### ✅ Success Criteria
- **Alert resolves**: Space drops below 80%
- **Performance unaffected**: No TrueNAS service degradation
- **Snapshots retained**: Keep critical ones (< 30 days old)

### ❌ Escalation Triggers
- Space still > 85% after cleanup
- Snapshots/logs cannot be safely deleted
- TrueNAS service becomes unresponsive
- Disk cannot be expanded in time

---

## Monitoring

### Prevent Recurrence

1. **Snapshot Retention Policy**
   - Auto-cleanup old snapshots via TrueNAS scheduled tasks
   - Set retention to 7-14 days for system snapshots

2. **Log Rotation**
   - Ensure `/etc/logrotate.conf` is configured
   - Check cron job: `0 3 * * * /usr/sbin/logrotate -f /etc/logrotate.conf`

3. **Proactive Alerts**
   - TrueNAS alert at 85% is good early warning
   - Plan expansion if trend is upward month-over-month

### Capacity Planning
- **Current**: 32GB VM disk, TrueNAS system only
- **Recommendation**: Monitor if usage grows > 3GB/month
- **Future expansion**: If steady-state > 70%, resize to 64GB

---

## Related Documentation

- **TrueNAS Architecture**: `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- **Proxmox Storage**: `/home/prod_homelab/infrastructure/terraform/proxmox.tf`
- **Infisical Secrets**: `/infrastructure/truenas-media/`

---

## Incident History

| Date | Alert | Space | Action | Status |
|------|-------|-------|--------|--------|
| 2026-03-14 | boot-pool 85% | ~27GB / 32GB | Investigation → cleanup | Pending |

---

**Last Updated**: 2026-03-14
**Owner**: Kernow Patrol
**Status**: Runbook created, awaiting SSH investigation
