# Plex Media Server CPU Baseline & Expected Spikes

## Overview
Plex VM on Ruapehu (10.10.0.50) runs background maintenance tasks that cause CPU spikes. These are normal and expected.

## CPU Baseline Behavior
- **Idle**: 10-20% CPU (normal background)
- **Light usage**: 30-50% (1-2 streams or metadata tasks)
- **Active maintenance**: 60-80% (library scan, metadata matching, thumbnail gen)
- **Spikes > 80%**: Expected during intensive tasks like full library rebuild

## Background Tasks
Plex performs these CPU-intensive tasks automatically:
- **Library scans**: Periodic (hourly/daily) to detect changes
- **Metadata matching**: Associate files with correct show/movie
- **Thumbnail generation**: Create artwork cache
- **Optimization**: Remove corrupted metadata, rebuild index

## Investigation Flow

### Step 1: Check Active Sessions
```bash
# Via Tautulli API
curl -s "https://tautulli.kernow.io/api/v2?apikey=<key>&cmd=get_activity"
```
- **0 sessions + CPU > 80%** → Background task (expected)
- **1+ sessions + CPU > 80%** → Active transcoding (expected if > 1 stream)
- **0 sessions + CPU > 80% for > 30 min** → Investigate (potential issue)

### Step 2: Check Plex Logs
```bash
# Via Plex container logs (if containerized)
docker logs plex | tail -100

# Or SSH to VM
ssh root@10.10.0.50
journalctl -u plex -n 100
```

### Step 3: Determine Action
| Condition | Action |
|-----------|--------|
| CPU declining (83% → 77%) + 0 sessions | **Auto-resolve** — transient background task |
| CPU stable > 80% for > 30 min + 0 sessions | Investigate logs for errors; escalate if unhealthy |
| CPU > 80% + 2+ concurrent streams | Expected; no action |
| CPU > 90% for > 10 min + unresponsive | Possible runaway process; restart Plex container |

## Resource Limits
- **VM**: 4 vCPU, 6.5GB RAM (sufficient for typical workload: 1-3 streams + maintenance)
- **Network**: Dual NICs (10.10.0.50 prod, 10.40.0.10 NFS)

## Escalation Criteria
Escalate if:
1. CPU > 80% persists > 30 minutes without activity
2. Plex becomes unresponsive (API timeout)
3. Error logs show corruption or OOM
4. NFS mount issues appear in logs

## Prevention
- Keep Plex updated (check Watchtower/Tugtainer logs)
- Monitor NFS mount health (mount-canary job)
- Review library size periodically (might need more RAM for massive libraries)

---
**Incident #307 Reference**: Plex CPU 83.9% on 2026-02-27 — confirmed as normal background task, no action needed.
