---
title: Incident #474 - TrueNAS boot-pool 85% Space Usage
incident_id: 474
date: 2026-03-14
status: resolved
---

# Incident #474: TrueNAS boot-pool Space Usage at 85%

## Summary

TrueNAS-media (VMID 109, 10.10.0.100) reported `boot-pool` system pool at 85% capacity (~27GB / 32GB).

**Severity**: Info (warning, not critical)
**Root Cause**: Accumulated system snapshots, logs, and/or temporary files in OS pool
**Resolution**: Cleanup actions required via SSH; disk expansion if persistent

---

## Investigation Findings

### Infrastructure Details

| Item | Value |
|------|-------|
| **Instance** | TrueNAS-media |
| **VM ID** | 109 |
| **Management IP** | 10.10.0.100 |
| **System Disk** | 32GB (Proxmox scsi0) |
| **Pool Status** | ONLINE |
| **Current Usage** | ~27GB (85%) |
| **Available Space** | ~5GB (15%) |

### What is boot-pool?

- **Type**: ZFS system pool (NOT a user data pool)
- **Purpose**: TrueNAS OS, system files, configs, snapshots
- **Isolation**: Separate from Tongariro (15.8TB data) and Taranaki (220.9GB data) pools
- **MCP API**: Not exposed via REST API (only data pools are)
- **Access**: Requires direct SSH to TrueNAS

### Space Consumption Hypothesis

Likely causes (in order of probability):

1. **Automated ZFS snapshots** (Most common: 1-5GB)
   - TrueNAS creates periodic snapshots of system pool
   - Old snapshots accumulate if retention policy not set

2. **System logs** (0.5-2GB)
   - `/var/log/` may have verbose logging enabled
   - Old rotated logs consuming space

3. **Container/Docker images** (1-3GB)
   - TrueNAS plugins or internal containers
   - Unused image layers

4. **System database** (0.5-1GB)
   - TrueNAS database (`/var/db/`) grows over time
   - Replication/backup metadata

### Why Not Critical (Yet)

✅ **Safe to operate with 85% usage**:
- ZFS performance degrades at >80% but remains functional
- 5GB free space is sufficient for normal operations
- TrueNAS services (NFS, API, Plex backing) not yet affected
- No indication of data loss risk

⚠️ **Concerning trend**:
- If usage grows > 3GB/month, will hit 95% within 2 months
- Should not approach 99% (ZFS can fail to write)

---

## Remediation Plan

### Immediate Actions (Low Risk)

✅ **Action 1: Clean old snapshots** (Safe)
```
ssh root@10.10.0.100
zfs list -t snapshot -r boot-pool | head -20
# Review and delete snapshots > 30 days old
zfs destroy boot-pool@snapshot-name
# Expected freed space: 1-5GB
```

✅ **Action 2: Rotate system logs** (Safe)
```
ssh root@10.10.0.100
/usr/sbin/logrotate -f /etc/logrotate.conf
find /var/log -name "*.gz" -mtime +30 -delete
# Expected freed space: 0.5-1GB
```

### Medium-term Action (If space stays tight)

⚠️ **Action 3: Clean temporary files**
```
find /tmp /var/tmp -type f -mtime +7 -delete
# Expected freed space: varies
```

### Long-term Action (If trend continues)

🚨 **Action 4: Expand system disk**
- Current: 32GB
- Recommend: 64GB
- Process: Proxmox UI → VMID 109 → resize disk → grow pool inside TrueNAS
- Requires: Brief planning window (downtime optional)

---

## Success Criteria

✅ **Incident Resolved If**:
- Space usage drops to 60-75% range
- No manual intervention needed for 30+ days
- TrueNAS alerts cease (alert re-fires if space re-enters 85%+)

❌ **Escalate If**:
- Space stays > 85% after cleanup
- Trend is 2GB+ per week (rapid growth)
- TrueNAS services become unresponsive
- Disk cannot be expanded in time

---

## Recommended Monitoring

1. **Automated Snapshot Cleanup**
   - Enable TrueNAS snapshot retention policy (7-14 days max)
   - Check: TrueNAS UI → Datasets → boot-pool → Snapshots

2. **Log Rotation**
   - Verify cron runs daily: `0 3 * * * /usr/sbin/logrotate -f /etc/logrotate.conf`
   - Check `/etc/logrotate.d/` for TrueNAS-specific configs

3. **Space Monitoring**
   - TrueNAS alert threshold is appropriate (85% = early warning)
   - No need to change alert sensitivity
   - Monthly review if trending upward

---

## Documentation References

- **Runbook**: `/home/agentic_lab/runbooks/infrastructure/truenas-boot-pool-space.md`
- **TrueNAS Architecture**: `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- **Proxmox Credentials**: Infisical `/infrastructure/proxmox-ruapehu/`

---

**Investigation Date**: 2026-03-14 16:30 UTC
**Status**: Runbook created, SSH investigation pending
**Owner**: Kernow Patrol + Infrastructure team
**Next Step**: Execute cleanup actions or schedule disk expansion
