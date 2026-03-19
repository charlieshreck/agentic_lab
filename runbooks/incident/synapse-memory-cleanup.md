# Synapse LXC Memory Management & Cleanup

**Last Updated**: 2026-03-19
**Severity**: Warning-level memory pressure
**Status**: RESOLVED (2026-03-19)

## Summary

Synapse LXC (VMID 100 on Hikurangi, 10.10.0.22) has a fixed 6 GB RAM allocation with no swap. Memory pressure occurs when multiple long-lived Claude Code screens accumulate without cleanup.

## Root Cause

- **6 GB RAM hard limit** (no swap configured)
- **Claude Code screens** consume 150-1000 MB each (8-16 instances typically running)
- **Tamar PWA service** permanently consumes ~700 MB
- **No automated screen cleanup** — screens persist indefinitely until manually killed
- **Alert threshold**: 85% (warning), ~5.1 GiB used

## Incident History

### 2026-03-19: Memory Alert #516

**Trigger**: Alert pulse detected 87.3% memory usage (threshold: 85%)

**Investigation**:
- 6 detached screens: troubleshooting (450M), albie (415M), backups (100M), t-shoot (450M), ai-business (400M), plus 2 active screens
- Tamar + Next.js dev server + Redis = 830M combined
- Total: 5.2 GB / 6 GB = 86.5%

**Resolution**:
- Killed 4 old detached screens (>7 days old): freed **1.1 GB**
- Memory dropped to **68.3%** ✓
- No service interruption (only old detached screens removed)
- Remaining active work screens (< 7 days) preserved

**Changes**:
```bash
screen -S troubleshooting -X quit  # 450 MB
screen -S albie -X quit             # 415 MB
screen -S backups -X quit           # 100 MB
screen -S t-shoot -X quit           # 450 MB
```

## Prevention

### Recommended: Add Automated Screen Cleanup

Add to crontab (runs daily at 2:00 AM):
```bash
# Clean detached screens older than 7 days
0 2 * * * find /run/screen/S-root -type s -mtime +7 2>/dev/null | while read sock; do screen -S "$(basename "$sock")" -X quit 2>/dev/null; done
```

### Manual Cleanup (if cron not set)

```bash
# List all screens with age
screen -ls

# Kill specific screen
screen -S <screenname> -X quit

# Kill all detached screens older than 7 days (manual)
find /run/screen/S-root -type s -mtime +7 2>/dev/null | while read sock; do \
  screen -S "$(basename "$sock")" -X quit 2>/dev/null; \
done
```

## Capacity Planning

**Current allocation**: 6 GB (no swap)

**Usage baseline**:
- Tamar PWA: 700 MB (always-on)
- Redis: 5 MB (session cache)
- OS + utilities: 300 MB
- Available for Claude screens: **~5 GB**

**Safe threshold**: Keep memory below 75% (4.5 GB)

### If Memory Pressure Persists

**Option 1**: Increase LXC RAM to 8 GB
- Terraform: `/home/prod_homelab/infrastructure/terraform/synapse-lxc.tf`
- Update: `memory = 8192`
- Requires Hikurangi host capacity check (currently 11.4 GB total)

**Option 2**: Implement session limits
- Limit concurrent Claude Code screens to 3 active + 1 inactive
- Tamar server can enforce this via session manager

**Option 3**: Move Tamar to dedicated LXC
- Reduces Synapse footprint to ~300 MB, allowing more Claude Code screens
- Requires DNS/routing updates

## Monitoring

**No Prometheus node-exporter currently running on 10.10.0.22.**

To add metrics:
```bash
# On Synapse LXC
apt-get install prometheus-node-exporter
systemctl enable prometheus-node-exporter
systemctl start prometheus-node-exporter

# Update scrape config in observability-mcp or Prometheus
```

## Related Alerts

- **#516** (2026-03-19): Container memory at 87.3% — RESOLVED
- **Alert rule**: `node_memory_MemAvailable_bytes < 0.15 * node_memory_MemTotal_bytes`

## Testing

After cleanup, verify:
```bash
free -h                              # Should show ~70% usage
ps aux --sort=-%mem | head -10       # No unexpected processes
systemctl status tamar.service       # Still running
redis-cli ping                       # Should respond PONG
```

## References

- Synapse LXC specs: `/home/.claude/projects/-home/memory/MEMORY.md`
- Infrastructure: `/home/prod_homelab/infrastructure/terraform/synapse-lxc.tf`
- Tamar service: `/home/tamar/server.js` (Express.js PWA)
