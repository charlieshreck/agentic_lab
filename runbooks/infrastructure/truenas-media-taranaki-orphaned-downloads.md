# Runbook: TrueNAS-Media Taranaki Pool Saturation (Orphaned Downloads)

**Status**: Incidents #385, #386, #387 (2026-02-28, recurring)
**Severity**: Warning (88%) / Critical (96%)
**Auto-trigger**: At 88% pool usage (warning), 96% (critical)
**Root Cause**: Orphaned Transmission downloads + SABnzbd import failures in `/mnt/Taranaki/Tarriance/hopuhopu_katoa`

## Problem

The Taranaki ZFS pool on **TrueNAS-Media** (VM 109, IP 10.10.0.100) fills to 88-96% because:

1. **Transmission downloads to** `/mnt/Taranaki/Tarriance/hopuhopu_katoa` (93.8GB)
2. **Sonarr uses SABnzbd**, not Transmission (no import connection)
3. **Cleanuparr's DownloadCleaner** cannot delete because no imports trigger
4. **Old downloads accumulate** and never clean up

## Root Cause Analysis

| Component | What It Does | Issue |
|-----------|--------------|-------|
| Transmission | Downloads torrents to `/downloads` → `/mnt/Taranaki/Tarriance/hopuhopu_katoa` | No connection to Sonarr — orphaned forever |
| SABnzbd | Downloads usenet content to same staging area | Completed downloads not always cleaned after import |
| Sonarr | Imports from SABnzbd only | Ignores Transmission downloads entirely |
| Radarr | Imports from SABnzbd | Sometimes gets stuck in `importBlocked` state |
| Cleanuparr DownloadCleaner | Deletes files **after import** | No import events from Transmission = no cleanup |
| Cleanuparr QueueCleaner | Removes failed queue items (4 strikes, every 20 min) | Handles stuck SABnzbd imports but slowly |
| Tarriance (NFS) | Holds download folder | Only 230 GiB pool — too small for 4K content staging |

**Result**: Pool usage: ~100GB baseline (orphaned files) → 88-96% when large downloads (especially 4K) arrive.

### Pattern (observed 2026-02-28)
1. SABnzbd grabs multiple items (Futurama S01 batch + Shawshank 4K + FernGully 2)
2. Pool spikes to 88% → 96% during download phase
3. Sonarr/Radarr import most files to Tongariro pool (large media storage)
4. Some imports get stuck (`importBlocked`) — 1.4 GB FernGully 2 example
5. Pool drops back to ~44% after import, but orphaned files persist
6. Alert fires during spike, self-heals within hours

### Self-Healing Pattern
This alert **typically self-resolves** within 1-2 hours as arr apps import and move files.
Only investigate if pool stays above 85% for more than 2 hours.

## Diagnosis

```bash
# SSH to TrueNAS-Media (if accessible)
ssh root@10.10.0.100

# Check Tarriance dataset usage
zfs list -o name,used,avail Taranaki Taranaki/Tarriance

# List old files in download folder
ls -lht /mnt/Taranaki/Tarriance/hopuhopu_katoa | head -30

# Find files older than 7 days
find /mnt/Taranaki/Tarriance/hopuhopu_katoa -mtime +7 -type f
```

## Solutions

### Option 1: Manual Cleanup (Immediate)

Delete old orphaned downloads:

```bash
# SSH to TrueNAS-Media
ssh root@10.10.0.100

# List files by age
ls -lht /mnt/Taranaki/Tarriance/hopuhopu_katoa | tail -20

# Remove old files (older than 7 days)
find /mnt/Taranaki/Tarriance/hopuhopu_katoa -mtime +7 -type f -delete

# Verify space freed
zfs list Taranaki/Tarriance
```

**Caution**: Ensure Sonarr/Radarr are not actively importing these files. Check logs first.

### Option 2: Cleanup CronJob (DEPLOYED — 2026-03-04)

A daily CronJob is deployed that deletes files older than 7 days from the staging area.

**Status**: ✅ Deployed via GitOps (commit `e720d7c` in prod_homelab)
**Files**:
- `kubernetes/applications/media/cleanup-tarriance/cronjob.yaml`
- `kubernetes/argocd-apps/applications/cleanup-tarriance-app.yaml`
**Schedule**: Daily at 03:00 UTC

The CronJob:
1. Logs current usage before/after
2. Deletes files (`-type f`) older than 7 days
3. Removes empty directories left behind
4. Uses UID/GID 3000 (same as arr apps)

### Option 3: Connect Transmission to Sonarr/Radarr (Architectural Fix)

Configure Sonarr/Radarr to use Transmission for torrent downloads:

1. Open Sonarr UI → Settings → Download Clients
2. Add "Transmission" client pointing to `transmission.media.svc.cluster.local:9091`
3. Configure import path: `/downloads` (Transmission mount)
4. Set as primary download client (higher priority than SABnzbd)
5. Repeat for Radarr

