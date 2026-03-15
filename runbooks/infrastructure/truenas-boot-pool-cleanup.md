# Runbook: TrueNAS boot-pool Space Management

**Status**: Active (2026-03-15)
**Severity**: Info → Warning (>85% full)
**Auto-trigger**: Pool reaches 85% capacity
**Root Cause**: Multiple ZFS boot environments (old OS versions) consume space

## Problem

The TrueNAS-Media boot-pool (system partition) fills up when multiple boot environments (BE) accumulate from OS upgrades. Each BE is a full snapshot of `/` (e.g., 2.3-2.9 GB each).

**Example**:
- Current: TrueNAS 25.10.0.1 (3.07 GB)
- Old: 25.10.0, 25.04.2.4, 25.04.1, 24.04.2.5, 24.04.1.1, 23.10.2, 23.10.1.3, 23.10.1 (each 2.3-2.8 GB)
- **Total**: 26.4 GB used in 31 GB pool = **85% full** ⚠️

TrueNAS keeps old boot environments for rollback, but older versions (>2 major releases) can be safely deleted.

---

## Diagnosis

### Check boot-pool usage
```bash
ssh root@10.10.0.100
zfs list boot-pool
zfs list -r boot-pool/ROOT
```

### Identify current boot environment
```bash
mount | grep "boot-pool/ROOT" | head -1
# Output: boot-pool/ROOT/25.10.0.1 on / type zfs (...)
```

### Check individual BE sizes
```bash
zfs list -o name,used boot-pool/ROOT
```

---

## Solution: Delete Old Boot Environments

### Safe Cleanup
Keep only the **current BE** and **one older BE** as backup. Delete all others older than 2 major releases.

```bash
# SSH to TrueNAS-Media
ssh root@10.10.0.100

# Identify current BE (will be mounted on /)
mount | grep "boot-pool/ROOT" | head -1

# Delete old BEs (adjust names based on your output)
# NEVER delete the one shown in the mount output above!
zfs destroy -r boot-pool/ROOT/<old-be-name>
zfs destroy -r boot-pool/ROOT/<old-be-name>
# ... repeat for each old BE

# Verify cleanup
zfs list -o name,used boot-pool
```

### Automated Cleanup (DEPLOYED)
A daily CronJob in the monit cluster runs ZFS BE cleanup at 02:00 UTC.

**Manifest**: `monit_homelab/kubernetes/platform/truenas-cleanup/cronjob.yaml`
**Action**: Deletes boot environments older than 2 major releases
**Status**: ✅ Deployed (2026-03-15, commit TBD)

---

## Example: Incident #1205 Resolution (2026-03-15)

**Initial State**:
- boot-pool: 26.4 GB used / 31 GB total = **85% full**
- Available: 3.62 GB

**Old Boot Environments Deleted**:
- boot-pool/ROOT/23.10.1 (2.37 GB)
- boot-pool/ROOT/23.10.1.3 (2.38 GB)
- boot-pool/ROOT/23.10.2 (2.41 GB)
- boot-pool/ROOT/24.04.1.1 (2.39 GB)
- boot-pool/ROOT/24.04.2.5 (2.57 GB)
- boot-pool/ROOT/25.04.1 (2.75 GB)
- boot-pool/ROOT/25.04.2.4 (2.79 GB)
- boot-pool/ROOT/25.10.0 (2.99 GB)

**Space Freed**: 20.66 GB

**Final State**:
- boot-pool: 5.74 GB used / 31 GB total = **19% full** ✅
- Available: 24.3 GB

---

## Prevention

### Monitoring
- Boot-pool is monitored via Coroot/AlertManager
- Alerts fire at 85% (warning) and 95% (critical)

### Retention Policy
Keep:
- ✅ Current boot environment (active system)
- ✅ One previous major version (rollback safety)
- ❌ Delete all others older than 2 major releases

Example (TrueNAS 25.10.0.1 active):
- Keep: 25.10.0.1 (current), 25.04.2.4 (previous)
- Delete: 25.04.1, 24.04.x, 23.10.x (too old)

### Schedule
- Manual cleanup when alert fires (>85%)
- CronJob runs daily at 02:00 UTC (automated cleanup)
- Post-upgrade verification: check pool usage after TrueNAS updates

---

## Technical Details

### Why Multiple Boot Environments?
TrueNAS ZFS layout for system:
```
boot-pool/ROOT/
├── 25.10.0.1 (current)   ← mounted on /
├── 25.10.0               ← previous point release
├── 25.04.2.4             ← previous major release
└── ... older versions
```

Each BE is a full ZFS dataset snapshot (not incremental). Safe to delete old ones after verifying the system boots correctly with the new version.

### Why Not Snapshots?
TrueNAS also creates snapshots of boot environments during upgrades, but these are auto-cleaned and NOT the primary issue here. The issue is the full replicated boot environments themselves.

---

## Related Issues

- **Incident #1205** (2026-03-15): boot-pool at 85%, resolved by deleting 8 old BE
- **Taranaki pool saturation**: Different issue (media download staging area) — see `truenas-media-taranaki-orphaned-downloads.md`

---

## References

- **TrueNAS-Media**: VMID 109, IP 10.10.0.100 (management)
- **boot-pool**: 31 GB system partition (Debian base + BE history)
- **Taranaki pool**: 230 GB media staging (separate issue)
- **Tongariro pool**: 21.8 TB media library (healthy, 70% used)
