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

### Option 2: Create Cleanup CronJob (Permanent)

Deploy a Kubernetes CronJob to periodically delete old downloads:

**File**: `/home/prod_homelab/kubernetes/applications/media/cleanup-tarriance-cronjob.yaml`

```yaml
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cleanup-tarriance-old-downloads
  namespace: media
spec:
  # Run daily at 02:00 UTC (off-peak)
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: cleanup
            image: busybox:1.36
            command:
            - /bin/sh
            - -c
            - |
              echo "Removing Tarriance downloads older than 7 days..."
              find /downloads -mtime +7 -type f -exec rm -v {} \;
              echo "Cleanup completed. Current usage:"
              du -sh /downloads
            volumeMounts:
            - name: downloads
              mountPath: /downloads
          volumes:
          - name: downloads
            nfs:
              server: 10.40.0.10
              path: /mnt/Taranaki/Tarriance/hopuhopu_katoa
```

Deploy:
```bash
kubectl -C /home/prod_homelab apply -f kubernetes/applications/media/cleanup-tarriance-cronjob.yaml
```

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
2. **Regular cleanup**: Run manual cleanup monthly OR deploy CronJob
3. **Verify imports**: Ensure Sonarr/Radarr are importing correctly
4. **Check logs**: Look for import failures that might block cleanup

## Known Limitation

**SSH to TrueNAS-Media is unreachable from Synapse LXC** (10.10.0.22). Port 22 is closed.
Manual cleanup requires SSH from Ruapehu (10.10.0.10) which can reach the VM directly.

## Related Issues

- **Incident #160**: Ruapehu memory pressure (similar resource saturation pattern)
- **Incidents #385, #386, #387**: Same-day recurrence (2026-02-28) — all self-healed
- **Known issue (2026-02-23)**: TrueNAS-Media NFS permissions broken for some UIDs (may prevent imports)

## References

- TrueNAS-Media: VMID 109, IP 10.10.0.100
- Tarriance NFS: `10.40.0.10:/mnt/Taranaki/Tarriance/hopuhopu_katoa`
- Cleanuparr: media namespace, enabled (queue cleaner every 20 min, download cleaner hourly)
- Sonarr: Uses SABnzbd (Usenet), NOT Transmission
- Radarr: Uses SABnzbd (confirmed 2026-02-28) — can get stuck in `importBlocked` state
