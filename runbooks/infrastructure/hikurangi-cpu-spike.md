# Runbook: Hikurangi CPU Spike

## Alert
- **Name**: cpu - Hikurangi
- **Source**: Beszel (via pulse sweep)
- **Threshold**: > 80% CPU
- **Severity**: Critical when > 95%

## Architecture

Hikurangi is a Proxmox host (10.10.0.178) with **4 physical CPU cores** and ~12GB RAM.

### LXC Containers

| VMID | Name | Allocated Cores | Purpose |
|------|------|----------------|---------|
| 100 | synapse | 2 | Claude Code, Tamar PWA, patrol agent |
| 101 | haute-banque | 4 | Investmentology CLI agents (Claude + Gemini) |
| 102 | tamar-test | 2 | Archived test environment |
| 103 | capture-creature | 1 | Capture Creature app |

**Total allocated: 9 cores on 4-core host (2.25x overcommit)**

This overcommit is intentional — most LXCs are idle most of the time. But when multiple Claude Code sessions become active simultaneously, they can saturate all 4 physical cores.

## Root Cause Pattern

The primary cause of Hikurangi CPU spikes is **multiple Claude Code processes running concurrently**:

1. **Synapse LXC** typically has 3-5 screen sessions, each potentially running a `claude` process
2. **HB LXC** runs `claude-invest` and `gemini-invest` screen sessions
3. **Stale sessions** accumulate over days/weeks, consuming memory and occasionally spiking CPU
4. When patrol agent + overnight pipeline + any interactive session overlap, CPU hits 99%

### Key Indicators
- Check `ps aux | grep claude` on Hikurangi host to see all Claude processes across all LXCs
- Each idle Claude process uses 200-400MB RSS; active ones can use 1-1.4GB
- Stale sessions (> 3 days old) should be considered for cleanup

## Investigation Steps

### 1. Verify Current State
```bash
# SSH to Hikurangi
ssh root@10.10.0.178

# Check current load and CPU
uptime
top -bn1 | head -5

# List all Claude processes
ps aux | grep -E 'claud[e]' | awk '{printf "PID=%s CPU=%s MEM=%s RSS=%sMB START=%s\n", $2, $3, $4, $6/1024, $9}'
```

### 2. Map Processes to LXCs
```bash
# For each PID, check which LXC it belongs to
cat /proc/<PID>/cgroup | head -1
# Look for /lxc/<VMID>/ in the path
```

### 3. Check Screen Sessions
```bash
# Synapse screens
pct exec 100 -- screen -ls

# HB screens
pct exec 101 -- screen -ls
```

### 4. Check Per-LXC CPU
```bash
# Via Proxmox API or pct status
for ct in 100 101 102 103; do
  echo -n "CT $ct: "
  pct status $ct | grep -E 'cpu|status'
done
```

## Resolution

### If Self-Healed (current CPU < 50%)
The spike was caused by transient concurrent activity. Resolve as transient but check for stale sessions.

### Clean Up Stale Sessions (Synapse)
**Ask user before killing sessions** — they may contain work-in-progress.

Stale indicators:
- Screen session age > 7 days with no recent activity
- Claude process RSS > 1GB and started > 3 days ago
- Multiple detached screens with no TTY attached

### Reduce Overcommit (Longer-term)
Consider reducing tamar-test (102) cores from 2 to 1, since it's archived.
Consider setting `cpulimit` on LXCs to cap burst usage.

## Known Patterns

| Pattern | Resolution |
|---------|-----------|
| Spike during overnight pipeline (02:00 UTC) | Transient — HB claude-invest + patrol overlap |
| Spike when multiple patrol/albie sessions active | Transient — clean stale sessions |
| Sustained > 80% for > 30 minutes | Investigate — likely a stuck Claude process |

## Related
- Incident #444 (2026-03-04): First occurrence, self-healed
- Incident #443 (2026-03-04): Companion HB LXC CPU spike
- Runbook: `proxmox-high-memory-pressure.md` — related resource issue on Ruapehu
