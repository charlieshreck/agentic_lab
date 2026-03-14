# TrueNAS Scrub Operations

## Overview
ZFS scrubs are routine integrity checks that verify data consistency across all blocks in a pool. They run periodically and are expected maintenance operations, not errors.

## Expected Behavior
- **Duration**: Scrubs can take hours depending on pool size
- **Performance**: Disk I/O is elevated, which may degrade general performance temporarily
- **Completion**: Always show 0 errors on healthy pools
- **Alerts**: Auto-generated when scrub starts; resolve naturally on completion

## Pools & Schedules

### TrueNAS-media (10.10.0.100)
- **Tongariro**: ONLINE, status OK
- **Taranaki**: ONLINE, status OK

### TrueNAS-HDD (10.10.0.103)
- **Taupo**: ONLINE, status OK (62% fragmentation - monitor)
- **Tekapo**: ONLINE, status OK

## Boot-Pool Capacity Alert (85%)
- **Level**: NOTICE (informational)
- **Normal Range**: 75-90% is acceptable
- **Action Required**: None unless consistently > 90% for extended periods

## Incident Response
If a scrub alert is received:
1. Check pool status via MCP tools
2. Verify scrub state (should show FINISHED after hours)
3. Confirm error count (should be 0)
4. If finished with 0 errors → routine completion, resolve incident
5. If errors detected → investigate disk health and ZFS issues

## Monitoring
- Watch Taupo fragmentation (currently 35%) — consider defragmentation if > 50%
- Boot-pool at 85% is normal; escalate if > 95%
- All disks showing 0 read/write/checksum errors — system healthy

## References
- ZFS scrub lifecycle: `/root/.kube/config` cluster docs
- Taranaki capacity note: brief spikes to 85-88% are transient, don't escalate unless > 90% for > 1 hour