This allows Cleanuparr to track and delete imports normally.

## Prevention

1. **Monitor pool usage**: Alert fires at 85% threshold
2. **Regular cleanup**: Cleanup CronJob deployed (Option 2) — deletes files >7 days old daily at 03:00 UTC
3. **Verify imports**: Ensure Sonarr/Radarr are importing correctly
4. **Check logs**: Look for import failures that might block cleanup

### Contributing Factors (Identified 2026-03-04, Incident #428)

**Huntarr `seasons_packs` mode**: Huntarr searches for missing content using `hunt_missing_mode: "seasons_packs"` in Sonarr. This grabs entire season packs (e.g., Mr. Robot S02 at 47 GB, Ghosts S01 at 27 GB) that can individually consume 20%+ of the 230 GB pool. Consider switching to `"episodes"` mode to grab individual episodes instead of full season packs.

**No Cleanuparr stall rules**: Cleanuparr has no `stallRules` configured. Torrents that stall at 0% progress (e.g., Mr. Robot S02 stopped at 0%, Nightmare Before Christmas at 0.1%) sit in the queue indefinitely, consuming queue slots and preventing other downloads. Add stall rules to auto-remove torrents with no progress after a configurable period.

**No Cleanuparr slow rules**: Cleanuparr has no `slowRules` configured. Extremely slow downloads (e.g., Hook 48 GB at 0 B/s) don't get cleaned up. Add slow rules to remove downloads below a minimum speed threshold after a grace period.

## SSH Access

SSH to TrueNAS-Media **IS accessible from Synapse LXC** (10.10.0.22):
```bash
ssh root@10.10.0.100  # TrueNAS-Media management IP
```
Note: The NFS interface is 10.40.0.10, but SSH management is on 10.10.0.100.

## Critical: Full Pool (100%) — Transmission and SABnzbd Stop

When pool hits **100%**, Transmission logs `No space left on device` and **stops ALL torrents**.
SABnzbd also pauses globally. All arr queue items show "warning" status.

**This does NOT self-heal** — completed downloads pile up without cleanup.

Diagnosis pattern when pool is 100%:
```bash
ssh root@10.10.0.100
du -sh /mnt/Taranaki/Tarriance/hopuhopu_katoa/*
# radarr/ and tv-sonarr/ folders likely contain completed but not-cleaned downloads
```

Resolution (seen 2026-03-04):
1. Check which completed downloads are already imported to Tongariro library
2. Delete imported files from radarr/ and tv-sonarr/ (safe if in library AND not seeding)
3. Resume SABnzbd via MCP: `mcp__media__sabnzbd_resume_queue`
4. Resume all Transmission torrents via MCP: `mcp__media__transmission_resume_torrent` for each ID

**Sonarr Import Failure Pattern**: Items in `tv-sonarr/` NOT in Tongariro library = Sonarr failed to import.
These files must NOT be deleted until Sonarr imports them. Investigate Sonarr logs.
Example: Pokemon Horizons S01 (85 episodes, ~55 GB) sat for 5+ weeks without import (found 2026-03-04).

## Related Issues

- **Incident #160**: Ruapehu memory pressure (similar resource saturation pattern)
- **Incidents #385, #386, #387**: Same-day recurrence (2026-02-28) — all self-healed
- **Finding #1056** (2026-03-04): Pool hit 100%, all downloads stopped. Fixed by deleting Matrix (66GB) + Shaun (13GB) + Dirk Gently (12GB) — all confirmed imported. Pokemon Horizons (85 eps, ~55 GB) + Hostage S01 (7.9 GB) NOT imported — needs Sonarr investigation.
- **Finding #1001** (2026-03-04): "A Shaun the Sheep Movie Farmageddon 2019 UHD Bluray 2160p" completed in Transmission but not cleaned by Cleanuparr (unlinked from Radarr queue). Pool was at 96% when detected. Systemic fix: cleanup CronJob deployed (commit `e720d7c`).
- **Incident #428** (2026-03-04): Pool spiked to 96%, self-healed to 57%. Root cause: massive download queue (15 Transmission torrents totaling ~294 GB + 16 SABnzbd items at 43 GB) exceeding pool capacity. SABnzbd auto-paused. Identified Huntarr `seasons_packs` mode and missing Cleanuparr stall/slow rules as contributing factors.
- **Known issue (2026-02-23)**: TrueNAS-Media NFS permissions broken for some UIDs (may prevent imports)

## References

- TrueNAS-Media: VMID 109, IP 10.10.0.100
- Tarriance NFS: `10.40.0.10:/mnt/Taranaki/Tarriance/hopuhopu_katoa`
- Cleanuparr: media namespace, enabled (queue cleaner every 20 min, download cleaner hourly)
- Sonarr: Uses SABnzbd (Usenet), NOT Transmission
- Radarr: Uses SABnzbd (confirmed 2026-02-28) — can get stuck in `importBlocked` state
