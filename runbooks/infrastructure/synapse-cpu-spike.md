# Synapse LXC CPU Spike

## Alert
- **Source**: KAO/error-hunter via Beszel agent metrics
- **Metric**: Container CPU utilization on Synapse LXC (10.10.0.22)
- **Threshold**: 80% (warning)
- **Typical spike**: 80-90%+ when multiple AI inference processes active

## Synapse Profile
- **VMID**: 100 on Hikurangi (10.10.0.178)
- **vCPUs**: 2
- **RAM**: 6GB
- **Role**: Claude Code LXC — runs Tamar PWA, screen sessions, patrol loops, MCP servers

## Root Cause Pattern

Synapse is a 2-vCPU LXC hosting multiple persistent `claude` processes via `screen` sessions.
CPU spikes occur when one or more of these processes performs AI inference (streaming API calls).

### Known persistent processes
```
screen -ls
```
Expected screens:
- `patrol` — rotating patrol agent sessions
- `invest` — investmentology overnight pipeline
- `backups` — backup monitoring
- `troubleshooting` — may be stale if old (check age)

### Check process age and CPU usage
```bash
ps aux --sort=-%cpu | grep claude | head -10
# Check elapsed time:
ps -p <PID> -o pid,pcpu,pmem,etime,cmd
# Check cumulative CPU:
cat /proc/<PID>/schedstat
```

## Investigation Steps

### Step 1: Check current state
```bash
top -bn1 | head -20
uptime
```
If CPU is now idle (>80% idle), the spike was transient.

### Step 2: Identify offending processes
```bash
ps aux --sort=-%cpu | head -15
```
Look for `claude` or `node` processes at high CPU%.

### Step 3: Check for stale screen sessions
```bash
screen -ls
# Check age of each session
ps aux | grep claude | grep -v grep
# A session > 3 days old with accumulated CPU time is likely stale
```

Stale sessions to look for:
- `troubleshooting` screen older than 2-3 days — likely stale, can be killed
- `invest` screen running during off-hours — may be stale outside 02:00-06:00 UTC

### Step 4: Identify if spike is during patrol/analysis
The patrol loop runs periodically. A CPU spike during 02:00-04:00 UTC is expected if:
- Overnight investmentology pipeline is running
- Patrol agent is doing LLM analysis

## Resolution

### If spike has cleared (transient)
- Verify current CPU is normal
- Note which sessions are long-running
- Auto-resolve as transient

### If stale sessions identified
Stale sessions accumulate memory (20-25% each) and cause occasional spikes.
To clean up a stale `troubleshooting` screen:
```bash
# Check what's in the screen first
screen -r troubleshooting
# If truly idle/stale, exit the claude process inside (Ctrl+C, then exit)
# Or kill the session
screen -X -S troubleshooting quit
```

### If CPU is consistently high (not transient)
1. Check if Tamar server.js is looping:
   ```bash
   ps aux | grep "node server.js"
   ```
2. Check if patrol loop is stuck:
   ```bash
   cat /tmp/patrol-loop.sh
   ```
3. Check Redis:
   ```bash
   redis-cli ping
   redis-cli info stats | grep total_commands_processed
   ```

## Memory Pressure Warning

Long-running `claude` processes consume ~20-25% RAM each (~1.2-1.5GB).
With 6GB total and 2+ old claude processes, memory can get tight.

```
Free RAM check:
free -h

If available < 1GB, consider cleaning up old screen sessions.
```

## Prevention

- Patrol screen sessions are short-lived by design (rotate per task)
- Invest screen is expected to persist during pipeline windows
- Troubleshooting screens should be manually cleaned up after use
- Consider: restart Synapse LXC periodically (monthly) to clear stale processes

## Alert Threshold Assessment

80% on a 2-vCPU LXC is appropriate — this is a shared resource LXC.
If alerts are too frequent, consider:
1. Cleaning up stale sessions first
2. Raising threshold to 90% if patrol activity is legitimately high
3. Adding a duration requirement (e.g., only alert if >80% for 5+ minutes)
