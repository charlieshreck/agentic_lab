# Synapse LXC Memory Cleanup

**Last Updated**: 2026-03-19
**Status**: Active
**Cluster**: N/A (Synapse LXC - 10.10.0.22, 6GB RAM, no swap)

## Overview

Synapse LXC runs multiple services including Tamar (Express PWA), Redis, and hosts detached Claude Code screen sessions. Old detached sessions accumulate over time and can consume 2-3 GB of memory, causing memory pressure alerts around 85%.

## Root Cause

Claude Code instances running in screen/tmux sessions persist even after becoming detached. Without cleanup:
- **4 old sessions** found consuming ~2.3 GiB total
- `invest` session: 28 days old (02/19)
- `ai-business`: 7 days old
- `1m`: 6 days old
- `ai-business-wording`: 2 days old

**Incident #516** (2026-03-19): Synapse memory hit 87.3% (3.2 GiB of 6GiB), triggered alert.

## Resolution

### Immediate Fix
Kill all detached screen sessions:
```bash
for session in $(screen -ls 2>/dev/null | grep Detached | awk '{print $1}'); do
  screen -S "$session" -X quit
done
```

**Result**: Memory dropped from 87.3% to ~15% (3.2 GiB → 919 MiB freed).

### Permanent Fix
Automated daily cleanup via cron at 1 AM:
- **Script**: `/home/scripts/cleanup-screens.sh`
- **Cron**: `0 1 * * * /home/scripts/cleanup-screens.sh`
- **Policy**: Kill detached sessions older than **3 days**
- **Log**: `/var/log/screen-cleanup.log`

## Monitoring

Alert currently set at **85% memory**. After cleanup automation:
- Expected baseline: 20-30% (1.2-1.8 GiB used)
- Max spike: 50-60% (during Claude processing)
- Alert threshold: 85% should trigger cleanup before issues

## Manual Checks

Check memory and active sessions:
```bash
free -h                     # Overall memory
screen -ls                  # List all sessions
ps aux --sort=-%mem | head  # Top memory consumers
```

## Related

- **Services on Synapse**:
  - Tamar v1.0 (Express + React, systemd)
  - Redis (session store, db 3)
  - Various Node.js applications
  - Claude Code screen sessions
- **Incident**: #516 (2026-03-19)
- **Memory**: 6 GiB total, 0B swap
