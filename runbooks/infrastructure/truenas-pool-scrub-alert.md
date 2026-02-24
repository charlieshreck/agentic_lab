# TrueNAS Pool Scrub Alert Runbook

## Alert: Scrub of pool 'boot-pool' has started

**Source**: TrueNAS monitoring system
**Severity**: INFO (expected maintenance)
**Instances**: TrueNAS-HDD, TrueNAS-Media
**Pool**: Internal system pool (boot-pool)

## What's Happening

TrueNAS automatically schedules routine ZFS pool scrubs as part of data integrity maintenance. This alert fires when a scrub operation begins.

### Normal Behavior
- **Frequency**: Monthly or based on TrueNAS maintenance schedule
- **Duration**: 30 minutes to several hours (depends on pool size)
- **Expected State**: `state: FINISHED` after completion (not hanging in progress)
- **Performance Impact**: Expected temporary I/O performance degradation (normal for ZFS)
- **Data Loss Risk**: None (scrub is read-only verification)

## Root Cause

This is a **routine maintenance operation**, not an error condition.

**Why it matters**: ZFS scrub verifies all data blocks against their checksums, catching silent data corruption before it spreads. TrueNAS initiates scrubs automatically.

## Investigation Protocol

### Step 1: Verify Scrub State

```bash
# Check if scrub is FINISHED or still running
truenas_list_pools(instance="hdd")

# Expected output (FINISHED):
{
  "name": "Taupo",
  "scan": {
    "function": "SCRUB",
    "state": "FINISHED",  # ← Not "IN PROGRESS"
    "errors": 0           # ← No data integrity issues
  }
}
```

### Step 2: Check Pool Health

```bash
truenas_get_alerts(instance="hdd")

# Expected: Empty array (no active issues)
# If alerts exist: Investigate specific error message
```

### Step 3: Verify No Performance Issues

```bash
# Check if services are degraded
# - Plex playback working?
# - NFS mounts responsive?
# - Kubernetes backups completing?

# If all services normal despite "Performance may be degraded" message:
# This is expected transient impact, no action needed
```

## When to Escalate vs Auto-Resolve

### ✅ AUTO-RESOLVE If:
- Scrub state is `FINISHED`
- Zero errors (`errors: 0`)
- Pool health is `OK`
- No active TrueNAS alerts
- All dependent services operational

**Action**: Resolve as "routine maintenance completed"

### 🚨 INVESTIGATE If:
- Scrub state is `IN PROGRESS` for > 12 hours (stuck)
- Errors > 0 (data corruption detected)
- Pool health is `DEGRADED` or `OFFLINE`
- Active TrueNAS alerts other than scrub notification
- Services actually unreachable (Plex down, NFS hung)

**Action**: Check physical connectivity, disk health, ZFS pool status

## Alert Configuration Issue

**Note**: This alert is triggering repeatedly (incidents #100, #219, #220) because:

1. TrueNAS alert fires when scrub **starts**
2. Alert system logs it as incident
3. TrueNAS alert does **not** auto-resolve when scrub **finishes**
4. Patrol needs to manually verify completion and resolve

**Improvement**: Configure alert system to either:
- Only alert on scrub **errors** (not start/finish)
- Auto-resolve when `state: FINISHED` detected
- Suppress routine maintenance notifications

## Related Documentation

- **TrueNAS Architecture**: `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- **ZFS Pool Management**: Taupo and Tekapo pools on TrueNAS-HDD
- **Backup Operations**: `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md`

## Incident History

| Date | Pool | State | Errors | Action |
|------|------|-------|--------|--------|
| 2024-11-24 | Taupo | FINISHED | 0 | Auto-resolved (routine) |
| 2026-02-14 | TrueNAS-Media | (stale) | 0 | Auto-resolved |
| 2026-02-24 | TrueNAS-HDD | FINISHED | 0 | Auto-resolved |

## Summary

**This is not a problem to fix.** It's expected routine maintenance that has already completed. Simply verify the scrub finished successfully and resolve the incident.

Recommend improving alert system to auto-suppress or auto-resolve routine maintenance notifications.

---

**Last Updated**: 2026-02-24
**Owner**: Kernow Patrol Agent
**Status**: Expected pattern (no action required)
