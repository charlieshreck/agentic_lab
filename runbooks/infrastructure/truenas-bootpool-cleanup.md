# TrueNAS boot-pool Capacity Management

**Status**: Production
**Last Updated**: 2026-03-14
**Severity**: Warning (85% = action needed, 90%+ = critical)

## Problem

TrueNAS appliances (media and hdd instances) have a system pool called `boot-pool` that stores:
- TrueNAS OS and system files
- Configuration database (TrueNAS UI settings)
- System logs (syslog, TrueNAS UI logs, middleware logs)
- Temporary files and cache

Unlike data pools (Tongariro, Tekapo), the boot-pool has limited space and requires periodic cleanup.

## Detection

**Alert**: TrueNAS native alert fires when boot-pool capacity exceeds 80%

```bash
# Check from TrueNAS API
curl -s -H "Authorization: Bearer <TOKEN>" \
  https://<truenas-ip>:6000/api/v2.0/alert/list | \
  jq '.[] | select(.title | contains("boot-pool"))'
```

**Current Status** (TrueNAS-Media):
- Instance: VMID 109 (10.10.0.100)
- Boot-pool capacity: 85% (incident #473, 2026-03-14)

## Root Causes

1. **Log Accumulation** (Primary)
   - `/var/log/` grows without rotation
   - TrueNAS middleware logs not compressed
   - System journal retained indefinitely

2. **Database Growth** (Secondary)
   - TrueNAS SQLite database grows with history
   - Alert logs, stats, and event records accumulate

3. **Cache & Temp Files** (Tertiary)
   - `/var/tmp/` not cleaned
   - Browser/session cache in database

## Remediation Steps

### Immediate (Within 1 hour)

1. **SSH to TrueNAS**
   ```bash
   # From Synapse LXC (10.10.0.22)
   ssh root@10.10.0.100
   # Password: H4ckwh1z
   ```

2. **Identify what's consuming space**
   ```bash
   zfs list -r boot-pool
   du -sh /var/log/*
   du -sh /var/db/* | sort -h
   du -sh /var/tmp/*
   du -sh /* | sort -h  # Check all root dirs - /usr and /var/db are typical culprits
   du -sh /var/db/system/* | sort -h  # Check system database subdirs (look for large update/ or netdata/)
   ```

3. **Clean update cache and old database files** (safe, recoverable)
   ```bash
   # Remove old update images from /var/db/system/update/ (typically 1-2GB)
   rm -f /var/db/system/update/*.sqsh

   # Clean old netdata metrics (>30 days old)
   find /var/db/system/netdata -type f -mtime +30 -delete
   ```

4. **Clean logs** (safe, recoverable)
   ```bash
   # Compress old logs (older than 7 days)
   find /var/log -name "*.log" -mtime +7 -exec gzip {} \;

   # Delete very old logs (older than 30 days)
   find /var/log -name "*.log.gz" -mtime +30 -delete

   # Truncate current system log if it's large
   logrotate -f /etc/logrotate.conf
   ```

5. **Clean TrueNAS database** (via UI or CLI)
   ```bash
   # Via middleware
   middlewareconfig call alert.list | head -100  # Check alert count

   # Delete old alerts (if DB is the problem)
   # This typically requires TrueNAS maintenance task
   ```

6. **Verify**
   ```bash
   # Sync filesystem to ensure writes are complete
   sync

   # Check pool usage (may take a few seconds to update)
   zfs list boot-pool
   zpool list boot-pool  # Shows ALLOC, FREE, and CAP%
   ```

### Short-term (Within 1 week)

1. **Set up log rotation** in TrueNAS UI:
   - Navigate to System → Settings → Advanced
   - Configure log retention policies
   - Enable log compression for archived logs

2. **Expand boot-pool** (if cleanup doesn't help):
   - Requires Proxmox disk expansion of TrueNAS VM
   - Resize boot disk partition
   - Extend ZFS pool (see section below)

### Long-term (Ongoing)

1. **Configure automated cleanup**:
   ```bash
   # Add to crontab (SSH to TrueNAS)
   # Daily cleanup at 02:00 UTC
   0 2 * * * find /var/log -name "*.log.gz" -mtime +30 -delete
   ```

2. **Monitor proactively**:
   - Set alert threshold at 75% instead of 85%
   - Add to Update Patrol registry if monitoring external
   - Review every 30 days

## Boot-pool Expansion (Advanced)

If cleanup doesn't resolve the issue:

```bash
# 1. On Proxmox (10.10.0.178)
ssh root@10.10.0.178

# 2. Expand TrueNAS VM disk
qm resize 109 scsi0 +100G  # Add 100GB to boot disk

# 3. On TrueNAS, extend partition and ZFS pool
ssh root@10.10.0.100

# List partitions
parted -l

# Extend partition (be careful with sizes)
parted /dev/sda resizepart 1 200GB  # Adjust as needed

# Extend ZFS pool
zpool online -e boot-pool sda1

# Verify
zfs list boot-pool
```

## Monitoring Rules

Current alert (TrueNAS native): Triggers at 85%
Recommended improvement: Trigger at 75% (earlier warning)

To modify alert thresholds in TrueNAS UI:
1. System → Alert Services
2. Find "Pool usage" alert
3. Adjust to 75% threshold

## Related Incidents

- **#473 / Finding #1187** (2026-03-14): boot-pool at 85% on TrueNAS-Media
  - **Resolution**: Executed immediate cleanup (removed 1.8G update.sqsh cache, compressed/deleted old logs, cleaned old database files, cleaned netdata metrics)
  - **Outcome**: Freed ~1GB; boot-pool stabilized at 85% capacity (26.4G of 31G)
  - **Root Cause**: Boot-pool is size-constrained by design (31G total). OS (/usr) consumes 2.9G, system database 2.2G, rest is logs/cache. Cleanup provides marginal relief.
  - **Next Steps**: Long-term solution requires boot-pool disk expansion via Proxmox (see "Boot-pool Expansion" section)
- Monitor Taupo and Taranaki pools separately (data pools, handled differently)

## Infisical Access

Admin credentials stored at:
```
/infrastructure/truenas-media/  # If created
```

Currently using default credentials (H4ckwh1z) - should migrate to Infisical.

## References

- [TrueNAS Boot Pool Documentation](https://www.truenas.com/)
- [ZFS Pool Management](https://docs.freebsd.org/en/books/handbook/zfs/#zfs-administration)
- [Proxmox Disk Expansion](https://pve.proxmox.com/wiki/Resize_disks)
